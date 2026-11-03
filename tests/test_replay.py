"""Explicit synthetic LOCAL_TEST tapes; these tests prove no sandbox behavior."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from crashcart.invariant import DEFAULT_INVARIANT
from crashcart.replay import (ReplayError, digest, export_package, load_package, package_run,
                              reduce_package, replay, validate_package, verify_manifest)


def synthetic_package(fault="response_loss", recovery_at="2026-10-22T10:00:02Z", observation_at=None):
    """Construct explicit test input through the same service-event package adapter."""
    run = {"id": "synthetic-run", "mode": "LOCAL_TEST", "fixture_id": "workshop-v1",
           "invariant": dict(DEFAULT_INVARIANT), "fault": {"kind": fault, "merchant": "defective"}}
    purchase = {"id": "synthetic-purchase", "order_id": "SYNTHETICORDER"}
    body = {"intent": "CAPTURE", "purchase_units": [{"reference_id": purchase["id"], "custom_id": purchase["id"],
            "amount": {"currency_code": "USD", "value": "29.00"}}],
            "payment_source": {"paypal": {"experience_context": {"return_url": "https://owned.example/return"}}}}
    operations = [{"semantic_key": "order.create", "request_id": "synthetic-create-request", "body": body},
                  {"semantic_key": "order.capture", "request_id": "synthetic-capture-request", "body": {}}]
    complete = {"id": "SYNTHETICORDER", "intent": "CAPTURE", "status": "COMPLETED", "purchase_units": deepcopy(body["purchase_units"])}
    complete["purchase_units"][0]["payments"] = {"captures": [{"id": "SYNTHETICCAPTURE", "status": "COMPLETED",
        "amount": {"currency_code": "USD", "value": "29.00"}, "update_time": "2026-10-22T10:00:00Z"}]}
    observed = observation_at or max(recovery_at, "2026-10-22T10:01:02Z")
    merchant = {"run_id": run["id"], "purchase_id": purchase["id"], "order_id": purchase["order_id"],
                "known": True, "ticket_count": 0, "tickets": [], "observed_at": observed}
    data = [
        ("create", "provider", "order_created", "2026-10-22T09:59:50Z", {"id": purchase["order_id"], "status": "CREATED"}),
        ("approve", "provider", "pre_capture_read", "2026-10-22T09:59:59Z", {"id": purchase["order_id"], "status": "APPROVED"}),
        ("fault", "harness", "fault_activated", "2026-10-22T09:59:59Z", run["fault"]),
        ("capture", "harness", "capture_transport_response", "2026-10-22T10:00:00Z", complete),
    ]
    if fault == "process_interrupt":
        data.append(("interruption", "harness", "process_exit_boundary", "2026-10-22T10:00:00Z",
                     {"exit_code": 86, "boundary": "after_capture_before_fulfillment"}))
    data.extend([
        ("browser", "browser", "customer_observation", "2026-10-22T10:00:01Z",
         {"url_path": "/return", "visible_text": "Payment could not be confirmed. No ticket is available yet.",
          "action": "checkout returned", "browser_kind": "LOCAL_BROWSER"}),
        ("reconcile", "provider", "independent_order_read", recovery_at, complete),
        ("merchant", "merchant", "entitlement_read", observed, merchant),
    ])
    events = [{"id": name, "source": source, "event_type": kind, "observed_at": at, "payload": payload,
               "run_id": run["id"], "purchase_id": purchase["id"], "order_id": purchase["order_id"]}
              for name, source, kind, at, payload in data]
    return package_run(run, purchase, operations, events, {"tests/test_replay.py": "0" * 64})


class ReplayTests(unittest.TestCase):
    def test_same_tape_reexecutes_real_store_rules_and_unchanged_invariant(self):
        package = synthetic_package()
        frozen = deepcopy(package)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")), patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            defective = replay(package)
            healthy = replay(package, "healthy")
        self.assertEqual(defective["signature"], "paid_without_ticket")
        self.assertEqual(healthy["signature"], "ticket_delivered_once_on_time")
        self.assertEqual((defective["ticket_count"], healthy["ticket_count"]), (0, 1))
        self.assertEqual(defective["invariant"], healthy["invariant"])
        self.assertEqual(defective["input_sha256"], healthy["input_sha256"])
        self.assertEqual(defective["mode"], "LOCAL_TEST")
        self.assertEqual(package, frozen)
        self.assertNotEqual(defective["namespace_mapping"]["replay_run"], healthy["namespace_mapping"]["replay_run"])
        # Input merchant record remains zero tickets even though recomputed healthy state is one.
        self.assertEqual(package["records"][-1]["payload"]["ticket_count"], 0)

    def test_process_interruption_reopens_persisted_store_without_losing_capture_identity(self):
        for variant, signature in [("defective", "paid_without_ticket"), ("healthy", "ticket_delivered_once_on_time")]:
            result = replay(synthetic_package("process_interrupt"), variant)
            self.assertEqual(result["signature"], signature)
            self.assertEqual(result["store_reopens"], 1)
            self.assertEqual(result["source_ids"]["capture_id"], "SYNTHETICCAPTURE")

    def test_late_recorded_reconciliation_cannot_be_retimed_to_make_healthy_pass(self):
        result = replay(synthetic_package(recovery_at="2026-10-22T10:01:10Z"), "healthy")
        self.assertEqual(result["signature"], "ticket_delivered_late")

    def test_evaluation_cannot_invent_a_later_merchant_observation(self):
        package = synthetic_package(observation_at="2026-10-22T10:00:03Z")
        self.assertEqual(package["evaluate_at"], "2026-10-22T10:00:03Z")
        self.assertEqual(replay(package)["signature"], "within_recovery_window")
        package["evaluate_at"] = "2026-10-22T10:01:02Z"
        with self.assertRaisesRegex(ReplayError, "merchant observation horizon"):
            replay(package)
        with self.assertRaises(ReplayError):
            reduce_package(package)

    def test_journal_append_time_cannot_extend_the_merchant_read_horizon(self):
        package = synthetic_package(observation_at="2026-10-22T10:00:03Z")
        package["records"][-1]["observed_at"] = "2026-10-22T10:01:02Z"
        self.assertEqual(replay(package)["signature"], "within_recovery_window")
        package["evaluate_at"] = "2026-10-22T10:01:02Z"
        with self.assertRaisesRegex(ReplayError, "merchant observation horizon"):
            replay(package)
        # A later provider effect also cannot be replayed before an older merchant read.
        package = synthetic_package(observation_at="2026-10-22T10:00:03Z")
        package["records"][-1]["payload"]["observed_at"] = "2026-10-22T10:00:01Z"
        package["evaluate_at"] = "2026-10-22T10:00:01Z"
        with self.assertRaisesRegex(ReplayError, "later interaction"):
            replay(package)

    def test_actual_journal_pre_order_and_trailing_browser_are_preserved(self):
        base = synthetic_package()
        source = base["source"]
        events = deepcopy(base["records"])
        early = deepcopy(next(r for r in events if r["event_type"] == "customer_observation"))
        early.update(id="before-order", order_id=None, observed_at="2026-10-22T09:59:49Z")
        late = deepcopy(early)
        late.update(id="after-merchant-read", order_id=source["order_id"], observed_at="2026-10-22T10:01:03Z")
        events = [early] + events + [late]
        operations = [{"semantic_key": op["kind"], "request_id": op["request_id"], "body": op["body"]}
                      for op in base["operations"]]
        run = {"id": source["run_id"], "mode": source["mode"], "fixture_id": base["fixture_id"],
               "invariant": base["invariant"], "fault": base["fault"]}
        package = package_run(run, {"id": source["purchase_id"], "order_id": source["order_id"]}, operations, events, source["hashes"])
        self.assertEqual([r["id"] for r in package["records"]], [r["id"] for r in events])
        self.assertIsNone(package["records"][0]["order_id"])
        self.assertEqual(package["evaluate_at"], base["evaluate_at"])
        self.assertNotIn(late["id"], [s["id"] for s in package["steps"]])
        result = replay(package)
        self.assertEqual(result["signature"], "paid_without_ticket")
        self.assertEqual(result["source_only_after_horizon"], [late["id"]])
        self.assertNotIn(late["id"], [s["step_id"] for s in result["trace"]])
        self.assertEqual(replay(package, "healthy")["signature"], "ticket_delivered_once_on_time")
        self.assertTrue(reduce_package(package)["repeatable"])
        with self.assertRaisesRegex(ReplayError, "horizon"):
            replay(package, steps=package["steps"] + [{"id": late["id"], "record_id": late["id"], "kind": "observe_browser"}])
        for field, value in [("run_id", "another-run"), ("purchase_id", "another-purchase"), ("order_id", "another-order")]:
            changed = deepcopy(package)
            changed["records"][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ReplayError, "namespace"):
                replay(changed)
        changed = deepcopy(package)
        changed["records"][-1]["order_id"] = None
        with self.assertRaisesRegex(ReplayError, "namespace"):
            replay(changed)

    def test_fault_activation_must_precede_capture_in_time_and_record_order(self):
        for alteration in ("late_timestamp", "late_record", "before_approval", "duplicate"):
            package = synthetic_package()
            fault = next(r for r in package["records"] if r["id"] == "fault")
            if alteration == "late_timestamp":
                fault["observed_at"] = "2026-10-22T10:01:02Z"
            elif alteration == "late_record":
                package["records"].remove(fault)
                fault["observed_at"] = "2026-10-22T10:01:02Z"
                package["records"].insert(-1, fault)
            elif alteration == "before_approval":
                package["records"].remove(fault)
                fault["observed_at"] = "2026-10-22T09:59:58Z"
                package["records"].insert(1, fault)
            else:
                duplicate = deepcopy(fault)
                duplicate["id"] = "fault-again"
                package["records"].insert(3, duplicate)
            with self.subTest(alteration=alteration), self.assertRaises(ReplayError):
                replay(package)

    def test_interruption_boundary_is_between_capture_and_recovery(self):
        for alteration in ("before_capture", "after_recovery", "late_timestamp", "wrong_fault"):
            package = synthetic_package("process_interrupt")
            boundary = next(r for r in package["records"] if r["id"] == "interruption")
            if alteration == "before_capture":
                package["records"].remove(boundary)
                package["records"].insert(3, boundary)
            elif alteration == "after_recovery":
                package["records"].remove(boundary)
                boundary["observed_at"] = "2026-10-22T10:00:02Z"
                package["records"].insert(-1, boundary)
            elif alteration == "late_timestamp":
                boundary["observed_at"] = "2026-10-22T10:01:02Z"
            else:
                package["fault"]["kind"] = "response_loss"
                next(r for r in package["records"] if r["id"] == "fault")["payload"]["kind"] = "response_loss"
            with self.subTest(alteration=alteration), self.assertRaises(ReplayError):
                replay(package)

    def test_unredacted_request_hash_must_match_and_capture_cannot_claim_redaction(self):
        package = synthetic_package()
        capture = next(op for op in package["operations"] if op["kind"] == "order.capture")
        capture["original_body_sha256"] = "f" * 64
        with self.assertRaisesRegex(ReplayError, "does not match its original hash"):
            replay(package)
        capture["redacted_fields"] = ["description"]
        with self.assertRaisesRegex(ReplayError, "empty capture body"):
            replay(package)
        package = synthetic_package()
        create = next(op for op in package["operations"] if op["kind"] == "order.create")
        create["redacted_fields"] = []
        create["original_body_sha256"] = digest(create["body"])
        self.assertEqual(replay(package)["operation_mapping"][0]["original_body_hash_status"], "verified")
        create["original_body_sha256"] = "f" * 64
        with self.assertRaisesRegex(ReplayError, "does not match its original hash"):
            replay(package)

    def test_redacted_original_hash_is_explicitly_unverifiable(self):
        result = replay(synthetic_package())
        self.assertEqual(result["operation_mapping"][0]["original_body_hash_status"], "unverifiable_after_redaction")
        self.assertEqual(result["operation_mapping"][1]["original_body_hash_status"], "verified")

    def test_missing_reconciliation_is_inconclusive_and_never_saved_failure(self):
        package = synthetic_package()
        steps = [s for s in package["steps"] if s["kind"] != "reconcile"]
        self.assertEqual(replay(package, steps=steps)["signature"], "missing_provider_evidence")

    def test_duplicate_reconciliation_fulfills_once(self):
        package = synthetic_package()
        record = deepcopy(next(r for r in package["records"] if r["id"] == "reconcile"))
        record.update(id="reconcile-again", observed_at="2026-10-22T10:00:03Z")
        package["records"].insert(-1, record)
        package["steps"].insert(-1, {"id": record["id"], "kind": "reconcile", "record_id": record["id"]})
        result = replay(package, "healthy")
        self.assertEqual(result["ticket_count"], 1)
        self.assertEqual(result["verdict"], "PASS")

    def test_reducer_executes_candidates_preserves_prerequisites_and_repeats(self):
        report = reduce_package(synthetic_package(), max_candidates=16, repeats=3)
        self.assertLess(report["reduced_size"], report["original_size"])
        self.assertEqual(report["repeat_signatures"], ["paid_without_ticket"] * 3)
        self.assertTrue(report["repeatable"])
        self.assertEqual(report["description"], "smallest reproducer found within the search")
        by_kind = {c["kind"]: c for c in report["candidates"]}
        for kind in ["order_create", "buyer_approval", "capture", "reconcile"]:
            self.assertFalse(by_kind[kind]["accepted"])
        self.assertFalse(by_kind["buyer_approval"]["executed"])
        self.assertTrue(by_kind["reconcile"]["executed"])
        self.assertEqual(report["candidates_attempted"], report["original_size"])
        self.assertTrue(by_kind["observe_browser"]["accepted"])
        self.assertTrue(by_kind["observe_merchant"]["accepted"])
        self.assertEqual(replay(report["package"])["signature"], "paid_without_ticket")
        bounded = reduce_package(synthetic_package(), max_candidates=1, repeats=2)
        self.assertEqual(bounded["termination_reason"], "budget_exhausted")

    def test_invalid_and_missing_source_records_fail_closed(self):
        for event in ["customer_observation", "capture_transport_response", "independent_order_read", "entitlement_read", "fault_activated"]:
            package = synthetic_package()
            package["records"] = [r for r in package["records"] if r["event_type"] != event]
            with self.subTest(event=event), self.assertRaises(ReplayError):
                replay(package)
        package = synthetic_package()
        package["source"]["mode"] = "RECORDED_REPLAY"
        with self.assertRaises(ReplayError):
            replay(package)
        package = synthetic_package()
        package["source"]["mode"] = "LIVE_SANDBOX"  # synthetic=True must prevent promotion
        with self.assertRaises(ReplayError):
            replay(package)

    def test_recorded_payment_correlation_and_contract_cannot_be_changed(self):
        for change in ["amount", "capture", "run", "deadline", "extra", "path"]:
            package = synthetic_package()
            if change == "amount":
                next(r for r in package["records"] if r["id"] == "reconcile")["payload"]["purchase_units"][0]["payments"]["captures"][0]["amount"]["value"] = "0.01"
            elif change == "capture":
                next(r for r in package["records"] if r["id"] == "reconcile")["payload"]["purchase_units"][0]["payments"]["captures"][0]["id"] = "other"
            elif change == "run":
                package["records"][-1]["run_id"] = "other"
            elif change == "deadline":
                package["invariant"]["recovery_seconds"] = 1000
            elif change == "extra":
                package["api_key"] = "should-not-be-exported"
            else:
                package["source"]["hashes"] = {"/absolute/private.py": "0" * 64}
            with self.subTest(change=change), self.assertRaises(ReplayError):
                replay(package)

    def test_existing_ticket_record_cannot_be_ignored_to_manufacture_mismatch(self):
        package = synthetic_package()
        merchant = package["records"][-1]["payload"]
        merchant.update(ticket_count=1, tickets=[{"id": "already-issued", "purchase_id": "synthetic-purchase",
                                                  "created_at": "2026-10-22T10:00:30Z"}])
        with self.assertRaises(ReplayError):
            replay(package)

    def test_unsupported_interactions_and_removed_buyer_approval_never_call_network(self):
        package = synthetic_package()
        cases = [[s for s in package["steps"] if s["kind"] != "buyer_approval"],
                 [{**package["steps"][0], "kind": "network_request"}] + package["steps"][1:]]
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            for steps in cases:
                with self.assertRaises(ReplayError):
                    replay(package, steps=steps)

    def test_export_runs_in_clean_directory_without_network_and_detects_tampering(self):
        with tempfile.TemporaryDirectory(prefix="crashcart-export-test-") as directory:
            root = Path(directory)
            receipt = export_package(synthetic_package(), root / "regression.zip")
            self.assertEqual(receipt["mode"], "LOCAL_TEST")
            with zipfile.ZipFile(root / "regression.zip") as archive:
                self.assertFalse(any(n.startswith("/") or ".." in Path(n).parts for n in archive.namelist()))
                archive.extractall(root / "clean")
            clean = root / "clean"
            self.assertEqual(verify_manifest(clean)["result"], "PASS")
            boot = ("import socket,runpy,sys; "
                    "socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden')); "
                    "socket.create_connection=socket.socket; "
                    "sys.argv=['crashcart.replay']+sys.argv[1:]; "
                    "runpy.run_module('crashcart.replay',run_name='__main__')")
            for variant, code, signature in [("defective", 1, "paid_without_ticket"), ("healthy", 0, "ticket_delivered_once_on_time")]:
                process = subprocess.run([sys.executable, "-c", boot, "run", "input.json", "--merchant", variant],
                    cwd=clean, env={"PATH": os.environ.get("PATH", ""), "PYTHONNOUSERSITE": "1"},
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(process.returncode, code, process.stderr + process.stdout)
                result = json.loads(process.stdout)
                self.assertEqual(result["signature"], signature)
                self.assertEqual(result["mode"], "LOCAL_TEST")
            with self.assertRaises(ReplayError):
                export_package(synthetic_package(), root / "regression.zip")
            (clean / "crashcart/invariant.py").write_text("tampered")
            with self.assertRaises(ReplayError):
                verify_manifest(clean)

    def test_duplicate_json_keys_and_oversized_input_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text('{"source": {}, "source": {}}')
            with self.assertRaises(ReplayError):
                load_package(path)
            path.write_text(" " * 2_000_001)
            with self.assertRaises(ReplayError):
                load_package(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
