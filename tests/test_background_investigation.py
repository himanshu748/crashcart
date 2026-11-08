"""LOCAL_TEST HTTP/worker integration; injected models and loopback sockets only."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from crashcart.investigator import Investigation, MAX_SECONDS
from crashcart.server import Handler, ThreadingHTTPServer
from crashcart.store import Store
from crashcart.worker import INVESTIGATION_JOB_KEY, _reserve_investigation_job, investigation_job, work
from tests.test_investigator import LocalModel, LocalProvider, LocalService, plan


class BackgroundInvestigationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "state.sqlite3"
        self.store = Store(self.path)
        self.run = self.store.create_run("USD 29 buys one ticket within 60 seconds", mode="LOCAL_TEST")
        self.store.update_purchase(self.run["purchase_id"], order_id="LOCALORDER")
        self.provider = LocalProvider(self.run["purchase_id"])
        self.service = LocalService(self.provider)
        self.model = LocalModel(lambda context: plan(context, "read_provider" if "read_provider" not in context["untrusted_observations"]
            else "read_merchant" if "read_merchant" not in context["untrusted_observations"] else "finish"))
        self.env = patch.dict(os.environ, {"CRASHCART_OPERATOR_TOKEN": "local-only-background-token",
            "CRASHCART_MODEL_PROVIDER": "openai", "OPENAI_API_KEY": "", "OPENAI_MODEL": "",
            "CRASHCART_ALLOW_MODEL": "0", "CRASHCART_ALLOW_SANDBOX": "0", "CRASHCART_EVALUATION_MODE": "ordinary"})
        self.env.start(); self.addCleanup(self.env.stop)
        original = socket.socket.connect
        def loopback(sock, address):
            if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise AssertionError("LOCAL_TEST external network forbidden")
            return original(sock, address)
        blocker = patch.object(socket.socket, "connect", loopback)
        blocker.start(); self.addCleanup(blocker.stop)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.store = self.store
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(3)

    def request(self, method, path=None, body=None, *, auth=True):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=3)
        headers = {"Content-Type": "application/json"}
        if auth: headers["Authorization"] = "Bearer local-only-background-token"
        connection.request(method, path or f"/api/runs/{self.run['id']}/investigation-job",
            json.dumps(body if body is not None else {}) if method == "POST" else None, headers)
        response = connection.getresponse(); result = (response.status, json.loads(response.read()))
        connection.close(); return result

    def run_worker(self, model=None):
        selected = self.model if model is None else model
        with patch("crashcart.investigator.Investigation", side_effect=lambda store, _service:
                Investigation(store, self.service, model_factory=lambda: selected)):
            work(self.path, once=True)

    def job_row(self):
        with self.store.connect() as db:
            return dict(db.execute("SELECT * FROM jobs WHERE run_id=?", (self.run["id"],)).fetchone())

    def test_http_acknowledges_queue_without_inference_and_deduplicates_across_restart(self):
        with patch("crashcart.investigator.Investigation", side_effect=AssertionError("Enqueue must not start analysis")):
            first_status, first = self.request("POST")
            second_status, second = self.request("POST")
        self.assertEqual((first_status, second_status), (202, 202))
        self.assertEqual(first["job"], second["job"])
        self.assertEqual(first["job"]["state"], "PENDING")
        self.assertIsNone(first["job"]["result"])
        self.assertEqual((self.model.calls, self.provider.calls), (0, 0))
        restored = Store(self.path)
        self.assertEqual(investigation_job(restored, self.run["id"]), first["job"])
        status, detail = self.request("GET", f"/api/runs/{self.run['id']}")
        self.assertEqual(status, 200); self.assertEqual(detail["investigation_job"], first["job"])
        with restored.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)

    def test_concurrent_http_requests_reserve_one_durable_job(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            replies = list(pool.map(lambda _: self.request("POST"), range(8)))
        self.assertEqual({status for status, _ in replies}, {202})
        self.assertEqual(len({body["job"]["id"] for _, body in replies}), 1)
        self.assertEqual(self.job_row()["attempts"], 0)
        self.assertEqual((self.model.calls, self.provider.calls), (0, 0))

    def test_two_workers_do_not_dispatch_concurrent_models(self):
        self.request("POST")
        entered, release = threading.Event(), threading.Event()
        strategy = self.model.strategy
        def wait(context):
            if not context["untrusted_observations"]:
                entered.set()
                if not release.wait(3): raise AssertionError("Test release missing")
            return strategy(context)
        self.model.strategy = wait
        thread = threading.Thread(target=self.run_worker)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.run_worker()
            self.assertEqual(self.model.calls, 1)
            self.assertEqual(self.job_row()["state"], "RUNNING")
        finally:
            release.set(); thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.model.calls, 3)
        self.assertEqual(self.job_row()["state"], "COMPLETED")

    def test_actual_worker_runs_adaptive_model_and_shared_records_then_never_requeues(self):
        self.request("POST")
        self.run_worker()
        row = self.job_row(); self.assertEqual(row["state"], "COMPLETED")
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["result"]["status"], "COMPLETED")
        self.assertEqual(summary["result"]["model_mode"], "LOCAL_TEST")
        self.assertEqual(summary["result"]["final_verdict"]["signature"], "paid_without_ticket")
        self.assertEqual(set(summary["result"]), {"status", "reason", "model_mode", "final_verdict"})
        self.assertEqual((self.model.calls, self.provider.calls), (3, 1))
        self.assertEqual(self.store.get_run(self.run["id"])["state"], "failed")
        self.assertEqual(len([e for e in self.store.get_events(self.run["id"]) if e["event_type"] == "investigation_ended"]), 1)
        self.assertEqual(self.request("POST")[1]["job"]["id"], row["id"])
        self.run_worker(); self.assertEqual((self.model.calls, self.provider.calls), (3, 1))

    def test_cancel_pending_job_never_runs_or_reports_success(self):
        self.request("POST")
        self.request("POST", f"/api/runs/{self.run['id']}/cancel")
        self.run_worker()
        status, detail = self.request("GET", f"/api/runs/{self.run['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(self.job_row()["state"], "CANCELLED")
        self.assertEqual(detail["investigation_job"]["state"], "CANCELLED")
        self.assertEqual(detail["investigation_job"]["result"]["status"], "CANCELLED")
        self.assertEqual((self.model.calls, self.provider.calls), (0, 0))
        self.assertEqual(self.request("POST")[0], 409)

    def test_model_failure_is_terminal_failed_without_automatic_retry(self):
        self.request("POST")
        def fail(_context): raise RuntimeError("private upstream detail must not persist")
        model = LocalModel(fail)
        self.run_worker(model)
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["result"]["status"], "FAILED")
        self.assertNotIn("private upstream detail", json.dumps(summary))
        self.run_worker(model); self.assertEqual(model.calls, 1)

    def test_completed_analysis_keeps_its_inconclusive_customer_verdict(self):
        self.request("POST")
        self.run_worker(LocalModel(lambda context: plan(context)))
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "COMPLETED")
        self.assertEqual(summary["result"]["final_verdict"]["verdict"], "INCONCLUSIVE")

    def test_cancellation_during_model_preserves_cancelled_job_without_provider_work(self):
        self.request("POST")
        def cancel(context):
            self.store.update_run(self.run["id"], cancel_requested=1)
            return plan(context)
        model = LocalModel(cancel)
        self.run_worker(model)
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "CANCELLED")
        self.assertEqual(summary["result"]["status"], "CANCELLED")
        self.assertEqual((model.calls, self.provider.calls), (1, 0))

    def test_lost_job_lease_cannot_commit_success_or_repeat_the_model(self):
        self.request("POST")
        def expire(context):
            with self.store.connect(write=True) as db:
                db.execute("UPDATE jobs SET lease_until=0 WHERE run_id=?", (self.run["id"],))
            return plan(context)
        model = LocalModel(expire)
        self.run_worker(model)
        self.assertEqual(self.job_row()["state"], "RUNNING")
        self.assertEqual(model.calls, 1)
        self.run_worker(model)
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["result"]["reason"], "BACKGROUND_INVESTIGATION_INTERRUPTED")
        self.assertEqual(model.calls, 1)

    def test_missing_configuration_fails_worker_without_any_model_request(self):
        self.request("POST")
        work(self.path, once=True)
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["result"]["status"], "BLOCKED")
        self.assertIn("MISSING_CONFIGURATION", summary["result"]["reason"])
        self.assertFalse([a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"])

    def test_reclaimed_job_is_interrupted_and_never_dispatches_unknown_inference(self):
        self.request("POST")
        old = self.store.claim_job("crashed-owner")
        with self.store.connect(write=True) as db:
            db.execute("UPDATE jobs SET lease_until=0 WHERE id=?", (old["id"],))
        with patch("crashcart.investigator.Investigation", side_effect=AssertionError("No inference retry")):
            work(self.path, once=True)
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["result"], {"status": "INTERRUPTED", "reason": "BACKGROUND_INVESTIGATION_INTERRUPTED"})
        self.assertEqual(self.job_row()["attempts"], 2)

    def test_job_lease_is_separate_from_unchanged_investigation_and_payment_deadlines(self):
        self.request("POST")
        claimed = self.store.claim_job("owner")
        before = self.store.get_run(self.run["id"])
        self.assertIsNone(_reserve_investigation_job(self.store, claimed, "owner"))
        row = self.job_row()
        self.assertGreater(row["lease_until"] - time.time(), MAX_SECONDS)
        self.assertIsNone(self.store.claim_job("competitor", now=time.time() + 31))
        after = self.store.get_run(self.run["id"])
        self.assertEqual(after["budget"], before["budget"])
        self.assertEqual(after["invariant"], before["invariant"])
        with self.assertRaises(ValueError): _reserve_investigation_job(self.store, claimed, "wrong-owner")
        with self.assertRaises(ValueError): _reserve_investigation_job(self.store, {**claimed, "fence_token": claimed["fence_token"] - 1}, "owner")

    def test_existing_execution_owner_wins_without_duplicate_model_work(self):
        self.request("POST")
        execution = self.store.begin_investigation(self.run["id"], 90)
        self.run_worker()
        self.assertEqual(self.model.calls, 0)
        summary = investigation_job(self.store, self.run["id"])
        self.assertEqual(summary["state"], "FAILED")
        self.assertEqual(summary["result"]["status"], "RUNNING")
        self.assertEqual(self.store.get_run(self.run["id"])["execution"]["attempt_id"], execution)
        self.assertTrue(self.store.get_run(self.run["id"])["execution"]["active"])

    def test_http_rejects_unauthorized_payload_unknown_replay_and_cancelled_requests(self):
        self.assertEqual(self.request("POST", auth=False)[0], 401)
        self.assertEqual(self.request("POST", body={"verdict": "PASS"})[0], 400)
        self.assertEqual(self.request("POST", "/api/runs/missing/investigation-job")[0], 404)
        replay = self.store.create_run("Recorded only", mode="RECORDED_REPLAY")
        self.assertEqual(self.request("POST", f"/api/runs/{replay['id']}/investigation-job")[0], 400)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 0)


if __name__ == "__main__": unittest.main()
