"""Persisted LOCAL_TEST execution ownership; injected models and loopback HTTP only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import http.client
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from crashcart.investigator import Investigation, InvestigationError
from crashcart.server import Handler, ThreadingHTTPServer
from crashcart.store import Store
from tests.test_investigator import LocalModel, LocalProvider, LocalService, plan


class RunStateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "state.sqlite3"
        self.store = Store(self.path)
        self.run = self.store.create_run("USD 29 buys one ticket within 60 seconds", mode="LOCAL_TEST")
        self.other = self.store.create_run("Independent approval wait", mode="LOCAL_TEST")
        self.store.update_run(self.other["id"], state="awaiting_approval")
        self.provider = LocalProvider(self.run["purchase_id"])
        self.service = LocalService(self.provider)
        self.env = patch.dict(os.environ, {"CRASHCART_EVALUATION_MODE": "ordinary", "CRASHCART_ALLOW_MODEL": "0", "CRASHCART_ALLOW_SANDBOX": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)
        original = socket.socket.connect
        def loopback(sock, address):
            if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise AssertionError("LOCAL_TEST external network forbidden")
            return original(sock, address)
        self.network = patch.object(socket.socket, "connect", loopback)
        self.network.start()
        self.addCleanup(self.network.stop)

    def execute(self, model):
        return Investigation(self.store, self.service, model_factory=lambda: model).run(self.run["id"])

    def models(self):
        return [a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"]

    def endings(self):
        return [e for e in self.store.get_events(self.run["id"]) if e["event_type"] == "investigation_ended"]

    def test_atomic_reservation_has_one_owner_and_is_durable(self):
        barrier = threading.Barrier(6)
        def reserve(_):
            store = Store(self.path)
            barrier.wait(timeout=3)
            return store.begin_investigation(self.run["id"], 30)
        with ThreadPoolExecutor(max_workers=6) as workers:
            claims = list(workers.map(reserve, range(6)))
        self.assertEqual(sum(c is not None for c in claims), 1)
        restored = Store(self.path).get_run(self.run["id"])
        self.assertEqual(restored["state"], "running")
        self.assertTrue(restored["execution"]["active"])
        self.assertIn(restored["execution"]["attempt_id"], claims)
        self.assertEqual(self.models(), [])
        self.assertEqual(self.store.get_run(self.other["id"])["state"], "awaiting_approval")

    def test_duplicate_between_model_calls_does_not_finalize_owner(self):
        duplicate = LocalModel(lambda context: plan(context))
        observed = []
        original = self.store.finish_attempt
        def finish(*args, **kwargs):
            original(*args, **kwargs)
            if not observed:
                observed.append(self.execute(duplicate))
                self.assertEqual(self.store.get_run(self.run["id"])["state"], "running")
                self.assertEqual(self.endings(), [])
        model = LocalModel(lambda context: plan(context, "finish" if context["untrusted_observations"] else "read_merchant"))
        with patch.object(self.store, "finish_attempt", side_effect=finish):
            result = self.execute(model)
        self.assertEqual(observed[0]["status"], "RUNNING")
        self.assertEqual(duplicate.calls, 0)
        self.assertEqual(model.calls, 2)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(len(self.endings()), 1)
        self.assertFalse(self.store.get_run(self.run["id"])["execution"]["active"])

    def test_cancel_immediately_before_terminal_commit_wins(self):
        original = self.store.finish_investigation
        def cancel_then_finish(*args, **kwargs):
            self.store.update_run(self.run["id"], cancel_requested=1, state="cancelled")
            return original(*args, **kwargs)
        with patch.object(self.store, "finish_investigation", side_effect=cancel_then_finish):
            result = self.execute(LocalModel(lambda context: plan(context)))
        self.assertEqual(result["status"], "CANCELLED")
        self.assertEqual(result["final_verdict"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(self.endings()[0]["payload"]["status"], "CANCELLED")
        self.assertEqual(self.store.get_run(self.run["id"])["state"], "cancelled")
        for state in ("running", "completed", "failed", "inconclusive"):
            self.store.update_run(self.run["id"], state=state)
            self.assertEqual(self.store.get_run(self.run["id"])["state"], "cancelled")
        self.assertEqual(self.models()[0]["result"]["response_id"], "local-response-1")
        self.assertEqual(self.provider.calls, 0)

    def test_stalled_unowned_failure_cannot_overwrite_newer_completed_execution(self):
        for failure in ("configuration", "proof_mode"):
            with self.subTest(failure=failure):
                self.store = Store(Path(self.folder.name) / (failure + ".sqlite3"))
                self.run = self.store.create_run("USD29 one ticket within60 seconds", mode="LOCAL_TEST")
                self.provider = LocalProvider(self.run["purchase_id"])
                self.service = LocalService(self.provider)
                self.store.update_purchase(self.run["purchase_id"], order_id="LOCALORDER")
                entered, release = threading.Event(), threading.Event()
                invalid = LocalModel(lambda context: plan(context))
                invalid.evidence_mode = "LIVE_MODEL"
                def stalled_factory():
                    entered.set()
                    if not release.wait(4):
                        raise AssertionError("Test did not release stale configuration")
                    if failure == "configuration":
                        raise InvestigationError("MODEL_CONFIGURATION_NOT_AUTHORIZED")
                    return invalid
                def owner_strategy(context):
                    for tool in ("read_provider", "read_merchant"):
                        if tool not in context["untrusted_observations"]:
                            return plan(context, tool)
                    return plan(context)
                with ThreadPoolExecutor(max_workers=1) as workers:
                    pending = workers.submit(Investigation(self.store, self.service, model_factory=stalled_factory).run, self.run["id"])
                    try:
                        self.assertTrue(entered.wait(3))
                        owner = self.execute(LocalModel(owner_strategy))
                        self.assertEqual(owner["status"], "COMPLETED")
                        before = {"run": self.store.get_run(self.run["id"]), "events": self.store.get_events(self.run["id"]), "attempts": self.store.get_attempts(self.run["id"])}
                        self.assertEqual(before["run"]["state"], "failed")
                    finally:
                        release.set()
                    stale = pending.result(timeout=3)
                after = {"run": self.store.get_run(self.run["id"]), "events": self.store.get_events(self.run["id"]), "attempts": self.store.get_attempts(self.run["id"])}
                self.assertEqual(after, before, "Unowned failure must not mutate the newer owner or its ending")
                self.assertEqual(stale["status"], "SUPERSEDED")
                self.assertEqual(stale["reason"], "INVESTIGATION_EXECUTION_CHANGED")
                self.assertIsNone(stale["execution_attempt_id"])
                self.assertEqual(stale["trace"], [])
                self.assertEqual(stale["final_verdict"]["verdict"], "INCONCLUSIVE")
                self.assertEqual(invalid.calls, 0)
                self.assertEqual(len(self.endings()), 1)

    def test_cancel_flag_cannot_be_cleared_by_generic_update(self):
        self.store.update_run(self.run["id"], cancel_requested=1, state="cancelled")
        before = self.store.get_run(self.run["id"])
        with self.assertRaisesRegex(ValueError, "Cancellation cannot be cleared"):
            self.store.update_run(self.run["id"], cancel_requested=0, state="completed")
        self.assertEqual(self.store.get_run(self.run["id"]), before)

    def test_expired_inflight_owner_keeps_late_usage_but_cannot_complete(self):
        self.run = self.store.create_run("One USD29 ticket", mode="LOCAL_TEST", budget={"max_seconds": .04, "max_model_calls": 1, "max_attempts": 1})
        clocks = {"monotonic": 0.0, "wall": time.time()}
        class SlowModel(LocalModel):
            def complete(model, context, **budgets):
                # Expire only after the request actually enters the model.
                # Real database setup can otherwise consume the 40ms budget
                # before there is any in-flight response or usage to retain.
                clocks["monotonic"] += .06
                clocks["wall"] += .06
                response = super().complete(context, **budgets)
                response["usage"] = {"total_tokens": 7}
                return response
        model = SlowModel(lambda context: plan(context))
        with patch("crashcart.store.time.time", side_effect=lambda: clocks["wall"]):
            outcome = Investigation(self.store, self.service, model_factory=lambda: model,
                                    clock=lambda: clocks["monotonic"]).run(self.run["id"])
            self.assertEqual(model.calls, 1, "A late in-flight response requires an actual model entry")
            self.assertEqual(outcome["status"], "INTERRUPTED")
            self.assertEqual(outcome["reason"], "INVESTIGATION_DEADLINE_EXPIRED")
            self.assertEqual(outcome["final_verdict"]["verdict"], "INCONCLUSIVE")
            self.assertEqual(self.models()[0]["result"]["usage"], {"total_tokens": 7})
            self.assertEqual(len(self.endings()), 1)
            self.assertEqual(self.store.get_run(self.run["id"])["state"], "inconclusive")
            # Keep both clocks advanced: restoring real wall time here could
            # resurrect the expired deadline before the retry is checked.
            retry = LocalModel(lambda context: plan(context))
            retried = Investigation(self.store, self.service, model_factory=lambda: retry,
                                    clock=lambda: clocks["monotonic"]).run(self.run["id"])
            self.assertEqual(retried["status"], "BUDGET_EXHAUSTED")
            self.assertEqual(retry.calls, 0)
            self.assertEqual(len(self.models()), 1)

    def test_process_exit_leaves_unknown_model_receipt_and_expires_without_retry(self):
        self.run = self.store.create_run("One USD29 ticket", mode="LOCAL_TEST", budget={"max_seconds": .15, "max_model_calls": 1, "max_attempts": 1})
        code = """
import os, sys
from crashcart.store import Store
s=Store(sys.argv[1]); run_id=sys.argv[2]
s.begin_investigation(run_id, .15)
s.create_attempt(run_id, 'investigator.model', {'mode':'LOCAL_TEST', 'outcome':'unknown'})
os._exit(17)
"""
        process = subprocess.run([sys.executable, "-c", code, str(self.path), self.run["id"]], capture_output=True, text=True)
        self.assertEqual(process.returncode, 17, process.stderr)
        time.sleep(.16)
        restored = Store(self.path)
        runs = {r["id"]: r for r in restored.list_runs()}
        self.assertEqual(runs[self.run["id"]]["state"], "inconclusive")
        self.assertEqual(runs[self.run["id"]]["execution"]["state"], "interrupted")
        self.assertFalse(runs[self.run["id"]]["execution"]["active"])
        self.assertEqual(runs[self.other["id"]]["state"], "awaiting_approval")
        self.assertEqual(self.models()[0]["state"], "RUNNING")
        self.assertIsNone(self.models()[0]["result"])
        self.assertEqual(len(self.endings()), 1)
        restored.get_run(self.run["id"])
        self.assertEqual(len(self.endings()), 1)
        model = LocalModel(lambda context: plan(context))
        self.assertEqual(self.execute(model)["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(model.calls, 0)
        self.assertEqual(self.provider.calls, 0)

    def test_expiry_before_first_model_reservation_cannot_reset_deadline(self):
        self.store.begin_investigation(self.run["id"], .01)
        time.sleep(.02)
        restored = Store(self.path).get_run(self.run["id"])
        self.assertEqual(restored["execution"]["state"], "interrupted")
        model = LocalModel(lambda context: plan(context))
        outcome = self.execute(model)
        self.assertEqual(outcome["status"], "BUDGET_EXHAUSTED")
        self.assertEqual(model.calls, 0)
        self.assertEqual(self.models(), [])

    def test_http_reload_duplicate_cancel_and_other_run_isolation(self):
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def paused(context):
            entered.set()
            if not release.wait(4):
                raise AssertionError("Local test did not release paused model")
            return plan(context, "read_provider")
        model = LocalModel(paused)
        original = Investigation
        factory = lambda store, service: original(store, service, model_factory=lambda: model)
        token = "LOCAL_TEST_RUN_STATE_HTTP"
        with patch.dict(os.environ, {"CRASHCART_OPERATOR_TOKEN": token}), patch("crashcart.investigator.Investigation", side_effect=factory):
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            httpd.store = self.store
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            def request(method, path, data=None):
                conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=6)
                try:
                    conn.request(method, path, body=json.dumps(data) if data is not None else None,
                        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
                    response = conn.getresponse()
                    body = json.loads(response.read())
                    self.assertEqual(response.status, 200, body)
                    return body
                finally:
                    conn.close()
            base = "/api/runs/" + self.run["id"]
            try:
                with ThreadPoolExecutor(max_workers=1) as workers:
                    pending = workers.submit(request, "POST", base + "/investigate", {})
                    self.assertTrue(entered.wait(3))
                    detail = request("GET", base)
                    listing = request("GET", "/api/runs")
                    listed = next(r for r in listing["runs"] if r["id"] == self.run["id"])
                    self.assertEqual(detail["run"]["state"], "running")
                    self.assertTrue(detail["run"]["execution"]["active"])
                    self.assertEqual(listed["execution"], detail["run"]["execution"])
                    self.assertEqual(set(listed["execution"]), {"state", "active", "attempt_id", "started_at", "deadline_at", "reason"})
                    before_other = deepcopy(request("GET", "/api/runs/" + self.other["id"])["run"])
                    duplicate = request("POST", base + "/investigate", {})
                    self.assertEqual(duplicate["status"], "RUNNING")
                    self.assertEqual(model.calls, 1)
                    self.assertEqual(self.endings(), [])
                    cancelled = request("POST", base + "/cancel", {})
                    self.assertEqual(cancelled["state"], "cancelled")
                    self.assertFalse(cancelled["execution"]["active"])
                    release.set()
                    outcome = pending.result(timeout=3)
                    self.assertEqual(outcome["status"], "CANCELLED")
                    self.assertEqual(request("GET", base)["run"]["state"], "cancelled")
                    self.assertEqual(request("GET", "/api/runs/" + self.other["id"])["run"], before_other)
                    self.assertEqual(self.models()[0]["state"], "CANCELLED")
                    self.assertEqual(self.models()[0]["result"]["response_id"], "local-response-1")
                    self.assertFalse(any(e["event_type"] == "tool_observation" for e in self.store.get_events(self.run["id"])))
                    self.assertEqual(len(self.endings()), 1)
            finally:
                release.set()
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
