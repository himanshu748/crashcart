"""Short-lived, loopback-only gateway for one existing owned investigation.

This module does not create ingress, approve exposure, or grant provider usage.
The normal merchant service still verifies approval, payments and webhooks.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import hmac
from http.cookies import SimpleCookie
from http.server import ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import parse_qs, urlsplit

from .config import load_env
from .server import Handler, ROOT
from .service import MerchantService
from .store import Store, canonical


MAX_LIFETIME = 1800
MAX_BODY = 131072
BODY_READ_TIMEOUT_SECONDS = 10
PAGE_PATHS = frozenset({"/", "/shop", "/checkout", "/return", "/cancel", "/ticket"})
ASSETS = {"/app.js": "application/javascript", "/marketing.js": "application/javascript", "/style.css": "text/css"}
ACTIONS = frozenset({"order", "capture", "observation", "reconcile", "cancel"})
COOKIE_NAME = "__Host-crashcart_gateway"


class GatewayError(ValueError):
    def __init__(self, code, status=400):
        self.code, self.status = code, status
        super().__init__(code)


def exact_https_origin(value):
    """Syntax only. Approval and reachable ownership must be established outside."""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.port not in (None, 443) or parsed.path or
                parsed.query or parsed.fragment or
                not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", parsed.hostname) or
                value != "https://" + parsed.hostname):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise GatewayError("EXACT_APPROVED_HTTPS_ORIGIN_REQUIRED") from None
    return value


@dataclass(frozen=True)
class Scope:
    run_id: str
    purchase_id: str
    origin: str
    expires_at: float
    context_hash: str


def _owned_context(store, run_id):
    run = store.get_run(run_id)
    purchase = store.purchase_for_run(run_id)
    if not run or not purchase:
        raise GatewayError("UNKNOWN_SCOPED_RUN", 404)
    with store.connect() as db:
        fixture = db.execute("SELECT * FROM fixtures WHERE id=?", (run["fixture_id"],)).fetchone()
    if (not fixture or fixture["owned"] != 1 or fixture["environment"] != "sandbox" or
            run["fixture_id"] != "workshop-v1" or run["invariant_version"] != "ticket-v1" or
            run["mode"] not in {"LIVE_SANDBOX", "FRESH_SANDBOX"} or
            purchase["amount"] != 2900 or purchase["currency"] != "USD" or
            fixture["amount"] != 2900 or fixture["currency"] != "USD"):
        raise GatewayError("OWNED_SANDBOX_SCOPE_REQUIRED", 403)
    stable = {name: run[name] for name in ("id", "purchase_id", "fixture_id", "mode", "promise",
                                         "invariant_version", "invariant", "fault", "budget", "created_at")}
    stable["purchase"] = {name: purchase[name] for name in ("id", "run_id", "amount", "currency", "created_at")}
    return run, purchase, hashlib.sha256(canonical(stable).encode()).hexdigest()


class VerificationGateway(ThreadingHTTPServer):
    """Binding is always 127.0.0.1; construction never starts a tunnel."""
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, store, *, run_id, public_origin, external_origin_approved=False,
                 lifetime_seconds=900, port=0, service=None, clock=time.time):
        if external_origin_approved is not True:
            raise GatewayError("EXTERNAL_ORIGIN_APPROVAL_REQUIRED", 403)
        origin = exact_https_origin(public_origin)
        if os.environ.get("CRASHCART_PUBLIC_URL") != origin:
            raise GatewayError("MERCHANT_RETURN_ORIGIN_MISMATCH", 403)
        if type(lifetime_seconds) is not int or not 1 <= lifetime_seconds <= MAX_LIFETIME:
            raise GatewayError("LIFETIME_MUST_BE_1_TO_1800_SECONDS")
        if type(port) is not int or not 0 <= port <= 65535:
            raise GatewayError("INVALID_LOOPBACK_PORT")
        run, purchase, digest = _owned_context(store, run_id)
        self.store, self.service, self.clock = store, service or MerchantService(store), clock
        self.scope = Scope(run["id"], purchase["id"], origin, clock() + lifetime_seconds, digest)
        self._monotonic_deadline = time.monotonic() + lifetime_seconds
        self._token = secrets.token_urlsafe(32)
        self._cookie = hmac.new(self._token.encode(), b"scoped-gateway-session-v1", hashlib.sha256).hexdigest()
        self._order_id = purchase["order_id"]
        self._revoked = False
        self._lock = threading.RLock()
        self._slots = threading.BoundedSemaphore(8)
        self._mutations = 0
        super().__init__(("127.0.0.1", port), GatewayHandler)

    @property
    def token(self):
        """Private handoff only; never serialize into receipts, URLs or logs."""
        return self._token

    def revoke(self):
        with self._lock:
            self._revoked = True

    def validate_scope(self):
        if self._revoked or self.clock() >= self.scope.expires_at or time.monotonic() >= self._monotonic_deadline:
            raise GatewayError("GATEWAY_EXPIRED", 410)
        if os.environ.get("CRASHCART_PUBLIC_URL") != self.scope.origin:
            raise GatewayError("MERCHANT_RETURN_ORIGIN_CHANGED", 403)
        run, purchase, digest = _owned_context(self.store, self.scope.run_id)
        if digest != self.scope.context_hash or purchase["id"] != self.scope.purchase_id:
            raise GatewayError("SCOPED_CONTEXT_CHANGED", 403)
        # The only permitted identity transition is this gateway's first order.
        if purchase["order_id"] != self._order_id:
            raise GatewayError("SCOPED_ORDER_CHANGED", 403)
        return run, purchase

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        # Default traceback can expose provider or request data.
        pass


class GatewayHandler(Handler):
    """No inherited dispatch: new core routes cannot widen this capability."""
    server_version = "CrashCartGateway/0.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *args):
        pass

    def parse_request(self):
        if not super().parse_request():
            return False
        # BaseHTTPRequestHandler normalizes a leading //; inspect the original
        # target as well so an alternate spelling cannot evade the allowlist.
        self._raw_target = self.requestline.split()[1]
        if (len(self.path) > 4096 or sum(len(k) + len(v) for k, v in self.headers.items()) > 16384 or
                any(len(self.headers.get_all(k, [])) > 1 for k in
                    ("Host", "Origin", "Authorization", "Cookie", "Content-Length", "Content-Type")) or
                self.headers.get("Transfer-Encoding")):
            self.send(400, {"error": "INVALID_REQUEST_FRAMING"})
            return False
        return True

    def _path(self):
        parsed = urlsplit(self._raw_target)
        if (parsed.scheme or parsed.netloc or parsed.fragment or "%" in parsed.path or
                "\\" in parsed.path or "//" in parsed.path or
                any(part in {".", ".."} for part in parsed.path.split("/"))):
            raise GatewayError("ROUTE_NOT_AVAILABLE", 404)
        if parsed.query and parsed.path not in PAGE_PATHS:
            raise GatewayError("ROUTE_NOT_AVAILABLE", 404)
        if parsed.query:
            query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=8)
            if (set(query) - {"run", "token", "PayerID"} or
                    any(len(values) != 1 for values in query.values()) or
                    query.get("run", [self.server.scope.run_id]) != [self.server.scope.run_id] or
                    ("token" in query and query["token"] != [self.server._order_id])):
                raise GatewayError("CALLBACK_SCOPE_MISMATCH", 403)
        return parsed.path

    def _origin(self, *, credential_request=False, webhook=False):
        origin = self.headers.get("Origin")
        if origin is not None and origin != self.server.scope.origin:
            raise GatewayError("CROSS_ORIGIN_REJECTED", 403)
        # Browsers send Origin on same-origin POST. Cookie-only writes without
        # it fail closed; server-to-server login/Bearer and webhook can omit it.
        if (self.command == "POST" and origin is None and not webhook and
                not credential_request and not self._bearer()):
            raise GatewayError("WRITE_ORIGIN_REQUIRED", 403)

    def _bearer(self):
        header = self.headers.get("Authorization", "")
        return header.startswith("Bearer ") and hmac.compare_digest(header[7:], self.server.token)

    def authenticated(self):
        if self._bearer():
            return True
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", "")).get(COOKIE_NAME)
            return bool(cookie and hmac.compare_digest(cookie.value, self.server._cookie))
        except Exception:
            return False

    def json_body(self, *, include_raw=False):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise GatewayError("JSON_CONTENT_TYPE_REQUIRED", 415)
        length = self.headers.get("Content-Length", "")
        if not re.fullmatch(r"[0-9]{1,6}", length):
            raise GatewayError("CONTENT_LENGTH_REQUIRED", 411)
        size = int(length)
        if not 0 < size <= MAX_BODY:
            raise GatewayError("BODY_TOO_LARGE", 413)
        # An idle socket timeout alone restarts as bytes arrive. Bound the whole
        # body, including continuous trickle input, by a monotonic deadline and
        # the remaining gateway lifetime. Do not hold the shared scope lock here.
        deadline = min(time.monotonic() + BODY_READ_TIMEOUT_SECONDS,
                       self.server._monotonic_deadline)
        chunks, received = [], 0
        try:
            while received < size:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise GatewayError("BODY_READ_TIMEOUT", 408)
                self.connection.settimeout(remaining)
                chunk = self.rfile.read1(min(65536, size - received))
                if time.monotonic() >= deadline:
                    raise GatewayError("BODY_READ_TIMEOUT", 408)
                if not chunk:
                    raise GatewayError("INCOMPLETE_BODY")
                chunks.append(chunk)
                received += len(chunk)
        except TimeoutError:
            self.close_connection = True
            raise GatewayError("BODY_READ_TIMEOUT", 408) from None
        except GatewayError:
            self.close_connection = True
            raise
        finally:
            self.connection.settimeout(10)
        raw = b"".join(chunks)
        if include_raw:
            from .paypal import parse_webhook_event
            return parse_webhook_event(raw), raw
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise GatewayError("DUPLICATE_JSON_KEY")
                value[key] = item
            return value
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(GatewayError("INVALID_JSON_NUMBER")))
        if not isinstance(value, dict):
            raise GatewayError("JSON_OBJECT_REQUIRED")
        return value

    def do_GET(self):
        self._dispatch(False)

    def do_POST(self):
        self._dispatch(True)

    def _dispatch(self, write):
        try:
            with self.server._lock:
                run, purchase = self.server.validate_scope()
                path = self._path()
                self._origin(credential_request=path == "/api/login", webhook=path == "/api/webhooks/paypal")
                if not write:
                    if self.headers.get("Content-Length", "0") != "0":
                        raise GatewayError("GET_BODY_REJECTED")
                    return self._get(path, run, purchase)
                if path not in {"/api/login", "/api/webhooks/paypal"} and not self.authenticated():
                    raise GatewayError("SCOPED_ACCESS_REQUIRED", 401)
            # Input can wait without blocking health, revocation or another
            # request. All state validation and service mutations remain serialized.
            if path == "/api/webhooks/paypal":
                body, raw = self.json_body(include_raw=True)
            else:
                body, raw = self.json_body(), None
            with self.server._lock:
                # Discard the pre-read state: scope, expiry and order may have
                # changed while this body was arriving.
                run, purchase = self.server.validate_scope()
                return self._post(path, body, run, purchase, raw_body=raw)
        except GatewayError as exc:
            self.send(exc.status, {"error": exc.code})
        except (ValueError, TypeError, KeyError, RecursionError):
            self.send(400, {"error": "INVALID_SCOPED_REQUEST"})
        except Exception:
            # Never copy untrusted provider messages or credentials to clients.
            self.send(503, {"error": "SCOPED_OPERATION_UNRESOLVED"})

    def _get(self, path, run, purchase):
        if path == "/healthz":
            return self.send(200, {"status": "ok", "database": "ok", "service": "crashcart-scoped-gateway"})
        if path == "/api/fixture":
            return self.send(200, {"id": "workshop-v1", "name": "The resilient systems workshop",
                "amount_minor": 2900, "currency": "USD", "recovery_seconds": 60,
                "promise": "One ticket within 60 seconds of confirmed payment."})
        if path in PAGE_PATHS or path in ASSETS:
            filename = "index.html" if path in PAGE_PATHS else path[1:]
            file = ROOT / "web" / filename
            # Exact names and no symlinks; no directory/static catch-all.
            if not file.is_file() or file.is_symlink():
                raise GatewayError("ASSET_UNAVAILABLE", 404)
            return self.send(200, file.read_bytes(), "text/html" if path in PAGE_PATHS else ASSETS[path])
        if not self.authenticated():
            raise GatewayError("SCOPED_ACCESS_REQUIRED", 401)
        if path == "/api/prerequisites":
            return self.send(200, {"gateway": {"configured": not self.server._revoked,
                "connectivity_verified": False, "gateway_scope": self.server.scope.run_id,
                "missing": [], "limitation": "Only this investigation is available; global integration access is not exposed."}})
        if path == "/api/runs":
            return self.send(200, {"runs": [run]})
        if path == "/api/runs/" + self.server.scope.run_id:
            return self.send(200, {"run": run, "purchase": purchase,
                "merchant": self.store.merchant_state(purchase["id"]),
                "events": self.store.get_events(run["id"]),
                "operations": self.store.get_operations(purchase["id"])})
        if path == "/api/merchant/" + self.server.scope.purchase_id:
            return self.send(200, self.store.merchant_state(purchase["id"]))
        raise GatewayError("ROUTE_NOT_AVAILABLE", 404)

    def _post(self, path, body, run, purchase, *, raw_body=None):
        if path == "/api/login":
            supplied = body.get("token")
            if (set(body) != {"token"} or not isinstance(supplied, str) or
                    not hmac.compare_digest(supplied, self.server.token)):
                raise GatewayError("INVALID_GATEWAY_TOKEN", 401)
            age = max(0, math.floor(self.server.scope.expires_at - self.server.clock()))
            return self.send(200, {"authenticated": True}, headers={"Set-Cookie":
                f"{COOKIE_NAME}={self.server._cookie}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age={age}"})
        if path == "/api/webhooks/paypal":
            # Correlation is only a scope filter, never authentication. Pass the
            # exact body and headers unchanged into normal signature validation.
            resource = body.get("resource")
            supplementary = resource.get("supplementary_data") if isinstance(resource, dict) else None
            related = supplementary.get("related_ids") if isinstance(supplementary, dict) else None
            related = related if isinstance(related, dict) else {}
            if not purchase["order_id"] or related.get("order_id") != purchase["order_id"]:
                raise GatewayError("WEBHOOK_ORDER_OUT_OF_SCOPE", 403)
            self._reserve_mutation()
            return self.send(200, self.server.service.webhook(dict(self.headers), body, raw_body=raw_body))
        if not self.authenticated():
            raise GatewayError("SCOPED_ACCESS_REQUIRED", 401)
        prefix = "/api/runs/" + self.server.scope.run_id + "/"
        action = path[len(prefix):] if path.startswith(prefix) else ""
        if action not in ACTIONS:
            raise GatewayError("ROUTE_NOT_AVAILABLE", 404)
        if action in {"order", "reconcile", "cancel"} and body:
            raise GatewayError("EMPTY_BODY_REQUIRED")
        if action == "capture" and (set(body) != {"order_id"} or not purchase["order_id"] or body["order_id"] != purchase["order_id"]):
            raise GatewayError("CAPTURE_ORDER_OUT_OF_SCOPE", 403)
        if action == "observation" and (set(body) - {"browser_kind", "url_path", "visible_text", "action"} or
                body.get("browser_kind") != "LOCAL_BROWSER" or body.get("url_path") not in PAGE_PATHS):
            raise GatewayError("LOCAL_OBSERVATION_SCHEMA_REQUIRED")
        self._reserve_mutation()
        service = self.server.service
        if action == "order":
            try:
                result = service.create_order(run["id"])
            finally:
                # Preserve a persisted identity even if the transport response
                # was lost. A failed call never permits choosing another order.
                self.server._order_id = self.store.purchase_for_run(run["id"])["order_id"]
        elif action == "capture":
            result = service.capture(run["id"], purchase["order_id"])
        elif action == "reconcile":
            result = service.reconcile(run["id"])
        elif action == "observation":
            return self.send(201, service.observe_browser(run["id"], body))
        else:
            self.store.update_run(run["id"], cancel_requested=1, state="cancelled")
            self.store.record_event(run["id"], "operator", "cancelled", {})
            result = self.store.get_run(run["id"])
        return self.send(200, result)

    def _reserve_mutation(self):
        if self.server._mutations >= 256:
            raise GatewayError("GATEWAY_MUTATION_LIMIT", 429)
        self.server._mutations += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--public-origin", required=True)
    parser.add_argument("--external-origin-approved", action="store_true")
    parser.add_argument("--lifetime-seconds", type=int, default=900)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token-file", required=True, help="New private file in ignored var/; never a public artifact")
    args = parser.parse_args()
    load_env()
    destination = Path(args.token_file).absolute()
    private_root = (ROOT / "var").resolve()
    if not destination.parent.resolve().is_relative_to(private_root):
        parser.error("token file must be inside this project's ignored var/ directory")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    gateway = VerificationGateway(Store(args.db), run_id=args.run, public_origin=args.public_origin,
        external_origin_approved=args.external_origin_approved, lifetime_seconds=args.lifetime_seconds, port=args.port)
    try:
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as output:
            output.write(gateway.token)
        print(json.dumps({"bind": "127.0.0.1", "port": gateway.server_port,
                          "run_id": gateway.scope.run_id, "expires_at": gateway.scope.expires_at}), flush=True)
        timer = threading.Timer(args.lifetime_seconds, gateway.shutdown)
        timer.daemon = True
        timer.start()
        try:
            gateway.serve_forever(poll_interval=0.25)
        finally:
            timer.cancel()
    finally:
        gateway.revoke()
        gateway.server_close()


if __name__ == "__main__":
    main()
