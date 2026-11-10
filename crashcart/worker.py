import json
import time
import uuid

from .store import Store, utcnow


INVESTIGATION_JOB_KEY = "investigation-v1"


def _investigation_result(result):
    """Persist/display a bounded summary, never raw model/provider exchanges."""
    from .investigator import _sanitize
    if not isinstance(result, dict):
        return {"status": "FAILED", "reason": "INVALID_INVESTIGATION_RESULT"}
    return _sanitize({key: result[key] for key in ("status", "reason", "model_mode", "final_verdict") if key in result})


def investigation_job(store, run_id):
    """Read-only operator projection of the once-per-run background request."""
    with store.connect() as db:
        row = db.execute("""SELECT j.id,j.state,j.updated_at,j.result_json,r.cancel_requested
            FROM jobs j JOIN runs r ON r.id=j.run_id
            WHERE j.run_id=? AND j.semantic_key=? AND j.kind='investigate'""",
            (run_id, INVESTIGATION_JOB_KEY)).fetchone()
    if row is None:
        return None
    result = _investigation_result(json.loads(row["result_json"])) if row["result_json"] else None
    state = row["state"]
    if row["cancel_requested"] and state in {"PENDING", "RUNNING"}:
        state, result = "CANCELLED", {"status": "CANCELLED", "reason": "CANCELLED"}
    return {"id": row["id"], "state": state, "updated_at": row["updated_at"], "result": result}


def _reserve_investigation_job(store, job, owner):
    """Fence this new job kind for its existing model deadline; never replay an unknown dispatch.

    This job lease is separate from payment/model deadlines. The investigator
    retains its original max_seconds and durable model-call reservations.
    """
    from .investigator import MAX_SECONDS
    now = time.time()
    with store.connect(write=True) as db:
        changed = db.execute("""UPDATE jobs SET lease_until=?,updated_at=?
            WHERE id=? AND state='RUNNING' AND owner=? AND fence_token=? AND lease_until>?
            AND EXISTS (SELECT 1 FROM runs WHERE id=jobs.run_id AND cancel_requested=0)""",
            (now + MAX_SECONDS + 30, utcnow(), job["id"], owner, job["fence_token"], now)).rowcount
        if not changed:
            raise ValueError("Investigation job lease lost or run cancelled")
    if job["attempts"] != 1:
        return {"status": "INTERRUPTED", "reason": "BACKGROUND_INVESTIGATION_INTERRUPTED"}
    return None


def work(db_path, once=False):
    store = Store(db_path)
    owner = "worker-" + uuid.uuid4().hex
    print(f"Worker ready: {owner}; durable database opened", flush=True)
    while True:
        job = store.claim_job(owner)
        if job:
            try:
                terminal = "COMPLETED"
                if job["kind"] == "health":
                    result = {"status": "ok", "owner": owner}
                elif job["kind"] == "reconcile":
                    from .paypal import PayPalError
                    from .service import MerchantService
                    attempt = job["payload"].get("attempt", 0)
                    try:
                        result = MerchantService(store).reconcile(job["run_id"])
                    except PayPalError as exc:
                        if exc.code in {"TIMEOUT", "TRANSPORT_ERROR"} and attempt < 29:
                            store.enqueue(job["run_id"], "reconcile", {"attempt": attempt+1}, semantic_key=f"recovery-{attempt+1}", available_at=time.time()+2)
                        raise
                    if result.get("verdict") == "INCONCLUSIVE" and attempt < 29:
                        store.enqueue(job["run_id"], "reconcile", {"attempt": attempt+1}, semantic_key=f"recovery-{attempt+1}", available_at=time.time()+2)
                elif job["kind"] == "investigate":
                    from .investigator import Investigation
                    from .service import MerchantService
                    result = _reserve_investigation_job(store, job, owner)
                    if result is None:
                        # Existing configuration, proof-mode, cancellation,
                        # wall-clock and call-budget gates still apply.
                        result = Investigation(store, MerchantService(store)).run(job["run_id"])
                    result = _investigation_result(result)
                    terminal = ("COMPLETED" if result.get("status") == "COMPLETED"
                                else "CANCELLED" if result.get("status") == "CANCELLED" else "FAILED")
                else:
                    raise ValueError("Unsupported job kind: " + job["kind"])
                store.complete_job(job["id"], owner, job["fence_token"], result, state=terminal)
                print(f"Job {job['id']} {terminal.lower()}", flush=True)
            except Exception as exc:
                # A cancelled or expired lease never becomes successful work.
                cancelled = job["kind"] == "investigate" and store.get_run(job["run_id"])["cancel_requested"]
                try:
                    failure = ({"status": "CANCELLED", "reason": "CANCELLED"} if cancelled else
                               {"status": "FAILED", "reason": "BACKGROUND_JOB_ERROR:" + type(exc).__name__}
                               if job["kind"] == "investigate" else {"error": type(exc).__name__})
                    store.complete_job(job["id"], owner, job["fence_token"], failure,
                                       state="CANCELLED" if cancelled else "FAILED")
                except ValueError:
                    pass
                store.record_event(job["run_id"], "worker", "job_cancelled" if cancelled else "job_failed",
                                   {"job_id": job["id"], "error": type(exc).__name__})
                print(f"Job {job['id']} {'cancelled' if cancelled else 'failed'}: {type(exc).__name__}", flush=True)
        if once:
            print("Worker cycle finished", flush=True)
            return
        time.sleep(1)
