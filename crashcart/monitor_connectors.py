"""Signed commerce order observations, not payment confirmation.

No network calls or customer addresses are retained here. See
``docs/CONNECTOR_CONTRACTS.md`` for supported payloads and proof boundaries.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import re
from typing import Mapping
from urllib.parse import urlsplit


class ConnectorError(ValueError):
    """An unauthenticated, unsupported, or unusable order observation."""


@dataclass(frozen=True)
class OrderUpdate:
    platform: str
    event_id: str
    topic: str
    platform_order_id: str
    display_number: str
    currency: str
    total_minor: int
    payment_references: tuple[str, ...]
    fulfillment_status: str
    fulfilled_at: str | None
    updated_at: str


# Explicit currency support avoids assuming every currency has two decimals.
_CURRENCY_DIGITS = {code: 2 for code in (
    'USD EUR GBP CAD AUD NZD CHF INR SGD HKD CNY BRL MXN PLN SEK NOK DKK ZAR '
    'THB PHP MYR ILS CZK HUF TWD'
).split()}
_CURRENCY_DIGITS.update(JPY=0, KRW=0, BHD=3, KWD=3, OMR=3)


def _text(value, field: str, maximum=160) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or any(ord(c) < 32 for c in value):
        raise ConnectorError('INVALID_' + field.upper())
    return value


def _identifier(value, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ConnectorError('INVALID_' + field.upper())
    result = str(value)
    if not re.fullmatch(r'[1-9][0-9]{0,39}', result):
        raise ConnectorError('INVALID_' + field.upper())
    return result


def _headers(headers: Mapping[str, str]) -> dict[str, str]:
    result = {}
    for key, value in headers.items():
        key = str(key).lower()
        if key in result or not isinstance(value, str):
            raise ConnectorError('AMBIGUOUS_HEADERS')
        result[key] = value
    return result


def _verified_body(raw: bytes, headers: dict[str, str], signature_header: str, secret: str) -> dict:
    if not isinstance(raw, bytes) or len(raw) > 1_048_576:
        raise ConnectorError('INVALID_BODY_SIZE')
    if not isinstance(secret, str) or not secret or len(secret) > 4096:
        raise ConnectorError('SIGNING_SECRET_REQUIRED')
    provided = headers.get(signature_header, '')
    try:
        signature = base64.b64decode(provided, validate=True)
    except (ValueError, binascii.Error):
        raise ConnectorError('INVALID_SIGNATURE') from None
    expected = hmac.new(secret.encode('utf-8'), raw, hashlib.sha256).digest()
    if len(signature) != len(expected) or not hmac.compare_digest(signature, expected):
        raise ConnectorError('INVALID_SIGNATURE')

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ConnectorError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result

    try:
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ConnectorError('INVALID_JSON_NUMBER')))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ConnectorError('INVALID_JSON') from None
    if not isinstance(data, dict):
        raise ConnectorError('INVALID_ORDER_PAYLOAD')
    return data


def _timestamp(value, field: str, *, gmt=False) -> str:
    value = _text(value, field, 64)
    pattern = r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?'
    if not re.fullmatch(pattern + (r'(?:Z|[+-]\d{2}:\d{2})?' if gmt else r'(?:Z|[+-]\d{2}:\d{2})'), value):
        raise ConnectorError('INVALID_' + field.upper())
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            if not gmt:
                raise ValueError('timezone required')
            dt = dt.replace(tzinfo=timezone.utc)
        offset = dt.utcoffset()
        if gmt and (offset is None or offset.total_seconds() != 0):
            raise ValueError('GMT field has non-UTC offset')
        return dt.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    except (ValueError, OverflowError):
        raise ConnectorError('INVALID_' + field.upper()) from None


def _money(value, currency) -> tuple[str, int]:
    currency = _text(currency, 'currency', 3)
    if currency not in _CURRENCY_DIGITS:
        raise ConnectorError('UNSUPPORTED_CURRENCY')
    if not isinstance(value, str) or len(value) > 30 or not re.fullmatch(r'\d+(?:\.\d+)?', value):
        raise ConnectorError('INVALID_TOTAL')
    try:
        amount = Decimal(value)
        minor = amount * (10 ** _CURRENCY_DIGITS[currency])
        if minor != minor.to_integral_value() or minor > 10**15:
            raise ConnectorError('INVALID_TOTAL_PRECISION_OR_SIZE')
        return currency, int(minor)
    except InvalidOperation:
        raise ConnectorError('INVALID_TOTAL') from None


def _shop_domain(value) -> str:
    value = _text(value, 'shop_domain', 253).lower()
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*\.myshopify\.com', value):
        raise ConnectorError('INVALID_SHOP_DOMAIN')
    return value


def _origin(value) -> str:
    value = _text(value, 'store_origin', 2048)
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise ValueError('HTTPS store base URL required')
        hostname = parsed.hostname.lower()
        hostname = '[' + hostname + ']' if ':' in hostname else hostname
        port = '' if parsed.port in (None, 443) else ':' + str(parsed.port)
        return 'https://' + hostname + port + parsed.path.rstrip('/')
    except ValueError:
        raise ConnectorError('INVALID_STORE_ORIGIN') from None


def parse_shopify(raw: bytes, headers: Mapping[str, str], secret: str, expected_domain: str) -> OrderUpdate:
    """Read order webhooks after HMAC/origin verification; never confirm payment."""
    hdr = _headers(headers)
    data = _verified_body(raw, hdr, 'x-shopify-hmac-sha256', secret)
    if _shop_domain(hdr.get('x-shopify-shop-domain')) != _shop_domain(expected_domain):
        raise ConnectorError('STORE_ORIGIN_MISMATCH')
    topic = hdr.get('x-shopify-topic')
    if topic not in {'orders/create', 'orders/updated', 'orders/paid', 'orders/fulfilled', 'orders/partially_fulfilled'}:
        raise ConnectorError('UNSUPPORTED_TOPIC')
    event_id = _text(hdr.get('x-shopify-webhook-id'), 'event_id')
    order_id = _identifier(data.get('id'), 'order_id')
    currency, amount = _money(data.get('total_price'), data.get('currency'))
    updated = _timestamp(data.get('updated_at'), 'updated_at')
    state = data.get('fulfillment_status')
    if state not in (None, 'fulfilled', 'partial', 'unfulfilled'):
        raise ConnectorError('UNSUPPORTED_FULFILLMENT_STATUS')
    status = state or 'unfulfilled'
    completed = None
    if status == 'fulfilled':
        fulfillments = data.get('fulfillments', [])
        if not isinstance(fulfillments, list):
            raise ConnectorError('INVALID_FULFILLMENTS')
        times = []
        unknown_time = False
        for item in fulfillments:
            if not isinstance(item, dict):
                raise ConnectorError('INVALID_FULFILLMENT')
            if item.get('status') == 'success':
                if item.get('created_at') is None:
                    unknown_time = True
                else:
                    times.append(_timestamp(item['created_at'], 'fulfilled_at'))
        if times:
            latest = max(times, key=lambda v: datetime.fromisoformat(v.replace('Z', '+00:00')))
            if datetime.fromisoformat(latest.replace('Z', '+00:00')) > datetime.fromisoformat(updated.replace('Z', '+00:00')):
                raise ConnectorError('FULFILLMENT_AFTER_ORDER_UPDATE')
            if not unknown_time:
                completed = latest
    # Standard order webhook payloads do not carry transaction/capture IDs.
    # financial_status='paid' is deliberately not converted to PayPal proof.
    return OrderUpdate('shopify', event_id, topic, order_id,
                       _text(data.get('name', order_id), 'display_number'), currency, amount,
                       (), status, completed, updated)


def parse_woocommerce(raw: bytes, headers: Mapping[str, str], secret: str, expected_origin: str) -> OrderUpdate:
    """Read v3-shaped order payloads; completed means merchant completion only."""
    hdr = _headers(headers)
    data = _verified_body(raw, hdr, 'x-wc-webhook-signature', secret)
    if _origin(hdr.get('x-wc-webhook-source')) != _origin(expected_origin):
        raise ConnectorError('STORE_ORIGIN_MISMATCH')
    topic = hdr.get('x-wc-webhook-topic')
    if topic not in {'order.created', 'order.updated'}:
        raise ConnectorError('UNSUPPORTED_TOPIC')
    event_id = _text(hdr.get('x-wc-webhook-delivery-id'), 'event_id')
    order_id = _identifier(data.get('id'), 'order_id')
    currency, amount = _money(data.get('total'), data.get('currency'))
    updated = _timestamp(data.get('date_modified_gmt'), 'updated_at', gmt=True)
    state = data.get('status')
    if state not in {'pending', 'processing', 'on-hold', 'completed', 'cancelled', 'refunded', 'failed', 'trash'}:
        raise ConnectorError('UNSUPPORTED_ORDER_STATUS')
    completed = None
    if state == 'completed' and data.get('date_completed_gmt') is not None:
        completed = _timestamp(data['date_completed_gmt'], 'fulfilled_at', gmt=True)
        if datetime.fromisoformat(completed.replace('Z', '+00:00')) > datetime.fromisoformat(updated.replace('Z', '+00:00')):
            raise ConnectorError('FULFILLMENT_AFTER_ORDER_UPDATE')
    transaction = data.get('transaction_id', '')
    if transaction is None:
        transaction = ''
    if transaction:
        transaction = _text(transaction, 'transaction_id', 256)
    # A transaction reference is only a join candidate. It proves neither the
    # gateway used nor the completion of a PayPal capture.
    references = (transaction,) if transaction else ()
    return OrderUpdate('woocommerce', event_id, topic, order_id,
                       _text(data.get('number', order_id), 'display_number'), currency, amount,
                       references, 'fulfilled' if state == 'completed' else 'unfulfilled', completed, updated)
