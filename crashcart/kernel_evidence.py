"""Import a reviewed prior KERNEL execution without any network or payment action.

The explicit local manifest is an operator attestation, not a provider signature.
Hashes bind reviewed bytes; they do not independently prove provider execution.
Never expose this importer as a client observation endpoint.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from .store import canonical, utcnow


AUTHORITY = "LOCAL_OPERATOR_REVIEWED_ARTIFACT"
EVENT_TYPE = "kernel_recorded_observation"
MAX_JSON = 2 * 1024 * 1024
MAX_VIDEO = 64 * 1024 * 1024
SCENARIO_PATHS = {"observe": "/shop", "checkout": "/checkoutnow",
                  "confirm_return": "/return", "cancel_return": "/cancel"}


class KernelEvidenceError(ValueError):
    """Fixed codes only: artifact paths and private content never enter errors."""


def require(condition, code):
    if not condition:
        raise KernelEvidenceError(code)


def exact_keys(value, required, optional=()):
    require(isinstance(value, dict) and required <= value.keys() and
            value.keys() <= required | set(optional), "INVALID_SCHEMA")


def identifier(value, prefix=None):
    pattern = prefix + r"_[a-f0-9]{32}" if prefix else r"[A-Za-z0-9_-]{1,128}"
    require(isinstance(value, str) and re.fullmatch(pattern, value), "INVALID_IDENTITY")
    return value


def timestamp(value):
    try:
        require(isinstance(value, str) and len(value) <= 40, "INVALID_TIMESTAMP")
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(result.utcoffset() is not None, "INVALID_TIMESTAMP")
        return result
    except (TypeError, ValueError):
        raise KernelEvidenceError("INVALID_TIMESTAMP") from None


def sha(value):
    require(isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value), "INVALID_HASH")
    return value


def contained(root, relative, *, directory=False):
    require(isinstance(relative, str) and 0 < len(relative) <= 512 and
            not any(c in relative for c in ("\\", ":", "\x00")), "INVALID_ARTIFACT_PATH")
    part = Path(relative)
    require(not part.is_absolute() and all(p not in (".", "..") for p in relative.split("/")) and
            all(relative.split("/")), "INVALID_ARTIFACT_PATH")
    path = root
    for segment in part.parts:
        path = path / segment
        require(not path.is_symlink(), "ARTIFACT_ALIAS_REJECTED")
    require(path.resolve().is_relative_to(root), "ARTIFACT_SCOPE_MISMATCH")
    require(path.is_dir() if directory else path.is_file(), "ARTIFACT_UNAVAILABLE")
    return path


def read_artifact(path, *, maximum, expected=None, json_content=False):
    """Bounded read from a regular, unaliased file; no path reaches diagnostics."""
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as file:
            before = os.fstat(file.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "ARTIFACT_ALIAS_REJECTED")
            require(0 < before.st_size <= maximum, "ARTIFACT_SIZE_INVALID")
            digest = hashlib.sha256(); chunks = []; total = 0; header = b""
            while chunk := file.read(1024 * 1024):
                total += len(chunk); require(total <= maximum, "ARTIFACT_SIZE_INVALID")
                if not header: header = chunk[:12]
                digest.update(chunk)
                if json_content: chunks.append(chunk)
            after = os.fstat(file.fileno())
            require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                    (after.st_size, after.st_mtime_ns, after.st_ino) and total == before.st_size,
                    "ARTIFACT_CHANGED_DURING_READ")
        actual = digest.hexdigest()
        if expected is not None: require(actual == sha(expected), "ARTIFACT_HASH_MISMATCH")
        value = json.loads(b"".join(chunks)) if json_content else None
        return value, actual, total, header
    except KernelEvidenceError:
        raise
    except (OSError, ValueError, UnicodeError):
        raise KernelEvidenceError("ARTIFACT_UNREADABLE") from None


def safe_message(value):
    require(isinstance(value, str) and len(value) <= 4000, "INVALID_BROWSER_TEXT")
    cleaned = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+|eyJ[A-Za-z0-9_.-]+", "[redacted]", value)
    cleaned = re.sub(r"(?i)(bearer|password|secret|access_token|api_key)\s*[:= ]\s*[^\s,;]+", r"\1 [redacted]", cleaned)
    return cleaned


def load_reviewed_bundle(manifest_path, artifact_root):
    root = Path(artifact_root).absolute()
    require(root.is_dir() and not root.is_symlink() and root == root.resolve(), "INVALID_ARTIFACT_ROOT")
    manifest_path = Path(manifest_path).absolute()
    require(manifest_path.is_relative_to(root), "MANIFEST_SCOPE_MISMATCH")
    manifest_path = contained(root, manifest_path.relative_to(root).as_posix())
    manifest, manifest_hash, _, _ = read_artifact(manifest_path, maximum=MAX_JSON, json_content=True)
    exact_keys(manifest, {"schema_version", "authority", "review_id", "reviewed_at", "identity", "artifacts", "source_snapshot"}, {"browser_projection"})
    projection = manifest.get("browser_projection", "message-v1")
    require(isinstance(projection, str) and projection in {"message-v1", "captured-fields-v2", "execution-fields-v3"}, "UNKNOWN_BROWSER_PROJECTION")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == 1 and
            manifest["authority"] == AUTHORITY, "OPERATOR_REVIEW_REQUIRED")
    identifier(manifest["review_id"]); reviewed = timestamp(manifest["reviewed_at"])
    require(reviewed <= datetime.now(timezone.utc), "REVIEW_TIME_INVALID")
    identity = manifest["identity"]
    exact_keys(identity, {"run_id", "purchase_id", "source_mode", "session_id", "replay_id", "session_name", "allowance_id"})
    for field in ("session_id", "replay_id", "session_name", "allowance_id"): identifier(identity[field])
    identifier(identity["run_id"], "run"); identifier(identity["purchase_id"], "purchase")
    require(identity["source_mode"] in {"LOCAL_TEST", "LIVE_SANDBOX", "FRESH_SANDBOX"}, "INVALID_SOURCE_MODE")
    artifacts = manifest["artifacts"]
    exact_keys(artifacts, {"receipt", "video", "reservation", "source_freeze"})
    loaded = {}; references = {"manifest": (manifest_path, manifest_hash)}
    for kind, spec in artifacts.items():
        exact_keys(spec, {"path", "sha256", "bytes"} if kind == "video" else {"path", "sha256"})
        path = contained(root, spec["path"])
        value, digest, size, header = read_artifact(path, maximum=MAX_VIDEO if kind == "video" else MAX_JSON,
                                                  expected=spec["sha256"], json_content=kind != "video")
        if kind == "video":
            require(type(spec["bytes"]) is int and spec["bytes"] == size and header[4:8] == b"ftyp", "RECORDING_MISMATCH")
        loaded[kind] = value; references[kind] = (path, digest)
    require(len({str(p) for p, _ in references.values()}) == len(references), "ARTIFACT_ALIAS_REJECTED")
    freeze = loaded["source_freeze"]
    require(isinstance(freeze, dict) and freeze.get("run_id") == identity["run_id"] and
            isinstance(freeze.get("source_hashes"), dict) and 1 <= len(freeze["source_hashes"]) <= 200 and
            "crashcart/kernel_browser.py" in freeze["source_hashes"], "SOURCE_FREEZE_MISMATCH")
    snapshot = contained(root, manifest["source_snapshot"], directory=True)
    for relative, expected in freeze["source_hashes"].items():
        read_artifact(contained(snapshot, relative), maximum=8 * MAX_JSON, expected=expected)
    receipt, reservation = loaded["receipt"], loaded["reservation"]
    validate_receipt(receipt, reservation, identity, artifacts["video"], reviewed)
    return {"manifest": manifest, "manifest_sha256": manifest_hash, "receipt": receipt,
            "references": references, "receipt_sha256": artifacts["receipt"]["sha256"]}


def validate_receipt(receipt, reservation, identity, video, reviewed):
    required = {"schema_version", "browser_kind", "mode", "identity", "observations", "cleanup", "status",
                "recording_state", "payment_verdict", "started_at", "finished_at", "allowance_id",
                "session_name", "session_id", "replay_id", "recording"}
    exact_keys(receipt, required, {"error", "orchestration_error", "approved_window_origin",
                                 "cumulative_credit_ceiling_usd", "exact_credit_usage_readback"})
    require(type(receipt["schema_version"]) is int and receipt["schema_version"] == 1 and
            receipt["browser_kind"] == "KERNEL" and receipt["mode"] == identity["source_mode"], "RECEIPT_MODE_MISMATCH")
    for key in ("session_id", "replay_id", "session_name", "allowance_id"):
        require(receipt[key] == identity[key], "RECEIPT_IDENTITY_MISMATCH")
    require(receipt["payment_verdict"] == "NOT_EVALUATED", "BROWSER_CANNOT_DECLARE_PAYMENT")
    require(receipt["status"] in {"OBSERVED", "INCOMPLETE", "FAILED", "CANCELLED", "TIMED_OUT"} and
            receipt["recording_state"] in {"SAVED", "SAVED_PARTIAL"}, "CLOSED_RECORDING_REQUIRED")
    started, finished = timestamp(receipt["started_at"]), timestamp(receipt["finished_at"])
    require(started <= finished <= reviewed, "RECEIPT_TIME_MISMATCH")
    recorded = receipt["recording"]
    exact_keys(recorded, {"sha256", "bytes", "public_review"}, {"private_path"})
    require(recorded["sha256"] == video["sha256"] and type(recorded["bytes"]) is int and
            recorded["bytes"] == video["bytes"] and recorded["public_review"] == "NOT_REVIEWED", "RECORDING_MISMATCH")
    exact_keys(receipt["cleanup"], {"recording_stop", "recording_download", "session_delete"})
    require(all(isinstance(v, str) and len(v) <= 128 for v in receipt["cleanup"].values()) and
            receipt["cleanup"]["recording_download"] == "SUCCEEDED", "RECORDING_UNAVAILABLE")
    original = receipt["identity"]
    exact_keys(original, {"run_id", "purchase_id", "order_id", "mode"})
    require(all(original[k] == identity[k] for k in ("run_id", "purchase_id")) and
            original["mode"] in {"LIVE_SANDBOX", "FRESH_SANDBOX"} and
            (receipt["mode"] == "LOCAL_TEST" or original["mode"] == receipt["mode"]), "RECEIPT_IDENTITY_MISMATCH")
    if original["order_id"] is not None: identifier(original["order_id"])
    exact_keys(reservation, {"grant", "identity", "session_name", "reserved_at"})
    exact_keys(reservation["identity"], {"run_id", "purchase_id", "order_id", "mode"})
    require(reservation["session_name"] == identity["session_name"] and
            all(reservation["identity"][k] == original[k] for k in ("run_id", "purchase_id", "mode")) and
            reservation["identity"]["order_id"] in (None, original["order_id"]), "RESERVATION_IDENTITY_MISMATCH")
    grant = reservation["grant"]
    exact_keys(grant, {"approval_id", "owned_origin", "expires_at", "max_session_seconds", "scenarios"})
    require(grant["approval_id"] == identity["allowance_id"] and type(grant["max_session_seconds"]) is int and
            10 <= grant["max_session_seconds"] <= 300 and isinstance(grant["scenarios"], list) and
            grant["scenarios"] and all(s in SCENARIO_PATHS for s in grant["scenarios"]), "RESERVATION_SCOPE_MISMATCH")
    require(isinstance(grant["owned_origin"], str) and re.fullmatch(r"https://[a-z0-9-]+(?:\.[a-z0-9-]+)+", grant["owned_origin"]), "RESERVATION_ORIGIN_INVALID")
    require(timestamp(reservation["reserved_at"]) <= started < timestamp(grant["expires_at"]), "RESERVATION_TIME_MISMATCH")
    if "approved_window_origin" in receipt:
        require(receipt["approved_window_origin"] == grant["owned_origin"], "RESERVATION_ORIGIN_MISMATCH")
    observations = receipt["observations"]
    require(isinstance(observations, list) and 1 <= len(observations) <= 64, "INVALID_OBSERVATIONS")
    for observation in observations:
        exact_keys(observation, {"run_id", "purchase_id", "order_id", "ticket_id", "observed_at", "path",
                                "scenario", "received_at", "session_id", "replay_id"},
                   {"run_state", "provider_title", "merchant_title", "message", "verdict"})
        require(all(observation[k] == identity[k] for k in ("run_id", "purchase_id", "session_id", "replay_id")), "OBSERVATION_IDENTITY_MISMATCH")
        require(observation["scenario"] in grant["scenarios"] and
                observation["path"] == SCENARIO_PATHS.get(observation["scenario"]), "OBSERVATION_PATH_MISMATCH")
        if observation["order_id"] is not None:
            identifier(observation["order_id"])
            require(observation["order_id"] == original["order_id"], "OBSERVATION_ORDER_MISMATCH")
        if observation["scenario"] != "observe": require(observation["order_id"] is not None, "OBSERVATION_ORDER_REQUIRED")
        if observation["ticket_id"] is not None: identifier(observation["ticket_id"], "ticket")
        timestamp(observation["observed_at"])
        require(started <= timestamp(observation["received_at"]) <= finished, "ADAPTER_TIME_MISMATCH")
        for field in ("run_state", "provider_title", "merchant_title", "message", "verdict"):
            require(isinstance(observation.get(field, ""), str) and len(observation.get(field, "")) <= 4000, "INVALID_BROWSER_TEXT")


def event_payload(bundle, observation, index, imported_at):
    receipt = bundle["receipt"]; identity = bundle["manifest"]["identity"]
    message = observation.get("message", ""); visible = safe_message(message)
    payload = {"browser_kind": "KERNEL", "action": observation["scenario"], "url_path": observation["path"],
            "visible_text": visible, "visible_text_available": bool(message), "visible_text_redacted": visible != message,
            "provenance": "PRIOR_LOCAL_TEST_EXECUTION" if receipt["mode"] == "LOCAL_TEST" else "PRIOR_SANDBOX_EXECUTION",
            "source_mode": receipt["mode"], "trust_authority": AUTHORITY, "fresh_verification": False,
            "browser_observed_at": observation["observed_at"], "adapter_received_at": observation["received_at"],
            "imported_at": imported_at, "clock_domains": {"event_time": "KERNEL_BROWSER", "adapter_received_at": "EXECUTION_ADAPTER", "observed_at": "LOCAL_IMPORTER", "cross_clock_order_proves_causality": False},
            "receipt_sha256": bundle["receipt_sha256"], "review_manifest_sha256": bundle["manifest_sha256"],
            "observation_index": index, "session_id": identity["session_id"], "replay_id": identity["replay_id"],
            "ticket_id": observation["ticket_id"],
            "recording": {"sha256": receipt["recording"]["sha256"], "bytes": receipt["recording"]["bytes"],
                          "public_review": "NOT_REVIEWED", "access": "PRIVATE_OPERATOR_ARTIFACT"}}
    # These are exact DOM reads in the bound adapter receipt, not payment facts
    # reconstructed from Store. Keep the actual page message separate, including
    # an empty message. Existing manifests retain byte-identical v1 payloads.
    projection = bundle["manifest"].get("browser_projection")
    if projection in {"captured-fields-v2", "execution-fields-v3"}:
        payload["browser_projection"] = projection
        payload["observed_fields"] = {key: safe_message(observation[key]) for key in
            ("run_state", "provider_title", "merchant_title", "verdict") if observation.get(key)}
    if projection == "execution-fields-v3":
        # Receipt execution outcome is separate from the captured page labels
        # and deterministic payment verdict. Never project arbitrary errors.
        known_issues = {"REMOTE_SCENARIO_FAILED": "checkout_step_failed",
                        "KERNEL_TIMEOUT": "time_limit", "SESSION_DEADLINE": "time_limit",
                        "KERNEL_NETWORK_ERROR": "connection_lost", "INTERRUPTED": "interrupted",
                        "CORRELATION_FAILED": "identity_check_failed", "REMOTE_AUTH_FAILED": "access_failed"}
        error = receipt.get("error")
        issue = known_issues.get(error, "unavailable_detail") if isinstance(error, str) else None
        payload["browser_execution"] = {"status": receipt["status"],
            "recording_state": receipt["recording_state"], "issue": issue}
    return payload


def stable_id(prefix, value):
    return prefix + "_" + hashlib.sha256(value.encode()).hexdigest()[:32]


def import_kernel_receipt(store, manifest_path, artifact_root, *, apply=False):
    """Validate by default. Apply appends evidence only, in one fenced transaction."""
    bundle = load_reviewed_bundle(manifest_path, artifact_root)
    receipt = bundle["receipt"]; identity = bundle["manifest"]["identity"]
    receipt_hash = bundle["receipt_sha256"]
    with store.connect(write=apply) as db:
        run = db.execute("SELECT * FROM runs WHERE id=?", (identity["run_id"],)).fetchone()
        purchase = db.execute("SELECT * FROM purchases WHERE id=? AND run_id=?", (identity["purchase_id"], identity["run_id"])).fetchone()
        require(run is not None and purchase is not None and run["mode"] == identity["source_mode"] and
                run["fixture_id"] == "workshop-v1" and run["invariant_version"] == "ticket-v1" and
                purchase["amount"] == 2900 and purchase["currency"] == "USD", "DESTINATION_SCOPE_MISMATCH")
        fixture = db.execute("SELECT owned,environment FROM fixtures WHERE id=?", (run["fixture_id"],)).fetchone()
        require(fixture and fixture["owned"] == 1 and fixture["environment"] == "sandbox", "OWNED_FIXTURE_REQUIRED")
        require(receipt["identity"]["order_id"] == purchase["order_id"], "DESTINATION_ORDER_MISMATCH")
        ticket_ids = {r[0] for r in db.execute("SELECT id FROM tickets WHERE purchase_id=?", (purchase["id"],))}
        for observation in receipt["observations"]:
            require(observation["ticket_id"] is None or observation["ticket_id"] in ticket_ids, "DESTINATION_TICKET_MISMATCH")
        previous = db.execute("SELECT * FROM events WHERE event_type=? AND json_extract(payload_json,'$.session_id')=? ORDER BY id", (EVENT_TYPE, identity["session_id"])).fetchall()
        imported_at = previous[0]["observed_at"] if previous else utcnow()
        expected_events = []
        for index, observation in enumerate(receipt["observations"]):
            # Browser order identity is preserved, including pre-order nulls.
            # Journal equality is correlation only; it creates no causal edge.
            semantic = {"checkout": "order.create", "confirm_return": "order.capture"}.get(observation["scenario"])
            operations = db.execute("SELECT id FROM operations WHERE purchase_id=? AND semantic_key=? AND json_extract(response_json,'$.id')=?", (purchase["id"], semantic, observation["order_id"])).fetchall() if semantic and observation["order_id"] else []
            operation_id = operations[0]["id"] if len(operations) == 1 else None
            # All observations share the real import instant. Preserve the
            # receipt's explicit sequence in Store's (observed_at, id) ordering
            # without inventing distinct timestamps or causal relationships.
            event_id = "event_" + receipt_hash[:28] + f"{index:04x}"
            expected_events.append({"id": event_id, "run_id": run["id"],
                "purchase_id": purchase["id"], "order_id": observation["order_id"], "operation_id": operation_id,
                "source": "browser", "event_type": EVENT_TYPE, "event_time": observation["observed_at"],
                "observed_at": imported_at, "caused_by": None,
                "payload_json": canonical(event_payload(bundle, observation, index, imported_at))})
        require(not previous or [dict(row) for row in previous] == sorted(expected_events, key=lambda row: row["id"]), "SESSION_IMPORT_CONFLICT")
        references = []
        existing_refs = db.execute("SELECT * FROM evidence_refs").fetchall()
        for kind, (path, digest) in bundle["references"].items():
            evidence_id = stable_id("evidence", receipt_hash + ":" + kind)
            same = [row for row in existing_refs if row["id"] == evidence_id]
            if previous:
                require(len(same) == 1 and same[0]["run_id"] == run["id"] and same[0]["kind"] == "kernel-" + kind + "-v1" and
                        same[0]["path"] == str(path) and same[0]["sha256"] == digest and same[0]["mode"] == run["mode"], "EVIDENCE_IMPORT_CONFLICT")
            else:
                for row in existing_refs:
                    old = Path(row["path"]).expanduser().resolve()
                    require(old != path and not (old.exists() and old.samefile(path)), "ARTIFACT_ALREADY_ASSIGNED")
                require(not same, "EVIDENCE_IMPORT_CONFLICT")
            references.append((evidence_id, run["id"], "kernel-" + kind + "-v1", str(path), digest, run["mode"], imported_at))
        if apply and not previous:
            for reference in references:
                db.execute("INSERT INTO evidence_refs VALUES(?,?,?,?,?,?,?)", reference)
            for event in expected_events:
                db.execute("INSERT INTO events(id,run_id,purchase_id,order_id,operation_id,source,event_type,event_time,observed_at,caused_by,payload_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)", tuple(event.values()))
    return {"status": "ALREADY_IMPORTED" if previous else "IMPORTED" if apply else "VALIDATED_ONLY",
            "mode": "LOCAL_TEST", "source_mode": receipt["mode"], "provenance": expected_events and json.loads(expected_events[0]["payload_json"])["provenance"],
            "trust_authority": AUTHORITY, "run_id": identity["run_id"], "purchase_id": identity["purchase_id"],
            "receipt_sha256": receipt_hash, "review_manifest_sha256": bundle["manifest_sha256"],
            "event_ids": [event["id"] for event in expected_events], "observations": len(expected_events),
            "payment_mutations": 0, "network_calls": 0, "fresh_verification": False}
