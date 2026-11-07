"""Minimal, dependency-free local HTTP shell: health, demo UI and dev authentication."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os
import re
import sys

from .auth import AuthError, AuthService, Principal

MAX_BODY = 4096
TENANT_ROUTE = re.compile(r"^/api/tenants/([A-Za-z0-9_-]{1,64})/whoami$")


class Handler(BaseHTTPRequestHandler):
    # --- helpers -------------------------------------------------------
    @property
    def auth(self) -> AuthService | None:
        return getattr(self.server, "auth", None)

    def _send(self, status: int, body: object | None = None, headers: dict[str, str] | None = None) -> None:
        payload = b"" if body is None else json.dumps(body).encode("utf-8")
        self.send_response(status)
        if body is not None:
            self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def _host_ok(self) -> bool:
        # Reject unexpected Host values (DNS rebinding against the loopback server).
        port = self.server.server_port
        return self.headers.get("Host", "") in {f"127.0.0.1:{port}", f"localhost:{port}"}

    def _token(self) -> str | None:
        auth = self.auth
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if auth and name == auth.cookie_name:
                return value
        return None

    def _cookie(self, value: str, max_age: int) -> str:
        auth = self.auth
        attrs = [f"{auth.cookie_name}={value}", "Path=/", "HttpOnly", "SameSite=Strict", f"Max-Age={max_age}"]
        if auth.cookie_secure:
            attrs.append("Secure")
        return "; ".join(attrs)

    def _principal(self) -> Principal | None:
        try:
            return self.auth.authenticate(self._token())
        except AuthError:
            self._send(401, {"error": "unauthenticated"})
            return None

    def _json_body(self) -> dict | None:
        """CSRF and framing checks for state-changing requests; sends the error itself."""
        origin = self.headers.get("Origin", "")
        if origin not in {f"http://{self.headers.get('Host', '')}"} or not self._host_ok():
            self._send(403, {"error": "forbidden_origin"})
            return None
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            self._send(415, {"error": "json_required"})
            return None
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send(411, {"error": "length_required"})
            return None
        if length < 0 or length > MAX_BODY:
            self._send(413, {"error": "too_large"})
            return None
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            data = None
        if not isinstance(data, dict):
            self._send(400, {"error": "invalid_json"})
            return None
        return data

    # --- routes --------------------------------------------------------
    def do_GET(self) -> None:
        if self.path == "/":
            payload = files("revenuepilot").joinpath("index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/health":
            payload = json.dumps({"status": "ok", "service": "revenuepilot-ai"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        match = TENANT_ROUTE.match(self.path)
        if self.auth is None or not (self.path == "/api/me" or match):
            self.send_error(404)
            return
        if not self._host_ok():
            self._send(403, {"error": "forbidden_host"})
            return
        principal = self._principal()
        if principal is None:
            return
        if match is None:
            self._send(200, {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role, "auth_mode": "dev-local-only"})
        elif match.group(1) != principal.tenant_id:
            # Identity comes from the session; a different tenant (existing or not) is denied identically.
            self._send(403, {"error": "forbidden"})
        else:
            self._send(200, {"tenant_id": principal.tenant_id, "role": principal.role})

    def do_POST(self) -> None:
        if self.auth is None or self.path not in {"/auth/login", "/auth/logout", "/auth/password"}:
            self.send_error(404)
            return
        data = self._json_body()
        if data is None:
            return
        client = self.client_address[0]
        try:
            if self.path == "/auth/login":
                token, principal = self.auth.login(data.get("username"), data.get("password"), client)
                self._send(
                    200,
                    {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role, "auth_mode": "dev-local-only"},
                    {"Set-Cookie": self._cookie(token, self.auth.absolute_ttl)},
                )
            elif self.path == "/auth/logout":
                self.auth.logout(self._token())
                self._send(204, None, {"Set-Cookie": self._cookie("", 0)})
            else:
                token = self._token()
                self.auth.authenticate(token)
                try:
                    new_token = self.auth.change_password(token, data.get("current_password"), data.get("new_password"), client)
                except ValueError:
                    self._send(400, {"error": "weak_password"})
                    return
                self._send(204, None, {"Set-Cookie": self._cookie(new_token, self.auth.absolute_ttl)})
        except AuthError as error:
            if error.code == "rate_limited":
                self._send(429, {"error": "rate_limited"}, {"Retry-After": str(error.retry_after)})
            elif error.code == "invalid_credentials":
                self._send(401, {"error": "invalid_credentials"})
            else:
                self._send(401, {"error": "unauthenticated"})

    def log_message(self, format: str, *args: object) -> None:
        pass  # never log request lines: they could carry identifiers


def build_auth_from_env() -> AuthService:
    """Dev-only bootstrap. No user exists unless the owner supplies a password at runtime."""
    insecure = os.environ.get("REVENUEPILOT_INSECURE_COOKIE") == "1"
    auth = AuthService(cookie_secure=not insecure)
    password = os.environ.get("REVENUEPILOT_DEV_PASSWORD")
    if password:
        auth.add_user(os.environ.get("REVENUEPILOT_DEV_USER", "dev-user"), password, "tenant-dev-synthetic", "editor")
        print("auth: DEV-LOCAL-ONLY user enabled (synthetic tenant)", file=sys.stderr)
    else:
        print("auth: no dev user configured; all protected routes deny", file=sys.stderr)
    return auth


def serve() -> None:
    # Loopback only: dev authentication, no tenant isolation of data, no persistence.
    port = int(os.environ.get("REVENUEPILOT_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.auth = build_auth_from_env()
    try:
        server.serve_forever()
    finally:
        server.server_close()
