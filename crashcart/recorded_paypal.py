"""Read-only, hash-bound projection of already-public 8 November PayPal evidence.

The saved body is an independent Orders v2 GET, not a captured POST response.
Capture route syntax comes from the existing adapter; no request is sent here.
"""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from .replay import ReplayError

PROOF = Path(__file__).resolve().parents[1] / "evidence/runs/submission-ready/live-flow-nov8/proof.json"
PROOF_SHA256 = "dbc1a950c360c3afbe58eebdb715b7c1bc46d39329202f06c68a93156d49747d"


def saved_capture(source_path=None):
    """Publish selected payment fields only; never load credentials or adapters."""
    raw = Path(PROOF if source_path is None else source_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise ReplayError("The saved PayPal proof changed")
    try:
        source = json.loads(raw)
        result = source["payment"]
        payment = result["payment"]
        ids = result["source_ids"]
        response = payment["provider_response"]
        units = response["purchase_units"]
        if len(units) != 1 or len(units[0]["payments"]["captures"]) != 1:
            raise ValueError("ambiguous capture")
        capture = units[0]["payments"]["captures"][0]
        order_id, capture_id = payment["order_id"], payment["capture_id"]
        if (not isinstance(order_id, str) or not re.fullmatch(r"[A-Z0-9]{17}", order_id)
                or not isinstance(capture_id, str) or not re.fullmatch(r"[A-Z0-9]{17}", capture_id)
                or response["id"] != order_id or ids["order_id"] != order_id
                or capture["id"] != capture_id or ids["capture_id"] != capture_id
                or response["status"] != "COMPLETED" or capture["status"] != "COMPLETED"
                or payment["status"] != "COMPLETED" or payment["confirmed"] is not True
                or payment["amount"] != 2900 or payment["currency"] != "USD"
                or units[0]["amount"] != {"value": "29.00", "currency_code": "USD"}
                or capture["amount"] != units[0]["amount"]):
            raise ValueError("contradictory saved payment")
        completed = capture["create_time"]
        observed = payment["observed_at"]
        if (not completed.startswith("2026-11-08T") or not observed.startswith("2026-11-08T")
                or completed != payment["completed_at"] or completed != payment["capture_completed_at"]):
            raise ValueError("saved date")
        completed_at = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        observed_at = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if completed_at.utcoffset() is None or observed_at.utcoffset() is None or observed_at < completed_at:
            raise ValueError("saved sequence")
    except (KeyError, IndexError, TypeError, ValueError, AttributeError):
        raise ReplayError("The saved PayPal evidence has unsupported or contradictory fields") from None
    path = f"/v2/checkout/orders/{order_id}"
    amount = {"value": capture["amount"]["value"], "currency_code": capture["amount"]["currency_code"]}
    return {
        "kind": "recorded-paypal-capture-evidence-v1", "fresh_execution": False,
        "environment": "Sandbox", "recorded_date": "2026-11-08",
        "order_id": order_id, "capture_id": capture_id, "amount": amount,
        "capture_status": capture["status"], "capture_completed_at": completed,
        "capture_route": {"method": "POST", "path": path + "/capture",
                          "basis": "Existing capture adapter route with this saved order ID; not a captured wire request"},
        "confirmation": {"method": "GET", "path": path, "observed_at": observed,
                         "source": "independent_order_lookup"},
        "response_fields": {"id": response["id"], "status": response["status"], "amount": dict(amount),
                            "capture": {"id": capture["id"], "status": capture["status"],
                                        "amount": dict(amount), "create_time": completed}},
        "proof_sha256": PROOF_SHA256,
    }
