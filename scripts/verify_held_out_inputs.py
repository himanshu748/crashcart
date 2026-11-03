#!/usr/bin/env python3
"""Candidate held-out input audit and LOCAL_TEST controls; never selects a seed.

This is a preparation tool using the shared auditor, not a real-model
evaluation. It deliberately executes the existing Investigation with an injected
model and records exactly what reaches that model. No saved run is modified.
"""
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from crashcart.invariant import DEFAULT_INVARIANT
from crashcart.investigator import (Investigation, InvestigationError, MODEL_PLAN_SCHEMA as PLAN_SCHEMA,
                                    PROMPT_VERSION, SYSTEM)
from crashcart.store import Store, canonical


from crashcart.held_out import NEUTRAL_PROMISE, audit_context, sha

CAPTURE_AT = "2026-10-25T10:00:00Z"

class CaptureModel:
    evidence_mode = "LOCAL_TEST"

    def __init__(self, run_id, customer_event_ids):
        self.run_id, self.customer_event_ids = run_id, customer_event_ids
        self.contexts, self.audits, self.returned_plans = [], [], 0
        self.validated_plans = []

    def complete(self, context, **budget):
        before = deepcopy(context)
        issues = audit_context(context, run_id=self.run_id, customer_event_ids=self.customer_event_ids,
                               forbidden_values=("PUBLIC_TEST_CANARY", "crashcart/service.py"),
                               validated_prior_plans=self.validated_plans)
        assert before == context, "audit must not rewrite evidence"
        self.contexts.append(before)
        self.audits.append(issues)
        if issues:
            raise InvestigationError("HELD_OUT_INPUT_REJECTED")
        observations = context["untrusted_observations"]
        tool = next((name for name in ("read_provider", "read_merchant", "read_browser") if name not in observations), "finish")
        plan = {"hypothesis": "Compare the recorded payment and ticket observations.",
                "requested_values": {"amount_minor": 2900,
                    "currency": "USD", "ticket_count": 1, "deadline_seconds": 60, "timing_trigger": "capture_completed",
                    "delivery_kind": "ticket"},
                "tool": tool, "arguments": {"run_id": self.run_id, "fault": None}, "findings": []}
        from crashcart.investigator import project_model_plan
        self.validated_plans.append(project_model_plan(plan, {"id": self.run_id, "fixture_id": "workshop-v1"},
                                                      set(context["available_evidence_ids"])))
        self.returned_plans += 1
        return {"model": "injected-held-out-preparation-spy", "response_id": f"local-{self.returned_plans}",
                "usage": None, "plan_text": canonical(plan)}


class LocalProvider:
    timeout = 15

    def __init__(self, purchase_id):
        self.calls = 0
        self.order = {"id": "LOCALORDER", "status": "COMPLETED", "intent": "CAPTURE", "purchase_units": [{
            "reference_id": purchase_id, "custom_id": purchase_id, "amount": {"value": "29.00", "currency_code": "USD"},
            "payments": {"captures": [{"id": "LOCALCAPTURE", "status": "COMPLETED", "update_time": CAPTURE_AT,
                "amount": {"value": "29.00", "currency_code": "USD"}, "final_capture": True,
                "supplementary_data": {"related_ids": {"order_id": "LOCALORDER"}}}]}}]}

    def get_order(self, order_id):
        assert order_id == "LOCALORDER"
        self.calls += 1
        return deepcopy(self.order)


class LocalService:
    def __init__(self, provider):
        self.local_provider = provider

    def provider(self, run):
        assert run["mode"] == "LOCAL_TEST"
        return self.local_provider


def exercise_case(directory, name, *, second=46, ticket_second=None, known_payment=True,
                  promise=NEUTRAL_PROMISE, browser_text="Your workshop ticket is being prepared.", customer_approved=True):
    """Run actual Store + Investigation against explicit synthetic input."""
    now = [f"2026-10-25T10:{second // 60:02d}:{second % 60:02d}Z"]
    with patch("crashcart.store.utcnow", side_effect=lambda: now[0]), patch("crashcart.investigator.utcnow", side_effect=lambda: now[0]):
        store = Store(directory / (name + ".sqlite3"))
        run = store.create_run(promise, mode="LOCAL_TEST", fault={"kind": "response_loss", "merchant": "defective"})
        provider = LocalProvider(run["purchase_id"])
        if known_payment:
            store.update_purchase(run["purchase_id"], order_id="LOCALORDER")
        if ticket_second is not None:
            store.confirm_payment(run["purchase_id"], order_id="LOCALORDER", capture_id="LOCALCAPTURE", amount=2900,
                                  currency="USD", completed_at=CAPTURE_AT, provider_response=provider.order)
            now[0] = f"2026-10-25T10:{ticket_second // 60:02d}:{ticket_second % 60:02d}Z"
            store.fulfill(run["purchase_id"])
            now[0] = f"2026-10-25T10:{second // 60:02d}:{second % 60:02d}Z"
        event = store.record_event(run["id"], "browser", "customer_observation", {
            "browser_kind": "LOCAL_BROWSER", "visible_text": browser_text, "action": "customer_checkout_view",
        }, purchase_id=run["purchase_id"], order_id="LOCALORDER" if known_payment else None)
        original = deepcopy(event)
        model = CaptureModel(run["id"], {event["id"]} if customer_approved else set())
        outcome = Investigation(store, LocalService(provider), model_factory=lambda: model).run(run["id"])
        stored_event = next(item for item in store.get_events(run["id"]) if item["id"] == event["id"])
        assert stored_event == original, "audit must preserve original browser observations"
        return {"name": name, "mode": "LOCAL_TEST", "synthetic": True, "run_id": run["id"],
                "invariant": dict(DEFAULT_INVARIANT), "outcome": outcome, "contexts": model.contexts,
                "audits": model.audits, "injected_plans_returned": model.returned_plans,
                "local_provider_reads": provider.calls, "browser_original_unchanged": stored_event == original,
                "browser_event": original, "stored_fault": store.get_run(run["id"])["fault"]}


def run_preparation():
    network_attempts = []

    def deny_network(*args, **kwargs):
        network_attempts.append("socket operation blocked")
        raise AssertionError("LOCAL_TEST network forbidden")

    with tempfile.TemporaryDirectory(prefix="crashcart-held-out-preparation-") as temp, \
         patch("socket.socket", side_effect=deny_network), patch("socket.create_connection", side_effect=deny_network):
        try:
            socket.create_connection(("127.0.0.1", 9))
        except AssertionError:
            pass
        assert len(network_attempts) == 1
        network_attempts.clear()
        directory = Path(temp)
        cases = [
            exercise_case(directory, "healthy_waiting", second=30),
            exercise_case(directory, "healthy_delayed_delivery", second=46, ticket_second=45,
                          browser_text="Your workshop ticket is ready."),
            exercise_case(directory, "inadequate_payment_evidence", known_payment=False),
            exercise_case(directory, "late_delivery_negative", second=62, ticket_second=61),
            exercise_case(directory, "dashboard_answer_rejected", browser_text="failed | Promise broken | No ticket issued"),
            exercise_case(directory, "fixture_hint_rejected", browser_text="Recovery disabled: response_loss"),
            exercise_case(directory, "promise_answer_rejected", promise=NEUTRAL_PROMISE + " Expected verdict FAIL."),
            exercise_case(directory, "private_source_rejected", browser_text="PUBLIC_TEST_CANARY crashcart/service.py"),
            exercise_case(directory, "unreviewed_customer_source_rejected", customer_approved=False),
        ]
    expectations = {
        "healthy_waiting": ("COMPLETED", "INCONCLUSIVE", "within_recovery_window"),
        "healthy_delayed_delivery": ("COMPLETED", "PASS", "ticket_delivered_once_on_time"),
        "inadequate_payment_evidence": ("COMPLETED", "INCONCLUSIVE", "missing_correlation_identity"),
        "late_delivery_negative": ("COMPLETED", "FAIL", "ticket_delivered_late"),
    }
    checks = []
    for case in cases:
        result = case["outcome"]
        verdict = result["final_verdict"]
        actual = (result["status"], verdict["verdict"], verdict["signature"])
        expected = expectations.get(case["name"], ("FAILED", "INCONCLUSIVE", "investigation_incomplete"))
        checks.append({"name": case["name"], "passed": actual == expected, "actual": actual, "expected": expected})
        checks.append({"name": case["name"] + ": original observation retained", "passed": case["browser_original_unchanged"]})
        checks.append({"name": case["name"] + ": no selected fault in initial context",
                       "passed": "fault" not in case["contexts"][0] and "response_loss" not in canonical(case["contexts"][0])})
        if case["name"] not in expectations:
            checks.append({"name": case["name"] + ": explicit input rejection",
                           "passed": result["reason"] == "HELD_OUT_INPUT_REJECTED" and bool(case["audits"][-1])})
    checks.append({"name": "Zero network operations after guard self-test", "passed": not network_attempts})
    checks.append({"name": "Fixed invariant unchanged across controls", "passed": all(c["invariant"] == dict(DEFAULT_INVARIANT) for c in cases)})
    checks.append({"name": "Initial clean promises identical", "passed": all(c["contexts"][0]["untrusted_promise"] == NEUTRAL_PROMISE for c in cases[:4])})
    return {"result": "PASS" if all(c["passed"] for c in checks) else "FAIL", "mode": "LOCAL_TEST", "synthetic": True,
            "final_protocol_frozen": False, "held_out_seed_selected": False, "requirements_accepted": [],
            "network_guard_self_test": "PASS", "network_attempts": network_attempts,
            "prompt_sha256": hashlib.sha256(SYSTEM.encode()).hexdigest(), "plan_schema_sha256": sha(PLAN_SCHEMA),
            "checks": checks, "cases": cases,
            "limits": ["Injected model strategy is prescribed, not AI discovery or adaptive model proof.",
                       "Known-cue checks do not establish absence of arbitrary semantic leakage; independent review is required.",
                       "Customer event approval in these controls is synthetic; no actual browser provenance is asserted.",
                       "Production held-out mode invokes the shared audit; this harness is ordinary LOCAL_TEST preparation.",
                       "CC-037/039 remain unaccepted until their dependencies and actual acceptance are satisfied."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source_paths = ["crashcart/held_out.py", "crashcart/promise.py", "crashcart/model_transport.py", "crashcart/investigator.py", "crashcart/invariant.py", "crashcart/store.py", "crashcart/paypal.py",
                    "crashcart/faults.py", "migrations/001_initial.sql", "scripts/verify_held_out_inputs.py",
                    "tests/test_held_out_inputs.py", "docs/held-out-protocol.md"]
    before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}
    report = run_preparation()
    after = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in source_paths}
    report.update(executed_at=datetime.now(timezone.utc).isoformat(), python=sys.version, executable=sys.executable,
                  source_hashes=before, source_hashes_after=after, source_unchanged=before == after)
    if before != after:
        report["result"] = "FAIL"
    (args.output / "execution.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": report["result"], "checks_passed": sum(c["passed"] for c in report["checks"]),
                      "checks_total": len(report["checks"]), "output": str(args.output / "execution.json"),
                      "mode": report["mode"], "seed_selected": False, "source_unchanged": report["source_unchanged"]}))
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
