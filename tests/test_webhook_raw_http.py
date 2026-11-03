"""Real loopback ingress; signature responses are explicitly synthetic LOCAL_TEST data."""
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from crashcart import paypal, server
from crashcart.service import MerchantService
from crashcart.store import Store
from crashcart.verification_gateway import VerificationGateway


RAW_EVENT = (' \n{ "resource" : {"z":1e1,"label":"café","id":"CAPTURE_RAW",'
             '"supplementary_data":{"related_ids":{"order_id":"ORDER_RAW"}}}, '
             '"event_type":"PAYMENT.CAPTURE.COMPLETED", "id":"WH_RAW_LOCAL" }\n').encode("utf-8")
HEADERS = {"Content-Type": "application/json", "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-LOCAL",
    "PAYPAL-TRANSMISSION-ID": "local-transmission", "PAYPAL-TRANSMISSION-SIG": "local-valid-signature",
    "PAYPAL-TRANSMISSION-TIME": "2026-10-28T10:00:00Z"}
ENV = {"PAYPAL_CLIENT_ID": "synthetic-client", "PAYPAL_CLIENT_SECRET": "synthetic-secret",
    "PAYPAL_WEBHOOK_ID": "synthetic-webhook", "CRASHCART_ALLOW_SANDBOX": "1",
    "CRASHCART_ALLOW_MODEL": "0", "CRASHCART_ALLOW_KERNEL": "0",
    "CRASHCART_PUBLIC_URL": "https://owned.example.test", "CRASHCART_OPERATOR_TOKEN": "synthetic-operator"}


class ExactBodySignatureTransport:
    def __init__(self):
        self.calls = []
        self.postbacks = []

    def __call__(self, request, timeout):
        self.calls.append(request)
        if request.full_url == paypal.SANDBOX_BASE + "/v1/oauth2/token":
            return 200, b'{"access_token":"synthetic-token","expires_in":3600,"token_type":"Bearer"}'
        if request.full_url != paypal.SANDBOX_BASE + "/v1/notifications/verify-webhook-signature":
            raise AssertionError("LOCAL_TEST signature transport forbids payment or other provider operations")
        self.postbacks.append(request)
        payload = json.loads(request.data)
        valid = (b'"webhook_event":' + RAW_EVENT in request.data and
                 payload["transmission_sig"] == "local-valid-signature")
        return 200, json.dumps({"verification_status": "SUCCESS" if valid else "FAILURE"}).encode()


class WebhookRawHTTPTests(unittest.TestCase):
    @contextmanager
    def running(self, kind):
        with tempfile.TemporaryDirectory(prefix="crashcart-raw-webhook-local-") as folder:
            store = Store(Path(folder) / "local.sqlite3")
            run = store.create_run("LOCAL_TEST synthetic webhook ingress", mode="LIVE_SANDBOX",
                fault={"kind": "none", "merchant": "healthy"})
            store.update_purchase(run["purchase_id"], order_id="ORDER_RAW")
            transport = ExactBodySignatureTransport()
            attempts = []
            connect = socket.socket.connect
            def loopback_only(sock, address):
                if not isinstance(address, tuple) or address[0] != "127.0.0.1":
                    attempts.append(address)
                    raise AssertionError("LOCAL_TEST external network forbidden")
                return connect(sock, address)
            with patch.dict(os.environ, ENV), patch.object(paypal, "_http_transport", transport), \
                    patch.object(socket.socket, "connect", loopback_only):
                if kind == "normal":
                    httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
                    httpd.store = store
                else:
                    httpd = VerificationGateway(store, run_id=run["id"], public_origin=ENV["CRASHCART_PUBLIC_URL"],
                        external_origin_approved=True, service=MerchantService(store))
                thread = threading.Thread(target=httpd.serve_forever, daemon=True)
                thread.start()
                try:
                    yield httpd, store, run, transport
                finally:
                    httpd.shutdown()
                    httpd.server_close()
                    thread.join(timeout=2)
                    self.assertFalse(thread.is_alive())
                    self.assertEqual(attempts, [])

    def post(self, httpd, raw, *, signature="local-valid-signature"):
        headers = {**HEADERS, "PAYPAL-TRANSMISSION-SIG": signature}
        connection = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=3)
        try:
            connection.request("POST", "/api/webhooks/paypal", raw, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def counts(self, store):
        with store.connect() as db:
            return tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("webhooks", "jobs", "tickets"))

    def test_normal_and_scoped_ingress_preserve_raw_and_verify_every_duplicate(self):
        for kind in ("normal", "scoped"):
            with self.subTest(kind=kind), self.running(kind) as (httpd, store, run, transport):
                first_status, first = self.post(httpd, RAW_EVENT)
                second_status, second = self.post(httpd, RAW_EVENT)
                self.assertEqual((first_status, second_status), (200, 200))
                self.assertEqual((first["stored"]["duplicate"], second["stored"]["duplicate"]), (False, True))
                self.assertEqual(self.counts(store), (1, 1, 0))
                self.assertEqual(store.purchase_for_run(run["id"])["payment_confirmed"], 0,
                    "Signature acceptance alone must not manufacture payment or a ticket")
                before = self.counts(store)
                bad_status, _ = self.post(httpd, RAW_EVENT, signature="local-invalid-signature")
                self.assertEqual(bad_status, 400)
                self.assertEqual(self.counts(store), before)
                self.assertEqual(len(transport.postbacks), 3, "Invalid and duplicate deliveries still verify")
                for request in transport.postbacks:
                    self.assertIn(b'"webhook_event":' + RAW_EVENT, request.data)
                    self.assertEqual(json.loads(request.data)["webhook_event"], json.loads(RAW_EVENT))

    def test_both_ingress_paths_reject_ambiguous_or_invalid_json_before_provider(self):
        invalid = [b'{"id":"WH_RAW_LOCAL","id":"OTHER"}',
            b'{"id":"WH_RAW_LOCAL","nested":{"a":1,"a":2}}',
            b'{"id":"WH_RAW_LOCAL","value":NaN}', b'{"id":"WH_RAW_LOCAL","value":1e999}',
            b'\xff{"id":"WH_RAW_LOCAL"}', b'[]', b'{"id":"WH_RAW_LOCAL"},"extra":true']
        for kind in ("normal", "scoped"):
            with self.subTest(kind=kind), self.running(kind) as (httpd, store, _, transport):
                for raw in invalid:
                    status, result = self.post(httpd, raw)
                    self.assertEqual(status, 400, result)
                self.assertEqual(transport.calls, [], "Malformed ingress must not obtain OAuth or verify remotely")
                self.assertEqual(self.counts(store), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
