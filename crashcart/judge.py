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
ASSETS = ("index.html", "app.js", "style.css")


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


def prepare_review(input_path=INPUT, *, exported=False):
    """Execute both variants and freeze a public, credential-free review bundle."""
    raw = Path(input_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != INPUT_SHA256:
        raise ReplayError("The reviewed historical input changed; refusing to publish a different example")
    tape = load_package(input_path)
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
            "cases": cases, "network_calls": 0,
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
    url = f"http://{display_host}:{port}/#investigation"
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
