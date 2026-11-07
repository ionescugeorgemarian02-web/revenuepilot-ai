"""Minimal, dependency-free local HTTP shell: health, demo UI and dev authentication."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
import os
import re
import secrets
import sys
from urllib.parse import parse_qs

from .auth import AuthError, AuthService, Principal
from .tenancy import ROLE_PERMISSIONS, AccessDenied, NotFound, TenancyService

MAX_BODY = 4096
TENANT_ROUTE = re.compile(r"^/api/tenants/([A-Za-z0-9_-]{1,64})/whoami$")
RESOURCE_ROUTE = re.compile(r"^/api/resources/(r[0-9]{1,9})(?:/(update|delete|grant|approve))?$")
AUTH_ROUTES = frozenset({"/auth/login", "/auth/logout", "/auth/password", "/auth/switch"})


class Handler(BaseHTTPRequestHandler):
    # --- helpers -------------------------------------------------------
    @property
    def auth(self) -> AuthService | None:
        return getattr(self.server, "auth", None)

    @property
    def tenancy(self) -> TenancyService | None:
        return getattr(self.server, "tenancy", None)

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
        if self.auth is None or not self.path.startswith("/api/"):
            self.send_error(404)
            return
        if not self._host_ok():
            self._send(403, {"error": "forbidden_host"})
            return
        principal = self._principal()
        if principal is None:
            return
        path, _, query = self.path.partition("?")
        if path == "/api/me":
            orgs = self.tenancy.organizations_of(principal.user_id) if self.tenancy else []
            self._send(200, {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role,
                             "organizations": orgs, "auth_mode": "dev-local-only"})
            return
        match = TENANT_ROUTE.match(path)
        if match:
            if principal.tenant_id is None or match.group(1) != principal.tenant_id:
                # Identity comes from the session; another tenant (existing or not) is denied identically.
                self._send(403, {"error": "forbidden"})
            else:
                self._send(200, {"tenant_id": principal.tenant_id, "role": principal.role})
            return
        self._tenant_call("GET", path, parse_qs(query), principal)

    def do_POST(self) -> None:
        if self.auth is None or not (self.path in AUTH_ROUTES or self.path.startswith("/api/")):
            self.send_error(404)
            return
        data = self._json_body()
        if data is None:
            return
        if self.path.startswith("/api/"):
            principal = self._principal()
            if principal is not None:
                self._tenant_call("POST", self.path, data, principal)
            return
        client = self.client_address[0]
        try:
            if self.path == "/auth/login":
                token, principal = self.auth.login(data.get("username"), data.get("password"), client, data.get("organization_id"))
                self._send(200, self._identity(principal), {"Set-Cookie": self._cookie(token, self.auth.absolute_ttl)})
            elif self.path == "/auth/switch":
                token, principal = self.auth.switch_organization(self._token(), data.get("organization_id"))
                self._send(200, self._identity(principal), {"Set-Cookie": self._cookie(token, self.auth.absolute_ttl)})
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
            elif error.code == "forbidden_organization":
                self._send(403, {"error": "forbidden"})
            else:
                self._send(401, {"error": "unauthenticated"})

    @staticmethod
    def _identity(principal: Principal) -> dict:
        return {"user_id": principal.user_id, "tenant_id": principal.tenant_id, "role": principal.role, "auth_mode": "dev-local-only"}

    # --- tenant-scoped API (PASUL 11) -----------------------------------
    def _tenant_call(self, method: str, path: str, data: dict, principal: Principal) -> None:
        t = self.tenancy
        if t is None:
            self.send_error(404)
            return
        try:
            # The context is rebuilt from the current membership on every request.
            ctx = t.context(principal.user_id, principal.tenant_id)
            one = RESOURCE_ROUTE.match(path)
            if method == "GET" and path == "/api/resources":
                q, kind = data.get("q", [""])[0], data.get("kind", [None])[0]
                self._send(200, {"items": t.search(ctx, q, kind)})
            elif method == "GET" and path == "/api/export":
                self._send(200, t.export(ctx))
            elif method == "GET" and path == "/api/members":
                self._send(200, {"members": t.members(ctx)})
            elif method == "GET" and one and one.group(2) is None:
                self._send(200, t.get(ctx, one.group(1)))
            elif method == "POST" and path == "/api/resources":
                self._send(201, t.create(ctx, data.get("kind"), data.get("title"), data.get("body"),
                                         data.get("visibility", "tenant"), data.get("parent_id")))
            elif method == "POST" and one and one.group(2) == "update":
                self._send(200, t.update(ctx, one.group(1), data.get("title"), data.get("body")))
            elif method == "POST" and one and one.group(2) == "delete":
                t.delete(ctx, one.group(1))
                self._send(204)
            elif method == "POST" and one and one.group(2) == "grant":
                t.grant_read(ctx, one.group(1), data.get("user_id"))
                self._send(204)
            elif method == "POST" and one and one.group(2) == "approve":
                self._send(200, t.approve(ctx, one.group(1)))
            elif method == "POST" and path == "/api/members":
                t.add_member(ctx, data.get("user_id"), data.get("role"))
                self._send(204)
            elif method == "POST" and path == "/api/members/remove":
                t.remove_member(ctx, data.get("user_id"))
                self._send(204)
            else:
                self._send(404, {"error": "not_found"})
        except NotFound:
            self._send(404, {"error": "not_found"})
        except AccessDenied as error:
            self._send(403, {"error": error.code})
        except ValueError:
            self._send(400, {"error": "invalid_request"})
        except Exception:  # last resort: never drop the connection; not reported as a client error
            self._send(500, {"error": "internal_error"})

    def log_message(self, format: str, *args: object) -> None:
        pass  # never log request lines: they could carry identifiers


def build_auth_from_env() -> AuthService:
    """Dev-only bootstrap. No user exists unless the owner supplies a password at runtime."""
    insecure = os.environ.get("REVENUEPILOT_INSECURE_COOKIE") == "1"
    tenancy = TenancyService()
    auth = AuthService(cookie_secure=not insecure, tenancy=tenancy)
    tenancy.user_exists = auth.user_exists
    password = os.environ.get("REVENUEPILOT_DEV_PASSWORD")
    if password:
        role = os.environ.get("REVENUEPILOT_DEV_ROLE", "editor")
        if role not in ROLE_PERMISSIONS:
            raise SystemExit("REVENUEPILOT_DEV_ROLE must be viewer, editor, approver or admin")
        user = auth.add_user(os.environ.get("REVENUEPILOT_DEV_USER", "dev-user"), password)
        if role == "admin":
            tenancy.create_organization("Organizație demo (sintetică)", user.user_id)
        else:
            # Roles do not inherit, so a non-admin dev user needs a separate admin; its random
            # password is discarded: nobody can log in as it (bootstrap only, dev-local-only).
            admin = auth.add_user("dev-bootstrap-admin", secrets.token_urlsafe(32))
            org = tenancy.create_organization("Organizație demo (sintetică)", admin.user_id)
            tenancy.add_member(tenancy.context(admin.user_id, org), user.user_id, role)
        print(f"auth: DEV-LOCAL-ONLY user enabled (synthetic organization, role {role})", file=sys.stderr)
    else:
        print("auth: no dev user configured; all protected routes deny", file=sys.stderr)
    return auth


def serve() -> None:
    # Loopback only: dev authentication, no tenant isolation of data, no persistence.
    port = int(os.environ.get("REVENUEPILOT_PORT", "8765"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.auth = build_auth_from_env()
    server.tenancy = server.auth.tenancy
    try:
        server.serve_forever()
    finally:
        server.server_close()
