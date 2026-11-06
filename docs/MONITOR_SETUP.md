# Connect an owned test store

CrashCart's monitoring console is a separate entry point from the recorded investigation. It stores orders and alerts by store and checks for overdue fulfilment every five seconds while the process is running. It does not create or capture payments.

This first implementation has local HTTP tests using signed commerce fixtures and an injected PayPal verifier. Those tests are not live store or PayPal verification. No owned Shopify or WooCommerce store is available yet. Shopify payment-to-order matching is also incomplete: a standard order webhook does not include the capture reference, so it remains unmatched rather than guessing.

## Start locally

Use Python 3.13.15. Set `CRASHCART_MONITOR_TOKEN` privately to a random value of at least 24 characters. Keep it in your password manager or process environment; do not put it in source, a URL, screenshots or a shared terminal log.

```sh
python3 -m crashcart.monitor_server --db var/monitor.sqlite3 --port 8790
```

Open `http://127.0.0.1:8790/` and enter that access key. The server binds only to loopback. The current console has one operator who owns all configured stores; separate customer accounts, OAuth installation and hosted SaaS operations are not implemented by this command. The durable database is separate from the existing investigation database. Back it up and restrict access to its parent directory.

Create a store using its name, platform, HTTPS store origin and fulfilment deadline. This registers local configuration; it does not install an app or register provider webhooks. For WooCommerce, include the WordPress subdirectory in the HTTPS base URL when present; the registered source path must match exactly. Shopify requires the store's canonical `*.myshopify.com` domain.

## Private connection settings

Every secret belongs to a specific store. If the returned store ID is `store_abc`, its environment prefix is `CC_MONITOR_STORE_ABC_`. Use the complete ID, uppercased, in the prefix. Restart the process after changing its environment.

| Setting after the store prefix | Purpose |
| --- | --- |
| `SHOPIFY_SECRET` | Shopify app secret for validating the raw webhook body. |
| `WOOCOMMERCE_SECRET` | Secret configured on the owned WooCommerce order webhook. |
| `ALLOW_SANDBOX` | Set to `1` only when Sandbox signature-verification calls are authorized. |
| `PAYPAL_CLIENT_ID` | Owned PayPal Sandbox app client ID. |
| `PAYPAL_CLIENT_SECRET` | Owned PayPal Sandbox app secret. |
| `PAYPAL_WEBHOOK_ID` | ID of the webhook registered on that same app. |
| `PAYPAL_MERCHANT_ID` | Expected Sandbox merchant ID, checked against the completed capture. |

Each registered store must have a separate commerce signing secret. Reusing one Shopify or WooCommerce secret across stores disables commerce ingestion for every affected store and reports that setup is needed. Unsigned source headers alone cannot safely bind a shared signing key to one store. This manual setup therefore requires a separate Shopify custom app secret per store, or a separate WooCommerce webhook secret per store. A shared Shopify public-app secret requires an additional installation/account binding design; that flow is not implemented or claimed here.

The console returns only configured/not-configured flags. It never returns these values and does not treat saved configuration as a verified connection. Missing PayPal configuration fails closed before any provider call.

## Callback routes

Only use an owned store and Sandbox payments. A separately authorized HTTPS reverse proxy is required for actual provider delivery; nothing in this setup command creates public hosting or a tunnel.

- Shopify: `/webhooks/<store-id>/shopify`
- WooCommerce: `/webhooks/<store-id>/woocommerce`
- PayPal: `/webhooks/<store-id>/paypal`

The proxy must preserve raw request bodies and signature headers. For the operator console behind HTTPS, set `CRASHCART_MONITOR_PUBLIC_ORIGIN` to its exact HTTPS origin. This enables Secure session cookies and the explicit origin check. Do not strip Origin headers or weaken the request-header checks. Direct HTTP operation is for loopback development only.

Shopify deliveries use the raw-body HMAC header, canonical shop domain, supported order topic and delivery ID. WooCommerce deliveries use the raw-body HMAC header, registered source origin, order topic and delivery ID. The connectors keep minimal order facts and discard customer addresses and contact fields. See [the connector contract](CONNECTOR_CONTRACTS.md) for supported payloads.

PayPal `PAYMENT.CAPTURE.COMPLETED` deliveries are posted back to PayPal's signature-verification endpoint with the original event bytes. Only a verified completed capture for the configured merchant is eligible for matching. Commerce “paid” or “processing” labels cannot independently confirm PayPal payment.

The first matcher requires an exact capture reference, exact total and currency, and one unambiguous order. A WooCommerce `transaction_id` is a candidate reference, not proof of payment. Partial, unmatched or conflicting records remain unresolved. The fulfilment deadline begins at PayPal's capture completion time and is not reset by redelivery. This version observes merchant-reported order completion; it does not prove physical delivery to a customer.

## Inbox and verification

The inbox retains one overdue alert per matched order/deadline. Acknowledging an alert records that it was seen; it does not delete the breach. Late fulfilment may resolve the current issue while preserving its history. Keep the monitoring process running: an offline process cannot deliver real-time alerts. `/healthz` exposes scanner status and its last successful scan; a scanner error reports degraded health rather than inventing a result.

Local request, rate and receipt-retention safeguards are implemented and independently verified; see [the exact limits, recovery checks and backup command](WEBHOOK_SAFEGUARDS.md). They do not establish deployed HTTPS/proxy operation or authentic provider delivery. Receipt limits bound retained receipt rows, not total business-data growth or database file bytes. Keep real-store connection and intended hosting acceptance open until exercised.

Before claiming a real connection, verify authentic order delivery, actual PayPal signature verification, exact transaction matching, timely and overdue fulfilment, a real inbox alert, duplicate delivery, bad-signature rejection and restart persistence on the owned store. Repeat this for each platform. These gates remain open until their evidence is recorded. Billing is not enabled; the planned pricing unit is one store.

## API and tests

Operator mutations require a valid HttpOnly session, `X-CrashCart-Request: 1`, and an exact allowed Origin when sent by a browser. Webhook callbacks use provider signatures instead of operator cookies. All webhook bodies are bounded; unsupported routes cannot initiate payments.

```sh
python3 -m unittest tests.test_monitor_connectors tests.test_monitor_store tests.test_monitor_http -v
```

The HTTP tests run an actual loopback server and SQLite database, sign local commerce fixtures and inject a verifier for the PayPal boundary. They demonstrate application behavior under those named local conditions, not authenticity of a provider delivery or a live shop integration.
