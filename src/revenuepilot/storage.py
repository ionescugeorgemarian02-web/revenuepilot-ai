"""Relational persistence with tenant-scoped integrity (PASUL 12).

SQLite (standard library) is used as a local, zero-cost engine behind a small store API.
It is NOT the production target: docs/architecture/README.md ADR-04-2 names PostgreSQL.
SQLite cannot demonstrate RLS or multi-connection pooling behaviour (threat T10/A03), so
those remain NOT_RUN. What this layer does enforce, in the schema itself:

* every tenant-owned row carries tenant_id, and composite foreign keys
  (tenant_id, id) make a cross-tenant reference impossible, not merely filtered;
* every store method takes tenant_id explicitly and every statement filters on it;
* versioned migrations (up and down), checksummed, applied transactionally;
* integrity checks when an existing database is reopened;
* optimistic concurrency on updates and a retention purge for audit events.

The in-memory TenancyService (PASUL 11) is not yet wired to this store; that is a
declared limitation of this step.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import sqlite3
import time
from typing import Callable

ROLES = ("viewer", "editor", "approver", "admin")
KINDS = ("brief", "campaign", "memory")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up: str
    down: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256((self.up + "\x00" + self.down).encode("utf-8")).hexdigest()


def _csv(values: tuple[str, ...]) -> str:
    return ",".join(f"'{v}'" for v in values)


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        1,
        "initial_schema",
        f"""
CREATE TABLE organizations (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
    created_at REAL NOT NULL
);
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE CHECK (length(username) BETWEEN 3 AND 64)
);
CREATE TABLE memberships (
    org_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    role TEXT NOT NULL CHECK (role IN ({_csv(ROLES)})),
    version INTEGER NOT NULL CHECK (version >= 1),
    PRIMARY KEY (org_id, user_id)
);
CREATE TABLE tenant_counters (
    tenant_id TEXT PRIMARY KEY REFERENCES organizations(id) ON DELETE RESTRICT,
    next_id INTEGER NOT NULL CHECK (next_id >= 1)
);
CREATE TABLE resources (
    tenant_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ({_csv(KINDS)})),
    title TEXT NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
    body TEXT NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
    owner_id TEXT NOT NULL,
    visibility TEXT NOT NULL CHECK (visibility IN ('tenant','private')),
    parent_id TEXT,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved')),
    approved_version INTEGER,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (tenant_id, id),
    FOREIGN KEY (tenant_id, owner_id) REFERENCES memberships(org_id, user_id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, parent_id) REFERENCES resources(tenant_id, id) ON DELETE RESTRICT,
    CHECK ((status = 'approved') = (approved_version IS NOT NULL))
);
CREATE TABLE resource_grants (
    tenant_id TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    PRIMARY KEY (tenant_id, resource_id, user_id),
    FOREIGN KEY (tenant_id, resource_id) REFERENCES resources(tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, user_id) REFERENCES memberships(org_id, user_id) ON DELETE CASCADE
);
CREATE TABLE audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    at REAL NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    decision TEXT NOT NULL
);
CREATE INDEX idx_resources_tenant_kind ON resources(tenant_id, kind);
CREATE INDEX idx_audit_tenant_at ON audit_events(tenant_id, at);
""",
        """
DROP INDEX idx_audit_tenant_at;
DROP INDEX idx_resources_tenant_kind;
DROP TABLE audit_events;
DROP TABLE resource_grants;
DROP TABLE resources;
DROP TABLE tenant_counters;
DROP TABLE memberships;
DROP TABLE users;
DROP TABLE organizations;
""",
    ),
    Migration(
        2,
        "resources_owner_index",
        # Expand-only change: an additive index; no existing column or table is altered.
        "CREATE INDEX idx_resources_tenant_owner ON resources(tenant_id, owner_id);",
        "DROP INDEX idx_resources_tenant_owner;",
    ),
)

LATEST = MIGRATIONS[-1].version


class StorageError(Exception):
    pass


class ConflictError(StorageError):
    """Optimistic-concurrency failure: the row changed since it was read."""


class NotFoundError(StorageError):
    """Missing, or belonging to another tenant (indistinguishable by design)."""


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        if path != ":memory:":
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = FULL")
    except Exception:
        conn.close()  # e.g. a file that is not a database
        raise
    return conn


def _ensure_meta(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL,"
        " checksum TEXT NOT NULL, applied_at REAL NOT NULL)"
    )


def applied_versions(conn: sqlite3.Connection) -> dict[int, str]:
    _ensure_meta(conn)
    return {r["version"]: r["checksum"] for r in conn.execute("SELECT version, checksum FROM schema_migrations")}


def verify_history(conn: sqlite3.Connection, migrations: tuple[Migration, ...] = MIGRATIONS) -> int:
    """Refuse unknown or tampered history; return the current version."""
    known = {m.version: m for m in migrations}
    applied = applied_versions(conn)
    for version, checksum in applied.items():
        if version not in known:
            raise StorageError(f"database is newer than this code (unknown migration {version})")
        if known[version].checksum != checksum:
            raise StorageError(f"migration {version} checksum mismatch: history was altered")
    expected = list(range(1, max(applied, default=0) + 1))
    if sorted(applied) != expected:
        raise StorageError("migration history has gaps")
    return max(applied, default=0)


def migrate(conn: sqlite3.Connection, target: int = LATEST, migrations: tuple[Migration, ...] = MIGRATIONS,
            clock: Callable[[], float] = time.time) -> int:
    """Move the schema to `target` (up or down). Each step is one transaction."""
    current = verify_history(conn, migrations)
    by_version = {m.version: m for m in migrations}
    if target < 0 or target > max(by_version):
        raise StorageError("unknown target version")
    while current < target:
        m = by_version[current + 1]
        _run(conn, m.up, "INSERT INTO schema_migrations VALUES (?, ?, ?, ?)", (m.version, m.name, m.checksum, clock()))
        current += 1
    while current > target:
        m = by_version[current]
        _run(conn, m.down, "DELETE FROM schema_migrations WHERE version = ?", (m.version,))
        current -= 1
    return current


def _run(conn: sqlite3.Connection, script: str, record_sql: str, params: tuple) -> None:
    statements = [s.strip() for s in script.split(";") if s.strip()]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in statements:
            conn.execute(statement)
        conn.execute(record_sql, params)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def open_store(path: str = ":memory:", clock: Callable[[], float] = time.time) -> "Store":
    """Open (and migrate) a database; verify integrity when reopening an existing file."""
    conn = connect(path)
    try:
        verify_history(conn)
        migrate(conn, clock=clock)
        store = Store(conn, clock)
        store.check_integrity()
    except Exception:
        conn.close()  # do not leak a handle on a refused database
        raise
    return store


class Store:
    """Tenant-scoped repository. No method reads or writes a row without a tenant_id filter."""

    def __init__(self, conn: sqlite3.Connection, clock: Callable[[], float] = time.time) -> None:
        self.conn = conn
        self._clock = clock

    def check_integrity(self) -> None:
        if self.conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise StorageError("integrity_check failed")
        if self.conn.execute("PRAGMA foreign_key_check").fetchall():
            raise StorageError("foreign_key_check failed")
        if verify_history(self.conn) != LATEST:
            raise StorageError("schema is not at the latest version")

    def close(self) -> None:
        self.conn.close()

    def _tx(self):
        return _Transaction(self.conn)

    # --- identity and membership ---------------------------------------
    def add_organization(self, org_id: str, name: str) -> None:
        with self._tx():
            self.conn.execute("INSERT INTO organizations VALUES (?, ?, ?)", (org_id, name, self._clock()))
            self.conn.execute("INSERT INTO tenant_counters (tenant_id, next_id) VALUES (?, 1)", (org_id,))

    def add_user(self, user_id: str, username: str) -> None:
        with self._tx():
            self.conn.execute("INSERT INTO users VALUES (?, ?)", (user_id, username))

    def set_member(self, org_id: str, user_id: str, role: str) -> None:
        with self._tx():
            self.conn.execute(
                "INSERT INTO memberships (org_id, user_id, role, version) VALUES (?, ?, ?, 1) ON CONFLICT(org_id, user_id)"
                " DO UPDATE SET role = excluded.role, version = memberships.version + 1",
                (org_id, user_id, role),
            )

    def role_of(self, org_id: str, user_id: str) -> str | None:
        row = self.conn.execute("SELECT role FROM memberships WHERE org_id = ? AND user_id = ?", (org_id, user_id)).fetchone()
        return row["role"] if row else None

    # --- resources -----------------------------------------------------
    def create_resource(self, tenant_id: str, owner_id: str, kind: str, title: str, body: str,
                        visibility: str = "tenant", parent_id: str | None = None) -> dict:
        now = self._clock()
        with self._tx():
            row = self.conn.execute("SELECT next_id FROM tenant_counters WHERE tenant_id = ?", (tenant_id,)).fetchone()
            if row is None:
                raise NotFoundError("tenant")
            local_id = f"r{row['next_id']}"
            self.conn.execute("UPDATE tenant_counters SET next_id = next_id + 1 WHERE tenant_id = ?", (tenant_id,))
            self.conn.execute(
                "INSERT INTO resources (tenant_id, id, kind, title, body, owner_id, visibility, parent_id, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tenant_id, local_id, kind, title, body, owner_id, visibility, parent_id, now, now),
            )
        return self.get_resource(tenant_id, local_id)

    def get_resource(self, tenant_id: str, local_id: str) -> dict:
        row = self.conn.execute("SELECT * FROM resources WHERE tenant_id = ? AND id = ?", (tenant_id, local_id)).fetchone()
        if row is None:
            raise NotFoundError("resource")
        return dict(row)

    def update_resource(self, tenant_id: str, local_id: str, expected_version: int,
                        title: str | None = None, body: str | None = None) -> dict:
        """Optimistic concurrency; any content change drops an approval (it covers one version)."""
        current = self.get_resource(tenant_id, local_id)
        new_title = current["title"] if title is None else title
        new_body = current["body"] if body is None else body
        with self._tx():
            cursor = self.conn.execute(
                "UPDATE resources SET title = ?, body = ?, version = version + 1, status = 'draft',"
                " approved_version = NULL, updated_at = ? WHERE tenant_id = ? AND id = ? AND version = ?",
                (new_title, new_body, self._clock(), tenant_id, local_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise ConflictError("resource changed since it was read")
        return self.get_resource(tenant_id, local_id)

    def approve_resource(self, tenant_id: str, local_id: str, expected_version: int) -> dict:
        with self._tx():
            cursor = self.conn.execute(
                "UPDATE resources SET status = 'approved', approved_version = version, updated_at = ?"
                " WHERE tenant_id = ? AND id = ? AND version = ?",
                (self._clock(), tenant_id, local_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise ConflictError("resource changed since it was read")
        return self.get_resource(tenant_id, local_id)

    def delete_resource(self, tenant_id: str, local_id: str) -> None:
        with self._tx():
            cursor = self.conn.execute("DELETE FROM resources WHERE tenant_id = ? AND id = ?", (tenant_id, local_id))
            if cursor.rowcount != 1:
                raise NotFoundError("resource")

    def grant_read(self, tenant_id: str, local_id: str, user_id: str) -> None:
        with self._tx():
            self.conn.execute("INSERT OR IGNORE INTO resource_grants (tenant_id, resource_id, user_id) VALUES (?, ?, ?)", (tenant_id, local_id, user_id))

    def visible_resources(self, tenant_id: str, user_id: str, kind: str | None = None, query: str = "") -> list[dict]:
        like = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        rows = self.conn.execute(
            "SELECT r.* FROM resources r WHERE r.tenant_id = ?"
            # A user who is not a member of this tenant sees nothing, whatever the visibility.
            " AND EXISTS (SELECT 1 FROM memberships m WHERE m.org_id = r.tenant_id AND m.user_id = ?)"
            " AND (r.visibility = 'tenant' OR r.owner_id = ?"
            "      OR EXISTS (SELECT 1 FROM resource_grants g WHERE g.tenant_id = r.tenant_id"
            "                 AND g.resource_id = r.id AND g.user_id = ?))"
            " AND (? IS NULL OR r.kind = ?)"
            " AND (r.title LIKE ? ESCAPE '\\' OR r.body LIKE ? ESCAPE '\\')"
            " ORDER BY r.id",
            (tenant_id, user_id, user_id, user_id, kind, kind, like, like),
        ).fetchall()
        return [dict(r) for r in rows]

    def export_tenant(self, tenant_id: str) -> dict:
        resources = [dict(r) for r in self.conn.execute(
            "SELECT * FROM resources WHERE tenant_id = ? ORDER BY id", (tenant_id,))]
        members = [dict(r) for r in self.conn.execute(
            "SELECT user_id, role FROM memberships WHERE org_id = ? ORDER BY user_id", (tenant_id,))]
        return {"tenant_id": tenant_id, "members": members, "resources": resources}

    # --- audit and retention -------------------------------------------
    def record_audit(self, tenant_id: str, user_id: str, action: str, target: str, decision: str) -> None:
        with self._tx():
            self.conn.execute(
                "INSERT INTO audit_events (tenant_id, at, user_id, action, target, decision) VALUES (?, ?, ?, ?, ?, ?)",
                (tenant_id, self._clock(), user_id, action, target, decision),
            )

    def audit_events(self, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM audit_events WHERE tenant_id = ? ORDER BY seq", (tenant_id,))]

    def purge_audit_before(self, tenant_id: str, cutoff: float) -> int:
        """Retention: delete one tenant's audit events older than cutoff; returns rows removed."""
        with self._tx():
            return self.conn.execute(
                "DELETE FROM audit_events WHERE tenant_id = ? AND at < ?", (tenant_id, cutoff)).rowcount


class _Transaction:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def __enter__(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")
        return False


# --- synthetic fixtures (three organizations from three industries) --------
FIXTURE_ORGS = {
    "demo_agency": ("[SINTETIC] Agenție de marketing", "marketing"),
    "demo_clinic": ("[SINTETIC] Clinică stomatologică", "sănătate"),
    "demo_bakery": ("[SINTETIC] Brutărie artizanală", "alimentație"),
}


def load_demo_fixtures(store: Store) -> dict[str, dict[str, str]]:
    """Idempotent. All names, users and texts are invented; no personal or customer data."""
    ids: dict[str, dict[str, str]] = {}
    for org_id, (name, industry) in FIXTURE_ORGS.items():
        if store.conn.execute("SELECT 1 FROM organizations WHERE id = ?", (org_id,)).fetchone() is None:
            store.add_organization(org_id, name)
        ids[org_id] = {}
        for suffix, role in (("admin", "admin"), ("editor", "editor"), ("viewer", "viewer")):
            user_id = f"{org_id}_{suffix}"
            if store.conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone() is None:
                store.add_user(user_id, f"{org_id}-{suffix}")
            if store.role_of(org_id, user_id) is None:
                store.set_member(org_id, user_id, role)
            ids[org_id][suffix] = user_id
        if not store.conn.execute("SELECT 1 FROM resources WHERE tenant_id = ?", (org_id,)).fetchone():
            store.create_resource(org_id, ids[org_id]["editor"], "brief", f"Brief {industry}", f"Brief sintetic pentru domeniul {industry}.")
            store.create_resource(org_id, ids[org_id]["editor"], "memory", f"Lecție {industry}", "Lecție sintetică, fără date reale.", visibility="private")
    return ids
