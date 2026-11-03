"""Supervise one explicitly selected actual sandbox process-crash experiment.

Run only after stopping the operator's existing local server and recovery worker.
It creates no payment: the operator must approve and capture the named UI run.
The restarted server remains available; the temporary recovery worker is stopped.
"""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from crashcart.store import Store

RUN = "run_2ed44d7801ce4363965c998b2d3f4c0c"
OUT = ROOT / "evidence/runs/process-recovery"
OUT.mkdir(parents=True, exist_ok=True)


def now():
    return datetime.now(timezone.utc).isoformat()


def save(name, data):
    with (OUT / name).open("x") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


def state():
    store = Store(ROOT / "var/crashcart.sqlite3")
    purchase = store.purchase_for_run(RUN)
    with sqlite3.connect(store.path) as connection:
        connection.row_factory = sqlite3.Row
        jobs = [dict(row) for row in connection.execute("SELECT * FROM jobs WHERE run_id=?", (RUN,))]
    return {"run": store.get_run(RUN), "purchase": purchase,
            "merchant": store.merchant_state(purchase["id"]),
            "operations": store.get_operations(purchase["id"]),
            "events": store.get_events(RUN), "jobs": jobs}


def main():
    initial = state()
    assert initial["run"]["mode"] == "FRESH_SANDBOX"
    assert initial["run"]["fault"] == {"kind": "process_interrupt", "merchant": "healthy"}
    assert initial["merchant"]["ticket_count"] == 0
    assert not initial["purchase"]["payment_confirmed"]
    assert not any(job["state"] in {"PENDING", "RUNNING"} for job in initial["jobs"])
    env = dict(os.environ, CRASHCART_ALLOW_PROCESS_INTERRUPT="1")
    log = (OUT / "crashing-server.log").open("x")
    server = subprocess.Popen([sys.executable, "-m", "crashcart", "serve"], cwd=ROOT, env=env, stdout=log, stderr=log)
    save("started.json", {"mode": "FRESH_SANDBOX", "run_id": RUN, "at": now(),
                           "pid": server.pid, "fault_enabled_for_this_process_only": True,
                           "worker_stopped_before_capture": True,
                           "source_hashes": {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                               for name in ["crashcart/service.py", "crashcart/store.py", "crashcart/worker.py", "crashcart/invariant.py", "crashcart/paypal.py"]}})
    print("Crash experiment server started; awaiting operator sandbox capture", flush=True)
    exit_code = server.wait(timeout=900)
    log.close()
    checkpoint = state()
    save("after-exit.json", {"at": now(), "actual_process_exit_code": exit_code, **checkpoint})
    assert exit_code == 86
    assert checkpoint["merchant"]["ticket_count"] == 0
    assert checkpoint["purchase"]["capture_id"] is None
    assert any(e["event_type"] == "process_exit_boundary" for e in checkpoint["events"])
    assert any(e["event_type"] == "capture_transport_response" for e in checkpoint["events"])
    env["CRASHCART_ALLOW_PROCESS_INTERRUPT"] = "0"
    restored_log = (OUT / "restored-server.log").open("x")
    restored = subprocess.Popen([sys.executable, "-m", "crashcart", "serve"], cwd=ROOT, env=env, stdout=restored_log, stderr=restored_log)
    worker_log = (OUT / "restarted-worker.log").open("x")
    worker = subprocess.Popen([sys.executable, "-m", "crashcart", "worker"], cwd=ROOT, env=env, stdout=worker_log, stderr=worker_log)
    save("restarted.json", {"at": now(), "server_pid": restored.pid, "worker_pid": worker.pid,
                            "interruption_disabled": True, "same_database": "var/crashcart.sqlite3"})
    try:
        for _ in range(55):
            final = state()
            if final["merchant"]["ticket_count"] == 1 and any(j["state"] == "COMPLETED" for j in final["jobs"]):
                break
            time.sleep(1)
        capture = next(e for e in final["events"] if e["event_type"] == "capture_transport_response")
        completed = capture["payload"]["purchase_units"][0]["payments"]["captures"][0]["update_time"]
        ticket = final["merchant"]["tickets"][0]
        elapsed = (datetime.fromisoformat(ticket["created_at"].replace("Z", "+00:00")) - datetime.fromisoformat(completed.replace("Z", "+00:00"))).total_seconds()
        assert 0 <= elapsed <= 60
        assert final["run"]["state"] == "completed"
        assert final["purchase"]["payment_confirmed"] == 1
        save("recovery.json", {"result": "PASS", "at": now(), "mode": "FRESH_SANDBOX",
                               "capture_to_ticket_seconds": elapsed, **final})
        print(json.dumps({"result": "PASS", "actual_exit": exit_code, "ticket_count": 1, "capture_to_ticket_seconds": elapsed}), flush=True)
    finally:
        worker.terminate()
        worker.wait(timeout=5)
        worker_log.close()
    print("Recovery worker stopped; restored server remains available", flush=True)
    try:
        restored.wait()
    finally:
        restored.terminate()
        restored_log.close()


if __name__ == "__main__":
    main()
