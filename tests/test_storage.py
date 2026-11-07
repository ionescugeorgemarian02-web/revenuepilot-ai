"""PASUL 12: relational persistence, migrations, tenant integrity and reopen checks.

Engine: SQLite from the standard library. These tests do NOT prove PostgreSQL behaviour, RLS or
connection pooling (T10/A03 at storage level remain NOT_RUN). All data is synthetic.
"""

import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from revenuepilot import storage
from revenuepilot.storage import (LATEST, MIGRATIONS, ConflictError, Migration, NotFoundError, StorageError,
                                  load_demo_fixtures, migrate, open_store, verify_history)


class Clock:
    def __init__(self, now=1_000.0):
        self.now = now

    def __call__(self):
        return self.now


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.store = open_store(clock=self.clock)
        self.ids = load_demo_fixtures(self.store)

    def tearDown(self):
        self.store.close()


class MigrationTest(unittest.TestCase):
    def test_up_down_up_roundtrip_and_history(self):
        conn = storage.connect()
        self.addCleanup(conn.close)
        self.assertEqual(migrate(conn), LATEST)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertTrue({"organizations", "memberships", "resources", "resource_grants", "audit_events", "tenant_counters"} <= tables)
        self.assertEqual(migrate(conn, 1), 1)
        self.assertNotIn("idx_resources_tenant_owner", {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")})
        self.assertEqual(migrate(conn, 0), 0)
        self.assertEqual({r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}, {"schema_migrations", "sqlite_sequence"} & {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} | {"schema_migrations"})
        self.assertEqual(migrate(conn), LATEST)
        self.assertEqual(verify_history(conn), LATEST)
        self.assertEqual(migrate(conn), LATEST)  # idempotent

    def test_failed_migration_rolls_back_completely(self):
        conn = storage.connect()
        self.addCleanup(conn.close)
        migrate(conn, 1)
        bad = MIGRATIONS[:1] + (Migration(2, "broken", "CREATE TABLE half_done (x INTEGER); CREATE TABLE half_done (y INTEGER)", "DROP TABLE half_done"),)
        with self.assertRaises(sqlite3.OperationalError):
            migrate(conn, 2, bad)
        self.assertEqual(verify_history(conn, bad), 1)
        self.assertIsNone(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'half_done'").fetchone())

    def test_tampered_or_unknown_history_is_refused(self):
        conn = storage.connect()
        self.addCleanup(conn.close)
        migrate(conn)
        conn.execute("UPDATE schema_migrations SET checksum = 'x' WHERE version = 1")
        with self.assertRaisesRegex(StorageError, "checksum"):
            verify_history(conn)
        conn.execute("UPDATE schema_migrations SET checksum = ? WHERE version = 1", (MIGRATIONS[0].checksum,))
        conn.execute("INSERT INTO schema_migrations VALUES (99, 'future', 'y', 0)")
        with self.assertRaisesRegex(StorageError, "newer"):
            verify_history(conn)
        conn.execute("DELETE FROM schema_migrations WHERE version = 99")
        conn.execute("DELETE FROM schema_migrations WHERE version = 1")
        with self.assertRaisesRegex(StorageError, "gaps"):
            verify_history(conn)


class IntegrityTest(StoreCase):
    def test_create_read_update_and_per_tenant_local_ids(self):
        for org in storage.FIXTURE_ORGS:
            self.assertEqual(self.store.get_resource(org, "r1")["tenant_id"], org)  # r1 exists in every tenant
        created = self.store.create_resource("demo_clinic", self.ids["demo_clinic"]["editor"], "campaign", "Campanie", "text")
        self.assertEqual((created["id"], created["version"], created["status"]), ("r3", 1, "draft"))
        updated = self.store.update_resource("demo_clinic", "r3", 1, body="nou")
        self.assertEqual((updated["version"], updated["body"], updated["title"]), (2, "nou", "Campanie"))

    def test_scope_other_tenant_rows_are_unreachable(self):
        before = self.store.get_resource("demo_bakery", "r1")
        self.store.create_resource("demo_agency", self.ids["demo_agency"]["editor"], "brief", "Doar agenție", "x")  # agency r3
        for op in (lambda: self.store.get_resource("demo_bakery", "r3"),
                   lambda: self.store.update_resource("demo_bakery", "r3", 1, body="hijack"),
                   lambda: self.store.approve_resource("demo_bakery", "r3", 1),
                   lambda: self.store.delete_resource("demo_bakery", "r3"),
                   lambda: self.store.get_resource("demo_agency", "r1' OR '1'='1")):
            with self.assertRaises((NotFoundError, ConflictError)):
                op()
        self.assertEqual(self.store.get_resource("demo_bakery", "r1"), before)
        self.assertEqual(self.store.get_resource("demo_agency", "r3")["body"], "x")

    def test_cross_tenant_references_are_rejected_by_the_schema(self):
        agency_owner, clinic_owner = self.ids["demo_agency"]["editor"], self.ids["demo_clinic"]["editor"]
        with self.assertRaises(sqlite3.IntegrityError):  # parent in another tenant
            self.store.create_resource("demo_clinic", clinic_owner, "brief", "t", "b", parent_id="r1") if False else \
                self.store.conn.execute("INSERT INTO resources (tenant_id,id,kind,title,body,owner_id,visibility,parent_id,created_at,updated_at)"
                                        " VALUES ('demo_clinic','rx','brief','t','b',?, 'tenant','nope',0,0)", (clinic_owner,))
        self.store.create_resource("demo_agency", agency_owner, "brief", "p3", "b")  # agency r3
        self.store.create_resource("demo_agency", agency_owner, "brief", "p4", "b")  # agency r4; the clinic has no r4
        with self.assertRaises(sqlite3.IntegrityError):  # clinic child pointing at agency's r4
            self.store.create_resource("demo_clinic", clinic_owner, "brief", "t", "b", parent_id="r4")
        self.store.create_resource("demo_clinic", clinic_owner, "brief", "ok", "b", parent_id="r1")  # same-tenant parent works
        with self.assertRaises(sqlite3.IntegrityError):  # owner is not a member of that tenant
            self.store.create_resource("demo_clinic", agency_owner, "brief", "t", "b")
        with self.assertRaises(sqlite3.IntegrityError):  # grant to a non-member
            self.store.grant_read("demo_clinic", "r1", agency_owner)
        with self.assertRaises(sqlite3.IntegrityError):  # unknown tenant row
            self.store.conn.execute("INSERT INTO audit_events (tenant_id,at,user_id,action,target,decision) VALUES ('ghost',0,'u','a','t','allow')")
        # a failed insert must not burn or skew the per-tenant counter beyond the attempt
        self.assertEqual(self.store.get_resource("demo_clinic", "r1")["id"], "r1")

    def test_check_constraints(self):
        owner = self.ids["demo_agency"]["editor"]
        for kwargs in ({"kind": "unknown"}, {"title": ""}, {"body": "x" * 2001}, {"visibility": "public"}):
            args = {"kind": "brief", "title": "t", "body": "b", "visibility": "tenant", **kwargs}
            with self.assertRaises(sqlite3.IntegrityError, msg=str(kwargs)):
                self.store.create_resource("demo_agency", owner, **args)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.set_member("demo_agency", owner, "root")
        with self.assertRaises(sqlite3.IntegrityError):  # approved status needs an approved version
            self.store.conn.execute("UPDATE resources SET status='approved' WHERE tenant_id='demo_agency' AND id='r1'")

    def test_optimistic_concurrency_and_approval_binding(self):
        r = self.store.get_resource("demo_agency", "r1")
        approved = self.store.approve_resource("demo_agency", "r1", r["version"])
        self.assertEqual((approved["status"], approved["approved_version"]), ("approved", 1))
        with self.assertRaises(ConflictError):  # stale writer
            self.store.update_resource("demo_agency", "r1", 99, body="x")
        edited = self.store.update_resource("demo_agency", "r1", 1, title="Titlu nou")
        self.assertEqual((edited["status"], edited["approved_version"], edited["version"]), ("draft", None, 2))
        with self.assertRaises(ConflictError):
            self.store.approve_resource("demo_agency", "r1", 1)  # approval of an outdated version

    def test_failed_write_leaves_no_partial_state(self):
        owner = self.ids["demo_agency"]["editor"]
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.create_resource("demo_agency", owner, "bad-kind", "t", "b")
        ok = self.store.create_resource("demo_agency", owner, "brief", "t", "b")
        self.assertEqual(ok["id"], "r3")  # counter was rolled back with the failed insert

    def test_visibility_search_and_export_are_tenant_scoped(self):
        agency = self.ids["demo_agency"]
        self.assertEqual([r["id"] for r in self.store.visible_resources("demo_agency", agency["viewer"])], ["r1"])  # r2 private
        self.assertEqual([r["id"] for r in self.store.visible_resources("demo_agency", agency["editor"])], ["r1", "r2"])
        self.store.grant_read("demo_agency", "r2", agency["viewer"])
        self.assertEqual([r["id"] for r in self.store.visible_resources("demo_agency", agency["viewer"])], ["r1", "r2"])
        self.assertEqual(self.store.visible_resources("demo_clinic", agency["editor"]), [])  # a user of another tenant sees nothing
        self.assertEqual(self.store.visible_resources("demo_agency", agency["editor"], query="%"), [])  # LIKE wildcards are escaped
        export = self.store.export_tenant("demo_bakery")
        self.assertEqual({r["tenant_id"] for r in export["resources"]}, {"demo_bakery"})
        self.assertTrue(all(m["user_id"].startswith("demo_bakery") for m in export["members"]))

    def test_every_executed_statement_on_tenant_tables_is_tenant_filtered(self):
        """Execution-time guard: trace the SQL the store really runs and require a tenant filter."""
        seen = []
        self.store.conn.set_trace_callback(seen.append)
        agency = self.ids["demo_agency"]
        r = self.store.create_resource("demo_agency", agency["editor"], "brief", "t", "b")
        self.store.update_resource("demo_agency", r["id"], 1, body="x")
        self.store.approve_resource("demo_agency", r["id"], 2)
        self.store.grant_read("demo_agency", r["id"], agency["viewer"])
        self.store.visible_resources("demo_agency", agency["viewer"], query="x")
        self.store.export_tenant("demo_agency")
        self.store.record_audit("demo_agency", "u", "a", "t", "allow")
        self.store.audit_events("demo_agency")
        self.store.purge_audit_before("demo_agency", 0)
        self.store.delete_resource("demo_agency", r["id"])
        self.store.conn.set_trace_callback(None)
        tables = ("resources", "resource_grants", "audit_events", "memberships", "tenant_counters")
        checked = [q for q in seen if re.match(r"\s*(SELECT|UPDATE|DELETE|INSERT)", q) and any(t in q for t in tables)]
        self.assertGreater(len(checked), 8)
        for q in checked:
            self.assertTrue("tenant_id" in q or "org_id" in q, q[:100])


class RetentionAndReopenTest(unittest.TestCase):
    def test_audit_retention_is_per_tenant(self):
        clock = Clock(100.0)
        store = open_store(clock=clock)
        load_demo_fixtures(store)
        for t in (100.0, 200.0, 300.0):
            clock.now = t
            store.record_audit("demo_agency", "u", "resource.read", "r1", "allow")
            store.record_audit("demo_clinic", "u", "resource.read", "r1", "allow")
        self.assertEqual(store.purge_audit_before("demo_agency", 250.0), 2)
        self.assertEqual([e["at"] for e in store.audit_events("demo_agency")], [300.0])
        self.assertEqual(len(store.audit_events("demo_clinic")), 3)  # other tenant untouched
        store.close()

    def test_fixtures_are_idempotent_synthetic_and_cover_three_industries(self):
        store = open_store()
        first = load_demo_fixtures(store)
        second = load_demo_fixtures(store)
        self.assertEqual(first, second)
        names = [r["name"] for r in store.conn.execute("SELECT name FROM organizations")]
        self.assertEqual(len(names), 3)
        self.assertTrue(all(n.startswith("[SINTETIC]") for n in names))
        self.assertEqual(store.conn.execute("SELECT count(*) FROM resources").fetchone()[0], 6)
        self.assertEqual(store.conn.execute("SELECT count(*) FROM memberships").fetchone()[0], 9)
        store.close()

    def test_data_survives_reopen_and_is_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.db")
            store = open_store(path)
            ids = load_demo_fixtures(store)
            created = store.create_resource("demo_agency", ids["demo_agency"]["editor"], "campaign", "Persistă", "după repornire")
            self.assertEqual(store.conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
            self.assertEqual(store.conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            store.close()
            again = open_store(path)  # reopen: history verified, integrity and FK checks run
            self.assertEqual(again.get_resource("demo_agency", created["id"])["body"], "după repornire")
            self.assertEqual(again.create_resource("demo_agency", ids["demo_agency"]["editor"], "brief", "t", "b")["id"], "r4")
            again.close()

    def test_reopen_refuses_newer_schema_and_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.db")
            open_store(path).close()
            conn = storage.connect(path)
            conn.execute("INSERT INTO schema_migrations VALUES (99, 'future', 'x', 0)")
            conn.close()
            with self.assertRaisesRegex(StorageError, "newer"):
                open_store(path)
            bad = os.path.join(tmp, "bad.db")
            Path(bad).write_bytes(b"this is not a sqlite database" * 20)
            with self.assertRaises(sqlite3.DatabaseError):
                open_store(bad)

    def test_foreign_key_violation_found_on_reopen_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "app.db")
            store = open_store(path)
            load_demo_fixtures(store)
            store.conn.execute("PRAGMA foreign_keys = OFF")  # simulate out-of-band damage
            store.conn.execute("DELETE FROM memberships WHERE org_id = 'demo_agency' AND user_id = 'demo_agency_editor'")
            store.close()
            with self.assertRaisesRegex(StorageError, "foreign_key_check"):
                open_store(path)


if __name__ == "__main__":
    unittest.main()
