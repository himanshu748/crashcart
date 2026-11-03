"""Actual loopback HTTP checks; temporary HTML fixtures, no payment operations."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from crashcart import server
from crashcart.store import Store


PINNED_SENSOR_CSS = b"@property --ag-studio-color-change { syntax: '<color>'; inherits: true; initial-value: transparent; }"


def style_hash_source(css):
    return "'sha256-" + base64.b64encode(hashlib.sha256(css).digest()).decode("ascii") + "'"


class StudioRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="crashcart-studio-routes-")
        cls.root = Path(cls.folder.name)
        web = cls.root / "web"
        (web / "studio").mkdir(parents=True)
        (web / "index.html").write_text("<!doctype html><title>CrashCart fixture</title>")
        (web / "app.js").write_text("/* ordinary script fixture */")
        (web / "style.css").write_text("body { color: black; }")
        (web / "studio/index.html").write_text('<!doctype html><meta name="csp-nonce" content="__STYLE_NONCE__"><script src="/studio/main.js"></script>')
        (web / "studio/main.js").write_text("/* studio asset fixture __STYLE_NONCE__ */")
        (cls.root / "outside-secret.txt").write_text("must-not-be-served")
        (web / "outside-link.txt").symlink_to(cls.root / "outside-secret.txt")
        cls.token = "isolated-route-test-token-not-a-real-secret"
        cls.env_patch = patch.dict(os.environ, {"CRASHCART_OPERATOR_TOKEN": cls.token,
            "CRASHCART_PUBLIC_URL": "", "CRASHCART_ALLOW_SANDBOX": "0", "CRASHCART_ALLOW_MODEL": "0"})
        cls.root_patch = patch.object(server, "ROOT", cls.root)
        cls.service_patch = patch("crashcart.service.MerchantService", side_effect=AssertionError("Route tests must not construct a payment service"))
        cls.env_patch.start()
        cls.root_patch.start()
        cls.payment_service = cls.service_patch.start()
        cls.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.httpd.store = Store(cls.root / "test.sqlite3")
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=2)
        cls.payment_service.assert_not_called()
        cls.service_patch.stop()
        cls.root_patch.stop()
        cls.env_patch.stop()
        cls.folder.cleanup()

    def request(self, method, path, body=None, headers=None):
        values = dict(headers or {})
        if body is not None:
            body = json.dumps(body)
            values["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=3)
        try:
            connection.request(method, path, body, values)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def assert_strict_csp(self, headers, nonce=None):
        policy = headers["Content-Security-Policy"]
        directives = dict(segment.strip().split(" ", 1) for segment in policy.split(";") if segment.strip())
        self.assertEqual(directives["script-src"], "'self'")
        studio_style = f" 'nonce-{nonce}' {style_hash_source(PINNED_SENSOR_CSS)}" if nonce else ""
        self.assertEqual(directives["style-src"], "'self'" + studio_style)
        if not nonce:
            self.assertNotIn("'nonce-", policy)
            self.assertNotIn("'sha256-", policy)
        self.assertEqual(directives["connect-src"], "'self'")
        self.assertEqual(directives["frame-ancestors"], "'none'")
        self.assertNotIn("unsafe-inline", policy)
        self.assertNotIn("unsafe-eval", policy)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_studio_html_nonce_matches_csp_and_changes_every_response(self):
        nonces = set()
        for _ in range(5):
            status, headers, body = self.request("GET", "/studio/index.html")
            self.assertEqual(status, 200)
            self.assertEqual(headers["Content-Type"], "text/html")
            match = re.search(rb'<meta name="csp-nonce" content="([A-Za-z0-9_-]+)">', body)
            self.assertIsNotNone(match)
            nonce = match.group(1).decode()
            self.assertGreaterEqual(len(nonce), 32)
            self.assertNotIn(b"__STYLE_NONCE__", body)
            self.assert_strict_csp(headers, nonce)
            nonces.add(nonce)
        self.assertEqual(len(nonces), 5)

    def test_studio_policy_allows_only_exact_pinned_sensor_hash(self):
        # Independently derive the source expression from the pinned 3.0.0
        # sensor's exact UTF-8 bytes, without importing the server's constant.
        self.assertEqual(len(PINNED_SENSOR_CSS), 101)
        expected_hash = style_hash_source(PINNED_SENSOR_CSS)
        rejected_hashes = [style_hash_source(PINNED_SENSOR_CSS + b"\n"),
                           style_hash_source(PINNED_SENSOR_CSS.replace(b"transparent", b"red"))]
        nonces = set()
        for _ in range(2):
            status, headers, body = self.request("GET", "/studio/index.html")
            self.assertEqual(status, 200)
            match = re.search(rb'<meta name="csp-nonce" content="([A-Za-z0-9_-]{32})">', body)
            self.assertIsNotNone(match)
            nonce = match.group(1).decode("ascii")
            style_policy = next(part.strip() for part in headers["Content-Security-Policy"].split(";")
                                if part.strip().startswith("style-src "))
            self.assertEqual(style_policy.split(), ["style-src", "'self'", f"'nonce-{nonce}'", expected_hash])
            for changed_hash in rejected_hashes:
                self.assertNotEqual(changed_hash, expected_hash)
                self.assertNotIn(changed_hash, headers["Content-Security-Policy"])
            self.assert_strict_csp(headers, nonce)
            nonces.add(nonce)
        self.assertEqual(len(nonces), 2)

    def test_normal_pages_and_assets_keep_strict_policy_without_nonce(self):
        for path in ["/", "/shop", "/return", "/cancel", "/ticket", "/app.js", "/style.css", "/studio/main.js"]:
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 200)
                self.assert_strict_csp(headers)
                if path == "/studio/main.js":
                    self.assertIn(b"__STYLE_NONCE__", body, "Only Studio HTML may be rewritten")

    def test_unauthenticated_api_and_invalid_login_remain_rejected(self):
        for method, path, body in [("GET", "/api/runs", None), ("GET", "/api/prerequisites", None), ("POST", "/api/login", {"token": "wrong"}), ("POST", "/api/runs", {"promise": "not authorized"})]:
            with self.subTest(path=path, method=method):
                status, headers, _ = self.request(method, path, body)
                self.assertEqual(status, 401)
                self.assertNotIn("Set-Cookie", headers)
                self.assert_strict_csp(headers)
        self.assertEqual(self.httpd.store.list_runs(), [])

    def test_valid_login_cookie_authenticates_read_only_api(self):
        status, headers, _ = self.request("POST", "/api/login", {"token": self.token})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        status, headers, body = self.request("GET", "/api/runs", headers={"Cookie": cookie.split(";", 1)[0]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"runs": []})
        self.assert_strict_csp(headers)

    def test_foreign_origin_is_rejected_even_with_valid_operator_token(self):
        for path, body in [("/api/login", {"token": self.token}), ("/api/runs", {"promise": "must not be created"})]:
            status, headers, payload = self.request("POST", path, body, {"Origin": "https://foreign.invalid", "Authorization": "Bearer " + self.token})
            self.assertEqual(status, 403)
            self.assertEqual(json.loads(payload)["error"], "Cross-origin writes are rejected")
            self.assert_strict_csp(headers)
        self.assertEqual(self.httpd.store.list_runs(), [])

    def test_traversal_encoded_traversal_and_symlink_escape_are_not_served(self):
        for path in ["/../outside-secret.txt", "/studio/../../outside-secret.txt", "/%2e%2e/outside-secret.txt", "/outside-link.txt", "/studio/missing.html"]:
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"must-not-be-served", body)
                self.assert_strict_csp(headers)

    def test_health_and_owned_fixture_still_work_without_provider(self):
        status, headers, body = self.request("GET", "/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["database"], "ok")
        self.assert_strict_csp(headers)
        status, _, body = self.request("GET", "/api/fixture")
        self.assertEqual(status, 200)
        fixture = json.loads(body)
        self.assertEqual((fixture["amount_minor"], fixture["currency"], fixture["recovery_seconds"]), (2900, "USD", 60))
        self.assertEqual(self.httpd.store.list_runs(), [])
