"""Bounded KERNEL browser execution. Injected transports always produce LOCAL_TEST.

Only fixed, reviewed scenarios are exposed. This module does not decide payment
truth, mark requirements, configure ingress, or grant its own usage allowance.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4


API = "https://api.onkernel.com"
SCENARIOS = frozenset({"observe", "checkout", "confirm_return", "cancel_return"})
PAYPAL_HOSTS = ("sandbox.paypal.com", "*.sandbox.paypal.com", "*.paypalobjects.com")
MAX_JSON = 2 * 1024 * 1024
MAX_VIDEO = 64 * 1024 * 1024
REMOTE_STAGES = frozenset({"RUN_READ", "RUN_CORRELATION", "NAVIGATE", "RETURN_VALIDATION",
                          "RUN_DOM", "INITIAL_IDLE", "DOM_CORRELATION", "CHECKOUT_ACTION",
                          "CHECKOUT_RESPONSE", "ORDER_VALIDATION", "APPROVAL_NAVIGATION",
                          "CAPTURE_ACTION", "CAPTURE_RESPONSE", "CAPTURE_IDLE", "OBSERVATION"})
REMOTE_ERRORS = frozenset({"RUN_UNAVAILABLE", "CORRELATION_FAILED", "OWNED_ORIGIN_REQUIRED",
                          "INVALID_RETURN", "DOM_CORRELATION_FAILED", "ALREADY_PAID",
                          "CHECKOUT_FAILED", "ORDER_CORRELATION_FAILED", "SANDBOX_APPROVAL_REQUIRED",
                          "SCENARIO_DEADLINE", "TIMEOUT", "REMOTE_ERROR"})


class KernelError(RuntimeError):
    def __init__(self, code, status=None):
        self.code, self.status = code, status
        super().__init__(code)  # Never include API bodies, URLs, tokens or stderr.


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise KernelError("INVALID_ID")
    return value


def _date(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.utcoffset() is None:
            raise ValueError()
        return date
    except (TypeError, ValueError, AttributeError):
        raise KernelError("INVALID_TIMESTAMP") from None


def _now():
    return datetime.now(timezone.utc).isoformat()


def owned_origin(value, resolver=socket.getaddrinfo):
    """An exact configured HTTPS origin plus public DNS; not proof of ownership."""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (parsed.scheme != "https" or parsed.username or parsed.password or
                parsed.port not in (None, 443) or parsed.path not in ("", "/") or
                parsed.query or parsed.fragment or value != value.strip() or
                not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", host) or
                host.endswith((".localhost", ".local", ".internal", ".test", ".invalid"))):
            raise ValueError()
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError()
        addresses = resolver(host, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError()
    except (ValueError, TypeError, OSError):
        raise KernelError("OWNED_PUBLIC_HTTPS_TARGET_REQUIRED") from None
    return "https://" + host


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _transport(request, timeout, limit):
    """One HTTP attempt; never forward the API bearer to a redirected host."""
    try:
        response = build_opener(_NoRedirect()).open(request, timeout=timeout)
    except HTTPError as exc:
        response = exc
    with response:
        body = response.read(limit + 1)
        if len(body) > limit:
            raise KernelError("RESPONSE_TOO_LARGE")
        return response.status, body, dict(response.headers)


class KernelBrowser:
    def __init__(self, *, allowance_path, state_dir="var/kernel", environ=None,
                 transport=None, resolver=socket.getaddrinfo):
        self._env = dict(os.environ if environ is None else environ)
        self._transport = transport or _transport
        self._local_test = transport is not None
        self._resolver = resolver
        self._allowance_path = Path(allowance_path)
        self._state_dir = Path(state_dir)

    def _reserve(self, identity):
        if self._env.get("CRASHCART_ALLOW_KERNEL") != "1":
            raise KernelError("KERNEL_DISABLED")
        if not self._env.get("KERNEL_API_KEY") or not self._env.get("CRASHCART_OPERATOR_TOKEN"):
            raise KernelError("MISSING_CONFIGURATION")
        origin = owned_origin(self._env.get("CRASHCART_PUBLIC_URL", ""), self._resolver)
        try:
            grant = json.loads(self._allowance_path.read_text())
            if set(grant) != {"approval_id", "owned_origin", "expires_at", "max_session_seconds", "scenarios"}:
                raise ValueError()
            _id(grant["approval_id"])
            if (grant["owned_origin"] != origin or _date(grant["expires_at"]) <= datetime.now(timezone.utc) or
                    type(grant["max_session_seconds"]) is not int or
                    not 10 <= grant["max_session_seconds"] <= 300 or
                    not isinstance(grant["scenarios"], list) or not grant["scenarios"] or
                    not set(grant["scenarios"]) <= SCENARIOS):
                raise ValueError()
            if (_date(grant["expires_at"]) - datetime.now(timezone.utc)).total_seconds() < grant["max_session_seconds"]:
                raise ValueError()
        except (OSError, ValueError, TypeError, KernelError):
            raise KernelError("EXPLICIT_ALLOWANCE_REQUIRED") from None
        for key, prefix in (("run_id", "run_"), ("purchase_id", "purchase_")):
            if not re.fullmatch(prefix + r"[a-f0-9]{32}", str(identity.get(key, ""))):
                raise KernelError("INVALID_CORRELATION")
        if identity.get("mode") not in ("LIVE_SANDBOX", "FRESH_SANDBOX"):
            raise KernelError("INVALID_SOURCE_MODE")
        if identity.get("order_id") is not None:
            _id(identity["order_id"])
        self._state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        ledger = self._state_dir / (grant["approval_id"] + ".reservation.json")
        name = "crashcart-" + uuid4().hex
        try:
            fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            raise KernelError("ALLOWANCE_ALREADY_RESERVED") from None
        with os.fdopen(fd, "w") as file:
            json.dump({"grant": grant, "identity": identity, "session_name": name, "reserved_at": _now()}, file)
            file.flush()
            os.fsync(file.fileno())
        # Never release a reservation after ambiguous creation or a failed run.
        return origin, grant, name

    def session(self, *, run_id, purchase_id, mode, order_id=None):
        return KernelSession(self, {"run_id": run_id, "purchase_id": purchase_id,
                                    "order_id": order_id, "mode": mode})

    def _request(self, method, path, body=None, *, binary=False, timeout=25, expected=200):
        request = Request(API + path, method=method, data=None if body is None else json.dumps(body).encode(),
                          headers={"Authorization": "Bearer " + self._env["KERNEL_API_KEY"],
                                   "Content-Type": "application/json", "Accept": "video/mp4" if binary else "application/json"})
        try:
            status, raw, headers = self._transport(request, timeout, MAX_VIDEO if binary else MAX_JSON)
            if not isinstance(raw, bytes) or len(raw) > (MAX_VIDEO if binary else MAX_JSON):
                raise KernelError("RESPONSE_TOO_LARGE")
            if status != expected:
                raise KernelError("KERNEL_HTTP_ERROR", status)
            if binary:
                if len(raw) < 12 or raw[4:8] != b"ftyp":
                    raise KernelError("INVALID_RECORDING")
                return raw
            data = json.loads(raw) if raw else {}
            if not isinstance(data, dict):
                raise KernelError("MALFORMED_RESPONSE")
            return data
        except (TimeoutError, socket.timeout):
            raise KernelError("KERNEL_TIMEOUT") from None
        except (URLError, OSError):
            raise KernelError("KERNEL_NETWORK_ERROR") from None
        except (ValueError, TypeError):
            raise KernelError("MALFORMED_RESPONSE") from None


class KernelSession:
    def __init__(self, adapter, identity):
        self.adapter, self.identity = adapter, dict(identity)
        self.session_id = self.replay_id = self._name = None
        self._view_url = None
        self._closed = False
        self._timer = None
        self._lock = threading.RLock()
        self._step_lock = threading.Lock()
        self.receipt = {"schema_version": 1, "browser_kind": "KERNEL",
                        "mode": "LOCAL_TEST" if adapter._local_test else identity["mode"],
                        "identity": dict(identity), "observations": [], "cleanup": {},
                        "status": "NOT_STARTED", "recording_state": "NOT_STARTED", "payment_verdict": "NOT_EVALUATED"}

    def __enter__(self):
        # A watchdog must not delete a session while creation/recording creation
        # is still returning its ID; setup calls themselves have bounded timeouts.
        with self._lock:
            return self._start()

    def _start(self):
        self.origin, self.grant, self._name = self.adapter._reserve(self.identity)
        self.receipt.update(started_at=_now(), allowance_id=self.grant["approval_id"], session_name=self._name)
        self._persist()
        self._deadline = time.monotonic() + self.grant["max_session_seconds"]
        self._timer = threading.Timer(self.grant["max_session_seconds"], self.cancel, args=("TIMED_OUT",))
        self._timer.daemon = True
        self._timer.start()
        try:
            session = self.adapter._request("POST", "/browsers", {
                "name": self._name, "timeout_seconds": self.grant["max_session_seconds"], "headless": False,
                "network": {"allowed_hosts": [urlsplit(self.origin).hostname, *PAYPAL_HOSTS]},
                "tags": {"app": "crashcart", "run_id": self.identity["run_id"], "purchase_id": self.identity["purchase_id"]}},
                timeout=min(25, self.grant["max_session_seconds"]))
            self.session_id = _id(session.get("session_id"))
            self.receipt["session_id"] = self.session_id
            self._persist()
            # Never copy live/CDP/replay URLs, API logs or headers into receipts.
            self._view_url = session.get("browser_live_view_url")
            if self._execute(self._bootstrap(), timeout=10).get("authenticated") is not True:
                raise KernelError("REMOTE_AUTH_FAILED")
            self._ensure_open()
            self.receipt["recording_state"] = "START_REQUESTED"
            replay = self.adapter._request("POST", self._path + "/replays", {
                "framerate": 10, "max_duration_in_seconds": self.grant["max_session_seconds"], "record_audio": False},
                expected=201, timeout=max(1, min(10, int(self._deadline - time.monotonic()))))
            self.replay_id = _id(replay.get("replay_id"))
            self.receipt["replay_id"] = self.replay_id
            self.receipt["recording_state"] = "RECORDING"
            self.receipt["status"] = "ACTIVE"
            self._persist()
            self._ensure_open()
            return self
        except BaseException as exc:
            self.receipt["error"] = exc.code if isinstance(exc, KernelError) else "INTERRUPTED"
            self.close("FAILED")
            raise

    @property
    def _path(self):
        return "/browsers/" + _id(self.session_id or self._name)

    def _persist(self):
        """Private crash checkpoint; these unreviewed artifacts are not public proof."""
        path = self.adapter._state_dir / (self._name + ".receipt.json")
        temporary = path.with_suffix(".tmp")
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump(self.receipt, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)

    def _ensure_open(self):
        if self._closed:
            raise KernelError("SESSION_CLOSED")
        if time.monotonic() >= self._deadline:
            raise KernelError("SESSION_DEADLINE")

    def private_live_view_url(self):
        """Operator-only access for manual sandbox approval; never publish/log."""
        self._ensure_open()
        return self._view_url

    def _diagnose(self, scenario, stage, error, elapsed_ms, clock):
        # Separate operator-only artifact: never imported as browser/payment proof.
        # Callers supply only validated enums/integers, never a remote error string.
        diagnostic = {"schema_version": 1, "kind": "UNTRUSTED_REMOTE_DIAGNOSTIC",
                      "session_id": self.session_id, "scenario": scenario,
                      "stage": stage, "error": error, "elapsed_ms": elapsed_ms, "clock": clock}
        self._diagnostic_state = "UNAVAILABLE"
        try:
            target = self.adapter._state_dir / (self._name + ".diagnostic.json")
            temporary = target.with_suffix(".tmp")
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as file:
                json.dump(diagnostic, file, indent=2)
                file.flush()
                os.fsync(file.fileno())
            temporary.replace(target)
            self._diagnostic_state = "SAVED"
        except OSError:
            pass  # Diagnostic I/O cannot mask the scenario failure or skip cleanup.

    def _execute(self, code, timeout=20, scenario="bootstrap"):
        self._ensure_open()
        seconds = max(1, min(timeout, int(self._deadline - time.monotonic())))
        started = time.monotonic()
        result = self.adapter._request("POST", self._path + "/playwright/execute",
                                       {"code": code, "timeout_sec": seconds}, timeout=seconds + 5)
        self._ensure_open()
        if result.get("success") is not True or not isinstance(result.get("result"), dict):
            self._diagnose(scenario, "EXECUTE", "REMOTE_EXECUTION_FAILED",
                           max(0, min(20000, int((time.monotonic() - started) * 1000))), "ADAPTER_ELAPSED_CAPPED_20000")
            raise KernelError("REMOTE_SCENARIO_FAILED")
        value = result["result"]
        if "crashcart_failure" in value:
            diagnostic = value["crashcart_failure"]
            if (set(value) == {"crashcart_failure"} and isinstance(diagnostic, dict) and
                    set(diagnostic) == {"stage", "error", "elapsed_ms"} and
                    isinstance(diagnostic["stage"], str) and diagnostic["stage"] in REMOTE_STAGES and
                    isinstance(diagnostic["error"], str) and diagnostic["error"] in REMOTE_ERRORS and
                    type(diagnostic["elapsed_ms"]) is int and 0 <= diagnostic["elapsed_ms"] <= 20000):
                self._diagnose(scenario, diagnostic["stage"], diagnostic["error"], diagnostic["elapsed_ms"],
                               "REMOTE_ELAPSED_CAPPED_20000")
            else:
                self._diagnose(scenario, "EXECUTE", "MALFORMED_DIAGNOSTIC",
                               max(0, min(20000, int((time.monotonic() - started) * 1000))), "ADAPTER_ELAPSED_CAPPED_20000")
            raise KernelError("REMOTE_SCENARIO_FAILED")
        return value

    def _bootstrap(self):
        # context.request shares cookies; the operator token never enters the DOM.
        return """
const origin = ORIGIN;
const login = await context.request.post(origin + '/api/login', {data: {token: TOKEN}, timeout: 8000, maxRedirects: 0});
if (login.status() !== 200) throw new Error('AUTH_FAILED');
return {authenticated: true};
""".replace("ORIGIN", json.dumps(self.origin)).replace("TOKEN", json.dumps(self.adapter._env["CRASHCART_OPERATOR_TOKEN"]))

    def _code(self, scenario):
        config = json.dumps({**self.identity, "origin": self.origin, "scenario": scenario})
        # This is the entire remote tool vocabulary. No model-provided code/selectors.
        return "const cfg = " + config + ";\nconst knownErrors = " + json.dumps(sorted(REMOTE_ERRORS)) + ";\n" + r"""
const diagnosticStarted = performance.now();
// confirm_return shares one budget, leaving 1 s below the unchanged 20 s execute cap.
const confirmationDeadline = diagnosticStarted + 19000;
const waitBudget = () => {
  if (cfg.scenario !== 'confirm_return') return 8000;
  const remaining = confirmationDeadline - performance.now();
  if (remaining <= 0) throw new Error('SCENARIO_DEADLINE');
  return remaining;
};
let stage = 'RUN_READ';
try {
page.setDefaultTimeout(8000);
page.setDefaultNavigationTimeout(12000);
const check = async () => {
  stage = 'RUN_READ';
  const response = await context.request.get(cfg.origin + '/api/runs/' + cfg.run_id, {timeout: waitBudget(), maxRedirects: 0});
  if (response.status() !== 200) throw new Error('RUN_UNAVAILABLE');
  const data = await response.json();
  stage = 'RUN_CORRELATION';
  if (data.run.id !== cfg.run_id || data.purchase.id !== cfg.purchase_id || data.run.mode !== cfg.mode ||
      data.run.fixture_id !== 'workshop-v1' || data.purchase.amount !== 2900 || data.purchase.currency !== 'USD' ||
      (cfg.order_id && data.purchase.order_id !== cfg.order_id)) throw new Error('CORRELATION_FAILED');
  return data;
};
let data = await check();
if (cfg.scenario === 'observe' || cfg.scenario === 'checkout') {
  stage = 'NAVIGATE';
  await page.goto(cfg.origin + '/shop?run=' + cfg.run_id, {waitUntil: 'domcontentloaded'});
  if (new URL(page.url()).origin !== cfg.origin) throw new Error('OWNED_ORIGIN_REQUIRED');
} else {
  stage = 'RETURN_VALIDATION';
  const u = new URL(page.url());
  const expectedPath = cfg.scenario === 'confirm_return' ? '/return' : '/cancel';
  if (u.origin !== cfg.origin || u.pathname !== expectedPath || u.searchParams.get('run') !== cfg.run_id ||
      (expectedPath === '/return' && u.searchParams.get('token') !== cfg.order_id)) throw new Error('INVALID_RETURN');
}
stage = 'RUN_DOM';
// The selected case is visible; its original-reference disclosure stays closed.
await page.locator('#case[data-run-id="' + cfg.run_id + '"]').waitFor({timeout: waitBudget()});
stage = 'INITIAL_IDLE';
await page.locator('#busy').waitFor({state: 'hidden', timeout: waitBudget()});
stage = 'DOM_CORRELATION';
const journal = JSON.parse(await page.locator('#journal').textContent({timeout: waitBudget()}));
if (journal.purchase_id !== cfg.purchase_id || journal.order_id !== data.purchase.order_id ||
    await page.locator('#case').getAttribute('data-run-id', {timeout: waitBudget()}) !== cfg.run_id ||
    (await page.locator('#run-id').textContent({timeout: waitBudget()})).trim() !== cfg.run_id) throw new Error('DOM_CORRELATION_FAILED');
if (cfg.scenario === 'checkout') {
  if (data.purchase.payment_confirmed === 1) throw new Error('ALREADY_PAID');
  const responsePromise = page.waitForResponse(r => r.url() === cfg.origin + '/api/runs/' + cfg.run_id + '/order' && r.request().method() === 'POST');
  stage = 'CHECKOUT_ACTION';
  await page.locator('#checkout').click();
  stage = 'CHECKOUT_RESPONSE';
  const response = await responsePromise;
  if (response.status() !== 200) throw new Error('CHECKOUT_FAILED');
  const order = await response.json();
  data = await check();
  stage = 'ORDER_VALIDATION';
  if (!order.order_id || data.purchase.order_id !== order.order_id) throw new Error('ORDER_CORRELATION_FAILED');
  const approval = new URL(order.approval_url);
  if (approval.protocol !== 'https:' || !['www.sandbox.paypal.com', 'sandbox.paypal.com'].includes(approval.hostname) ||
      approval.searchParams.get('token') !== order.order_id) throw new Error('SANDBOX_APPROVAL_REQUIRED');
  stage = 'APPROVAL_NAVIGATION';
  await page.waitForURL(u => u.hostname === approval.hostname && u.searchParams.get('token') === order.order_id);
  return {run_id: data.run.id, purchase_id: data.purchase.id, order_id: data.purchase.order_id,
    path: '/checkoutnow', phase: 'AWAITING_MANUAL_SANDBOX_APPROVAL', ticket_id: null, observed_at: new Date().toISOString()};
}
if (cfg.scenario === 'confirm_return') {
  const captureResponse = page.waitForResponse(r => r.url() === cfg.origin + '/api/runs/' + cfg.run_id + '/capture' && r.request().method() === 'POST', {timeout: waitBudget()});
  // A failed click must not leave a later unhandled rejection. Await the original
  // promise below so its failure is still reported, with the same shared budget.
  void captureResponse.catch(() => {});
  stage = 'CAPTURE_ACTION';
  await page.locator('#capture').click({timeout: waitBudget()});
  stage = 'CAPTURE_RESPONSE';
  await captureResponse;
  stage = 'CAPTURE_IDLE';
  await page.locator('#busy').waitFor({state: 'hidden', timeout: waitBudget()});
  data = await check();
}
stage = 'OBSERVATION';
const j = JSON.parse(await page.locator('#journal').textContent({timeout: waitBudget()}));
const visibleTicket = await page.locator('#ticket-card').isVisible();
return {run_id: await page.locator('#case').getAttribute('data-run-id', {timeout: waitBudget()}), purchase_id: j.purchase_id, order_id: j.order_id,
  path: new URL(page.url()).pathname, phase: cfg.scenario, observed_at: new Date().toISOString(),
  ticket_id: visibleTicket ? (await page.locator('#ticket-id').innerText({timeout: waitBudget()})).trim() : null,
  run_state: await page.locator('#run-state').innerText({timeout: waitBudget()}), provider_title: await page.locator('#provider-title').innerText({timeout: waitBudget()}),
  merchant_title: await page.locator('#merchant-title').innerText({timeout: waitBudget()}), message: await page.locator('#message').innerText({timeout: waitBudget()}),
  verdict: await page.locator('#verdict').innerText({timeout: waitBudget()})};
} catch (error) {
  return {crashcart_failure: {stage,
    error: knownErrors.includes(error?.message) ? error.message : error?.name === 'TimeoutError' ? 'TIMEOUT' : 'REMOTE_ERROR',
    elapsed_ms: Math.max(0, Math.min(20000, Math.floor(performance.now() - diagnosticStarted)))}};
}
"""

    def perform(self, scenario):
        with self._step_lock:
            self._ensure_open()
            if scenario not in SCENARIOS or scenario not in self.grant["scenarios"]:
                raise KernelError("SCENARIO_NOT_ALLOWED")
            if scenario == "confirm_return" and not self.identity.get("order_id"):
                raise KernelError("ORDER_REQUIRED")
            try:
                result = self._execute(self._code(scenario), scenario=scenario)
                if (result.get("run_id") != self.identity["run_id"] or result.get("purchase_id") != self.identity["purchase_id"] or
                        self.identity.get("order_id") and result.get("order_id") != self.identity["order_id"]):
                    raise KernelError("CORRELATION_FAILED")
                _date(result.get("observed_at"))
                order = result.get("order_id")
                if order is not None:
                    _id(order)
                if scenario == "checkout" and not order:
                    raise KernelError("CORRELATION_FAILED")
                if result.get("ticket_id") is not None:
                    if not re.fullmatch(r"ticket_[a-f0-9]{32}", str(result["ticket_id"])):
                        raise KernelError("CORRELATION_FAILED")
                paths = {"observe": "/shop", "checkout": "/checkoutnow", "confirm_return": "/return", "cancel_return": "/cancel"}
                if result.get("path") != paths[scenario]:
                    raise KernelError("CORRELATION_FAILED")
                clean = {key: result.get(key) for key in ("run_id", "purchase_id", "order_id", "ticket_id", "observed_at", "path")}
                clean.update(scenario=scenario, received_at=_now(), session_id=self.session_id, replay_id=self.replay_id)
                for key in ("run_state", "provider_title", "merchant_title", "message", "verdict"):
                    value = str(result.get(key, ""))[:2000]
                    for secret in (self.adapter._env["KERNEL_API_KEY"], self.adapter._env["CRASHCART_OPERATOR_TOKEN"]):
                        value = value.replace(secret, "[redacted]")
                    value = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+|eyJ[A-Za-z0-9_.-]+", "[redacted]", value)
                    clean[key] = value
                with self._lock:
                    self._ensure_open()
                    self.identity["order_id"] = order
                    self.receipt["identity"]["order_id"] = order
                    self.receipt["observations"].append(clean)
                    self._persist()
                return clean
            except BaseException as exc:
                self.receipt["error"] = exc.code if isinstance(exc, KernelError) else "INTERRUPTED"
                self.close("FAILED")
                raise

    def cancel(self, reason="CANCELLED"):
        self.close(reason if reason in ("CANCELLED", "TIMED_OUT") else "CANCELLED")

    def close(self, status="OBSERVED"):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._timer:
                self._timer.cancel()
            self.receipt["status"] = status if self.receipt["observations"] or status != "OBSERVED" else "INCOMPLETE"
            if self.replay_id:
                path = self._path + "/replays/" + self.replay_id
                for label, method, endpoint in (("recording_stop", "POST", path + "/stop"), ("recording_download", "GET", path)):
                    try:
                        result = self.adapter._request(method, endpoint, binary=label == "recording_download", timeout=10)
                        if label == "recording_download":
                            target = self.adapter._state_dir / (self._name + ".private.mp4")
                            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                            with os.fdopen(fd, "wb") as file:
                                file.write(result)
                            self.receipt["recording"] = {"private_path": str(target), "sha256": hashlib.sha256(result).hexdigest(),
                                                         "bytes": len(result), "public_review": "NOT_REVIEWED"}
                            self.receipt["recording_state"] = "SAVED" if status == "OBSERVED" else "SAVED_PARTIAL"
                        self.receipt["cleanup"][label] = "SUCCEEDED"
                    except BaseException as exc:
                        self.receipt["cleanup"][label] = exc.code if isinstance(exc, KernelError) else "INTERRUPTED"
            if self._name:
                try:
                    # Name exists before POST: ambiguous creates are cleaned by name.
                    self.adapter._request("DELETE", self._path, timeout=10, expected=204)
                    self.receipt["cleanup"]["session_delete"] = "SUCCEEDED"
                except BaseException as exc:
                    self.receipt["cleanup"]["session_delete"] = exc.code if isinstance(exc, KernelError) else "INTERRUPTED"
            if any(value != "SUCCEEDED" for value in self.receipt["cleanup"].values()) and status == "OBSERVED":
                self.receipt["status"] = "INCOMPLETE"
            self._view_url = None
            self.receipt["finished_at"] = _now()
            if self._name:
                self._persist()

    def __exit__(self, typ, value, traceback):
        self.close("CANCELLED" if typ in (KeyboardInterrupt, SystemExit) else "FAILED" if typ else "OBSERVED")
        return False
