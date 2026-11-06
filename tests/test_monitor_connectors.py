"""Signed local fixtures verify parser contracts; these are not store execution."""
import base64
from dataclasses import asdict
import hashlib
import hmac
import json
import unittest

from crashcart.monitor_connectors import ConnectorError, parse_shopify, parse_woocommerce

SECRET = 'local-test-signing-secret-not-a-provider-credential'


def body(data):
    return json.dumps(data, separators=(',', ':')).encode()


def signature(raw):
    return base64.b64encode(hmac.new(SECRET.encode(), raw, hashlib.sha256).digest()).decode()


class ConnectorTests(unittest.TestCase):
    def shop(self, **changes):
        data = {'id': 123, 'name': '#1001', 'currency': 'USD', 'total_price': '29.00',
                'financial_status': 'paid', 'updated_at': '2026-11-06T10:00:00Z',
                'fulfillment_status': None, 'fulfillments': [],
                'email': 'do-not-retain@example.test', 'shipping_address': {'address1': 'private'}}
        data.update(changes)
        raw = body(data)
        headers = {'X-Shopify-Hmac-Sha256': signature(raw), 'X-Shopify-Shop-Domain': 'owned.myshopify.com',
                   'X-Shopify-Topic': 'orders/updated', 'X-Shopify-Webhook-Id': 'delivery-shop-1'}
        return raw, headers

    def woo(self, **changes):
        data = {'id': 456, 'number': '1002', 'currency': 'USD', 'total': '29.00',
                'status': 'processing', 'date_modified_gmt': '2026-11-06T10:00:00',
                'date_completed_gmt': None, 'transaction_id': 'CAPTURE-REFERENCE-ONLY',
                'payment_method': 'bacs', 'billing': {'email': 'private@example.test'}}
        data.update(changes)
        raw = body(data)
        headers = {'X-WC-Webhook-Signature': signature(raw), 'X-WC-Webhook-Source': 'https://owned.example.test/shop/',
                   'X-WC-Webhook-Topic': 'order.updated', 'X-WC-Webhook-Delivery-ID': 'delivery-woo-1'}
        return raw, headers

    def parse_shop(self, changes=None, header_changes=None):
        raw, headers = self.shop(**(changes or {})); headers.update(header_changes or {})
        return parse_shopify(raw, headers, SECRET, 'owned.myshopify.com')

    def parse_woo(self, changes=None, header_changes=None):
        raw, headers = self.woo(**(changes or {})); headers.update(header_changes or {})
        return parse_woocommerce(raw, headers, SECRET, 'https://owned.example.test/shop')

    def test_shopify_signed_order_is_minimal_and_never_payment_confirmation(self):
        update = self.parse_shop()
        self.assertEqual(update.platform_order_id, '123')
        self.assertEqual(update.total_minor, 2900)
        self.assertEqual(update.payment_references, ())
        self.assertNotIn('financial_status', asdict(update))
        self.assertNotIn('email', json.dumps(asdict(update)))
        self.assertEqual(update.fulfillment_status, 'unfulfilled')
        self.assertIsNone(update.fulfilled_at)

    def test_woocommerce_transaction_is_reference_not_payment_proof(self):
        update = self.parse_woo()
        self.assertEqual(update.payment_references, ('CAPTURE-REFERENCE-ONLY',))
        self.assertEqual(update.fulfillment_status, 'unfulfilled')
        self.assertNotIn('payment_confirmed', asdict(update))
        self.assertNotIn('billing', asdict(update))
        self.assertEqual(update.updated_at, '2026-11-06T10:00:00Z')

    def test_case_insensitive_headers_and_stable_delivery_identity(self):
        raw, headers = self.shop()
        one = parse_shopify(raw, {k.lower(): v for k, v in headers.items()}, SECRET, 'OWNED.myshopify.com')
        two = parse_shopify(raw, headers, SECRET, 'owned.myshopify.com')
        self.assertEqual(one, two)
        self.assertEqual(one.event_id, 'delivery-shop-1')

    def test_invalid_missing_and_malformed_signatures_fail_closed(self):
        for get, parse, origin, key in [(self.shop, parse_shopify, 'owned.myshopify.com', 'X-Shopify-Hmac-Sha256'),
                                         (self.woo, parse_woocommerce, 'https://owned.example.test/shop', 'X-WC-Webhook-Signature')]:
            for invalid in ['', 'not-base64', '☃', base64.b64encode(b'x' * 32).decode()]:
                raw, headers = get(); headers[key] = invalid
                with self.subTest(platform=parse.__name__, signature=invalid):
                    with self.assertRaisesRegex(ConnectorError, 'INVALID_SIGNATURE'):
                        parse(raw, headers, SECRET, origin)
            raw, headers = get()
            with self.assertRaisesRegex(ConnectorError, 'INVALID_SIGNATURE'):
                parse(raw + b' ', headers, SECRET, origin)
            with self.assertRaisesRegex(ConnectorError, 'SIGNING_SECRET_REQUIRED'):
                parse(raw, headers, '', origin)

    def test_origin_is_bound_to_registered_store(self):
        with self.assertRaisesRegex(ConnectorError, 'STORE_ORIGIN_MISMATCH'):
            self.parse_shop(header_changes={'X-Shopify-Shop-Domain': 'another.myshopify.com'})
        for origin in ['https://another.example.test/shop', 'https://owned.example.test/other']:
            with self.assertRaisesRegex(ConnectorError, 'STORE_ORIGIN_MISMATCH'):
                self.parse_woo(header_changes={'X-WC-Webhook-Source': origin})
        for origin in ['http://owned.example.test/shop', 'https://user@owned.example.test/shop', 'https://owned.example.test/shop?x=1']:
            with self.assertRaisesRegex(ConnectorError, 'INVALID_STORE_ORIGIN'):
                self.parse_woo(header_changes={'X-WC-Webhook-Source': origin})

    def test_duplicate_case_headers_and_json_keys_rejected(self):
        raw, headers = self.shop(); headers['x-shopify-hmac-sha256'] = headers['X-Shopify-Hmac-Sha256']
        with self.assertRaisesRegex(ConnectorError, 'AMBIGUOUS_HEADERS'):
            parse_shopify(raw, headers, SECRET, 'owned.myshopify.com')
        raw = b'{"id":123,"id":456}'
        _, headers = self.shop(); headers['X-Shopify-Hmac-Sha256'] = signature(raw)
        with self.assertRaisesRegex(ConnectorError, 'DUPLICATE_JSON_KEY'):
            parse_shopify(raw, headers, SECRET, 'owned.myshopify.com')

    def test_unknown_topics_and_missing_event_ids_rejected(self):
        for change in [{'X-Shopify-Topic': 'products/update'}, {'X-Shopify-Webhook-Id': ''}]:
            with self.assertRaises(ConnectorError):
                self.parse_shop(header_changes=change)
        with self.assertRaisesRegex(ConnectorError, 'UNSUPPORTED_TOPIC'):
            self.parse_woo(header_changes={'X-WC-Webhook-Topic': 'customer.updated'})

    def test_partial_fulfillment_cannot_close_a_promise(self):
        update = self.parse_shop({'fulfillment_status': 'partial', 'fulfillments': [
            {'status': 'success', 'created_at': '2026-11-06T09:59:00Z'}]})
        self.assertEqual(update.fulfillment_status, 'partial')
        self.assertIsNone(update.fulfilled_at)

    def test_full_fulfillment_uses_latest_successful_creation_not_order_update(self):
        update = self.parse_shop({'fulfillment_status': 'fulfilled', 'fulfillments': [
            {'status': 'success', 'created_at': '2026-11-06T09:55:00Z'},
            {'status': 'cancelled', 'created_at': '2026-11-06T10:00:00Z'},
            {'status': 'success', 'created_at': '2026-11-06T09:59:00Z'}]})
        self.assertEqual(update.fulfilled_at, '2026-11-06T09:59:00Z')
        unknown_time = self.parse_shop({'fulfillment_status': 'fulfilled'})
        self.assertIsNone(unknown_time.fulfilled_at)

    def test_successful_fulfillment_without_creation_time_remains_unknown(self):
        for item in [{'status': 'success'}, {'status': 'success', 'created_at': None}]:
            with self.subTest(item=item):
                update = self.parse_shop({'fulfillment_status': 'fulfilled', 'fulfillments': [item]})
                self.assertEqual(update.fulfillment_status, 'fulfilled')
                self.assertIsNone(update.fulfilled_at)

    def test_mixed_known_and_missing_fulfillment_times_do_not_invent_completion(self):
        known = {'status': 'success', 'created_at': '2026-11-06T09:59:00Z'}
        missing = {'status': 'success'}
        for items in [[known, missing], [missing, known]]:
            with self.subTest(items=items):
                update = self.parse_shop({'fulfillment_status': 'fulfilled', 'fulfillments': items})
                self.assertEqual(update.fulfillment_status, 'fulfilled')
                self.assertIsNone(update.fulfilled_at)

    def test_woo_completed_retains_explicit_merchant_completion_time(self):
        update = self.parse_woo({'status': 'completed', 'date_completed_gmt': '2026-11-06T09:59:59'})
        self.assertEqual(update.fulfillment_status, 'fulfilled')
        self.assertEqual(update.fulfilled_at, '2026-11-06T09:59:59Z')
        self.assertIsNone(self.parse_woo({'status': 'completed'}).fulfilled_at)

    def test_timestamp_timezone_and_chronology_are_not_guessed(self):
        for timestamp in ['2026-11-06T10:00:00', '2026-11-06', '2026-99-99T10:00:00Z']:
            with self.assertRaisesRegex(ConnectorError, 'INVALID_UPDATED_AT'):
                self.parse_shop({'updated_at': timestamp})
        with self.assertRaisesRegex(ConnectorError, 'FULFILLMENT_AFTER_ORDER_UPDATE'):
            self.parse_woo({'status': 'completed', 'date_completed_gmt': '2026-11-06T10:00:00.1'})
        with self.assertRaisesRegex(ConnectorError, 'INVALID_UPDATED_AT'):
            self.parse_woo({'date_modified_gmt': '2026-11-06T15:30:00+05:30'})
        normalized = self.parse_shop({'updated_at': '2026-11-06T15:30:00+05:30'})
        self.assertEqual(normalized.updated_at, '2026-11-06T10:00:00Z')

    def test_out_of_order_facts_keep_their_own_event_time(self):
        newer = self.parse_shop({'updated_at': '2026-11-06T10:00:00Z'})
        older = self.parse_shop({'updated_at': '2026-11-06T09:00:00Z'})
        self.assertLess(older.updated_at, newer.updated_at)

    def test_money_is_exact_and_currency_precision_explicit(self):
        self.assertEqual(self.parse_shop({'total_price': '0.29'}).total_minor, 29)
        self.assertEqual(self.parse_shop({'total_price': '123', 'currency': 'JPY'}).total_minor, 123)
        self.assertEqual(self.parse_shop({'total_price': '1.234', 'currency': 'KWD'}).total_minor, 1234)
        for total in ['1.234', '-1.00', 'NaN', '1e4', 29.0]:
            with self.assertRaises(ConnectorError):
                self.parse_shop({'total_price': total})
        with self.assertRaisesRegex(ConnectorError, 'UNSUPPORTED_CURRENCY'):
            self.parse_shop({'currency': 'XYZ'})
        with self.assertRaises(ConnectorError):
            self.parse_shop({'total_price': '1.5', 'currency': 'JPY'})

    def test_signed_invalid_json_and_scalars_are_rejected(self):
        for raw in [b'{', b'[]', b'null', b'{"n":NaN}', b'\xff']:
            _, headers = self.shop(); headers['X-Shopify-Hmac-Sha256'] = signature(raw)
            with self.assertRaises(ConnectorError):
                parse_shopify(raw, headers, SECRET, 'owned.myshopify.com')
        raw, headers = self.shop()
        with self.assertRaisesRegex(ConnectorError, 'INVALID_BODY_SIZE'):
            parse_shopify(b' ' * 1_048_577, headers, SECRET, 'owned.myshopify.com')


if __name__ == '__main__':
    unittest.main()
