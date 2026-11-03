"""Actual loopback concurrency; provider results are constructed LOCAL_TEST data."""
from contextlib import contextmanager
import http.client
import socket
import threading
import time
import unittest
from unittest.mock import patch

from crashcart import verification_gateway as gateway
from tests import test_verification_gateway as fixture
from tests.test_webhook_raw_http import RAW_EVENT


class SlowBodyTests(unittest.TestCase):
    setUp = fixture.GatewayTests.setUp
    close_gateway = fixture.GatewayTests.close_gateway
    request = fixture.GatewayTests.request
    create_order = fixture.GatewayTests.create_order
    base = fixture.GatewayTests.base

    @contextmanager
    def pending(self, path, *, length=2, prefix=b"{", auth=False):
        entered = threading.Event()
        finished = threading.Event()
        original = gateway.GatewayHandler.json_body

        def observed(handler, **kwargs):
            if handler.headers.get("X-Local-Test-Pending") != "yes":
                return original(handler, **kwargs)
            entered.set()
            try:
                return original(handler, **kwargs)
            finally:
                finished.set()

        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=2)
        with patch.object(gateway.GatewayHandler, "json_body", observed):
            connection.putrequest("POST", path)
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(length))
            connection.putheader("Origin", self.httpd.scope.origin)
            connection.putheader("X-Local-Test-Pending", "yes")
            if auth:
                connection.putheader("Authorization", "Bearer " + self.httpd.token)
            connection.endheaders(prefix)
            try:
                yield connection, entered, finished
            finally:
                if connection.sock:
                    try:
                        connection.sock.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                connection.close()
                finished.wait(1)

    def test_incomplete_public_login_does_not_block_health(self):
        with self.pending("/api/login") as (_, entered, finished):
            self.assertTrue(entered.wait(1))
            connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=0.4)
            try:
                connection.request("GET", "/healthz")
                response = connection.getresponse()
                self.assertEqual(response.status, 200)
                response.read()
                self.assertFalse(finished.is_set(), "Health must finish while login body is still incomplete")
            finally:
                connection.close()
        self.assertEqual(self.provider.calls, [])

    def test_revoke_completes_during_body_and_prevents_order(self):
        with self.pending(self.base + "/order", auth=True) as (connection, entered, _):
            self.assertTrue(entered.wait(1))
            done = threading.Event()
            thread = threading.Thread(target=lambda: (self.httpd.revoke(), done.set()), daemon=True)
            thread.start()
            try:
                self.assertTrue(done.wait(0.4), "Revoke must not wait for a request body")
                connection.send(b"}")
                response = connection.getresponse()
                self.assertEqual(response.status, 410)
                response.read()
            finally:
                # Release a pre-repair blocked revoke before fixture cleanup.
                connection.close()
                thread.join(timeout=1)
        self.assertEqual(self.provider.calls, [])
        self.assertIsNone(self.store.purchase_for_run(self.run["id"])["order_id"])
        self.assertEqual(self.httpd._mutations, 0)

    def test_trickled_body_has_total_deadline_not_idle_timeout(self):
        # Shorten the same production policy for a bounded regression, not time.monotonic.
        with patch.object(gateway, "BODY_READ_TIMEOUT_SECONDS", 0.3, create=True):
            with self.pending("/api/login", length=100) as (connection, entered, finished):
                self.assertTrue(entered.wait(1))
                started = time.monotonic()
                while time.monotonic() - started < 0.7 and not finished.wait(0.04):
                    connection.send(b" ")  # Always inside the ten-second idle timeout.
                self.assertTrue(finished.is_set(), "Continuous input must not extend the total deadline")
                self.assertLess(time.monotonic() - started, 0.65)
                response = connection.getresponse()
                self.assertEqual(response.status, 408)
                self.assertIn(b"BODY_READ_TIMEOUT", response.read())
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.httpd._mutations, 0)
        self.assertEqual(self.request("GET", "/healthz")[0], 200)

    def test_remaining_gateway_lifetime_caps_body_wait(self):
        self.httpd._monotonic_deadline = time.monotonic() + 0.3
        with self.pending(self.base + "/order", auth=True) as (connection, entered, finished):
            self.assertTrue(entered.wait(1))
            self.assertTrue(finished.wait(0.7), "Incomplete body must stop at gateway expiry")
            response = connection.getresponse()
            self.assertEqual(response.status, 408)
            response.read()
        self.assertEqual(self.request("GET", "/healthz")[0], 410)
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.httpd._mutations, 0)

    def test_truncated_body_is_rejected_without_mutation(self):
        with self.pending(self.base + "/order", auth=True) as (connection, entered, _):
            self.assertTrue(entered.wait(1))
            connection.sock.shutdown(socket.SHUT_WR)
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn(b"INCOMPLETE_BODY", response.read())
        self.assertEqual(self.provider.calls, [])
        self.assertEqual(self.httpd._mutations, 0)
        self.assertEqual(self.request("GET", "/healthz")[0], 200)

    def test_concurrent_order_body_does_not_duplicate_order(self):
        with self.pending(self.base + "/order", auth=True) as (connection, entered, finished):
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.create_order(), "ORDER_SCOPED")
            self.assertFalse(finished.is_set())
            connection.send(b"}")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
        self.assertEqual(sum(call[0] == "create" for call in self.provider.calls), 1)
        self.assertEqual(self.store.purchase_for_run(self.run["id"])["order_id"], "ORDER_SCOPED")

    def test_unauthenticated_financial_route_rejects_before_body_read(self):
        with self.pending(self.base + "/order", prefix=b"") as (connection, entered, _):
            connection.sock.settimeout(0.4)
            response = connection.getresponse()
            self.assertEqual(response.status, 401)
            response.read()
            self.assertFalse(entered.is_set())
        self.assertEqual(self.provider.calls, [])

    def test_fragmented_webhook_preserves_exact_raw_bytes_and_dedup(self):
        self.create_order()
        raw = RAW_EVENT.replace(b"ORDER_RAW", b"ORDER_SCOPED")
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port, timeout=2)
        try:
            connection.putrequest("POST", "/api/webhooks/paypal")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", str(len(raw)))
            connection.putheader("test-signature", "local-verified-fixture")
            connection.endheaders()
            # Split inside UTF-8 as well as across JSON punctuation and number text.
            for offset in range(0, len(raw), 3):
                connection.send(raw[offset:offset + 3])
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            response.read()
        finally:
            connection.close()
        self.assertEqual(self.request("POST", "/api/webhooks/paypal", raw=raw,
            headers={"test-signature": "local-verified-fixture"}, auth=False, origin=False)[0], 200)
        self.assertEqual(self.request("POST", "/api/webhooks/paypal", raw=raw,
            headers={"test-signature": "bad-local-signature"}, auth=False, origin=False)[0], 400)
        checks = [call for call in self.provider.calls if call[0] == "verify"]
        self.assertEqual(len(checks), 3)
        self.assertTrue(all(call[3] == raw for call in checks))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], 1)
        self.assertEqual(self.store.merchant_state(self.purchase["id"])["ticket_count"], 0)


if __name__ == "__main__":
    unittest.main()
