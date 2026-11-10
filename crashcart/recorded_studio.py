"""Optional, read-only AG Studio export over the existing public replay.

This module neither reads environment files nor loads live adapters. A compiled
Studio build must explicitly declare its licence state before its assets leave
the local build directory. The default keyless judge entry point is unchanged.
"""
import argparse
import base64
from copy import deepcopy
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

from . import judge

ASSETS = Path(__file__).resolve().parents[1] / "web/studio-recorded"
BUILD_MARKER = "recorded-studio-build.json"
COLOR_SENSOR_HASH = "'sha256-ydedGqCb79ipYJuuWRyOTMrKbkjYWv8WIjG7SRdnEPU='"
_SUFFIXES = {".html", ".js", ".css", ".json", ".woff", ".woff2", ".ttf", ".svg", ".png", ".ico", ".txt", ".md"}
_PRIVATE_FIELDS = {"authorization", "access_token", "refresh_token", "client_secret", "password", "api_key",
                   "license_key", "licence_key", ".env", "ag_studio_license_key", "paypal_client_secret",
                   "openai_api_key", "modal_api_key", "kernel_api_key", "crashcart_operator_token"}


def _pick(value, names):
    return {key: deepcopy(value[key]) for key in names if key in value}


def _public_payload(value):
    """Retain the original public event payload, rejecting credential fields."""
    if isinstance(value, dict):
        if any(str(key).casefold() in _PRIVATE_FIELDS for key in value):
            raise ValueError("Credential-like field in recorded event payload")
        return {key: _public_payload(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_public_payload(item) for item in value]
    return deepcopy(value)


def project_records(review):
    """Project actual replay outputs into the existing Studio widget contracts."""
    invariant = review["invariant"]
    promise = (f"One {invariant['currency']} {invariant['amount'] / 100:.2f} ticket within "
               f"{invariant['recovery_seconds']} seconds of confirmed payment")
    runs, details, rows = [], {}, []
    for variant in ("defective", "healthy"):
        case = review["cases"][variant]
        receipt, purchase, merchant = case["receipt"], case["purchase"], case["merchant"]
        run_id = receipt["run_id"]
        if (receipt["mode"] != "RECORDED_REPLAY" or receipt["network_calls"] != 0
                or purchase["run_id"] != run_id or purchase["id"] != receipt["purchase_id"]
                or receipt["merchant_variant"] != variant or case["execution"]["merchant_variant"] != variant):
            raise ValueError("Recorded case identity or execution scope mismatch")
        run = {"id": run_id, "promise": promise, "mode": "RECORDED_REPLAY",
               "state": {"PASS": "completed", "FAIL": "failed", "INCONCLUSIVE": "inconclusive"}[receipt["verdict"]],
               # Match replay.replay's actual Store.create_run: the saved fault
               # is shared input; the executed merchant is selected separately.
               "fault": {**deepcopy(case["execution"]["fault"]), "merchant": receipt["merchant_variant"]},
               "purchase_id": purchase["id"],
               "invariant_version": invariant["version"]}
        events = []
        for original in case["events"]:
            if original["run_id"] != run_id:
                raise ValueError("Recorded event belongs to another case")
            event = _pick(original, ("id", "run_id", "purchase_id", "order_id", "operation_id", "source",
                                     "event_type", "observed_at", "event_time", "caused_by"))
            event["payload"] = _public_payload(original["payload"])
            events.append(event)
        tickets = [_pick(ticket, ("id", "created_at")) for ticket in merchant["tickets"]]
        if len(tickets) != receipt["ticket_count"] or len(tickets) != merchant["ticket_count"]:
            raise ValueError("Recorded ticket count mismatch")
        runs.append(run)
        details[run_id] = {
            "run": run,
            "purchase": _pick(purchase, ("id", "run_id", "order_id", "capture_id", "amount", "currency",
                                         "payment_state", "payment_confirmed", "capture_completed_at")),
            "merchant": {**_pick(merchant, ("known", "ticket_count", "status", "observed_at")), "tickets": tickets},
            "events": events,
        }

        def latest(source=None, event_type=None):
            matches = [event for event in events if (source is None or event["source"] == source)
                       and (event_type is None or event["event_type"] == event_type)]
            return max(matches, key=lambda event: (event["observed_at"], event["id"]))["id"] if matches else None

        rows.append({"run_id": run_id, "mode": "RECORDED_REPLAY",
                     **_pick(purchase, ("payment_state", "payment_confirmed", "amount", "currency", "order_id", "capture_id")),
                     "purchase_id": purchase["id"], "ticket_count": len(tickets),
                     "ticket_id": tickets[0]["id"] if tickets else None,
                     "source_ids": {"browser_event_id": latest(source="browser"),
                                    "provider_event_id": latest(event_type="independent_order_read"),
                                    "merchant_event_id": latest(event_type="entitlement_read"),
                                    "invariant_event_id": latest(event_type="invariant_result")}})
    dataset = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"version": "recorded-studio-v1", "runs": runs, "details": details, "rows": rows,
            "dataset_sha256": hashlib.sha256(dataset).hexdigest(), "snapshot_at": review["computed_at"],
            "historical_ai": deepcopy(review["historical_ai"])}


def _gate(reason):
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            "<title>CrashCart — records explorer unavailable</title>"
            "<link rel=\"stylesheet\" href=\"../style.css\"></head><body>"
            "<a class=\"skip-link\" href=\"#main\">Skip to content</a>"
            "<header class=\"bar\"><a class=\"brand\" href=\"../index.html\">CrashCart</a>"
            "<nav class=\"bar-nav\" aria-label=\"Main\"><a href=\"../product.html\">Product</a>"
            "<a href=\"../demo.html\">Recorded example</a></nav></header>"
            "<main id=\"main\" tabindex=\"-1\"><section class=\"product\"><div>"
            "<p class=\"eyebrow\">Records explorer</p>"
            "<h1>The records explorer is not available in this build</h1>"
            "<p class=\"lead\">You can still follow the payment, inspect the missing ticket, and compare the repair in the recorded investigation.</p>"
            "<div class=\"product-actions\"><a class=\"btn btn-signal\" href=\"../demo.html#investigation\">"
            "Open the recorded investigation</a></div></div></section>"
            "<details class=\"load-state\"><summary>Why is the explorer unavailable?</summary><p>" + reason + "</p>"
            "<p>The site owner must configure a valid AG Studio licence and rebuild the explorer. "
            "This licence/build gate is not an AG Studio dashboard. No SDK, payment or AI service is loaded.</p>"
            "</details></main></body></html>").encode()


def _compiled_assets(directory):
    directory = Path(directory)
    if not directory.exists():
        return {}, "A licensed records explorer has not been built."
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Studio asset directory must be a regular directory")
    marker = directory / BUILD_MARKER
    if not marker.exists():
        return {}, "The build has no reviewed licence declaration."
    if marker.is_symlink() or not marker.is_file() or marker.stat().st_size > 4096:
        raise ValueError("Invalid Studio build declaration")
    try:
        declaration = json.loads(marker.read_bytes())
    except (ValueError, UnicodeError):
        raise ValueError("Invalid Studio build declaration") from None
    if (not isinstance(declaration, dict) or set(declaration) != {"version", "licensed"}
            or type(declaration["version"]) is not int or declaration["version"] != 1
            or type(declaration["licensed"]) is not bool):
        raise ValueError("Invalid Studio build declaration")
    if not declaration["licensed"]:
        return {}, "This build has no AG Studio licence; its SDK assets are not served."
    files, size = {}, 0
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("Studio assets cannot contain symlinks")
        if path.is_dir():
            continue
        relative = path.relative_to(directory)
        if relative.as_posix() == BUILD_MARKER:
            continue
        if (not path.is_file() or path.suffix not in _SUFFIXES
                or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) for part in relative.parts)
                or path.stat().st_size > 16 * 1024 * 1024):
            raise ValueError("Unsupported Studio asset")
        body = path.read_bytes()
        size += len(body)
        if len(files) >= 100 or size > 64 * 1024 * 1024:
            raise ValueError("Studio assets exceed export limit")
        content_type = {".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
                        ".html": "text/html; charset=utf-8", ".json": "application/json"}.get(
                            path.suffix, mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        files["explorer/" + relative.as_posix()] = (content_type, body)
    if "explorer/records.json" in files:
        raise ValueError("Compiled assets must not supply recorded data")
    if not {"explorer/index.html", "explorer/main.js", "explorer/main.css"} <= files.keys():
        raise ValueError("Incomplete licensed Studio build")
    return files, None


def explorer_policy(nonce):
    return ("default-src 'none'; script-src 'self'; style-src 'self' 'nonce-" + nonce + "' " + COLOR_SENSOR_HASH
            + "; connect-src 'self'; img-src 'self' data:; font-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def prepare_recorded_site(assets_dir=None):
    files = judge.prepare_review(exported=True)
    compiled, reason = _compiled_assets(ASSETS if assets_dir is None else assets_dir)
    if reason:
        files["explorer/index.html"] = ("text/html; charset=utf-8", _gate(reason))
        return files
    html = compiled["explorer/index.html"][1].decode("utf-8")
    if "__STYLE_NONCE__" not in html:
        raise ValueError("Studio index must declare the style nonce placeholder")
    nonce = base64.b64encode(secrets.token_bytes(18)).decode("ascii")
    compiled["explorer/index.html"] = ("text/html; charset=utf-8", html.replace("__STYLE_NONCE__", nonce).encode())
    compiled["explorer/records.json"] = ("application/json", judge.json_bytes(project_records(json.loads(files["data.json"][1]))))
    files.update(compiled)
    return files


def _nonce(files):
    found = re.search(rb'<meta name="csp-nonce" content="([A-Za-z0-9+/=]+)">', files["explorer/index.html"][1])
    return found[1].decode() if found else None


def export_site(destination, assets_dir=None):
    target = Path(destination)
    if target.exists():
        raise ValueError("Export destination already exists; choose a new directory")
    files = prepare_recorded_site(assets_dir)
    target.mkdir(parents=True)
    for name, (_, body) in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    (target / ".nojekyll").write_text("")
    nonce = _nonce(files)
    return {"path": str(target), "mode": "RECORDED_REPLAY", "files": len(files),
            "studio_available": nonce is not None,
            "explorer_content_security_policy": explorer_policy(nonce) if nonce else None,
            "sha256": {name: hashlib.sha256(body).hexdigest() for name, (_, body) in files.items()}}


def make_server(files, port=8769):
    server = judge.make_server(files, "127.0.0.1", port)
    nonce = _nonce(files)
    parent_handler = server.RequestHandlerClass

    class RecordedHandler(parent_handler):
        def send_header(self, keyword, value):
            if (keyword == "Content-Security-Policy" and nonce
                    and urlsplit(self.path).path in ("/explorer/", "/explorer/index.html")):
                value = explorer_policy(nonce)
            super().send_header(keyword, value)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/explorer":
                self.reply(308, "text/plain", b"", location="/explorer/")
            elif path == "/explorer/":
                self.reply(200, *files["explorer/index.html"])
            else:
                super().do_GET()

        do_HEAD = do_GET

    server.RequestHandlerClass = RecordedHandler
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New static export directory")
    parser.add_argument("--serve", action="store_true", help="Serve locally on 127.0.0.1 only")
    parser.add_argument("--port", type=int, default=8769)
    args = parser.parse_args(argv)
    if not args.output and not args.serve:
        parser.error("choose --output or --serve")
    if args.output:
        print(json.dumps(export_site(args.output), indent=2))
    if args.serve:
        server = make_server(prepare_recorded_site(), args.port)
        print(f"Recorded examples: http://127.0.0.1:{server.server_port}/explorer/", flush=True)
        print("No new PayPal, AI or private workspace requests.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
