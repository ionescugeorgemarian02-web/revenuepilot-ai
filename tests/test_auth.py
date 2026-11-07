"""PASUL 10: authentication, sessions and identity checks against the real HTTP handler.

All users and passwords are synthetic and generated at run time; none is stored in the repo.
"""

import http.client
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from revenuepilot.app import Handler, ThreadingHTTPServer
from revenuepilot.auth import AuthService, hash_password, verify_password
from revenuepilot.tenancy import TenancyService


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


class AuthHttpTest(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.tenancy = TenancyService()
        self.auth = AuthService(clock=self.clock, tenancy=self.tenancy)
        self.tenancy.user_exists = self.auth.user_exists
        self.pw_a = secrets.token_urlsafe(18)
        self.pw_b = secrets.token_urlsafe(18)
        self.user_a = self.auth.add_user("synthetic-a@example.invalid", self.pw_a)
        self.user_b = self.auth.add_user("synthetic-b@example.invalid", self.pw_b)
        self.org_a = self.tenancy.create_organization("Synthetic A", self.user_a.user_id)
        self.org_b = self.tenancy.create_organization("Synthetic B", self.user_b.user_id)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.auth = self.auth
        self.server.tenancy = self.tenancy
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def req(self, method, path, body=None, cookie=None, origin="default", host="default", ctype="application/json", raw=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        hostval = f"127.0.0.1:{self.port}" if host == "default" else host
        headers = {"Host": hostval}
        if method == "POST":
            if origin == "default":
                origin = f"http://{hostval}"
            if origin is not None:
                headers["Origin"] = origin
            if ctype:
                headers["Content-Type"] = ctype
        if cookie:
            headers["Cookie"] = cookie
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        payload = resp.read()
        result = (resp.status, dict(resp.getheaders()), json.loads(payload) if payload and resp.getheader('Content-Type', '').startswith('application/json') else None)
        conn.close()
        return result

    def login(self, user="synthetic-a@example.invalid", password=None):
        password = password if password is not None else self.pw_a
        status, headers, body = self.req("POST", "/auth/login", {"username": user, "password": password})
        cookie = headers.get("Set-Cookie", "").split(";")[0] if status == 200 else None
        return status, headers, body, cookie

    # --- unauthorized access ------------------------------------------
    def test_unauthenticated_access_denied(self):
        for path in ("/api/me", f"/api/tenants/{self.org_a}/whoami"):
            status, _, body = self.req("GET", path)
            self.assertEqual((status, body), (401, {"error": "unauthenticated"}))

    def test_login_sets_hardened_cookie_and_hides_token(self):
        status, headers, body, cookie = self.login()
        self.assertEqual(status, 200)
        flags = headers["Set-Cookie"]
        for flag in ("HttpOnly", "SameSite=Strict", "Secure", "Path=/"):
            self.assertIn(flag, flags)
        self.assertNotIn("Domain", flags)
        self.assertTrue(flags.startswith("__Host-rp_session="))
        token = cookie.split("=", 1)[1]
        self.assertNotIn(token, json.dumps(body))
        self.assertEqual(body["auth_mode"], "dev-local-only")
        self.assertEqual(headers["Cache-Control"], "no-store")
        status, _, me = self.req("GET", "/api/me", cookie=cookie)
        self.assertEqual((status, me["tenant_id"], me["role"]), (200, self.org_a, "admin"))

    def test_bad_credentials_are_indistinguishable(self):
        wrong = self.login(password="x" * 20)[:3:2]
        unknown = self.login(user="nobody@example.invalid", password="x" * 20)[:3:2]
        self.assertEqual(wrong, unknown)
        self.assertEqual(wrong, (401, {"error": "invalid_credentials"}))

    # --- invalid session ------------------------------------------------
    def test_invalid_forged_and_truncated_sessions(self):
        _, _, _, cookie = self.login()
        name, token = cookie.split("=", 1)
        for bad in (f"{name}=", f"{name}={token[:-3]}", f"{name}={'A' * 43}", f"{name}={'A' * 500}", "rp_session=" + token, "garbage"):
            self.assertEqual(self.req("GET", "/api/me", cookie=bad)[0], 401, bad[:30])

    def test_logout_invalidates_session(self):
        _, _, _, cookie = self.login()
        status, headers, _ = self.req("POST", "/auth/logout", {}, cookie=cookie)
        self.assertEqual(status, 204)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.req("GET", "/api/me", cookie=cookie)[0], 401)

    def test_idle_and_absolute_expiry(self):
        _, _, _, cookie = self.login()
        self.clock.now += self.auth.idle_ttl - 10
        self.assertEqual(self.req("GET", "/api/me", cookie=cookie)[0], 200)  # activity renews idle timer
        self.clock.now += self.auth.idle_ttl + 1
        self.assertEqual(self.req("GET", "/api/me", cookie=cookie)[0], 401)
        _, _, _, cookie = self.login()
        for _ in range(20):  # keep active, but absolute TTL still applies
            self.clock.now += 1700
            status = self.req("GET", "/api/me", cookie=cookie)[0]
            if status == 401:
                break
        self.assertEqual(status, 401)

    def test_deactivated_user_loses_access_immediately(self):
        _, _, _, cookie = self.login()
        self.auth.deactivate_user(self.user_a.user_id)
        self.assertEqual(self.req("GET", "/api/me", cookie=cookie)[0], 401)
        self.assertEqual(self.login()[0], 401)

    # --- wrong identity --------------------------------------------------
    def test_tenant_is_taken_from_session_not_client(self):
        _, _, _, cookie_a = self.login()
        self.assertEqual(self.req("GET", f"/api/tenants/{self.org_a}/whoami", cookie=cookie_a)[0], 200)
        other = self.req("GET", f"/api/tenants/{self.org_b}/whoami", cookie=cookie_a)
        missing = self.req("GET", "/api/tenants/no-such-tenant/whoami", cookie=cookie_a)
        self.assertEqual((other[0], other[2]), (403, {"error": "forbidden"}))
        self.assertEqual((missing[0], missing[2]), (403, {"error": "forbidden"}))  # no tenant enumeration
        _, _, _, cookie_b = self.login("synthetic-b@example.invalid", self.pw_b)
        self.assertEqual(self.req("GET", "/api/me", cookie=cookie_b)[2]["tenant_id"], self.org_b)
        self.assertEqual(self.req("GET", f"/api/tenants/{self.org_a}/whoami", cookie=cookie_b)[0], 403)

    # --- brute force -----------------------------------------------------
    def test_lockout_after_repeated_failures_and_recovery(self):
        for _ in range(self.auth.max_failures):
            self.assertEqual(self.login(password="wrong-password-123")[0], 401)
        status, headers, _, _ = self.login(password="wrong-password-123")
        self.assertEqual(status, 429)
        self.assertGreaterEqual(int(headers["Retry-After"]), 1)
        self.assertEqual(self.login()[0], 429)  # correct password does not bypass lockout
        self.clock.now += self.auth.lockout_seconds + 1
        self.assertEqual(self.login()[0], 200)

    # --- CSRF / request hygiene -----------------------------------------
    def test_csrf_and_framing_checks(self):
        body = {"username": "synthetic-a@example.invalid", "password": self.pw_a}
        self.assertEqual(self.req("POST", "/auth/login", body, origin="http://evil.example")[0], 403)
        self.assertEqual(self.req("POST", "/auth/login", body, origin=None)[0], 403)
        self.assertEqual(self.req("POST", "/auth/login", body, ctype="text/plain")[0], 415)
        self.assertEqual(self.req("POST", "/auth/login", body, host="evil.example", origin="http://evil.example")[0], 403)
        self.assertEqual(self.req("GET", "/api/me", host="evil.example")[0], 403)
        self.assertEqual(self.req("POST", "/auth/login", raw=b"not json")[0], 400)
        self.assertEqual(self.req("POST", "/auth/login", raw=b"[1]")[0], 400)
        self.assertEqual(self.req("POST", "/auth/login", raw=b"{" + b" " * 5000 + b"}")[0], 413)

    # --- sensitive action: re-authentication ----------------------------
    def test_password_change_requires_current_password_and_revokes_sessions(self):
        _, _, _, c1 = self.login()
        _, _, _, c2 = self.login()
        new_pw = secrets.token_urlsafe(18)
        self.assertEqual(self.req("POST", "/auth/password", {"current_password": "wrong-password-123", "new_password": new_pw}, cookie=c1)[0], 401)
        self.assertEqual(self.req("POST", "/auth/password", {"current_password": self.pw_a, "new_password": "short"}, cookie=c1)[0], 400)
        self.assertEqual(self.req("POST", "/auth/password", {"current_password": self.pw_a, "new_password": new_pw})[0], 401)  # no session
        status, headers, _ = self.req("POST", "/auth/password", {"current_password": self.pw_a, "new_password": new_pw}, cookie=c1)
        self.assertEqual(status, 204)
        self.assertEqual(self.req("GET", "/api/me", cookie=c1)[0], 401)
        self.assertEqual(self.req("GET", "/api/me", cookie=c2)[0], 401)
        self.assertEqual(self.req("GET", "/api/me", cookie=headers["Set-Cookie"].split(";")[0])[0], 200)
        self.assertEqual(self.login()[0], 401)
        self.assertEqual(self.login(password=new_pw)[0], 200)

    def test_without_auth_service_routes_do_not_exist(self):
        del self.server.auth
        self.assertEqual(self.req("GET", "/api/me")[0], 404)
        self.assertEqual(self.req("POST", "/auth/login", {"username": "a", "password": "b"})[0], 404)


class AuthUnitTest(unittest.TestCase):
    def test_password_hashing(self):
        pw = secrets.token_urlsafe(18)
        h1, h2 = hash_password(pw), hash_password(pw)
        self.assertNotEqual(h1, h2)  # unique salts
        self.assertNotIn(pw, h1)
        self.assertTrue(verify_password(pw, h1))
        self.assertFalse(verify_password(pw + "x", h1))
        for bad in ("", "scrypt$1$2", "md5$1$1$1$00$00", "scrypt$99999999$8$1$00$00", "scrypt$x$8$1$zz$zz"):
            self.assertFalse(verify_password(pw, bad), bad)
        self.assertFalse(verify_password("a" * 100_000, h1))

    def test_store_keeps_no_plaintext_secrets(self):
        tenancy = TenancyService()
        auth = AuthService(tenancy=tenancy)
        pw = secrets.token_urlsafe(18)
        user = auth.add_user("synthetic@example.invalid", pw)
        org = tenancy.create_organization("Synthetic X", user.user_id)
        token, _ = auth.login("synthetic@example.invalid", pw, "c")
        self.assertNotIn(pw, repr(auth._users))
        self.assertTrue(user.password_hash.startswith("scrypt$"))
        self.assertNotIn(token, auth._sessions)  # only a hash of the token is stored
        self.assertEqual(auth.authenticate(token).tenant_id, org)

    def test_input_validation_and_session_cap(self):
        auth = AuthService(max_sessions_per_user=2)
        pw = secrets.token_urlsafe(18)
        for args in (("ab", pw), ("valid-name", "short"), ("x" * 65, pw)):
            with self.assertRaises(ValueError):
                auth.add_user(*args)
        auth.add_user("valid-name", pw)
        with self.assertRaises(ValueError):
            auth.add_user("VALID-NAME", pw)
        tokens = [auth.login("valid-name", pw, "c")[0] for _ in range(3)]
        live = [t for t in tokens if self._ok(auth, t)]
        self.assertEqual(len(live), 2)
        self.assertNotIn(tokens[0], live)

    @staticmethod
    def _ok(auth, token):
        try:
            auth.authenticate(token)
            return True
        except Exception:
            return False


class NoSecretsInRepoTest(unittest.TestCase):
    def test_no_password_literals_in_source(self):
        pattern = re.compile(r"""(?i)(password|passwd|secret|api[_-]?key)\s*[:=]\s*["'][^"'\s]{6,}["']""")
        root = Path(__file__).resolve().parents[1]
        hits = [str(p.relative_to(root)) for p in (root / "src").rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
