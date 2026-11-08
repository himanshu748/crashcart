"""Account allowance at the actual provider boundary; no external requests."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request

from crashcart import model_allowance as allowance, model_transport as wire


class AllowanceTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "allowance.json"
        self.state = {"version": 1, "call_limit": 24, "ceiling_micro_usd": 1000000, "calls": []}
        self.save()
        self.env = {"CRASHCART_MODEL_ALLOWANCE_PATH": str(self.path), "CRASHCART_ALLOW_MODEL": "1",
            "CRASHCART_MODEL_PROVIDER": "modal", "MODAL_API_KEY": "synthetic-test-credential",
            "MODAL_MODEL": wire.MODAL_MODEL, "MODAL_BASE_URL": "https://tenant.us-east.modal.direct",
            "MODAL_ALLOWED_ORIGIN": "https://tenant.us-east.modal.direct"}
        self.request = Request(self.env["MODAL_BASE_URL"] + "/v1/chat/completions",
            data=json.dumps({"model": wire.MODAL_MODEL, "n": 1, "max_tokens": 1024,
                "stream": False, "reasoning_effort": "none",
                "messages": [{"role": "system", "content": "Test only."},
                             {"role": "user", "content": "Synthetic records only."}]}).encode(),
            headers={"Authorization": "Bearer " + self.env["MODAL_API_KEY"]}, method="POST")
        self.response = {"id": "response-test", "model": wire.MODAL_MODEL,
            "usage": {"prompt_tokens": 100, "completion_tokens": 10},
            "choices": [{"message": {"content": "This content must not enter the allowance ledger."}}]}

    def save(self):
        self.path.write_text(json.dumps(self.state))
        self.path.chmod(0o600)

    def test_success_reserves_before_dispatch_and_records_metadata_only(self):
        def dispatch(request, timeout):
            self.assertEqual(json.loads(self.path.read_text())["calls"][0]["state"], "RESERVED")
            self.assertIs(request, self.request)
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 5)
            return self.response
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire, "_bounded_http", side_effect=dispatch) as http:
            self.assertIs(wire.http(self.request, 5), self.response)
        self.assertEqual(http.call_count, 1)
        raw = self.path.read_text()
        entry = json.loads(raw)["calls"][0]
        self.assertEqual((entry["state"], entry["reserved_micro_usd"], entry["observed_rate_cost_micro_usd"]),
                         ("RESPONDED", 40000, 42))
        self.assertNotIn("choices", raw)
        self.assertNotIn(self.env["MODAL_API_KEY"], raw)

    def test_unknown_previous_dispatch_blocks_before_any_network(self):
        allowance.reserve(self.path, self.request, expected_origin=self.env["MODAL_BASE_URL"], expected_model=wire.MODAL_MODEL)
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire, "_bounded_http") as http:
            with self.assertRaisesRegex(wire.ModelTransportError, "MODEL_ALLOWANCE_UNRESOLVED"):
                wire.http(self.request, 5)
        http.assert_not_called()

    def test_missing_or_empty_ledger_fails_before_network(self):
        self.path.unlink()
        for value in (str(self.path), ""):
            with self.subTest(value=value), patch.dict(wire.os.environ, {**self.env, "CRASHCART_MODEL_ALLOWANCE_PATH": value}, clear=True), patch.object(wire, "_bounded_http") as http:
                with self.assertRaises(wire.ModelTransportError):
                    wire.http(self.request, 5)
                http.assert_not_called()

    def test_provider_error_consumes_one_reservation_and_does_not_retry(self):
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire, "_bounded_http", side_effect=wire.ModelTransportError("MODEL_HTTP_401")) as http:
            with self.assertRaisesRegex(wire.ModelTransportError, "MODEL_HTTP_401"):
                wire.http(self.request, 5)
        self.assertEqual(http.call_count, 1)
        entry = json.loads(self.path.read_text())["calls"][0]
        self.assertEqual((entry["state"], entry["error"], entry["reserved_micro_usd"]), ("ERROR", "MODEL_HTTP_401", 40000))

    def test_late_observed_response_keeps_usage_and_error(self):
        error = wire.ModelTransportError("MODEL_TIMEOUT", response=self.response)
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire, "_bounded_http", side_effect=error):
            with self.assertRaises(wire.ModelTransportError) as caught:
                wire.http(self.request, 5)
        self.assertIs(caught.exception.response, self.response)
        entry = json.loads(self.path.read_text())["calls"][0]
        self.assertEqual((entry["state"], entry["response_id"], entry["observed_rate_cost_micro_usd"]), ("ERROR", "response-test", 42))

    def test_reservation_time_is_deducted_and_prevents_expired_dispatch(self):
        original_reserve = allowance.reserve
        def delayed_reserve(*args, **kwargs):
            reservation = original_reserve(*args, **kwargs)
            clock[0] = 110
            return reservation
        clock = [100]
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire.time, "monotonic", side_effect=lambda: clock[0]), patch.object(allowance, "reserve", side_effect=delayed_reserve), patch.object(wire, "_bounded_http") as http:
            with self.assertRaisesRegex(wire.ModelTransportError, "MODEL_TIMEOUT"):
                wire.http(self.request, 5)
        http.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text())["calls"][0]["state"], "RESERVED")

    def test_response_after_deadline_keeps_usage_and_does_not_add_a_finish_lock_window(self):
        clock = [100]
        def dispatch(*args):
            clock[0] = 110
            return self.response
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire.time, "monotonic", side_effect=lambda: clock[0]), patch.object(wire, "_bounded_http", side_effect=dispatch), patch.object(allowance, "finish") as finish:
            with self.assertRaisesRegex(wire.ModelTransportError, "MODEL_TIMEOUT") as caught:
                wire.http(self.request, 5)
        self.assertIs(caught.exception.response, self.response)
        finish.assert_not_called()
        self.assertEqual(json.loads(self.path.read_text())["calls"][0]["state"], "RESERVED")

    def test_failed_finish_preserves_observed_response_and_blocks_next_dispatch(self):
        with patch.dict(wire.os.environ, self.env, clear=True), patch.object(wire, "_bounded_http", return_value=self.response) as http:
            with patch.object(allowance, "finish", side_effect=allowance.ModelAllowanceError("MODEL_ALLOWANCE_UNAVAILABLE")):
                with self.assertRaises(wire.ModelTransportError) as caught:
                    wire.http(self.request, 5)
            self.assertIs(caught.exception.response, self.response)
            with self.assertRaisesRegex(wire.ModelTransportError, "MODEL_ALLOWANCE_UNRESOLVED"):
                wire.http(self.request, 5)
        self.assertEqual(http.call_count, 1)

    def test_unset_account_ledger_preserves_existing_transport_contract(self):
        with patch.dict(wire.os.environ, {}, clear=True), patch.object(wire, "_bounded_http", return_value=self.response) as http:
            self.assertIs(wire.http(self.request, 5), self.response)
        http.assert_called_once_with(self.request, 5)
        self.assertEqual(json.loads(self.path.read_text())["calls"], [])

    def test_account_allowance_cannot_be_attached_to_another_provider(self):
        env = {**self.env, "CRASHCART_MODEL_PROVIDER": "openai", "OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}
        with patch.dict(wire.os.environ, env, clear=True), patch.object(wire, "_bounded_http") as http:
            with self.assertRaisesRegex(wire.ModelTransportError, "MODEL_ALLOWANCE_PROVIDER_UNSUPPORTED"):
                wire.http(self.request, 5)
        http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
