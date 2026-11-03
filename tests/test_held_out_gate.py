"""Production gate with intercepted transport and synthetic LOCAL_TEST evidence.

No model/provider calls or selected seed. All receipts are explicit local fixtures.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
import uuid
from unittest.mock import patch
from urllib.request import Request

from crashcart import held_out, model_transport
from crashcart.held_out import HeldOutGate, HeldOutError, NEUTRAL_PROMISE, sha
from crashcart.invariant import DEFAULT_INVARIANT
from crashcart.investigator import Investigation, OpenAIModel, SYSTEM, MODEL_PLAN_SCHEMA, PROMPT_VERSION
from crashcart.store import Store, canonical
from tests.test_investigator import LocalProvider, LocalService, plan


class HeldOutGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = Store(self.directory / "state.sqlite3")
        self.run = self.store.create_run(NEUTRAL_PROMISE, mode="LOCAL_TEST")
        self.provider = LocalProvider(self.run["purchase_id"])
        self.service = LocalService(self.provider)
        self.event = self.store.record_event(self.run["id"], "browser", "customer_observation",
            {"browser_kind": "LOCAL_BROWSER", "visible_text": "Your workshop ticket is being prepared.",
             "action": "customer_checkout_view", "url_path": "/checkout"}, purchase_id=self.run["purchase_id"])
        self.receipt_path = self.directory / "customer-receipt.json"
        self.receipt_path.write_text(canonical({"synthetic": True, "event": self.event}))
        self.policy_path = self.directory / "policy.json"
        self.calls, self.contexts = [], []
        self.strategy = lambda context: plan(context)
        self.model = OpenAIModel(environ={}, transport=self.transport)
        self.policy = self.make_policy()
        self.env = self.write_policy()
        self.environ_patch = patch.dict(os.environ, self.env, clear=True)
        self.environ_patch.start()
        self.addCleanup(self.environ_patch.stop)
        for target in ("socket.socket", "socket.create_connection"):
            guard = patch(target, side_effect=AssertionError("LOCAL_TEST forbids sockets"))
            guard.start()
            self.addCleanup(guard.stop)

    def make_policy(self):
        run = self.store.get_run(self.run["id"])
        return {"version": held_out.POLICY_VERSION, "run_id": run["id"], "purchase_id": run["purchase_id"],
            "order_id": self.store.purchase_for_run(run["id"])["order_id"], "fixture_id": run["fixture_id"],
            "proof_mode": run["mode"], "neutral_promise": NEUTRAL_PROMISE, "invariant": dict(DEFAULT_INVARIANT),
            "budget": run["budget"], "model_configuration": {**self.model.provenance(), "endpoint": self.model.config.endpoint},
            "input_version": PROMPT_VERSION, "system_sha256": sha(SYSTEM), "schema_sha256": sha(MODEL_PLAN_SCHEMA),
            "schema_name": "crashcart_investigator_wire_v4", "max_output_tokens": 1024,
            "response_model": self.model.model, "source_hashes": held_out.source_hashes(), "customer_receipts": [{"event": deepcopy(self.event),
                "event_sha256": sha(self.event), "receipt_path": str(self.receipt_path),
                "receipt_sha256": hashlib.sha256(self.receipt_path.read_bytes()).hexdigest()}]}

    def write_policy(self):
        if self.policy_path.exists():
            self.policy_path.chmod(0o600)
        self.policy_path.write_text(canonical(self.policy))
        self.policy_path.chmod(0o400)
        return {"CRASHCART_EVALUATION_MODE": "held_out", "CRASHCART_HELD_OUT_POLICY": str(self.policy_path),
                "CRASHCART_HELD_OUT_POLICY_SHA256": hashlib.sha256(self.policy_path.read_bytes()).hexdigest()}

    def refresh_policy(self):
        self.policy = self.make_policy()
        os.environ.update(self.write_policy())

    def transport(self, request, timeout):
        self.calls.append(bytes(request.data))
        body = json.loads(request.data)
        context = json.loads(body["input"][1]["content"])
        self.contexts.append(deepcopy(context))
        result = self.strategy(context)
        return {"id": "local-response-" + str(len(self.calls)), "model": self.model.model,
                "status": "completed", "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                "output": [{"type": "message", "role": "assistant", "content": [
                    {"type": "output_text", "text": canonical(result)}]}]}

    def execute(self, **kwargs):
        return Investigation(self.store, self.service, model_factory=lambda: self.model, **kwargs).run(self.run["id"])

    def assert_rejected(self, outcome, *, sends=0):
        self.assertEqual(outcome["final_verdict"]["verdict"], "INCONCLUSIVE", outcome)
        self.assertEqual(outcome["status"], "BLOCKED", outcome)
        self.assertTrue(outcome["reason"].startswith("HELD_OUT_"), outcome)
        self.assertEqual(len(self.calls), sends)

    def test_clean_production_entrypoint_exact_wire_and_receipts(self):
        self.strategy = lambda context: plan(context, "read_browser" if not context["prior_plans"] else "finish")
        original = deepcopy(self.event)
        outcome = self.execute()
        self.assertEqual(outcome["status"], "COMPLETED", outcome)
        self.assertEqual(len(self.calls), 2)
        observation = self.contexts[-1]["untrusted_observations"]["read_browser"]["data"]["observations"][0]
        self.assertEqual(observation["visible_text"], original["payload"]["visible_text"])
        self.assertEqual(next(e for e in self.store.get_events(self.run["id"]) if e["id"] == original["id"]), original)
        self.assertNotIn("customer_receipts", self.calls[0].decode())
        self.assertNotIn(str(self.policy_path), self.calls[0].decode())
        self.assertNotIn(str(self.receipt_path), self.calls[0].decode())

    def test_missing_corrupt_writable_and_changed_policy_fail_closed(self):
        for change in ("missing_path", "missing_hash", "corrupt", "writable", "changed_hash"):
            with self.subTest(change=change):
                os.environ.update(self.write_policy())
                if change == "missing_path": os.environ.pop("CRASHCART_HELD_OUT_POLICY")
                if change == "missing_hash": os.environ.pop("CRASHCART_HELD_OUT_POLICY_SHA256")
                if change == "corrupt":
                    self.policy_path.chmod(0o600)
                    self.policy_path.write_text('{"bad":')
                    self.policy_path.chmod(0o400)
                    os.environ["CRASHCART_HELD_OUT_POLICY_SHA256"] = hashlib.sha256(self.policy_path.read_bytes()).hexdigest()
                if change == "writable": self.policy_path.chmod(0o600)
                if change == "changed_hash": os.environ["CRASHCART_HELD_OUT_POLICY_SHA256"] = "0" * 64
                self.assert_rejected(self.execute())
        self.assertEqual(self.store.get_attempts(self.run["id"]), [])

    def test_wrong_run_purchase_order_and_source_freeze_block_before_send(self):
        for field, value in (("run_id", "run_other"), ("purchase_id", "purchase_other"), ("order_id", "OTHER"),
                             ("system_sha256", "0" * 64), ("schema_sha256", "0" * 64),
                             ("source_hashes", {}), ("budget", {"max_attempts": 500})):
            with self.subTest(field=field):
                self.setUp_next_run()
                self.policy = self.make_policy()
                self.policy[field] = value
                os.environ.update(self.write_policy())
                self.assert_rejected(self.execute())

    def test_policy_and_customer_mutation_after_first_request_stop_next_send(self):
        def strategy(context):
            self.receipt_path.write_text("Changed original customer receipt")
            return plan(context, "read_browser")
        self.strategy = strategy
        outcome = self.execute()
        self.assert_rejected(outcome, sends=1)
        self.assertEqual([a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"][0]["result"]["usage"]["total_tokens"], 15)

    def test_original_event_identity_full_payload_and_missing_text_are_checked(self):
        for mutation in ("changed_payload", "wrong_purchase", "wrong_order", "no_text"):
            with self.subTest(mutation=mutation):
                self.setUp_next_run()
                self.policy = self.make_policy()
                event = self.policy["customer_receipts"][0]["event"]
                if mutation == "changed_payload": event["payload"]["nested"] = {"opaque": ["new"]}
                if mutation == "wrong_purchase": event["purchase_id"] = "foreign"
                if mutation == "wrong_order": event["order_id"] = "foreign"
                if mutation == "no_text": event["payload"]["visible_text"] = ""
                self.policy["customer_receipts"][0]["event_sha256"] = sha(event)
                os.environ.update(self.write_policy())
                self.assert_rejected(self.execute())

    def test_leaked_nested_keys_values_arrays_and_approved_dashboard_are_blocked(self):
        for leaked in ({"expected_answer": "opaque"}, {"extra": [{"response_loss": "opaque"}]},
                       {"extra": ["Promise broken"]}, {"extra": {"verdict": "opaque"}}):
            with self.subTest(leaked=leaked):
                self.setUp_next_run()
                self.event["payload"].update(leaked)
                self.event["payload_json"] = canonical(self.event["payload"])
                with self.store.connect(write=True) as db:
                    db.execute("UPDATE events SET payload_json=? WHERE id=?", (self.event["payload_json"], self.event["id"]))
                self.receipt_path.write_text(canonical({"synthetic": True, "event": self.event}))
                self.refresh_policy()
                self.assert_rejected(self.execute())
                self.assertEqual(next(e for e in self.store.get_events(self.run["id"]) if e["id"] == self.event["id"]), self.event)

    def test_exact_final_request_mutation_is_rejected_before_transport(self):
        real_request = Request
        for mutation in ("nested", "prior", "proposal", "system", "schema", "model", "extra", "destination"):
            with self.subTest(mutation=mutation):
                def mutated(url, *, data, **kwargs):
                    body = json.loads(data)
                    if mutation == "nested":
                        context = json.loads(body["input"][1]["content"])
                        context["untrusted_observations"] = {"read_provider": {"data": {"expected_answer": "opaque"}}}
                        body["input"][1]["content"] = canonical(context)
                    if mutation in {"prior", "proposal"}:
                        context = json.loads(body["input"][1]["content"])
                        if mutation == "prior": context["prior_plans"] = [{"hypothesis": "response_loss"}]
                        else: context["untrusted_observations"] = {"propose_fault": {"data": {"proposal": "response_loss"}}}
                        body["input"][1]["content"] = canonical(context)
                    if mutation == "system": body["input"][0]["content"] += " extra instruction"
                    if mutation == "schema": body["text"]["format"]["schema"]["title"] = "extra"
                    if mutation == "model": body["model"] = "other"
                    if mutation == "extra": body["metadata"] = {"seed": "opaque"}
                    if mutation == "destination": url = "https://example.invalid"
                    return real_request(url, data=canonical(body).encode(), **kwargs)
                # Fresh run budget for each separate synthetic attempt.
                with patch.object(model_transport, "Request", side_effect=mutated):
                    outcome = self.execute()
                self.assert_rejected(outcome)
                if mutation != "destination":
                    self.setUp_next_run()

    def setUp_next_run(self):
        self.store = Store(self.directory / (uuid.uuid4().hex + ".sqlite3"))
        self.run = self.store.create_run(NEUTRAL_PROMISE, mode="LOCAL_TEST")
        self.provider = LocalProvider(self.run["purchase_id"])
        self.service = LocalService(self.provider)
        self.event = self.store.record_event(self.run["id"], "browser", "customer_observation",
            {"browser_kind": "LOCAL_BROWSER", "visible_text": "Your workshop ticket is being prepared.",
             "action": "customer_checkout_view", "url_path": "/checkout"}, purchase_id=self.run["purchase_id"])
        self.receipt_path = self.directory / (self.run["id"] + "-receipt.json")
        self.receipt_path.write_text(canonical({"synthetic": True, "event": self.event}))
        self.refresh_policy()

    def test_spoofed_prior_plan_and_proposal_are_not_exempt(self):
        gate = HeldOutGate.for_run(self.store, self.run["id"])
        for key, value in (("prior_plans", [{"hypothesis": "response_loss"}]),
                           ("untrusted_observations", {"propose_fault": {"data": {"proposal": "response_loss"}}}),
                           ("available_evidence_ids", ["forged"])):
            context = gate._empty_context()
            context[key] = value
            with self.assertRaises(HeldOutError): gate.audit_context(context)
        self.assertEqual(self.calls, [])

    def test_actual_validated_fault_proposal_receipt_is_allowed_without_execution(self):
        def strategy(context):
            if not context["prior_plans"]:
                return plan(context, "propose_fault", arguments={"run_id": self.run["id"], "fault":
                    {"kind": "response_loss", "merchant": "defective", "delay_seconds": None}})
            return plan(context)
        self.strategy = strategy
        outcome = self.execute()
        self.assertEqual(outcome["status"], "COMPLETED", outcome)
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(self.contexts[-1]["untrusted_observations"]["propose_fault"]["data"]["executed"])
        self.assertEqual(self.store.get_run(self.run["id"])["fault"], {})

    def test_direct_model_transport_and_http_dispatch_cannot_bypass_required_policy(self):
        from crashcart.server import Handler
        handler = object.__new__(Handler)
        handler.server = SimpleNamespace(store=self.store)
        responses = []
        handler.send = lambda status, value: responses.append((status, value))
        os.environ.pop("CRASHCART_HELD_OUT_POLICY")
        handler.api_post("/api/runs/" + self.run["id"] + "/investigate", {})
        self.assert_rejected(responses[-1][1])
        with self.assertRaises(Exception) as caught:
            self.model.complete({"untrusted_promise": "opaque"})
        self.assertIn("HELD_OUT_", str(caught.exception))
        self.assertEqual(self.calls, [])

    def test_changed_projection_and_foreign_tool_identity_never_reach_next_request(self):
        original_tool = Investigation._tool
        for change in ("text", "purchase", "nested_key"):
            with self.subTest(change=change):
                if change != "text": self.setUp_next_run()
                before = len(self.calls)
                self.strategy = lambda context: plan(context, "read_browser" if change == "text" else "read_merchant")
                def altered(investigator, name, args, run, remaining, **kwargs):
                    result = original_tool(investigator, name, args, run, remaining, **kwargs)
                    if change == "text": result["observations"][0]["visible_text"] = "Different customer statement."
                    if change == "purchase": result["purchase_id"] = "foreign"
                    if change == "nested_key": result["extra"] = [{"expected_answer": "opaque"}]
                    return result
                with patch.object(Investigation, "_tool", altered):
                    outcome = self.execute()
                self.assert_rejected(outcome, sends=before + 1)
                events = self.store.get_events(self.run["id"])
                self.assertTrue(any(e["event_type"] == "held_out_rejected_observation" for e in events))

    def test_neutral_dashboard_and_source_path_are_rejected_even_if_reviewed(self):
        for change in ("dashboard", "source"):
            with self.subTest(change=change):
                if change != "dashboard": self.setUp_next_run()
                if change == "dashboard": self.event["payload"]["url_path"] = "/"
                else: self.event["payload"]["visible_text"] = "Please inspect crashcart/service.py"
                self.event["payload_json"] = canonical(self.event["payload"])
                with self.store.connect(write=True) as db:
                    db.execute("UPDATE events SET payload_json=? WHERE id=?", (self.event["payload_json"], self.event["id"]))
                self.receipt_path.write_text(canonical(self.event))
                self.refresh_policy()
                self.assert_rejected(self.execute())

    def test_trial_rejection_is_durable_and_changed_policy_cannot_reuse_run(self):
        original_request = Request
        def mutated(url, *, data, **kwargs):
            body = json.loads(data)
            body["metadata"] = {"expected_answer": "opaque"}
            return original_request(url, data=canonical(body).encode(), **kwargs)
        with patch.object(model_transport, "Request", side_effect=mutated):
            self.assert_rejected(self.execute())
        repeated = self.execute()
        self.assertEqual(repeated["reason"], "HELD_OUT_TRIAL_ALREADY_REJECTED")
        self.assertEqual(len([a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"]), 1)
        self.assertEqual(self.calls, [])

    def test_response_model_drift_preserves_usage_and_blocks_next_action(self):
        original = self.model.transport
        def wrong_identity(request, timeout):
            response = original(request, timeout)
            response["model"] = "unfrozen-model"
            return response
        self.model.transport = wrong_identity
        outcome = self.execute()
        self.assert_rejected(outcome, sends=1)
        result = [a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"][0]["result"]
        self.assertEqual(result["model"], "unfrozen-model")
        self.assertEqual(result["usage"]["total_tokens"], 15)
        self.assertNotIn("tool_exchange", result)

    def test_final_response_mutations_reject_finish_and_preserve_usage_and_trial_rejection(self):
        for mutation, reason in (("customer_receipt", "HELD_OUT_CUSTOMER_SOURCE_CHANGED"),
                                 ("policy_permissions", "HELD_OUT_POLICY_PERMISSIONS"),
                                 ("model_receipt", "HELD_OUT_MODEL_RECEIPT_CHANGED"),
                                 ("tool_receipt", "HELD_OUT_TOOL_RECEIPT_CHANGED")):
            with self.subTest(mutation=mutation):
                if mutation != "customer_receipt": self.setUp_next_run()
                self.store.update_purchase(self.run["purchase_id"], order_id="LOCALORDER")
                self.event["order_id"] = "LOCALORDER"
                with self.store.connect(write=True) as db:
                    db.execute("UPDATE events SET order_id=? WHERE id=?", ("LOCALORDER", self.event["id"]))
                original_receipt = canonical({"synthetic": True, "event": self.event})
                self.receipt_path.write_text(original_receipt)
                self.refresh_policy()
                sends_before = len(self.calls)
                def strategy(context):
                    for tool in ("read_provider", "read_merchant"):
                        if tool not in context["untrusted_observations"]:
                            return plan(context, tool)
                    if mutation == "customer_receipt": self.receipt_path.write_text("Changed during final model response")
                    if mutation == "policy_permissions": self.policy_path.chmod(0o600)
                    if mutation in {"model_receipt", "tool_receipt"}:
                        event_type = "model_plan" if mutation == "model_receipt" else "tool_observation"
                        event = next(e for e in self.store.get_events(self.run["id"]) if e["event_type"] == event_type)
                        payload = deepcopy(event["payload"])
                        payload["changed_during_http"] = True
                        with self.store.connect(write=True) as db:
                            db.execute("UPDATE events SET payload_json=? WHERE id=?", (canonical(payload), event["id"]))
                    return plan(context)
                self.strategy = strategy
                outcome = self.execute()
                self.assert_rejected(outcome, sends=sends_before + 3)
                self.assertEqual(outcome["reason"], reason)
                attempts = [a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"]
                self.assertEqual(len(attempts), 3)
                self.assertEqual(attempts[-1]["state"], "FAILED")
                self.assertEqual(attempts[-1]["result"]["usage"]["total_tokens"], 15)
                self.assertNotIn("plan", attempts[-1]["result"])
                self.assertNotIn("tool_exchange", attempts[-1]["result"])
                ended = [e for e in self.store.get_events(self.run["id"]) if e["event_type"] == "investigation_ended"]
                self.assertEqual(ended[-1]["payload"]["reason"], reason)
                # Restore the local fixture only to prove the durable rejection
                # still prevents another call; this trial is never reaccepted.
                self.policy_path.chmod(0o400)
                self.receipt_path.write_text(original_receipt)
                repeated = self.execute()
                self.assertEqual(repeated["reason"], "HELD_OUT_TRIAL_ALREADY_REJECTED")
                self.assertEqual(len(self.calls), sends_before + 3)

    def test_terminal_binding_recheck_rejects_post_response_mutation(self):
        original_remember = HeldOutGate.remember_plan
        def mutate_after_validated_response(gate, event_id, response):
            original_remember(gate, event_id, response)
            self.receipt_path.write_text("Changed after validated final response")
        with patch.object(HeldOutGate, "remember_plan", mutate_after_validated_response):
            outcome = self.execute()
        self.assert_rejected(outcome, sends=1)
        self.assertEqual(outcome["reason"], "HELD_OUT_CUSTOMER_SOURCE_CHANGED")
        self.assertEqual([a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"][0]["result"]["usage"]["total_tokens"], 15)

    def test_raw_http_helper_and_half_configured_mode_fail_closed(self):
        with self.assertRaises(model_transport.ModelTransportError) as caught:
            model_transport.http(Request("https://example.invalid", data=b"{}"), 1)
        self.assertEqual(caught.exception.code, "HELD_OUT_REQUEST_SCOPE_REQUIRED")
        os.environ.pop("CRASHCART_EVALUATION_MODE")
        self.assert_rejected(self.execute())
        self.assertEqual(self.calls, [])

    def test_cancellation_and_durable_budget_remain_inconclusive_without_reset(self):
        self.store.update_run(self.run["id"], cancel_requested=1)
        outcome = self.execute()
        self.assertEqual(outcome["status"], "CANCELLED")
        self.assertEqual(self.calls, [])
        with self.assertRaisesRegex(ValueError, "Cancellation cannot be cleared"):
            self.store.update_run(self.run["id"], cancel_requested=0)
        self.assertEqual(self.store.get_run(self.run["id"])["cancel_requested"], 1)
        # The independent call-budget scenario needs its own uncancelled fixture.
        self.setUp_next_run()
        self.strategy = lambda context: plan(context, "read_merchant")
        exhausted = self.execute()
        self.assertEqual(exhausted["status"], "BUDGET_EXHAUSTED", exhausted)
        self.assertEqual(len(self.calls), 4)
        repeated = self.execute()
        self.assertEqual(repeated["status"], "BUDGET_EXHAUSTED", repeated)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(repeated["final_verdict"]["verdict"], "INCONCLUSIVE")

    def test_clean_no_ticket_late_ticket_waiting_and_unknown_facts_unchanged(self):
        for case, signature in (("none", "paid_without_ticket"), ("waiting", "within_recovery_window"),
                                ("late", "ticket_delivered_late"), ("unknown", "missing_correlation_identity")):
            with self.subTest(case=case):
                if case != "none": self.setUp_next_run()
                captured = datetime.now(timezone.utc) - timedelta(seconds=30 if case == "waiting" else 90)
                capture_at = captured.isoformat()
                self.provider.order["purchase_units"][0]["payments"]["captures"][0]["update_time"] = capture_at
                if case != "unknown":
                    self.store.update_purchase(self.run["purchase_id"], order_id="LOCALORDER")
                    self.event["order_id"] = "LOCALORDER"
                    with self.store.connect(write=True) as db:
                        db.execute("UPDATE events SET order_id=? WHERE id=?", ("LOCALORDER", self.event["id"]))
                if case == "late":
                    self.store.confirm_payment(self.run["purchase_id"], order_id="LOCALORDER", capture_id="LOCALCAPTURE",
                        amount=2900, currency="USD", completed_at=capture_at, provider_response=self.provider.order)
                    with patch("crashcart.store.utcnow", return_value=(captured + timedelta(seconds=61)).isoformat()):
                        self.store.fulfill(self.run["purchase_id"])
                self.receipt_path.write_text(canonical({"synthetic": True, "event": self.event}))
                self.refresh_policy()
                self.strategy = lambda context: plan(context, next((tool for tool in ("read_provider", "read_merchant")
                    if tool not in context["untrusted_observations"]), "finish"))
                outcome = self.execute()
                self.assertEqual(outcome["status"], "COMPLETED", outcome)
                self.assertEqual(outcome["final_verdict"]["signature"], signature, outcome)
                if case == "unknown": self.assertEqual(self.provider.calls, 0)


if __name__ == "__main__":
    unittest.main()
