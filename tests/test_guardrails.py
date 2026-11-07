"""PASUL 14: budgets, approvals, kill switch, retries, circuit breaker and the dispatch gate.

There is no real provider: adapters below are local fakes that count their calls.
"""

from pathlib import Path
import secrets
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from revenuepilot.guardrails import Denied, Dispatcher, Guardrails, TimeoutAfterSend
from revenuepilot.observability import Observability


class Clock:
    def __init__(self):
        self.now = 1_000.0

    def __call__(self):
        return self.now


class Adapter:
    """Fake external provider: counts calls so tests can prove 'zero unauthorized calls'."""

    def __init__(self, behaviour="ok"):
        self.calls, self.behaviour = 0, behaviour

    def __call__(self, reservation):
        self.calls += 1
        if self.behaviour == "timeout":
            raise TimeoutAfterSend()
        if self.behaviour == "error":
            raise RuntimeError("provider rejected")
        return "done"


class Base(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.obs = Observability()
        self.g = Guardrails(clock=self.clock, obs=self.obs)
        self.d = Dispatcher(self.g)
        self.g.set_provider("p1", "ENABLED")
        for scope, cap in ((("global",), 1000), (("tenant", "A"), 500), (("tenant", "B"), 500),
                           (("provider", "A", "p1"), 400), (("provider", "B", "p1"), 400),
                           (("task", "A", "t1"), 300), (("task", "A", "t2"), 300), (("task", "B", "t1"), 300)):
            self.g.set_cap(scope, cap, "EUR")
        self.g.set_auto_threshold("A", 10_000)  # small spends are automatic unless a test resets it
        self.g.set_auto_threshold("B", 10_000)
        self.n = 0

    def key(self):
        self.n += 1
        return f"k{self.n}"

    def reserve(self, tenant="A", task="t1", amount=100, provider="p1", currency="EUR", key=None, approval=None):
        return self.g.reserve(tenant, provider, task, amount, currency, key or self.key(), approval)

    def deny(self, code, *args, **kwargs):
        with self.assertRaises(Denied) as e:
            self.reserve(*args, **kwargs)
        self.assertEqual(e.exception.code, code)


class BudgetTest(Base):
    def test_over_budget_is_blocked_deterministically_at_every_level(self):
        self.reserve(amount=300)  # task t1 is now full
        self.deny("budget_exceeded", amount=1)  # task cap
        self.reserve(task="t2", amount=100)  # tenant A: 400 used, provider cap 400 reached
        self.deny("budget_exceeded", task="t2", amount=1)  # provider cap (400) before tenant cap (500)
        self.g.set_cap(("provider", "A", "p1"), 450, "EUR")
        self.reserve(task="t2", amount=50)  # exactly at the provider cap
        self.deny("budget_exceeded", task="t2", amount=1)
        self.g.set_cap(("tenant", "B"), 500, "EUR")
        self.reserve(tenant="B", amount=200)
        self.g.set_cap(("global",), 750, "EUR")
        self.deny("budget_exceeded", tenant="B", amount=101)  # global cap: 750 - 450 - 200 = 100
        self.reserve(tenant="B", amount=100)
        self.assertEqual(self.g.available(("global",)), 0)

    def test_undefined_cap_unknown_cost_and_currency_are_denied(self):
        self.deny("cap_undefined", task="t-without-cap")
        self.deny("cap_undefined", tenant="C")
        for bad in (None, 0, -5, 1.5, "100", True, [100]):
            self.deny("unknown_cost", amount=bad)
        self.deny("currency_mismatch", currency="USD")
        self.assertEqual(self.g.available(("tenant", "A")), 500)  # nothing was reserved

    def test_concurrent_requests_never_exceed_the_cap(self):
        self.g.set_cap(("task", "A", "t1"), 100, "EUR")
        results = []

        def worker():
            try:
                self.reserve(amount=15)
                results.append("ok")
            except Denied as e:
                results.append(e.code)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(results.count("ok"), 6)  # floor(100 / 15)
        self.assertEqual(results.count("budget_exceeded"), 14)
        self.assertEqual(self.g.available(("task", "A", "t1")), 100 - 6 * 15)

    def test_idempotency_one_charge_per_key(self):
        adapter = Adapter()
        _, permit = self.g.reserve("A", "p1", "t1", 100, "EUR", "same")
        self.d.run(permit, adapter)  # dispatched once
        self.deny("duplicate_request", amount=100, key="same")  # a replay after dispatch is never a second charge
        r2, _ = self.g.reserve("A", "p1", "t1", 100, "EUR", "fresh")
        r3, _ = self.g.reserve("A", "p1", "t1", 100, "EUR", "fresh")  # pristine replay: same reservation
        self.assertEqual(r2.id, r3.id)
        self.deny("idempotency_conflict", amount=250, key="fresh")
        self.assertEqual((self.g.available(("tenant", "A")), adapter.calls), (500 - 100 - 100, 1))

    def test_tenants_cannot_touch_each_others_reservations(self):
        r, permit = self.reserve(tenant="A")
        for op in (lambda: self.g.settle("B", r.id, 1), lambda: self.g.release("B", r.id), lambda: self.g.renew_permit("B", r.id),
                   lambda: self.g.authorize_dispatch(type(permit)(r.id, "B", permit.token, permit.epoch))):
            with self.assertRaises(Denied) as e:
                op()
            self.assertEqual(e.exception.code, "not_found")


class ApprovalTest(Base):
    def setUp(self):
        super().setUp()
        self.g.set_auto_threshold("A", 0)  # default policy: every spend needs explicit approval
        self.g.set_auto_threshold("B", 0)

    def test_spend_requires_explicit_valid_single_use_approval(self):
        self.deny("approval_required")
        self.deny("approval_required", approval="ap_unknown")
        with self.assertRaises(Denied) as e:
            self.g.approve_spend("A", "editor", 500, "EUR", 60)
        self.assertEqual(e.exception.code, "not_approver")
        low = self.g.approve_spend("A", "approver", 50, "EUR", 60)
        self.deny("approval_too_low", amount=100, approval=low)
        ok = self.g.approve_spend("A", "approver", 100, "EUR", 60)
        self.deny("approval_required", tenant="B", approval=ok)  # another tenant's approval is useless
        self.reserve(amount=100, approval=ok)
        self.deny("approval_used", amount=100, approval=ok)
        old = self.g.approve_spend("A", "approver", 100, "EUR", 60)
        self.clock.now += 61
        self.deny("approval_expired", amount=100, approval=old)
        self.deny("approval_too_low", amount=100, approval=self.g.approve_spend("A", "approver", 100, "USD", 60))
        self.assertEqual(self.g.available(("tenant", "A")), 400)  # only the one approved spend is held

    def test_budget_still_applies_with_an_approval(self):
        big = self.g.approve_spend("A", "approver", 10_000, "EUR", 60)
        self.deny("budget_exceeded", amount=301, approval=big)


class KillSwitchTest(Base):
    def test_stop_blocks_reservation_and_already_issued_permits_with_zero_calls(self):
        adapter = Adapter()
        _, permit = self.reserve()
        self.g.stop("tenant", "A")
        self.deny("stopped")
        with self.assertRaises(Denied) as e:
            self.d.run(permit, adapter)
        self.assertEqual(e.exception.code, "permit_invalid")
        self.assertEqual(adapter.calls, 0)
        self.reserve(tenant="B")  # other tenants are unaffected

    def test_all_three_levels_and_restrictive_wins(self):
        for level, key, tenant in (("global", "", "A"), ("tenant", "A", "A"), ("integration", "p1", "B")):
            self.g.stop(level, key)
            self.deny("stopped", tenant=tenant)
            self.g.start(level, key, "human")
        self.reserve()

    def test_agent_cannot_start_and_start_does_not_revive_old_permits(self):
        _, old_permit = self.reserve()
        self.g.stop("global")
        with self.assertRaises(Denied) as e:
            self.g.start("global", "", "agent")
        self.assertEqual(e.exception.code, "agent_cannot_start")
        self.deny("stopped")
        self.g.start("global", "", "human")
        adapter = Adapter()
        with self.assertRaises(Denied):
            self.d.run(old_permit, adapter)  # issued before the STOP epoch
        self.assertEqual(adapter.calls, 0)
        self.reserve()

    def test_unreadable_stop_state_means_stop(self):
        def broken():
            raise OSError("store unavailable")

        g = Guardrails(clock=self.clock, stop_reader=broken)
        g.set_provider("p1", "ENABLED")
        for scope in (("global",), ("tenant", "A"), ("provider", "A", "p1"), ("task", "A", "t1")):
            g.set_cap(scope, 100, "EUR")
        g.set_auto_threshold("A", 100)
        with self.assertRaises(Denied) as e:
            g.reserve("A", "p1", "t1", 10, "EUR", "k")
        self.assertEqual(e.exception.code, "stopped")


class ProviderStateTest(Base):
    def test_no_api_means_disabled_and_nothing_is_called(self):
        self.deny("provider_disabled", provider="chatgpt-subscription")  # never configured
        self.g.set_provider("p2", "DISABLED")
        self.deny("provider_disabled", provider="p2")
        self.g.set_provider("p1", "QUOTA_EXHAUSTED")
        self.deny("provider_quota_exhausted")
        _, permit = (self.g.set_provider("p1", "ENABLED"), self.reserve())[1]
        self.g.set_provider("p1", "DISABLED")  # disabled after the permit was issued
        adapter = Adapter()
        with self.assertRaises(Denied) as e:
            self.d.run(permit, adapter)
        self.assertEqual((e.exception.code, adapter.calls), ("provider_disabled", 0))


class DispatchTest(Base):
    def test_authorized_call_runs_exactly_once_and_permit_is_single_use(self):
        adapter = Adapter()
        r, permit = self.reserve()
        self.assertEqual(self.d.run(permit, adapter), "done")
        with self.assertRaises(Denied) as e:
            self.d.run(permit, adapter)
        self.assertEqual((e.exception.code, adapter.calls), ("permit_invalid", 1))
        self.g.settle("A", r.id, 80)
        self.assertEqual(self.g.available(("task", "A", "t1")), 300 - 80)  # actual replaces the estimate

    def test_forged_and_foreign_permits_are_rejected_without_a_call(self):
        adapter = Adapter()
        r, permit = self.reserve()
        forged = type(permit)(r.id, "A", secrets.token_urlsafe(16), permit.epoch)
        for bad in (forged, type(permit)(r.id, "B", permit.token, permit.epoch), type(permit)("res_nope", "A", "x", 0)):
            with self.assertRaises(Denied):
                self.d.run(bad, adapter)
        self.assertEqual(adapter.calls, 0)

    def test_overrun_is_recorded_and_pauses_the_provider(self):
        adapter = Adapter()
        r, permit = self.reserve(amount=100)
        self.d.run(permit, adapter)
        settled = self.g.settle("A", r.id, 150)
        self.assertTrue(settled.overrun)
        self.deny("stopped")  # integration paused until a human reviews and starts it
        self.g.start("integration", "p1", "human")
        self.reserve()

    def test_unknown_outcome_keeps_money_held_and_blocks_retry_until_reconciled(self):
        adapter = Adapter("timeout")
        r, permit = self.reserve(amount=100)
        with self.assertRaises(TimeoutAfterSend):
            self.d.run(permit, adapter)
        self.assertEqual(r.status, "UNKNOWN_OUTCOME")
        self.assertEqual(self.g.available(("tenant", "A")), 400)  # still reserved
        with self.assertRaises(Denied) as e:
            self.g.renew_permit("A", r.id)
        self.assertEqual(e.exception.code, "unknown_outcome_requires_reconciliation")
        with self.assertRaises(Denied):
            self.g.release("A", r.id)
        self.assertEqual(self.g.reconcile("A", r.id, None).status, "UNKNOWN_OUTCOME")  # no receipt yet
        self.g.reconcile("A", r.id, 60)
        self.assertEqual(self.g.available(("tenant", "A")), 440)
        self.assertEqual(adapter.calls, 1)  # never sent a second time

    def test_retries_are_bounded_and_each_needs_a_fresh_permit_and_stop_check(self):
        self.g.breaker_threshold = 99  # keep the breaker out of this test
        adapter = Adapter("error")
        r, permit = self.reserve()
        for attempt in range(3):  # 1 initial call + max_retries (2)
            with self.assertRaises(RuntimeError):
                self.d.run(permit, adapter)
            if attempt < 2:
                permit = self.g.renew_permit("A", r.id)
        with self.assertRaises(Denied) as e:
            self.g.renew_permit("A", r.id)
        self.assertEqual((e.exception.code, adapter.calls), ("max_retries", 3))
        self.g.release("A", r.id, confirmed_no_effect=True)  # operator confirms nothing was charged
        self.assertEqual(self.g.available(("tenant", "A")), 500)
        r2, p2 = self.reserve()
        self.g.stop("global")
        with self.assertRaises(Denied):
            self.d.run(p2, adapter)
        self.assertEqual(adapter.calls, 3)

    def test_circuit_breaker_opens_half_opens_and_closes(self):
        adapter = Adapter("error")
        for _ in range(3):
            _, permit = self.reserve(amount=10)
            with self.assertRaises(RuntimeError):
                self.d.run(permit, adapter)
        self.deny("circuit_open", amount=10)
        self.clock.now += 61
        _, probe = self.reserve(amount=10, key="probe")  # half-open: exactly one probe allowed
        self.deny("circuit_open", amount=10, key="second")
        with self.assertRaises(RuntimeError):
            self.d.run(probe, adapter)  # probe fails: breaker reopens
        self.deny("circuit_open", amount=10, key="third")
        self.clock.now += 61
        ok = Adapter("ok")
        _, probe2 = self.reserve(amount=10, key="probe2")
        self.d.run(probe2, ok)  # probe succeeds: breaker closes
        self.reserve(amount=10, key="after")
        self.assertEqual(ok.calls, 1)

    def test_release_is_refused_after_a_dispatch_without_confirmation(self):
        r, permit = self.reserve()
        with self.assertRaises(RuntimeError):
            self.d.run(permit, Adapter("error"))
        with self.assertRaises(Denied) as e:
            self.g.release("A", r.id)
        self.assertEqual(e.exception.code, "cannot_release")


class AuditTest(Base):
    def test_decisions_are_logged_with_reason_codes_and_no_secrets(self):
        self.deny("budget_exceeded", amount=999)
        self.deny("provider_disabled", provider="p9")
        _, permit = self.reserve()
        self.g.stop("global")
        with self.assertRaises(Denied):
            self.d.run(permit, Adapter())
        decisions = [(e["fields"]["action"], e["fields"]["decision"]) for e in self.obs.snapshot() if e["name"] == "budget.decision"]
        self.assertEqual(decisions, [("reserve", "budget_exceeded"), ("reserve", "provider_disabled"), ("reserve", "allow"),
                                     ("stop", "global:"), ("dispatch", "permit_invalid")])
        self.assertNotIn(permit.token, repr(self.obs.snapshot()))
        self.assertTrue(self.obs.verify_chain())


if __name__ == "__main__":
    unittest.main()
