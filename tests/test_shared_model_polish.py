"""Local equivalence checks; synthetic text and loopback HTTP only."""
from contextlib import redirect_stdout
from copy import deepcopy
import http.client
import io
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from crashcart import __version__, server
from crashcart.investigator import _sanitize
from crashcart.model_allowance import MODEL
from crashcart.model_ids import DEEPSEEK_MODEL_ID
from crashcart.model_transport import MODAL_MODEL, SECRET_KEYS, redact
from crashcart.promise import _expected_values
from crashcart.redaction import sanitize_text
from crashcart.store import Store


def legacy_redact(value, environ, *, bounded=False):
    """Frozen previous output policy, including truncation before email substitution."""
    if isinstance(value, dict):
        return {key: legacy_redact(item, environ, bounded=bounded) for key, item in value.items()
                if isinstance(key, str) and not re.search(r"secret|authorization|api.?key|password|payer|shipping", key, re.I)}
    if isinstance(value, list):
        return [legacy_redact(item, environ, bounded=bounded) for item in (value[:50] if bounded else value)]
    if isinstance(value, str):
        for name in SECRET_KEYS:
            secret = environ.get(name)
            if isinstance(secret, str) and secret:
                value = value.replace(secret, "[REDACTED]")
        output = value[:4000] if bounded else value
        return re.sub(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", output) if "@" in value else output
    return value


class SharedRedactionTests(unittest.TestCase):
    def examples(self):
        return [
            None, 0, False, ("unchanged tuple",),
            {"AUTHORIZATION": "do not retain", "api-key": "remove", "payer": {}, 7: "non-string key",
             "nested": [{"safe": "buyer@example.com synthetic-key"}, "x" * 4100], "safe": "keep"},
            [str(index) for index in range(55)],
            "x" * 3995 + "person@example.com", "x" * 4001 + "@example.com",
            "synthetic-key" * 1000, "not an email @ without a domain", "a+b.c-d@example.test",
        ]

    def test_transport_retains_exact_unbounded_output_and_input(self):
        environ = {"OPENAI_API_KEY": "synthetic-key", "MODAL_API_KEY": "", "KERNEL_API_KEY": 7}
        for value in self.examples():
            with self.subTest(kind=type(value).__name__):
                before = deepcopy(value)
                self.assertEqual(redact(value, environ), legacy_redact(value, environ))
                self.assertEqual(value, before)

    def test_investigator_retains_exact_recursive_list_and_text_bounds(self):
        environ = {"OPENAI_API_KEY": "synthetic-key"}
        with patch.dict(os.environ, environ, clear=True):
            for value in self.examples():
                with self.subTest(kind=type(value).__name__):
                    self.assertEqual(_sanitize(value), legacy_redact(value, environ, bounded=True))
        self.assertEqual(len(_sanitize(list(range(55)))), 50)

    def test_text_helper_preserves_replacement_then_truncation_order(self):
        value = "synthetic-key " + "x" * 3995 + " buyer@example.com"
        environ = {"OPENAI_API_KEY": "synthetic-key"}
        self.assertEqual(sanitize_text(value, environ, max_characters=4000),
                         legacy_redact(value, environ, bounded=True))
        self.assertEqual(sanitize_text(value, environ), legacy_redact(value, environ))

    def test_model_identity_aliases_are_unchanged(self):
        self.assertEqual(MODAL_MODEL, DEEPSEEK_MODEL_ID)
        self.assertEqual(MODEL, DEEPSEEK_MODEL_ID)
        self.assertEqual(DEEPSEEK_MODEL_ID, "deepseek-ai/DeepSeek-V4.1-Flash")

    def test_expected_promise_projection_is_fresh_and_not_mutable_shared_state(self):
        first, second = _expected_values(), _expected_values()
        self.assertIsNot(first, second)
        self.assertEqual(first, {"amount_minor": 2900, "currency": "USD", "ticket_count": 1,
                                 "deadline_seconds": 60, "timing_trigger": "capture_completed",
                                 "delivery_kind": "ticket"})
        first["deadline_seconds"] = 900
        self.assertEqual(second["deadline_seconds"], 60)
        self.assertEqual(_expected_values()["deadline_seconds"], 60)


class ServiceDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.httpd.store = Store(Path(self.folder.name) / "state.sqlite3")
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(2)
        self.folder.cleanup()

    def request(self, path):
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=3)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_health_and_http_banner_share_the_package_version(self):
        with patch.object(server.Handler, "recorded_get", return_value=False):
            status, headers, body = self.request("/healthz")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["version"], __version__)
        self.assertIn("CrashCart/" + __version__, headers["Server"])

    def test_get_failure_logs_only_type_and_keeps_response_generic(self):
        output = io.StringIO()
        with redirect_stdout(output), patch.object(server.Handler, "recorded_get",
                                                   side_effect=RuntimeError("private-buyer@example.com sensitive text")):
            status, _, body = self.request("/example")
        self.assertEqual(status, 500)
        self.assertEqual(output.getvalue(), "request error: RuntimeError\n")
        self.assertNotIn(b"private-buyer", body)
        self.assertEqual(json.loads(body), {"error": "Internal error; inspect local service logs"})


if __name__ == "__main__":
    unittest.main()
