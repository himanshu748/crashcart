"""Synthetic transport tests. These never establish actual sandbox execution."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import json
import tempfile
import unittest
from unittest.mock import patch

from crashcart.store import Store
from crashcart.service import MerchantService
from crashcart.paypal import PayPalError


class FakePayPal:
    def __init__(self):
        self.order = None
        self.calls = []
        self.webhook_inputs = []

    def create_order(self, body, request_id):
        self.calls.append(("create", request_id, deepcopy(body)))
        self.order = {"id": "ORDER_TEST", "intent": "CAPTURE", "status": "CREATED", "purchase_units": deepcopy(body["purchase_units"]), "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER_TEST"}]}
        return deepcopy(self.order)

    def get_order(self, order_id):
        self.calls.append(("get", order_id))
        return deepcopy(self.order)

    def capture_order(self, order_id, body, request_id):
        self.calls.append(("capture", request_id, deepcopy(body)))
        now = datetime.now(timezone.utc).isoformat()
        self.order["status"] = "COMPLETED"
        self.order["purchase_units"][0]["payments"] = {"captures": [{"id": "CAPTURE_TEST", "status": "COMPLETED", "amount": {"value": "29.00", "currency_code": "USD"}, "update_time": now}]}
        return deepcopy(self.order)

    def verify_webhook(self, headers, event, *, raw_body=None):
        self.webhook_inputs.append((deepcopy(headers), deepcopy(event), raw_body))
        return headers.get("test") == "verified"


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name + "/db.sqlite3")
        self.provider = FakePayPal()
        self.service = MerchantService(self.store, lambda: self.provider)

    def start(self, fault=None):
        run = self.store.create_run("synthetic local transport acceptance test", fault=fault or {"kind": "none", "merchant": "healthy"})
        order = self.service.create_order(run["id"])
        return run, order

    def test_price_identity_approval_and_healthy_ticket(self):
        run, order = self.start()
        purchase = self.store.purchase_for_run(run["id"])
        self.assertEqual(self.provider.calls[0][2]["purchase_units"][0]["amount"], {"value": "29.00", "currency_code": "USD"})
        self.assertEqual(self.store.merchant_state(purchase["id"])["ticket_count"], 0)
        with self.assertRaisesRegex(ValueError, "buyer approval"):
            self.service.capture(run["id"], order["order_id"])
        self.assertFalse(any(c[0] == "capture" for c in self.provider.calls))
        self.provider.order["status"] = "APPROVED"
        result = self.service.capture(run["id"], order["order_id"])
        self.assertEqual(result["verdict"], "PASS")
        again = self.service.capture(run["id"], order["order_id"])
        self.assertEqual(again["merchant"]["ticket_count"], 1)
        self.assertEqual(sum(c[0] == "capture" for c in self.provider.calls), 1)
        self.assertEqual(self.service.create_order(run["id"])["reconciliation"]["verdict"], "PASS")

    def test_lost_response_remains_unknown_until_independent_read(self):
        run, order = self.start({"kind": "response_loss", "merchant": "defective"})
        self.provider.order["status"] = "APPROVED"
        result = self.service.capture(run["id"], order["order_id"])
        self.assertEqual(result["state"], "unresolved")
        purchase = self.store.purchase_for_run(run["id"])
        self.assertIsNone(purchase["capture_id"])
        self.assertEqual(purchase["payment_confirmed"], 0)
        self.assertEqual(self.store.merchant_state(purchase["id"])["ticket_count"], 0)
        capture = self.provider.order["purchase_units"][0]["payments"]["captures"][0]
        capture["update_time"] = (datetime.now(timezone.utc)-timedelta(seconds=61)).isoformat()
        result = self.service.reconcile(run["id"])
        self.assertEqual(result["signature"], "paid_without_ticket")
        self.assertEqual(result["verdict"], "FAIL")
        ops = self.store.get_operations(purchase["id"])
        self.assertEqual([o for o in ops if o["semantic_key"] == "order.capture"][0]["state"], "UNRESOLVED")

    def test_healthy_response_loss_recovers_once_by_saved_order(self):
        run, order = self.start({"kind": "response_loss", "merchant": "healthy"})
        self.provider.order["status"] = "APPROVED"
        self.service.capture(run["id"], order["order_id"])
        restarted = MerchantService(Store(self.tmp.name+"/db.sqlite3"), lambda: self.provider)
        self.assertEqual(restarted.reconcile(run["id"])["verdict"], "PASS")
        self.assertEqual(restarted.reconcile(run["id"])["merchant"]["ticket_count"], 1)

    def test_timeout_never_means_payment_completed(self):
        run, order = self.start()
        self.provider.order["status"] = "APPROVED"
        with patch.object(self.provider, "capture_order", side_effect=PayPalError("TIMEOUT", "timed out", ambiguous=True)):
            with self.assertRaises(PayPalError):
                self.service.capture(run["id"], order["order_id"])
        purchase = self.store.purchase_for_run(run["id"])
        self.assertFalse(purchase["payment_confirmed"])
        self.assertEqual(self.service.reconcile(run["id"])["verdict"], "INCONCLUSIVE")
        self.assertEqual(self.store.merchant_state(purchase["id"])["ticket_count"], 0)

    def test_correlated_wrong_charge_fails_without_confirming_or_fulfilling(self):
        for amount, currency, minor, signature in [("28.00", "USD", 2800, "payment_amount_mismatch"), ("29.00", "EUR", 2900, "payment_currency_mismatch")]:
            with self.subTest(amount=amount, currency=currency):
                # Use separate database identities, as each case is a distinct
                # synthetic experiment; none is a real sandbox transaction.
                with tempfile.TemporaryDirectory() as path:
                    store = Store(path + "/wrong-charge.sqlite3")
                    provider = FakePayPal()
                    service = MerchantService(store, lambda: provider)
                    run = store.create_run("synthetic wrong-charge verification")
                    order = service.create_order(run["id"])
                    provider.order["status"] = "APPROVED"
                    provider.capture_order(order["order_id"], {}, "local-capture-request")
                    unit = provider.order["purchase_units"][0]
                    unit["amount"] = {"value": amount, "currency_code": currency}
                    unit["payments"]["captures"][0]["amount"] = deepcopy(unit["amount"])
                    with patch.object(store, "confirm_payment", wraps=store.confirm_payment) as confirm, patch.object(store, "fulfill", wraps=store.fulfill) as fulfill:
                        result = service.reconcile(run["id"])
                    self.assertEqual(result["verdict"], "FAIL")
                    self.assertEqual(result["signature"], signature)
                    self.assertEqual(result["payment"]["currency"], currency)
                    self.assertEqual(result["payment"]["amount"], minor)
                    self.assertEqual(result["merchant"]["ticket_count"], 0)
                    self.assertEqual(store.get_purchase(run["purchase_id"])["payment_confirmed"], 0)
                    confirm.assert_not_called()
                    fulfill.assert_not_called()
                    events = {event["id"]: event for event in store.get_events(run["id"])}
                    self.assertEqual(events[result["source_ids"]["provider_observation_id"]]["event_type"], "independent_order_read")
                    self.assertEqual(events[result["source_ids"]["merchant_observation_id"]]["event_type"], "entitlement_read")

    def test_registered_target_and_replay_boundaries_before_network(self):
        run = self.store.create_run("replay", mode="RECORDED_REPLAY")
        with self.assertRaisesRegex(ValueError, "cannot contact PayPal"):
            self.service.create_order(run["id"])
        self.assertEqual(self.provider.calls, [])
        with self.assertRaises(ValueError):
            self.store.create_run("arbitrary", fixture_id="https://not-owned.example")

    def test_wrong_capture_is_failed_but_foreign_purchase_evidence_is_inconclusive(self):
        run, order = self.start()
        self.provider.order["status"] = "APPROVED"
        self.provider.capture_order(order["order_id"], {}, "local-request")
        unit = self.provider.order["purchase_units"][0]
        # The order still requests USD29; the actual completed capture is USD28.
        unit["payments"]["captures"][0]["amount"]["value"] = "28.00"
        self.assertEqual(self.service.reconcile(run["id"])["signature"], "payment_amount_mismatch")
        unit["custom_id"] = "FOREIGN_PURCHASE"
        self.assertEqual(self.service.reconcile(run["id"])["verdict"], "INCONCLUSIVE")
        self.assertEqual(self.store.get_purchase(run["purchase_id"])["payment_confirmed"], 0)
        self.assertEqual(self.store.merchant_state(run["purchase_id"])["ticket_count"], 0)

    def test_callback_mismatch_and_cancellation_do_not_capture(self):
        run, order = self.start()
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.service.capture(run["id"], "OTHER")
        self.store.update_run(run["id"], cancel_requested=1, state="cancelled")
        with self.assertRaisesRegex(ValueError, "cancelled"):
            self.service.reconcile(run["id"])
        self.assertFalse(any(c[0] == "capture" for c in self.provider.calls))

    def test_duplicate_fulfillment_has_one_ticket_and_trace(self):
        run, order = self.start({"kind": "event_duplicate", "merchant": "healthy"})
        self.provider.order["status"] = "APPROVED"
        result = self.service.capture(run["id"], order["order_id"])
        self.assertEqual(result["merchant"]["ticket_count"], 1)
        types = [e["event_type"] for e in self.store.get_events(run["id"])]
        self.assertIn("duplicate_processing", types)
        self.assertIn("fault_deactivated", types)

    def test_webhook_invalid_rejected_and_duplicate_deduped(self):
        run, order = self.start()
        event = {"id": "WH_TEST", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"id": "CAPTURE_TEST", "supplementary_data": {"related_ids": {"order_id": order["order_id"]}}}}
        raw = (json.dumps(event, indent=2) + "\n").encode()
        with self.assertRaisesRegex(ValueError, "signature rejected"):
            self.service.webhook({}, event, raw_body=raw)
        self.assertFalse(self.service.webhook({"test": "verified"}, event, raw_body=raw)["stored"]["duplicate"])
        self.assertTrue(self.service.webhook({"test": "verified"}, event, raw_body=raw)["stored"]["duplicate"])
        self.assertEqual(len(self.provider.webhook_inputs), 3)
        self.assertTrue(all(item[1] == event and item[2] is raw for item in self.provider.webhook_inputs))
        self.assertEqual(self.store.merchant_state(run["purchase_id"])["ticket_count"], 0)


if __name__ == "__main__":
    unittest.main()
