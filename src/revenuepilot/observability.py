"""Structured events, trace IDs, redaction and a tamper-evident bounded log (PASUL 13).

Design rules (threat T11, Meta §10, §17.4):
* Events are built from a closed schema: an unknown event name or field is dropped, so a
  new code path cannot start logging arbitrary data by accident.
* Redaction happens at the source, before anything is stored or written: sensitive field
  names are masked, and string values are scanned for emails, phone numbers, bearer
  tokens, well-known key formats and long token-like strings.
* Only scalar values are accepted; containers are dropped (no nested secrets).
* The buffer is bounded (no unbounded global memory); eviction is counted, and the hash
  chain keeps an anchor so the retained window can still be verified.
* Events carry a tenant and are only returned to that tenant by `trace()`.

Redaction is pattern based and can miss formats it does not know (declared residual risk).
Events are in memory only; durable audit storage is a later step.
"""

from __future__ import annotations

from collections import deque
import contextvars
import hashlib
import json
import re
import secrets
import threading
import time
from typing import Callable, TextIO

current_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="-")

EVENTS: dict[str, frozenset[str]] = {
    "request.received": frozenset({"method", "route"}),
    "request.completed": frozenset({"method", "route", "status", "duration_ms", "cost_units"}),
    "request.error": frozenset({"error_class"}),
    "auth.login": frozenset({"outcome", "reason"}),
    "auth.logout": frozenset(),
    "authz.decision": frozenset({"action", "target", "decision"}),
}
LEVELS = frozenset({"info", "warning", "error"})
MAX_VALUE = 200
REDACTED = "[REDACTED]"
SENSITIVE_KEY = re.compile(r"(?i)(pass(word|wd)?|secret|token|authorization|cookie|api[_-]?key|credential|private|session)")
TRACE_ID = re.compile(r"^[0-9a-f]{16}$")

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{6,}"), "Bearer " + REDACTED),
    (re.compile(r"(?i)\b(?:sk|pk|ghp|gho|ghs|xox[baprs])[-_][A-Za-z0-9_-]{12,}"), REDACTED),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[REDACTED:email]"),
    # Not inside identifiers such as u_0123456789ab: a digit run must stand alone.
    (re.compile(r"(?<![A-Za-z0-9_])\+?\d[\d\s().-]{7,}\d(?![A-Za-z0-9_])"), "[REDACTED:phone]"),
    (re.compile(r"\b[A-Za-z0-9_-]{32,}\b"), "[REDACTED:token]"),
)


def redact_text(value: str) -> str:
    for pattern, replacement in _PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def redact_field(name: str, value: object) -> object:
    """Return a safe scalar, or raise TypeError when the value is not an accepted scalar."""
    if SENSITIVE_KEY.search(name):
        return REDACTED
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return redact_text(value)[:MAX_VALUE]
    raise TypeError("only scalar values are logged")


def new_trace_id() -> str:
    return secrets.token_hex(8)


def _canonical(record: dict) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


class Observability:
    def __init__(self, capacity: int = 2000, clock: Callable[[], float] = time.time,
                 stream: TextIO | None = None) -> None:
        self._events: deque[dict] = deque()
        self._capacity = capacity
        self._clock = clock
        self._stream = stream
        self._lock = threading.Lock()
        self._seq = 0
        self._last_hash = "0" * 64
        self._anchor = "0" * 64
        self.dropped_events = 0  # evicted by the bounded buffer
        self.rejected_events = 0  # unknown event name or invalid level

    def emit(self, name: str, level: str = "info", tenant_id: str | None = None,
             user_id: str | None = None, **fields: object) -> dict | None:
        allowed = EVENTS.get(name)
        if allowed is None or level not in LEVELS:
            with self._lock:
                self.rejected_events += 1
            return None
        clean: dict[str, object] = {}
        for key, value in fields.items():
            if key not in allowed:
                continue  # closed schema: unknown fields are dropped, never logged
            try:
                clean[key] = redact_field(key, value)
            except TypeError:
                continue
        with self._lock:
            self._seq += 1
            record = {
                "seq": self._seq, "ts": round(self._clock(), 6), "level": level, "name": name,
                "trace_id": current_trace_id.get(),
                "tenant_id": redact_text(str(tenant_id))[:64] if tenant_id else "-",
                "user_id": redact_text(str(user_id))[:64] if user_id else "-",
                "fields": clean, "prev": self._last_hash,
            }
            record["hash"] = hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()
            self._last_hash = record["hash"]
            self._events.append(record)
            while len(self._events) > self._capacity:
                evicted = self._events.popleft()
                self._anchor = evicted["hash"]
                self.dropped_events += 1
            if self._stream is not None:
                self._stream.write(json.dumps(record, sort_keys=True, ensure_ascii=True) + "\n")
            return record

    def verify_chain(self) -> bool:
        """True if the retained window is an unbroken, unmodified hash chain."""
        with self._lock:
            prev = self._anchor
            for record in self._events:
                body = {k: v for k, v in record.items() if k != "hash"}
                if record["prev"] != prev or hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest() != record["hash"]:
                    return False
                prev = record["hash"]
            return True

    def trace(self, trace_id: str, tenant_id: str) -> list[dict]:
        """Reconstruct one request path, restricted to the caller's tenant (no cross-tenant reads)."""
        if not TRACE_ID.match(trace_id or ""):
            return []
        with self._lock:
            same = [e for e in self._events if e["trace_id"] == trace_id]
            if not any(e["tenant_id"] == tenant_id for e in same):
                return []  # the trace never touched this tenant
            # Events recorded before authentication carry tenant "-" (method and route only).
            return [dict(e) for e in same if e["tenant_id"] in (tenant_id, "-")]

    def snapshot(self) -> list[dict]:
        """All retained events; platform operator / tests only, never exposed over HTTP."""
        with self._lock:
            return [dict(e) for e in self._events]
