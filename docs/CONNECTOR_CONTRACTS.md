# Commerce webhook contracts

These connectors turn signed order notifications into minimal order observations. They make no network calls and do not retain customer names, addresses, email, IP addresses or line-item data. The original raw request must reach the verifier without JSON reserialization.

Both connectors are implemented and exercised with locally signed fixtures. **Neither has been verified against a real Shopify or WooCommerce store.** No merchant store is available yet. These tests do not establish store connection, automatic registration, payment matching, subscription health or actual provider delivery.

## Python interface

```python
parse_shopify(raw: bytes, headers, secret: str, expected_domain: str) -> OrderUpdate
parse_woocommerce(raw: bytes, headers, secret: str, expected_origin: str) -> OrderUpdate
```

`ConnectorError` is a `ValueError` with a stable reason code. Missing signatures, mismatches, malformed payloads, duplicate JSON keys, conflicting case-variant headers and unsupported topics fail closed. Body size is bounded to 1 MiB. Secrets and supplied signatures are never included in exception messages.

`OrderUpdate` contains `platform`, `event_id`, `topic`, `platform_order_id`, `display_number`, `currency`, `total_minor`, `payment_references`, `fulfillment_status`, `fulfilled_at` and `updated_at`. It can be converted with `dataclasses.asdict`. `event_id` is the delivery ID, suitable for a **store-scoped** receipt key. The caller must implement persistence, idempotency and per-order event ordering; parsing the same delivery twice is not proof of durable deduplication.

## Shopify

Supports `orders/create`, `orders/updated`, `orders/paid`, `orders/fulfilled` and `orders/partially_fulfilled`. The verifier checks the Base64 HMAC-SHA256 digest of raw bytes and matches `X-Shopify-Shop-Domain` against the registered `*.myshopify.com` host. Headers are case-insensitive, and a delivery ID is required. This follows Shopify's [delivery verification](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries) and [webhook header/topic contract](https://shopify.dev/docs/api/webhooks/latest?reference=toml).

`financial_status=paid` is **not** PayPal capture confirmation. Standard order payloads do not provide a reliable PayPal capture ID, so `payment_references` is empty. Linking the PayPal capture needs a separately verified transaction lookup or explicit merchant-provided mapping; no ID is invented from an order number.

A partial fulfillment remains partial. A fully fulfilled order uses the latest successful fulfillment's `created_at` when supplied. Missing timestamps remain unknown; `updated_at` is never substituted as completion time. This is fulfillment creation, **not proof of physical delivery**. The caller must check that this event matches the merchant's configured promise.

## WooCommerce

Supports current v3-shaped order payloads on `order.created` and `order.updated`. Uses `X-WC-Webhook-Signature`, `X-WC-Webhook-Delivery-ID` and the registered HTTPS source base URL. The configured URL must preserve any WordPress subdirectory. Trailing `/` and default port 443 are normalized; other ports and paths must match exactly. See WooCommerce's [webhook signature/header contract](https://developer.woocommerce.com/docs/apis/rest-api/v2/webhooks) and [order properties](https://developer.woocommerce.com/docs/apis/rest-api/v3/orders/).

`transaction_id`, when present, is a join candidate only; it does not prove which gateway processed it or that PayPal captured funds. `processing` never confirms payment. `completed` means the merchant marked the order complete. Its explicit `date_completed_gmt` is retained, but this does **not** establish physical delivery. A missing completion time stays unknown. Unsupported event topics, legacy wrapper payloads and unsigned setup pings are rejected rather than treated as order events.

## Time, amounts and unknown facts

Aware ISO timestamps normalize to UTC. WooCommerce's documented `_gmt` fields may omit the timezone; only those fields are interpreted as UTC. A non-UTC offset in a GMT field, date-only value, precision beyond six fractional digits, missing required update time or completion after the order update is rejected. The caller receives older event times unchanged and must prevent old deliveries from regressing current state.

Money uses `Decimal`, never a binary float. The current explicit currency list is in `_CURRENCY_DIGITS`; unsupported currencies and excess decimal precision are rejected. `total_minor` uses that currency's minor unit, so it is not always cents.

The monitor must independently verify a PayPal completion, match currency/amount and a store-scoped payment reference, and apply the configured fulfillment promise. A commerce observation alone cannot start a PayPal-confirmed timer or resolve a payment alert. Merchant cancellation/refund status is not provider refund proof.

## Reproduce local verification

```sh
python3 -m unittest tests.test_monitor_connectors -v
```

The tests cover signature tampering, missing/malformed signatures, origin mismatch, duplicate headers/JSON keys, unsupported topics, minimal retained data, delivery identity, partial completion, missing completion time, timezone/chronology, old event times and exact currency arithmetic. All payloads and signing secrets are test-only.
