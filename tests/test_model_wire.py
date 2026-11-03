"""Semantic wire projection and recorded rejection controls; no new model calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crashcart.invariant import DEFAULT_INVARIANT
from crashcart.investigator import (Investigation, InvestigationError, MODEL_PLAN_SCHEMA,
    MODEL_WIRE_VERSION, project_model_plan, validate_plan)
from crashcart.promise import PROJECTION_VERSION, VALUE_FIELDS
from crashcart.store import Store
from tests.test_investigator import LocalModel, plan
from tests.test_promise import requested_values


class ModelWireTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/"local.sqlite3")
        self.run=self.store.create_run("One workshop ticket soon",mode="LOCAL_TEST")
        blocker=patch("socket.socket",side_effect=AssertionError("No network in model wire tests"))
        blocker.start();self.addCleanup(blocker.stop)

    def execute(self,wire):
        model=LocalModel(lambda _:deepcopy(wire))
        result=Investigation(self.store,None,model_factory=lambda:model).run(self.run["id"])
        return result,[a for a in self.store.get_attempts(self.run["id"]) if a["kind"] == "investigator.model"][0]["result"]

    def test_model_schema_has_only_semantics_and_actions_with_nonempty_bounded_text(self):
        schema=MODEL_PLAN_SCHEMA
        self.assertEqual(set(schema["required"]),{"requested_values","hypothesis","tool","arguments","findings"})
        self.assertFalse(schema["additionalProperties"])
        values=schema["properties"]["requested_values"]
        self.assertEqual(set(values["required"]),set(VALUE_FIELDS));self.assertFalse(values["additionalProperties"])
        for name in ("hypothesis",):
            self.assertEqual((schema["properties"][name]["minLength"],schema["properties"][name]["maxLength"]),(1,1000))
        self.assertEqual(schema["properties"]["findings"]["maxItems"],8)
        claim=schema["properties"]["findings"]["items"]["properties"]["claim"]
        self.assertEqual((claim["minLength"],claim["maxLength"]),(1,1000))

    def test_projection_preserves_model_values_action_and_original_input(self):
        wire=plan({"run_id":self.run["id"]},"read_browser",requested_values=requested_values(
            amount_minor=None,currency="EUR",deadline_seconds=120,timing_trigger="buyer_approval"))
        original=deepcopy(wire)
        full=project_model_plan(wire,self.run,set())
        self.assertEqual(wire,original)
        for key in ("hypothesis","tool","arguments","findings"):self.assertEqual(full[key],wire[key])
        self.assertEqual({k:full["proposed_invariant"][k] for k in VALUE_FIELDS},wire["requested_values"])
        self.assertEqual(full["promise_status"],"unsupported");self.assertEqual(full["missing_fields"],["amount_minor"])
        self.assertIsNone(full["proposed_invariant"]["adapter_fields"]["timing_start"])
        self.assertEqual(self.store.get_run(self.run["id"])["invariant"],dict(DEFAULT_INVARIANT))
        full["arguments"]["run_id"]="changed"
        self.assertEqual(wire,original)

    def test_real_failed_old_plans_remain_failed_and_are_not_upgraded(self):
        expected={1:"INVALID_FAULT_PROPOSAL",3:"INVALID_FINDING",4:"INVALID_PROMISE_TIMING_SEMANTICS",5:"INVALID_PROMISE_TIMING_SEMANTICS"}
        for call,code in expected.items():
            with self.subTest(call=call):
                raw=json.loads((Path(__file__).parent/f"fixtures/model-call-{call:02}-invalid-plan.json").read_text())
                original=deepcopy(raw);run={"id":raw["arguments"]["run_id"],"fixture_id":"workshop-v1"}
                refs={ref for f in raw["findings"] for ref in f["evidence_ids"]}
                with self.assertRaisesRegex(InvestigationError,code):validate_plan(raw,run,refs)
                with self.assertRaisesRegex(InvestigationError,"INVALID_MODEL_WIRE_FIELDS"):project_model_plan(raw,run,refs)
                self.assertEqual(raw,original)

    def test_raw_sanitized_text_is_lossless_separate_and_bound_to_derived_plan(self):
        wire=plan({"run_id":self.run["id"]},requested_values=requested_values(
            amount_minor=None,currency=None,deadline_seconds=None,timing_trigger=None))
        wire["hypothesis"]="Missing request details, private test-secret-value."
        original=" "*5000+json.dumps(wire,indent=2)
        with patch.dict("os.environ",{"MODAL_API_KEY":"test-secret-value"}):
            result,saved=self.execute(original)
        sanitized=original.replace("test-secret-value","[REDACTED]")
        record=saved["wire_response"]
        self.assertEqual("".join(record["text_chunks"]),sanitized)
        self.assertEqual(record["sha256"],hashlib.sha256(sanitized.encode()).hexdigest())
        self.assertEqual(record["schema_version"],MODEL_WIRE_VERSION)
        self.assertEqual(record["characters"],len(sanitized))
        self.assertTrue(all(len(x)<=4000 for x in record["text_chunks"]))
        self.assertEqual(saved["projection"]["version"],PROJECTION_VERSION)
        self.assertEqual(saved["projection"]["input_wire_sha256"],record["sha256"])
        self.assertEqual(saved["plan"]["promise_status"],"ambiguous")
        self.assertEqual(saved["plan"]["missing_fields"],["amount_minor","currency","deadline_seconds","timing_trigger"])
        self.assertEqual(saved["plan"]["proposed_invariant"]["ticket_count"],1)
        self.assertEqual(saved["plan"]["proposed_invariant"]["delivery_kind"],"ticket")
        self.assertNotIn("test-secret-value",json.dumps(saved)+json.dumps(result))
        trace=next(e["payload"] for e in result["trace"] if e["kind"]=="model_wire")
        self.assertEqual(trace["sha256"],record["sha256"])
        self.assertEqual("".join(trace["text_chunks"]),sanitized)
        self.assertFalse(any(e["kind"]=="tool_observation" for e in result["trace"]))

    def test_invalid_action_retains_wire_but_never_repairs_or_dispatches(self):
        wire=plan({"run_id":self.run["id"]},"propose_fault")
        result,saved=self.execute(wire)
        self.assertEqual(result["reason"],"INVALID_FAULT_PROPOSAL")
        self.assertEqual(json.loads("".join(saved["wire_response"]["text_chunks"])),wire)
        self.assertNotIn("plan",saved);self.assertNotIn("projection",saved)
        self.assertFalse(any(e["kind"]=="tool_observation" for e in result["trace"]))

    def test_rejected_wire_values_and_text_bounds_are_retained_without_defaults(self):
        base=plan({"run_id":self.run["id"]})
        cases=[{**base,"promise_status":"compatible"},
               {**base,"requested_values":requested_values(amount_minor=True)},
               {**base,"requested_values":requested_values(ticket_count="one")},
               {**base,"requested_values":requested_values(deadline_seconds=86401)},
               {**base,"requested_values":{k:v for k,v in requested_values().items() if k!="currency"}},
               {**base,"hypothesis":""},{**base,"hypothesis":"x"*1001},
               {**base,"findings":[{"kind":"hypothesis","claim":"","evidence_ids":[]}]},
               {**base,"findings":[{"kind":"hypothesis","claim":"x"*1001,"evidence_ids":[]}]},
               {**base,"findings":[{"kind":"hypothesis","claim":"x","evidence_ids":[]}]*9}]
        for wire in cases:
            with self.subTest(wire=wire):
                self.run=self.store.create_run("Synthetic rejected wire",mode="LOCAL_TEST")
                wire["arguments"]={"run_id":self.run["id"],"fault":None}
                result,saved=self.execute(wire)
                self.assertEqual(result["status"],"FAILED")
                self.assertEqual(json.loads("".join(saved["wire_response"]["text_chunks"])),wire)
                self.assertNotIn("plan",saved)
                self.assertFalse(any(e["kind"]=="tool_observation" for e in result["trace"]))

    def test_oversized_injected_text_is_omitted_explicitly_and_rejected(self):
        result,saved=self.execute("x"*16001)
        self.assertEqual(result["reason"],"MALFORMED_STRUCTURED_OUTPUT")
        self.assertEqual(saved["wire_response"]["omitted"],"over_length_limit")
        self.assertEqual(saved["wire_response"]["characters"],16001)
        self.assertNotIn("text_chunks",saved["wire_response"])

if __name__=="__main__":unittest.main(verbosity=2)
