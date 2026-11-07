"""Budgets, quotas, kill switch and the single gate before any external effect (PASUL 14).

In-memory reference implementation (persistence and outbox arrive with the orchestrator,
PASUL 18). There is NO real provider here: every provider is DISABLED until explicitly
configured, and a disabled provider can never be called. Subscriptions (Codex, Claude,
ChatGPT) are not APIs and are never modelled as one.

Rules enforced, all fail-closed:
* money is integer minor units plus a currency; unknown, negative, non-integer or
  mismatched cost -> DENY; an undefined cap at any level -> DENY (never "unlimited");
* a reservation is checked atomically against global, tenant, provider and task caps:
  reserved + consumed + estimate <= cap at every level;
* spending needs an explicit, unexpired, single-use approval from an approver of the same
  tenant whose maximum covers the estimate (the automatic threshold defaults to zero);
* STOP at global / tenant / integration level wins; unreadable state means STOP; a STOP
  bumps an epoch so permits issued earlier never work again; agents can request STOP but
  never START;
* the only way to run an external call is `Dispatcher.run`, which re-validates everything
  and consumes a single-use permit before the adapter is invoked;
* an unknown outcome keeps the money reserved and blocks automatic retries until reconciled;
* retries are bounded and a per-provider circuit breaker opens after repeated failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import secrets
import threading
import time
from typing import Callable

from .observability import Observability


class Denied(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class TimeoutAfterSend(Exception):
    """Raised by an adapter when the request may have reached the provider (outcome unknown)."""


class ProviderDisabled(Exception):
    pass


@dataclass
class Reservation:
    id: str
    tenant_id: str
    provider: str
    task_id: str
    currency: str
    estimate: int
    idem_key: str
    status: str = "RESERVED"  # RESERVED | SETTLED | RELEASED | UNKNOWN_OUTCOME
    attempts: int = 0
    actual: int | None = None
    overrun: bool = False
    permit: str | None = None
    permit_epoch: int = 0


@dataclass(frozen=True)
class Permit:
    reservation_id: str
    tenant_id: str
    token: str
    epoch: int


@dataclass
class _Approval:
    tenant_id: str
    max_amount: int
    currency: str
    expires_at: float
    uses_left: int = 1


@dataclass
class _Circuit:
    failures: int = 0
    opened_at: float | None = None
    probing: bool = False


class Guardrails:
    def __init__(self, clock: Callable[[], float] = time.time, obs: Observability | None = None,
                 max_retries: int = 2, breaker_threshold: int = 3, breaker_cooldown: float = 60.0,
                 stop_reader: Callable[[], None] | None = None) -> None:
        self._clock = clock
        self._obs = obs
        self.max_retries = max_retries
        self.breaker_threshold = breaker_threshold
        self.breaker_cooldown = breaker_cooldown
        self._stop_reader = stop_reader  # may raise: an unreadable STOP store means STOP
        self._lock = threading.RLock()
        self._caps: dict[tuple, int] = {}  # ("global",) ("tenant",t) ("provider",t,p) ("task",t,task)
        self._currency: dict[tuple, str] = {}
        self._thresholds: dict[str, int] = {}
        self._providers: dict[str, str] = {}  # name -> DISABLED | ENABLED | QUOTA_EXHAUSTED
        self._stops: dict[tuple, bool] = {}
        self.epoch = 0
        self._reservations: dict[str, Reservation] = {}
        self._by_key: dict[tuple[str, str], str] = {}
        self._approvals: dict[str, _Approval] = {}
        self._circuits: dict[tuple[str, str], _Circuit] = {}

    # --- configuration (operator / tenant admin; not reachable by agents) ----------------
    def set_cap(self, scope: tuple, amount: int, currency: str) -> None:
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("cap must be a non-negative integer of minor units")
        with self._lock:
            self._caps[scope] = amount
            self._currency[scope] = currency

    def set_auto_threshold(self, tenant_id: str, amount: int) -> None:
        with self._lock:
            self._thresholds[tenant_id] = amount

    def set_provider(self, name: str, state: str) -> None:
        if state not in {"DISABLED", "ENABLED", "QUOTA_EXHAUSTED"}:
            raise ValueError("unknown provider state")
        with self._lock:
            self._providers[name] = state

    # --- kill switch -----------------------------------------------------------------------
    def stop(self, level: str, key: str = "") -> None:
        """Anyone (including an agent) may request STOP; it never needs confirmation."""
        with self._lock:
            self._stops[(level, key)] = True
            self.epoch += 1
            self._note("stop", f"{level}:{key}"[:64])

    def start(self, level: str, key: str, actor_kind: str) -> None:
        if actor_kind != "human":
            raise Denied("agent_cannot_start")
        with self._lock:
            self._stops.pop((level, key), None)
            self.epoch += 1  # a START never revives permits issued before it
            self._note("start", f"{level}:{key}"[:64])

    def _stopped(self, tenant_id: str, provider: str) -> bool:
        if self._stop_reader is not None:
            try:
                self._stop_reader()
            except Exception:
                return True  # unreadable state -> STOP
        return any(self._stops.get(k) for k in (("global", ""), ("tenant", tenant_id), ("integration", provider)))

    # --- approvals -------------------------------------------------------------------------
    def approve_spend(self, tenant_id: str, approver_role: str, max_amount: int, currency: str,
                      ttl_seconds: float, uses: int = 1) -> str:
        if approver_role != "approver":
            raise Denied("not_approver")
        if not isinstance(max_amount, int) or isinstance(max_amount, bool) or max_amount <= 0 or ttl_seconds <= 0:
            raise Denied("invalid_approval")
        with self._lock:
            approval_id = "ap_" + secrets.token_hex(6)
            self._approvals[approval_id] = _Approval(tenant_id, max_amount, currency, self._clock() + ttl_seconds, uses)
            return approval_id

    # --- reservation -----------------------------------------------------------------------
    def reserve(self, tenant_id: str, provider: str, task_id: str, estimate: object, currency: str,
                idem_key: str, approval_id: str | None = None) -> tuple[Reservation, Permit]:
        with self._lock:
            try:
                result = self._reserve(tenant_id, provider, task_id, estimate, currency, idem_key, approval_id)
            except Denied as denied:
                self._note("reserve", denied.code, tenant_id, provider, estimate, currency)
                raise
            self._note("reserve", "allow", tenant_id, provider, estimate, currency)
            return result

    def _reserve(self, tenant_id, provider, task_id, estimate, currency, idem_key, approval_id):
        existing = self._by_key.get((tenant_id, idem_key))
        if existing is not None:
            r = self._reservations[existing]
            if (r.provider, r.task_id, r.estimate, r.currency) != (provider, task_id, estimate, currency):
                raise Denied("idempotency_conflict")
            if r.status != "RESERVED" or r.attempts > 0:
                raise Denied("duplicate_request")  # already dispatched or settled: never a second charge
            return r, self._issue_permit(r)  # pristine replay: same reservation, fresh permit
        if not isinstance(estimate, int) or isinstance(estimate, bool) or estimate <= 0:
            raise Denied("unknown_cost")
        if self._stopped(tenant_id, provider):
            raise Denied("stopped")
        state = self._providers.get(provider, "DISABLED")
        if state != "ENABLED":
            raise Denied("provider_disabled" if state == "DISABLED" else "provider_quota_exhausted")
        if self._circuit_blocks(tenant_id, provider):
            raise Denied("circuit_open")
        scopes = [("global",), ("tenant", tenant_id), ("provider", tenant_id, provider), ("task", tenant_id, task_id)]
        for scope in scopes:
            if scope not in self._caps:
                raise Denied("cap_undefined")
            if self._currency[scope] != currency:
                raise Denied("currency_mismatch")
            if self._used(scope) + estimate > self._caps[scope]:
                raise Denied("budget_exceeded")
        if estimate > self._thresholds.get(tenant_id, 0):
            self._consume_approval(approval_id, tenant_id, estimate, currency)
        r = Reservation("res_" + secrets.token_hex(6), tenant_id, provider, task_id, currency, estimate, idem_key)
        self._reservations[r.id] = r
        self._by_key[(tenant_id, idem_key)] = r.id
        return r, self._issue_permit(r)

    def _consume_approval(self, approval_id, tenant_id, estimate, currency) -> None:
        a = self._approvals.get(approval_id or "")
        if a is None or a.tenant_id != tenant_id:
            raise Denied("approval_required")
        if self._clock() >= a.expires_at:
            raise Denied("approval_expired")
        if a.currency != currency or a.max_amount < estimate:
            raise Denied("approval_too_low")
        if a.uses_left <= 0:
            raise Denied("approval_used")
        a.uses_left -= 1

    def _issue_permit(self, r: Reservation) -> Permit:
        r.permit, r.permit_epoch = secrets.token_urlsafe(16), self.epoch
        return Permit(r.id, r.tenant_id, r.permit, self.epoch)

    def _used(self, scope: tuple) -> int:
        """reserved + consumed for a scope (RESERVED and UNKNOWN keep money held; SETTLED is spent)."""
        total = 0
        for r in self._reservations.values():
            if r.status == "RELEASED":
                continue
            if scope == ("global",) or (scope[0] == "tenant" and r.tenant_id == scope[1]) \
                    or (scope[0] == "provider" and (r.tenant_id, r.provider) == scope[1:]) \
                    or (scope[0] == "task" and (r.tenant_id, r.task_id) == scope[1:]):
                total += r.actual if r.status == "SETTLED" and r.actual is not None else r.estimate
        return total

    def available(self, scope: tuple) -> int:
        with self._lock:
            return self._caps.get(scope, 0) - self._used(scope)

    # --- settlement ------------------------------------------------------------------------
    def _get(self, tenant_id: str, reservation_id: str) -> Reservation:
        r = self._reservations.get(reservation_id)
        if r is None or r.tenant_id != tenant_id:
            raise Denied("not_found")
        return r

    def settle(self, tenant_id: str, reservation_id: str, actual: int) -> Reservation:
        with self._lock:
            r = self._get(tenant_id, reservation_id)
            if r.status not in ("RESERVED", "UNKNOWN_OUTCOME") or not isinstance(actual, int) \
                    or isinstance(actual, bool) or actual < 0:
                raise Denied("invalid_settlement")
            r.status, r.actual, r.overrun = "SETTLED", actual, actual > r.estimate
            if r.overrun:  # the provider charged more than estimated: pause the provider for review
                self.stop("integration", r.provider)
            self._note("settle", "overrun" if r.overrun else "allow", tenant_id, r.provider, actual, r.currency)
            return r

    def release(self, tenant_id: str, reservation_id: str, confirmed_no_effect: bool = False) -> Reservation:
        """Release held money only if nothing was dispatched, or the caller confirms no effect occurred."""
        with self._lock:
            r = self._get(tenant_id, reservation_id)
            if r.status != "RESERVED" or (r.attempts > 0 and not confirmed_no_effect):
                raise Denied("cannot_release")
            r.status = "RELEASED"
            return r

    def mark_unknown(self, tenant_id: str, reservation_id: str) -> None:
        with self._lock:
            self._get(tenant_id, reservation_id).status = "UNKNOWN_OUTCOME"

    def reconcile(self, tenant_id: str, reservation_id: str, actual: int | None) -> Reservation:
        """Resolve an unknown outcome from a receipt/status query; `None` keeps the money held."""
        with self._lock:
            r = self._get(tenant_id, reservation_id)
            if r.status != "UNKNOWN_OUTCOME":
                raise Denied("invalid_settlement")
            return r if actual is None else self.settle(tenant_id, reservation_id, actual)

    # --- circuit breaker -------------------------------------------------------------------
    def _circuit_blocks(self, tenant_id: str, provider: str) -> bool:
        c = self._circuits.get((tenant_id, provider))
        if c is None or c.opened_at is None:
            return False
        if self._clock() - c.opened_at < self.breaker_cooldown:
            return True
        if c.probing:
            return True  # half-open: one probe at a time
        c.probing = True
        return False

    def _record_outcome(self, tenant_id: str, provider: str, ok: bool) -> None:
        c = self._circuits.setdefault((tenant_id, provider), _Circuit())
        if ok:
            c.failures, c.opened_at, c.probing = 0, None, False
        else:
            c.failures += 1
            c.probing = False
            if c.failures >= self.breaker_threshold or c.opened_at is not None:
                c.opened_at = self._clock()

    # --- the gate --------------------------------------------------------------------------
    def authorize_dispatch(self, permit: Permit) -> Reservation:
        """Re-validate everything, then consume the single-use permit. Called before any effect."""
        with self._lock:
            try:
                r = self._authorize(permit)
            except Denied as denied:
                self._note("dispatch", denied.code, permit.tenant_id, "-", None, "-")
                raise
            self._note("dispatch", "allow", r.tenant_id, r.provider, r.estimate, r.currency)
            return r

    def _authorize(self, permit: Permit) -> Reservation:
        r = self._get(permit.tenant_id, permit.reservation_id)
        if r.permit is None or r.permit != permit.token or r.permit_epoch != self.epoch or permit.epoch != self.epoch:
            raise Denied("permit_invalid")  # used, replaced, or issued before a STOP/START
        if r.status == "UNKNOWN_OUTCOME":
            raise Denied("unknown_outcome_requires_reconciliation")
        if r.status != "RESERVED":
            raise Denied("not_reserved")
        if self._stopped(r.tenant_id, r.provider):
            raise Denied("stopped")
        if self._providers.get(r.provider, "DISABLED") != "ENABLED":
            raise Denied("provider_disabled")
        if r.attempts > self.max_retries:
            raise Denied("max_retries")
        r.attempts += 1
        r.permit = None  # single use: a retry needs a fresh permit from `renew_permit`
        return r

    def renew_permit(self, tenant_id: str, reservation_id: str) -> Permit:
        """Fresh permit for an automatic retry; denied for unknown outcomes and after max retries."""
        with self._lock:
            r = self._get(tenant_id, reservation_id)
            if r.status == "UNKNOWN_OUTCOME":
                raise Denied("unknown_outcome_requires_reconciliation")
            if r.status != "RESERVED":
                raise Denied("not_reserved")
            if r.attempts > self.max_retries:
                raise Denied("max_retries")
            if self._stopped(r.tenant_id, r.provider):
                raise Denied("stopped")
            return self._issue_permit(r)

    def _note(self, action: str, decision: str, tenant_id: str | None = None, provider: str | None = None,
              amount: object = None, currency: str | None = None) -> None:
        if self._obs is not None:
            self._obs.emit("budget.decision", level="info" if decision == "allow" else "warning", tenant_id=tenant_id,
                           action=action, decision=decision, provider=provider, amount_minor=amount, currency=currency)


class Dispatcher:
    """The only path to an external call. The adapter is invoked after authorization, never before."""

    def __init__(self, guard: Guardrails) -> None:
        self.guard = guard

    def run(self, permit: Permit, adapter: Callable[[Reservation], object]) -> object:
        r = self.guard.authorize_dispatch(permit)  # raises Denied: the adapter is not called
        try:
            result = adapter(r)
        except TimeoutAfterSend:
            with self.guard._lock:
                r.status = "UNKNOWN_OUTCOME"
                self.guard._record_outcome(r.tenant_id, r.provider, False)
            raise
        except Exception:
            with self.guard._lock:
                self.guard._record_outcome(r.tenant_id, r.provider, False)
            raise
        with self.guard._lock:
            self.guard._record_outcome(r.tenant_id, r.provider, True)
        return result
