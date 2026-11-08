"""LOCAL_TEST: actual adapter wiring with injected cloud replies; no provider execution."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from crashcart.kernel_browser import KernelBrowser, KernelError
from crashcart.store import Store
from tests.test_kernel_browser import ORIGIN, Transport, observation, public_dns

spec = importlib.util.spec_from_file_location("kernel_entrypoint", Path(__file__).parents[1] / "scripts/run_kernel_checkout.py")
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class KernelEntrypointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / "state.sqlite3"
        self.store = Store(self.db)
        self.run = self.store.create_run("Synthetic owned workshop observation", mode="LIVE_SANDBOX")
        self.allowance = self.root / "grant.json"
        self.grant = {"approval_id": "local-test-only-grant", "owned_origin": ORIGIN,
                      "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                      "max_session_seconds": 60, "scenarios": ["observe"]}
        self.allowance.write_text(json.dumps(self.grant))
        self.state = self.root / "private"
        self.env = {"KERNEL_API_KEY": "test-only-provider-key", "CRASHCART_OPERATOR_TOKEN": "test-only-operator-key",
                    "CRASHCART_ALLOW_KERNEL": "1", "CRASHCART_PUBLIC_URL": ORIGIN}
        self.actions = observation(run_id=self.run["id"], purchase_id=self.run["purchase_id"], order_id=None)
        blocker = patch.object(socket.socket, "connect", side_effect=AssertionError("External network forbidden"))
        blocker.start(); self.addCleanup(blocker.stop)

    def execute(self, transport, **changes):
        def factory(**kwargs):
            kwargs["environ"] = self.env
            return KernelBrowser(**kwargs, transport=transport, resolver=public_dns)
        args = dict(db_path=self.db, run_id=self.run["id"], allowance_path=self.allowance, state_dir=self.state,
                    adapter_factory=factory)
        args.update(changes)
        return entry.observe_checkout(**args)

    def test_observe_uses_existing_identity_retains_private_recording_and_closes(self):
        transport = Transport(self.actions)
        before = self.store.purchase_for_run(self.run["id"])
        result = self.execute(transport)
        self.assertEqual(result["status"], "OBSERVED_UNREVIEWED")
        self.assertEqual(result["mode"], "LOCAL_TEST")
        self.assertEqual(result["payment_verdict"], "NOT_EVALUATED")
        self.assertFalse(result["imported"])
        receipt_path = Path(result["receipt_path"])
        self.assertEqual(receipt_path.stat().st_mode & 0o777, 0o600)
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["observations"][0]["scenario"], "observe")
        self.assertEqual(receipt["identity"]["run_id"], self.run["id"])
        self.assertEqual(receipt["cleanup"]["session_delete"], "SUCCEEDED")
        self.assertTrue(Path(receipt["recording"]["private_path"]).is_file())
        self.assertEqual(before, self.store.purchase_for_run(self.run["id"]))
        code = [json.loads(request.data)["code"] for request, _, _ in transport.calls if request.full_url.endswith("/playwright/execute")][-1]
        self.assertIn('"scenario": "observe"', code)
        self.assertNotIn("private-view-token", json.dumps(result))
        self.assertNotIn(self.env["KERNEL_API_KEY"], json.dumps(result))

    def test_missing_database_and_unknown_run_never_construct_adapter(self):
        for changes in ({"db_path": self.root / "absent.db"}, {"run_id": "run_" + "0" * 32}):
            with self.subTest(changes=changes):
                factory = unittest.mock.Mock(side_effect=AssertionError("must not construct"))
                with self.assertRaises(KernelError):
                    entry.observe_checkout(changes.get("db_path", self.db), changes.get("run_id", self.run["id"]), self.allowance, self.state, adapter_factory=factory)
                factory.assert_not_called()
        self.assertFalse((self.root / "absent.db").exists())

    def test_local_replay_and_cancelled_runs_never_dispatch(self):
        for mode in ("LOCAL_TEST", "RECORDED_REPLAY"):
            run = self.store.create_run("Synthetic invalid mode", mode=mode)
            transport = Transport()
            with self.assertRaisesRegex(KernelError, "ACTUAL_SANDBOX_RUN_REQUIRED"):
                self.execute(transport, run_id=run["id"])
            self.assertEqual(transport.calls, [])
        self.store.update_run(self.run["id"], cancel_requested=1)
        transport = Transport()
        with self.assertRaisesRegex(KernelError, "RUN_CANCELLED"):
            self.execute(transport)
        self.assertEqual(transport.calls, [])

    def test_missing_expired_wrong_scenario_or_disabled_grant_never_contacts_provider(self):
        for changes in ({"expires_at": "2000-01-01T00:00:00Z"}, {"scenarios": ["checkout"]}):
            self.allowance.write_text(json.dumps({**self.grant, **changes}))
            transport = Transport()
            with self.assertRaises(KernelError): self.execute(transport)
            self.assertEqual(transport.calls, [])
        self.allowance.write_text(json.dumps(self.grant))
        self.env["CRASHCART_ALLOW_KERNEL"] = "0"
        transport = Transport()
        with self.assertRaisesRegex(KernelError, "KERNEL_DISABLED"): self.execute(transport)
        self.assertEqual(transport.calls, [])
        self.allowance.unlink()
        with self.assertRaisesRegex(KernelError, "EXPLICIT_ALLOWANCE_REQUIRED"): self.execute(transport)
        self.assertEqual(transport.calls, [])

    def test_remote_identity_mismatch_closes_and_retains_failed_receipt(self):
        transport = Transport(observation(run_id="run_" + "0" * 32, purchase_id=self.run["purchase_id"], order_id=None))
        with self.assertRaisesRegex(KernelError, "CORRELATION_FAILED"): self.execute(transport)
        receipts = list(self.state.glob("*.receipt.json"))
        self.assertEqual(len(receipts), 1)
        receipt = json.loads(receipts[0].read_text())
        self.assertEqual(receipt["status"], "FAILED")
        self.assertEqual(receipt["cleanup"]["session_delete"], "SUCCEEDED")
        self.assertEqual(self.store.get_events(self.run["id"]), [])

    def test_interrupt_closes_without_creating_payment_or_importing(self):
        transport = Transport(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt): self.execute(transport)
        receipt = json.loads(next(self.state.glob("*.receipt.json")).read_text())
        self.assertEqual(receipt["cleanup"]["session_delete"], "SUCCEEDED")
        self.assertEqual(self.store.get_events(self.run["id"]), [])
        self.assertIsNone(self.store.purchase_for_run(self.run["id"])["order_id"])

    def test_cleanup_failure_is_incomplete_not_observed_success(self):
        transport = Transport(self.actions, failures={("DELETE", "/browsers/kernel-session-1"): (500, b"private upstream message", {})})
        result = self.execute(transport)
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertNotIn("private upstream", json.dumps(result))

    def test_registered_nonworkshop_fixture_is_rejected_before_adapter(self):
        with self.store.connect(write=True) as db:
            db.execute("INSERT INTO fixtures VALUES ('another-store','Synthetic other store',1,'sandbox',2900,'USD')")
        other = self.store.create_run("Synthetic registered nonworkshop", mode="LIVE_SANDBOX", fixture_id="another-store")
        transport = Transport()
        with self.assertRaisesRegex(KernelError, "OWNED_WORKSHOP_REQUIRED"): self.execute(transport, run_id=other["id"])
        self.assertEqual(transport.calls, [])

    def test_cancellation_during_observation_closes_and_never_returns_success(self):
        transport = Transport(self.actions)
        def cancel_after_observation(request, timeout, limit):
            result = transport(request, timeout, limit)
            if request.full_url.endswith("/playwright/execute") and "authenticated: true" not in json.loads(request.data)["code"]:
                self.store.update_run(self.run["id"], cancel_requested=1)
            return result
        with self.assertRaisesRegex(KernelError, "RUN_CANCELLED"): self.execute(cancel_after_observation)
        receipt = json.loads(next(self.state.glob("*.receipt.json")).read_text())
        self.assertEqual(receipt["status"], "FAILED")
        self.assertEqual(receipt["cleanup"]["session_delete"], "SUCCEEDED")
        self.assertEqual(self.store.get_events(self.run["id"]), [])

    def test_main_outputs_only_fixed_error_on_unexpected_exception(self):
        out = io.StringIO()
        with patch.object(entry, "observe_checkout", side_effect=RuntimeError("secret https://view.example/?jwt=private")), redirect_stdout(out):
            result = entry.main(["--db", str(self.db), "--run-id", self.run["id"], "--allowance", str(self.allowance), "--state-dir", str(self.state)])
        self.assertEqual(result, 1)
        self.assertEqual(json.loads(out.getvalue()), {"status": "REJECTED", "error": "OBSERVATION_FAILED"})

    def test_cli_rejects_unsupported_checkout_action_before_adapter(self):
        with patch.object(entry, "observe_checkout") as observe, redirect_stdout(io.StringIO()), patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as failure:
                entry.main(["--db", str(self.db), "--run-id", self.run["id"], "--allowance", str(self.allowance), "--state-dir", str(self.state), "--scenario", "checkout"])
        self.assertEqual(failure.exception.code, 2)
        observe.assert_not_called()
