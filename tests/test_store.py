"""LOCAL_TEST persistence checks. These never call or impersonate PayPal."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest

from crashcart.store import Store


ROOT = Path(__file__).resolve().parents[1]


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "merchant.sqlite3"
        self.store = Store(self.path)
        self.run = self.store.create_run("One USD 29 ticket within 60 seconds", mode="LOCAL_TEST")
        self.purchase_id = self.run["purchase_id"]

    def tearDown(self):
        self.temp.cleanup()

    def confirm_local(self, purchase_id=None, *, order="local-test-order", capture="local-test-capture"):
        purchase_id = purchase_id or self.purchase_id
        self.store.update_purchase(purchase_id, order_id=order)
        return self.store.confirm_payment(purchase_id, order_id=order, capture_id=capture,
            amount=2900, currency="USD", completed_at="2026-10-22T10:00:00Z",
            provider_response={"mode": "LOCAL_TEST", "synthetic_test_input": True, "status": "COMPLETED"})

    def test_persists_all_experiment_identities_across_process_restart(self):
        op = self.store.operation(self.purchase_id, "create-order", {"amount": 2900, "currency": "USD"})
        self.store.update_purchase(self.purchase_id, order_id="local-order-durable")
        attempt = self.store.create_attempt(self.run["id"], "local-persistence", {"hypothesis": "restart preserves identity"})
        self.store.finish_attempt(attempt["id"], "COMPLETED", {"observed": "stored"})
        event = self.store.record_event(self.run["id"], "local_test", "created", {"local": True},
            purchase_id=self.purchase_id, order_id="local-order-durable", operation_id=op["id"], event_time="2026-10-22T09:00:00Z")
        self.store.add_evidence(self.run["id"], "local-test", f"evidence/{self.run['id']}/sample.json", "a" * 64)
        # A fresh interpreter has no access to the old connection or Python objects.
        script = """import json,sys
from crashcart.store import Store
s=Store(sys.argv[1]); r=s.get_run(sys.argv[2]); p=s.purchase_for_run(r['id'])
print(json.dumps({'run':r,'purchase':p,'operations':s.get_operations(p['id']), 'events':s.get_events(r['id']), 'attempts':s.get_attempts(r['id']), 'evidence':s.get_evidence(r['id'])}))
"""
        restored = json.loads(subprocess.check_output([sys.executable, "-c", script, str(self.path), self.run["id"]], cwd=ROOT, text=True))
        self.assertEqual(restored["run"]["id"], self.run["id"])
        self.assertEqual(restored["run"]["invariant"]["recovery_seconds"], 60)
        self.assertEqual(restored["run"]["invariant_version"], "ticket-v1")
        self.assertEqual(restored["run"]["mode"], "LOCAL_TEST")
        self.assertEqual(restored["purchase"]["order_id"], "local-order-durable")
        self.assertEqual(restored["operations"][0]["request_id"], op["request_id"])
        self.assertEqual(restored["events"][0]["id"], event["id"])
        self.assertEqual(restored["attempts"][0]["state"], "COMPLETED")
        self.assertEqual(restored["evidence"][0]["mode"], "LOCAL_TEST")

    def test_two_runs_isolate_faults_merchant_state_and_evidence(self):
        second = self.store.create_run("same promise", mode="RECORDED_REPLAY", fault={"kind": "response_loss"})
        self.confirm_local()
        self.store.fulfill(self.purchase_id)
        self.store.add_evidence(self.run["id"], "record", "exclusive-record.json", "a" * 64)
        self.assertEqual(self.store.get_run(self.run["id"])["fault"], {})
        self.assertEqual(self.store.get_run(second["id"])["fault"], {"kind": "response_loss"})
        self.assertEqual(self.store.merchant_state(second["purchase_id"])["ticket_count"], 0)
        self.assertEqual(self.store.get_evidence(second["id"]), [])
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_evidence(second["id"], "record", "exclusive-record.json", "a" * 64)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.update_purchase(second["purchase_id"], order_id="local-test-order")

    def test_all_modes_explicit_and_unregistered_fixture_rejected(self):
        for mode in ["LIVE_SANDBOX", "FRESH_SANDBOX", "RECORDED_REPLAY", "LOCAL_TEST"]:
            self.assertEqual(self.store.create_run("promise", mode=mode)["mode"], mode)
        with self.assertRaises(ValueError):
            self.store.create_run("promise", mode="LIVE")
        with self.assertRaises(ValueError):
            self.store.create_run("promise", fixture_id="https://unowned.example")

    def test_evidence_rejects_dot_relative_symlink_and_hardlink_aliases(self):
        second = self.store.create_run("separate evidence", mode="LOCAL_TEST")
        artifact = Path(self.temp.name) / "record.json"
        artifact.write_text('{"mode":"LOCAL_TEST"}')
        symlink = artifact.with_name("symlink.json")
        symlink.symlink_to(artifact)
        hardlink = artifact.with_name("hardlink.json")
        hardlink.hardlink_to(artifact)
        saved = self.store.add_evidence(self.run["id"], "record", artifact, "a" * 64)
        self.assertEqual(saved["path"], str(artifact.resolve()))
        aliases = [f"{artifact.parent}/./{artifact.name}", os.path.relpath(artifact), symlink, hardlink]
        for alias in aliases:
            with self.subTest(alias=str(alias)), self.assertRaises(sqlite3.IntegrityError):
                self.store.add_evidence(second["id"], "record", alias, "a" * 64)
        self.assertEqual(self.store.get_evidence(second["id"]), [])

    def test_evidence_rejects_alias_of_legacy_noncanonical_reference(self):
        second = self.store.create_run("separate evidence", mode="LOCAL_TEST")
        artifact = Path(self.temp.name) / "legacy-record.json"
        with self.store.connect(write=True) as db:
            db.execute("INSERT INTO evidence_refs VALUES(?,?,?,?,?,?,?)", (
                "legacy-reference", self.run["id"], "record", f"{artifact.parent}/./{artifact.name}",
                "a" * 64, "LOCAL_TEST", "2026-10-22T10:00:00Z"))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_evidence(second["id"], "record", artifact, "a" * 64)

    def test_financial_request_identity_survives_retry_and_restart(self):
        body = {"amount": 2900, "currency": "USD"}
        op = self.store.operation(self.purchase_id, "capture:v1", body)
        self.store.update_operation(op["id"], state="UNRESOLVED", response={"reason": "local injected response loss"})
        retry = Store(self.path).operation(self.purchase_id, "capture:v1", {"currency": "USD", "amount": 2900})
        self.assertEqual(op["request_id"], retry["request_id"])
        self.assertEqual(op["body_json"], retry["body_json"])
        self.assertEqual(retry["state"], "UNRESOLVED")
        with self.assertRaises(ValueError):
            self.store.operation(self.purchase_id, "capture:v1", {"amount": 1, "currency": "USD"})
        with self.store.connect(write=True) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE operations SET request_id='replacement' WHERE id=?", (op["id"],))

    def test_confirmation_is_required_and_fulfillment_is_unique(self):
        with self.assertRaises(ValueError):
            self.store.fulfill(self.purchase_id)
        self.store.update_purchase(self.purchase_id, payment_state="COMPLETED", capture_id="local-test-capture")
        with self.assertRaises(ValueError):
            self.store.fulfill(self.purchase_id)
        self.confirm_local()
        first = self.store.fulfill(self.purchase_id)
        repeated = Store(self.path).fulfill(self.purchase_id)
        self.assertEqual(first["id"], repeated["id"])
        self.assertEqual(self.store.merchant_state(self.purchase_id)["ticket_count"], 1)

    def test_confirmation_rejects_amount_currency_and_order_mismatch(self):
        self.store.update_purchase(self.purchase_id, order_id="local-order")
        good = dict(order_id="local-order", capture_id="local-capture", amount=2900, currency="USD",
                    completed_at="2026-10-22T10:00:00Z", provider_response={"LOCAL_TEST": True})
        for changes in [{"amount": 29}, {"amount": 2900.0}, {"currency": "EUR"}, {"order_id": "other"}, {"provider_response": {}}]:
            with self.assertRaises(ValueError):
                self.store.confirm_payment(self.purchase_id, **{**good, **changes})
        self.assertEqual(self.store.get_purchase(self.purchase_id)["payment_confirmed"], 0)

    def test_missing_is_distinct_from_unpaid(self):
        unpaid = self.store.merchant_state(self.purchase_id)
        missing = self.store.merchant_state("unknown-purchase")
        self.assertTrue(unpaid["known"])
        self.assertEqual(unpaid["ticket_count"], 0)
        self.assertFalse(missing["known"])
        self.assertIsNone(missing["ticket_count"])
        self.assertIsNone(self.store.get_run("unknown-run"))

    def test_trace_has_explicit_causality_and_rejects_cross_run_links(self):
        first = self.store.record_event(self.run["id"], "provider-local-input", "capture", event_time="2026-10-22T10:00:05Z")
        late = self.store.record_event(self.run["id"], "browser-local-input", "navigation", event_time="2026-10-22T10:00:01Z")
        consequence = self.store.record_event(self.run["id"], "merchant", "delivery", caused_by=first["id"])
        self.assertIsNone(late["caused_by"])
        self.assertLess(late["event_time"], first["event_time"])
        self.assertEqual(consequence["caused_by"], first["id"])
        second = self.store.create_run("separate", mode="LOCAL_TEST")
        for correlation in [{"purchase_id": self.purchase_id}, {"caused_by": first["id"]}]:
            with self.assertRaises(sqlite3.IntegrityError):
                self.store.record_event(second["id"], "local", "invalid", **correlation)

    def test_run_contract_and_evidence_modes_cannot_change_silently(self):
        with self.store.connect(write=True) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE runs SET invariant_json='{}' WHERE id=?", (self.run["id"],))
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_evidence(self.run["id"], "record", "wrong-mode.json", "b" * 64, mode="LIVE_SANDBOX")

    def test_competing_workers_claim_only_once(self):
        job = self.store.enqueue(self.run["id"], "recover", {"purchase_id": self.purchase_id}, available_at=0)
        barrier = threading.Barrier(2)
        def claim(owner):
            worker = Store(self.path)
            barrier.wait()
            return worker.claim_job(owner, now=100, lease_seconds=20)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed = list(pool.map(claim, ["worker-a", "worker-b"]))
        actual = [row for row in claimed if row is not None]
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["id"], job["id"])
        self.assertEqual(actual[0]["attempts"], 1)

    def test_expired_worker_is_fenced_after_restart(self):
        job = self.store.enqueue(self.run["id"], "recover", available_at=0)
        stale = self.store.claim_job("old-worker", now=100, lease_seconds=10)
        fresh_store = Store(self.path)
        fresh = fresh_store.claim_job("replacement-worker", now=111, lease_seconds=10)
        self.assertEqual(fresh["id"], job["id"])
        self.assertGreater(fresh["fence_token"], stale["fence_token"])
        with self.assertRaises(ValueError):
            self.store.complete_job(job["id"], "old-worker", stale["fence_token"], now=112)
        fresh_store.complete_job(job["id"], "replacement-worker", fresh["fence_token"], {"local_result": "done"}, now=112)
        self.assertIsNone(self.store.claim_job("third-worker", now=200))

    def test_duplicate_jobs_and_cancelled_runs(self):
        first = self.store.enqueue(self.run["id"], "recover", {"a": 1}, available_at=0)
        retry = self.store.enqueue(self.run["id"], "recover", {"a": 1}, available_at=0)
        self.assertEqual(first["id"], retry["id"])
        with self.assertRaises(ValueError):
            self.store.enqueue(self.run["id"], "recover", {"a": 2})
        self.store.update_run(self.run["id"], cancel_requested=1)
        self.assertIsNone(self.store.claim_job("worker", now=10))

    def test_webhook_requires_verified_marker_and_deduplicates(self):
        payload = {"id": "local-test-webhook", "mode": "LOCAL_TEST"}
        with self.assertRaises(ValueError):
            self.store.accept_webhook(payload["id"], payload, verified=False, run_id=self.run["id"])
        first = self.store.accept_webhook(payload["id"], payload, verified=True, run_id=self.run["id"])
        second = Store(self.path).accept_webhook(payload["id"], payload, verified=True, run_id=self.run["id"])
        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        with self.assertRaises(ValueError):
            self.store.accept_webhook(payload["id"], {**payload, "altered": True}, verified=True, run_id=self.run["id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
