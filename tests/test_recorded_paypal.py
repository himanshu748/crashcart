"""Saved capture evidence is a bounded public projection, never a provider call."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crashcart import recorded_paypal
from crashcart.replay import ReplayError


class RecordedPayPalTests(unittest.TestCase):
    def test_saved_capture_matches_independent_order_lookup(self):
        result = recorded_paypal.saved_capture()
        self.assertEqual(("29.00", "USD", "COMPLETED"),
                         (result["amount"]["value"], result["amount"]["currency_code"], result["capture_status"]))
        self.assertEqual("POST", result["capture_route"]["method"])
        self.assertEqual("GET", result["confirmation"]["method"])
        self.assertEqual(result["capture_route"]["path"].removesuffix("/capture"), result["confirmation"]["path"])
        self.assertIn(result["order_id"], result["capture_route"]["path"])
        self.assertEqual(result["capture_id"], result["response_fields"]["capture"]["id"])
        self.assertFalse(result["fresh_execution"])
        self.assertEqual("independent_order_lookup", result["confirmation"]["source"])

    def test_changed_proof_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "proof.json"
            target.write_bytes(recorded_paypal.PROOF.read_bytes() + b" ")
            with self.assertRaisesRegex(ReplayError, "saved PayPal proof changed"):
                recorded_paypal.saved_capture(target)

    def _project_modified(self, value):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "proof.json"
            target.write_text(json.dumps(value))
            with patch.object(recorded_paypal, "PROOF_SHA256", hashlib.sha256(target.read_bytes()).hexdigest()):
                return recorded_paypal.saved_capture(target)

    def test_only_selected_public_fields_leave_the_boundary(self):
        value = json.loads(recorded_paypal.PROOF.read_text())
        value["payment"]["payment"]["provider_response"]["payer"] = {"email_address": "PRIVATE_BUYER"}
        value["payment"]["payment"]["authorization"] = "PRIVATE_TOKEN"
        value["private_path"] = "/private/PRIVATE_FILE"
        result = self._project_modified(value)
        self.assertNotIn("PRIVATE_", json.dumps(result))
        self.assertEqual({"id", "status", "amount", "capture"}, set(result["response_fields"]))

    def test_contradictory_response_is_rejected_even_with_a_matching_hash(self):
        original = json.loads(recorded_paypal.PROOF.read_text())
        for change in ("status", "amount", "capture_id", "currency", "confirmed"):
            value = copy.deepcopy(original)
            payment = value["payment"]["payment"]
            capture = payment["provider_response"]["purchase_units"][0]["payments"]["captures"][0]
            if change == "status":
                capture["status"] = "PENDING"
            elif change == "amount":
                capture["amount"]["value"] = "2900.00"
            elif change == "capture_id":
                capture["id"] = "FOREIGN_CAPTURE"
            elif change == "currency":
                capture["amount"]["currency_code"] = "EUR"
            else:
                payment["confirmed"] = False
            with self.subTest(change=change), self.assertRaises(ReplayError):
                self._project_modified(value)


if __name__ == "__main__":
    unittest.main()
