"""One-attempt PayPal Sandbox transport; never substitutes simulated payment data.

APIMatic context informed the explicit PAYPAL_* credential mapping, fixed sandbox
environment and one-attempt policy (evidence/runs/apimatic/). The application owns
durable operation/request IDs and reconciliation; this adapter never retries.
"""
from base64 import b64encode
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import os
import re
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


SANDBOX_BASE = "https://api-m.sandbox.paypal.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_WEBHOOK_BYTES = 131072
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class PayPalError(Exception):
    def __init__(self, code, message, *, status=None, ambiguous=False):
        super().__init__(message)
        self.code, self.status, self.http_status = code, status, status
        self.ambiguous = ambiguous

    def as_dict(self):
        return {"code": self.code, "message": str(self), "http_status": self.status,
                "ambiguous": self.ambiguous}


class PaymentValidationError(PayPalError, ValueError):
    def __init__(self, message):
        super().__init__("INVALID_PAYMENT_EVIDENCE", message)


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http_transport(request, timeout):
    # Bearer/basic credentials must never follow a provider-supplied redirect.
    try:
        with build_opener(_NoRedirects()).open(request, timeout=timeout) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        try:
            return exc.code, exc.read(MAX_RESPONSE_BYTES + 1)
        finally:
            exc.close()


def _identifier(value, label):
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise PaymentValidationError(f"A valid {label} is required")
    return value


def _money(amount):
    if not isinstance(amount, dict) or amount.get("currency_code") != "USD":
        raise PaymentValidationError("Payment currency must be USD")
    value = amount.get("value")
    # Parse decimal strings, never floats; reject exponent notation and fractional cents.
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{2}", value):
        raise PaymentValidationError("Payment value must be an exact decimal string with two fractional digits")
    try:
        minor = Decimal(value) * 100
    except InvalidOperation:
        raise PaymentValidationError("Payment amount is invalid") from None
    if minor != 2900:
        raise PaymentValidationError("Payment amount must be exactly 2900 minor units")
    return int(minor)


def _observed_money(amount):
    """Normalize observed money without treating a wrong charge as unknown.

    Precision follows https://developer.paypal.com/api/codes/currency/.
    Unknown currencies remain invalid rather than guessing their minor units.
    This parser is for evidence, never permission to create or fulfill a charge.
    """
    supported = {"AUD", "BRL", "CAD", "CNY", "CZK", "DKK", "EUR", "HKD", "HUF", "ILS", "JPY", "MYR",
                 "MXN", "TWD", "NZD", "NOK", "PHP", "PLN", "GBP", "RUB", "SGD", "SEK", "CHF", "THB", "USD"}
    if not isinstance(amount, dict) or not isinstance(amount.get("currency_code"), str) or amount["currency_code"] not in supported:
        raise PaymentValidationError("Observed payment requires a supported explicit currency")
    currency, value = amount["currency_code"], amount.get("value")
    pattern = r"(?:0|[1-9][0-9]*)" if currency in {"HUF", "JPY", "TWD"} else r"(?:0|[1-9][0-9]*)\.[0-9]{2}"
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(pattern, value):
        raise PaymentValidationError("Observed payment value must have exact currency precision")
    return int(value.replace(".", "")), currency


def _timestamp(value):
    if not isinstance(value, str):
        raise PaymentValidationError("Completed capture requires an update timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PaymentValidationError("Capture update timestamp must be ISO 8601") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise PaymentValidationError("Capture update timestamp must include a timezone")
    return value


def _safe_link(link):
    if not isinstance(link, dict) or not isinstance(link.get("href"), str):
        return None
    try:
        url = urlsplit(link["href"])
        if url.scheme != "https" or url.username or url.password or url.fragment or url.port not in (None, 443):
            return None
        rel = link.get("rel")
        if rel in {"approve", "payer-action"}:
            query = parse_qs(url.query, keep_blank_values=True)
            if (url.hostname not in {"www.sandbox.paypal.com", "sandbox.paypal.com"}
                    or url.path != "/checkoutnow" or set(query) != {"token"}
                    or len(query["token"]) != 1 or not IDENTIFIER.fullmatch(query["token"][0])):
                return None
        elif rel in {"self", "capture", "up"}:
            if url.hostname != "api-m.sandbox.paypal.com" or url.query or not re.fullmatch(r"/v2/(?:checkout/orders|payments/captures)/[A-Za-z0-9_-]+(?:/capture)?", url.path):
                return None
        else:
            return None
        return {"href": link["href"], "rel": rel,
                "method": link.get("method") if link.get("method") in {"GET", "POST"} else "GET"}
    except ValueError:
        return None


def sanitize_snapshot(value):
    """Keep payment identities/state only; drop payer, shipping, auth and unknowns."""
    if not isinstance(value, dict):
        return {}
    clean = {}
    for key in ("id", "status", "intent", "reference_id", "custom_id", "create_time", "update_time", "verification_status"):
        if isinstance(value.get(key), str) and len(value[key]) <= 160:
            clean[key] = value[key]
    if isinstance(value.get("amount"), dict):
        clean["amount"] = {key: value["amount"][key] for key in ("currency_code", "value")
                           if isinstance(value["amount"].get(key), str) and len(value["amount"][key]) <= 64}
    if isinstance(value.get("purchase_units"), list):
        clean["purchase_units"] = [sanitize_snapshot(unit) for unit in value["purchase_units"]]
    if isinstance(value.get("payments"), dict) and isinstance(value["payments"].get("captures"), list):
        clean["payments"] = {"captures": [sanitize_snapshot(capture) for capture in value["payments"]["captures"]]}
    if isinstance(value.get("links"), list):
        clean["links"] = [safe for link in value["links"] if (safe := _safe_link(link))]
    return clean


def approval_url(order):
    if not isinstance(order, dict):
        raise PaymentValidationError("Order approval evidence must be an object")
    order_id = _identifier(order.get("id"), "order ID")
    links = order.get("links")
    if not isinstance(links, list):
        raise PaymentValidationError("No sandbox buyer approval link was returned")
    for rel in ("payer-action", "approve"):
        for link in links:
            safe = _safe_link(link)
            if safe and safe["rel"] == rel and parse_qs(urlsplit(safe["href"]).query)["token"] == [order_id]:
                return safe["href"]
    raise PaymentValidationError("No correlated sandbox buyer approval link was returned")


def inspect_capture(order, expected_order_id, purchase_id):
    """Read trustworthy correlated capture evidence, including wrong charges.

    This establishes capture identity and observed money, not fulfillment
    eligibility. Call validate_capture before confirming or delivering a ticket.
    """
    _identifier(expected_order_id, "expected order ID")
    _identifier(purchase_id, "purchase ID")
    if not isinstance(order, dict) or order.get("id") != expected_order_id:
        raise PaymentValidationError("Retrieved order ID does not match the persisted order")
    if order.get("status") != "COMPLETED" or order.get("intent") != "CAPTURE":
        raise PaymentValidationError("Retrieved order is not a completed capture order")
    units = order.get("purchase_units")
    if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
        raise PaymentValidationError("Exactly one purchase unit is required")
    unit = units[0]
    if unit.get("reference_id") != purchase_id or unit.get("custom_id") != purchase_id:
        raise PaymentValidationError("Purchase unit identities do not match the logical purchase")
    order_amount, order_currency = _observed_money(unit.get("amount"))
    payments = unit.get("payments")
    captures = payments.get("captures") if isinstance(payments, dict) else None
    if not isinstance(captures, list) or len(captures) != 1 or not isinstance(captures[0], dict):
        raise PaymentValidationError("Exactly one independently observed capture is required")
    capture = captures[0]
    if capture.get("status") != "COMPLETED":
        raise PaymentValidationError("Capture status is not COMPLETED")
    amount, currency = _observed_money(capture.get("amount"))
    capture_id = _identifier(capture.get("id"), "capture ID")
    completed_at = _timestamp(capture.get("update_time"))
    return {"order_id": expected_order_id, "purchase_id": purchase_id, "capture_id": capture_id,
            "amount": amount, "currency": currency, "completed_at": completed_at,
            "order_amount": order_amount, "order_currency": order_currency,
            "provider_response": sanitize_snapshot(order)}


def validate_capture(order, expected_order_id, purchase_id):
    """Require the exact agreed charge before calling Store.confirm_payment."""
    payment = inspect_capture(order, expected_order_id, purchase_id)
    _money(order["purchase_units"][0]["amount"])
    _money(order["purchase_units"][0]["payments"]["captures"][0]["amount"])
    return payment


def parse_webhook_event(raw_body):
    """Validate a received JSON object without reconstructing its signed bytes."""
    if not isinstance(raw_body, bytes) or not 0 < len(raw_body) <= MAX_WEBHOOK_BYTES:
        raise ValueError("Bounded raw webhook bytes required")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate webhook JSON key")
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError("Nonfinite webhook JSON number")
    try:
        event = json.loads(raw_body.decode("utf-8"), object_pairs_hook=unique,
                           parse_constant=invalid_constant)
        if not isinstance(event, dict):
            raise ValueError("Webhook JSON object required")
        # Validation only: reject exponent overflow as well as NaN/Infinity.
        # These reconstructed bytes are never used for signature verification.
        json.dumps(event, allow_nan=False)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        raise ValueError("Invalid webhook JSON") from None
    return event


class PayPalSandbox:
    """Constructing an adapter is inert; explicit enables gate every service call."""
    def __init__(self, *, environ=None, transport=None, timeout=15):
        self._env = os.environ if environ is None else environ
        self._transport = _http_transport if transport is None else transport
        if not isinstance(timeout, (int, float)) or not 0 < timeout <= 60:
            raise ValueError("PayPal timeout must be between zero and 60 seconds")
        self.timeout = timeout
        self._token, self._token_expires = None, 0
        self._token_lock = threading.Lock()

    def _configuration(self, *, webhook=False):
        if self._env.get("CRASHCART_ALLOW_SANDBOX") != "1":
            raise PayPalError("SANDBOX_DISABLED", "CRASHCART_ALLOW_SANDBOX=1 is required")
        required = ["PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"] + (["PAYPAL_WEBHOOK_ID"] if webhook else [])
        missing = [name for name in required if not isinstance(self._env.get(name), str) or not self._env[name].strip()]
        if missing:
            raise PayPalError("MISSING_CONFIGURATION", "Missing configuration: " + ", ".join(missing))

    def _request(self, method, path, *, headers=None, data=None, payment_action=False):
        request = Request(SANDBOX_BASE + path, data=data, method=method,
                          headers={"Accept": "application/json", **(headers or {})})
        try:
            status, raw = self._transport(request, self.timeout)
        except (TimeoutError, socket.timeout):
            raise PayPalError("TIMEOUT", "PayPal Sandbox request timed out; reconcile before retrying", ambiguous=payment_action) from None
        except (URLError, OSError):
            raise PayPalError("TRANSPORT_ERROR", "PayPal Sandbox transport failed; no automatic retry was attempted", ambiguous=payment_action) from None
        if status < 200 or status >= 300:
            raise PayPalError("PROVIDER_HTTP_ERROR", "PayPal Sandbox rejected the request", status=status,
                              ambiguous=payment_action and (status >= 500 or status in {408, 429}))
        if not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
            raise PayPalError("MALFORMED_RESPONSE", "PayPal Sandbox response is invalid or too large", status=status, ambiguous=payment_action)
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise PayPalError("MALFORMED_RESPONSE", "PayPal Sandbox response is not JSON", status=status, ambiguous=payment_action) from None
        if not isinstance(value, dict):
            raise PayPalError("MALFORMED_RESPONSE", "PayPal Sandbox response must be an object", status=status, ambiguous=payment_action)
        return value

    def _bearer(self):
        self._configuration()
        with self._token_lock:
            if self._token and time.monotonic() < self._token_expires:
                return self._token
            basic = b64encode(f"{self._env['PAYPAL_CLIENT_ID']}:{self._env['PAYPAL_CLIENT_SECRET']}".encode()).decode()
            value = self._request("POST", "/v1/oauth2/token", headers={"Authorization": "Basic " + basic,
                                  "Content-Type": "application/x-www-form-urlencoded"}, data=b"grant_type=client_credentials")
            token, expires = value.get("access_token"), value.get("expires_in")
            if (not isinstance(token, str) or not token or "\r" in token or "\n" in token
                    or str(value.get("token_type", "")).lower() != "bearer"
                    or type(expires) not in (int, float) or not 0 < expires <= 86400):
                raise PayPalError("MALFORMED_TOKEN", "PayPal Sandbox returned an invalid OAuth token response")
            self._token, self._token_expires = token, time.monotonic() + max(0, expires - 30)
            return token

    def _call(self, method, path, *, body=None, request_id=None):
        self._configuration()
        headers = {"Authorization": "Bearer " + self._bearer(), "Content-Type": "application/json",
                   "Prefer": "return=representation"}
        if request_id is not None:
            headers["PayPal-Request-Id"] = _identifier(request_id, "persisted request ID")
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() if body is not None else None
        result = self._request(method, path, headers=headers, data=raw,
                               payment_action=method == "POST" and path.startswith("/v2/checkout/orders"))
        return sanitize_snapshot(result)

    def create_order(self, body, request_id):
        if not isinstance(body, dict) or body.get("intent") != "CAPTURE":
            raise PaymentValidationError("Create order requires an explicit CAPTURE body")
        units = body.get("purchase_units")
        if not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict):
            raise PaymentValidationError("Create order requires one purchase unit")
        _money(units[0].get("amount"))
        reference = _identifier(units[0].get("reference_id"), "purchase reference")
        if units[0].get("custom_id") != reference:
            raise PaymentValidationError("Create order requires matching purchase identities")
        _identifier(request_id, "persisted request ID")
        order = self._call("POST", "/v2/checkout/orders", body=body, request_id=request_id)
        try:
            _identifier(order.get("id"), "created order ID")
            if order.get("status") not in {"CREATED", "PAYER_ACTION_REQUIRED", "APPROVED", "COMPLETED"}:
                raise PaymentValidationError("Unexpected created order state")
            if order["status"] in {"CREATED", "PAYER_ACTION_REQUIRED"}:
                approval_url(order)
        except PaymentValidationError:
            raise PayPalError("MALFORMED_ORDER", "Order response lacks a correlated sandbox approval link", ambiguous=True) from None
        return order

    def capture_order(self, order_id, body, request_id):
        _identifier(order_id, "order ID")
        _identifier(request_id, "persisted request ID")
        if not isinstance(body, dict):
            raise PaymentValidationError("Capture request body must be an object")
        return self._call("POST", f"/v2/checkout/orders/{order_id}/capture", body=body, request_id=request_id)

    def get_order(self, order_id):
        _identifier(order_id, "order ID")
        order = self._call("GET", f"/v2/checkout/orders/{order_id}")
        if order.get("id") != order_id:
            raise PaymentValidationError("Independent provider read returned a different order")
        return order

    def verify_webhook(self, headers, event, *, raw_body=None):
        self._configuration(webhook=True)
        if not isinstance(event, dict) or not isinstance(event.get("id"), str):
            return False
        try:
            original = parse_webhook_event(raw_body)
            # Ensure the parsed processing input represents the signed body.
            # This comparison must not become the body sent back to PayPal.
            if json.dumps(original, sort_keys=True, allow_nan=False) != json.dumps(event, sort_keys=True, allow_nan=False):
                return False
            incoming = {key.lower(): value for key, value in headers.items()}
            mapping = {"auth_algo": "paypal-auth-algo", "cert_url": "paypal-cert-url",
                       "transmission_id": "paypal-transmission-id", "transmission_sig": "paypal-transmission-sig",
                       "transmission_time": "paypal-transmission-time"}
            body = {key: incoming[header] for key, header in mapping.items()}
            if any(not isinstance(value, str) or not value or len(value) > 8192 for value in body.values()):
                return False
            cert = urlsplit(body["cert_url"])
            if (cert.scheme != "https" or cert.hostname not in {"api.paypal.com", "api.sandbox.paypal.com", "api-m.sandbox.paypal.com"}
                    or cert.username or cert.password or cert.port not in (None, 443)
                    or not cert.path.startswith("/v1/notifications/certs/") or cert.query or cert.fragment):
                return False
            if body["auth_algo"] != "SHA256withRSA":
                return False
            _timestamp(body["transmission_time"])
        except (KeyError, AttributeError, ValueError, TypeError, RecursionError):
            return False
        body["webhook_id"] = self._env["PAYPAL_WEBHOOK_ID"]
        envelope = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        # PayPal signs the original event payload. Keep its whitespace, key
        # order, Unicode and numeric spellings intact inside the postback.
        payload = envelope[:-1] + b',"webhook_event":' + raw_body + b"}"
        result = self._request("POST", "/v1/notifications/verify-webhook-signature",
            headers={"Authorization": "Bearer " + self._bearer(), "Content-Type": "application/json",
                     "Prefer": "return=representation"}, data=payload)
        return result.get("verification_status") == "SUCCESS"
