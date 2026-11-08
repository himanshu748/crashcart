"""Reviewable private Sandbox core, separate from the public recorded demo.

No credential, ledger initialization, injected model, deployment, webhook or
remote-browser launch is provided here. API and worker require the same existing
private state/ledger and an explicit finite access window.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import hmac
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import threading
import time
import uuid
from urllib.parse import urlsplit

from .faults import validate_fault
from .model_allowance import ModelAllowanceError, _locked
from .model_transport import MODAL_MODEL, ModelTransportError, configuration, strict_json
from .monitor_ingress import BoundedHTTPServer, IngressLimits
from .server import Handler
from .service import MerchantService
from .store import Store, utcnow

PUBLIC_URL = "https://workspace-crashcart.52.202.25.181.sslip.io"
MAX_WINDOW_END = datetime(2026, 12, 23, tzinfo=timezone.utc)
CASE_LIMIT = 8
ALLOWED_MODES = {"LIVE_SANDBOX", "FRESH_SANDBOX"}
ALLOWED_ACTIONS = {"order", "capture", "reconcile", "observation", "investigation-job", "cancel"}
_SECRET_NAMES = {"CRASHCART_OPERATOR_TOKEN", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET", "MODAL_API_KEY"}
_ALLOWED_NAMES = _SECRET_NAMES | {"CRASHCART_PUBLIC_URL", "CRASHCART_MODEL_PROVIDER", "MODAL_MODEL",
    "MODAL_ALLOWED_ORIGIN", "MODAL_BASE_URL", "CRASHCART_MODEL_ALLOWANCE_PATH", "CRASHCART_ALLOW_MODEL",
    "CRASHCART_ALLOW_SANDBOX", "CRASHCART_ALLOW_KERNEL", "CRASHCART_ALLOW_PROCESS_INTERRUPT",
    "CRASHCART_EVALUATION_MODE", "CRASHCART_LIVE_WINDOW_EXPIRES_AT"}


class HostedLiveError(Exception):
    def __init__(self, code, status=503):
        super().__init__(code)
        self.code, self.status = code, status


def error_message(code):
    return {
        "LIVE_CASE_LIMIT_REACHED": "This workspace has used its eight test checkouts. Contact the workspace owner before starting more.",
        "LIVE_WINDOW_EXPIRED": "This test workspace's access window has ended. Contact the workspace owner for retained results.",
        "LIVE_CASE_SCOPE_INVALID": "That checkout is not available in this workspace. Choose a checkout from your list.",
        "LIVE_UNKNOWN_CASE": "We could not find that checkout. Choose a checkout from your list.",
        "LIVE_FEATURE_DISABLED": "That action is not available in this workspace. Return to your checkout workspace.",
    }.get(code, "This workspace needs attention. Contact the workspace owner before continuing.")


def _now():
    return datetime.now(timezone.utc)


def read_credentials(path):
    """Read only an explicitly staged, owned 0600 regular credential file."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
                raise HostedLiveError("LIVE_CREDENTIAL_FILE_PERMISSIONS")
            raw = handle.read(32769)
        if len(raw) > 32768:
            raise HostedLiveError("LIVE_CREDENTIAL_FILE_INVALID")
        values = {}
        for line in raw.decode().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            if not separator or name not in _ALLOWED_NAMES or name in values:
                raise HostedLiveError("LIVE_CREDENTIAL_FILE_INVALID")
            value = value.strip()
            if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
                value = value[1:-1]
            values[name] = value
        return values
    except (OSError, UnicodeError):
        raise HostedLiveError("LIVE_CREDENTIAL_FILE_UNAVAILABLE") from None


class Runtime:
    def __init__(self, environ):
        self.environ = dict(environ)
        value = self.environ.get("CRASHCART_LIVE_WINDOW_EXPIRES_AT", "")
        try:
            self.expires = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if self.expires.tzinfo is None or self.expires.utcoffset() is None or self.expires > MAX_WINDOW_END:
                raise ValueError("window")
        except (ValueError, TypeError):
            raise HostedLiveError("LIVE_WINDOW_INVALID") from None
        self.active()
        env = self.environ
        if (env.get("CRASHCART_PUBLIC_URL") != PUBLIC_URL or env.get("CRASHCART_MODEL_PROVIDER") != "modal"
                or env.get("MODAL_MODEL") != MODAL_MODEL or env.get("CRASHCART_ALLOW_SANDBOX") != "1"
                or env.get("CRASHCART_ALLOW_MODEL") != "1"
                or env.get("CRASHCART_EVALUATION_MODE", "ordinary") != "ordinary"
                or env.get("CRASHCART_ALLOW_KERNEL", "0") != "0"
                or env.get("CRASHCART_ALLOW_PROCESS_INTERRUPT", "0") != "0"):
            raise HostedLiveError("LIVE_PROVIDER_SCOPE_INVALID")
        forbidden = ("KERNEL_API_KEY", "AG_STUDIO_LICENSE_KEY", "PAYPAL_WEBHOOK_ID", "OPENAI_API_KEY",
                     "OPENAI_MODEL", "CRASHCART_HELD_OUT_POLICY", "CRASHCART_HELD_OUT_POLICY_SHA256")
        if any(env.get(key) for key in forbidden):
            raise HostedLiveError("LIVE_FEATURE_DISABLED")
        token = env.get("CRASHCART_OPERATOR_TOKEN", "")
        if (not isinstance(token, str) or not 32 <= len(token) <= 256
                or any(not 33 <= ord(char) <= 126 for char in token)
                or any(not isinstance(env.get(key), str) or not env[key].strip() for key in _SECRET_NAMES)):
            raise HostedLiveError("LIVE_CREDENTIALS_REQUIRED")
        try:
            model = configuration(env)
            if model.provider != "modal":
                raise HostedLiveError("LIVE_PROVIDER_SCOPE_INVALID")
            ledger = env.get("CRASHCART_MODEL_ALLOWANCE_PATH", "")
            if not Path(ledger).is_absolute():
                raise HostedLiveError("LIVE_MODEL_ALLOWANCE_REQUIRED")
            # Existing ledger only. This validates it and never reserves a call.
            with _locked(Path(ledger), lock_timeout=2) as state:
                if any(item["state"] == "RESERVED" for item in state["calls"]):
                    raise HostedLiveError("LIVE_MODEL_ALLOWANCE_UNRESOLVED")
        except (ModelTransportError, ModelAllowanceError) as exc:
            raise HostedLiveError(exc.code) from None

    def active(self):
        if _now() >= self.expires:
            raise HostedLiveError("LIVE_WINDOW_EXPIRED")


def _private_database(path):
    path = Path(path)
    if not path.is_absolute() or path.parent.is_symlink():
        raise HostedLiveError("LIVE_DATABASE_PATH_INVALID")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    parent = path.parent.stat()
    if parent.st_uid != os.getuid() or stat.S_IMODE(parent.st_mode) & 0o022:
        raise HostedLiveError("LIVE_DATABASE_PERMISSIONS")
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise HostedLiveError("LIVE_DATABASE_PERMISSIONS")
    store = Store(path)
    os.chmod(path, 0o600)
    with store.connect(write=True) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS hosted_live_case_grants(
            grant_index INTEGER PRIMARY KEY CHECK(grant_index BETWEEN 1 AND 8),
            run_id TEXT UNIQUE REFERENCES runs(id),reserved_at TEXT NOT NULL)""")
    return store


def _reserve_case(store):
    with store.connect(write=True) as db:
        row = db.execute("SELECT COUNT(*) total,COALESCE(MAX(grant_index),0) latest FROM hosted_live_case_grants").fetchone()
        if row["total"] != row["latest"] or row["total"] > CASE_LIMIT:
            raise HostedLiveError("LIVE_CASE_GRANTS_CORRUPT")
        if row["total"] >= CASE_LIMIT:
            raise HostedLiveError("LIVE_CASE_LIMIT_REACHED", 429)
        index = row["latest"] + 1
        db.execute("INSERT INTO hosted_live_case_grants(grant_index,reserved_at) VALUES(?,?)", (index, utcnow()))
        return index


def require_case(store, run_id):
    run = store.get_run(run_id)
    if not run:
        raise HostedLiveError("LIVE_UNKNOWN_CASE", 404)
    with store.connect() as db:
        granted = db.execute("SELECT 1 FROM hosted_live_case_grants WHERE run_id=?", (run_id,)).fetchone()
    if not granted or run["fixture_id"] != "workshop-v1" or run["mode"] not in ALLOWED_MODES:
        raise HostedLiveError("LIVE_CASE_SCOPE_INVALID", 403)
    if validate_fault(run["fault"], run["fixture_id"])["kind"] == "process_interrupt":
        raise HostedLiveError("LIVE_FEATURE_DISABLED", 403)
    return run


def granted_runs(store):
    """Quarantine partial creations; an unbound slot is consumed, never inferred.

    A crash may occur after create_run commits and before its grant is bound.
    That record remains for operator accounting but cannot dispatch or leak
    through the hosted API, and does not prevent other granted cases restarting.
    """
    with store.connect() as db:
        identities = [row[0] for row in db.execute(
            "SELECT run_id FROM hosted_live_case_grants WHERE run_id IS NOT NULL ORDER BY grant_index DESC")]
    return [require_case(store, identity) for identity in identities]


class HostedHandler(Handler):
    def send(self, *args, **kwargs):
        try:
            return super().send(*args, **kwargs)
        except (BrokenPipeError, ConnectionResetError):
            # An expired ingress deadline closes the client socket. Preserve
            # the recorded operation outcome; there is no recipient to notify.
            self.close_connection = True

    def authenticated(self):
        token = self.server.runtime.environ["CRASHCART_OPERATOR_TOKEN"]
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

    def origin_allowed(self):
        return not self.headers.get("Origin") or self.headers["Origin"] == PUBLIC_URL

    def json_body(self, **kwargs):
        if self.headers.get("Transfer-Encoding") is not None or any(
                len(self.headers.get_all(key, [])) > 1 for key in
                ("Content-Length", "Content-Type", "Authorization", "Cookie", "Origin", "Host")):
            raise ValueError("Ambiguous request headers")
        value = self.headers.get("Content-Length", "")
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Content-Length required")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise ValueError("JSON body required")
        size = int(value)
        if not 0 < size <= 131072:
            raise ValueError("Body size rejected")
        raw = self.rfile.read(size)
        if len(raw) != size:
            raise ValueError("Incomplete body")
        data = strict_json(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON object required")
        return data

    def do_POST(self):
        path = urlsplit(self.path).path
        try:
            if path != "/api/login" and not self.authenticated():
                return self.send(401, {"error": "Workspace access required"})
            if not self.origin_allowed():
                return self.send(403, {"error": "Origin not allowed"})
            if path == "/api/login":
                self.server.runtime.active()
                body = self.json_body()
                token = self.server.runtime.environ["CRASHCART_OPERATOR_TOKEN"]
                if set(body) != {"token"} or not isinstance(body["token"], str) or not hmac.compare_digest(body["token"], token):
                    return self.send(401, {"error": "Invalid workspace access"})
                session = hmac.new(token.encode(), b"operator-session-v1", hashlib.sha256).hexdigest()
                return self.send(200, {"authenticated": True}, headers={"Set-Cookie":
                    f"crashcart_session={session}; Secure; HttpOnly; SameSite=Strict; Path=/"})
            if path == "/api/runs":
                self.server.runtime.active()
                body = self.json_body()
                if set(body) - {"promise", "mode", "fault", "fixture_id"}:
                    raise ValueError("Unsupported case fields")
                if body.get("mode", "LIVE_SANDBOX") not in ALLOWED_MODES or body.get("fixture_id", "workshop-v1") != "workshop-v1":
                    raise HostedLiveError("LIVE_CASE_SCOPE_INVALID", 403)
                if not isinstance(body.get("promise"), str) or not 1 <= len(body["promise"].strip()) <= 1000:
                    raise ValueError("A bounded delivery promise is required")
                fault = validate_fault(body.get("fault"), "workshop-v1")
                if fault["kind"] == "process_interrupt":
                    raise HostedLiveError("LIVE_FEATURE_DISABLED", 403)
                index = _reserve_case(self.store)
                # Failures/crashes after reservation intentionally consume a
                # slot. No refund/reset or replacement checkout is automatic.
                run = self.store.create_run(body["promise"], mode=body.get("mode", "LIVE_SANDBOX"), fault=fault)
                with self.store.connect(write=True) as db:
                    db.execute("UPDATE hosted_live_case_grants SET run_id=? WHERE grant_index=? AND run_id IS NULL", (run["id"], index))
                return self.send(201, run)
            parts = path.split("/")
            if len(parts) != 5 or parts[:3] != ["", "api", "runs"] or parts[4] not in ALLOWED_ACTIONS:
                raise HostedLiveError("LIVE_FEATURE_DISABLED", 403)
            require_case(self.store, parts[3])
            if parts[4] != "cancel":
                self.server.runtime.active()
            return self.api_post(path, self.json_body())
        except HostedLiveError as exc:
            self.send(exc.status, {"error": error_message(exc.code), "code": exc.code})
        except (ValueError, KeyError, TypeError):
            self.send(400, {"error": "Invalid workspace request"})
        except Exception as exc:
            from .paypal import PayPalError
            if isinstance(exc, PayPalError):
                return self.send(503, {"error": "PayPal Sandbox could not confirm this action. Check the payment status before trying again.", "code": exc.code, "ambiguous": exc.ambiguous})
            self.send(500, {"error": "This action could not finish. Contact the workspace owner for retained records."})

    def _unsupported_mutation(self):
        self.send(405 if self.authenticated() else 401, {"error": "Method not allowed"})

    do_PUT = _unsupported_mutation
    do_PATCH = _unsupported_mutation
    do_DELETE = _unsupported_mutation

    def api_get(self, path):
        if path == "/api/runs":
            return self.send(200, {"runs": granted_runs(self.store)})
        if path.startswith("/api/merchant/"):
            parts = path.split("/")
            if len(parts) != 4:
                return self.send(404, {"error": "Not found"})
            purchase = self.store.get_purchase(parts[3])
            if purchase is None:
                return self.send(404, {"error": "Unknown purchase"})
            try:
                require_case(self.store, purchase["run_id"])
            except HostedLiveError as exc:
                return self.send(exc.status, {"error": error_message(exc.code), "code": exc.code})
        if path.startswith("/api/runs/"):
            parts = path.split("/")
            if len(parts) not in {4, 5} or len(parts) == 5 and parts[4] not in {"export", "regression.zip"}:
                return self.send(404, {"error": "Not found"})
            try:
                require_case(self.store, parts[3])
            except HostedLiveError as exc:
                return self.send(exc.status, {"error": error_message(exc.code), "code": exc.code})
        return super().api_get(path)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/healthz":
            try:
                self.server.runtime.active()
            except HostedLiveError as exc:
                return self.send(503, {"error": error_message(exc.code), "code": exc.code})
        if path.startswith(("/studio/", "/deadlines/", "/monitor/")):
            return self.send(200, b"<!doctype html><html lang='en'><meta charset='utf-8'>"
                b"<meta name='viewport' content='width=device-width,initial-scale=1'>"
                b"<link rel='stylesheet' href='/style.css'><title>CrashCart workspace</title>"
                b"<main><h1>Your checkout workspace is ready</h1>"
                b"<p>This private workspace runs PayPal Sandbox checkout and background AI investigations. "
                b"The optional report builder and scheduling views are available in the local full workspace.</p>"
                b"<a href='/'>Return to your checkout workspace</a></main></html>", "text/html")
        return super().do_GET()


def make_server(db_path, environ, *, host="0.0.0.0", port=8765, limits=None):
    runtime = Runtime(environ)
    limits = limits or IngressLimits()
    if limits.max_handlers > 16 or limits.request_timeout > 10:
        raise HostedLiveError("LIVE_INGRESS_LIMIT_INVALID")
    server = BoundedHTTPServer((host, port), HostedHandler, limits=limits)
    try:
        server.store = _private_database(db_path)
        server.runtime = runtime
        granted_runs(server.store)
        server.enable_recordings = False
        return server
    except BaseException:
        server.server_close(); raise


def _install_expiry(runtime):
    # Only the CLI installs this hard local stop. In the private Docker PID
    # namespace, exiting the main process stops its remaining local children.
    # A provider request already accepted remotely cannot be un-billed here.
    delay = max(0, (runtime.expires - _now()).total_seconds())
    timer = threading.Timer(delay, lambda: os._exit(78))
    timer.daemon = True; timer.start()
    return timer


def _claim_role(store, owner, kind):
    """Same lease/fencing scheme, with recovery and analysis in separate lanes."""
    if kind not in {"reconcile", "investigate"}:
        raise HostedLiveError("LIVE_WORKER_ROLE_INVALID")
    now = time.time()
    with store.connect(write=True) as db:
        job = db.execute("""SELECT j.* FROM jobs j JOIN runs r ON r.id=j.run_id
            JOIN hosted_live_case_grants g ON g.run_id=j.run_id
            WHERE j.kind=? AND r.cancel_requested=0 AND
            (j.state='PENDING' AND j.available_at<=? OR j.state='RUNNING' AND j.lease_until<=?)
            ORDER BY j.available_at,j.created_at LIMIT 1""", (kind, now, now)).fetchone()
        if job is None:
            return None
        db.execute("""UPDATE jobs SET state='RUNNING',owner=?,lease_until=?,fence_token=fence_token+1,
            attempts=attempts+1,updated_at=? WHERE id=?""", (owner, now+30, utcnow(), job["id"]))
        result = dict(db.execute("SELECT * FROM jobs WHERE id=?", (job["id"],)).fetchone())
        result["payload"] = json.loads(result["payload_json"])
        return result


def worker_cycle(store, runtime, owner, kind):
    """Real adapters only; tests may patch dependencies, never client supplied."""
    from .investigator import Investigation
    from .worker import _investigation_result, _reserve_investigation_job
    runtime.active()
    job = _claim_role(store, owner, kind)
    if job is None:
        return False
    try:
        require_case(store, job["run_id"])
        runtime.active()
        service = MerchantService(store)
        terminal = "COMPLETED"
        if kind == "reconcile":
            result = service.reconcile(job["run_id"])
            attempt = job["payload"].get("attempt", 0)
            if result.get("verdict") == "INCONCLUSIVE" and attempt < 29:
                store.enqueue(job["run_id"], "reconcile", {"attempt": attempt+1},
                              semantic_key=f"recovery-{attempt+1}", available_at=time.time()+2)
        else:
            result = _reserve_investigation_job(store, job, owner)
            if result is None:
                result = Investigation(store, service).run(job["run_id"])
            result = _investigation_result(result)
            terminal = ("COMPLETED" if result.get("status") == "COMPLETED" else
                        "CANCELLED" if result.get("status") == "CANCELLED" else "FAILED")
        store.complete_job(job["id"], owner, job["fence_token"], result, state=terminal)
    except Exception as exc:
        cancelled = store.get_run(job["run_id"])["cancel_requested"]
        result = {"status": "CANCELLED" if cancelled else "FAILED", "reason": "LIVE_JOB_STOPPED:" + type(exc).__name__}
        try:
            store.complete_job(job["id"], owner, job["fence_token"], result,
                               state="CANCELLED" if cancelled else "FAILED")
        except ValueError:
            pass
        store.record_event(job["run_id"], "worker", "job_cancelled" if cancelled else "job_failed",
                           {"job_id": job["id"], "error": type(exc).__name__})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("api", "worker", "worker-role"))
    parser.add_argument("--role", choices=("reconcile", "investigate"))
    parser.add_argument("--env-file", default="/run/secrets/crashcart.env")
    parser.add_argument("--db", default="/data/workspace.sqlite3")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    os.umask(0o077)
    if os.geteuid() == 0:
        raise SystemExit("LIVE_NONROOT_REQUIRED")
    children = []
    try:
        env = read_credentials(args.env_file)
        for name in list(os.environ):
            if name.startswith(("CRASHCART_", "PAYPAL_", "MODAL_", "OPENAI_", "KERNEL_", "AG_STUDIO_")):
                del os.environ[name]
        os.environ.update(env)
        runtime = Runtime(env)
        timer = _install_expiry(runtime)
        def terminate(*_):
            raise SystemExit(0)
        signal.signal(signal.SIGTERM, terminate)
        if args.command == "api":
            server = make_server(args.db, env, port=args.port)
            try:
                server.serve_forever()
            finally:
                timer.cancel(); server.server_close()
        elif args.command == "worker":
            # Two private child workers preserve recovery capacity while the
            # analysis lane waits on a bounded model response. No extra service.
            for role in ("reconcile", "investigate"):
                children.append(subprocess.Popen([sys.executable, "-m", "crashcart.hosted_live", "worker-role",
                    "--role", role, "--env-file", args.env_file, "--db", args.db]))
            while True:
                runtime.active()
                if any(child.poll() is not None for child in children):
                    raise HostedLiveError("LIVE_WORKER_EXITED")
                time.sleep(1)
        else:
            if args.role is None:
                raise HostedLiveError("LIVE_WORKER_ROLE_REQUIRED")
            store = _private_database(args.db)
            granted_runs(store)
            owner = "hosted-" + args.role + "-" + uuid.uuid4().hex
            while True:
                worker_cycle(store, runtime, owner, args.role)
                time.sleep(1)
    except (HostedLiveError, ModelAllowanceError, ModelTransportError) as exc:
        raise SystemExit(exc.code) from None
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()


if __name__ == "__main__":
    main()
