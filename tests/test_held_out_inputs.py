"""LOCAL_TEST preparation only; no held-out seed or actual model invocation."""
from copy import deepcopy
import unittest

from scripts.verify_held_out_inputs import audit_context, run_preparation


class HeldOutPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = run_preparation()
        cls.cases = {case["name"]: case for case in cls.report["cases"]}

    def audit(self, context, case="healthy_delayed_delivery", **kwargs):
        record = self.cases[case]
        return audit_context(context, run_id=record["run_id"],
                             customer_event_ids={record["browser_event"]["id"]},
                             validated_prior_plans=kwargs.pop("validated_prior_plans", record["contexts"][-1]["prior_plans"][:len(context["prior_plans"])]), **kwargs)

    def test_actual_investigation_contexts_pass_clean_controls_without_network(self):
        self.assertEqual(self.report["result"], "PASS")
        self.assertEqual(self.report["network_attempts"], [])
        case = self.cases["healthy_delayed_delivery"]
        self.assertEqual(case["outcome"]["final_verdict"]["verdict"], "PASS")
        self.assertEqual(case["local_provider_reads"], 1)
        self.assertEqual(len(case["contexts"]), 4)
        self.assertEqual([len(context["untrusted_observations"]) for context in case["contexts"]], [0, 1, 2, 3])

    def test_waiting_and_missing_payment_do_not_become_false_failure_or_success(self):
        for name in ("healthy_waiting", "inadequate_payment_evidence"):
            self.assertEqual(self.cases[name]["outcome"]["final_verdict"]["verdict"], "INCONCLUSIVE")
        self.assertEqual(self.cases["inadequate_payment_evidence"]["local_provider_reads"], 0)
        self.assertEqual(self.cases["late_delivery_negative"]["outcome"]["final_verdict"]["signature"], "ticket_delivered_late")

    def test_dashboard_answer_rejected_before_another_injected_plan(self):
        case = self.cases["dashboard_answer_rejected"]
        self.assertEqual(case["outcome"]["reason"], "HELD_OUT_INPUT_REJECTED")
        self.assertEqual(case["injected_plans_returned"], 3)
        self.assertIn("Promise broken", case["contexts"][-1]["untrusted_observations"]["read_browser"]["data"]["observations"][0]["visible_text"])
        self.assertIn("Promise broken", case["browser_event"]["payload"]["visible_text"])
        self.assertTrue(case["browser_original_unchanged"])

    def test_fixture_hint_private_source_and_unreviewed_origin_are_rejected(self):
        for name in ("fixture_hint_rejected", "private_source_rejected", "unreviewed_customer_source_rejected"):
            with self.subTest(name=name):
                self.assertEqual(self.cases[name]["outcome"]["reason"], "HELD_OUT_INPUT_REJECTED")
                self.assertTrue(self.cases[name]["audits"][-1])

    def test_promise_answer_rejected_before_first_injected_plan_or_provider_read(self):
        case = self.cases["promise_answer_rejected"]
        self.assertEqual(case["injected_plans_returned"], 0)
        self.assertEqual(case["local_provider_reads"], 0)

    def test_nested_expected_answer_and_changed_deadline_are_rejected_without_editing(self):
        context = deepcopy(self.cases["healthy_delayed_delivery"]["contexts"][-1])
        context["untrusted_observations"]["read_merchant"]["data"]["expected_answer"] = "hidden"
        original = deepcopy(context)
        self.assertTrue(self.audit(context))
        self.assertEqual(context, original)
        context = deepcopy(self.cases["healthy_delayed_delivery"]["contexts"][0])
        context["invariant"]["recovery_seconds"] = 61
        self.assertTrue(self.audit(context))

    def test_unknown_top_level_fields_and_private_canaries_are_rejected(self):
        context = deepcopy(self.cases["healthy_delayed_delivery"]["contexts"][0])
        context["seed"] = "test-only"
        self.assertTrue(self.audit(context))
        context.pop("seed")
        context["untrusted_promise"] += " REVIEWER_ONLY_TEST_MARKER"
        self.assertTrue(self.audit(context, forbidden_values=("REVIEWER_ONLY_TEST_MARKER",)))

    def test_unlinked_prior_hypothesis_is_rejected_and_exact_validated_receipt_is_required(self):
        context = deepcopy(self.cases["healthy_delayed_delivery"]["contexts"][0])
        context["prior_plans"] = [{"hypothesis": "A response_loss experiment could test whether the promise is broken."}]
        self.assertTrue(self.audit(context))
        self.assertEqual(self.audit(context, validated_prior_plans=deepcopy(context["prior_plans"])), [])

    def test_external_keys_cannot_carry_private_markers_source_paths_or_fixture_clues(self):
        for marker in ("PUBLIC_TEST_CANARY", "crashcart/service.py", "response_loss", "Promise broken"):
            with self.subTest(marker=marker):
                context = deepcopy(self.cases["healthy_delayed_delivery"]["contexts"][-1])
                context["untrusted_observations"]["read_provider"]["data"][marker] = "ordinary value"
                original = deepcopy(context)
                self.assertTrue(self.audit(context, forbidden_values=("PUBLIC_TEST_CANARY", "crashcart/service.py")))
                self.assertEqual(context, original)

    def test_invariant_requires_exact_json_types_not_python_numeric_equality(self):
        for field, value in (("ticket_count", True), ("ticket_count", 1.0), ("amount", 2900.0),
                             ("recovery_seconds", 60.0), ("ticket_count", "1")):
            with self.subTest(field=field, value=value):
                context = deepcopy(self.cases["healthy_delayed_delivery"]["contexts"][0])
                context["invariant"][field] = value
                issues = self.audit(context)
                self.assertTrue(any(issue["path"] == "$.invariant" for issue in issues))

    def test_no_seed_selection_final_freeze_or_acceptance_is_claimed(self):
        self.assertFalse(self.report["held_out_seed_selected"])
        self.assertFalse(self.report["final_protocol_frozen"])
        self.assertEqual(self.report["requirements_accepted"], [])
        self.assertEqual(self.report["mode"], "LOCAL_TEST")


if __name__ == "__main__":
    unittest.main()
