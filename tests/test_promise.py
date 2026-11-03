"""LOCAL_TEST hand-authored model proposals; not real language-model proof."""
from copy import deepcopy
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from crashcart.invariant import DEFAULT_INVARIANT, evaluate
from crashcart.paypal import inspect_capture
from crashcart.promise import (ADAPTER_FIELDS, CAPTURE_TIME_FIELD, MISSING_FIELDS_SCHEMA,
                               PROPOSED_INVARIANT_SCHEMA, PROPOSAL_VERSION, PromiseMappingError,
                               validate_promise_mapping, project_requested_values, VALUE_FIELDS, TRIGGERS)
from crashcart.store import Store


def proposal(**changes):
    value = {"version": PROPOSAL_VERSION, "amount_minor": 2900, "currency": "USD", "ticket_count": 1,
             "deadline_seconds": 60, "timing_trigger": "capture_completed", "delivery_kind": "ticket",
             "adapter_fields": {**ADAPTER_FIELDS, "timing_start": CAPTURE_TIME_FIELD}}
    value.update(changes)
    return value


def requested_values(**changes):
    value = {name: proposal()[name] for name in VALUE_FIELDS}
    value.update(changes)
    return value


class PromiseMappingTests(unittest.TestCase):
    def setUp(self):
        self.network = patch("socket.create_connection", side_effect=AssertionError("LOCAL_TEST has no network"))
        self.network_socket = patch("socket.socket", side_effect=AssertionError("LOCAL_TEST has no network"))
        self.network.start()
        self.network_socket.start()

    def tearDown(self):
        self.network_socket.stop()
        self.network.stop()

    def test_projection_preserves_every_semantic_value_and_derives_all_triggers(self):
        for trigger in (*TRIGGERS,None):
            for amount in (2900,3100,None):
                with self.subTest(trigger=trigger,amount=amount):
                    values=requested_values(timing_trigger=trigger,amount_minor=amount)
                    before=deepcopy(values);mapped=project_requested_values(values)
                    self.assertEqual(values,before)
                    self.assertEqual({k:mapped["proposed_invariant"][k] for k in VALUE_FIELDS},before)
                    self.assertEqual(mapped["proposed_invariant"]["adapter_fields"]["timing_start"],CAPTURE_TIME_FIELD if trigger=="capture_completed" else None)
                    self.assertEqual(mapped["missing_fields"],[k for k in VALUE_FIELDS if before[k] is None])
                    expected="unsupported" if amount==3100 or trigger not in (None,"capture_completed") else "ambiguous" if amount is None or trigger is None else "compatible"
                    self.assertEqual(mapped["promise_status"],expected)
                    self.assertFalse(mapped["execution_invariant_changed"])
                    mapped["proposed_invariant"]["amount_minor"]=17
                    self.assertEqual(values,before)
        for field in VALUE_FIELDS:
            values=requested_values(**{field:None});mapped=project_requested_values(values)
            self.assertEqual(mapped["missing_fields"],[field]);self.assertEqual(mapped["promise_status"],"ambiguous")
        all_missing=project_requested_values(dict.fromkeys(VALUE_FIELDS))
        self.assertEqual(all_missing["missing_fields"],list(VALUE_FIELDS))
        self.assertEqual(all_missing["promise_status"],"ambiguous")
        self.assertEqual(dict(DEFAULT_INVARIANT),{"version":"ticket-v1","amount":2900,"currency":"USD","ticket_count":1,"recovery_seconds":60})

    def test_projection_rejects_extra_missing_mistyped_and_out_of_bounds_values_without_coercion(self):
        cases=[[],{},True,{**requested_values(),"adapter_fields":{}},{k:v for k,v in requested_values().items() if k!="currency"}]
        cases += [requested_values(**{name:value}) for name in ("amount_minor","ticket_count","deadline_seconds")
                  for value in (True,False,1.0,"1",-1,1_000_000_001)]
        cases += [requested_values(currency=x) for x in ("usd",[],True,"USD ")]
        cases += [requested_values(timing_trigger="approved"),requested_values(delivery_kind="email_sent")]
        for value in cases:
            before=deepcopy(value)
            with self.subTest(value=value),self.assertRaises(PromiseMappingError):project_requested_values(value)
            self.assertEqual(value,before)

    def test_local_network_guard_rejects_connections_and_socket_creation(self):
        with self.assertRaises(AssertionError):
            socket.create_connection(("127.0.0.1", 9))
        with self.assertRaises(AssertionError):
            socket.socket()

    def test_two_meaningfully_different_promises_retain_distinct_proposals_without_changing_execution(self):
        # Explicit supplied proposals, not NLP extraction or real model output.
        cases = [
            ("USD 29.00 buys one workshop ticket within 60 seconds of completed capture.", proposal(), "compatible"),
            ("EUR 45.00 buys two workshop tickets within 120 seconds of buyer approval.",
             proposal(amount_minor=4500, currency="EUR", ticket_count=2, deadline_seconds=120,
                      timing_trigger="buyer_approval", adapter_fields={**ADAPTER_FIELDS, "timing_start": None}), "unsupported"),
        ]
        frozen = dict(DEFAULT_INVARIANT)
        records = [validate_promise_mapping(item, status, []) for _, item, status in cases]
        self.assertNotEqual(records[0]["proposed_invariant"], records[1]["proposed_invariant"])
        self.assertEqual(records[1]["unsupported_fields"], ["amount_minor", "currency", "ticket_count", "deadline_seconds", "timing_trigger"])
        self.assertEqual(dict(DEFAULT_INVARIANT), frozen)
        self.assertTrue(all(record["execution_invariant_changed"] is False for record in records))

    def test_ambiguous_promise_keeps_missing_information_null(self):
        # "Send my workshop ticket soon" does not specify price/currency/time.
        value = proposal(amount_minor=None, currency=None, ticket_count=None, deadline_seconds=None,
                         timing_trigger=None, adapter_fields={**ADAPTER_FIELDS, "timing_start": None})
        fields = ["amount_minor", "currency", "ticket_count", "deadline_seconds", "timing_trigger"]
        result = validate_promise_mapping(value, "ambiguous", fields)
        self.assertEqual(result["missing_fields"], fields)
        self.assertTrue(all(result["proposed_invariant"][key] is None for key in fields))

    def test_each_requested_value_change_is_descriptive_unsupported_only(self):
        for field, value in (("amount_minor", 3000), ("currency", "GBP"), ("ticket_count", 2),
                             ("deadline_seconds", 61), ("delivery_kind", "unsupported")):
            with self.subTest(field=field):
                result = validate_promise_mapping(proposal(**{field: value}), "unsupported", [])
                self.assertEqual(result["unsupported_fields"], [field])
                self.assertEqual(result["proposed_invariant"][field], value)

    def test_wrong_trigger_cannot_be_relabelled_as_capture_completion(self):
        for trigger in ("buyer_approval", "order_created", "checkout_return", "unsupported", None):
            value = proposal(timing_trigger=trigger)
            with self.subTest(trigger=trigger), self.assertRaisesRegex(PromiseMappingError, "TIMING_SEMANTICS"):
                validate_promise_mapping(value, "unsupported", [])
            value["adapter_fields"]["timing_start"] = None
            result = validate_promise_mapping(value, "ambiguous" if trigger is None else "unsupported",
                                             ["timing_trigger"] if trigger is None else [])
            self.assertIsNone(result["proposed_invariant"]["adapter_fields"]["timing_start"])

    def test_known_incompatibility_remains_unsupported_even_with_missing_information(self):
        value = proposal(currency="EUR", amount_minor=None)
        result = validate_promise_mapping(value, "unsupported", ["amount_minor"])
        self.assertEqual(result["unsupported_fields"], ["currency"])
        with self.assertRaisesRegex(PromiseMappingError, "STATUS"):
            validate_promise_mapping(value, "ambiguous", ["amount_minor"])

    def test_boolean_float_numeric_strings_and_out_of_bound_values_are_rejected(self):
        for field in ("amount_minor", "ticket_count", "deadline_seconds"):
            for value in (True, False, 1.0, "1", -1, 1_000_000_001):
                with self.subTest(field=field, value=value), self.assertRaises(PromiseMappingError):
                    validate_promise_mapping(proposal(**{field: value}), "unsupported", [])

    def test_malformed_currency_and_unknown_trigger_or_kind_are_rejected(self):
        for field, value in (("currency", "usd"), ("currency", "US"), ("currency", "USD "),
                             ("currency", True), ("currency", []), ("timing_trigger", "payment_started"),
                             ("delivery_kind", "email_sent")):
            with self.subTest(field=field, value=value), self.assertRaises(PromiseMappingError):
                validate_promise_mapping(proposal(**{field: value}), "unsupported", [])

    def test_unknown_currency_code_is_descriptive_unsupported_not_observed_support(self):
        value = proposal(currency="ZZZ", amount_minor=None)
        result = validate_promise_mapping(value, "unsupported", ["amount_minor"])
        self.assertEqual(result["unsupported_fields"], ["currency"])
        self.assertIsNone(result["proposed_invariant"]["amount_minor"])

    def test_unobservable_or_added_fields_are_rejected(self):
        for path in ("provider.email_sent", "merchant.shipment_arrived", "provider.approved_at", "merchant.tickets.created_at"):
            value = proposal()
            value["adapter_fields"]["delivered_at"] = path
            with self.subTest(path=path), self.assertRaisesRegex(PromiseMappingError, "UNOBSERVABLE"):
                validate_promise_mapping(value, "compatible", [])
        for target in ("root", "adapter"):
            value = proposal()
            (value if target == "root" else value["adapter_fields"])["email_sent"] = True
            with self.subTest(target=target), self.assertRaises(PromiseMappingError):
                validate_promise_mapping(value, "compatible", [])

    def test_compatible_classification_requires_all_exact_values_and_missing_list_is_exact(self):
        for value, status, missing in ((proposal(amount_minor=2901), "compatible", []),
                                       (proposal(currency=None), "compatible", ["currency"]),
                                       (proposal(), "ambiguous", []), (proposal(), "unsupported", []),
                                       (proposal(currency=None), "ambiguous", []),
                                       (proposal(currency=None), "ambiguous", ["currency", "currency"]),
                                       (proposal(), "compatible", ["email_sent"])):
            with self.subTest(status=status, missing=missing), self.assertRaises(PromiseMappingError):
                validate_promise_mapping(value, status, missing)

    def test_schema_required_fields_match_validator_and_cannot_set_verdict(self):
        value = proposal()
        self.assertEqual(set(PROPOSED_INVARIANT_SCHEMA["required"]), set(value))
        self.assertFalse(PROPOSED_INVARIANT_SCHEMA["additionalProperties"])
        self.assertNotIn("verdict", PROPOSED_INVARIANT_SCHEMA["properties"])
        self.assertEqual(set(MISSING_FIELDS_SCHEMA["items"]["enum"]), set(value) - {"version", "adapter_fields"})
        value["verdict"] = "PASS"
        with self.assertRaises(PromiseMappingError):
            validate_promise_mapping(value, "compatible", [])

    def test_returned_data_is_detached_and_active_invariant_stays_immutable(self):
        value = proposal()
        original = deepcopy(value)
        result = validate_promise_mapping(value, "compatible", [])
        result["proposed_invariant"]["amount_minor"] = 1
        result["proposed_invariant"]["adapter_fields"]["amount_minor"] = "changed"
        self.assertEqual(value, original)
        self.assertEqual(DEFAULT_INVARIANT["amount"], 2900)
        with self.assertRaises(TypeError):
            DEFAULT_INVARIANT["amount"] = 1
        with self.assertRaises(ValueError):
            evaluate(None, None, "2026-10-25T10:00:00Z", invariant=result["proposed_invariant"])

    def test_adapter_references_exist_in_actual_normalizer_and_store_outputs(self):
        with tempfile.TemporaryDirectory(prefix="crashcart-promise-test-") as tmp:
            store = Store(Path(tmp) / "state.sqlite3")
            run = store.create_run("Explicit LOCAL_TEST adapter check", mode="LOCAL_TEST")
            store.update_purchase(run["purchase_id"], order_id="LOCALORDER")
            order = {"id": "LOCALORDER", "intent": "CAPTURE", "status": "COMPLETED", "purchase_units": [{
                "reference_id": run["purchase_id"], "custom_id": run["purchase_id"],
                "amount": {"value": "29.00", "currency_code": "USD"}, "payments": {"captures": [{
                    "id": "LOCALCAPTURE", "status": "COMPLETED", "update_time": "2026-10-25T10:00:00Z",
                    "amount": {"value": "29.00", "currency_code": "USD"}, "final_capture": True,
                    "supplementary_data": {"related_ids": {"order_id": "LOCALORDER"}}}]}}]}
            payment = inspect_capture(order, "LOCALORDER", run["purchase_id"])
            # Matches the existing Investigation read_provider normalization.
            provider = {**payment, "capture_completed_at": payment["completed_at"]}
            store.confirm_payment(run["purchase_id"], order_id="LOCALORDER", capture_id="LOCALCAPTURE",
                                  amount=2900, currency="USD", completed_at=provider["capture_completed_at"], provider_response=order)
            store.fulfill(run["purchase_id"])
            merchant = store.merchant_state(run["purchase_id"])
            self.assertEqual(provider["amount"], 2900)
            self.assertEqual(provider["currency"], "USD")
            self.assertEqual(provider["capture_completed_at"], "2026-10-25T10:00:00Z")
            self.assertEqual(merchant["ticket_count"], 1)
            self.assertIsInstance(merchant["tickets"][0]["created_at"], str)


if __name__ == "__main__":
    unittest.main()
