"""Durable admission limits for an explicitly authorized public Sandbox window.

This supplementary ledger never initializes or resets ModelAllowance. Admission
reserves all three possible AI calls before any payment/provider dispatch;
failures and unknown outcomes remain charged. The HTTP boundary must pass the
socket peer (or an independently authenticated proxy address), never a request's
Forwarded/X-Forwarded-For value. This module accepts a single IP literal only.
"""
from datetime import datetime, timezone
import hashlib
import ipaddress
import math
import re
import time
import uuid


MAX_RUNS = 8
MAX_IP_HOURLY = 3
MAX_AI_CALLS = 3
AI_CALL_MICRO_USD = 40_000
RUN_MICRO_USD = MAX_AI_CALLS * AI_CALL_MICRO_USD
DAILY_MICRO_USD = 1_000_000
MAX_AUTHORIZED_UNTIL = datetime(2026, 12, 23, tzinfo=timezone.utc).timestamp()
PREFIX = "CRASHCART_PUBLIC_LIVE_"


class PublicLiveLimitError(Exception):
    """Stable, non-sensitive denial; no provider dispatch is authorized."""

    def __init__(self, code, status=429):
        super().__init__(code)
        self.code, self.status = code, status


def _deny(code, status=429):
    raise PublicLiveLimitError(code, status)


def _bounded(env, suffix, default, maximum, *, minimum=1):
    value = env.get(PREFIX + suffix, str(default))
    if not isinstance(value, str) or not re.fullmatch(r"0|[1-9][0-9]{0,6}", value):
        _deny("PUBLIC_LIVE_CONFIG_INVALID", 503)
    result = int(value)
    if not minimum <= result <= maximum:
        _deny("PUBLIC_LIVE_CONFIG_INVALID", 503)
    return result


def _identity(value, *, hashed=False):
    pattern = r"[a-f0-9]{64}" if hashed else r"[A-Za-z0-9_-]{16,128}"
    if not isinstance(value, str) or not re.fullmatch(pattern, value):
        _deny("PUBLIC_LIVE_IDENTITY_INVALID", 400)
    return value


def _ip_key(value):
    if not isinstance(value, str) or len(value) > 45 or "%" in value:
        _deny("PUBLIC_LIVE_IP_INVALID", 400)
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        _deny("PUBLIC_LIVE_IP_INVALID", 400)
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        address = address.ipv4_mapped
    # A pseudonymous operational key, not a claim that IPs are anonymous.
    return hashlib.sha256(str(address).encode("ascii")).hexdigest()


class Limits:
    """Every mutation uses Store's BEGIN IMMEDIATE transaction across processes.

    Keep ``environ`` mutable: the live kill switch and tighter caps are re-read
    for every admission, binding and model phase. Repeated admission never
    grants another dispatch, including an unbound/unknown prior reservation.
    """

    def __init__(self, store, environ, clock=time.time):
        self.store, self.environ, self.clock = store, environ, clock
        with store.connect(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS public_live_reservations (
                id TEXT PRIMARY KEY,
                ip_key TEXT NOT NULL,
                session_hash TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                created_at REAL NOT NULL,
                utc_day TEXT NOT NULL,
                reserved_micro_usd INTEGER NOT NULL CHECK(reserved_micro_usd=120000),
                run_id TEXT UNIQUE REFERENCES runs(id),
                UNIQUE(session_hash, idempotency_key))""")
            db.execute("""CREATE INDEX IF NOT EXISTS public_live_reservation_ip_time
                ON public_live_reservations(ip_key,created_at)""")
            db.execute("""CREATE INDEX IF NOT EXISTS public_live_reservation_day
                ON public_live_reservations(utc_day)""")
            db.execute("""CREATE TABLE IF NOT EXISTS public_live_ai_phases (
                reservation_id TEXT NOT NULL REFERENCES public_live_reservations(id),
                phase_key TEXT NOT NULL,
                call_index INTEGER NOT NULL CHECK(call_index BETWEEN 1 AND 3),
                reserved_micro_usd INTEGER NOT NULL CHECK(reserved_micro_usd=40000),
                created_at REAL NOT NULL,
                PRIMARY KEY(reservation_id,phase_key),
                UNIQUE(reservation_id,call_index))""")

    def _config(self):
        now = self.clock()
        if type(now) not in {int, float} or not math.isfinite(now) or not 0 <= now <= MAX_AUTHORIZED_UNTIL:
            _deny("PUBLIC_LIVE_CLOCK_INVALID", 503)
        env = self.environ
        enabled = env.get(PREFIX + "ENABLED", "0")
        if enabled not in {"0", "1"}:
            _deny("PUBLIC_LIVE_CONFIG_INVALID", 503)
        owner_runs = _bounded(env, "AUTHORIZED_RUNS", 0, MAX_RUNS, minimum=0)
        expires_text = env.get(PREFIX + "AUTHORIZED_UNTIL", "")
        expires = None
        if expires_text:
            try:
                if not isinstance(expires_text, str) or len(expires_text) > 80:
                    raise ValueError("expiry")
                stamp = datetime.fromisoformat(expires_text.replace("Z", "+00:00"))
                if stamp.utcoffset() is None:
                    raise ValueError("timezone")
                expires = stamp.timestamp()
                if expires > MAX_AUTHORIZED_UNTIL:
                    raise ValueError("expiry")
            except (ValueError, TypeError, OverflowError):
                _deny("PUBLIC_LIVE_CONFIG_INVALID", 503)
        return {
            "enabled": enabled == "1" and owner_runs > 0 and expires is not None and now < expires,
            "authorized_runs": owner_runs,
            "authorized_until": expires_text or None,
            "ip_hourly_runs": _bounded(env, "IP_HOURLY_RUNS", MAX_IP_HOURLY, MAX_IP_HOURLY),
            "daily_runs": _bounded(env, "DAILY_RUNS", MAX_RUNS, MAX_RUNS),
            "daily_micro_usd": _bounded(env, "DAILY_MICRO_USD", DAILY_MICRO_USD, DAILY_MICRO_USD),
            "run_micro_usd": RUN_MICRO_USD,
            "ai_calls_per_run": MAX_AI_CALLS,
            "ai_call_micro_usd": AI_CALL_MICRO_USD,
            "now": now,
            "utc_day": datetime.fromtimestamp(now, timezone.utc).date().isoformat(),
        }

    @staticmethod
    def _active(config):
        if not config["enabled"]:
            _deny("PUBLIC_LIVE_PAUSED", 503)

    @staticmethod
    def _clock_order(db, now):
        latest = db.execute("SELECT MAX(created_at) FROM public_live_reservations").fetchone()[0]
        ai_latest = db.execute("SELECT MAX(created_at) FROM public_live_ai_phases").fetchone()[0]
        if any(stamp is not None and now < stamp for stamp in (latest, ai_latest)):
            _deny("PUBLIC_LIVE_CLOCK_REVERSED", 503)

    @staticmethod
    def _daily(db, config):
        return db.execute("""SELECT COUNT(*) runs,COALESCE(SUM(reserved_micro_usd),0) micro_usd
            FROM public_live_reservations WHERE utc_day=?""", (config["utc_day"],)).fetchone()

    @staticmethod
    def _result(row, *, created=False):
        return {"id": row["id"], "run_id": row["run_id"], "created": created,
                "reserved_micro_usd": row["reserved_micro_usd"], "utc_day": row["utc_day"]}

    def admit(self, ip, session_hash, idempotency_key, *, capacity_check=None):
        """Reserve before dispatch. Only ``created=True`` may create a new run.

        Same session/key on retry returns the existing reservation, even if
        admission crashed before bind. It never refunds, replaces or resumes a
        dispatch; the controller must report an unbound retry as pending.
        """
        ip_key = _ip_key(ip)
        _identity(session_hash, hashed=True)
        _identity(idempotency_key)
        with self.store.connect(write=True) as db:
            config = self._config()
            self._active(config)
            self._clock_order(db, config["now"])
            previous = db.execute("""SELECT * FROM public_live_reservations
                WHERE session_hash=? AND idempotency_key=?""", (session_hash, idempotency_key)).fetchone()
            if previous is not None:
                return self._result(previous)
            if db.execute("SELECT COUNT(*) FROM public_live_reservations").fetchone()[0] >= config["authorized_runs"]:
                _deny("PUBLIC_LIVE_OWNER_LIMIT")
            hourly = db.execute("""SELECT COUNT(*) FROM public_live_reservations
                WHERE ip_key=? AND created_at>?""", (ip_key, config["now"] - 3600)).fetchone()[0]
            if hourly >= config["ip_hourly_runs"]:
                _deny("PUBLIC_LIVE_IP_LIMIT")
            day = self._daily(db, config)
            if day["runs"] >= config["daily_runs"]:
                _deny("PUBLIC_LIVE_DAILY_RUN_LIMIT")
            if day["micro_usd"] + RUN_MICRO_USD > config["daily_micro_usd"]:
                _deny("PUBLIC_LIVE_DAILY_BUDGET")
            # The orchestrator can check its existing provider ledger while
            # this admission transaction excludes concurrent reservations.
            # Idempotent readback above never consumes another capacity hold.
            if capacity_check is not None:
                capacity_check(db)
            reservation_id = "public_" + uuid.uuid4().hex
            db.execute("""INSERT INTO public_live_reservations
                (id,ip_key,session_hash,idempotency_key,created_at,utc_day,reserved_micro_usd)
                VALUES(?,?,?,?,?,?,?)""", (reservation_id, ip_key, session_hash, idempotency_key,
                                           config["now"], config["utc_day"], RUN_MICRO_USD))
            row = db.execute("SELECT * FROM public_live_reservations WHERE id=?", (reservation_id,)).fetchone()
            return self._result(row, created=True)

    def bind(self, reservation_id, run_id):
        """Attach once to an existing run before starting any provider work."""
        with self.store.connect(write=True) as db:
            config = self._config()
            self._active(config)
            self._clock_order(db, config["now"])
            row = db.execute("SELECT * FROM public_live_reservations WHERE id=?", (reservation_id,)).fetchone()
            if row is None or db.execute("SELECT id FROM runs WHERE id=?", (run_id,)).fetchone() is None:
                _deny("PUBLIC_LIVE_UNKNOWN_RESERVATION", 404)
            if row["run_id"] is not None and row["run_id"] != run_id:
                _deny("PUBLIC_LIVE_BINDING_CONFLICT", 409)
            existing = db.execute("SELECT id FROM public_live_reservations WHERE run_id=?", (run_id,)).fetchone()
            if existing is not None and existing["id"] != reservation_id:
                _deny("PUBLIC_LIVE_BINDING_CONFLICT", 409)
            if row["utc_day"] != config["utc_day"]:
                _deny("PUBLIC_LIVE_RESERVATION_EXPIRED", 409)
            db.execute("UPDATE public_live_reservations SET run_id=? WHERE id=?", (run_id, reservation_id))
            return self._result(db.execute("SELECT * FROM public_live_reservations WHERE id=?", (reservation_id,)).fetchone())

    def allow_ai(self, run_id, phase_key="investigation"):
        """Consume a one-use phase permit before dispatch; never refund it.

        Pass stable keys (e.g. model-1..3). An identical key is denied rather
        than returned as a reusable permit. Midnight expires unused admission
        reservations, so yesterday's budget cannot fund extra calls today.
        ModelAllowance must still approve the dispatch independently.
        """
        if not isinstance(phase_key, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", phase_key):
            _deny("PUBLIC_LIVE_AI_PHASE_INVALID", 400)
        with self.store.connect(write=True) as db:
            config = self._config()
            self._active(config)
            self._clock_order(db, config["now"])
            row = db.execute("SELECT * FROM public_live_reservations WHERE run_id=?", (run_id,)).fetchone()
            if row is None:
                _deny("PUBLIC_LIVE_UNKNOWN_RESERVATION", 404)
            if row["utc_day"] != config["utc_day"]:
                _deny("PUBLIC_LIVE_RESERVATION_EXPIRED", 409)
            if db.execute("SELECT COUNT(*) FROM public_live_reservations").fetchone()[0] > config["authorized_runs"]:
                _deny("PUBLIC_LIVE_OWNER_LIMIT")
            daily = self._daily(db, config)
            if daily["runs"] > config["daily_runs"]:
                _deny("PUBLIC_LIVE_DAILY_RUN_LIMIT")
            if daily["micro_usd"] > config["daily_micro_usd"]:
                _deny("PUBLIC_LIVE_DAILY_BUDGET")
            if db.execute("""SELECT 1 FROM public_live_ai_phases
                    WHERE reservation_id=? AND phase_key=?""", (row["id"], phase_key)).fetchone():
                _deny("PUBLIC_LIVE_AI_PHASE_ALREADY_USED", 409)
            calls = db.execute("SELECT COUNT(*) FROM public_live_ai_phases WHERE reservation_id=?", (row["id"],)).fetchone()[0]
            if calls >= MAX_AI_CALLS:
                _deny("PUBLIC_LIVE_AI_CALL_LIMIT")
            db.execute("""INSERT INTO public_live_ai_phases
                (reservation_id,phase_key,call_index,reserved_micro_usd,created_at) VALUES(?,?,?,?,?)""",
                (row["id"], phase_key, calls + 1, AI_CALL_MICRO_USD, config["now"]))
            return {"reservation_id": row["id"], "phase_key": phase_key, "call_index": calls + 1,
                    "reserved_micro_usd": AI_CALL_MICRO_USD}

    def snapshot(self):
        """Safe status/config only; no IPs, session hashes, run IDs or secrets."""
        config = self._config()
        with self.store.connect() as db:
            daily = self._daily(db, config)
            total = db.execute("SELECT COUNT(*) FROM public_live_reservations").fetchone()[0]
        return {**{key: value for key, value in config.items() if key != "now"},
                "reserved_runs": total, "daily_reserved_runs": daily["runs"],
                "daily_reserved_micro_usd": daily["micro_usd"],
                "remaining_authorized_runs": max(0, config["authorized_runs"] - total),
                "legacy_model_allowance": "required_separately_unchanged"}
