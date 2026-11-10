"""Pinned public presentation of the saved 8 November failure investigation."""
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path

from .replay import ReplayError
from .model_ids import DEEPSEEK_MODEL_ID

SUMMARY = Path(__file__).resolve().parents[1] / "evidence/runs/submission-ready/ai-failure-nov8-summary.json"
SUMMARY_SHA256 = "5e30391a8673228eaae6e0ec16b13f1db86686e5f608a69b865babad5fbc569a"


def failure_ai(source_path=None):
    raw = Path(SUMMARY if source_path is None else source_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != SUMMARY_SHA256:
        raise ReplayError("The reviewed failure investigation changed")
    try:
        source = json.loads(raw)
        result = source["deterministic_result"]
        trace = source["trace"]
        if (source["kind"] != "recorded-failure-investigation-v1"
                or source["fresh_execution"] is not False
                or source["same_case_as_public_faulty_replay"] is not False
                or source["provider"] != "Modal"
                or source["model"] != DEEPSEEK_MODEL_ID
                or source["recorded_date"] != "2026-11-08"
                or result["verdict"] != "FAIL" or result["signature"] != "paid_without_ticket"
                or result["source_ids"]["ticket_ids"] != []
                or len(trace) != 3):
            raise ValueError("scope")
        for key in ("investigation_started_at", "investigation_finished_at", "payment_completed_at"):
            value = source[key]
            if not value.startswith("2026-11-08T") or datetime.fromisoformat(value.replace("Z", "+00:00")).utcoffset() is None:
                raise ValueError("date")
        if datetime.fromisoformat(source["investigation_started_at"].replace("Z", "+00:00")) > datetime.fromisoformat(source["investigation_finished_at"].replace("Z", "+00:00")):
            raise ValueError("sequence")
        allowed = {result["source_ids"]["provider_observation_id"], result["source_ids"]["merchant_observation_id"]}
        projected = []
        for index, action in enumerate(("read_provider", "read_merchant", "finish")):
            step = trace[index]
            if (step["step"] != index + 1 or step["action"] != action
                    or not isinstance(step["hypothesis"], str) or not 1 <= len(step["hypothesis"]) <= 2000
                    or len(step["findings"]) != index):
                raise ValueError("step")
            findings = []
            for finding in step["findings"]:
                if (finding["kind"] != "observed" or not isinstance(finding["claim"], str)
                        or not 1 <= len(finding["claim"]) <= 2000
                        or not finding["evidence_ids"] or not set(finding["evidence_ids"]) <= allowed):
                    raise ValueError("citation")
                findings.append({key: deepcopy(finding[key]) for key in ("claim", "evidence_ids", "kind")})
            projected.append({"step": index + 1, "action": action, "hypothesis": step["hypothesis"], "findings": findings})
        if {value for finding in projected[-1]["findings"] for value in finding["evidence_ids"]} != allowed:
            raise ValueError("missing citation")
    except (KeyError, ValueError, TypeError, AttributeError):
        raise ReplayError("The failure investigation has an unsupported scope or citation") from None
    return {**{key: deepcopy(source[key]) for key in (
        "kind", "fresh_execution", "same_case_as_public_faulty_replay", "provider", "model", "recorded_date",
        "investigation_started_at", "investigation_finished_at", "payment_completed_at", "proof_sha256")},
        "trace": projected, "deterministic_result": {key: deepcopy(result[key]) for key in (
            "verdict", "signature", "deadline", "invariant_version", "source_ids")},
        "source_summary_sha256": SUMMARY_SHA256}
