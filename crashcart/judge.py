"""Keyless, read-only review of a real recorded input, re-executed locally.

This entry point never loads .env, imports live adapters, or starts a worker.
Only the checked-in example and newly executed replay projections are served.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
import webbrowser
import zipfile

from .replay import ReplayError, export_package, load_package
from .replay_workspace import import_replay
from .store import Store

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "evidence/runs/paypal-live/early-response-loss-input.json"
INPUT_SHA256 = "07609306e1310420c49e9908ee26b2da361e42028ea6f40b5d19005d47498288"
AI_HISTORY = ROOT / "evidence/runs/submission-ready/ai-historical-summary.json"
AI_HISTORY_SHA256 = "152c1c77dfcc219b32d7ae36c06ad7b39a35656e95f54f87a6691fe95010c8fb"
ASSETS = ("index.html", "product.html", "integrations.html", "demo.html", "app.js", "style.css", "site.js")


def json_bytes(value):
    return (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()


def licensed_replay(archive, licence):
    """Keep the strict replay format while carrying its required MIT notice.

    README is already a required, hash-bound member. No executable member or
    input is modified, and the core export format/validator stay unchanged.
    """
    with zipfile.ZipFile(archive) as original:
        members = {name: original.read(name) for name in original.namelist()}
    members["README.md"] += b"\n## Licence\n\n" + licence
    manifest = json.loads(members["manifest.json"])
    manifest["files"]["README.md"] = hashlib.sha256(members["README.md"]).hexdigest()
    members["manifest.json"] = json_bytes(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as delivered:
        for name, content in members.items():
            delivered.writestr(name, content)
    return output.getvalue()


def historical_ai(source_path=None):
    """Project the pinned public historical summary; never replay or infer AI.

    The source retains private-artifact provenance paths. They are not needed by
    the product view, so only its explicitly allowed presentation fields leave
    this boundary. A hash is a source binding, not provider authentication.
    """
    raw = Path(AI_HISTORY if source_path is None else source_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != AI_HISTORY_SHA256:
        raise ReplayError("The reviewed historical AI summary changed; refusing to publish a different investigation")
    try:
        source = json.loads(raw)
        operations = source["actual_operations"]
        trace = source["trace"]
        result = source["deterministic_result"]
        expected_operations = {"model_calls": 3, "paypal_oauth_requests": 1,
                               "paypal_existing_order_gets": 1, "new_payments": 0,
                               "kernel_sessions": 0, "studio_queries": 0}
        if (source["kind"] != "sanitized-historical-ai-evidence-summary-v1"
                or source["new_verification_claim"] is not False
                or source["public_judge_mode_calls_model"] is not False
                or source["same_case_as_public_faulty_replay"] is not False
                or source["provider"] != "Modal"
                or source["model"] != "deepseek-ai/DeepSeek-V4.1-Flash"
                or source["historical_capture_date"] != "2026-10-23"
                or operations != expected_operations
                or any(type(value) is not int for value in operations.values())
                or not isinstance(trace, list) or len(trace) != 3
                or result != {"verdict": "PASS", "signature": "ticket_delivered_once_on_time",
                              "delivery_latency_seconds": 3.417739}):
            raise ValueError("historical scope")
        for key in ("investigation_started_at", "investigation_finished_at"):
            value = source[key]
            if not isinstance(value, str) or not value.startswith("2026-10-26T"):
                raise ValueError("historical date")
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError("historical timezone")
        if (datetime.fromisoformat(source["investigation_finished_at"].replace("Z", "+00:00"))
                < datetime.fromisoformat(source["investigation_started_at"].replace("Z", "+00:00"))):
            raise ValueError("historical sequence")
        projected_trace = []
        for index, action in enumerate(("read_provider", "read_merchant", "finish"), 1):
            step = trace[index - 1]
            evidence = step["evidence_categories_before_response"]
            if (type(step["step"]) is not int or step["step"] != index
                    or step["action"] != action or not isinstance(evidence, list)
                    or len(evidence) != index - 1
                    or any(not isinstance(value, str) or not 1 <= len(value) <= 200 for value in evidence)):
                raise ValueError("historical trace")
            projected = {"step": index, "action": action,
                         "evidence_categories_before_response": list(evidence)}
            for key in ("reasoning_summary", "exact_model_excerpt"):
                if key in step:
                    value = step[key]
                    if not isinstance(value, str) or not 1 <= len(value) <= 1000:
                        raise ValueError("historical text")
                    projected[key] = value
            if not any(key in projected for key in ("reasoning_summary", "exact_model_excerpt")):
                raise ValueError("missing historical explanation")
            projected_trace.append(projected)
    except (KeyError, TypeError, ValueError):
        raise ReplayError("The historical AI summary has an unsupported scope or shape") from None
    return {"mode": "RECORDED_AI_INVESTIGATION", "fresh_execution": False,
            "same_case_as_public_faulty_replay": False,
            "provider": source["provider"], "model": source["model"],
            "investigation_started_at": source["investigation_started_at"],
            "investigation_finished_at": source["investigation_finished_at"],
            "historical_capture_date": source["historical_capture_date"],
            "actual_operations": dict(operations), "trace": projected_trace,
            "deterministic_result": dict(result), "source_summary_sha256": AI_HISTORY_SHA256,
            "limits": ["An earlier recorded AI investigation of a different historical case, not the faulty checkout replay.",
                       "The historical model read one existing PayPal Sandbox order and copied merchant records; no new checkout occurred.",
                       "Viewing these saved steps makes no model or provider request and creates no payment.",
                       "The public summary and source hash do not independently authenticate the underlying private provider receipts."]}


def prepare_review(input_path=INPUT, *, exported=False):
    """Execute both variants and freeze a public, credential-free review bundle."""
    raw = Path(input_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ReplayError("The reviewed historical input changed; refusing to publish a different example")
    tape = load_package(input_path)
    ai_history = historical_ai()
    licence = (ROOT / "LICENSE").read_bytes()
    cases = {}
    downloads = {"downloads/input.json": ("application/json", raw)}
    with tempfile.TemporaryDirectory(prefix="crashcart-judge-") as folder:
        store = Store(Path(folder) / "review.sqlite3")
        for variant, expected in (("defective", ("FAIL", "paid_without_ticket", 0)),
                                  ("healthy", ("PASS", "ticket_delivered_once_on_time", 1))):
            receipt = import_replay(store, tape, variant)
            actual = (receipt["verdict"], receipt["signature"], receipt["ticket_count"])
            if actual != expected:
                raise ReplayError(f"{variant} replay does not meet the published example: {actual}")
            attempt = store.get_attempts(receipt["run_id"])[0]
            execution = attempt["result"]["execution"]
            purchase = store.purchase_for_run(receipt["run_id"])
            merchant = store.merchant_state(receipt["purchase_id"])
            case = {"variant": variant, "receipt": receipt, "execution": execution,
                    "purchase": purchase, "merchant": merchant,
                    "events": store.get_events(receipt["run_id"])}
            cases[variant] = case
            downloads[f"downloads/{variant}.json"] = ("application/json", json_bytes(case))
        archive = Path(folder) / "replay.zip"
        export_package(tape, archive)
        downloads["downloads/replay.zip"] = ("application/zip", licensed_replay(archive, licence))
    data = {"mode": "RECORDED_REPLAY", "fresh_execution": False,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "computed_when": "site build" if exported else "app launch",
            "input_file_sha256": INPUT_SHA256, "invariant": tape["invariant"],
            "recorded_source": tape["source"], "original_records": tape["records"],
            "cases": cases, "network_calls": 0, "historical_ai": ai_history,
            "limits": ["Historical PayPal Sandbox observations, replayed without new service calls.",
                       "The healthy merchant is re-executed on the same recorded input and clock.",
                       "This is not a fresh payment, a deployed repair or a new AI investigation.",
                       "The original fault video is unavailable; saved page observations remain inspectable."]}
    files = {name: ("text/html; charset=utf-8" if name.endswith("html") else
                    "text/javascript; charset=utf-8" if name.endswith("js") else "text/css; charset=utf-8",
                    (ROOT / "web/judge" / name).read_bytes()) for name in ASSETS}
    files["data.json"] = ("application/json", json_bytes(data))
    files["LICENSE"] = ("text/plain; charset=utf-8", licence)
    files.update(downloads)
    return files


def export_site(destination):
    target = Path(destination)
    if target.exists():
        raise ValueError("Export destination already exists; choose a new directory")
    files = prepare_review(exported=True)
    target.mkdir(parents=True)
    for name, (_, body) in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    # GitHub Pages serves these exact static files; it does not run a backend.
    (target / ".nojekyll").write_text("")
    return {"path": str(target), "mode": "RECORDED_REPLAY", "files": len(files),
            "sha256": {name: hashlib.sha256(body).hexdigest() for name, (_, body) in files.items()}}


def make_server(files, host="127.0.0.1", port=8766):
    class ReviewHandler(BaseHTTPRequestHandler):
        def reply(self, status, content_type, body, *, download=False):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            if download:
                self.send_header("Content-Disposition", 'attachment; filename="' + urlsplit(self.path).path.rsplit("/", 1)[-1] + '"')
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def do_GET(self):
            path = urlsplit(self.path).path
            key = "index.html" if path == "/" else path.removeprefix("/")
            if key not in files:
                self.reply(404, "application/json", b'{"error":"This review only serves recorded examples"}\n')
                return
            content_type, body = files[key]
            self.reply(200, content_type, body, download=key.startswith("downloads/"))

        do_HEAD = do_GET

        def do_POST(self):
            self.close_connection = True
            self.reply(405, "application/json", b'{"error":"Recorded review is read-only; no payment or live action is available"}\n')

        do_PUT = do_POST
        do_PATCH = do_POST
        do_DELETE = do_POST

        def log_message(self, *_):
            # Do not log arbitrary request text or environment values.
            pass

    return ThreadingHTTPServer((host, port), ReviewHandler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-open", action="store_true", help="Do not launch the local browser")
    parser.add_argument("--export-site", metavar="DIRECTORY", help="Execute replay and export a static, read-only review")
    args = parser.parse_args(argv)
    if args.export_site:
        print(json.dumps(export_site(args.export_site), indent=2))
        return 0
    server = make_server(prepare_review(), args.host, args.port)
    port = server.server_address[1]
    display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{display_host}:{port}/demo.html#investigation"
    print(f"CrashCart recorded review: {url}\nBoth outcomes recomputed at launch. No new payment or service call.\nPress Ctrl+C to stop.", flush=True)
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
