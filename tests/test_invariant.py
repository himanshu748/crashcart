"""LOCAL_TEST deterministic observations; no sandbox claims."""

from copy import deepcopy
import unittest

from crashcart.invariant import DEFAULT_INVARIANT, evaluate


class InvariantTests(unittest.TestCase):
    def setUp(self):
        self.provider = {"confirmed": True, "status": "COMPLETED", "amount": 2900, "currency": "USD",
            "run_id": "local-run", "purchase_id": "local-purchase", "order_id": "local-order", "capture_id": "local-capture",
            "capture_completed_at": "2026-10-22T10:00:00Z", "observed_at": "2026-10-22T10:00:05Z"}
        self.merchant = {"known": True, "run_id": "local-run", "purchase_id": "local-purchase", "order_id": "local-order",
            "observed_at": "2026-10-22T10:01:01Z", "ticket_count": 0, "tickets": []}
        self.now = "2026-10-22T10:01:02Z"

    def evaluate(self, **kwargs):
        return evaluate(kwargs.get("provider", self.provider), kwargs.get("merchant", self.merchant), kwargs.get("now", self.now))

    def ticket(self, created_at="2026-10-22T10:00:45Z"):
        self.merchant.update(ticket_count=1, tickets=[{"id": "local-ticket", "purchase_id": "local-purchase", "created_at": created_at}])

    def test_missing_delivery_beyond_deadline_fails_stably_with_source_ids(self):
        verdict = self.evaluate()
        self.assertEqual(verdict["verdict"], "FAIL")
        self.assertEqual(verdict["signature"], "paid_without_ticket")
        self.assertEqual(verdict["deadline"], "2026-10-22T10:01:00Z")
        self.assertEqual(verdict["source_ids"]["capture_id"], "local-capture")
        self.assertEqual(verdict["invariant_version"], "ticket-v1")
        self.assertEqual(self.evaluate(now="2026-10-22T11:00:00Z")["signature"], verdict["signature"])

    def test_healthy_delayed_delivery_passes_without_changing_invariant(self):
        self.merchant["observed_at"] = "2026-10-22T10:00:30Z"
        waiting = self.evaluate(now="2026-10-22T10:00:30Z")
        self.assertEqual(waiting["verdict"], "INCONCLUSIVE")
        self.assertEqual(waiting["signature"], "within_recovery_window")
        self.merchant["observed_at"] = "2026-10-22T10:01:01Z"
        self.ticket()
        delivered = self.evaluate()
        self.assertEqual(delivered["verdict"], "PASS")
        self.assertEqual(delivered["deadline"], waiting["deadline"])

    def test_ticket_at_deadline_passes_but_late_ticket_fails(self):
        self.ticket("2026-10-22T10:01:00Z")
        self.assertEqual(self.evaluate()["verdict"], "PASS")
        self.ticket("2026-10-22T10:01:01Z")
        self.assertEqual(self.evaluate()["signature"], "ticket_delivered_late")

    def test_stale_zero_ticket_observation_does_not_prove_deadline_failure(self):
        self.merchant["observed_at"] = "2026-10-22T10:00:30Z"
        self.assertEqual(self.evaluate()["signature"], "stale_merchant_observation")

    def test_missing_payment_or_merchant_is_inconclusive(self):
        for kwargs in [{"provider": None}, {"merchant": None}, {"merchant": {"known": False}}]:
            with self.subTest(kwargs=kwargs):
                self.assertEqual(self.evaluate(**kwargs)["verdict"], "INCONCLUSIVE")

    def test_bad_amount_currency_fail_only_for_confirmed_correlated_payment(self):
        for changes, signature in [({"amount": 1}, "payment_amount_mismatch"), ({"currency": "EUR"}, "payment_currency_mismatch")]:
            provider = {**self.provider, **changes}
            self.assertEqual(self.evaluate(provider=provider)["signature"], signature)
            self.assertEqual(self.evaluate(provider={**provider, "order_id": "different-order"})["verdict"], "INCONCLUSIVE")
            self.assertEqual(self.evaluate(provider={**provider, "confirmed": False})["verdict"], "INCONCLUSIVE")

    def test_noninteger_payment_or_count_is_inconclusive(self):
        for value in [2900.0, "2900", True, None]:
            self.assertEqual(self.evaluate(provider={**self.provider, "amount": value})["verdict"], "INCONCLUSIVE")
        for value in [0.0, "0", False, -1]:
            self.assertEqual(self.evaluate(merchant={**self.merchant, "ticket_count": value})["verdict"], "INCONCLUSIVE")

    def test_missing_or_mismatched_identities_are_inconclusive(self):
        for field in ["run_id", "purchase_id", "order_id"]:
            for value in [None, "", "wrong-value"]:
                self.assertEqual(self.evaluate(provider={**self.provider, field: value})["verdict"], "INCONCLUSIVE")
        self.assertEqual(self.evaluate(provider={**self.provider, "capture_id": None})["verdict"], "INCONCLUSIVE")

    def test_unknown_future_and_reordered_times_do_not_create_false_failure(self):
        for value in [None, "invalid", "2026-10-22T10:00:00", "2026-10-22T11:00:00Z"]:
            for field in ["capture_completed_at", "observed_at"]:
                with self.subTest(field=field, value=value):
                    self.assertEqual(self.evaluate(provider={**self.provider, field: value})["verdict"], "INCONCLUSIVE")
            self.assertEqual(self.evaluate(merchant={**self.merchant, "observed_at": value})["verdict"], "INCONCLUSIVE")
        self.assertEqual(self.evaluate(provider={**self.provider, "observed_at": "2026-10-22T09:59:59Z"})["signature"], "observation_precedes_payment")
        self.assertEqual(self.evaluate(now="2026-10-22T10:00:00")["signature"], "invalid_evaluation_time")

    def test_duplicate_records_are_distinct_from_duplicate_entitlements(self):
        self.ticket()
        self.merchant["ticket_count"] = 2
        self.merchant["tickets"].append(deepcopy(self.merchant["tickets"][0]))
        self.assertEqual(self.evaluate()["verdict"], "INCONCLUSIVE")
        self.merchant["tickets"][1]["id"] = "second-ticket"
        self.assertEqual(self.evaluate()["signature"], "duplicate_tickets")

    def test_malformed_or_uncorrelated_ticket_evidence_stays_inconclusive(self):
        self.ticket()
        for changes in [{"purchase_id": "different"}, {"id": None}, {"created_at": None},
                        {"created_at": "2026-10-22T09:00:00Z"}, {"created_at": "2026-10-22T11:00:00Z"}]:
            merchant = deepcopy(self.merchant)
            merchant["tickets"][0].update(changes)
            self.assertEqual(self.evaluate(merchant=merchant)["verdict"], "INCONCLUSIVE")

    def test_timeout_and_noncompleted_status_are_never_success(self):
        self.ticket()
        for status in ["PENDING", "FAILED", "UNRESOLVED", None, "HTTP_200"]:
            self.assertEqual(self.evaluate(provider={**self.provider, "status": status})["verdict"], "INCONCLUSIVE")

    def test_contract_cannot_be_mutated_or_relaxed_after_observation(self):
        with self.assertRaises(TypeError):
            DEFAULT_INVARIANT["recovery_seconds"] = 600
        for change in [{"recovery_seconds": 600}, {"amount": 2900.0}, {"version": "changed"}]:
            with self.assertRaises(ValueError):
                evaluate(self.provider, self.merchant, self.now, {**DEFAULT_INVARIANT, **change})
        original = deepcopy(self.provider), deepcopy(self.merchant)
        self.evaluate()
        self.assertEqual((self.provider, self.merchant), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
