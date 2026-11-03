"""Real loopback HTTP boundaries for the Studio query route; no provider I/O."""
import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import uuid4

from crashcart import server
from crashcart.store import Store
from crashcart.studio_agent import StudioQueryError


class StudioAgentRouteTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="crashcart-studio-agent-http-")
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name) / "isolated.sqlite3")
        self.token = "test-only-operator"
        env = patch.dict(os.environ, {"CRASHCART_OPERATOR_TOKEN": self.token,
            "CRASHCART_PUBLIC_URL": "", "CRASHCART_ALLOW_MODEL": "0",
            "CRASHCART_ALLOW_SANDBOX": "0"})
        env.start()
        self.addCleanup(env.stop)
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.store = self.store
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.payload = {"run_id": "run_" + "a" * 32, "request_id": str(uuid4()),
                        "question": "Show completed payments with missing tickets"}

    def stop_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(self, *, auth=True, origin=None, path="/api/studio/query", body=None):
        headers = {"Content-Type": "application/json"}
        if auth:
            headers["Authorization"] = "Bearer " + self.token
        if origin is not None:
            headers["Origin"] = origin
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=5)
        try:
            connection.request("POST", path, json.dumps(self.payload if body is None else body), headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), json.loads(response.read())
        finally:
            connection.close()

    def test_authentication_rejects_before_constructing_query_or_payment_service(self):
        with patch("crashcart.studio_agent.StudioQuery") as query, patch("crashcart.service.MerchantService") as payment:
            status, _, body = self.request(auth=False)
            self.assertEqual(status, 401)
            self.assertEqual(body["error"], "Operator access required")
            query.assert_not_called()
            payment.assert_not_called()

    def test_foreign_origin_rejected_before_query(self):
        with patch("crashcart.studio_agent.StudioQuery") as query:
            status, _, _ = self.request(origin="https://foreign.invalid")
            self.assertEqual(status, 403)
            query.assert_not_called()

    def test_typed_query_errors_keep_status_without_private_receipt(self):
        for status in (400, 409, 429, 503):
            with self.subTest(status=status), patch("crashcart.studio_agent.StudioQuery") as query:
                query.return_value.query.side_effect = StudioQueryError("TEST_QUERY_GATE", status)
                actual, headers, body = self.request()
                self.assertEqual(actual, status)
                self.assertEqual(body, {"error": "TEST_QUERY_GATE", "code": "TEST_QUERY_GATE"})
                self.assertEqual(headers["Cache-Control"], "no-store")

    def test_success_uses_owned_store_and_exact_payload_without_payment_service(self):
        receipt = {"status": "COMPLETED", "model_mode": "LOCAL_TEST", "rows": [], "count": 0}
        with patch("crashcart.studio_agent.StudioQuery") as query, patch("crashcart.service.MerchantService") as payment:
            query.return_value.query.return_value = receipt
            status, _, body = self.request()
            self.assertEqual(status, 200)
            self.assertEqual(body, receipt)
            query.assert_called_once_with(self.store)
            query.return_value.query.assert_called_once_with(self.payload)
            payment.assert_not_called()

    def test_suffix_path_cannot_invoke_query(self):
        with patch("crashcart.studio_agent.StudioQuery") as query:
            status, _, _ = self.request(path="/api/studio/query/arbitrary")
            self.assertEqual(status, 404)
            query.assert_not_called()

    def test_invalid_json_shape_rejected_before_query(self):
        with patch("crashcart.studio_agent.StudioQuery") as query:
            status, _, _ = self.request(body=[self.payload])
            self.assertEqual(status, 400)
            query.assert_not_called()
