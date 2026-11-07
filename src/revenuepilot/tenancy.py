"""Organizations, memberships, RBAC and tenant-scoped resources (PASUL 11).

In-memory reference implementation; persistence arrives at PASUL 12 and must keep
these rules. Invariants:

* The tenant is never accepted from the caller: every operation takes an
  AccessContext built server-side from the session and the *current* membership.
* Resources are keyed by (tenant_id, local_id). Local IDs are per-tenant counters,
  so the same ID exists in different tenants; a lookup can only ever reach the
  caller's tenant partition.
* Every operation checks a named permission against the role held *now*; a
  revoked or changed membership invalidates contexts built before the change.
* Not found and not visible are indistinguishable (no cross-tenant enumeration).
* Every authorization decision is audited (allow and deny), without content.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import secrets
import threading
import time
from typing import Callable

from .observability import current_trace_id

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    # Conjunctive and explicit: no role inherits another role's permissions.
    "viewer": frozenset({"resource.read"}),
    "editor": frozenset({"resource.read", "resource.create", "resource.update_own", "resource.delete_own", "resource.grant_own"}),
    "approver": frozenset({"resource.read", "resource.approve"}),
    "admin": frozenset({"resource.read", "export", "membership.manage"}),
}
KINDS = frozenset({"brief", "campaign", "memory"})
VISIBILITIES = frozenset({"tenant", "private"})
MAX_TEXT = 2000


class AccessDenied(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class NotFound(Exception):
    """Raised for missing *and* for invisible resources, identically."""


@dataclass(frozen=True)
class AccessContext:
    user_id: str
    tenant_id: str
    role: str
    membership_version: int


@dataclass
class Membership:
    user_id: str
    org_id: str
    role: str
    version: int


@dataclass
class Resource:
    tenant_id: str
    local_id: str
    kind: str
    title: str
    body: str
    owner_id: str
    visibility: str
    parent_id: str | None
    version: int = 1
    status: str = "draft"
    approved_version: int | None = None
    grants: set[str] = field(default_factory=set)

    def public(self) -> dict:
        return {
            "id": self.local_id, "tenant_id": self.tenant_id, "kind": self.kind, "title": self.title,
            "body": self.body, "owner_id": self.owner_id, "visibility": self.visibility,
            "parent_id": self.parent_id, "version": self.version, "status": self.status,
        }


@dataclass(frozen=True)
class AuditEntry:
    at: float
    tenant_id: str
    user_id: str
    action: str
    target: str
    decision: str  # "allow" or a deny reason code
    trace_id: str = "-"


def _text(value: object, name: str, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"invalid {name}")
    return value


class TenancyService:
    def __init__(self, user_exists: Callable[[str], bool] = lambda _u: True, clock: Callable[[], float] = time.time) -> None:
        self.user_exists = user_exists
        self._clock = clock
        self._lock = threading.RLock()
        self._orgs: dict[str, str] = {}
        self._members: dict[tuple[str, str], Membership] = {}  # (org_id, user_id)
        self._resources: dict[str, dict[str, Resource]] = {}  # tenant partition -> local_id -> resource
        self._counters: dict[str, int] = {}
        self._version = 0
        self.audit: list[AuditEntry] = []
        # Optional observer (PASUL 13): receives every audit entry; must not call back into this service.
        self.audit_sink: Callable[[AuditEntry], None] | None = None

    # --- organizations and memberships ---------------------------------
    def create_organization(self, name: str, founder_user_id: str) -> str:
        """Platform bootstrap only (not exposed over HTTP): founder becomes admin."""
        _text(name, "name", 120)
        with self._lock:
            org_id = "org_" + secrets.token_hex(6)
            self._orgs[org_id] = name
            self._resources[org_id] = {}
            self._counters[org_id] = 0
            self._set_member(org_id, founder_user_id, "admin")
            return org_id

    def _set_member(self, org_id: str, user_id: str, role: str) -> None:
        self._version += 1
        self._members[(org_id, user_id)] = Membership(user_id, org_id, role, self._version)

    def membership(self, user_id: str, org_id: str | None) -> Membership | None:
        with self._lock:
            return self._members.get((org_id or "", user_id))

    def organizations_of(self, user_id: str) -> list[str]:
        with self._lock:
            return sorted(org for (org, user) in self._members if user == user_id)

    def context(self, user_id: str, org_id: str | None) -> AccessContext:
        with self._lock:
            m = self._members.get((org_id or "", user_id))
            if m is None:
                self._log(org_id or "-", user_id, "context", "-", "no_membership")
                raise AccessDenied("no_membership")
            return AccessContext(user_id, m.org_id, m.role, m.version)

    def _require(self, ctx: AccessContext, permission: str) -> Membership:
        """Re-validate the membership as it is *now*, then check the permission.

        Does not audit by itself: the enclosing `_decision` records the final outcome.
        """
        m = self._members.get((ctx.tenant_id, ctx.user_id))
        if m is None or m.version != ctx.membership_version:
            raise AccessDenied("stale_membership")
        if permission not in ROLE_PERMISSIONS[m.role]:
            raise AccessDenied("forbidden")
        return m

    @contextmanager
    def _decision(self, ctx: AccessContext, action: str, target: object):
        """Hold the lock for the whole operation and audit exactly one *final* decision.

        allow is recorded only when the operation completes; denials, "not_found"
        (missing or invisible, indistinguishable) and "invalid_request" are recorded
        with the same generic codes the caller receives. No content is logged.
        """
        tgt = target if isinstance(target, str) and len(target) <= 64 else "-"
        with self._lock:
            try:
                yield
            except AccessDenied as error:
                self._log(ctx.tenant_id, ctx.user_id, action, tgt, error.code)
                raise
            except NotFound:
                self._log(ctx.tenant_id, ctx.user_id, action, tgt, "not_found")
                raise
            except ValueError:
                self._log(ctx.tenant_id, ctx.user_id, action, tgt, "invalid_request")
                raise
            self._log(ctx.tenant_id, ctx.user_id, action, tgt, "allow")

    def _log(self, tenant: str, user: str, action: str, target: str, decision: str) -> None:
        entry = AuditEntry(self._clock(), tenant, user, action, target, decision, current_trace_id.get())
        self.audit.append(entry)
        if self.audit_sink is not None:
            self.audit_sink(entry)

    @staticmethod
    def _user_id(value: object) -> str:
        if not isinstance(value, str) or not (1 <= len(value) <= 64):
            raise ValueError("invalid user_id")
        return value

    def add_member(self, ctx: AccessContext, user_id: object, role: object) -> None:
        # Lock order rule: TenancyService never calls into AuthService while holding its own
        # lock, and AuthService never calls TenancyService while holding its lock (R11-2).
        exists = isinstance(user_id, str) and self.user_exists(user_id)
        with self._decision(ctx, "membership.manage", "member"):
            self._require(ctx, "membership.manage")
            uid = self._user_id(user_id)
            if not isinstance(role, str) or role not in ROLE_PERMISSIONS or not exists:
                raise ValueError("invalid user or role")
            current = self._members.get((ctx.tenant_id, uid))
            if current and current.role == "admin" and role != "admin":
                self._ensure_other_admin(ctx.tenant_id, uid)
            self._set_member(ctx.tenant_id, uid, role)

    def remove_member(self, ctx: AccessContext, user_id: object) -> None:
        with self._decision(ctx, "membership.manage", "member"):
            self._require(ctx, "membership.manage")
            uid = self._user_id(user_id)
            current = self._members.get((ctx.tenant_id, uid))
            if current is None:
                raise NotFound()
            if current.role == "admin":
                self._ensure_other_admin(ctx.tenant_id, uid)
            self._version += 1  # removal also invalidates contexts issued earlier
            del self._members[(ctx.tenant_id, uid)]
            for r in self._resources[ctx.tenant_id].values():
                r.grants.discard(uid)

    def _ensure_other_admin(self, org_id: str, leaving: str) -> None:
        if not any(m.role == "admin" and m.user_id != leaving for (o, _), m in self._members.items() if o == org_id):
            raise AccessDenied("last_admin")

    def members(self, ctx: AccessContext) -> list[dict]:
        with self._decision(ctx, "membership.manage", "members"):
            self._require(ctx, "membership.manage")
            result = [{"user_id": m.user_id, "role": m.role} for (o, _), m in sorted(self._members.items()) if o == ctx.tenant_id]
        return result

    # --- resources -----------------------------------------------------
    def _partition(self, ctx: AccessContext) -> dict[str, Resource]:
        return self._resources.get(ctx.tenant_id, {})

    @staticmethod
    def _visible(ctx: AccessContext, r: Resource) -> bool:
        return r.tenant_id == ctx.tenant_id and (r.visibility == "tenant" or r.owner_id == ctx.user_id or ctx.user_id in r.grants)

    def _find(self, ctx: AccessContext, local_id: object) -> Resource:
        r = self._partition(ctx).get(local_id) if isinstance(local_id, str) else None
        if r is None or not self._visible(ctx, r):
            raise NotFound()
        return r

    def create(self, ctx: AccessContext, kind: object, title: object, body: object,
               visibility: object = "tenant", parent_id: object = None) -> dict:
        with self._decision(ctx, "resource.create", "new"):
            self._require(ctx, "resource.create")
            if not isinstance(kind, str) or kind not in KINDS:
                raise ValueError("invalid kind")
            if not isinstance(visibility, str) or visibility not in VISIBILITIES:
                raise ValueError("invalid visibility")
            if parent_id is not None and not isinstance(parent_id, str):
                raise ValueError("invalid parent_id")
            title, body = _text(title, "title", 200), _text(body, "body")
            if parent_id is not None:
                self._find(ctx, parent_id)  # parent must be visible in the same tenant
            self._counters[ctx.tenant_id] += 1
            local_id = f"r{self._counters[ctx.tenant_id]}"
            r = Resource(ctx.tenant_id, local_id, kind, title, body, ctx.user_id, visibility, parent_id)
            self._resources[ctx.tenant_id][local_id] = r
            result = r.public()
        return result

    def get(self, ctx: AccessContext, local_id: object) -> dict:
        with self._decision(ctx, "resource.read", local_id):
            self._require(ctx, "resource.read")
            result = self._find(ctx, local_id).public()
        return result

    def search(self, ctx: AccessContext, query: object = "", kind: object = None) -> list[dict]:
        """Query, search and memory retrieval share this single tenant-filtered path."""
        with self._decision(ctx, "resource.read", "search"):
            self._require(ctx, "resource.read")
            if not isinstance(query, str) or (kind is not None and not isinstance(kind, str)):
                raise ValueError("invalid query")
            q = query.lower()[:200]
            result = [
                r.public() for r in self._partition(ctx).values()
                if self._visible(ctx, r) and (kind is None or r.kind == kind)
                and (not q or q in r.title.lower() or q in r.body.lower())
            ]
        return result

    def update(self, ctx: AccessContext, local_id: object, title: object = None, body: object = None) -> dict:
        with self._decision(ctx, "resource.update_own", local_id):
            self._require(ctx, "resource.update_own")
            r = self._find(ctx, local_id)
            if r.owner_id != ctx.user_id:
                raise AccessDenied("not_owner")
            # Validate every field before any mutation: a rejected update changes nothing (R11-1).
            new_title = r.title if title is None else _text(title, "title", 200)
            new_body = r.body if body is None else _text(body, "body")
            if title is None and body is None:
                raise ValueError("nothing to update")
            r.title, r.body = new_title, new_body
            r.version += 1
            if r.status == "approved":  # an approval covers one exact version only
                r.status, r.approved_version = "draft", None
            result = r.public()
        return result

    def delete(self, ctx: AccessContext, local_id: object) -> None:
        with self._decision(ctx, "resource.delete_own", local_id):
            self._require(ctx, "resource.delete_own")
            r = self._find(ctx, local_id)
            if r.owner_id != ctx.user_id:
                raise AccessDenied("not_owner")
            if any(c.parent_id == r.local_id for c in self._partition(ctx).values()):
                raise AccessDenied("has_children")
            del self._resources[ctx.tenant_id][r.local_id]

    def grant_read(self, ctx: AccessContext, local_id: object, user_id: object) -> None:
        with self._decision(ctx, "resource.grant_own", local_id):
            self._require(ctx, "resource.grant_own")
            r = self._find(ctx, local_id)
            if r.owner_id != ctx.user_id:
                raise AccessDenied("not_owner")
            uid = self._user_id(user_id)
            if (ctx.tenant_id, uid) not in self._members:
                raise AccessDenied("not_member")  # never grant across tenants
            r.grants.add(uid)

    def approve(self, ctx: AccessContext, local_id: object) -> dict:
        with self._decision(ctx, "resource.approve", local_id):
            self._require(ctx, "resource.approve")
            r = self._find(ctx, local_id)
            if r.owner_id == ctx.user_id:
                raise AccessDenied("self_approval")
            r.status, r.approved_version = "approved", r.version
            result = r.public()
        return result

    def export(self, ctx: AccessContext) -> dict:
        """Segregated export: only the caller's tenant partition, only what the caller may read."""
        with self._decision(ctx, "export", "export"):
            self._require(ctx, "export")
            result = {"tenant_id": ctx.tenant_id, "exported_by": ctx.user_id,
                      "items": [r.public() for r in self._partition(ctx).values() if self._visible(ctx, r)]}
        return result
