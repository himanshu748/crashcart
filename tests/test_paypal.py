"""LOCAL_TEST only: fake transport inputs are not PayPal Sandbox evidence."""
import copy
import json
import unittest
from urllib.error import URLError

from crashcart.paypal import (PayPalError, PayPalSandbox, PaymentValidationError,
                             approval_url, inspect_capture, sanitize_snapshot, validate_capture)


def order_fixture():
    return {
        "id": "ORDER123", "intent": "CAPTURE", "status": "COMPLETED",
        "purchase_units": [{"reference_id": "purchase_123", "custom_id": "purchase_123",
            "amount": {"value": "29.00", "currency_code": "USD"},
            "payments": {"captures": [{"id": "CAPTURE123", "status": "COMPLETED",
                "amount": {"value": "29.00", "currency_code": "USD"},
                "create_time": "2026-10-22T10:00:00Z", "update_time": "2026-10-22T10:00:01Z"}]}}],
        "payer": {"email_address": "private-buyer@example.test", "name": {"given_name": "Private"}},
        "access_token": "synthetic-sensitive-provider-token",
    }


def create_body():
    return {"intent": "CAPTURE", "purchase_units": [{"reference_id": "purchase_123", "custom_id": "purchase_123",
            "amount": {"value": "29.00", "currency_code": "USD"}}]}


def created_fixture():
    return {"id": "ORDER123", "status": "PAYER_ACTION_REQUIRED", "links": [
        {"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123", "method": "GET"}]}


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, request, timeout):
        self.calls.append((request, timeout))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        status, body = response
        return status, body if isinstance(body, bytes) else json.dumps(body).encode()


class PayPalTests(unittest.TestCase):
    env = {"PAYPAL_CLIENT_ID": "synthetic-client", "PAYPAL_CLIENT_SECRET": "synthetic-secret",
           "PAYPAL_WEBHOOK_ID": "synthetic-webhook", "CRASHCART_ALLOW_SANDBOX": "1"}
    token = (200, {"access_token": "synthetic-token", "expires_in": 3600, "token_type": "Bearer"})

    def adapter(self, *responses):
        transport = FakeTransport(self.token, *responses)
        return PayPalSandbox(environ=dict(self.env), transport=transport), transport

    def test_missing_enable_or_credentials_never_calls_transport(self):
        for environment, code in (({}, "SANDBOX_DISABLED"), ({"CRASHCART_ALLOW_SANDBOX": "1"}, "MISSING_CONFIGURATION")):
            with self.subTest(code=code):
                transport = FakeTransport()
                adapter = PayPalSandbox(environ=environment, transport=transport)
                with self.assertRaises(PayPalError) as failure:
                    adapter.get_order("ORDER123")
                self.assertEqual(failure.exception.code, code)
                self.assertEqual(transport.calls, [])

    def test_actual_request_shapes_fixed_sandbox_and_token_cache(self):
        adapter, transport = self.adapter((201, created_fixture()), (201, order_fixture()), (200, order_fixture()))
        self.assertEqual(adapter.create_order(create_body(), "create-request-123")["id"], "ORDER123")
        adapter.capture_order("ORDER123", {}, "capture-request-123")
        order = adapter.get_order("ORDER123")
        self.assertEqual(len(transport.calls), 4)  # one OAuth, three independent operations
        token_request = transport.calls[0][0]
        self.assertEqual(token_request.full_url, "https://api-m.sandbox.paypal.com/v1/oauth2/token")
        self.assertEqual(token_request.data, b"grant_type=client_credentials")
        self.assertTrue(token_request.get_header("Authorization").startswith("Basic "))
        expected = [("POST", "/v2/checkout/orders", "create-request-123"),
                    ("POST", "/v2/checkout/orders/ORDER123/capture", "capture-request-123"),
                    ("GET", "/v2/checkout/orders/ORDER123", None)]
        for (request, timeout), (method, path, request_id) in zip(transport.calls[1:], expected):
            self.assertEqual(request.full_url, "https://api-m.sandbox.paypal.com" + path)
            self.assertEqual(request.method, method)
            self.assertEqual(request.get_header("Paypal-request-id"), request_id)
            self.assertEqual(timeout, 15)
            self.assertEqual(request.get_header("Prefer"), "return=representation")
        self.assertNotIn("payer", order)
        self.assertNotIn("access_token", order)

    def test_fixed_environment_ignores_arbitrary_base(self):
        adapter, transport = self.adapter((200, order_fixture()))
        adapter._env.update(PAYPAL_BASE_URL="https://attacker.example", PAYPAL_ENVIRONMENT="production")
        adapter.get_order("ORDER123")
        self.assertTrue(all(request.full_url.startswith("https://api-m.sandbox.paypal.com/") for request, _ in transport.calls))

    def test_client_price_mutation_rejected_before_network(self):
        adapter, transport = self.adapter()
        body = create_body()
        body["purchase_units"][0]["amount"]["value"] = "0.01"
        with self.assertRaises(PaymentValidationError):
            adapter.create_order(body, "create-request-123")
        self.assertEqual(transport.calls, [])

    def test_order_id_path_injection_rejected_before_network(self):
        adapter, transport = self.adapter()
        with self.assertRaises(PaymentValidationError):
            adapter.get_order("../production?secret=private")
        self.assertEqual(transport.calls, [])

    def test_timeout_preserves_ambiguous_capture_without_retry(self):
        adapter, transport = self.adapter(TimeoutError("synthetic-secret synthetic-token"))
        with self.assertRaises(PayPalError) as failure:
            adapter.capture_order("ORDER123", {}, "capture-request-123")
        self.assertEqual(failure.exception.code, "TIMEOUT")
        self.assertTrue(failure.exception.ambiguous)
        self.assertNotIn("synthetic", json.dumps(failure.exception.as_dict()))
        self.assertEqual(len(transport.calls), 2)

    def test_transport_failure_is_sanitized_and_not_retried(self):
        adapter, transport = self.adapter(URLError("synthetic-secret in upstream URL"))
        with self.assertRaises(PayPalError) as failure:
            adapter.get_order("ORDER123")
        self.assertEqual(failure.exception.code, "TRANSPORT_ERROR")
        self.assertFalse(failure.exception.ambiguous)
        self.assertNotIn("synthetic-secret", str(failure.exception))
        self.assertEqual(len(transport.calls), 2)

    def test_provider_unauthorized_does_not_retry_or_leak_body(self):
        adapter, transport = self.adapter((401, {"message": "synthetic-secret", "access_token": "synthetic-token"}))
        with self.assertRaises(PayPalError) as failure:
            adapter.get_order("ORDER123")
        self.assertEqual(failure.exception.status, 401)
        self.assertEqual(len(transport.calls), 2)
        self.assertNotIn("synthetic", str(failure.exception))

    def test_malformed_json_and_html_cannot_be_payment_success(self):
        for response in (b"not json synthetic-secret", b"[]", b"null"):
            with self.subTest(response=response):
                adapter, transport = self.adapter((200, response))
                with self.assertRaises(PayPalError) as failure:
                    adapter.capture_order("ORDER123", {}, "capture-request-123")
                self.assertEqual(failure.exception.code, "MALFORMED_RESPONSE")
                self.assertTrue(failure.exception.ambiguous)
                self.assertNotIn("synthetic-secret", str(failure.exception))
                self.assertEqual(len(transport.calls), 2)

    def test_invalid_oauth_response_never_reaches_payment_endpoint(self):
        transport = FakeTransport((200, {"access_token": "synthetic-token"}))
        adapter = PayPalSandbox(environ=self.env, transport=transport)
        with self.assertRaises(PayPalError) as failure:
            adapter.get_order("ORDER123")
        self.assertEqual(failure.exception.code, "MALFORMED_TOKEN")
        self.assertEqual(len(transport.calls), 1)

    def test_create_missing_approval_does_not_invent_success(self):
        adapter, _ = self.adapter((201, {"id": "ORDER123", "status": "CREATED"}))
        with self.assertRaises(PayPalError) as failure:
            adapter.create_order(create_body(), "create-request-123")
        self.assertEqual(failure.exception.code, "MALFORMED_ORDER")
        self.assertTrue(failure.exception.ambiguous)

    def test_create_retry_can_return_latest_completed_state(self):
        adapter, _ = self.adapter((200, order_fixture()))
        order = adapter.create_order(create_body(), "create-request-123")
        self.assertEqual(order["status"], "COMPLETED")
        # This alone is not a confirmation; service still performs get_order.

    def test_approval_links_require_sandbox_and_matching_order(self):
        self.assertEqual(approval_url(created_fixture()), "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123")
        bad_urls = ["https://www.paypal.com/checkoutnow?token=ORDER123",
                    "https://www.sandbox.paypal.com.attacker.example/checkoutnow?token=ORDER123",
                    "http://www.sandbox.paypal.com/checkoutnow?token=ORDER123",
                    "https://www.sandbox.paypal.com/checkoutnow?token=DIFFERENT",
                    "https://user:secret@www.sandbox.paypal.com/checkoutnow?token=ORDER123",
                    "https://www.sandbox.paypal.com/checkoutnow?token=ORDER123&email=private"]
        for url in bad_urls:
            with self.subTest(url=url):
                order = created_fixture()
                order["links"][0]["href"] = url
                with self.assertRaises(PaymentValidationError):
                    approval_url(order)

    def test_valid_capture_has_exact_minor_units_and_sanitized_record(self):
        result = validate_capture(order_fixture(), "ORDER123", "purchase_123")
        self.assertEqual(result["amount"], 2900)
        self.assertIs(type(result["amount"]), int)
        self.assertEqual(result["completed_at"], "2026-10-22T10:00:01Z")
        self.assertEqual(result["capture_id"], "CAPTURE123")
        self.assertNotIn("private-buyer", json.dumps(result))
        self.assertNotIn("synthetic-sensitive", json.dumps(result))

    def test_inspection_preserves_wrong_charge_while_fulfillment_validation_rejects(self):
        for value, currency, expected in [("28.00", "USD", 2800), ("29.00", "EUR", 2900), ("29", "JPY", 29)]:
            for update_order_amount in (False, True):
                with self.subTest(value=value, currency=currency, update_order_amount=update_order_amount):
                    order = order_fixture()
                    unit = order["purchase_units"][0]
                    unit["payments"]["captures"][0]["amount"] = {"value": value, "currency_code": currency}
                    if update_order_amount:
                        unit["amount"] = {"value": value, "currency_code": currency}
                    observed = inspect_capture(order, "ORDER123", "purchase_123")
                    self.assertEqual(observed["amount"], expected)
                    self.assertIs(type(observed["amount"]), int)
                    self.assertEqual(observed["currency"], currency)
                    self.assertEqual(observed["capture_id"], "CAPTURE123")
                    with self.assertRaises(PaymentValidationError):
                        validate_capture(order, "ORDER123", "purchase_123")

    def test_inspection_does_not_relax_identity_completion_or_precision(self):
        for mutate in [lambda o: o.update(id="OTHER"),
                       lambda o: o["purchase_units"][0].update(custom_id="OTHER"),
                       lambda o: o["purchase_units"][0]["payments"]["captures"][0].update(status="PENDING"),
                       lambda o: o["purchase_units"][0]["payments"]["captures"][0].update(update_time="unknown"),
                       lambda o: o["purchase_units"][0]["payments"]["captures"][0]["amount"].update(value="28.001"),
                       lambda o: o["purchase_units"][0]["payments"]["captures"][0]["amount"].update(currency_code="ZZZ")]:
            order = order_fixture()
            mutate(order)
            with self.assertRaises(PaymentValidationError):
                inspect_capture(order, "ORDER123", "purchase_123")

    def test_capture_rejects_missing_wrong_and_ambiguous_payment_objects(self):
        mutations = {
            "wrong order": lambda o: o.update(id="OTHER"),
            "wrong intent": lambda o: o.update(intent="AUTHORIZE"),
            "top-level success only": lambda o: o["purchase_units"][0].pop("payments"),
            "pending order": lambda o: o.update(status="APPROVED"),
            "multiple units": lambda o: o["purchase_units"].append(copy.deepcopy(o["purchase_units"][0])),
            "wrong reference": lambda o: o["purchase_units"][0].update(reference_id="OTHER"),
            "wrong custom id": lambda o: o["purchase_units"][0].update(custom_id="OTHER"),
            "missing custom id": lambda o: o["purchase_units"][0].pop("custom_id"),
            "unit amount mismatch": lambda o: o["purchase_units"][0]["amount"].update(value="28.00"),
            "missing capture": lambda o: o["purchase_units"][0]["payments"].update(captures=[]),
            "double capture": lambda o: o["purchase_units"][0]["payments"]["captures"].append(copy.deepcopy(o["purchase_units"][0]["payments"]["captures"][0])),
            "pending capture": lambda o: o["purchase_units"][0]["payments"]["captures"][0].update(status="PENDING"),
            "missing capture id": lambda o: o["purchase_units"][0]["payments"]["captures"][0].pop("id"),
            "missing completion time": lambda o: o["purchase_units"][0]["payments"]["captures"][0].pop("update_time"),
            "naive completion time": lambda o: o["purchase_units"][0]["payments"]["captures"][0].update(update_time="2026-10-22T10:00:01"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name):
                order = order_fixture()
                mutate(order)
                with self.assertRaises(PaymentValidationError):
                    validate_capture(order, "ORDER123", "purchase_123")

    def test_capture_rejects_fractional_currency_and_float_amounts(self):
        for value, currency in (("29.001", "USD"), ("29.00", "EUR"), (29.00, "USD"),
                                ("NaN", "USD"), ("2.9E1", "USD"), ("-29.00", "USD"), ("30.00", "USD")):
            with self.subTest(value=value, currency=currency):
                order = order_fixture()
                order["purchase_units"][0]["payments"]["captures"][0]["amount"] = {"value": value, "currency_code": currency}
                with self.assertRaises(PaymentValidationError):
                    validate_capture(order, "ORDER123", "purchase_123")

    def test_get_order_rejects_mismatched_identity(self):
        adapter, _ = self.adapter((200, {"id": "DIFFERENT", "status": "COMPLETED"}))
        with self.assertRaises(PaymentValidationError):
            adapter.get_order("ORDER123")

    def webhook_headers(self):
        return {"PAYPAL-AUTH-ALGO": "SHA256withRSA", "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/v1/notifications/certs/CERT-123",
                "PAYPAL-TRANSMISSION-ID": "transmission-123", "PAYPAL-TRANSMISSION-SIG": "synthetic-signature",
                "PAYPAL-TRANSMISSION-TIME": "2026-10-22T10:00:00Z"}

    def test_webhook_accepts_only_explicit_provider_success(self):
        for value, expected in (("SUCCESS", True), ("FAILURE", False), (None, False)):
            with self.subTest(value=value):
                adapter, transport = self.adapter((200, {"verification_status": value}))
                event = {"id": "EVENT123", "resource": {"id": "CAPTURE123"}}
                raw = json.dumps(event).encode()
                self.assertEqual(adapter.verify_webhook(self.webhook_headers(), event, raw_body=raw), expected)
                sent = json.loads(transport.calls[1][0].data)
                self.assertEqual(sent["webhook_event"], event)
                self.assertIn(b'"webhook_event":' + raw, transport.calls[1][0].data)
                self.assertEqual(sent["webhook_id"], "synthetic-webhook")
                self.assertEqual(sent["transmission_sig"], "synthetic-signature")

    def test_webhook_missing_headers_or_untrusted_cert_never_calls(self):
        for headers in ({}, {**self.webhook_headers(), "PAYPAL-CERT-URL": "http://127.0.0.1/private"}):
            adapter, transport = self.adapter()
            self.assertFalse(adapter.verify_webhook(headers, {"id": "EVENT123"}, raw_body=b'{"id":"EVENT123"}'))
            self.assertEqual(transport.calls, [])

    def test_webhook_postback_preserves_signed_whitespace_order_unicode_and_number_forms(self):
        raw = (' \n{ "resource" : {"z":1e1,"label":"café","a":0.50}, '
               '"id":"EVENT123", "event_type":"PAYMENT.CAPTURE.COMPLETED" }\n').encode("utf-8")
        event = json.loads(raw)
        adapter, transport = self.adapter((200, {"verification_status": "SUCCESS"}))
        self.assertTrue(adapter.verify_webhook(self.webhook_headers(), event, raw_body=raw))
        request = transport.calls[1][0]
        self.assertIn(b'"webhook_event":' + raw, request.data)
        self.assertEqual(json.loads(request.data)["webhook_event"], event)
        self.assertEqual(request.full_url, "https://api-m.sandbox.paypal.com/v1/notifications/verify-webhook-signature")
        self.assertEqual(len(transport.calls), 2, "One OAuth and one signature postback; no payment operation")

    def test_webhook_missing_malformed_or_mismatched_raw_never_calls(self):
        event = {"id": "EVENT123"}
        invalid = [None, "not bytes", b"", b"[]", b"{", b'\xff{"id":"EVENT123"}',
                   b'{"id":"EVENT123","id":"OTHER"}',
                   b'{"id":"EVENT123","nested":{"a":1,"a":2}}',
                   b'{"id":"EVENT123","n":NaN}', b'{"id":"EVENT123","n":Infinity}',
                   b'{"id":"EVENT123","n":1e999}',
                   b'{"id":"OTHER"}', b'{"id":"EVENT123"},"extra":true',
                   b'{"id":"EVENT123"}' + b" " * 131072]
        for raw in invalid:
            with self.subTest(raw_type=type(raw).__name__, length=len(raw) if raw is not None else None):
                adapter, transport = self.adapter()
                self.assertFalse(adapter.verify_webhook(self.webhook_headers(), event, raw_body=raw))
                self.assertEqual(transport.calls, [], "Malformed input must be rejected before OAuth")
        adapter, transport = self.adapter()
        self.assertFalse(adapter.verify_webhook(self.webhook_headers(), {"id": "EVENT123", "n": 1},
            raw_body=b'{"id":"EVENT123","n":true}'))
        self.assertEqual(transport.calls, [])

    def test_webhook_missing_configuration_is_explicit(self):
        adapter, transport = self.adapter()
        del adapter._env["PAYPAL_WEBHOOK_ID"]
        with self.assertRaises(PayPalError) as failure:
            adapter.verify_webhook(self.webhook_headers(), {"id": "EVENT123"})
        self.assertIn("PAYPAL_WEBHOOK_ID", str(failure.exception))
        self.assertEqual(transport.calls, [])

    def test_allowlist_removes_nested_personal_and_authentication_fields(self):
        order = order_fixture()
        order["purchase_units"][0]["shipping"] = {"address": "private-address"}
        order["purchase_units"][0]["payments"]["captures"][0]["seller_receivable_breakdown"] = {"paypal_fee": "private-field"}
        order["links"] = [{"rel": "self", "href": "https://api-m.sandbox.paypal.com/v2/checkout/orders/ORDER123?access_token=private-token"}]
        clean = sanitize_snapshot(order)
        self.assertNotIn("private", json.dumps(clean))
        self.assertEqual(clean["links"], [])


if __name__ == "__main__":
    unittest.main()
