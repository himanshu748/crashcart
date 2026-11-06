# CrashCart merchant monitoring

Approved 6 November 2026: payment-to-fulfilment monitoring for small merchants, sold per store. Build Shopify and WooCommerce connectors and an in-app alert inbox. No owned store is currently available for live verification.

The workflow: add a store, set its fulfilment promise, receive authenticated order/payment updates, match the payment to the order, and alert when a paid order becomes late. Acknowledging an alert never erases the breach. Later fulfilment resolves it while retaining history.

This is newly authorized product scope. Original CC-001–060 and the frozen private 47/60 remain intact; they do not establish monitoring acceptance. scripts/judge.sh remains the separate recorded demonstration. No old replay becomes live proof.

First slice: one merchant operator with multiple owned stores, separate database and entry point. Multi-customer accounts, platform OAuth, hosting and commercial billing require further acceptance. Store configuration is not proof of a connection.

PayPal confirmation requires the store's authenticated capture notification and merchant identity. Platform status alone cannot confirm a PayPal payment. Match exact transaction reference, full order amount and currency; unmatched or ambiguous evidence stays unresolved. The first promise concerns merchant-marked fulfilment, not physical receipt. Partial Shopify fulfilment cannot satisfy the whole order; WooCommerce completed is a merchant completion signal.

The deadline starts at payment completion. Duplicate notifications, restarts and order updates cannot extend it. A late fulfilment is a historical breach even when first scanned after fulfilment. Alerts preserve their evidence and timeline.

## Acceptance



Only an exercised complete condition is checked. PM-001, PM-005 and PM-007 have independent local verification; the remaining seven are open. Local signed fixtures are separate evidence from authentic provider delivery.

- [x] **PM-001 — Store boundaries:** actual authenticated HTTP access, identical external IDs across two stores, cross-store negative cases and restart preserve isolation.
- [ ] **PM-002 — Commerce ingestion:** both raw-body signatures and registered origins validated; tampering rejected; duplicate/event identity and supported fields preserved. Signed local contracts AND authentic delivery from each owned platform required.
- [ ] **PM-003 — Merchant PayPal connection:** genuine Sandbox capture notification verified against that store's app, webhook and merchant identity; bad signatures, wrong merchant and absent configuration fail closed. Monitoring creates no payments.
- [ ] **PM-004 — Matching:** real platform transaction identifiers match the same capture, amount and currency. Unmatched/partial/ambiguous evidence stays explicit. Real Shopify and WooCommerce transaction samples required.
- [x] **PM-005 — Promise clock:** exact boundary, duplicate/out-of-order arrival, restart and late fulfilment preserve the immutable original deadline and historical breach. Store changes never rewrite old deadlines.
- [ ] **PM-006 — In-app alerts:** running worker opens one alert without a page visit; acknowledgement and later fulfilment retain history through restart. Actual HTTP/worker checks AND authentic connected-store execution required.
- [x] **PM-007 — Human workflow:** browser add/select store, understand readiness, inspect order and acknowledge alert; keyboard/phone and empty/unavailable/unmatched/expired-session states. No invented connected-store activity.
- [ ] **PM-008 — Installation:** owner completes supported setup for both platforms with minimum order/fulfilment access and working disconnection. Manual technical setup is not OAuth installation.
- [ ] **PM-009 — SaaS operation:** separate merchant accounts, session lifecycle/isolation, HTTPS, intended hosting, retention/recovery exercised. A loopback operator app does not pass this.
- [ ] **PM-010 — Per-store billing:** subscription boundary/cancellation defined and separately authorized Sandbox billing verified. No real charge or invented price is authorized.

## Current local verification — 6 November

Webhook safeguard changes have fresh source-bound reacceptance of PM-001/005/007. Full suite **456 tests in 103.486s, OK**, replay **3 in 1.295s, OK**, existing UI **14 pass**; both independent reviews passed. New supplemental WH-001–006 pass locally. [Current evidence](../evidence/runs/submission-ready/monitor-v2.json) and [exact guards/recovery limits](WEBHOOK_SAFEGUARDS.md).

Initial browser pressure exercised the default 16-handler cap and retained records. A later screenshot found the notice below the viewport; the sticky repair has fresh validation/offline/session/acknowledgement visibility proof on desktop and phone. The exact repaired-notice/overload screenshot remains unverified after two stopped fixture failures. Unchanged-UI phone/empty/unmatched/setup evidence retains its earlier scope. This is not authentic delivery, physical-phone certification or deployed operation.

## First preview — historical local verification

PM-001: actual authenticated HTTP readback after server recreation against the same database, colliding external IDs, different order outcomes, expired prior session and cross-store acknowledgement rejection. This is single-operator store separation, not separate customer accounts or host-crash recovery.

PM-005: exact deadline boundary, duplicate/out-of-order events, restart, immutable promise/capture association, late fulfilment history and delayed on-time correction. Signed HTTP updates and the actual browser show distinct corrected histories. This proves deterministic local mechanics, not provider authenticity.

Full suite: **426 tests in 62.086s, OK**. Replay: **3 tests in 0.314s, OK**. Existing UI tests: **14 pass, 0 fail**. Independent correctness and security review accepted the scoped loopback slice. [Source-bound evidence and retained failures](../evidence/runs/submission-ready/monitor-v1.json).

PM-002/003/004/006 remain blocked on authentic store/payment data. PM-007 passes the local browser workflow: keyboard add/select/order/acknowledgement, readiness, empty/unavailable/unmatched states, session invalidation/recovery and phone layout. This is not an eight-hour session endurance run, a physical-phone test or full accessibility certification. PM-008 installation/disconnection, PM-009 customer SaaS/operations and PM-010 billing are pending. Local request/rate/receipt guards and recovery now have verified evidence. Intended HTTPS/proxy operation, authentic callbacks and total business-data retention remain open.

The later Shopify address bug was preserved, fixed and reverified: unusable addresses create no store; valid canonical case/default-port variants normalize. The safe guidance appears in the actual browser. Previous source-bound reports remain historical; the latest receipt identifies the final hashes.

## Current blockers

Owned platform stores, authentic order/transaction samples, merchant-specific PayPal Sandbox webhook registration and approved HTTPS ingress are missing. No provider connection, public registration, hosting or charge is implied by code. Local tests can validate mechanics while real-store acceptance stays open.

## Protocol references

- [Shopify raw webhook verification](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries)
- [Shopify topics/payloads](https://shopify.dev/docs/api/webhooks/latest)
- [WooCommerce webhook contracts](https://developer.woocommerce.com/docs/apis/rest-api/v2/webhooks)
- [PayPal webhook integration](https://developer.paypal.com/api/rest/webhooks/rest/)
