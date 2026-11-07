"""Dependency-free identity, session and login controls (PASUL 10).

Scope: local development authentication only. There is no external OAuth/OIDC
provider, no persistent store and no account recovery. Users and sessions live
in memory. Every deny path returns a generic reason; unknown states deny.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import secrets
import threading
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .tenancy import TenancyService

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_MAX_N = 2**15  # refuse stored hashes that would force excessive CPU/RAM
SCRYPT_MAXMEM = 64 * 1024 * 1024
MIN_PASSWORD = 12
MAX_PASSWORD = 256


class AuthError(Exception):
    """Raised for any authentication failure; `code` is a stable reason code."""

    def __init__(self, code: str, retry_after: int = 0) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


def hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
        dklen=32, maxmem=SCRYPT_MAXMEM,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        n, r, p = int(n), int(r), int(p)
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(digest_hex)
        if scheme != "scrypt" or not (2 <= n <= SCRYPT_MAX_N) or not (1 <= r <= 8) or not (1 <= p <= 4):
            return False
        if len(password) > MAX_PASSWORD:
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
            dklen=len(expected), maxmem=SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError, MemoryError):
        return False
    return hmac.compare_digest(actual, expected)


def _check_new_password(password: object) -> str:
    if not isinstance(password, str) or not (MIN_PASSWORD <= len(password) <= MAX_PASSWORD):
        raise ValueError(f"password must be {MIN_PASSWORD}-{MAX_PASSWORD} characters")
    return password


@dataclass
class User:
    user_id: str
    username: str
    password_hash: str
    active: bool = True
    auth_version: int = 1


@dataclass
class Session:
    user_id: str
    created_at: float
    last_seen: float
    auth_version: int
    active_org: str | None = None


@dataclass(frozen=True)
class Principal:
    """Identity derived server-side on every request; never taken from the client.

    tenant_id/role are None when the session has no active organization or the
    membership was revoked; callers must then deny tenant-scoped access.
    """

    user_id: str
    tenant_id: str | None
    role: str | None


class AuthService:
    def __init__(
        self,
        clock: Callable[[], float] = time.time,
        idle_ttl: int = 1800,
        absolute_ttl: int = 8 * 3600,
        max_failures: int = 5,
        lockout_seconds: int = 60,
        max_sessions_per_user: int = 5,
        cookie_secure: bool = True,
        tenancy: "TenancyService | None" = None,
    ) -> None:
        self.tenancy = tenancy
        self._clock = clock
        self.idle_ttl = idle_ttl
        self.absolute_ttl = absolute_ttl
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self.max_sessions_per_user = max_sessions_per_user
        self.cookie_secure = cookie_secure
        self.cookie_name = "__Host-rp_session" if cookie_secure else "rp_session"
        self._lock = threading.Lock()
        self._users: dict[str, User] = {}
        self._by_name: dict[str, str] = {}
        self._sessions: dict[str, Session] = {}  # key: sha256(token); raw token is never stored
        self._failures: dict[tuple[str, str], tuple[int, float]] = {}
        self._dummy_hash = hash_password(secrets.token_urlsafe(16))

    @staticmethod
    def _norm(username: object) -> str:
        if not isinstance(username, str):
            raise ValueError("username must be a string")
        name = username.strip().lower()
        if not (3 <= len(name) <= 64):
            raise ValueError("username must be 3-64 characters")
        return name

    @staticmethod
    def _key(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def add_user(self, username: str, password: str) -> User:
        """Users are global identities; organization access comes only from memberships."""
        name = self._norm(username)
        _check_new_password(password)
        password_hash = hash_password(password)
        with self._lock:
            if name in self._by_name:
                raise ValueError("username exists")
            user = User("u_" + secrets.token_hex(8), name, password_hash)
            self._users[user.user_id] = user
            self._by_name[name] = user.user_id
            return user

    def user_exists(self, user_id: str) -> bool:
        with self._lock:
            return user_id in self._users

    def _principal(self, user: User, org_id: str | None) -> Principal:
        m = self.tenancy.membership(user.user_id, org_id) if self.tenancy and org_id else None
        return Principal(user.user_id, m.org_id if m else None, m.role if m else None)

    def _initial_org(self, user_id: str, requested: object) -> str | None:
        orgs = self.tenancy.organizations_of(user_id) if self.tenancy else []
        if requested is not None:
            if requested not in orgs:
                raise AuthError("forbidden_organization")
            return requested
        return orgs[0] if len(orgs) == 1 else None  # several memberships: caller must choose

    def deactivate_user(self, user_id: str) -> None:
        with self._lock:
            if user_id in self._users:
                self._users[user_id].active = False

    def _blocked(self, key: tuple[str, str], now: float) -> int:
        count, until = self._failures.get(key, (0, 0.0))
        if count >= self.max_failures and now < until:
            return max(1, int(until - now + 0.999))
        if count >= self.max_failures and now >= until:
            self._failures.pop(key, None)
        return 0

    def _record_failure(self, key: tuple[str, str], now: float) -> None:
        if len(self._failures) > 10_000:
            self._failures = {k: v for k, v in self._failures.items() if v[1] > now}
        count, _ = self._failures.get(key, (0, 0.0))
        self._failures[key] = (count + 1, now + self.lockout_seconds)

    def login(self, username: object, password: object, client_id: str, organization_id: object = None) -> tuple[str, Principal]:
        try:
            name = self._norm(username)
        except ValueError:
            name = ""
        if not isinstance(password, str):
            password = ""
        now = self._clock()
        key = (client_id, name)
        with self._lock:
            wait = self._blocked(key, now)
            if wait:
                raise AuthError("rate_limited", wait)
            user = self._users.get(self._by_name.get(name, ""))
            stored = user.password_hash if user else self._dummy_hash
        # Verify outside the lock; unknown users cost the same as wrong passwords.
        ok = verify_password(password, stored) and user is not None
        with self._lock:
            if not ok or user is None or not user.active:
                self._record_failure(key, now)
                raise AuthError("invalid_credentials")
            self._failures.pop(key, None)
        org = self._initial_org(user.user_id, organization_id)
        with self._lock:
            token = self._create_session(user, now, org)
            return token, self._principal(user, org)

    def _create_session(self, user: User, now: float, active_org: str | None = None) -> str:
        self._purge(now)
        mine = sorted(
            (k for k, s in self._sessions.items() if s.user_id == user.user_id),
            key=lambda k: self._sessions[k].created_at,
        )
        for old in mine[: max(0, len(mine) - self.max_sessions_per_user + 1)]:
            del self._sessions[old]
        token = secrets.token_urlsafe(32)
        self._sessions[self._key(token)] = Session(user.user_id, now, now, user.auth_version, active_org)
        return token

    def _purge(self, now: float) -> None:
        for k in [k for k, s in self._sessions.items() if self._expired(s, now)]:
            del self._sessions[k]

    def _expired(self, s: Session, now: float) -> bool:
        return now - s.last_seen > self.idle_ttl or now - s.created_at > self.absolute_ttl

    def authenticate(self, token: str | None) -> Principal:
        """Re-authorize from current server state on every call."""
        if not token or len(token) > 128:
            raise AuthError("unauthenticated")
        now = self._clock()
        key = self._key(token)
        with self._lock:
            session = self._sessions.get(key)
            if session is None:
                raise AuthError("unauthenticated")
            user = self._users.get(session.user_id)
            if (
                user is None
                or not user.active
                or session.auth_version != user.auth_version
                or self._expired(session, now)
            ):
                del self._sessions[key]
                raise AuthError("unauthenticated")
            session.last_seen = now
            active_org = session.active_org
        # Membership is re-read on every request: revocation takes effect immediately.
        return self._principal(user, active_org)

    def switch_organization(self, token: str | None, org_id: object) -> tuple[str, Principal]:
        """Changing tenant re-checks membership and rotates the session token."""
        principal = self.authenticate(token)
        if not isinstance(org_id, str) or not self.tenancy or self.tenancy.membership(principal.user_id, org_id) is None:
            raise AuthError("forbidden_organization")
        with self._lock:
            old = self._sessions.pop(self._key(token), None)
            user = self._users.get(principal.user_id)
            if old is None or user is None:
                raise AuthError("unauthenticated")
            new_token = secrets.token_urlsafe(32)
            self._sessions[self._key(new_token)] = Session(user.user_id, old.created_at, self._clock(), old.auth_version, org_id)
        return new_token, self._principal(user, org_id)

    def logout(self, token: str | None) -> None:
        if token:
            with self._lock:
                self._sessions.pop(self._key(token), None)

    def change_password(self, token: str, current: object, new: object, client_id: str) -> str:
        """Sensitive action: requires the current password; revokes every session."""
        principal = self.authenticate(token)
        new_password = _check_new_password(new)
        now = self._clock()
        key = (client_id, "pw:" + principal.user_id)
        with self._lock:
            wait = self._blocked(key, now)
            if wait:
                raise AuthError("rate_limited", wait)
            user = self._users[principal.user_id]
            stored = user.password_hash
        if not isinstance(current, str) or not verify_password(current, stored):
            with self._lock:
                self._record_failure(key, now)
            raise AuthError("invalid_credentials")
        new_hash = hash_password(new_password)
        with self._lock:
            user.password_hash = new_hash
            user.auth_version += 1
            self._failures.pop(key, None)
            active = next((s.active_org for k, s in self._sessions.items() if k == self._key(token)), None)
            for k in [k for k, s in self._sessions.items() if s.user_id == user.user_id]:
                del self._sessions[k]
            return self._create_session(user, now, active)
