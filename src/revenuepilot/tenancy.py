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

from dataclasses import dataclass, field
import secrets
import threading
import time
from typing import Callable

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

    def _require(self, ctx: AccessContext, permission: str, target: str = "-") -> Membership:
        """Re-validate the membership as it is *now*, then check the permission."""
        m = self._members.get((ctx.tenant_id, ctx.user_id))
        if m is None or m.version != ctx.membership_version:
            self._log(ctx.tenant_id, ctx.user_id, permission, target, "stale_membership")
            raise AccessDenied("stale_membership")
        if permission not in ROLE_PERMISSIONS[m.role]:
            self._log(ctx.tenant_id, ctx.user_id, permission, target, "forbidden")
            raise AccessDenied("forbidden")
        self._log(ctx.tenant_id, ctx.user_id, permission, target, "allow")
        return m

    def _deny(self, ctx: AccessContext, action: str, target: str, code: str) -> None:
        self._log(ctx.tenant_id, ctx.user_id, action, target, code)
        raise AccessDenied(code)

    def _log(self, tenant: str, user: str, action: str, target: str, decision: str) -> None:
        self.audit.append(AuditEntry(self._clock(), tenant, user, action, target, decision))

    def add_member(self, ctx: AccessContext, user_id: str, role: str) -> None:
        with self._lock:
            self._require(ctx, "membership.manage", "member:" + str(user_id))
            if role not in ROLE_PERMISSIONS or not isinstance(user_id, str) or not self.user_exists(user_id):
                raise ValueError("invalid user or role")
            current = self._members.get((ctx.tenant_id, user_id))
            if current and current.role == "admin" and role != "admin":
                self._ensure_other_admin(ctx.tenant_id, user_id)
            self._set_member(ctx.tenant_id, user_id, role)

    def remove_member(self, ctx: AccessContext, user_id: str) -> None:
        with self._lock:
            self._require(ctx, "membership.manage", "member:" + str(user_id))
            current = self._members.get((ctx.tenant_id, user_id))
            if current is None:
                raise NotFound()
            if current.role == "admin":
                self._ensure_other_admin(ctx.tenant_id, user_id)
            self._version += 1  # removal also invalidates contexts issued earlier
            del self._members[(ctx.tenant_id, user_id)]
            for r in self._resources[ctx.tenant_id].values():
                r.grants.discard(user_id)

    def _ensure_other_admin(self, org_id: str, leaving: str) -> None:
        if not any(m.role == "admin" and m.user_id != leaving for (o, _), m in self._members.items() if o == org_id):
            raise AccessDenied("last_admin")

    def members(self, ctx: AccessContext) -> list[dict]:
        with self._lock:
            self._require(ctx, "membership.manage", "members")
            return [{"user_id": m.user_id, "role": m.role} for (o, _), m in sorted(self._members.items()) if o == ctx.tenant_id]

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

    def create(self, ctx: AccessContext, kind: str, title: str, body: str, visibility: str = "tenant", parent_id: str | None = None) -> dict:
        with self._lock:
            self._require(ctx, "resource.create", "new")
            if kind not in KINDS or visibility not in VISIBILITIES:
                raise ValueError("invalid kind or visibility")
            title, body = _text(title, "title", 200), _text(body, "body")
            if parent_id is not None:
                self._find(ctx, parent_id)  # parent must be visible in the same tenant
            self._counters[ctx.tenant_id] += 1
            local_id = f"r{self._counters[ctx.tenant_id]}"
            r = Resource(ctx.tenant_id, local_id, kind, title, body, ctx.user_id, visibility, parent_id)
            self._resources[ctx.tenant_id][local_id] = r
            return r.public()

    def get(self, ctx: AccessContext, local_id: str) -> dict:
        with self._lock:
            self._require(ctx, "resource.read", str(local_id))
            return self._find(ctx, local_id).public()

    def search(self, ctx: AccessContext, query: str = "", kind: str | None = None) -> list[dict]:
        """Query, search and memory retrieval share this single tenant-filtered path."""
        with self._lock:
            self._require(ctx, "resource.read", "search")
            q = (query or "").lower()[:200]
            return [
                r.public() for r in self._partition(ctx).values()
                if self._visible(ctx, r) and (kind is None or r.kind == kind)
                and (not q or q in r.title.lower() or q in r.body.lower())
            ]

    def update(self, ctx: AccessContext, local_id: str, title: str | None = None, body: str | None = None) -> dict:
        with self._lock:
            self._require(ctx, "resource.update_own", str(local_id))
            r = self._find(ctx, local_id)
            if r.owner_id != ctx.user_id:
                self._deny(ctx, "resource.update_own", local_id, "not_owner")
            if title is not None:
                r.title = _text(title, "title", 200)
            if body is not None:
                r.body = _text(body, "body")
            r.version += 1
            if r.status == "approved":  # an approval covers one exact version only
                r.status, r.approved_version = "draft", None
            return r.public()

    def delete(self, ctx: AccessContext, local_id: str) -> None:
        with self._lock:
            self._require(ctx, "resource.delete_own", str(local_id))
            r = self._find(ctx, local_id)
            if r.owner_id != ctx.user_id:
                self._deny(ctx, "resource.delete_own", local_id, "not_owner")
            if any(c.parent_id == local_id for c in self._partition(ctx).values()):
                self._deny(ctx, "resource.delete_own", local_id, "has_children")
            del self._resources[ctx.tenant_id][local_id]

    def grant_read(self, ctx: AccessContext, local_id: str, user_id: str) -> None:
        with self._lock:
            self._require(ctx, "resource.grant_own", str(local_id))
            r = self._find(ctx, local_id)
            if r.owner_id != ctx.user_id:
                self._deny(ctx, "resource.grant_own", local_id, "not_owner")
            if (ctx.tenant_id, user_id) not in self._members:
                self._deny(ctx, "resource.grant_own", local_id, "not_member")  # never grant across tenants
            r.grants.add(user_id)

    def approve(self, ctx: AccessContext, local_id: str) -> dict:
        with self._lock:
            self._require(ctx, "resource.approve", str(local_id))
            r = self._find(ctx, local_id)
            if r.owner_id == ctx.user_id:
                self._deny(ctx, "resource.approve", local_id, "self_approval")
            r.status, r.approved_version = "approved", r.version
            return r.public()

    def export(self, ctx: AccessContext) -> dict:
        """Segregated export: only the caller's tenant partition, only what the caller may read."""
        with self._lock:
            self._require(ctx, "export", "export")
            items = [r.public() for r in self._partition(ctx).values() if self._visible(ctx, r)]
            return {"tenant_id": ctx.tenant_id, "exported_by": ctx.user_id, "items": items}
