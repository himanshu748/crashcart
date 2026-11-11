"""Owner-scoped public Sandbox flow, disabled until a finite grant is configured.

This is a separate entry point, not an expansion of the operator API. Static
judge export remains keyless. Existing payment, webhook and AI validators decide
the evidence; this module only orchestrates them and projects public fields.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import hmac
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import subprocess
import sys
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .investigator import Investigation, StructuredModel
from .model_allowance import ModelAllowanceError, _locked
from .monitor_ingress import BoundedHTTPServer, IngressLimits, WebhookLimiter
from .paypal import PayPalError, PayPalSandbox, parse_webhook_event
from .public_live_limits import Limits, PublicLiveLimitError
from .service import MerchantService
from .store import Store

RUN_ID = re.compile(r"run_[a-f0-9]{32}")
COOKIE = "crashcart_judge"
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "EXPIRED"}
RUN_SECONDS = 600
SESSION_SECONDS = 7200
ROOT = Path(__file__).resolve().parents[1]
ERROR_TEXT = {
    "PUBLIC_LIVE_PAUSED": "Live runs paused, showing saved replay.",
    "PUBLIC_LIVE_IP_LIMIT": "This connection has reached its hourly test limit. Open the saved replay.",
    "PUBLIC_LIVE_OWNER_LIMIT": "The authorized test allowance is used. Open the saved replay.",
    "PUBLIC_LIVE_DAILY_RUN_LIMIT": "Today's test limit is reached. Open the saved replay.",
    "PUBLIC_LIVE_DAILY_BUDGET": "Today's AI allowance is reserved. Open the saved replay.",
    "PUBLIC_LIVE_MODEL_CAPACITY": "The available AI allowance is already reserved. Open the saved replay.",
    "WEBHOOK_NOT_CONFIRMED": "PayPal's verified payment notification did not arrive in time. Open the saved replay.",
    "BUYER_APPROVAL_REQUIRED": "PayPal has not confirmed buyer approval. Return to PayPal or open the saved replay.",
    "PAYPAL_ORDER_UNAVAILABLE": "PayPal could not start this Sandbox checkout. Open the saved replay instead.",
    "PAYPAL_CONFIRMATION_UNAVAILABLE": "PayPal confirmation failed or timed out. This checkout will not be retried automatically. Open the saved replay.",
    "INVESTIGATION_INCOMPLETE": "The AI investigation could not finish. The saved payment records are retained; open the replay.",
    "RUN_TIMEOUT": "This test took too long. Its saved payment records are retained; open the replay.",
    "CANCELLED": "The test checkout was cancelled. Open the saved replay whenever you like.",
}


class LiveError(Exception):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.code, self.status = code, status


def safe_error(code):
    return {"code": code, "message": ERROR_TEXT.get(code, "This live test could not finish. Open the saved replay.")}


def timestamp(value):
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.utcoffset() is None:
        raise ValueError("Timezone required")
    return stamp


def approval_link(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise LiveError("INVALID_APPROVAL_URL")
    url = urlsplit(value)
    if (url.scheme != "https" or url.hostname not in {"www.sandbox.paypal.com", "sandbox.paypal.com"}
            or url.username or url.password or url.port not in (None, 443) or url.fragment
            or url.path not in {"/checkoutnow", "/webapps/hermes"}):
        raise LiveError("INVALID_APPROVAL_URL")
    return value


class Controller:
    def __init__(self, store, environ, *, dispatch=None, service_factory=None,
                 investigation_factory=None, clock=time.time, sleep=time.sleep):
        self.store, self.env, self.clock, self.sleep = store, environ, clock, sleep
        self.limits = Limits(store, environ, clock=clock)
        self.service_factory = service_factory
        self.investigation_factory = investigation_factory
        self.dispatch = dispatch or self.spawn
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="judge-sandbox")
        self.submit_lock = threading.Lock()
        self.webhook_limiter = WebhookLimiter(IngressLimits(global_burst=4, global_per_second=.2,
            store_burst=2, store_per_second=.1, max_store_buckets=8))
        origin = environ.get("CRASHCART_PUBLIC_URL", "https://crashcart.32.193.44.79.sslip.io").rstrip("/")
        parsed = urlsplit(origin)
        if (parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password
                or not ((parsed.scheme == "https" and parsed.hostname == "crashcart.32.193.44.79.sslip.io"
                         and parsed.port in (None, 443))
                        or (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost"}))):
            raise LiveError("PUBLIC_ORIGIN_INVALID")
        self.origin = origin
        secret = environ.get("CRASHCART_PUBLIC_SESSION_SECRET", "")
        # A paused server may show the replay without credentials. No public run
        # is enabled without an operator-provided stable session secret.
        self.secret = secret if len(secret) >= 32 else secrets.token_urlsafe(48)
        self.stable_secret = len(secret) >= 32
        with store.connect(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS public_live_runs(
                run_id TEXT PRIMARY KEY REFERENCES runs(id),owner TEXT NOT NULL,
                state TEXT NOT NULL,approval_url TEXT,created_at REAL NOT NULL,
                expires_at REAL NOT NULL,error_code TEXT,phase TEXT,
                phase_started REAL,result_json TEXT)""")

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)

    def digest(self, value):
        return hmac.new(self.secret.encode(), value.encode(), hashlib.sha256).hexdigest()

    def session(self, cookie_header, *, create=False):
        # Anonymous configuration reads mint no durable rows. The versioned
        # cookie authenticates only its random nonce and bounded expiration;
        # owner and CSRF identities use separate HMAC domains and contain no PII.
        token = None
        try:
            entry = SimpleCookie(cookie_header or "").get(COOKIE)
            match = re.fullmatch(r"v1\.([1-9][0-9]{8,11})\.([A-Za-z0-9_-]{43})\.([a-f0-9]{64})",
                                 entry.value) if entry else None
            if match:
                expiry = int(match[1])
                payload = entry.value.rsplit('.', 1)[0]
                authenticated = hmac.compare_digest(match[3], self.digest("session:" + payload))
                now = self.clock()
                if authenticated and now < expiry <= now + SESSION_SECONDS:
                    token = entry.value
        except (CookieError, ValueError, TypeError):
            pass
        if token:
            return self.digest("owner:" + token), self.digest("csrf:" + token), None
        if not create:
            raise LiveError("SESSION_REQUIRED", 401)
        payload = f"v1.{int(self.clock()) + SESSION_SECONDS}.{secrets.token_urlsafe(32)}"
        token = payload + "." + self.digest("session:" + payload)
        owner = self.digest("owner:" + token)
        secure = "; Secure" if self.origin.startswith("https://") else ""
        cookie = f"{COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_SECONDS}{secure}"
        return owner, self.digest("csrf:" + token), cookie

    def configured(self, *, check_capacity=True):
        policy = self.limits.snapshot()
        if not policy["enabled"] or not self.stable_secret:
            raise LiveError("PUBLIC_LIVE_PAUSED")
        required = ("PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "PAYPAL_WEBHOOK_ID", "MODAL_API_KEY")
        if (any(not self.env.get(key) for key in required)
                or self.env.get("CRASHCART_ALLOW_SANDBOX") != "1"
                or self.env.get("CRASHCART_ALLOW_MODEL") != "1"
                or self.env.get("CRASHCART_MODEL_PROVIDER") != "modal"):
            raise LiveError("PUBLIC_LIVE_PAUSED")
        from .model_transport import configuration
        try:
            if configuration(self.env).provider != "modal":
                raise LiveError("PUBLIC_LIVE_PAUSED")
            path = Path(self.env.get("CRASHCART_MODEL_ALLOWANCE_PATH", ""))
            if not path.is_absolute():
                raise LiveError("PUBLIC_LIVE_PAUSED")
            if check_capacity:
                with self.store.connect() as db:
                    self.capacity(db)
            else:
                with _locked(path):
                    pass  # Validate the existing private ledger; never initialize it.
        except (ModelAllowanceError, OSError, ValueError):
            raise LiveError("PUBLIC_LIVE_PAUSED") from None
        return policy

    def capacity(self, db):
        # Unknown, failed and cancelled attempts retain their entire hold.
        # Only a proven completed investigation releases pending capacity;
        # actual used calls remain charged in the unchanged provider ledger.
        pending = db.execute("""SELECT COUNT(*) FROM public_live_reservations r
            LEFT JOIN public_live_runs l ON l.run_id=r.run_id
            WHERE l.run_id IS NULL OR l.state!='COMPLETED'""").fetchone()[0]
        required = 3 * (pending + 1)
        with _locked(Path(self.env["CRASHCART_MODEL_ALLOWANCE_PATH"])) as ledger:
            spent = Decimal(0)
            for call in ledger["calls"]:
                usage = call.get("usage") or {}
                derived = Decimal(usage.get("prompt_tokens", 0)) * Decimal('.30') + Decimal(
                    usage.get("completion_tokens", 0)) * Decimal('1.20')
                spent += max(Decimal(40000), Decimal(str(call.get("observed_rate_cost_micro_usd", 0))), derived)
            if (any(call['state'] == 'RESERVED' for call in ledger['calls'])
                    or ledger['call_limit'] - len(ledger['calls']) < required
                    or spent + required * 40000 > ledger['ceiling_micro_usd']):
                raise LiveError("PUBLIC_LIVE_MODEL_CAPACITY", 429)

    def configuration(self):
        try:
            policy = self.configured()
            enabled = policy["remaining_authorized_runs"] > 0
        except Exception:
            enabled = False
        return {"enabled": enabled, "reason": None if enabled else "PUBLIC_LIVE_PAUSED",
                "mode": "LIVE_SANDBOX" if enabled else "SAVED_REPLAY", "replay_url": "demo.html"}

    def row(self, run_id, owner=None):
        if not RUN_ID.fullmatch(run_id):
            raise LiveError("UNKNOWN_RUN", 404)
        with self.store.connect() as db:
            row = db.execute("SELECT * FROM public_live_runs WHERE run_id=?", (run_id,)).fetchone()
        if not row or (owner is not None and not hmac.compare_digest(row["owner"], owner)):
            raise LiveError("UNKNOWN_RUN", 404)
        return dict(row)

    def update(self, run_id, state, **fields):
        allowed = {"approval_url", "error_code", "result_json", "phase", "phase_started"}
        if set(fields) - allowed:
            raise ValueError("Private lifecycle field")
        with self.store.connect(write=True) as db:
            row = db.execute("SELECT state,expires_at FROM public_live_runs WHERE run_id=?", (run_id,)).fetchone()
            if not row or row["state"] in TERMINAL:
                return False
            if self.clock() >= row["expires_at"]:
                state, fields = "EXPIRED", {"error_code": "RUN_TIMEOUT"}
            pairs = {"state": state, **fields}
            db.execute("UPDATE public_live_runs SET " + ",".join(key + "=?" for key in pairs) + " WHERE run_id=?",
                       (*pairs.values(), run_id))
        return state not in {"EXPIRED", "CANCELLED", "FAILED"}

    def active(self, run_id):
        row = self.row(run_id)
        if row["state"] in TERMINAL or self.clock() >= row["expires_at"]:
            raise LiveError("RUN_TIMEOUT")
        # Check the kill switch without requiring three unused legacy calls in
        # the middle of an already-budgeted investigation.
        config = self.limits._config()
        if not config["enabled"]:
            raise LiveError("PUBLIC_LIVE_PAUSED")

    def start(self, owner, ip, idempotency):
        with self.submit_lock:
            self.configured(check_capacity=False)
            reservation = self.limits.admit(ip, owner, idempotency, capacity_check=self.capacity)
            if not reservation["created"]:
                if not reservation["run_id"]:
                    raise LiveError("PRIOR_START_INCOMPLETE")
                return self.status(reservation["run_id"], owner)
            run = self.store.create_run("One ticket within 60 seconds of confirmed payment.",
                mode="LIVE_SANDBOX", fault={"kind": "response_loss", "merchant": "defective"},
                budget={"max_attempts": 3, "max_model_calls": 3, "max_seconds": 90, "max_browser_sessions": 0})
            with self.store.connect(write=True) as db:
                db.execute("""INSERT INTO public_live_runs
                    (run_id,owner,state,created_at,expires_at,phase,phase_started)
                    VALUES(?,?,?,?,?,?,?)""", (run["id"], owner, "CREATING", self.clock(),
                                               self.clock() + RUN_SECONDS, "create", self.clock()))
            self.limits.bind(reservation["id"], run["id"])
            self.dispatch(run["id"], "create")
            return self.status(run["id"], owner)

    def confirm(self, run_id, owner):
        row = self.row(run_id, owner)
        if row["state"] in TERMINAL:
            return self.status(run_id, owner)
        try:
            self.active(run_id)
        except LiveError:
            # A concurrent phase may have completed between the first read
            # and the guard. Returning retained results never authorizes work.
            if self.row(run_id, owner)["state"] in TERMINAL:
                return self.status(run_id, owner)
            raise
        with self.store.connect(write=True) as db:
            changed = db.execute("""UPDATE public_live_runs SET state='CONFIRMING',phase='confirm',phase_started=?
                WHERE run_id=? AND owner=? AND state='AWAITING_APPROVAL'""", (self.clock(), run_id, owner)).rowcount
        if changed:
            self.dispatch(run_id, "confirm")
        return self.status(run_id, owner)

    def cancel(self, run_id, owner):
        row = self.row(run_id, owner)
        if row["state"] not in TERMINAL:
            self.store.update_run(run_id, cancel_requested=1)
            self.update(run_id, "CANCELLED", error_code="CANCELLED")
        return self.status(run_id, owner)

    def payment_webhook(self, run_id):
        purchase = self.store.purchase_for_run(run_id)
        with self.store.connect() as db:
            rows = db.execute("SELECT event_id,payload_json FROM webhooks WHERE run_id=? AND verified=1", (run_id,)).fetchall()
        for row in rows:
            payload = json.loads(row["payload_json"])
            if (payload.get("event_type") == "PAYMENT.CAPTURE.COMPLETED"
                    and payload.get("order_id") == purchase["order_id"]
                    and payload.get("resource_id") == purchase["capture_id"] and purchase["payment_confirmed"]):
                return row["event_id"]
        return None

    def webhook_candidate(self, event):
        # Scope and throttle before any OAuth/signature-verification request.
        # These unsigned fields are only a cheap rejection filter, never proof.
        if not self.limits._config()['enabled']:
            raise LiveError('PUBLIC_LIVE_PAUSED')
        if (event.get('event_type') != 'PAYMENT.CAPTURE.COMPLETED'
                or not isinstance(event.get('id'), str) or not 1 <= len(event['id']) <= 200):
            raise LiveError('WEBHOOK_OUT_OF_SCOPE', 400)
        try:
            resource = event['resource']
            order = resource['supplementary_data']['related_ids']['order_id']
            capture = resource['id']
            if any(not isinstance(value, str) or not 1 <= len(value) <= 200 for value in (order, capture)):
                raise ValueError('identifier')
        except (KeyError, TypeError, ValueError):
            raise LiveError('WEBHOOK_OUT_OF_SCOPE', 400) from None
        with self.store.connect() as db:
            row = db.execute("""SELECT l.run_id,l.state,l.expires_at,p.capture_id FROM public_live_runs l
                JOIN purchases p ON p.run_id=l.run_id WHERE p.order_id=?""", (order,)).fetchone()
        if (not row or row['state'] not in {'CONFIRMING', 'WAITING_FOR_WEBHOOK', 'WAITING_FOR_PROMISE', 'INVESTIGATING', 'COMPLETED'}
                or self.clock() >= row['expires_at'] or (row['capture_id'] and row['capture_id'] != capture)):
            raise LiveError('WEBHOOK_OUT_OF_SCOPE', 400)
        if self.webhook_limiter.global_admit() or self.webhook_limiter.store_admit(row['run_id']):
            raise LiveError('WEBHOOK_RATE_LIMIT', 429)
        return row['run_id']

    def status(self, run_id, owner):
        row = self.row(run_id, owner)
        if row["state"] not in TERMINAL and self.clock() >= row["expires_at"]:
            self.update(run_id, "EXPIRED", error_code="RUN_TIMEOUT")
            row = self.row(run_id, owner)
        purchase = self.store.purchase_for_run(run_id)
        merchant = self.store.merchant_state(purchase["id"])
        result = json.loads(row["result_json"]) if row["result_json"] else {}
        steps, citations = [], []
        for event in self.store.get_events(run_id):
            if event["source"] != "investigator":
                continue
            payload = event["payload"]
            if event["event_type"] == "tool_observation" and payload.get("tool") in {"read_provider", "read_merchant"}:
                tool = payload["tool"]
                summary = ("Read the PayPal payment record." if tool == "read_provider" else "Read the linked ticket records.")
                citations.append({"id": event["id"], "kind": tool, "summary": summary})
                steps.append({"action": tool, "summary": summary, "evidence_ids": [event["id"]]})
            if event["event_type"] == "model_plan" and payload.get("plan", {}).get("tool") == "finish":
                known = {citation["id"] for citation in citations}
                claims = payload["plan"].get("findings", [])
                cited = sorted({identity for claim in claims for identity in claim.get("evidence_ids", []) if identity in known})
                steps.append({"action": "finish", "summary": "Finished with cited payment and ticket evidence.", "evidence_ids": cited})
        completed = purchase["capture_completed_at"]
        deadline = (timestamp(completed) + timedelta(seconds=60)).isoformat() if completed else None
        ticket_times = [ticket["created_at"] for ticket in merchant.get("tickets", [])]
        return {"run_id": run_id, "mode": "LIVE_SANDBOX", "state": row["state"],
                "approval_url": row["approval_url"] if row["state"] == "AWAITING_APPROVAL" else None,
                "payment": {"amount": purchase["amount"], "currency": purchase["currency"],
                            "status": purchase["payment_state"], "order_id": purchase["order_id"],
                            "capture_id": purchase["capture_id"], "completed_at": completed},
                "tickets": {"count": len(ticket_times), "created_at": ticket_times[0] if ticket_times else None},
                "deadline": deadline, "webhook": {"verified": bool(self.payment_webhook(run_id))},
                "investigation": {"status": result.get("status", "PENDING"), "steps": steps, "citations": citations},
                "verdict": result.get("final_verdict"), "error": safe_error(row["error_code"]) if row["error_code"] else None,
                "replay_url": "demo.html"}

    def timing(self, owner):
        with self.store.connect() as db:
            identities = [row[0] for row in db.execute("SELECT run_id FROM public_live_runs WHERE owner=? ORDER BY created_at DESC LIMIT 8", (owner,))]
        cases = []
        for run_id in identities:
            data = self.status(run_id, owner)
            cases.append({"run_id": run_id, "reference": "Sandbox checkout " + run_id[-8:],
                          "payment_completed_at": data["payment"]["completed_at"], "deadline": data["deadline"],
                          "ticket_created_at": data["tickets"]["created_at"], "ticket_count": data["tickets"]["count"],
                          "state": data["state"], "verdict": data["verdict"], "webhook_verified": data["webhook"]["verified"]})
        return {"mode": "LIVE_SANDBOX", "cases": cases}

    def service(self, run_id):
        controller = self
        class GuardedPayPal(PayPalSandbox):
            def __init__(self):
                super().__init__(environ=controller.env, timeout=8)

            def _request(self, *args, **kwargs):
                controller.active(run_id)
                return super()._request(*args, **kwargs)
        return self.service_factory(self.store) if self.service_factory else MerchantService(self.store, GuardedPayPal)

    def run_create(self, run_id):
        try:
            self.active(run_id)
            response = self.service(run_id).create_order(run_id)
            self.update(run_id, "AWAITING_APPROVAL", approval_url=approval_link(response.get("approval_url")))
        except PayPalError:
            self.update(run_id, "FAILED", error_code="PAYPAL_ORDER_UNAVAILABLE")
        except Exception as exc:
            self.fail(run_id, exc)

    def run_confirm(self, run_id):
        try:
            self.active(run_id)
            service = self.service(run_id)
            purchase = self.store.purchase_for_run(run_id)
            service.capture(run_id, purchase["order_id"])
            self.active(run_id)
            service.reconcile(run_id)
            if not self.store.purchase_for_run(run_id)["payment_confirmed"]:
                raise LiveError("PAYMENT_NOT_CONFIRMED")
            self.update(run_id, "WAITING_FOR_WEBHOOK")
            until = min(self.clock() + 90, self.row(run_id)["expires_at"])
            while not self.payment_webhook(run_id):
                self.active(run_id)
                if self.clock() >= until:
                    raise LiveError("WEBHOOK_NOT_CONFIRMED")
                self.sleep(.5)
            self.update(run_id, "WAITING_FOR_PROMISE")
            completed = self.store.purchase_for_run(run_id)["capture_completed_at"]
            due = timestamp(completed).timestamp() + 60
            while self.clock() <= due:
                self.active(run_id)
                self.sleep(min(.5, due - self.clock() + .01))
            self.active(run_id)
            checked = service.reconcile(run_id)
            if checked.get("verdict") not in {"FAIL", "PASS"}:
                raise LiveError("PAYMENT_CHECK_INCOMPLETE")
            self.update(run_id, "INVESTIGATING")
            controller = self
            class LimitedModel(StructuredModel):
                def __init__(self):
                    super().__init__(environ=controller.env)
                    self.ordinal = 0

                def complete(self, *args, **kwargs):
                    controller.active(run_id)
                    self.ordinal += 1
                    controller.limits.allow_ai(run_id, "model-" + str(self.ordinal))
                    return super().complete(*args, **kwargs)
            investigator = (self.investigation_factory(self.store, service) if self.investigation_factory
                            else Investigation(self.store, service, model_factory=LimitedModel))
            result = investigator.run(run_id)
            if (result.get("status") != "COMPLETED" or result.get("model_mode") != "LIVE_MODEL"
                    or result.get("final_verdict", {}).get("verdict") not in {"PASS", "FAIL"}
                    or not self.payment_webhook(run_id)):
                raise LiveError("INVESTIGATION_INCOMPLETE")
            evidence, cited = {}, set()
            for event in self.store.get_events(run_id):
                payload = event["payload"]
                if event["source"] != "investigator":
                    continue
                if event["event_type"] == "tool_observation" and payload.get("tool") in {"read_provider", "read_merchant"}:
                    evidence[payload["tool"]] = event["id"]
                if event["event_type"] == "model_plan" and payload.get("plan", {}).get("tool") == "finish":
                    cited = {identity for finding in payload["plan"].get("findings", [])
                             if finding.get("kind") == "observed" for identity in finding.get("evidence_ids", [])}
            if set(evidence) != {"read_provider", "read_merchant"} or not set(evidence.values()).issubset(cited):
                raise LiveError("INVESTIGATION_CITATIONS_REQUIRED")
            # Publish only a bounded summary; raw prompts/wire responses remain private.
            public = {"status": result["status"], "final_verdict": {
                key: result["final_verdict"].get(key) for key in ("verdict", "signature", "reason", "deadline")}}
            self.update(run_id, "COMPLETED", result_json=json.dumps(public, allow_nan=False))
        except PayPalError:
            self.update(run_id, "FAILED", error_code="PAYPAL_CONFIRMATION_UNAVAILABLE")
        except Exception as exc:
            self.fail(run_id, exc)

    def fail(self, run_id, exc):
        code = getattr(exc, "code", "LIVE_STEP_FAILED")
        self.update(run_id, "FAILED", error_code=code if code in ERROR_TEXT else "LIVE_STEP_FAILED")

    def spawn(self, run_id, phase):
        self.pool.submit(self._child, run_id, phase)

    def _child(self, run_id, phase):
        command = [sys.executable, "-m", "crashcart.public_live", "--db", str(self.store.path), "--work", run_id, phase]
        try:
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, env=dict(self.env), start_new_session=True)
        except OSError:
            self.update(run_id, "FAILED", error_code="LIVE_STEP_FAILED")
            return
        try:
            proc.wait(timeout=40 if phase == "create" else 240)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            self.update(run_id, "FAILED", error_code="RUN_TIMEOUT")
        if proc.returncode:
            self.update(run_id, "FAILED", error_code="LIVE_STEP_FAILED")


class LiveHandler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    @property
    def controller(self):
        return self.server.controller

    def send(self, status, value, kind="application/json", headers=None):
        body = value if isinstance(value, bytes) else json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        for key, val in {"Content-Type": kind, "Content-Length": str(len(body)), "Cache-Control": "no-store",
                         "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
                         "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self'; font-src 'self'; base-uri 'none'; "
                         "form-action 'none'; frame-ancestors 'none'",
                         **(headers or {})}.items():
            self.send_header(key, val)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def session(self, create=False):
        return self.controller.session(self.headers.get("Cookie"), create=create)

    def ip(self):
        peer = ipaddress.ip_address(self.client_address[0])
        forwarded = self.headers.get("X-CrashCart-Client-IP")
        if forwarded:
            if not peer.is_loopback or self.controller.env.get("CRASHCART_TRUST_LOCAL_PROXY") != "1":
                raise LiveError("UNTRUSTED_PROXY", 400)
            peer = ipaddress.ip_address(forwarded)
        return str(peer)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            path = urlsplit(self.path).path
            if path == "/api/live/config":
                _, csrf, cookie = self.session(True)
                return self.send(200, {**self.controller.configuration(), "csrf_token": csrf},
                                 headers={"Set-Cookie": cookie} if cookie else None)
            if path == "/api/live/timing":
                return self.send(200, self.controller.timing(self.session()[0]))
            match = re.fullmatch(r"/api/live/runs/(run_[a-f0-9]{32})", path)
            if match:
                return self.send(200, self.controller.status(match[1], self.session()[0]))
            if path in {"/return", "/cancel"}:
                query = parse_qs(urlsplit(self.path).query)
                run_id = query.get("run", [""])[0]
                self.controller.row(run_id, self.session()[0])
                destination = "/live.html?run=" + run_id + ("&cancel=1" if path == "/cancel" else "&approval_return=1")
                return self.send(303, b"", "text/plain", {"Location": destination})
            name = {"/": "index.html", "/product": "product.html", "/example": "demo.html",
                    "/integrations": "integrations.html"}.get(path, path.removeprefix("/"))
            if name in self.server.files:
                kind, body = self.server.files[name]
                return self.send(200, body, kind)
            return self.send(404, {"error": safe_error("NOT_FOUND"), "replay_url": "/demo.html"})
        except (LiveError, PublicLiveLimitError) as exc:
            self.send(exc.status, {"error": safe_error(exc.code), "replay_url": "/demo.html"})
        except Exception:
            self.send(503, {"error": safe_error("LIVE_STEP_FAILED"), "replay_url": "/demo.html"})

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                raise LiveError("JSON_REQUIRED", 415)
            if self.headers.get("Transfer-Encoding"):
                raise LiveError("INVALID_BODY", 400)
            sizes = self.headers.get_all("Content-Length", [])
            if len(sizes) != 1 or not re.fullmatch(r"[1-9][0-9]{0,5}", sizes[0]) or int(sizes[0]) > 131072:
                raise LiveError("INVALID_BODY", 400)
            raw = self.rfile.read(int(sizes[0]))
            if len(raw) != int(sizes[0]):
                raise LiveError("INVALID_BODY", 400)
            if path == "/api/live/webhook":
                return self.webhook(raw)
            if self.headers.get("Origin") != self.controller.origin:
                raise LiveError("ORIGIN_REJECTED", 403)
            owner, csrf, _ = self.session()
            supplied = self.headers.get("X-CSRF-Token", "")
            if not supplied or not hmac.compare_digest(csrf, supplied):
                raise LiveError("CSRF_REJECTED", 403)
            if json.loads(raw) != {}:
                raise LiveError("EMPTY_ACTION_BODY_REQUIRED", 400)
            if path == "/api/live/runs":
                result = self.controller.start(owner, self.ip(), self.headers.get("Idempotency-Key", ""))
            else:
                match = re.fullmatch(r"/api/live/runs/(run_[a-f0-9]{32})/(confirm|cancel)", path)
                if not match:
                    raise LiveError("NOT_FOUND", 404)
                result = getattr(self.controller, match[2])(match[1], owner)
            self.send(202, result)
        except (LiveError, PublicLiveLimitError) as exc:
            self.send(exc.status, {"error": safe_error(exc.code), "replay_url": "demo.html"})
        except (ValueError, TypeError):
            self.send(400, {"error": safe_error("INVALID_REQUEST"), "replay_url": "demo.html"})
        except Exception:
            self.send(503, {"error": safe_error("LIVE_STEP_FAILED"), "replay_url": "demo.html"})

    def webhook(self, raw):
        event = parse_webhook_event(raw)
        required = {"paypal-auth-algo", "paypal-cert-url", "paypal-transmission-id", "paypal-transmission-sig", "paypal-transmission-time"}
        headers = {key.lower(): val for key, val in self.headers.items() if key.lower() in required}
        if set(headers) != required:
            raise LiveError("WEBHOOK_SIGNATURE_REQUIRED", 400)
        self.controller.webhook_candidate(event)
        # Synchronous verification runs in a hard-bounded child, never a
        # request-supplied transport or a trusted callback-query claim.
        packet = json.dumps({"headers": headers, "raw": raw.decode("utf-8")}).encode()
        command = [sys.executable, "-m", "crashcart.public_live", "--db", str(self.controller.store.path), "--webhook"]
        proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=dict(self.controller.env), start_new_session=True)
        try:
            output, _ = proc.communicate(packet, timeout=7)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.communicate()
            raise LiveError("WEBHOOK_VERIFICATION_TIMEOUT") from None
        if proc.returncode != 0:
            raise LiveError("WEBHOOK_SIGNATURE_REJECTED", 400)
        verified = json.loads(output)
        if verified != {"verified": True, "event_id": event.get("id")}:
            raise LiveError("WEBHOOK_SIGNATURE_REJECTED", 400)
        self.send(200, verified)


def private_store(path):
    path = Path(path)
    if not path.is_absolute():
        raise LiveError("PRIVATE_DATABASE_REQUIRED")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.parent.is_symlink():
        raise LiveError("PRIVATE_DATABASE_REQUIRED")
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o022:
        raise LiveError("PRIVATE_DATABASE_REQUIRED")
    # Reject a shared existing inode; chmod must never conceal an unsafe input.
    if path.exists():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise LiveError("PRIVATE_DATABASE_REQUIRED")
    os.umask(0o077)
    store = Store(path)
    path.chmod(0o600)
    return store


def make_server(address, controller, files=None):
    if not ipaddress.ip_address(address[0]).is_loopback:
        raise LiveError("LOOPBACK_BIND_REQUIRED")
    if files is None:
        from .judge import prepare_review
        files = prepare_review()
    server = BoundedHTTPServer(address, LiveHandler, limits=IngressLimits(max_handlers=12, global_burst=40))
    server.controller, server.files = controller, files
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--port", type=int, default=8767)
    parser.add_argument("--work", nargs=2, metavar=("RUN", "PHASE"))
    parser.add_argument("--webhook", action="store_true")
    args = parser.parse_args()
    store = private_store(args.db)
    if args.webhook:
        try:
            packet = json.loads(sys.stdin.buffer.read(1100001))
            raw = packet["raw"].encode()
            event = parse_webhook_event(raw)
            accepted = MerchantService(store).webhook(packet["headers"], event, raw_body=raw)
            print(json.dumps({"verified": accepted["verified"], "event_id": accepted["event_id"]}))
            return
        except Exception:
            raise SystemExit(1) from None
    controller = Controller(store, os.environ)
    if args.work:
        run_id, phase = args.work
        row = controller.row(run_id)
        if row["phase"] != phase or row["state"] in TERMINAL:
            raise SystemExit(1)
        (controller.run_create if phase == "create" else controller.run_confirm)(run_id)
        controller.close()
        return
    server = make_server(("127.0.0.1", args.port), controller)
    print(f"CrashCart judge API on 127.0.0.1:{args.port}; live runs default paused", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        controller.close()


if __name__ == "__main__":
    main()
