#!/usr/bin/env python3
"""Observe an existing owned Sandbox checkout in one explicitly allowed KERNEL session.

This entry point does not create an order, approve/capture a payment, expose a
server or grant usage. Its private recording requires review before import.
Only the existing fixed `observe` scenario is available here.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from crashcart.kernel_browser import KernelBrowser, KernelError


def selected_identity(db_path, run_id):
    """Read selection without creating/migrating/mutating the merchant database."""
    path = Path(db_path)
    if not path.is_file() or path.is_symlink():
        raise KernelError("EXISTING_DATABASE_REQUIRED")
    if not isinstance(run_id, str) or not re.fullmatch(r"run_[a-f0-9]{32}", run_id):
        raise KernelError("INVALID_RUN_ID")
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        if db.execute("PRAGMA user_version").fetchone()[0] != 1:
            raise KernelError("EXISTING_SCHEMA_REQUIRED")
        row = db.execute("""SELECT r.id,r.mode,r.fixture_id,r.cancel_requested,r.state,
            p.id purchase_id,p.run_id purchase_run,p.order_id,p.amount,p.currency,
            f.owned,f.environment,f.amount fixture_amount,f.currency fixture_currency
            FROM runs r JOIN purchases p ON p.run_id=r.id JOIN fixtures f ON f.id=r.fixture_id
            WHERE r.id=?""", (run_id,)).fetchone()
    if row is None:
        raise KernelError("EXISTING_RUN_REQUIRED")
    if row["cancel_requested"] or row["state"] == "cancelled":
        raise KernelError("RUN_CANCELLED")
    if (row["fixture_id"] != "workshop-v1" or row["owned"] != 1 or
            row["environment"] != "sandbox" or row["amount"] != 2900 or
            row["fixture_amount"] != 2900 or row["currency"] != "USD" or row["fixture_currency"] != "USD"):
        raise KernelError("OWNED_WORKSHOP_REQUIRED")
    if row["mode"] not in {"LIVE_SANDBOX", "FRESH_SANDBOX"}:
        raise KernelError("ACTUAL_SANDBOX_RUN_REQUIRED")
    if not re.fullmatch(r"purchase_[a-f0-9]{32}", row["purchase_id"]):
        raise KernelError("INVALID_PURCHASE_ID")
    return {"run_id": row["id"], "purchase_id": row["purchase_id"],
            "mode": row["mode"], "order_id": row["order_id"]}


def observe_checkout(db_path, run_id, allowance_path, state_dir, *, adapter_factory=KernelBrowser, environ=None):
    identity = selected_identity(db_path, run_id)
    allowance = Path(allowance_path)
    if not allowance.is_file() or allowance.is_symlink():
        raise KernelError("EXPLICIT_ALLOWANCE_REQUIRED")
    try:
        grant = json.loads(allowance.read_text())
        if not isinstance(grant, dict) or not isinstance(grant.get("scenarios"), list) or "observe" not in grant["scenarios"]:
            raise ValueError()
    except (OSError, ValueError, TypeError):
        raise KernelError("OBSERVE_ALLOWANCE_REQUIRED") from None
    directory = Path(state_dir).resolve()
    adapter = adapter_factory(allowance_path=allowance, state_dir=directory, environ=environ)
    with adapter.session(**identity) as session:
        session.perform("observe")
        # Stop a cancelled/replaced local selection from becoming a success.
        # The remote scenario independently checks run/purchase/fixture identity.
        if selected_identity(db_path, run_id) != identity:
            raise KernelError("SELECTED_IDENTITY_CHANGED")
    receipt = session.receipt
    name = receipt.get("session_name", "")
    if not re.fullmatch(r"crashcart-[a-f0-9]{32}", name):
        raise KernelError("INVALID_RECEIPT_IDENTITY")
    complete = (receipt.get("status") == "OBSERVED" and receipt.get("recording_state") == "SAVED" and
                receipt.get("cleanup") == {"recording_stop": "SUCCEEDED", "recording_download": "SUCCEEDED", "session_delete": "SUCCEEDED"})
    return {"status": "OBSERVED_UNREVIEWED" if complete else "INCOMPLETE",
            "mode": receipt.get("mode"), "run_id": run_id,
            "receipt_path": str(directory / (name + ".receipt.json")),
            "payment_verdict": "NOT_EVALUATED", "imported": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--allowance", required=True, type=Path)
    parser.add_argument("--state-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = observe_checkout(args.db, args.run_id, args.allowance, args.state_dir)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "OBSERVED_UNREVIEWED" else 1
    except KernelError as exc:
        print(json.dumps({"status": "REJECTED", "error": exc.code}, sort_keys=True))
        return 1
    except (KeyboardInterrupt, SystemExit):
        print(json.dumps({"status": "STOPPED", "error": "INTERRUPTED"}, sort_keys=True))
        return 130
    except Exception:
        # No URLs, provider messages, tracebacks or credentials in CLI output.
        print(json.dumps({"status": "REJECTED", "error": "OBSERVATION_FAILED"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
