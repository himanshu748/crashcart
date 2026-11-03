"""Strictly offline replay. No network client or live-provider fallback is imported.

Recorded service observations drive the real Store entitlement rules and the
unchanged invariant. A source label is provenance metadata, not authentication.
Synthetic inputs remain LOCAL_TEST through replay, reduction and export.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import tempfile
import zipfile

from .invariant import DEFAULT_INVARIANT, evaluate


class ReplayError(ValueError):
    pass


WORKSPACE_IMPORT_VERSION = "replay-workspace-v1"
MAX_BYTES = 2_000_000
MAX_STEPS = 100
EVENTS = {
    "order_created": ("provider", "order_create"),
    "pre_capture_read": ("provider", "buyer_approval"),
    "capture_transport_response": ("harness", "capture"),
    "independent_order_read": ("provider", "reconcile"),
    "customer_observation": ("browser", "observe_browser"),
    "entitlement_read": ("merchant", "observe_merchant"),
    "fault_activated": ("harness", None),
    "process_exit_boundary": ("harness", None),
}
ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
HASH = re.compile(r"[0-9a-f]{64}")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (AttributeError, ValueError, TypeError):
        raise ReplayError("A timezone-aware fixed timestamp is required") from None


def keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ReplayError("Unsupported or missing package fields")


def identity(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise ReplayError("Invalid correlation identity")
    return value


def safe_relative(value):
    if not isinstance(value, str) or "\\" in value or ":" in value:
        raise ReplayError("Manifest paths must be relative POSIX paths")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(p in {".", ".."} or p.startswith(".") for p in path.parts):
        raise ReplayError("Unsafe manifest path")
    return value


def payment_snapshot(value):
    """Allowlist financial identity/state; discard links, payer, shipping and tokens."""
    if not isinstance(value, dict):
        raise ReplayError("Payment record must be an object")
    result = {}
    for key in ("id", "status", "intent", "reference_id", "custom_id", "create_time", "update_time"):
        if key in value:
            text = value[key]
            if not isinstance(text, str) or len(text) > 160:
                raise ReplayError("Invalid payment string")
            result[key] = text
    if "amount" in value:
        amount = value["amount"]
        if not isinstance(amount, dict) or any(not isinstance(amount.get(k), str) for k in ("value", "currency_code")):
            raise ReplayError("Malformed amount")
        result["amount"] = {k: amount[k] for k in ("value", "currency_code")}
    if "purchase_units" in value:
        if not isinstance(value["purchase_units"], list) or len(value["purchase_units"]) != 1:
            raise ReplayError("One owned purchase unit is required")
        result["purchase_units"] = [payment_snapshot(v) for v in value["purchase_units"]]
    if "payments" in value:
        payments = value["payments"]
        if not isinstance(payments, dict) or not isinstance(payments.get("captures"), list) or len(payments["captures"]) != 1:
            raise ReplayError("One recorded capture is required")
        result["payments"] = {"captures": [payment_snapshot(v) for v in payments["captures"]]}
    return result


def payment(order, source):
    if order.get("id") != source["order_id"] or order.get("intent") != "CAPTURE" or order.get("status") != "COMPLETED":
        raise ReplayError("A correlated completed CAPTURE order is required")
    try:
        unit = order["purchase_units"][0]
        capture = unit["payments"]["captures"][0]
        if unit["reference_id"] != source["purchase_id"] or unit["custom_id"] != source["purchase_id"]:
            raise ReplayError("Recorded purchase identity mismatch")
        for amount in (unit["amount"], capture["amount"]):
            if amount != {"currency_code": "USD", "value": "29.00"}:
                raise ReplayError("Recorded amount/currency must match frozen ticket-v1")
        if capture["status"] != "COMPLETED":
            raise ReplayError("Recorded capture is not completed")
        identity(capture["id"])
        timestamp(capture["update_time"])
        return {"capture_id": capture["id"], "completed_at": capture["update_time"]}
    except (KeyError, IndexError, TypeError):
        raise ReplayError("Incomplete captured-payment object") from None


def browser_snapshot(value):
    for name in ("url_path", "visible_text", "action", "browser_kind"):
        if not isinstance(value.get(name), str) or len(value[name]) > 4000:
            raise ReplayError("Actual bounded browser observation is required")
    if value["browser_kind"] not in {"LOCAL_BROWSER", "KERNEL"}:
        raise ReplayError("Unknown browser evidence mode")
    path = value["url_path"].split("?", 1)[0].split("#", 1)[0]
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        raise ReplayError("Browser path must be an application-relative URL path")
    def redact(text):
        text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[redacted-email]", text)
        return re.sub(r"(?i)(bearer|password|secret|access_token|api_key)\s*[:= ]\s*[^\s,;]+", r"\1 [redacted]", text)
    return {"url_path": path, "visible_text": redact(value["visible_text"]),
            "action": redact(value["action"]), "browser_kind": value["browser_kind"]}


def merchant_snapshot(value):
    required = {"run_id", "purchase_id", "order_id", "known", "ticket_count", "tickets", "observed_at"}
    if not isinstance(value, dict) or required - set(value):
        raise ReplayError("Actual merchant entitlement observation is required")
    result = {k: deepcopy(value[k]) for k in required}
    if value["known"] is not True or type(value["ticket_count"]) is not int or not 0 <= value["ticket_count"] <= 10:
        raise ReplayError("Known bounded merchant state is required")
    if not isinstance(value["tickets"], list) or len(value["tickets"]) != value["ticket_count"]:
        raise ReplayError("Ticket records and count must agree")
    result["tickets"] = [{k: ticket[k] for k in ("id", "purchase_id", "created_at")} for ticket in value["tickets"]]
    return result


def observation_time(record):
    # A merchant read observes state before the journal appends its envelope.
    # The envelope cannot extend the interval for which absent delivery is known.
    return record["payload"]["observed_at"] if record["event_type"] == "entitlement_read" else record["observed_at"]


def package_run(run, purchase, operations, events, source_hashes):
    """Convert Store/service observations to a sanitized package; no invented records."""
    # Imported workspace rows are projections. Export the sealed exact input
    # tape (including its selected/reduced steps), never reconstruct a new
    # provider execution from namespaced replay rows.
    imports = [event for event in events if event.get("source") == "replay" and event.get("event_type") == "replay_imported"]
    if imports:
        if len(imports) != 1 or run["mode"] not in {"LOCAL_TEST", "RECORDED_REPLAY"}:
            raise ReplayError("Ambiguous or invalid replay import provenance")
        receipt = imports[0].get("payload", {})
        if receipt.get("import_version") != WORKSPACE_IMPORT_VERSION:
            raise ReplayError("Unknown replay import provenance version")
        original = validate_package(receipt.get("source_package"))
        expected_mode = "LOCAL_TEST" if original["source"]["synthetic"] else "RECORDED_REPLAY"
        mapping = receipt.get("identity_mapping", {})
        if (digest(original) != receipt.get("input_sha256") or run["mode"] != expected_mode
                or mapping.get(original["source"]["run_id"]) != run["id"]
                or mapping.get(original["source"]["purchase_id"]) != purchase["id"]
                or mapping.get(original["source"]["order_id"]) != purchase["order_id"]):
            raise ReplayError("Sealed replay input hash, mode or namespace mismatch")
        return original
    source = {"mode": run["mode"], "synthetic": run["mode"] == "LOCAL_TEST", "run_id": run["id"],
              "purchase_id": purchase["id"], "order_id": purchase["order_id"], "hashes": source_hashes}
    tape = {"schema_version": 1, "source": source, "fixture_id": run["fixture_id"],
            "invariant": deepcopy(run["invariant"]), "fault": deepcopy(run["fault"]),
            "operations": [], "records": [], "steps": [], "evaluate_at": None}
    for operation in operations:
        if operation["semantic_key"] not in {"order.create", "order.capture"}:
            continue
        body = payment_snapshot(operation["body"]) if operation["semantic_key"] == "order.create" else deepcopy(operation["body"])
        tape["operations"].append({"kind": operation["semantic_key"], "request_id": operation["request_id"],
                                   "body": body, "original_body_sha256": digest(operation["body"]),
                                   "redacted_fields": sorted(set(operation["body"]) - set(body))})
    for event in events:
        kind = event["event_type"]
        if kind not in EVENTS:
            continue
        # Only APPROVED pre-capture reads can provide the approval prerequisite.
        if kind == "pre_capture_read" and event["payload"].get("status") != "APPROVED":
            continue
        payload = event["payload"]
        if kind in {"order_created", "pre_capture_read", "capture_transport_response", "independent_order_read"}:
            payload = payment_snapshot(payload)
        elif kind == "customer_observation":
            payload = browser_snapshot(payload)
        elif kind == "entitlement_read":
            payload = merchant_snapshot(payload)
        record = {k: event[k] for k in ("id", "source", "event_type", "run_id", "purchase_id", "order_id", "observed_at")}
        record["payload"] = deepcopy(payload)
        tape["records"].append(record)
        if EVENTS[kind][1]:
            tape["steps"].append({"id": event["id"], "kind": EVENTS[kind][1], "record_id": event["id"]})
    merchant_reads = [r for r in tape["records"] if r["event_type"] == "entitlement_read"]
    if merchant_reads:
        tape["evaluate_at"] = max((observation_time(r) for r in merchant_reads), key=timestamp)
        horizon = timestamp(tape["evaluate_at"])
        records = {r["id"]: r for r in tape["records"]}
        # Keep trailing browser observations in the source tape, but never advance
        # executable replay beyond the last actual merchant state observation.
        tape["steps"] = [s for s in tape["steps"]
                         if not (s["kind"] == "observe_browser"
                                 and timestamp(observation_time(records[s["record_id"]])) > horizon)]
    return validate_package(tape)


def validate_package(tape):
    if len(encoded(tape)) > MAX_BYTES:
        raise ReplayError("Replay package exceeds the bounded input size")
    keys(tape, {"schema_version", "source", "fixture_id", "invariant", "fault", "operations", "records", "steps", "evaluate_at"})
    if type(tape["schema_version"]) is not int or tape["schema_version"] != 1 or tape["fixture_id"] != "workshop-v1":
        raise ReplayError("Unsupported replay schema or fixture")
    if tape["invariant"] != dict(DEFAULT_INVARIANT) or any(type(tape["invariant"].get(k)) is not int for k in ("amount", "ticket_count", "recovery_seconds")):
        raise ReplayError("Replay cannot alter the frozen invariant")
    source = tape["source"]
    keys(source, {"mode", "synthetic", "run_id", "purchase_id", "order_id", "hashes"})
    if source["mode"] not in {"LOCAL_TEST", "LIVE_SANDBOX", "FRESH_SANDBOX"} or source["synthetic"] is not (source["mode"] == "LOCAL_TEST"):
        raise ReplayError("Synthetic provenance must remain LOCAL_TEST; replay is not new sandbox proof")
    for field in ("run_id", "purchase_id", "order_id"):
        identity(source[field])
    if not isinstance(source["hashes"], dict) or not source["hashes"]:
        raise ReplayError("Source hashes are required")
    for path, sha in source["hashes"].items():
        safe_relative(path)
        if not isinstance(sha, str) or not HASH.fullmatch(sha):
            raise ReplayError("Invalid source hash")
    keys(tape["fault"], {"kind", "merchant"})
    if tape["fault"]["kind"] not in {"response_loss", "process_interrupt"} or tape["fault"]["merchant"] != "defective":
        raise ReplayError("This reducer accepts only the recorded defective response-loss/interruption fixture")
    final = timestamp(tape["evaluate_at"])
    if not isinstance(tape["operations"], list) or len(tape["operations"]) != 2:
        raise ReplayError("Create and capture operation journals are required")
    operations = {}
    for op in tape["operations"]:
        keys(op, {"kind", "request_id", "body", "original_body_sha256", "redacted_fields"})
        if op["kind"] not in {"order.create", "order.capture"} or op["kind"] in operations:
            raise ReplayError("Exactly one operation of each kind is required")
        identity(op["request_id"])
        if not isinstance(op["original_body_sha256"], str) or not HASH.fullmatch(op["original_body_sha256"]):
            raise ReplayError("Original operation hash is required")
        if (not isinstance(op["redacted_fields"], list)
                or any(not isinstance(field, str) for field in op["redacted_fields"])
                or op["redacted_fields"] != sorted(set(op["redacted_fields"]))
                or set(op["redacted_fields"]) - {"payment_source", "description"}):
            raise ReplayError("Unsupported request redaction")
        if not op["redacted_fields"] and digest(op["body"]) != op["original_body_sha256"]:
            raise ReplayError("Unredacted operation body does not match its original hash")
        if op["kind"] == "order.capture" and (op["body"] != {} or op["redacted_fields"]):
            raise ReplayError("Only the recorded empty capture body is supported")
        if op["kind"] == "order.create":
            if payment_snapshot(op["body"]) != op["body"] or op["body"].get("intent") != "CAPTURE":
                raise ReplayError("Unsupported create request")
            try:
                unit = op["body"]["purchase_units"][0]
                if unit["reference_id"] != source["purchase_id"] or unit["custom_id"] != source["purchase_id"] or unit["amount"] != {"currency_code": "USD", "value": "29.00"}:
                    raise ReplayError("Create request does not match recorded purchase")
            except (KeyError, IndexError, TypeError):
                raise ReplayError("Create request missing purchase unit") from None
        operations[op["kind"]] = op
    if len({o["request_id"] for o in operations.values()}) != 2:
        raise ReplayError("Create and capture cannot share a request identity")
    if not isinstance(tape["records"], list) or not 1 <= len(tape["records"]) <= MAX_STEPS:
        raise ReplayError("Bounded observation tape required")
    records, seen = {}, set()
    captured = None
    last_record_at, order_seen = None, False
    for record in tape["records"]:
        keys(record, {"id", "source", "event_type", "run_id", "purchase_id", "order_id", "observed_at", "payload"})
        identity(record["id"])
        kind = record["event_type"]
        if record["id"] in records or kind not in EVENTS or record["source"] != EVENTS[kind][0]:
            raise ReplayError("Duplicate or unsupported source observation")
        pre_order_browser = kind == "customer_observation" and record["order_id"] is None and not order_seen
        if (any(record[k] != source[k] for k in ("run_id", "purchase_id"))
                or (record["order_id"] != source["order_id"] and not pre_order_browser)):
            raise ReplayError("Observation crosses source namespace")
        if kind == "order_created":
            order_seen = True
        observed = timestamp(record["observed_at"])
        if last_record_at is not None and observed < last_record_at:
            raise ReplayError("Source records must preserve their observation order")
        last_record_at = observed
        payload = record["payload"]
        if kind in {"order_created", "pre_capture_read", "capture_transport_response", "independent_order_read"}:
            if payment_snapshot(payload) != payload or payload.get("id") != source["order_id"]:
                raise ReplayError("Unsanitized or uncorrelated provider record")
            if kind == "pre_capture_read" and payload.get("status") != "APPROVED":
                raise ReplayError("Buyer approval was not observed")
            if kind in {"capture_transport_response", "independent_order_read"}:
                current = payment(payload, source)
                if timestamp(current["completed_at"]) > observed:
                    raise ReplayError("Capture observation precedes recorded completion")
                if captured and current != captured:
                    raise ReplayError("Capture and independent observation disagree")
                captured = current
        elif kind == "customer_observation":
            if browser_snapshot(payload) != payload:
                raise ReplayError("Browser observation requires sanitization")
        elif kind == "entitlement_read":
            if merchant_snapshot(payload) != payload or any(payload[k] != source[k] for k in ("run_id", "purchase_id", "order_id")):
                raise ReplayError("Merchant observation crosses namespace or contains extra fields")
            if timestamp(payload["observed_at"]) > observed:
                raise ReplayError("Merchant payload is newer than recorded observation")
            if payload["ticket_count"] != 0:
                raise ReplayError("Recorded defective missing-ticket witness must actually have zero tickets")
        elif kind == "fault_activated" and payload != tape["fault"]:
            raise ReplayError("Fault activation does not match frozen schedule")
        elif kind == "process_exit_boundary" and payload != {"exit_code": 86, "boundary": "after_capture_before_fulfillment"}:
            raise ReplayError("Unsupported interruption boundary")
        records[record["id"]], seen = record, seen | {kind}
    required = {"order_created", "pre_capture_read", "capture_transport_response", "independent_order_read", "customer_observation", "entitlement_read", "fault_activated"}
    if tape["fault"]["kind"] == "process_interrupt":
        required.add("process_exit_boundary")
    if required - seen:
        raise ReplayError("Missing actual source observations: " + ", ".join(sorted(required - seen)))
    horizon = max(timestamp(observation_time(r)) for r in records.values() if r["event_type"] == "entitlement_read")
    if final != horizon:
        raise ReplayError("Evaluation time must equal the captured merchant observation horizon")
    if any(r["event_type"] != "customer_observation" and timestamp(observation_time(r)) > horizon
           for r in records.values()):
        raise ReplayError("A later interaction requires another captured merchant observation")
    validate_fault_boundaries(tape)
    validate_steps(tape["steps"], records, horizon)
    return deepcopy(tape)


def validate_fault_boundaries(tape):
    indexed = {}
    for index, record in enumerate(tape["records"]):
        indexed.setdefault(record["event_type"], []).append((index, record))
    if len(indexed["fault_activated"]) != 1 or len(indexed["capture_transport_response"]) != 1:
        raise ReplayError("One activation and capture boundary are required")
    activation_index, activation = indexed["fault_activated"][0]
    capture_index, capture = indexed["capture_transport_response"][0]
    approvals = indexed["pre_capture_read"]
    if (not any(i < activation_index and timestamp(r["observed_at"]) <= timestamp(activation["observed_at"])
                for i, r in approvals)
            or activation_index >= capture_index
            or timestamp(activation["observed_at"]) > timestamp(capture["observed_at"])):
        raise ReplayError("Fault activation must follow approval and precede the capture response")
    interruptions = indexed.get("process_exit_boundary", [])
    if tape["fault"]["kind"] == "response_loss":
        if interruptions:
            raise ReplayError("Response loss cannot claim a process interruption boundary")
        return
    if len(interruptions) != 1:
        raise ReplayError("One recorded process interruption boundary is required")
    boundary_index, boundary = interruptions[0]
    if (boundary_index <= capture_index
            or timestamp(boundary["observed_at"]) < timestamp(capture["observed_at"])):
        raise ReplayError("Process interruption must follow the capture response")
    for kind in ("independent_order_read", "entitlement_read"):
        if any(i <= boundary_index or timestamp(observation_time(r)) < timestamp(boundary["observed_at"])
               for i, r in indexed[kind]):
            raise ReplayError("Process interruption must precede recovery and entitlement observations")


def validate_steps(steps, records, horizon):
    if not isinstance(steps, list) or not 3 <= len(steps) <= MAX_STEPS:
        raise ReplayError("Invalid replay step count")
    seen, prerequisite, last = set(), [], None
    for step in steps:
        keys(step, {"id", "kind", "record_id"})
        if step["id"] in seen or step["record_id"] not in records or step["id"] != step["record_id"]:
            raise ReplayError("Invalid step identity or absent tape interaction")
        record = records[step["record_id"]]
        if step["kind"] != EVENTS[record["event_type"]][1] or step["kind"] is None:
            raise ReplayError("Unsupported replay interaction; no live fallback")
        at = timestamp(observation_time(record))
        if at > horizon:
            raise ReplayError("Replay step exceeds the captured merchant observation horizon")
        if last is not None and at < last:
            raise ReplayError("Replay schedule must preserve observation order")
        last = at
        seen.add(step["id"])
        if step["kind"] in {"order_create", "buyer_approval", "capture"}:
            prerequisite.append(step["kind"])
        elif step["kind"] == "reconcile" and prerequisite != ["order_create", "buyer_approval", "capture"]:
            raise ReplayError("Reconciliation requires create, approval and capture")
    if prerequisite != ["order_create", "buyer_approval", "capture"]:
        raise ReplayError("Mandatory order_create, buyer_approval, capture prerequisites cannot be removed")


def _clocked_store(path, clock):
    # Isolate the Store module's clock without mutating shared process globals.
    spec = importlib.util.spec_from_file_location("_crashcart_replay_store", Path(__file__).with_name("store.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.utcnow = lambda: clock[0]
    return module.Store(path)


def replay(package, merchant="defective", steps=None, *, include_state=False):
    if type(include_state) is not bool:
        raise ReplayError("include_state must be boolean")
    tape = validate_package(package)
    if merchant not in {"defective", "healthy"}:
        raise ReplayError("Unknown merchant variant")
    selected = tape["steps"] if steps is None else steps
    records = {r["id"]: r for r in tape["records"]}
    validate_steps(selected, records, timestamp(tape["evaluate_at"]))
    mode = "LOCAL_TEST" if tape["source"]["synthetic"] else "RECORDED_REPLAY"
    clock = [records[selected[0]["record_id"]]["observed_at"]]
    trace, provider, restart_count, operation_mapping = [], None, 0, []
    with tempfile.TemporaryDirectory(prefix="crashcart-replay-") as directory:
        database = Path(directory) / "isolated.sqlite3"
        store = _clocked_store(database, clock)
        run = store.create_run("Recorded USD 29 workshop ticket promise", mode=mode,
                               fault={**tape["fault"], "merchant": merchant})
        purchase_id = run["purchase_id"]
        operations = {o["kind"]: o for o in tape["operations"]}
        for step in selected:
            record = records[step["record_id"]]
            clock[0] = observation_time(record)
            kind = step["kind"]
            if kind == "order_create":
                op = store.operation(purchase_id, "order.create", operations["order.create"]["body"])
                operation_mapping.append({"kind": "order.create", "source_request_id": operations["order.create"]["request_id"], "replay_request_id": op["request_id"]})
                store.update_operation(op["id"], state="COMPLETED", response=record["payload"])
                store.update_purchase(purchase_id, order_id=tape["source"]["order_id"], payment_state="AWAITING_APPROVAL")
            elif kind == "buyer_approval":
                store.update_purchase(purchase_id, payment_state="APPROVED")
            elif kind == "capture":
                op = store.operation(purchase_id, "order.capture", operations["order.capture"]["body"])
                operation_mapping.append({"kind": "order.capture", "source_request_id": operations["order.capture"]["request_id"], "replay_request_id": op["request_id"]})
                store.update_operation(op["id"], state="UNRESOLVED" if tape["fault"]["kind"] == "response_loss" else "IN_FLIGHT")
                store.update_purchase(purchase_id, payment_state="UNRESOLVED")
                if tape["fault"]["kind"] == "process_interrupt":
                    store = _clocked_store(database, clock)
                    restart_count += 1
            elif kind == "reconcile":
                evidence = payment(record["payload"], tape["source"])
                store.confirm_payment(purchase_id, order_id=tape["source"]["order_id"], capture_id=evidence["capture_id"],
                                      amount=2900, currency="USD", completed_at=evidence["completed_at"], provider_response=record["payload"])
                if merchant == "healthy":
                    store.fulfill(purchase_id)
                provider = {"run_id": run["id"], "purchase_id": purchase_id, "order_id": tape["source"]["order_id"],
                            "capture_id": evidence["capture_id"], "capture_completed_at": evidence["completed_at"],
                            "observed_at": clock[0], "confirmed": True, "status": "COMPLETED", "amount": 2900, "currency": "USD"}
            elif kind not in {"observe_browser", "observe_merchant"}:
                raise ReplayError("Unsupported interaction; no external fallback")
            actual = store.merchant_state(purchase_id)
            trace.append({"step_id": step["id"], "kind": kind, "at": clock[0], "ticket_count": actual["ticket_count"],
                          "payment_state": actual["payment_state"], "source_record": record["id"]})
            if include_state:
                trace[-1]["merchant_state"] = deepcopy(actual)
        clock[0] = tape["evaluate_at"]
        actual = store.merchant_state(purchase_id)
        verdict = evaluate(provider, actual, clock[0], tape["invariant"])
        for mapping in operation_mapping:
            operation = operations[mapping["kind"]]
            mapping["original_body_sha256"] = operation["original_body_sha256"]
            mapping["original_body_hash_status"] = "unverifiable_after_redaction" if operation["redacted_fields"] else "verified"
        horizon_record = max((r for r in records.values() if r["event_type"] == "entitlement_read"),
                             key=lambda r: timestamp(observation_time(r)))
        result = {**verdict, "mode": mode, "source_mode": tape["source"]["mode"], "merchant_variant": merchant,
                "source_authenticity": "not authenticated by replay; inspect original service evidence",
                "network_calls": 0, "ticket_count": actual["ticket_count"], "trace": trace, "store_reopens": restart_count,
                "input_sha256": digest(tape), "invariant": tape["invariant"], "fault": tape["fault"],
                "operation_mapping": operation_mapping,
                "evaluation": {"at": tape["evaluate_at"], "merchant_observation_id": horizon_record["id"]},
                "source_only_after_horizon": [r["id"] for r in records.values()
                    if timestamp(observation_time(r)) > timestamp(tape["evaluate_at"])],
                "namespace_mapping": {"source_run": tape["source"]["run_id"], "replay_run": run["id"],
                                      "source_purchase": tape["source"]["purchase_id"], "replay_purchase": purchase_id}}
        if include_state:
            # Only state actually produced by the offline engine is importable.
            # Raw SQLite columns avoid silently reconstructing financial rows.
            with store.connect() as db:
                result["execution_state"] = {table: [dict(row) for row in db.execute("SELECT * FROM " + table)]
                    for table in ("runs", "purchases", "operations", "tickets")}
        return result


def reduce_package(package, max_candidates=16, repeats=3):
    tape = validate_package(package)
    if type(max_candidates) is not int or not 1 <= max_candidates <= 100 or type(repeats) is not int or not 2 <= repeats <= 10:
        raise ReplayError("Bounded candidates (1..100) and repeats (2..10) required")
    original = replay(tape)
    if original["signature"] != "paid_without_ticket":
        raise ReplayError("Original replay does not exhibit the claimed paid_without_ticket failure")
    best, candidates = list(tape["steps"]), []
    for step in list(tape["steps"]):
        if len(candidates) >= max_candidates:
            break
        candidate = [s for s in best if s["id"] != step["id"]]
        executed = False
        try:
            outcome = replay(tape, steps=candidate)
            executed = True
            accepted = outcome["signature"] == "paid_without_ticket" and outcome["verdict"] == "FAIL"
            reason = outcome["signature"]
        except ReplayError as exc:
            accepted, reason = False, str(exc)
        candidates.append({"removed_step": step["id"], "kind": step["kind"], "accepted": accepted, "executed": executed, "result": reason,
                           "remaining_size": len(candidate)})
        if accepted:
            best = candidate
    repeated = [replay(tape, steps=best) for _ in range(repeats)]
    signatures = [result["signature"] for result in repeated]
    reduced = deepcopy(tape)
    reduced["steps"] = best
    return {"mode": original["mode"], "description": "smallest reproducer found within the search",
            "original_size": len(tape["steps"]), "reduced_size": len(best), "budget": max_candidates,
            "candidates_attempted": len(candidates), "candidates_executed": sum(c["executed"] for c in candidates),
            "candidates": candidates, "repeat_count": repeats,
            "repeat_signatures": signatures, "repeatable": len(set(signatures)) == 1 and signatures[0] == "paid_without_ticket",
            "termination_reason": "budget_exhausted" if len(candidates) < len(tape["steps"]) else "single_deletion_pass_complete",
            "package": reduced}


def load_package(path):
    data = Path(path).read_bytes()
    if len(data) > MAX_BYTES:
        raise ReplayError("Replay input too large")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ReplayError("Duplicate JSON keys are forbidden")
            result[key] = value
        return result
    return validate_package(json.loads(data, object_pairs_hook=unique))


def export_package(package, destination):
    tape = validate_package(package)
    target = Path(destination)
    if target.exists():
        raise ReplayError("Export destination already exists")
    root = Path(__file__).resolve().parents[1]
    files = {"input.json": json.dumps(tape, indent=2).encode(), "crashcart/__init__.py": b""}
    for path in ("crashcart/replay.py", "crashcart/store.py", "crashcart/invariant.py", "migrations/001_initial.sql"):
        files[path] = (root / path).read_bytes()
    mode = "LOCAL_TEST" if tape["source"]["synthetic"] else "RECORDED_REPLAY"
    files["README.md"] = (f"# CrashCart offline regression\n\nMode: {mode}. Source mode: {tape['source']['mode']}.\n"
        "Python 3.11+ and its standard library only. No credentials, installation, or network access are needed.\n\n"
        "Run from the extracted folder:\n\n"
        "    python3 -m crashcart.replay verify-manifest .\n"
        "    python3 -m crashcart.replay run input.json --merchant defective\n"
        "    python3 -m crashcart.replay run input.json --merchant healthy\n"
        "    python3 -m crashcart.replay reduce input.json --budget 16 --repeats 3\n\n"
        "Exit codes: PASS=0, invariant FAIL=1, INCONCLUSIVE=2, invalid package=3.\n"
        "The defective regression must fail specifically with paid_without_ticket. The healthy variant uses the SAME input, clock, fault and invariant; it passes only if recorded reconciliation occurs within 60 seconds.\n"
        "A new SQLite namespace re-executes Store confirmation/fulfillment and the invariant. Saved verdicts are not inputs. Process interruption is simulated by reopening persisted Store state, not killing an OS process.\n"
        "This artifact makes no fresh-sandbox claim. Source labels/hashes do not authenticate the original observations. A fresh sandbox run requires new approval and provider evidence outside this offline program. Browser recordings are external original evidence; this package carries sanitized observations, not a fabricated recording.\n").encode()
    files["manifest.json"] = json.dumps({"schema_version": 1, "mode": mode,
        "files": {name: hashlib.sha256(content).hexdigest() for name, content in files.items()}}, indent=2).encode()
    with zipfile.ZipFile(target, "x", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return {"path": str(target), "mode": mode, "files": len(files), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}


def verify_manifest(directory):
    root = Path(directory).resolve()
    manifest = json.loads((root / "manifest.json").read_text())
    keys(manifest, {"schema_version", "mode", "files"})
    if manifest["schema_version"] != 1 or manifest["mode"] not in {"LOCAL_TEST", "RECORDED_REPLAY"} or not isinstance(manifest["files"], dict):
        raise ReplayError("Invalid export manifest")
    required = {"input.json", "README.md", "crashcart/__init__.py", "crashcart/replay.py", "crashcart/store.py",
                "crashcart/invariant.py", "migrations/001_initial.sql"}
    if set(manifest["files"]) != required:
        raise ReplayError("Manifest must cover every required export member")
    for name, expected in manifest["files"].items():
        path = root / safe_relative(name)
        if path.is_symlink() or not path.is_file() or root not in path.resolve().parents or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ReplayError("Missing or changed export member: " + name)
    tape = load_package(root / "input.json")
    if manifest["mode"] != ("LOCAL_TEST" if tape["source"]["synthetic"] else "RECORDED_REPLAY"):
        raise ReplayError("Manifest proof mode does not match source tape")
    return {"result": "PASS", "files_checked": len(manifest["files"]), "mode": manifest["mode"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("input")
    run.add_argument("--merchant", choices=("defective", "healthy"), default="defective")
    reduction = sub.add_parser("reduce")
    reduction.add_argument("input")
    reduction.add_argument("--budget", type=int, default=16)
    reduction.add_argument("--repeats", type=int, default=3)
    export = sub.add_parser("export")
    export.add_argument("input")
    export.add_argument("destination")
    verify = sub.add_parser("verify-manifest")
    verify.add_argument("directory")
    args = parser.parse_args(argv)
    try:
        if args.action == "verify-manifest":
            result = verify_manifest(args.directory)
        else:
            tape = load_package(args.input)
            if args.action == "run":
                result = replay(tape, args.merchant)
            elif args.action == "reduce":
                result = reduce_package(tape, args.budget, args.repeats)
            else:
                result = export_package(tape, args.destination)
        print(json.dumps(result, indent=2))
        return {"PASS": 0, "FAIL": 1, "INCONCLUSIVE": 2}.get(result.get("verdict"), 0)
    except (ReplayError, ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"error": "INVALID_REPLAY", "reason": str(exc)}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
