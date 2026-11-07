"""PASUL 13: events, trace IDs, redaction, bounded tamper-evident log, trace reconstruction.

Sentinels and users are synthetic and generated at run time.
"""

import http.client
import io
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from revenuepilot.app import Handler, ThreadingHTTPServer, attach_observability
from revenuepilot.observability import Observability, redact_field, redact_text
from test_tenancy import World


class RedactionTest(unittest.TestCase):
    def setUp(self):
        self.obs = Observability()

    def test_sensitive_keys_and_patterns_are_masked_at_the_source(self):
        s = "SENT" + secrets.token_hex(6)
        self.assertEqual(redact_field("password", s), "[REDACTED]")
        self.assertEqual(redact_field("Authorization", s), "[REDACTED]")
        self.assertEqual(redact_field("session_cookie", s), "[REDACTED]")
        samples = {
            "mail me at ana.popescu@example.invalid now": "example.invalid",
            "call +40 721 000 000 please": "721",
            "Authorization: Bearer abcDEF123456xyz": "abcDEF123456xyz",
            "key sk-live_abcdefghijklmnop1234": "abcdefghijklmnop",
            "token " + secrets.token_urlsafe(32): "",  # random session-like token, checked below
        }
        for text, leaked in samples.items():
            out = redact_text(text)
            if leaked:
                self.assertNotIn(leaked, out, text)
            self.assertIn("[REDACTED", out)
        tok = secrets.token_urlsafe(32)
        self.assertNotIn(tok, redact_text(f"cookie value {tok}"))

    def test_ids_and_reason_codes_survive_redaction(self):
        for value in ("org_1a2b3c4d5e6f", "u_0123456789abcdef", "u_1234567890123456", "resource.read", "stale_membership", "r12", "not_found"):
            self.assertEqual(redact_field("target", value), value)
        self.assertEqual(redact_field("status", 403), 403)

    def test_closed_schema_scalars_only_and_one_line_per_event(self):
        stream = io.StringIO()
        obs = Observability(stream=stream)
        rec = obs.emit("authz.decision", action="a", target="x\n{\"seq\":999,\"fake\":true}", decision="allow",
                       extra_field="leak-me", nested={"password": "p"}, tenant_id=None)
        self.assertNotIn("extra_field", rec["fields"])
        self.assertNotIn("nested", rec["fields"])
        self.assertIsNone(obs.emit("not.an.event", x=1))
        self.assertIsNone(obs.emit("request.received", level="debug"))
        self.assertEqual(obs.rejected_events, 2)
        obs.emit("auth.logout")
        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 2)  # an embedded newline cannot forge a second log line
        self.assertEqual([json.loads(l)["seq"] for l in lines], [1, 2])
        self.assertNotIn("leak-me", stream.getvalue())

    def test_values_are_truncated(self):
        rec = self.obs.emit("authz.decision", action="a", target="t" * 5000, decision="allow")
        self.assertLessEqual(len(rec["fields"]["target"]), 200)


class LogIntegrityTest(unittest.TestCase):
    def test_bounded_buffer_counts_drops_and_chain_still_verifies(self):
        obs = Observability(capacity=5)
        for _ in range(12):
            obs.emit("auth.logout")
        snap = obs.snapshot()
        self.assertEqual((len(snap), obs.dropped_events, snap[0]["seq"]), (5, 7, 8))
        self.assertTrue(obs.verify_chain())

    def test_tampering_deletion_and_reordering_are_detected(self):
        for mutate in (
            lambda e: e[2]["fields"].update({"decision": "allow"}),
            lambda e: e[2].update({"user_id": "someone-else"}),
            lambda e: e.pop(1),
            lambda e: e.reverse(),
        ):
            obs = Observability()
            for i in range(5):
                obs.emit("authz.decision", action="a", target=f"r{i}", decision="deny")
            self.assertTrue(obs.verify_chain())
            events = list(obs._events)
            mutate(events)
            obs._events = type(obs._events)(events)
            self.assertFalse(obs.verify_chain())

    def test_concurrent_emitters_keep_a_valid_chain(self):
        obs = Observability(capacity=10_000)
        threads = [threading.Thread(target=lambda: [obs.emit("auth.logout") for _ in range(100)]) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        seqs = [e["seq"] for e in obs.snapshot()]
        self.assertEqual(seqs, list(range(1, 601)))
        self.assertTrue(obs.verify_chain())


class HttpTraceTest(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.stream = io.StringIO()
        self.obs = Observability(stream=self.stream)
        attach_observability(self.w.tenancy, self.obs)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.auth, self.server.tenancy, self.server.obs = self.w.auth, self.w.tenancy, self.obs
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def done_trace(self, trace_id, tenant_id, timeout=3.0):
        """`request.completed` is emitted after the response is written, so a client can see the
        response a moment before the event exists; wait (bounded) for it instead of racing."""
        deadline = time.monotonic() + timeout
        while True:
            events = self.obs.trace(trace_id, tenant_id)
            if any(e["name"] == "request.completed" for e in events) or time.monotonic() > deadline:
                return events
            time.sleep(0.005)

    def req(self, method, path, body=None, cookie=None, extra=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        host = f"127.0.0.1:{self.port}"
        headers = {"Host": host, **(extra or {})}
        if method == "POST":
            headers.update({"Origin": f"http://{host}", "Content-Type": "application/json"})
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, body=json.dumps(body or {}).encode() if method == "POST" else None, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        data = json.loads(raw) if raw and resp.getheader("Content-Type", "").startswith("application/json") else None
        result = (resp.status, {k.lower(): v for k, v in resp.getheaders()}, data)
        conn.close()
        return result

    def login(self, key):
        status, headers, _ = self.req("POST", "/auth/login", {"username": f"{key.lower()}@example.invalid", "password": self.w.passwords[key]})
        self.assertEqual(status, 200)
        return headers["set-cookie"].split(";")[0], headers["x-trace-id"]

    def test_every_operation_has_a_unique_server_generated_trace_id(self):
        seen = set()
        cookie, trace = self.login("A-editor")
        seen.add(trace)
        for method, path, body in (("GET", "/api/me", None), ("GET", "/health", None), ("GET", "/api/resources", None),
                                   ("POST", "/api/resources", {"kind": "brief", "title": "t", "body": "b"}),
                                   ("GET", "/api/resources/r999", None), ("GET", "/nope", None), ("POST", "/auth/logout", {})):
            status, headers, _ = self.req(method, path, body, cookie, extra={"X-Trace-Id": "attacker", "X-Request-ID": "attacker"})
            self.assertRegex(headers["x-trace-id"], r"^[0-9a-f]{16}$", f"{method} {path} {status}")
            seen.add(headers["x-trace-id"])
        self.assertEqual(len(seen), 8)  # unique per request; client-supplied IDs are ignored

    def test_trace_reconstruction_orders_the_whole_path(self):
        cookie, _ = self.login("A-editor")
        status, headers, _ = self.req("POST", "/api/resources", {"kind": "brief", "title": "t", "body": "b"}, cookie)
        self.assertEqual(status, 201)
        events = self.done_trace(headers["x-trace-id"], self.w.orgs["A"])
        self.assertEqual([e["name"] for e in events], ["request.received", "authz.decision", "request.completed"])
        self.assertEqual([e["seq"] for e in events], sorted(e["seq"] for e in events))
        self.assertEqual(events[1]["fields"], {"action": "resource.create", "target": "new", "decision": "allow"})
        done = events[2]["fields"]
        self.assertEqual((done["method"], done["route"], done["status"], done["cost_units"]), ("POST", "/api/resources", 201, 0))
        self.assertGreaterEqual(done["duration_ms"], 0)
        self.assertEqual({e["trace_id"] for e in events}, {headers["x-trace-id"]})

    def test_denied_access_is_traceable_with_reason_code_and_audit_trace_id(self):
        cookie_a, _ = self.login("A-editor")
        self.req("POST", "/api/resources", {"kind": "brief", "title": "t", "body": "secret-A"}, cookie_a)
        cookie_b, _ = self.login("B-viewer")
        status, headers, _ = self.req("GET", "/api/resources/r1", cookie=cookie_b)  # B's own r1 does not exist
        status2, headers2, _ = self.req("GET", "/api/export", cookie=cookie_b)  # viewer cannot export
        self.assertEqual((status, status2), (404, 403))
        e1 = self.done_trace(headers["x-trace-id"], self.w.orgs["B"])
        e2 = self.done_trace(headers2["x-trace-id"], self.w.orgs["B"])
        self.assertEqual([x["fields"].get("decision") for x in e1 if x["name"] == "authz.decision"], ["not_found"])
        self.assertEqual([x["fields"].get("decision") for x in e2 if x["name"] == "authz.decision"], ["forbidden"])
        audit_trace_ids = {a.trace_id for a in self.w.tenancy.audit if a.decision in ("not_found", "forbidden")}
        self.assertTrue({headers["x-trace-id"], headers2["x-trace-id"]} <= audit_trace_ids)
        self.assertNotIn("secret-A", self.stream.getvalue())

    def test_a_tenant_cannot_read_another_tenants_trace(self):
        cookie, _ = self.login("A-editor")
        _, headers, _ = self.req("GET", "/api/resources", cookie=cookie)
        tid = headers["x-trace-id"]
        self.assertTrue(self.done_trace(tid, self.w.orgs["A"]))
        self.assertEqual(self.obs.trace(tid, self.w.orgs["B"]), [])
        for bad in ("", "../x", "A" * 16, tid + "0", None):
            self.assertEqual(self.obs.trace(bad, self.w.orgs["A"]), [])

    def test_sentinels_never_reach_the_log(self):
        sentinel = "SENTINEL" + secrets.token_hex(8)
        bearer = "Bearer " + secrets.token_urlsafe(24)
        # failed login with a secret in the password and an email-shaped username
        self.req("POST", "/auth/login", {"username": "victim.person@example.invalid", "password": sentinel})
        cookie, _ = self.login("A-editor")
        session_token = cookie.split("=", 1)[1]
        self.req("GET", f"/api/resources?q={sentinel}&token={sentinel}", cookie=cookie, extra={"Authorization": bearer, "X-Api-Key": sentinel})
        self.req("POST", "/api/resources", {"kind": "brief", "title": f"titlu {sentinel}", "body": f"corp {sentinel}", "password": sentinel}, cookie)
        self.req("POST", "/auth/password", {"current_password": sentinel, "new_password": sentinel + "x"}, cookie)
        dump = self.stream.getvalue() + json.dumps(self.obs.snapshot()) + repr(self.w.tenancy.audit)
        for secret in (sentinel, bearer.split()[1], session_token, "victim.person", self.w.passwords["A-editor"], "example.invalid"):
            self.assertNotIn(secret, dump, secret)
        # positive control: debugging information is still there
        names = [e["name"] for e in self.obs.snapshot()]
        self.assertIn("auth.login", names)
        failure = [e for e in self.obs.snapshot() if e["name"] == "auth.login" and e["fields"].get("outcome") == "failure"]
        self.assertEqual(failure[0]["fields"]["reason"], "invalid_credentials")
        self.assertTrue(self.obs.verify_chain())

    def test_internal_errors_log_the_class_only_never_message_or_traceback(self):
        sentinel = "SENTINEL-ERR-" + secrets.token_hex(8)
        cookie, _ = self.login("A-editor")

        def boom(*a, **k):
            raise RuntimeError(sentinel)

        self.w.tenancy.search = boom
        status, headers, _ = self.req("GET", "/api/resources", cookie=cookie)
        self.assertEqual(status, 500)
        events = self.done_trace(headers["x-trace-id"], self.w.orgs["A"])
        error = [e for e in events if e["name"] == "request.error"]
        self.assertEqual(error[0]["fields"], {"error_class": "RuntimeError"})
        self.assertEqual(error[0]["level"], "error")
        self.assertEqual([e["fields"]["status"] for e in events if e["name"] == "request.completed"], [500])
        self.assertNotIn(sentinel, self.stream.getvalue() + json.dumps(self.obs.snapshot()))

    def test_server_without_observer_behaves_as_before(self):
        del self.server.obs
        status, headers, _ = self.req("GET", "/health")
        self.assertEqual(status, 200)
        self.assertNotIn("x-trace-id", headers)


if __name__ == "__main__":
    unittest.main()
