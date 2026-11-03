"""LOCAL_TEST receipts and fake video bytes; no cloud or payment proof."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from crashcart.kernel_evidence import AUTHORITY, EVENT_TYPE, KernelEvidenceError, import_kernel_receipt, load_reviewed_bundle, event_payload
from crashcart.investigator import Investigation
from crashcart.service import MerchantService
from crashcart.store import Store


ROOT = Path(__file__).resolve().parents[1]


class KernelEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.store = Store(self.root / "copy.sqlite3")
        self.run = self.store.create_run("One sandbox ticket", mode="LOCAL_TEST", fault={"kind": "none", "merchant": "healthy"})
        self.purchase_id = self.run["purchase_id"]
        self.order_id = "LOCAL_TEST_ORDER"
        self.store.update_purchase(self.purchase_id, order_id=self.order_id, payment_state="AWAITING_APPROVAL")
        self.operation = self.store.operation(self.purchase_id, "order.create", {"LOCAL_TEST": True})
        self.store.update_operation(self.operation["id"], state="COMPLETED", response={"id": self.order_id})
        started = datetime.now(timezone.utc) - timedelta(minutes=10)
        iso = lambda seconds: (started + timedelta(seconds=seconds)).isoformat()
        self.identity = {"run_id": self.run["id"], "purchase_id": self.purchase_id, "source_mode": "LOCAL_TEST",
                         "session_id": "LOCAL_TEST_SESSION", "replay_id": "LOCAL_TEST_REPLAY",
                         "session_name": "LOCAL_TEST_NAME", "allowance_id": "LOCAL_TEST_ALLOWANCE"}
        initial_identity = {"run_id": self.run["id"], "purchase_id": self.purchase_id, "order_id": None, "mode": "LIVE_SANDBOX"}
        self.video = self.root / "fake.private.mp4"
        self.video.write_bytes(b"\x00\x00\x00\x18ftypLOCAL_TEST_NOT_A_REAL_VIDEO")
        recording = {"sha256": self.digest(self.video), "bytes": self.video.stat().st_size, "public_review": "NOT_REVIEWED"}
        observations = []
        for index, (scenario, path, order, observed, received) in enumerate((
                ("observe", "/shop", None, 5, 6), ("checkout", "/checkoutnow", self.order_id, 3, 8))):
            observations.append({"run_id": self.run["id"], "purchase_id": self.purchase_id, "order_id": order,
                "ticket_id": None, "observed_at": iso(observed), "received_at": iso(received), "path": path,
                "scenario": scenario, "session_id": self.identity["session_id"], "replay_id": self.identity["replay_id"],
                "message": "Recorded browser message" if index == 0 else "", "provider_title": "NOT CUSTOMER TEXT",
                "merchant_title": "NOT CUSTOMER TEXT", "verdict": "NOT A PAYMENT VERDICT", "run_state": "awaiting_approval"})
        self.receipt = {"schema_version": 1, "browser_kind": "KERNEL", "mode": "LOCAL_TEST",
            "identity": {**initial_identity, "order_id": self.order_id}, "observations": observations,
            "cleanup": {"recording_stop": "SUCCEEDED", "recording_download": "SUCCEEDED", "session_delete": "SUCCEEDED"},
            "status": "OBSERVED", "recording_state": "SAVED", "payment_verdict": "NOT_EVALUATED",
            "started_at": iso(0), "finished_at": iso(30), "recording": recording,
            **{k: self.identity[k] for k in ("allowance_id", "session_name", "session_id", "replay_id")}}
        self.reservation = {"grant": {"approval_id": self.identity["allowance_id"], "owned_origin": "https://owned.example.com",
            "expires_at": iso(330), "max_session_seconds": 300, "scenarios": ["observe", "checkout", "confirm_return", "cancel_return"]},
            "identity": initial_identity, "session_name": self.identity["session_name"], "reserved_at": iso(-1)}
        snapshot = self.root / "frozen-source/crashcart/kernel_browser.py"
        snapshot.parent.mkdir(parents=True); snapshot.write_text("# LOCAL_TEST frozen source fixture\n")
        self.freeze = {"run_id": self.run["id"], "source_hashes": {"crashcart/kernel_browser.py": self.digest(snapshot)}}
        self.manifest_path = self.root / "operator-review.json"
        self.manifest = {"schema_version": 1, "authority": AUTHORITY, "review_id": "LOCAL_TEST_REVIEW",
            "reviewed_at": iso(40), "identity": self.identity, "source_snapshot": "frozen-source", "artifacts": {}}
        self.write_bundle()
        self.socket_guard = patch.object(socket, "socket", side_effect=AssertionError("NETWORK_FORBIDDEN"))
        self.network = self.socket_guard.start()

    def tearDown(self):
        self.socket_guard.stop(); self.assertEqual(self.network.call_count, 0)
        self.temp.cleanup()

    @staticmethod
    def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

    def write_bundle(self):
        for kind, value in (("receipt", self.receipt), ("reservation", self.reservation), ("source_freeze", self.freeze)):
            path = self.root / (kind + ".json"); path.write_text(json.dumps(value))
            self.manifest["artifacts"][kind] = {"path": path.name, "sha256": self.digest(path)}
        self.manifest["artifacts"]["video"] = {"path": self.video.name, "sha256": self.digest(self.video), "bytes": self.video.stat().st_size}
        self.save_manifest()

    def save_manifest(self): self.manifest_path.write_text(json.dumps(self.manifest))

    def apply(self, *, apply=True):
        return import_kernel_receipt(self.store, self.manifest_path, self.root, apply=apply)

    def business_state(self):
        with self.store.connect() as db:
            return {table: [tuple(row) for row in db.execute("SELECT * FROM " + table + " ORDER BY 1")]
                    for table in ("runs", "purchases", "operations", "tickets", "jobs", "attempts", "webhooks")}

    def assert_empty(self):
        self.assertEqual(self.store.get_events(self.run["id"]), [])
        self.assertEqual(self.store.get_evidence(self.run["id"]), [])

    def test_validation_only_never_appends_or_changes_business_state(self):
        before = self.business_state(); result = self.apply(apply=False)
        self.assertEqual(result["status"], "VALIDATED_ONLY"); self.assert_empty()
        self.assertEqual(self.business_state(), before)

    def test_import_preserves_delayed_clock_domains_null_order_and_missing_visible_text(self):
        before = self.business_state(); result = self.apply()
        events = self.store.get_events(self.run["id"])
        self.assertEqual(result["status"], "IMPORTED"); self.assertEqual(len(events), 2)
        self.assertIsNone(events[0]["order_id"]); self.assertIsNone(events[0]["operation_id"])
        self.assertEqual(events[1]["operation_id"], self.operation["id"])
        self.assertLess(events[1]["event_time"], events[0]["event_time"])
        for event, observation in zip(events, self.receipt["observations"]):
            p = event["payload"]
            self.assertEqual(event["event_time"], observation["observed_at"])
            self.assertEqual(p["adapter_received_at"], observation["received_at"])
            self.assertEqual(p["imported_at"], event["observed_at"])
            self.assertNotEqual(event["event_time"], event["observed_at"])
            self.assertEqual(p["provenance"], "PRIOR_LOCAL_TEST_EXECUTION")
            self.assertEqual(p["trust_authority"], AUTHORITY)
            self.assertFalse(p["fresh_verification"]); self.assertIsNone(event["caused_by"])
            self.assertFalse(p["clock_domains"]["cross_clock_order_proves_causality"])
            self.assertNotIn(str(self.root), json.dumps(p))
            self.assertNotIn("NOT CUSTOMER TEXT", json.dumps(p))
        self.assertEqual(events[1]["payload"]["visible_text"], "")
        self.assertFalse(events[1]["payload"]["visible_text_available"])
        self.assertEqual(self.business_state(), before)

    def test_store_and_browser_tool_keep_receipt_sequence_when_import_times_tie(self):
        self.apply()
        events = self.store.get_events(self.run["id"])
        self.assertEqual(len({event["observed_at"] for event in events}), 1)
        self.assertEqual([event["payload"]["observation_index"] for event in events], [0, 1])
        self.assertGreater(events[0]["event_time"], events[1]["event_time"])
        for event in events:
            self.assertRegex(event["id"], r"^event_[a-f0-9]{32}$")
            self.assertIsNone(event["caused_by"])
        observations = Investigation(self.store, None)._tool("read_browser", {}, self.run, 10)["observations"]
        self.assertEqual([observation["observation_index"] for observation in observations], [0, 1])
        self.assertEqual(observations[-1]["url_path"], "/checkoutnow")
        self.assertFalse(observations[-1]["visible_text_available"])

    def test_repeat_and_concurrent_imports_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: self.apply(), range(3)))
        self.assertEqual(sorted(r["status"] for r in results), ["ALREADY_IMPORTED", "ALREADY_IMPORTED", "IMPORTED"])
        self.assertEqual(len(self.store.get_events(self.run["id"])), 2)
        self.assertEqual(len(self.store.get_evidence(self.run["id"])), 5)
        self.assertEqual(len({tuple(r["event_ids"]) for r in results}), 1)

    def test_second_event_database_failure_rolls_back_first_event_and_all_references(self):
        with self.store.connect(write=True) as db:
            db.execute("CREATE TRIGGER local_test_abort_second BEFORE INSERT ON events WHEN json_extract(NEW.payload_json,'$.observation_index')=1 BEGIN SELECT RAISE(ABORT,'LOCAL_TEST_FORCED_FAILURE'); END")
        before = self.business_state()
        with self.assertRaises(sqlite3.IntegrityError): self.apply()
        self.assert_empty(); self.assertEqual(self.business_state(), before)

    def test_changed_receipt_without_new_operator_pin_is_rejected(self):
        self.receipt["observations"][1]["message"] = "changed"
        (self.root / "receipt.json").write_text(json.dumps(self.receipt))
        with self.assertRaisesRegex(KernelEvidenceError, "HASH_MISMATCH"): self.apply()
        self.assert_empty()

    def test_changed_receipt_for_previously_imported_session_is_rejected(self):
        self.apply(); before = self.store.get_events(self.run["id"])
        self.receipt["observations"][1]["message"] = "changed"; self.write_bundle()
        with self.assertRaisesRegex(KernelEvidenceError, "SESSION_IMPORT_CONFLICT"): self.apply()
        self.assertEqual(self.store.get_events(self.run["id"]), before)

    def test_later_cross_run_observation_rejects_entire_bundle(self):
        self.receipt["observations"][1]["run_id"] = "run_" + "b" * 32; self.write_bundle()
        with self.assertRaisesRegex(KernelEvidenceError, "OBSERVATION_IDENTITY_MISMATCH"): self.apply()
        self.assert_empty()

    def test_wrong_purchase_order_session_replay_ticket_and_path_are_rejected(self):
        good = deepcopy(self.receipt)
        for field, value in (("purchase_id", "purchase_" + "b" * 32), ("order_id", "ANOTHER_ORDER"),
                             ("session_id", "ANOTHER_SESSION"), ("replay_id", "ANOTHER_REPLAY"),
                             ("ticket_id", "ticket_" + "c" * 32), ("path", "/return?secret=forbidden")):
            with self.subTest(field=field):
                self.receipt = deepcopy(good); self.receipt["observations"][1][field] = value; self.write_bundle()
                with self.assertRaises(KernelEvidenceError): self.apply()
                self.assert_empty()

    def test_local_test_mode_cannot_be_promoted_to_sandbox(self):
        self.manifest["identity"]["source_mode"] = "LIVE_SANDBOX"; self.save_manifest()
        with self.assertRaisesRegex(KernelEvidenceError, "RECEIPT_MODE_MISMATCH"): self.apply()
        self.assert_empty()

    def test_local_receipt_cannot_enter_a_live_destination(self):
        other = self.store.create_run("Actual mode, no provider call", mode="LIVE_SANDBOX")
        self.store.update_purchase(other["purchase_id"], order_id="OTHER_ORDER")
        self.identity.update(run_id=other["id"], purchase_id=other["purchase_id"])
        self.freeze["run_id"] = other["id"]
        self.receipt["identity"].update(run_id=other["id"], purchase_id=other["purchase_id"], order_id="OTHER_ORDER")
        self.reservation["identity"].update(run_id=other["id"], purchase_id=other["purchase_id"])
        for o in self.receipt["observations"]:
            o.update(run_id=other["id"], purchase_id=other["purchase_id"])
            if o["order_id"]: o["order_id"] = "OTHER_ORDER"
        self.write_bundle()
        with self.assertRaisesRegex(KernelEvidenceError, "DESTINATION_SCOPE_MISMATCH"): self.apply()
        self.assertEqual(self.store.get_events(other["id"]), [])

    def test_receipt_cannot_declare_payment_or_change_existing_payment_state(self):
        before = self.business_state(); self.receipt["payment_verdict"] = "PASS"; self.write_bundle()
        with self.assertRaisesRegex(KernelEvidenceError, "BROWSER_CANNOT_DECLARE_PAYMENT"): self.apply()
        self.assertEqual(self.business_state(), before); self.assert_empty()

    def test_operator_authority_is_explicit_not_provider_signed(self):
        for authority in ("PROVIDER_SIGNED", "KERNEL", None):
            self.manifest["authority"] = authority; self.save_manifest()
            with self.assertRaisesRegex(KernelEvidenceError, "OPERATOR_REVIEW_REQUIRED"): self.apply()
        self.assert_empty()

    def test_source_snapshot_reservation_and_video_are_all_bound(self):
        for relative in ("frozen-source/crashcart/kernel_browser.py", "reservation.json", self.video.name):
            with self.subTest(relative=relative):
                path = self.root / relative; before = path.read_bytes(); path.write_bytes(before + b"changed")
                with self.assertRaisesRegex(KernelEvidenceError, "HASH_MISMATCH"): self.apply()
                path.write_bytes(before); self.assert_empty()

    def test_reservation_identity_cannot_be_rewritten_even_with_rehashed_artifact(self):
        self.reservation["session_name"] = "OTHER_SESSION"; self.write_bundle()
        with self.assertRaisesRegex(KernelEvidenceError, "RESERVATION_IDENTITY_MISMATCH"): self.apply()
        self.assert_empty()

    def test_naive_and_invalid_adapter_times_are_rejected(self):
        good = deepcopy(self.receipt)
        for value in ("2026-01-01T10:00:00", "not-a-time", "2000-01-01T00:00:00Z"):
            self.receipt = deepcopy(good); self.receipt["observations"][1]["received_at"] = value; self.write_bundle()
            with self.assertRaises(KernelEvidenceError): self.apply()
        self.assert_empty()

    def test_partial_recording_can_be_imported_without_success_claim(self):
        self.receipt.update(status="FAILED", recording_state="SAVED_PARTIAL", error="KERNEL_TIMEOUT")
        self.write_bundle(); result = self.apply()
        self.assertEqual(result["status"], "IMPORTED"); self.assertFalse(result["fresh_verification"])
        self.assertEqual(self.store.get_purchase(self.purchase_id)["payment_confirmed"], 0)

    def test_path_traversal_symlink_and_hardlink_aliases_are_rejected(self):
        original = deepcopy(self.manifest["artifacts"]["receipt"])
        for path in ("../receipt.json", "/tmp/receipt.json", "https://example.com/receipt.json"):
            self.manifest["artifacts"]["receipt"]["path"] = path; self.save_manifest()
            with self.assertRaises(KernelEvidenceError): self.apply()
        for name, create in (("symbolic.json", lambda p: p.symlink_to(self.root / "receipt.json")),
                             ("hard.json", lambda p: p.hardlink_to(self.root / "receipt.json"))):
            alias = self.root / name; create(alias)
            self.manifest["artifacts"]["receipt"] = {**original, "path": name}; self.save_manifest()
            with self.assertRaisesRegex(KernelEvidenceError, "ALIAS"): self.apply()
            alias.unlink()
        self.assert_empty()

    def test_artifact_already_assigned_to_another_run_is_rejected(self):
        other = self.store.create_run("Separate local test", mode="LOCAL_TEST")
        self.store.add_evidence(other["id"], "local-test", self.video, self.digest(self.video))
        with self.assertRaisesRegex(KernelEvidenceError, "ARTIFACT_ALREADY_ASSIGNED"): self.apply()
        self.assert_empty()

    def test_messages_are_redacted_without_copying_server_labels(self):
        self.receipt["observations"][0]["message"] = "Contact buyer@example.com token https://private.example/?token=abc password=abc"
        self.write_bundle(); self.apply()
        event = next(e for e in self.store.get_events(self.run["id"]) if e["payload"]["observation_index"] == 0)
        self.assertTrue(event["payload"]["visible_text_redacted"])
        for forbidden in ("buyer@example.com", "https://private.example", "password=abc", "NOT CUSTOMER TEXT"):
            self.assertNotIn(forbidden, json.dumps(event))

    def test_v2_projects_exact_redacted_dom_fields_without_inventing_message_or_payment(self):
        self.manifest["browser_projection"] = "captured-fields-v2"
        observed = self.receipt["observations"][1]
        observed.update(provider_title="Payment confirmed", merchant_title="1 ticket",
                        verdict="Shown to buyer@example.com https://private.example/ password=secret", run_state="Completed")
        self.write_bundle(); before = self.business_state(); self.apply()
        payload = self.store.get_events(self.run["id"])[1]["payload"]
        self.assertEqual(payload["visible_text"], "")
        self.assertFalse(payload["visible_text_available"])
        self.assertEqual(payload["observed_fields"]["provider_title"], "Payment confirmed")
        self.assertEqual(payload["observed_fields"]["merchant_title"], "1 ticket")
        self.assertEqual(payload["observed_fields"]["run_state"], "Completed")
        for private in ("buyer@example.com", "https://private.example/", "password=secret"):
            self.assertNotIn(private, json.dumps(payload))
        self.assertEqual(self.business_state(), before)
        self.assertEqual(self.store.get_purchase(self.purchase_id)["payment_confirmed"], 0)
        self.assertEqual(self.apply()["status"], "ALREADY_IMPORTED")

    def test_projection_upgrade_cannot_rewrite_existing_v1_import(self):
        self.apply(); before = self.store.get_events(self.run["id"])
        self.manifest["browser_projection"] = "captured-fields-v2"; self.save_manifest()
        with self.assertRaisesRegex(KernelEvidenceError, "SESSION_IMPORT_CONFLICT"):
            self.apply()
        self.assertEqual(self.store.get_events(self.run["id"]), before)

    def test_v3_separates_failed_browser_partial_recording_from_financial_state(self):
        self.manifest["browser_projection"] = "execution-fields-v3"
        self.receipt.update(status="FAILED", recording_state="SAVED_PARTIAL", error="REMOTE_SCENARIO_FAILED")
        self.write_bundle(); before = self.business_state(); self.apply()
        events = self.store.get_events(self.run["id"])
        for event in events:
            self.assertEqual(event["payload"]["browser_execution"], {"status":"FAILED", "recording_state":"SAVED_PARTIAL", "issue":"checkout_step_failed"})
            self.assertEqual(event["payload"]["browser_projection"], "execution-fields-v3")
            self.assertNotIn("payment_verdict", event["payload"]["browser_execution"])
        self.assertEqual(self.business_state(), before)
        self.assertEqual(self.apply()["status"], "ALREADY_IMPORTED")
        self.assertEqual(events, self.store.get_events(self.run["id"]))

    def test_v3_terminal_outcomes_never_expose_arbitrary_error_content(self):
        self.manifest["browser_projection"] = "execution-fields-v3"
        for status in ("OBSERVED", "INCOMPLETE", "FAILED", "CANCELLED", "TIMED_OUT"):
            for error in ("KERNEL_TIMEOUT", "unknown password=private buyer@example.com https://private.example/", {"private":"value"}, None):
                with self.subTest(status=status, error_type=type(error).__name__):
                    self.receipt.update(status=status, recording_state="SAVED" if status=="OBSERVED" else "SAVED_PARTIAL", error=error)
                    self.write_bundle(); bundle=load_reviewed_bundle(self.manifest_path,self.root)
                    result=event_payload(bundle,self.receipt["observations"][0],0,self.manifest["reviewed_at"])
                    summary=result["browser_execution"]
                    self.assertEqual(summary["status"],status)
                    self.assertIn(summary["issue"],("time_limit","unavailable_detail",None))
                    for private in ("password=private","buyer@example.com","https://private.example/",'"private": "value"'):
                        self.assertNotIn(private,json.dumps(result))

    def test_v3_cannot_rewrite_an_existing_v2_import(self):
        self.manifest["browser_projection"]="captured-fields-v2";self.save_manifest()
        self.apply();before=self.store.get_events(self.run["id"])
        self.manifest["browser_projection"]="execution-fields-v3";self.save_manifest()
        with self.assertRaisesRegex(KernelEvidenceError,"SESSION_IMPORT_CONFLICT"):self.apply()
        self.assertEqual(self.store.get_events(self.run["id"]),before)

    def test_v3_cannot_rewrite_an_existing_v1_import(self):
        self.apply();before=self.store.get_events(self.run["id"])
        self.manifest["browser_projection"]="execution-fields-v3";self.save_manifest()
        with self.assertRaisesRegex(KernelEvidenceError,"SESSION_IMPORT_CONFLICT"):self.apply()
        self.assertEqual(self.store.get_events(self.run["id"]),before)

    def test_unknown_projection_is_rejected_before_import(self):
        for projection in ("invented-v3", {}, None, 2):
            self.manifest["browser_projection"] = projection; self.save_manifest()
            with self.assertRaisesRegex(KernelEvidenceError, "UNKNOWN_BROWSER_PROJECTION"):
                self.apply()
            self.assert_empty()

    def test_client_observation_cannot_request_import_provenance(self):
        service = MerchantService(self.store)
        local = {"url_path": "/shop", "visible_text": "client report", "action": "inspect", "browser_kind": "LOCAL_BROWSER"}
        for body in ({**local, "browser_kind": "KERNEL"}, {**local, "provenance": "PRIOR_SANDBOX_EXECUTION"}):
            with self.assertRaises(ValueError): service.observe_browser(self.run["id"], body)
        saved = service.observe_browser(self.run["id"], local)
        self.assertEqual(saved["payload"]["browser_kind"], "LOCAL_BROWSER")
        self.assertNotIn("trust_authority", saved["payload"])

    def test_real_cli_defaults_to_validation_then_applies_idempotently_without_network(self):
        script = ROOT / "scripts/import_kernel_evidence.py"
        wrapper = "import runpy,socket,sys; socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('NETWORK_FORBIDDEN')); sys.argv=sys.argv[1:]; runpy.run_path(sys.argv[0],run_name='__main__')"
        args = [sys.executable, "-c", wrapper, str(script), "--db", self.store.path,
                "--manifest", str(self.manifest_path), "--artifact-root", str(self.root)]
        before = self.business_state()
        for extra, expected in (([], "VALIDATED_ONLY"), (["--apply"], "IMPORTED"), (["--apply"], "ALREADY_IMPORTED")):
            command = subprocess.run(args + extra, capture_output=True, text=True, timeout=15, cwd=ROOT)
            self.assertEqual(command.returncode, 0, command.stderr + command.stdout)
            response = json.loads(command.stdout); self.assertEqual(response["status"], expected)
            self.assertNotIn(str(self.root), command.stdout)
            if not extra: self.assert_empty()
        self.assertEqual(self.business_state(), before)


if __name__ == "__main__": unittest.main(verbosity=2)
