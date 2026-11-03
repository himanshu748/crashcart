"""LOCAL_TEST grammar checks. Schedules are plans, not execution evidence."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from crashcart.faults import MAX_DELAY_SECONDS, fault_schedule, validate_fault


class FaultTests(unittest.TestCase):
    def test_default_is_healthy_without_fault(self):
        self.assertEqual(validate_fault(), {"kind": "none", "merchant": "healthy"})
        self.assertEqual(fault_schedule(), [])

    def test_each_typed_fault_has_an_owned_merchant_boundary(self):
        for kind in ["response_loss", "event_delay", "event_duplicate", "process_interrupt"]:
            config = {"kind": kind, "merchant": "defective"}
            if kind == "event_delay":
                config["delay_seconds"] = 61
            step = fault_schedule(config)[0]
            self.assertEqual(step["kind"], kind)
            self.assertEqual(step["fixture_id"], "workshop-v1")
            self.assertTrue(step["boundary"])
            self.assertTrue(step["action"])
        self.assertEqual(fault_schedule({"kind": "event_duplicate"})[0]["boundary"], "verified_fixture_event")

    def test_unregistered_targets_rejected_before_network(self):
        with patch("socket.create_connection", side_effect=AssertionError("network action forbidden")) as network:
            for target in ["unknown-fixture", "https://api-m.paypal.com", "https://arbitrary.example", None, "workshop-v2"]:
                with self.subTest(target=target), self.assertRaises(ValueError):
                    fault_schedule({"kind": "response_loss"}, target)
            network.assert_not_called()

    def test_unsupported_faults_and_fields_rejected(self):
        for config in [{"kind": "provider_mutation"}, {"kind": None}, {"kind": []}, {"merchant": "external"},
                       {"merchant": []}, {"url": "https://arbitrary.example"}, {"kind": "none", "delay_seconds": 1},
                       {"kind": "response_loss", "disable_signature_verification": True}, [], "response_loss"]:
            with self.subTest(config=config), self.assertRaises(ValueError):
                validate_fault(config)

    def test_event_delay_has_strict_integer_bounds(self):
        for seconds in [1, MAX_DELAY_SECONDS]:
            self.assertEqual(validate_fault({"kind": "event_delay", "delay_seconds": seconds})["delay_seconds"], seconds)
        for seconds in [0, -1, MAX_DELAY_SECONDS + 1, True, 1.0, "1", None]:
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                validate_fault({"kind": "event_delay", "delay_seconds": seconds})

    def test_validation_does_not_mutate_input_or_share_configuration(self):
        original = {"kind": "event_delay", "delay_seconds": 61, "merchant": "defective"}
        before = deepcopy(original)
        normalized = validate_fault(original)
        normalized["delay_seconds"] = 1
        self.assertEqual(original, before)
        self.assertEqual(validate_fault()["merchant"], "healthy")


if __name__ == "__main__":
    unittest.main(verbosity=2)
