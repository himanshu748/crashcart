import os
import time
import uuid

from .store import Store


def work(db_path, once=False):
    store = Store(db_path)
    owner = "worker-" + uuid.uuid4().hex
    print(f"Worker ready: {owner}; durable database opened", flush=True)
    while True:
        job = store.claim_job(owner)
        if job:
            try:
                if job["kind"] == "health":
                    result = {"status": "ok", "owner": owner}
                elif job["kind"] == "reconcile":
                    from .service import MerchantService
                    result = MerchantService(store).reconcile(job["run_id"])
                    attempt = job["payload"].get("attempt", 0)
                    if result.get("verdict") == "INCONCLUSIVE" and attempt < 29:
                        store.enqueue(job["run_id"], "reconcile", {"attempt": attempt+1}, semantic_key=f"recovery-{attempt+1}", available_at=time.time()+2)
                else:
                    raise ValueError("Unsupported job kind: " + job["kind"])
                store.complete_job(job["id"], owner, job["fence_token"], result)
                print(f"Job {job['id']} completed", flush=True)
            except Exception as exc:
                # A cancelled or expired lease never becomes successful work.
                try:
                    store.complete_job(job["id"], owner, job["fence_token"], {"error": type(exc).__name__}, state="FAILED")
                except ValueError:
                    pass
                store.record_event(job["run_id"], "worker", "job_failed", {"job_id": job["id"], "error": type(exc).__name__})
                print(f"Job {job['id']} failed: {type(exc).__name__}", flush=True)
        if once:
            print("Worker cycle finished", flush=True)
            return
        time.sleep(1)
