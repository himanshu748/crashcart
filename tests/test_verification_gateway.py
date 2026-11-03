"""Real loopback HTTP and SQLite; all provider responses are LOCAL_TEST fakes."""
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit

from crashcart.service import MerchantService
from crashcart.store import Store
from crashcart import verification_gateway as gateway


class FakePayPal:
    """Injected provider only; no request leaves this process."""
    def __init__(self):
        self.order = None
        self.calls = []

    def create_order(self, body, request_id):
        self.calls.append(("create", deepcopy(body), request_id))
        self.order = {"id": "ORDER_SCOPED", "intent": "CAPTURE", "status": "CREATED",
            "purchase_units": deepcopy(body["purchase_units"]),
            "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER_SCOPED"}]}
        return deepcopy(self.order)

    def get_order(self, order_id):
        self.calls.append(("get", order_id))
        return deepcopy(self.order)

    def capture_order(self, order_id, body, request_id):
        self.calls.append(("capture", order_id, deepcopy(body), request_id))
        self.order["status"] = "COMPLETED"
        self.order["purchase_units"][0]["payments"] = {"captures": [{"id": "CAPTURE_SCOPED", "status": "COMPLETED",
            "amount": {"value": "29.00", "currency_code": "USD"}, "update_time": datetime.now(timezone.utc).isoformat()}]}
        return deepcopy(self.order)

    def verify_webhook(self, headers, event, *, raw_body=None):
        self.calls.append(("verify", deepcopy(headers), deepcopy(event), raw_body))
        return {k.lower(): v for k, v in headers.items()}.get("test-signature") == "local-verified-fixture"


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="crashcart-gateway-local-test-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        (self.root / "web").mkdir()
        for name in ("index.html", "app.js", "marketing.js", "style.css"):
            (self.root / "web" / name).write_text("LOCAL_TEST asset " + name)
        (self.root / "outside-secret.txt").write_text("must-not-be-served")
        self.env = patch.dict(os.environ, {"CRASHCART_PUBLIC_URL": "https://owned.example.test",
            "CRASHCART_OPERATOR_TOKEN": "global-operator-must-not-work", "CRASHCART_ALLOW_SANDBOX": "0"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.web_patch = patch.object(gateway, "ROOT", self.root)
        self.web_patch.start()
        self.addCleanup(self.web_patch.stop)
        self.connections = []
        connect = socket.socket.connect
        def local_only(sock, address):
            if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                raise AssertionError("LOCAL_TEST forbids external socket connections")
            self.connections.append(address)
            return connect(sock, address)
        self.socket_patch = patch.object(socket.socket, "connect", local_only)
        self.socket_patch.start()
        self.addCleanup(self.socket_patch.stop)
        self.store = Store(self.root / "database.sqlite3")
        self.run = self.store.create_run("LOCAL_TEST synthetic gateway proof", fault={"kind": "none", "merchant": "healthy"})
        self.purchase = self.store.purchase_for_run(self.run["id"])
        self.other = self.store.create_run("Private other run", fault={"kind": "none", "merchant": "healthy"})
        self.other_purchase = self.store.purchase_for_run(self.other["id"])
        self.provider = FakePayPal()
        self.service = MerchantService(self.store, lambda: self.provider)
        self.now = 1000.0
        self.httpd = gateway.VerificationGateway(self.store, run_id=self.run["id"],
            public_origin="https://owned.example.test", external_origin_approved=True,
            service=self.service, clock=lambda: self.now)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_gateway)

    def close_gateway(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None, *, headers=None, auth=True, origin=True, raw=None):
        values = dict(headers or {})
        if auth:
            values.setdefault("Authorization", "Bearer " + self.httpd.token)
        if origin:
            values.setdefault("Origin", self.httpd.scope.origin)
        if raw is not None:
            body = raw
            values.setdefault("Content-Type", "application/json")
        elif body is not None:
            body = json.dumps(body)
            values.setdefault("Content-Type", "application/json")
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=3)
        try:
            connection.request(method, path, body, values)
            response = connection.getresponse()
            status, returned_headers, data = response.status, dict(response.getheaders()), response.read()
            parsed = json.loads(data) if returned_headers.get("Content-Type") == "application/json" else data
            self.assertNotIn(self.httpd.token.encode(), data)
            self.assertNotIn(b"global-operator-must-not-work", data)
            return status, returned_headers, parsed
        finally:
            connection.close()

    @property
    def base(self):
        return "/api/runs/" + self.run["id"]

    def create_order(self):
        status, _, data = self.request("POST", self.base + "/order", {})
        self.assertEqual(status, 200, data)
        return data["order_id"]

    def test_loopback_scope_and_private_authentication(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")
        self.assertGreaterEqual(len(self.httpd.token), 43)
        self.assertNotEqual(self.httpd.token, os.environ["CRASHCART_OPERATOR_TOKEN"])
        for credentials in ({}, {"Authorization": "Bearer global-operator-must-not-work"},
                            {"Cookie": "crashcart_session=global-operator-must-not-work"}):
            status, _, _ = self.request("GET", "/api/runs", headers=credentials, auth=False)
            self.assertEqual(status, 401)
        status, _, data = self.request("GET", "/api/runs")
        self.assertEqual(status, 200)
        self.assertEqual([row["id"] for row in data["runs"]], [self.run["id"]])
        self.assertEqual(self.provider.calls, [])

    def test_approval_configuration_and_existing_owned_run_required(self):
        settings = {"run_id": self.run["id"], "public_origin": self.httpd.scope.origin,
                    "external_origin_approved": True, "service": self.service}
        cases = [{"external_origin_approved": False}, {"lifetime_seconds": 1801},
                 {"lifetime_seconds": True}, {"lifetime_seconds": 0}, {"run_id": "run_missing"},
                 {"public_origin": "https://different.example.test"},
                 {"public_origin": "http://owned.example.test"},
                 {"public_origin": "https://owned.example.test/"},
                 {"public_origin": "https://owned.example.test:443"},
                 {"public_origin": "https://user@owned.example.test"},
                 {"public_origin": "https://owned.example.test/path"}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(gateway.GatewayError):
                gateway.VerificationGateway(self.store, **{**settings, **changes})
        local = self.store.create_run("not live", mode="LOCAL_TEST")
        with self.assertRaisesRegex(gateway.GatewayError, "OWNED_SANDBOX_SCOPE"):
            gateway.VerificationGateway(self.store, **{**settings, "run_id": local["id"]})

    def test_login_secure_scoped_cookie_and_no_origin_programmatic_login(self):
        status, headers, data = self.request("POST", "/api/login", {"token": self.httpd.token}, auth=False, origin=False)
        self.assertEqual((status, data), (200, {"authenticated": True}))
        cookie = headers["Set-Cookie"]
        for part in ("__Host-crashcart_gateway=", "; HttpOnly", "; Secure", "; SameSite=Lax", "; Path=/", "; Max-Age=900"):
            self.assertIn(part, cookie)
        self.assertNotIn("Domain=", cookie)
        status, _, _ = self.request("GET", self.base, auth=False, headers={"Cookie": cookie.split(";", 1)[0]})
        self.assertEqual(status, 200)
        status, _, _ = self.request("POST", self.base + "/cancel", {}, auth=False, origin=False,
                                    headers={"Cookie": cookie.split(";", 1)[0]})
        self.assertEqual(status, 403)
        self.assertFalse(self.store.get_run(self.run["id"])["cancel_requested"])
        status, _, _ = self.request("POST", "/api/login", {"token": "global-operator-must-not-work"}, auth=False)
        self.assertEqual(status, 401)

    def test_host_and_forwarded_headers_never_authorize_origin(self):
        for supplied in ("http://attacker.test", "https://attacker.test", "null", self.httpd.scope.origin + "/"):
            status, _, data = self.request("POST", "/api/login", {"token": self.httpd.token}, headers={
                "Origin": supplied, "Host": "attacker.test", "X-Forwarded-Host": "owned.example.test",
                "X-Forwarded-Proto": "https"})
            self.assertEqual(status, 403, data)
        status, _, _ = self.request("GET", "/api/runs", headers={"Origin": "https://attacker.test"})
        self.assertEqual(status, 403)
        self.assertEqual(self.provider.calls, [])

    def test_exact_routes_deny_other_runs_and_admin_even_with_valid_token(self):
        blocked = ["/api/runs/" + self.other["id"], "/api/merchant/" + self.other_purchase["id"],
                   self.base + "/export", self.base + "/regression.zip", self.base + "/more",
                   "/api/studio/query", "/studio/index.html", "/.env", "/api/runs/", "/api/runs?limit=1",
                   "/marketing.js?version=1", "/marketing.js/", "/web/marketing.js", "/unlisted.js"]
        for path in blocked:
            with self.subTest(path=path):
                self.assertEqual(self.request("GET", path)[0], 404)
        for path in ("/api/runs", self.base + "/investigate", self.base + "/extra/order",
                     "/api/runs/" + self.other["id"] + "/order", self.base + "/capture/"):
            with self.subTest(path=path):
                self.assertEqual(self.request("POST", path, {})[0], 404)
        self.assertEqual(len(self.store.list_runs()), 2)
        self.assertEqual(self.provider.calls, [])

    def test_public_assets_callback_scope_and_strict_csp(self):
        for path in ("/", "/shop?run=" + self.run["id"], "/app.js", "/marketing.js", "/style.css", "/api/fixture", "/healthz"):
            status, headers, _ = self.request("GET", path, auth=False, origin=False)
            self.assertEqual(status, 200)
            self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
            self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
            self.assertEqual(headers["Cache-Control"], "no-store")
        for path in ("/return?run=" + self.other["id"], "/return?run=" + self.run["id"] + "&token=OTHER",
                     "/return?token=x&token=y", "/?unrecognized=1"):
            self.assertEqual(self.request("GET", path, auth=False)[0], 403)
        order_id = self.create_order()
        path = "/return?run=" + self.run["id"] + "&token=" + order_id + "&PayerID=LOCAL_FIXTURE"
        self.assertEqual(self.request("GET", path, auth=False, origin=False)[0], 200)

    def test_delivered_shop_declared_assets_are_available_with_exact_bytes(self):
        class RequiredAssets(HTMLParser):
            def __init__(self):
                super().__init__()
                self.assets = []

            def handle_starttag(self, tag, attributes):
                attributes = dict(attributes)
                if tag == "script" and attributes.get("src"):
                    self.assets.append((attributes["src"], "application/javascript"))
                elif tag == "link" and "stylesheet" in attributes.get("rel", "").split():
                    self.assets.append((attributes["href"], "text/css"))

        delivered_root = Path(__file__).resolve().parents[1]
        page_path = "/shop?run=" + self.run["id"]
        page_url = self.httpd.scope.origin + page_path
        expected_csp = ("default-src 'self'; script-src 'self'; style-src 'self'; "
                        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; "
                        "base-uri 'none'; form-action 'self'")
        # Serve the actual delivered document and its files, not the synthetic
        # setUp assets: a new HTML dependency must be usable through the gateway.
        with patch.object(gateway, "ROOT", delivered_root):
            status, headers, document = self.request("GET", page_path, auth=False, origin=False)
            self.assertEqual(status, 200)
            self.assertEqual(document, (delivered_root / "web/index.html").read_bytes())
            self.assertEqual(headers["Content-Type"], "text/html")
            self.assertEqual(headers["Content-Security-Policy"], expected_csp)
            parser = RequiredAssets()
            parser.feed(document.decode("utf-8"))
            required = []
            for source, mime in parser.assets:
                asset = urlsplit(urljoin(page_url, source))
                if (asset.scheme, asset.netloc) == ("https", "owned.example.test"):
                    required.append((asset.path + ("?" + asset.query if asset.query else ""), mime))
            self.assertEqual({path for path, _ in required}, {"/app.js", "/marketing.js", "/style.css"})
            for path, mime in required:
                for authenticated in (False, True):
                    with self.subTest(asset=path, authenticated=authenticated):
                        status, headers, body = self.request("GET", path, auth=authenticated, origin=False)
                        self.assertEqual(status, 200, path)
                        self.assertEqual(body, (delivered_root / "web" / path[1:]).read_bytes())
                        self.assertEqual(headers["Content-Type"], mime)
                        self.assertEqual(headers["Content-Security-Policy"], expected_csp)
                        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.provider.calls, [])

    def test_traversal_encoding_and_symlink_cannot_serve_other_files(self):
        for path in ("/../outside-secret.txt", "/%2e%2e/outside-secret.txt", "/app.js/../index.html",
                     "//app.js", "/app%2ejs", "/web\\app.js", "https://owned.example.test/app.js"):
            status, _, data = self.request("GET", path)
            self.assertEqual(status, 404, path)
            self.assertNotIn("must-not-be-served", str(data))
        (self.root / "web/app.js").unlink()
        (self.root / "web/app.js").symlink_to(self.root / "outside-secret.txt")
        self.assertEqual(self.request("GET", "/app.js")[0], 404)

    def test_expiry_and_revoke_cover_assets_login_api_and_webhook(self):
        self.now = self.httpd.scope.expires_at
        for method, path, body in (("GET", "/", None), ("GET", self.base, None),
                                   ("POST", "/api/login", {"token": self.httpd.token}),
                                   ("POST", "/api/webhooks/paypal", {})):
            self.assertEqual(self.request(method, path, body)[0], 410)
        self.assertEqual(self.provider.calls, [])
        self.now = 1001
        self.httpd.revoke()
        self.assertEqual(self.request("GET", self.base)[0], 410)

    def test_owner_or_frozen_context_change_closes_gateway(self):
        with self.store.connect(write=True) as db:
            db.execute("UPDATE runs SET promise=? WHERE id=?", ("changed scope", self.run["id"]))
        self.assertEqual(self.request("GET", self.base)[0], 403)
        self.assertEqual(self.request("POST", self.base + "/order", {})[0], 403)
        self.assertEqual(self.provider.calls, [])

    def test_fixture_ownership_environment_is_rechecked(self):
        with self.store.connect(write=True) as db:
            # Adversarial out-of-band database corruption, explicitly local.
            # Normal writes are already blocked by the schema's CHECK.
            db.execute("PRAGMA ignore_check_constraints=ON")
            db.execute("UPDATE fixtures SET environment='retired' WHERE id='workshop-v1'")
            db.execute("PRAGMA ignore_check_constraints=OFF")
        self.assertEqual(self.request("POST", self.base + "/order", {})[0], 403)
        self.assertEqual(self.provider.calls, [])

    def test_expiry_during_body_read_cannot_start_payment(self):
        original = gateway.GatewayHandler.json_body
        def expired(handler):
            value = original(handler)
            self.now = self.httpd.scope.expires_at
            return value
        with patch.object(gateway.GatewayHandler, "json_body", expired):
            self.assertEqual(self.request("POST", self.base + "/order", {})[0], 410)
        self.assertEqual(self.provider.calls, [])

    def test_monotonic_expiry_survives_wall_clock_rollback(self):
        self.httpd._monotonic_deadline = 0
        self.now = 1
        self.assertEqual(self.request("GET", self.base)[0], 410)
        self.assertEqual(self.provider.calls, [])

    def test_order_changed_outside_gateway_is_rejected(self):
        self.store.update_purchase(self.purchase["id"], order_id="EXTERNAL_CHANGE")
        self.assertEqual(self.request("GET", self.base)[0], 403)
        self.assertEqual(self.provider.calls, [])

    def test_return_origin_environment_drift_rejects_request(self):
        with patch.dict(os.environ, {"CRASHCART_PUBLIC_URL": "https://different.example.test"}):
            self.assertEqual(self.request("POST", self.base + "/order", {})[0], 403)
        self.assertEqual(self.provider.calls, [])

    def test_scoped_healthy_journey_uses_real_service_and_immutable_order(self):
        self.assertEqual(self.request("POST", self.base + "/order", {"amount": 1})[0], 400)
        order_id = self.create_order()
        sent = self.provider.calls[0][1]
        self.assertEqual(sent["purchase_units"][0]["amount"], {"currency_code": "USD", "value": "29.00"})
        self.assertEqual(sent["payment_source"]["paypal"]["experience_context"]["return_url"],
                         self.httpd.scope.origin + "/return?run=" + self.run["id"])
        self.assertEqual(self.request("POST", self.base + "/capture", {"order_id": "OTHER"})[0], 403)
        self.assertEqual(self.request("POST", self.base + "/capture", {"order_id": order_id, "status": "APPROVED"})[0], 403)
        self.assertEqual(self.request("POST", self.base + "/capture", {"order_id": order_id})[0], 400)
        self.assertFalse(any(call[0] == "capture" for call in self.provider.calls))
        self.provider.order["status"] = "APPROVED"
        status, _, result = self.request("POST", self.base + "/capture", {"order_id": order_id})
        self.assertEqual((status, result["verdict"], result["merchant"]["ticket_count"]), (200, "PASS", 1))
        self.assertEqual(self.request("POST", self.base + "/reconcile", {})[0], 200)
        self.assertEqual(self.request("POST", self.base + "/capture", {"order_id": order_id})[0], 200)
        self.assertEqual(sum(call[0] == "capture" for call in self.provider.calls), 1)
        self.assertEqual(self.store.merchant_state(self.other_purchase["id"])["ticket_count"], 0)
        self.assertIsNone(self.store.purchase_for_run(self.other["id"])["order_id"])

    def test_observation_remains_local_and_cancel_preserves_other_run(self):
        body = {"browser_kind": "LOCAL_BROWSER", "url_path": "/shop", "visible_text": "LOCAL_TEST observation", "action": "inspected"}
        self.assertEqual(self.request("POST", self.base + "/observation", body)[0], 201)
        self.assertEqual(self.request("POST", self.base + "/observation", {**body, "browser_kind": "KERNEL"})[0], 400)
        self.assertEqual(self.request("POST", self.base + "/observation", {**body, "recording_id": "forged"})[0], 400)
        self.assertEqual(self.request("POST", self.base + "/observation", {**body, "url_path": "https://unowned.test"})[0], 400)
        self.assertEqual(self.request("POST", self.base + "/cancel", {})[0], 200)
        self.assertEqual(self.request("POST", self.base + "/order", {})[0], 400)
        self.assertFalse(self.store.get_run(self.other["id"])["cancel_requested"])
        self.assertEqual(self.provider.calls, [])

    def test_webhook_order_filter_then_unchanged_authentication_and_dedup(self):
        order_id = self.create_order()
        event = {"id": "EVENT_LOCAL_TEST", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {
            "id": "CAPTURE_SCOPED", "supplementary_data": {"related_ids": {"order_id": order_id}}}}
        foreign = deepcopy(event)
        foreign["resource"]["supplementary_data"]["related_ids"]["order_id"] = "OTHER_ORDER"
        self.assertEqual(self.request("POST", "/api/webhooks/paypal", foreign, auth=False, origin=False)[0], 403)
        self.assertFalse(any(call[0] == "verify" for call in self.provider.calls))
        self.assertEqual(self.request("POST", "/api/webhooks/paypal", event, auth=False, origin=False)[0], 400)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0], 0)
        headers = {"test-signature": "local-verified-fixture"}
        first = self.request("POST", "/api/webhooks/paypal", event, headers=headers, auth=False, origin=False)
        second = self.request("POST", "/api/webhooks/paypal", event, headers=headers, auth=False, origin=False)
        self.assertEqual((first[0], first[2]["stored"]["duplicate"], second[0], second[2]["stored"]["duplicate"]),
                         (200, False, 200, True))
        checks = [call for call in self.provider.calls if call[0] == "verify"]
        self.assertEqual(len(checks), 3, "Every duplicate must still verify its external signature")
        self.assertTrue(all(call[2] == event for call in checks))
        self.assertTrue(all(call[3] == json.dumps(event).encode() for call in checks))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0], 1)
            jobs = db.execute("SELECT run_id FROM jobs").fetchall()
        self.assertEqual([row["run_id"] for row in jobs], [self.run["id"]])
        self.assertEqual(self.store.merchant_state(self.purchase["id"])["ticket_count"], 0,
                         "Webhook receipt itself must not manufacture payment confirmation")

    def test_body_bounds_types_duplicate_json_and_framing(self):
        for raw, expected in (("{", 400), ("[]", 400), ('{"a":1,"a":2}', 400), ('{"a":NaN}', 400),
                              (" " * (gateway.MAX_BODY + 1), 413)):
            self.assertEqual(self.request("POST", self.base + "/order", raw=raw)[0], expected)
        self.assertEqual(self.request("POST", self.base + "/order", {}, headers={"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("GET", self.base, raw="{}")[0], 400)
        self.assertEqual(self.request("POST", self.base + "/order", {}, headers={"Transfer-Encoding": "chunked"})[0], 400)
        self.assertEqual(self.provider.calls, [])

    def test_mutation_limit_stops_new_service_calls(self):
        self.httpd._mutations = 256
        self.assertEqual(self.request("POST", self.base + "/order", {})[0], 429)
        self.assertEqual(self.provider.calls, [])

    def test_gateway_configuration_response_does_not_claim_integrations(self):
        status, _, body = self.request("GET", "/api/prerequisites")
        self.assertEqual(status, 200)
        self.assertEqual(set(body), {"gateway"})
        self.assertFalse(body["gateway"]["connectivity_verified"])
        self.assertEqual(body["gateway"]["gateway_scope"], self.run["id"])
        self.assertEqual(self.provider.calls, [])


if __name__ == "__main__":
    unittest.main()
