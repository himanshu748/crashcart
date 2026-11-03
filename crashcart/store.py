"""Durable owned-fixture state. No method performs a provider/network operation.

One connection per transaction supports process restarts and independent workers.
Financial operation bodies are immutable, and leases use monotonically increasing
fencing tokens. LOCAL_TEST records never establish real sandbox payment evidence.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
import uuid


MODES = frozenset({"LOCAL_TEST", "LIVE_SANDBOX", "RECORDED_REPLAY", "FRESH_SANDBOX"})


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _id(prefix):
    return f"{prefix}_{uuid.uuid4().hex}"


def _row(row):
    if row is None:
        return None
    result = dict(row)
    for key, value in list(result.items()):
        if key.endswith("_json"):
            result[key[:-5]] = json.loads(value) if value is not None else None
    return result


class Store:
    def __init__(self, path):
        self.path = str(path)
        if self.path == ":memory:":
            raise ValueError("Store requires a durable database path")
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA busy_timeout = 15000")
        try:
            if write:
                db.execute("BEGIN IMMEDIATE")
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def migrate(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.execute("PRAGMA synchronous = FULL")
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError("database schema is newer than this application")
            if version < 1:
                sql = (Path(__file__).resolve().parents[1] / "migrations" / "001_initial.sql").read_text()
                db.executescript("BEGIN IMMEDIATE;\n" + sql + "\nCOMMIT;")

    def create_run(self, promise, mode="LIVE_SANDBOX", fault=None, fixture_id="workshop-v1", *, budget=None):
        if mode not in MODES:
            raise ValueError("unsupported run mode")
        if not isinstance(promise, str) or not promise.strip():
            raise ValueError("a delivery promise is required")
        if fault is not None and not isinstance(fault, dict):
            raise ValueError("fault must be an object")
        run_id, purchase_id, now = _id("run"), _id("purchase"), utcnow()
        with self.connect(write=True) as db:
            fixture = db.execute("SELECT * FROM fixtures WHERE id=? AND owned=1 AND environment='sandbox'", (fixture_id,)).fetchone()
            if fixture is None:
                raise ValueError("unregistered owned merchant fixture")
            invariant = db.execute("SELECT body_json FROM invariant_versions WHERE version='ticket-v1'").fetchone()[0]
            db.execute("""INSERT INTO runs(id,state,promise,mode,fixture_id,invariant_version,fault_json,invariant_json,budget_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (run_id, "CREATED", promise.strip(), mode, fixture_id, "ticket-v1", canonical(fault or {}), invariant, canonical(budget or {"max_attempts": 8, "max_seconds": 180, "max_model_calls": 4, "max_browser_sessions": 1}), now, now))
            db.execute("INSERT INTO purchases(id,run_id,amount,currency,created_at,updated_at) VALUES(?,?,?,?,?,?)", (purchase_id, run_id, fixture["amount"], fixture["currency"], now, now))
        return self.get_run(run_id)

    def get_run(self, run_id):
        with self.connect(write=True) as db:
            self._expire_investigations(db, run_id)
            return self._run_execution(db, _row(db.execute("SELECT r.*,p.id purchase_id FROM runs r JOIN purchases p ON p.run_id=r.id WHERE r.id=?", (run_id,)).fetchone()))

    def list_runs(self):
        with self.connect(write=True) as db:
            self._expire_investigations(db)
            return [self._run_execution(db, _row(r)) for r in db.execute("SELECT r.*,p.id purchase_id FROM runs r JOIN purchases p ON p.run_id=r.id ORDER BY r.created_at DESC")]

    @staticmethod
    def _run_execution(db, run):
        if run is None:
            return None
        execution = _row(db.execute("SELECT * FROM attempts WHERE run_id=? AND kind='investigator.execution' ORDER BY ordinal DESC LIMIT 1", (run["id"],)).fetchone())
        run["execution"] = None if execution is None else {
            "state": execution["state"].lower(),
            "active": execution["state"] == "RUNNING" and not run["cancel_requested"],
            "attempt_id": execution["id"], "started_at": execution["created_at"],
            "deadline_at": execution["input"]["deadline_at"],
            "reason": (execution["result"] or {}).get("summary", {}).get("reason"),
        }
        return run

    @staticmethod
    def incomplete_investigation(status, reason, *, model_mode=None):
        return {"status": status, "reason": reason, "model_mode": model_mode,
                "final_verdict": {"verdict": "INCONCLUSIVE", "reason": reason,
                    "signature": "investigation_incomplete", "invariant_version": "ticket-v1",
                    "source_ids": {}, "deadline": None}}

    def _end_investigation(self, db, run_id, execution_id, summary):
        # The terminal receipt and state share the cancellation read and commit.
        run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if run["cancel_requested"]:
            summary = self.incomplete_investigation("CANCELLED", "CANCELLED", model_mode=summary.get("model_mode"))
        now, event_id = utcnow(), _id("event")
        purchase = db.execute("SELECT id FROM purchases WHERE run_id=?", (run_id,)).fetchone()
        payload = {**summary, "execution_attempt_id": execution_id}
        db.execute("""INSERT INTO events(id,run_id,purchase_id,source,event_type,observed_at,payload_json)
            VALUES(?,?,?,'investigator','investigation_ended',?,?)""",
            (event_id, run_id, purchase["id"], now, canonical(payload)))
        state = "cancelled" if summary["status"] == "CANCELLED" else {"PASS": "completed", "FAIL": "failed", "INCONCLUSIVE": "inconclusive"}[summary["final_verdict"]["verdict"]]
        db.execute("UPDATE runs SET state=?,updated_at=? WHERE id=?", (state, now, run_id))
        if execution_id:
            terminal = summary["status"] if summary["status"] in {"CANCELLED", "INTERRUPTED"} else "COMPLETED" if summary["status"] in {"COMPLETED", "NEEDS_INPUT"} else "FAILED"
            db.execute("UPDATE attempts SET state=?,result_json=?,finished_at=? WHERE id=? AND state='RUNNING'",
                (terminal, canonical({"summary": summary, "event_id": event_id}), now, execution_id))
        return summary, _row(db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    def _expire_investigations(self, db, run_id=None):
        # A readback may close an expired owner, but never retries its unknown call.
        sql = "SELECT * FROM attempts WHERE kind='investigator.execution' AND state='RUNNING' AND json_extract(input_json,'$.deadline_epoch')<=?"
        values = [time.time()]
        if run_id is not None:
            sql += " AND run_id=?"
            values.append(run_id)
        for row in db.execute(sql, values).fetchall():
            self._end_investigation(db, row["run_id"], row["id"],
                self.incomplete_investigation("INTERRUPTED", "INVESTIGATION_DEADLINE_EXPIRED"))

    def begin_investigation(self, run_id, remaining_seconds):
        with self.connect(write=True) as db:
            self._expire_investigations(db, run_id)
            run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            if run["cancel_requested"]:
                return None
            if db.execute("SELECT 1 FROM attempts WHERE run_id=? AND kind='investigator.execution' AND state='RUNNING'", (run_id,)).fetchone():
                return None
            now, identity = utcnow(), _id("attempt")
            deadline = time.time() + max(0, remaining_seconds)
            input_data = {"deadline_epoch": deadline, "deadline_at": datetime.fromtimestamp(deadline, timezone.utc).isoformat().replace("+00:00", "Z")}
            ordinal = db.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM attempts WHERE run_id=?", (run_id,)).fetchone()[0]
            db.execute("INSERT INTO attempts(id,run_id,ordinal,kind,state,input_json,created_at) VALUES(?,?,?,'investigator.execution','RUNNING',?,?)",
                (identity, run_id, ordinal, canonical(input_data), now))
            db.execute("UPDATE runs SET state='running',updated_at=? WHERE id=?", (now, run_id))
            return identity

    def finish_investigation(self, run_id, execution_id, summary, *, expected_execution_id=None):
        with self.connect(write=True) as db:
            self._expire_investigations(db, run_id)
            if execution_id:
                execution = _row(db.execute("SELECT * FROM attempts WHERE id=? AND run_id=? AND kind='investigator.execution'", (execution_id, run_id)).fetchone())
                if execution is None:
                    raise ValueError("Unknown investigation execution")
                if execution["state"] != "RUNNING":
                    result = execution["result"]
                    return result["summary"], _row(db.execute("SELECT * FROM events WHERE id=?", (result["event_id"],)).fetchone())
            else:
                latest = db.execute("SELECT id,state FROM attempts WHERE run_id=? AND kind='investigator.execution' ORDER BY ordinal DESC LIMIT 1", (run_id,)).fetchone()
                if (latest["id"] if latest else None) != expected_execution_id:
                    # Configuration can fail before ownership is acquired. It
                    # must not publish over an execution started in the meantime,
                    # even if that newer execution has already completed.
                    return self.incomplete_investigation("SUPERSEDED", "INVESTIGATION_EXECUTION_CHANGED"), None
                if latest and latest["state"] == "RUNNING":
                    if db.execute("SELECT cancel_requested FROM runs WHERE id=?", (run_id,)).fetchone()[0]:
                        return self.incomplete_investigation("CANCELLED", "CANCELLED"), None
                    return self.incomplete_investigation("RUNNING", "INVESTIGATION_ALREADY_RUNNING"), None
            return self._end_investigation(db, run_id, execution_id, summary)

    def get_purchase(self, purchase_id):
        with self.connect() as db:
            return _row(db.execute("SELECT * FROM purchases WHERE id=?", (purchase_id,)).fetchone())

    def purchase_for_run(self, run_id):
        with self.connect() as db:
            return _row(db.execute("SELECT * FROM purchases WHERE run_id=?", (run_id,)).fetchone())

    def _update(self, table, identity, fields, allowed):
        if not fields or set(fields) - allowed:
            raise ValueError(f"unsupported {table} update fields: {sorted(set(fields) - allowed)}")
        fields["updated_at"] = utcnow()
        with self.connect(write=True) as db:
            changed = db.execute(f"UPDATE {table} SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?", (*fields.values(), identity)).rowcount
            if not changed:
                raise KeyError(identity)

    def update_run(self, run_id, **fields):
        if not fields or set(fields) - {"state", "cancel_requested"}:
            raise ValueError("unsupported runs update fields")
        with self.connect(write=True) as db:
            run = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            if run["cancel_requested"] and fields.get("cancel_requested") == 0:
                raise ValueError("Cancellation cannot be cleared; create a new run")
            if fields.get("cancel_requested", run["cancel_requested"]):
                fields["state"] = "cancelled"
            fields["updated_at"] = utcnow()
            db.execute("UPDATE runs SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?", (*fields.values(), run_id))
        return self.get_run(run_id)

    def update_purchase(self, purchase_id, **fields):
        self._update("purchases", purchase_id, fields, {"order_id", "payment_state", "capture_id", "capture_completed_at"})
        return self.get_purchase(purchase_id)

    def operation(self, purchase_id, semantic_key, body):
        if not isinstance(semantic_key, str) or not semantic_key:
            raise ValueError("semantic operation key is required")
        if not isinstance(body, dict):
            raise ValueError("operation body must be an object")
        body_json, now = canonical(body), utcnow()
        with self.connect(write=True) as db:
            existing = db.execute("SELECT * FROM operations WHERE purchase_id=? AND semantic_key=?", (purchase_id, semantic_key)).fetchone()
            if existing:
                if existing["body_json"] != body_json:
                    raise ValueError("a changed body cannot reuse a semantic operation identity")
                return _row(existing)
            op_id = _id("op")
            db.execute("""INSERT INTO operations(id,purchase_id,semantic_key,request_id,body_json,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)""", (op_id, purchase_id, semantic_key, str(uuid.uuid4()), body_json, now, now))
            return _row(db.execute("SELECT * FROM operations WHERE id=?", (op_id,)).fetchone())

    def update_operation(self, operation_id, *, state, response=None):
        self._update("operations", operation_id, {"state": state, "response_json": canonical(response) if response is not None else None}, {"state", "response_json"})
        with self.connect() as db:
            return _row(db.execute("SELECT * FROM operations WHERE id=?", (operation_id,)).fetchone())

    def get_operations(self, purchase_id):
        with self.connect() as db:
            return [_row(r) for r in db.execute("SELECT * FROM operations WHERE purchase_id=? ORDER BY created_at", (purchase_id,))]

    def confirm_payment(self, purchase_id, *, order_id, capture_id, amount, currency, completed_at, provider_response):
        """Persist an independent provider read validated by the payment adapter.

        Caller must use actual independent retrieval for sandbox modes. This
        persistence method does not itself assert that network evidence is real.
        """
        if type(amount) is not int or not order_id or not capture_id or not completed_at:
            raise ValueError("confirmation requires exact integer amount and payment identities")
        if not isinstance(provider_response, dict) or not provider_response:
            raise ValueError("independent provider read is required")
        with self.connect(write=True) as db:
            purchase = db.execute("SELECT * FROM purchases WHERE id=?", (purchase_id,)).fetchone()
            if purchase is None:
                raise KeyError(purchase_id)
            if purchase["amount"] != amount or purchase["currency"] != currency:
                raise ValueError("provider amount/currency mismatch")
            if purchase["order_id"] != order_id:
                raise ValueError("confirmation order does not match persisted purchase")
            db.execute("""UPDATE purchases SET payment_state='COMPLETED',payment_confirmed=1,capture_id=?,capture_completed_at=?,confirmation_json=?,updated_at=? WHERE id=?""", (capture_id, completed_at, canonical(provider_response), utcnow(), purchase_id))
        return self.get_purchase(purchase_id)

    def fulfill(self, purchase_id):
        with self.connect(write=True) as db:
            purchase = db.execute("SELECT * FROM purchases WHERE id=?", (purchase_id,)).fetchone()
            if purchase is None:
                raise KeyError(purchase_id)
            if not purchase["payment_confirmed"] or purchase["payment_state"] != "COMPLETED":
                raise ValueError("independently confirmed completed payment is required")
            db.execute("INSERT OR IGNORE INTO tickets(id,purchase_id,created_at) VALUES(?,?,?)", (_id("ticket"), purchase_id, utcnow()))
            return _row(db.execute("SELECT * FROM tickets WHERE purchase_id=?", (purchase_id,)).fetchone())

    def merchant_state(self, purchase_id):
        with self.connect() as db:
            purchase = db.execute("SELECT * FROM purchases WHERE id=?", (purchase_id,)).fetchone()
            if purchase is None:
                return {"purchase_id": purchase_id, "status": "MISSING_PURCHASE", "known": False, "ticket_count": None, "tickets": None}
            tickets = [_row(r) for r in db.execute("SELECT * FROM tickets WHERE purchase_id=?", (purchase_id,))]
            return {"purchase_id": purchase_id, "run_id": purchase["run_id"], "order_id": purchase["order_id"], "known": True, "status": "DELIVERED" if tickets else "NOT_DELIVERED", "payment_state": purchase["payment_state"], "ticket_count": len(tickets), "tickets": tickets, "observed_at": utcnow()}

    def record_event(self, run_id, source, event_type, payload=None, *, purchase_id=None, order_id=None, operation_id=None, event_time=None, caused_by=None):
        event_id = _id("event")
        with self.connect(write=True) as db:
            db.execute("""INSERT INTO events(id,run_id,purchase_id,order_id,operation_id,source,event_type,event_time,observed_at,caused_by,payload_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (event_id, run_id, purchase_id, order_id, operation_id, source, event_type, event_time, utcnow(), caused_by, canonical(payload or {})))
            return _row(db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    def get_events(self, run_id):
        with self.connect() as db:
            return [_row(r) for r in db.execute("SELECT * FROM events WHERE run_id=? ORDER BY observed_at,id", (run_id,))]

    def add_evidence(self, run_id, kind, path, sha256, *, mode=None):
        artifact = Path(path).expanduser().resolve()
        with self.connect(write=True) as db:
            run = db.execute("SELECT mode FROM runs WHERE id=?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            # Resolve earlier stored paths too: databases created before path
            # canonicalization must not retain an alias-based isolation bypass.
            for reference in db.execute("SELECT path FROM evidence_refs"):
                previous = Path(reference["path"]).expanduser().resolve()
                same_file = artifact.exists() and previous.exists() and artifact.samefile(previous)
                if previous == artifact or same_file:
                    raise sqlite3.IntegrityError("evidence artifact already belongs to a run")
            evidence_id = _id("evidence")
            db.execute("INSERT INTO evidence_refs VALUES(?,?,?,?,?,?,?)", (evidence_id, run_id, kind, str(artifact), sha256, mode or run["mode"], utcnow()))
            return _row(db.execute("SELECT * FROM evidence_refs WHERE id=?", (evidence_id,)).fetchone())

    def get_evidence(self, run_id):
        with self.connect() as db:
            return [_row(r) for r in db.execute("SELECT * FROM evidence_refs WHERE run_id=? ORDER BY created_at", (run_id,))]

    def create_attempt(self, run_id, kind, input_data=None):
        with self.connect(write=True) as db:
            ordinal = db.execute("SELECT COALESCE(MAX(ordinal),0)+1 FROM attempts WHERE run_id=?", (run_id,)).fetchone()[0]
            attempt_id = _id("attempt")
            db.execute("INSERT INTO attempts(id,run_id,ordinal,kind,state,input_json,created_at) VALUES(?,?,?,?,?,?,?)", (attempt_id, run_id, ordinal, kind, "RUNNING", canonical(input_data or {}), utcnow()))
            return _row(db.execute("SELECT * FROM attempts WHERE id=?", (attempt_id,)).fetchone())

    def finish_attempt(self, attempt_id, state, result):
        with self.connect(write=True) as db:
            if not db.execute("UPDATE attempts SET state=?,result_json=?,finished_at=? WHERE id=? AND finished_at IS NULL", (state, canonical(result), utcnow(), attempt_id)).rowcount:
                raise ValueError("attempt missing or already finished")

    def get_attempts(self, run_id):
        with self.connect() as db:
            return [_row(r) for r in db.execute("SELECT * FROM attempts WHERE run_id=? ORDER BY ordinal", (run_id,))]

    def enqueue(self, run_id, kind, payload=None, *, semantic_key=None, available_at=None):
        key, body, now = semantic_key or kind, canonical(payload or {}), utcnow()
        with self.connect(write=True) as db:
            existing = db.execute("SELECT * FROM jobs WHERE run_id=? AND semantic_key=?", (run_id, key)).fetchone()
            if existing:
                if existing["kind"] != kind or existing["payload_json"] != body:
                    raise ValueError("duplicate job identity has changed payload")
                return _row(existing)
            job_id = _id("job")
            db.execute("INSERT INTO jobs(id,run_id,kind,semantic_key,payload_json,available_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)", (job_id, run_id, kind, key, body, time.time() if available_at is None else available_at, now, now))
            return _row(db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone())

    def claim_job(self, owner, lease_seconds=30, *, now=None):
        if not owner or lease_seconds <= 0:
            raise ValueError("owner and positive lease required")
        now = time.time() if now is None else now
        with self.connect(write=True) as db:
            job = db.execute("""SELECT j.* FROM jobs j JOIN runs r ON r.id=j.run_id WHERE r.cancel_requested=0 AND
                (j.state='PENDING' AND j.available_at<=? OR j.state='RUNNING' AND j.lease_until<=?)
                ORDER BY j.available_at,j.created_at LIMIT 1""", (now, now)).fetchone()
            if job is None:
                return None
            db.execute("UPDATE jobs SET state='RUNNING',owner=?,lease_until=?,fence_token=fence_token+1,attempts=attempts+1,updated_at=? WHERE id=?", (owner, now + lease_seconds, utcnow(), job["id"]))
            return _row(db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone())

    def complete_job(self, job_id, owner, token, result=None, *, now=None, state="COMPLETED"):
        if state not in {"COMPLETED", "FAILED", "CANCELLED"}:
            raise ValueError("invalid job terminal state")
        now = time.time() if now is None else now
        with self.connect(write=True) as db:
            changed = db.execute("""UPDATE jobs SET state=?,result_json=?,lease_until=NULL,updated_at=?
                WHERE id=? AND state='RUNNING' AND owner=? AND fence_token=? AND lease_until>?""", (state, canonical(result), utcnow(), job_id, owner, token, now)).rowcount
            if not changed:
                raise ValueError("job lease was lost or expired")

    def accept_webhook(self, event_id, payload, *, verified, run_id=None):
        if verified is not True:
            raise ValueError("webhook signature has not been verified")
        body = canonical(payload)
        with self.connect(write=True) as db:
            existing = db.execute("SELECT * FROM webhooks WHERE event_id=?", (event_id,)).fetchone()
            if existing:
                if existing["payload_json"] != body or existing["run_id"] != run_id:
                    raise ValueError("webhook identity reused with altered payload or run")
                return {**_row(existing), "duplicate": True}
            db.execute("INSERT INTO webhooks(event_id,run_id,verified,payload_json,received_at) VALUES(?,?,?,?,?)", (event_id, run_id, 1, body, utcnow()))
            return {**_row(db.execute("SELECT * FROM webhooks WHERE event_id=?", (event_id,)).fetchone()), "duplicate": False}
