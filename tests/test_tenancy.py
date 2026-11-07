"""PASUL 11: multi-tenant RBAC and isolation, with three synthetic organizations from three industries.

Every name, user and password is synthetic and generated at run time.
"""

import http.client
import json
from pathlib import Path
import secrets
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from revenuepilot.app import Handler, ThreadingHTTPServer
from revenuepilot.auth import AuthService
from revenuepilot.tenancy import ROLE_PERMISSIONS, AccessDenied, NotFound, TenancyService


class World:
    """Agency (A), clinic (B), bakery (C); each with admin, editor, second editor, approver, viewer."""

    def __init__(self) -> None:
        self.tenancy = TenancyService()
        self.auth = AuthService(tenancy=self.tenancy)
        self.tenancy.user_exists = self.auth.user_exists
        self.passwords: dict[str, str] = {}
        self.users: dict[str, str] = {}
        self.orgs: dict[str, str] = {}
        for org_key, name in (("A", "Synthetic Agency"), ("B", "Synthetic Clinic"), ("C", "Synthetic Bakery")):
            admin = self.user(f"{org_key}-admin")
            self.orgs[org_key] = self.tenancy.create_organization(name, admin)
            ctx = self.ctx(f"{org_key}-admin", org_key)
            for role, suffix in (("editor", "editor"), ("editor", "editor2"), ("approver", "approver"), ("viewer", "viewer")):
                self.tenancy.add_member(ctx, self.user(f"{org_key}-{suffix}"), role)

    def user(self, key: str) -> str:
        pw = secrets.token_urlsafe(18)
        u = self.auth.add_user(f"{key.lower()}@example.invalid", pw)
        self.passwords[key], self.users[key] = pw, u.user_id
        return u.user_id

    def ctx(self, user_key: str, org_key: str):
        return self.tenancy.context(self.users[user_key], self.orgs[org_key])


class TenancyServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.w = World()
        self.t = self.w.tenancy
        # Each tenant gets its own r1 ("same local ID") with distinct content.
        self.r1 = {k: self.t.create(self.w.ctx(f"{k}-editor", k), "brief", f"Brief {k}", f"secret-{k}")["id"] for k in "ABC"}
        # Tenant B has extra objects so B-only IDs exist (r2 memory, r3 private).
        self.t.create(self.w.ctx("B-editor", "B"), "memory", "Lecție B", "memorie-B")
        self.t.create(self.w.ctx("B-editor", "B"), "campaign", "Privat B", "privat-B", visibility="private")

    def test_same_local_ids_resolve_only_inside_own_tenant(self):
        self.assertEqual(set(self.r1.values()), {"r1"})
        for k in "ABC":
            item = self.t.get(self.w.ctx(f"{k}-viewer", k), "r1")
            self.assertEqual((item["tenant_id"], item["body"]), (self.w.orgs[k], f"secret-{k}"))

    def test_ids_existing_only_in_another_tenant_are_not_found(self):
        ctx_a = self.w.ctx("A-editor", "A")
        for rid in ("r2", "r3", "r999", "../r1", None, 1):
            with self.assertRaises(NotFound):
                self.t.get(ctx_a, rid)
        with self.assertRaises(NotFound):
            self.t.update(ctx_a, "r2", body="hijack")
        with self.assertRaises(NotFound):
            self.t.delete(ctx_a, "r3")
        with self.assertRaises(NotFound):
            self.t.create(ctx_a, "brief", "child", "x", parent_id="r2")  # no cross-tenant parent link
        b = self.w.ctx("B-editor", "B")
        self.assertEqual(self.t.get(b, "r2")["body"], "memorie-B")
        self.assertEqual(self.t.get(b, "r3")["version"], 1)

    def test_search_memory_and_export_never_cross_tenants(self):
        for k in "ABC":
            ctx = self.w.ctx(f"{k}-viewer", k)
            found = self.t.search(ctx, "secret")
            self.assertEqual({i["tenant_id"] for i in found}, {self.w.orgs[k]})
            memories = self.t.search(ctx, "memorie", kind="memory")
            self.assertEqual([m["body"] for m in memories], ["memorie-B"] if k == "B" else [])
        self.assertEqual(self.t.search(self.w.ctx("A-viewer", "A"), "secret-B"), [])
        export_a = self.t.export(self.w.ctx("A-admin", "A"))
        self.assertEqual({i["tenant_id"] for i in export_a["items"]}, {self.w.orgs["A"]})
        self.assertNotIn("secret-B", json.dumps(export_a))
        export_b = self.t.export(self.w.ctx("B-admin", "B"))
        self.assertNotIn("privat-B", json.dumps(export_b))  # private object of another user is not exported

    def test_no_context_without_membership(self):
        for user_key, org_key in (("A-admin", "B"), ("B-viewer", "C"), ("C-editor", "A")):
            with self.assertRaises(AccessDenied) as e:
                self.w.ctx(user_key, org_key)
            self.assertEqual(e.exception.code, "no_membership")

    def test_role_permission_matrix_in_every_tenant(self):
        ops = {
            "resource.read": lambda ctx: self.t.get(ctx, "r1"),
            "resource.create": lambda ctx: self.t.create(ctx, "brief", "t", "b"),
            "export": lambda ctx: self.t.export(ctx),
            "membership.manage": lambda ctx: self.t.members(ctx),
        }
        for k in "ABC":
            for user_key in ("admin", "editor", "approver", "viewer"):
                role = "admin" if user_key == "admin" else user_key
                ctx = self.w.ctx(f"{k}-{user_key}", k)
                for perm, op in ops.items():
                    if perm in ROLE_PERMISSIONS[role]:
                        op(ctx)
                    else:
                        with self.assertRaises(AccessDenied, msg=f"{k} {role} {perm}"):
                            op(ctx)

    def test_ownership_private_visibility_and_grants(self):
        ed, ed2, viewer = (self.w.ctx(f"B-{x}", "B") for x in ("editor", "editor2", "viewer"))
        with self.assertRaises(AccessDenied):
            self.t.update(ed2, "r1", body="not mine")
        for ctx in (ed2, viewer):
            with self.assertRaises(NotFound):
                self.t.get(ctx, "r3")
            self.assertEqual(self.t.search(ctx, "privat"), [])  # private objects stay out of search
        self.assertEqual([i["id"] for i in self.t.search(ed, "privat")], ["r3"])
        with self.assertRaises(AccessDenied) as e:
            self.t.grant_read(ed, "r3", self.w.users["A-viewer"])  # user of another tenant
        self.assertEqual(e.exception.code, "not_member")
        self.t.grant_read(ed, "r3", self.w.users["B-viewer"])
        self.assertEqual(self.t.get(viewer, "r3")["title"], "Privat B")
        self.assertEqual([i["id"] for i in self.t.search(viewer, "privat")], ["r3"])
        with self.assertRaises(NotFound):
            self.t.get(ed2, "r3")

    def test_membership_revocation_and_role_change_apply_immediately(self):
        admin = self.w.ctx("A-admin", "A")
        old_editor = self.w.ctx("A-editor", "A")
        self.t.add_member(admin, self.w.users["A-editor"], "viewer")
        with self.assertRaises(AccessDenied) as e:
            self.t.create(old_editor, "brief", "t", "b")
        self.assertEqual(e.exception.code, "stale_membership")
        with self.assertRaises(AccessDenied):
            self.t.create(self.w.ctx("A-editor", "A"), "brief", "t", "b")
        old_viewer = self.w.ctx("A-viewer", "A")
        self.t.remove_member(self.w.ctx("A-admin", "A"), self.w.users["A-viewer"])
        with self.assertRaises(AccessDenied):
            self.t.get(old_viewer, "r1")
        with self.assertRaises(AccessDenied):
            self.w.ctx("A-viewer", "A")

    def test_last_admin_cannot_be_removed_or_demoted(self):
        admin = self.w.ctx("C-admin", "C")
        uid = self.w.users["C-admin"]
        for op in (lambda: self.t.remove_member(admin, uid), lambda: self.t.add_member(admin, uid, "viewer")):
            with self.assertRaises(AccessDenied) as e:
                op()
            self.assertEqual(e.exception.code, "last_admin")
        with self.assertRaises(ValueError):
            self.t.add_member(admin, "u_does_not_exist", "viewer")
        with self.assertRaises(ValueError):
            self.t.add_member(admin, self.w.users["C-viewer"], "owner")

    def test_approval_is_separate_and_bound_to_version(self):
        with self.assertRaises(AccessDenied):
            self.t.approve(self.w.ctx("A-editor", "A"), "r1")  # editors cannot approve
        approved = self.t.approve(self.w.ctx("A-approver", "A"), "r1")
        self.assertEqual((approved["status"], approved["version"]), ("approved", 1))
        edited = self.t.update(self.w.ctx("A-editor", "A"), "r1", body="changed")
        self.assertEqual((edited["status"], edited["version"]), ("draft", 2))
        with self.assertRaises(NotFound):
            self.t.approve(self.w.ctx("A-approver", "A"), "r3")  # B's private ID does not exist in A

    def test_multi_organization_user_has_separate_roles(self):
        uid = self.w.users["A-viewer"]
        self.t.add_member(self.w.ctx("C-admin", "C"), uid, "editor")
        in_a, in_c = self.t.context(uid, self.w.orgs["A"]), self.t.context(uid, self.w.orgs["C"])
        self.assertEqual((in_a.role, in_c.role), ("viewer", "editor"))
        created = self.t.create(in_c, "brief", "Doar în C", "c-only")
        with self.assertRaises(AccessDenied):
            self.t.create(in_a, "brief", "t", "b")
        self.assertEqual(self.t.search(in_a, "c-only"), [])
        self.assertEqual(created["tenant_id"], self.w.orgs["C"])

    def test_delete_rules(self):
        ed = self.w.ctx("A-editor", "A")
        child = self.t.create(ed, "campaign", "child", "x", parent_id="r1")
        with self.assertRaises(AccessDenied) as e:
            self.t.delete(ed, "r1")
        self.assertEqual(e.exception.code, "has_children")
        with self.assertRaises(AccessDenied):
            self.t.delete(self.w.ctx("A-editor2", "A"), child["id"])
        self.t.delete(ed, child["id"])
        with self.assertRaises(NotFound):
            self.t.get(ed, child["id"])

    def test_every_decision_is_audited_without_content(self):
        before = len(self.t.audit)
        self.t.get(self.w.ctx("B-viewer", "B"), "r1")
        with self.assertRaises(AccessDenied):
            self.t.export(self.w.ctx("B-viewer", "B"))
        new = self.t.audit[before:]
        self.assertEqual([(e.action, e.decision) for e in new], [("resource.read", "allow"), ("export", "forbidden")])
        self.assertTrue(all(e.tenant_id == self.w.orgs["B"] for e in new))
        self.assertNotIn("secret-", repr(self.t.audit))

    def test_input_validation(self):
        ed = self.w.ctx("A-editor", "A")
        for args in (("unknown", "t", "b"), ("brief", "", "b"), ("brief", "t", "x" * 2001), ("brief", "t", "b", "public")):
            with self.assertRaises(ValueError):
                self.t.create(ed, *args)


class R11RemediationTest(unittest.TestCase):
    """Regression tests for the Codex review findings R11-1..R11-4 on eaa99e0."""

    def setUp(self) -> None:
        self.w = World()
        self.t = self.w.tenancy
        self.ed = self.w.ctx("A-editor", "A")
        self.t.create(self.ed, "campaign", "Titlu aprobat", "corp aprobat")

    def test_r11_1_rejected_update_changes_nothing(self):
        self.t.approve(self.w.ctx("A-approver", "A"), "r1")
        before = self.t.get(self.ed, "r1")
        for kwargs in ({"title": "UNAPPROVED", "body": ""}, {"title": "", "body": "nou"}, {"title": "ok", "body": []}, {}):
            with self.assertRaises(ValueError, msg=str(kwargs)):
                self.t.update(self.ed, "r1", **kwargs)
            self.assertEqual(self.t.get(self.ed, "r1"), before)
        self.assertEqual(before["status"], "approved")
        after = self.t.update(self.ed, "r1", title="Titlu nou")
        self.assertEqual((after["status"], after["version"], after["body"]), ("draft", 2, "corp aprobat"))

    def _assert_no_cross_service_lock(self):
        auth, t = self.w.auth, self.t
        real_membership, real_orgs, real_exists = t.membership, t.organizations_of, t.user_exists

        def membership(*a):
            self.assertFalse(auth._lock.locked(), "TenancyService called while holding the auth lock")
            return real_membership(*a)

        def orgs(*a):
            self.assertFalse(auth._lock.locked(), "TenancyService called while holding the auth lock")
            return real_orgs(*a)

        def exists(uid):
            self.assertFalse(t._lock._is_owned(), "AuthService called while holding the tenancy lock")
            return real_exists(uid)

        t.membership, t.organizations_of, t.user_exists = membership, orgs, exists

    def test_r11_2_single_lock_order_between_services(self):
        self._assert_no_cross_service_lock()
        token, principal = self.w.auth.login("a-admin@example.invalid", self.w.passwords["A-admin"], "c")
        self.assertEqual(principal.role, "admin")
        self.w.auth.authenticate(token)
        self.t.add_member(self.w.ctx("A-admin", "A"), self.w.users["B-viewer"], "viewer")
        self.t.add_member(self.w.ctx("C-admin", "C"), self.w.users["A-admin"], "viewer")
        self.w.auth.switch_organization(token, self.w.orgs["C"])

    def test_r11_2_interleaving_login_and_add_member_completes(self):
        """The exact interleaving that deadlocked on eaa99e0 must now finish."""
        auth, t = self.w.auth, self.t
        login_at_principal, member_at_exists = threading.Event(), threading.Event()
        real_principal, real_exists = auth._principal, t.user_exists

        def principal(*a):
            login_at_principal.set()
            member_at_exists.wait(3)
            return real_principal(*a)

        def exists(uid):
            member_at_exists.set()
            return real_exists(uid)

        auth._principal, t.user_exists = principal, exists
        results = {}
        login = threading.Thread(target=lambda: results.setdefault("login", auth.login(
            "a-admin@example.invalid", self.w.passwords["A-admin"], "c")[1]), daemon=True)
        member = threading.Thread(target=lambda: results.setdefault("member", t.add_member(
            self.w.ctx("A-admin", "A"), self.w.users["C-viewer"], "viewer")), daemon=True)
        login.start()  # force the order: login must be inside _principal before add_member starts
        self.assertTrue(login_at_principal.wait(5))
        member.start()
        self.assertTrue(member_at_exists.wait(5))
        login.join(5)
        member.join(5)
        self.assertFalse(login.is_alive() or member.is_alive(), "deadlock: threads still blocked")
        self.assertEqual(results["login"].role, "admin")
        self.assertEqual(t.membership(self.w.users["C-viewer"], self.w.orgs["A"]).role, "viewer")
        self.assertFalse(auth._lock.locked())
        self.assertTrue(t._lock.acquire(blocking=False))
        t._lock.release()

    def test_r11_3_final_decision_is_audited(self):
        self.t.create(self.ed, "brief", "Privat", "continut-privat", visibility="private")  # r2
        viewer = self.w.ctx("A-viewer", "A")
        cases = [
            (lambda: self.t.get(viewer, "r2"), ("resource.read", "not_found")),     # private
            (lambda: self.t.get(viewer, "r99"), ("resource.read", "not_found")),    # missing: same code
            (lambda: self.t.get(viewer, "r1"), ("resource.read", "allow")),
            (lambda: self.t.update(self.w.ctx("A-editor2", "A"), "r1", body="x"), ("resource.update_own", "not_owner")),
            (lambda: self.t.remove_member(self.w.ctx("B-admin", "B"), self.w.users["B-admin"]), ("membership.manage", "last_admin")),
            (lambda: self.t.create(self.ed, [], "t", "b"), ("resource.create", "invalid_request")),
        ]
        for op, expected in cases:
            before = len(self.t.audit)
            try:
                op()
            except (AccessDenied, NotFound, ValueError):
                pass
            new = [(e.action, e.decision) for e in self.t.audit[before:]]
            self.assertEqual(new, [expected])  # exactly one final decision, never a false allow
        self.assertNotIn("continut-privat", repr(self.t.audit))

    def test_r11_4_wrong_json_types_rejected_by_service(self):
        admin = self.w.ctx("A-admin", "A")
        bad = [[], {}, 1, None, 1.5, True]
        for value in bad:
            for call in (
                lambda v: self.t.create(self.ed, v, "t", "b"),
                lambda v: self.t.create(self.ed, "brief", v, "b"),
                lambda v: self.t.create(self.ed, "brief", "t", v),
                lambda v: self.t.create(self.ed, "brief", "t", "b", visibility=v),
                lambda v: self.t.add_member(admin, self.w.users["B-viewer"], v),
                lambda v: self.t.add_member(admin, v, "viewer"),
                lambda v: self.t.search(self.ed, v),
            ):
                with self.assertRaises(ValueError, msg=repr(value)):
                    call(value)
            if value is not None:
                for call in (
                    lambda v: self.t.create(self.ed, "brief", "t", "b", parent_id=v),
                    lambda v: self.t.grant_read(self.ed, "r1", v),
                    lambda v: self.t.remove_member(admin, v),
                ):
                    with self.assertRaises(ValueError, msg=repr(value)):
                        call(value)


class TenancyHttpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.w = World()
        self.w.tenancy.add_member(self.w.ctx("C-admin", "C"), self.w.users["A-viewer"], "editor")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.auth, self.server.tenancy = self.w.auth, self.w.tenancy
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def req(self, method, path, body=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        host = f"127.0.0.1:{self.port}"
        headers = {"Host": host}
        if method == "POST":
            headers.update({"Origin": f"http://{host}", "Content-Type": "application/json"})
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, body=json.dumps(body or {}).encode() if method == "POST" else None, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        ok_json = raw and resp.getheader("Content-Type", "").startswith("application/json")
        result = (resp.status, dict(resp.getheaders()), json.loads(raw) if ok_json else None)
        conn.close()
        return result

    def login(self, key, org_key=None):
        body = {"username": f"{key.lower()}@example.invalid", "password": self.w.passwords[key]}
        if org_key:
            body["organization_id"] = self.w.orgs[org_key]
        status, headers, data = self.req("POST", "/auth/login", body)
        return status, data, headers.get("Set-Cookie", "").split(";")[0]

    def test_client_supplied_tenant_is_ignored(self):
        _, _, cookie = self.login("A-editor")
        status, _, created = self.req("POST", "/api/resources", {"kind": "brief", "title": "t", "body": "b", "tenant_id": self.w.orgs["B"]}, cookie)
        self.assertEqual((status, created["tenant_id"]), (201, self.w.orgs["A"]))
        status, _, items = self.req("GET", f"/api/resources?tenant_id={self.w.orgs['B']}", cookie=cookie)
        self.assertEqual({i["tenant_id"] for i in items["items"]}, {self.w.orgs["A"]})

    def test_cross_tenant_http_paths(self):
        _, _, cookie_b = self.login("B-editor")
        self.req("POST", "/api/resources", {"kind": "brief", "title": "B1", "body": "secret-B"}, cookie_b)
        self.req("POST", "/api/resources", {"kind": "brief", "title": "B2", "body": "secret-B"}, cookie_b)
        _, _, cookie_a = self.login("A-editor")
        self.req("POST", "/api/resources", {"kind": "brief", "title": "A1", "body": "secret-A"}, cookie_a)
        self.assertEqual(self.req("GET", "/api/resources/r1", cookie=cookie_a)[2]["body"], "secret-A")
        for method, path in (("GET", "/api/resources/r2"), ("POST", "/api/resources/r2/update"), ("POST", "/api/resources/r2/delete"),
                             ("POST", "/api/resources/r2/grant"), ("GET", "/api/resources/r2/../r1")):
            self.assertEqual(self.req(method, path, {"body": "x", "user_id": "u"}, cookie_a)[0], 404, path)
        self.assertNotIn("secret-B", json.dumps(self.req("GET", "/api/resources?q=secret", cookie=cookie_a)[2]))
        self.assertEqual(self.req("GET", "/api/export", cookie=cookie_a)[0], 403)  # editor cannot export
        _, _, admin_a = self.login("A-admin")
        export = self.req("GET", "/api/export", cookie=admin_a)[2]
        self.assertEqual({i["tenant_id"] for i in export["items"]}, {self.w.orgs["A"]})
        self.assertEqual(self.req("GET", "/api/resources/r2", cookie=cookie_b)[2]["title"], "B2")

    def test_multi_org_login_requires_choice_and_switch_rotates_session(self):
        status, data, cookie = self.login("A-viewer")
        self.assertEqual((status, data["tenant_id"]), (200, None))
        status, _, data = self.req("GET", "/api/resources", cookie=cookie)
        self.assertEqual((status, data), (403, {"error": "no_membership"}))
        self.assertEqual(self.req("POST", "/auth/switch", {"organization_id": self.w.orgs["B"]}, cookie)[0], 403)
        status, headers, data = self.req("POST", "/auth/switch", {"organization_id": self.w.orgs["C"]}, cookie)
        self.assertEqual((status, data["tenant_id"], data["role"]), (200, self.w.orgs["C"], "editor"))
        new_cookie = headers["Set-Cookie"].split(";")[0]
        self.assertEqual(self.req("GET", "/api/me", cookie=cookie)[0], 401)  # old token revoked
        self.assertEqual(self.req("POST", "/api/resources", {"kind": "brief", "title": "t", "body": "b"}, new_cookie)[0], 201)
        self.assertEqual(self.login("A-viewer", "B")[0], 403)
        self.assertEqual(self.login("A-viewer", "A")[1]["role"], "viewer")

    def test_r11_4_wrong_json_types_return_400_not_disconnect(self):
        _, _, editor = self.login("A-editor")
        _, _, admin = self.login("A-admin")
        good = {"kind": "brief", "title": "t", "body": "b"}
        self.assertEqual(self.req("POST", "/api/resources", good, editor)[0], 201)  # positive control
        for value in ([], {}, 7, None, True):
            for field in ("kind", "title", "body", "visibility", "parent_id"):
                if field == "parent_id" and value is None:
                    continue
                status, _, data = self.req("POST", "/api/resources", {**good, field: value}, editor)
                self.assertEqual((status, data), (400, {"error": "invalid_request"}), f"{field}={value!r}")
            for path, body, cookie in (
                ("/api/resources/r1/update", {"title": value}, editor),
                ("/api/resources/r1/grant", {"user_id": value}, editor),
                ("/api/members", {"user_id": self.w.users["A-viewer"], "role": value}, admin),
                ("/api/members", {"user_id": value, "role": "viewer"}, admin),
                ("/api/members/remove", {"user_id": value}, admin),
            ):
                status, _, data = self.req("POST", path, body, cookie)
                self.assertEqual((status, data), (400, {"error": "invalid_request"}), f"{path} {body!r}")
            status, _, _ = self.req("POST", "/auth/switch", {"organization_id": value}, editor)
            self.assertEqual(status, 403)
        self.assertEqual(self.req("GET", "/api/resources/r1", cookie=editor)[2]["title"], "t")

    def test_membership_removal_over_http_cuts_access_immediately(self):
        _, _, viewer = self.login("B-viewer")
        self.assertEqual(self.req("GET", "/api/resources", cookie=viewer)[0], 200)
        _, _, admin = self.login("B-admin")
        self.assertEqual(self.req("POST", "/api/members/remove", {"user_id": self.w.users["B-viewer"]}, admin)[0], 204)
        self.assertEqual(self.req("GET", "/api/resources", cookie=viewer)[0], 403)
        self.assertEqual(self.req("GET", f"/api/tenants/{self.w.orgs['B']}/whoami", cookie=viewer)[0], 403)
        self.assertEqual(self.req("POST", "/api/members", {"user_id": self.w.users["B-viewer"], "role": "admin"}, viewer)[0], 403)
        _, _, editor = self.login("B-editor")
        self.assertEqual(self.req("POST", "/api/members", {"user_id": self.w.users["B-editor"], "role": "admin"}, editor)[2], {"error": "forbidden"})


if __name__ == "__main__":
    unittest.main()
