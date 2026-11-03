"""Small same-origin HTTP application. Operator routes require a local secret."""

import hashlib
import hmac
import json
import mimetypes
import os
import secrets
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .config import prerequisites
from .store import Store

ROOT = Path(__file__).resolve().parent.parent
# Pinned AG Studio 3.0.0 injects this exact 101-byte color sensor without a nonce.
STUDIO_COLOR_SENSOR_STYLE_HASH = "'sha256-ydedGqCb79ipYJuuWRyOTMrKbkjYWv8WIjG7SRdnEPU='"


class Handler(BaseHTTPRequestHandler):
    server_version = "CrashCart/0.1"

    def log_message(self, fmt, *args):
        # Avoid logging URLs that might carry provider return parameters.
        if args and isinstance(args[0], str) and args[0].startswith(("GET ", "POST ")):
            return

    def send(self, status, value, content_type="application/json", headers=None, *, style_nonce=None):
        data = json.dumps(value).encode() if content_type == "application/json" else value
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        style_policy = "'self'" + (f" 'nonce-{style_nonce}' {STUDIO_COLOR_SENSOR_STYLE_HASH}" if style_nonce else "")
        self.send_header("Content-Security-Policy", f"default-src 'self'; script-src 'self'; style-src {style_policy}; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        for key, val in (headers or {}).items():
            self.send_header(key, val)
        self.end_headers()
        self.wfile.write(data)

    def authenticated(self):
        token = os.environ.get("CRASHCART_OPERATOR_TOKEN", "")
        if not token:
            return False
        supplied = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if supplied and hmac.compare_digest(supplied, token):
            return True
        try:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            actual = cookie.get("crashcart_session")
            expected = hmac.new(token.encode(), b"operator-session-v1", hashlib.sha256).hexdigest()
            return bool(actual and hmac.compare_digest(actual.value, expected))
        except Exception:
            return False

    def json_body(self, *, include_raw=False):
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("Content-Type must be application/json")
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 131072:
            raise ValueError("JSON body must be between 1 and 131072 bytes")
        raw = self.rfile.read(size)
        if include_raw:
            from .paypal import parse_webhook_event
            if len(raw) != size:
                raise ValueError("Incomplete webhook body")
            return parse_webhook_event(raw), raw
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def origin_allowed(self):
        origin = self.headers.get("Origin")
        configured = os.environ.get("CRASHCART_PUBLIC_URL", "")
        allowed = {f"http://{self.headers.get('Host', '')}", configured.rstrip("/")}
        return not origin or origin in allowed

    @property
    def store(self):
        return self.server.store

    def do_GET(self):
        path = urlparse(self.path).path
        try:
            if path == "/healthz":
                with self.store.connect() as db:
                    db.execute("SELECT 1").fetchone()
                return self.send(200, {"status": "ok", "database": "ok", "service": "crashcart", "version": "0.1.0"})
            if path == "/api/fixture":
                return self.send(200, {"id": "workshop-v1", "name": "The resilient systems workshop", "amount_minor": 2900, "currency": "USD", "recovery_seconds": 60, "promise": "One ticket within 60 seconds of confirmed payment."})
            if path.startswith("/api/"):
                if not self.authenticated():
                    return self.send(401, {"error": "Operator access required"})
                return self.api_get(path)
            if path in ("/", "/shop", "/checkout", "/return", "/cancel", "/ticket"):
                file = ROOT / "web/index.html"
            else:
                relative = path.removeprefix("/")
                file = (ROOT / "web" / relative).resolve()
                if not file.is_relative_to((ROOT / "web").resolve()):
                    return self.send(404, {"error": "Not found"})
            if not file.is_file():
                return self.send(404, {"error": "Not found"})
            kind = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            data = file.read_bytes()
            if file.resolve() == (ROOT / "web/studio/index.html").resolve():
                # Studio's documented styleNonce supports its generated styles
                # without allowing arbitrary inline styles or scripts.
                nonce = secrets.token_urlsafe(24)
                data = data.replace(b"__STYLE_NONCE__", nonce.encode("ascii"))
                return self.send(200, data, kind, style_nonce=nonce)
            return self.send(200, data, kind)
        except (ValueError, KeyError) as exc:
            return self.send(400, {"error": str(exc)})
        except Exception:
            return self.send(500, {"error": "Internal error; inspect local service logs"})

    def api_get(self, path):
        if path == "/api/prerequisites":
            return self.send(200, prerequisites())
        if path == "/api/runs":
            return self.send(200, {"runs": self.store.list_runs()})
        if path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            run = self.store.get_run(run_id)
            if not run:
                return self.send(404, {"error": "Unknown run"})
            from .recording import availability, enabled, load_recording, byte_range, RecordingUnavailable, InvalidRange
            allow_recording = enabled(self.server, os.environ)
            if path.endswith("/recording"):
                if path != f"/api/runs/{run_id}/recording" or not allow_recording:
                    return self.send(404, {"error": "Saved checkout unavailable"})
                try:
                    recording = load_recording(self.store, run_id, ROOT / "var")
                except RecordingUnavailable:
                    return self.send(404, {"error": "Saved checkout unavailable"})
                try:
                    start, end, partial = byte_range(self.headers.get("Range"), recording.size)
                except InvalidRange:
                    return self.send(416, {"error": "Requested video range unavailable"}, headers={"Content-Range": f"bytes */{recording.size}"})
                self.send_response(206 if partial else 200)
                headers = {"Content-Type": "video/mp4", "Content-Length": str(end - start + 1),
                           "Accept-Ranges": "bytes", "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                           "Cross-Origin-Resource-Policy": "same-origin", "Referrer-Policy": "no-referrer",
                           "Content-Disposition": 'inline; filename="saved-checkout.mp4"'}
                if partial:
                    headers["Content-Range"] = f"bytes {start}-{end}/{recording.size}"
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                try:
                    view = memoryview(recording.body)
                    for offset in range(start, end + 1, 65536):
                        self.wfile.write(view[offset:min(offset + 65536, end + 1)])
                except (BrokenPipeError, ConnectionResetError):
                    pass  # A browser seek/close must not trigger another response.
                return
            purchase = self.store.purchase_for_run(run_id)
            data = {"run": run, "purchase": purchase, "merchant": self.store.merchant_state(purchase["id"]), "events": self.store.get_events(run_id), "operations": self.store.get_operations(purchase["id"]),
                    "recording": availability(self.store, run_id, ROOT / "var", allow=allow_recording)}
            if path.endswith("/regression.zip"):
                from .replay import package_run, export_package
                import tempfile
                sources = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in ("crashcart/service.py", "crashcart/store.py", "crashcart/invariant.py", "crashcart/replay.py", "migrations/001_initial.sql")}
                package = package_run(run, purchase, data["operations"], data["events"], sources)
                with tempfile.TemporaryDirectory(prefix="crashcart-export-") as folder:
                    output = Path(folder) / "regression.zip"
                    export_package(package, output)
                    return self.send(200, output.read_bytes(), "application/zip", {"Content-Disposition": f'attachment; filename="{run_id}-regression.zip"'})
            if path.endswith("/export"):
                return self.send(200, {"format": "crashcart-inspection-v1", "runnable_replay": False, "limitation": "Inspection records only; executable replay acceptance remains unverified.", **data}, headers={"Content-Disposition": f'attachment; filename="{run_id}.json"'})
            return self.send(200, data)
        if path.startswith("/api/merchant/"):
            return self.send(200, self.store.merchant_state(path.split("/")[3]))
        return self.send(404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if not self.origin_allowed():
                return self.send(403, {"error": "Cross-origin writes are rejected"})
            if path == "/api/webhooks/paypal":
                from .service import MerchantService
                body, raw = self.json_body(include_raw=True)
                return self.send(200, MerchantService(self.store).webhook(dict(self.headers), body, raw_body=raw))
            body = self.json_body()
            if path == "/api/login":
                token = os.environ.get("CRASHCART_OPERATOR_TOKEN", "")
                supplied = body.get("token")
                if not token or not isinstance(supplied, str) or not hmac.compare_digest(supplied, token):
                    return self.send(401, {"error": "Invalid operator token"})
                session = hmac.new(token.encode(), b"operator-session-v1", hashlib.sha256).hexdigest()
                secure = "; Secure" if os.environ.get("CRASHCART_PUBLIC_URL", "").startswith("https://") else ""
                return self.send(200, {"authenticated": True}, headers={"Set-Cookie": f"crashcart_session={session}; HttpOnly; SameSite=Lax; Path=/{secure}"})
            if not self.authenticated():
                return self.send(401, {"error": "Operator access required"})
            return self.api_post(path, body)
        except (ValueError, TypeError, KeyError) as exc:
            return self.send(400, {"error": str(exc)})
        except Exception as exc:
            from .paypal import PayPalError
            from .studio_agent import StudioQueryError
            if isinstance(exc, StudioQueryError):
                return self.send(exc.status_code, {"error": exc.code, "code": exc.code})
            if isinstance(exc, PayPalError):
                return self.send(503, {"error": str(exc), "code": exc.code, "ambiguous": exc.ambiguous})
            # Log only exception type: provider responses may contain buyer details.
            print(f"request error: {type(exc).__name__}", flush=True)
            return self.send(500, {"error": "Internal error; evidence remains persisted"})

    def api_post(self, path, body):
        if path == "/api/studio/query":
            from .studio_agent import StudioQuery
            return self.send(200, StudioQuery(self.store).query(body))
        if path == "/api/runs":
            from .faults import validate_fault
            allowed = {"promise", "mode", "fault", "fixture_id"}
            if set(body) - allowed:
                raise ValueError("Unknown fields: " + ", ".join(sorted(set(body) - allowed)))
            body["fault"] = validate_fault(body.get("fault"), fixture_id=body.get("fixture_id", "workshop-v1"))
            if body.get("mode", "LIVE_SANDBOX") not in {"LIVE_SANDBOX", "FRESH_SANDBOX"}:
                raise ValueError("Browser creation requires actual sandbox mode; replay is imported separately")
            run = self.store.create_run(**body)
            return self.send(201, run)
        if path.startswith("/api/runs/"):
            from .service import MerchantService
            service = MerchantService(self.store)
            run_id = path.split("/")[3]
            action = path.split("/")[-1]
            if action == "order":
                if body:
                    raise ValueError("Order accepts no client price or currency; merchant price is fixed")
                return self.send(200, service.create_order(run_id))
            if action == "capture":
                if set(body) != {"order_id"}:
                    raise ValueError("Expected persisted order_id only")
                return self.send(200, service.capture(run_id, body["order_id"]))
            if action == "reconcile":
                if body:
                    raise ValueError("Reconciliation accepts no client payment evidence")
                return self.send(200, service.reconcile(run_id))
            if action == "observation":
                return self.send(201, service.observe_browser(run_id, body))
            if action == "investigate":
                if body:
                    raise ValueError("Investigation accepts no supplied verdict or tool result")
                from .investigator import Investigation
                return self.send(200, Investigation(self.store, service).run(run_id))
        if path.endswith("/cancel") and path.startswith("/api/runs/"):
            run_id = path.split("/")[3]
            if not self.store.get_run(run_id):
                return self.send(404, {"error": "Unknown run"})
            self.store.update_run(run_id, cancel_requested=1, state="cancelled")
            self.store.record_event(run_id, "operator", "cancelled", {})
            return self.send(200, self.store.get_run(run_id))
        return self.send(404, {"error": "Not found"})


def serve(db_path, host="127.0.0.1", port=8765):
    if not os.environ.get("CRASHCART_OPERATOR_TOKEN"):
        raise SystemExit("Missing CRASHCART_OPERATOR_TOKEN. Run python3 -m crashcart setup.")
    server = ThreadingHTTPServer((host, port), Handler)
    server.store = Store(db_path)
    print(f"CrashCart listening at http://{host}:{server.server_port}; database migrated", flush=True)
    server.serve_forever()
