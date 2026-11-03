#!/usr/bin/env python3
"""Execute the actual export against a clean local API; never create a payment."""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from crashcart.server import Handler
from crashcart.store import Store

VERSION = "6.2.1"


def hashes():
    names = ["exports/crashcart.postman_collection.json", "exports/crashcart.postman_environment.json",
             "scripts/verify_postman.py", "crashcart/server.py", "crashcart/store.py", "migrations/001_initial.sql"]
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--newman", default=shutil.which("newman"), help="Path to installed newman 6.2.1 executable")
    parser.add_argument("--evidence-dir", default="evidence/runs/postman")
    args = parser.parse_args()
    evidence = (ROOT / args.evidence_dir).resolve()
    if not evidence.is_relative_to(ROOT / "evidence"):
        parser.error("evidence directory must be inside this repository's evidence/")
    evidence.mkdir(parents=True, exist_ok=True)
    if not args.newman:
        parser.error("newman 6.2.1 is missing; install the documented pinned temporary runner")
    version = subprocess.run([args.newman, "--version"], capture_output=True, text=True, check=False)
    (evidence / "newman-version.log").write_text(version.stdout + version.stderr)
    if version.returncode or version.stdout.strip() != VERSION:
        parser.error(f"expected Newman {VERSION}; inspect newman-version.log")
    (evidence / "node-version.log").write_text(subprocess.check_output(["node", "--version"], text=True))
    before = hashes()
    # This disposable process has no enabled provider and its token is never exported.
    os.environ["CRASHCART_OPERATOR_TOKEN"] = secrets.token_urlsafe(32)
    os.environ["CRASHCART_ALLOW_SANDBOX"] = "0"
    os.environ["CRASHCART_ALLOW_MODEL"] = "0"
    os.environ["CRASHCART_ALLOW_KERNEL"] = "0"
    runs = []
    with tempfile.TemporaryDirectory(prefix="crashcart-postman-api-") as work:
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.store = Store(Path(work) / "fresh.sqlite3")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            for label, folder in (("smoke", "Local smoke"), ("missing-proof-negative", "Observed sandbox evidence")):
                report = evidence / f"{label}.newman.json"
                command = [args.newman, "run", str(ROOT / "exports/crashcart.postman_collection.json"),
                           "--environment", str(ROOT / "exports/crashcart.postman_environment.json"),
                           "--env-var", "base_url=" + base, "--folder", folder,
                           "--timeout-request", "5000", "--reporters", "cli,json",
                           "--reporter-json-export", str(report), "--color", "off"]
                process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=60, check=False)
                (evidence / f"{label}.log").write_text(process.stdout + process.stderr)
                result = json.loads(report.read_text()) if report.is_file() else {}
                stats = result.get("run", {}).get("stats", {})
                runs.append({"name": label, "folder": folder, "command": command,
                             "expected_exit": 0 if label == "smoke" else 1,
                             "observed_exit": process.returncode, "stats": stats})
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    after = hashes()
    smoke, negative = runs
    smoke_pass = (smoke["observed_exit"] == 0 and smoke["stats"].get("requests", {}).get("total") == 2
                  and smoke["stats"].get("assertions", {}).get("total", 0) >= 7
                  and smoke["stats"].get("assertions", {}).get("failed") == 0
                  and smoke["stats"].get("assertions", {}).get("pending", 0) == 0)
    negative_pass = negative["observed_exit"] != 0 and negative["stats"].get("assertions", {}).get("failed", 0) > 0
    receipt = {"executed_at": datetime.now(timezone.utc).isoformat(), "runner": "newman", "runner_version": VERSION,
               "mode": "LOCAL_TEST", "source_hashes": before,
               "source_changed_during_run": [name for name in before if before[name] != after[name]],
               "smoke_pass": smoke_pass, "missing_proof_rejected": negative_pass, "runs": runs,
               "sandbox_execution": "NOT RUN", "CC-050": "BLOCKED",
               "blocker": "No approved actual paid sandbox run with independent provider evidence; CC-010 and executable regression export CC-035 remain prerequisites.",
               "limitations": "Smoke establishes local API/database health and fixture only. Negative execution establishes missing live proof fails instead of being skipped."}
    (evidence / "execution.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    return 0 if smoke_pass and negative_pass and not receipt["source_changed_during_run"] else 1


if __name__ == "__main__":
    sys.exit(main())
