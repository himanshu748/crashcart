# One-investigation verification gateway

`crashcart.verification_gateway` is a prepared, loopback-only entry point for a
short, explicitly approved verification window. It does **not** open a tunnel,
publish a service, configure PayPal, create a run, or authorize provider usage.
Local checks are labelled `LOCAL_TEST`. A source checkout creates no public
window or provider authorization. Any real use needs the operator's own owned
HTTPS target, credentials and explicitly approved session/payment/webhook scope.
Historical temporary windows and recordings are not published here. Authentic
webhook and fresh repair acceptance remain separate from local gateway tests.

The application’s full operator credential stays local. The gateway generates a
fresh random 256-bit credential for exactly one existing run and its purchase.
The gateway has no catch-all forwarding route, so later additions to the ordinary
server cannot silently become public. It calls the unchanged `MerchantService`
and `Store`; it does not add another payment or entitlement implementation.

## Capabilities and limits

Request bodies have a ten-second total monotonic read deadline, capped by the
gateway's remaining lifetime. A continuously trickled body cannot extend that
deadline. Body reads release the shared scope lock, so one incomplete request
does not hold up health checks or revocation. Before any mutation, the gateway
reacquires the lock and rechecks scope, expiry and order identity; payment
operations remain serialized. Timeout responses are HTTP 408 and truncated
bodies are rejected. Webhook signature verification receives the original bytes.

This bounds body input for the temporary gateway. It does not claim general
production denial-of-service resistance: headers and response writes still have
idle timeouts, and the eight request slots can be occupied temporarily.

| Surface | Allowed behavior |
| --- | --- |
| Public static pages | `/`, `/shop`, `/checkout`, `/return`, `/cancel`, `/ticket`, plus exactly `/app.js`, `/marketing.js`, and `/style.css`. No static directory listing, Studio bundle, `.env`, or export. |
| Public configuration | `/healthz` and the fixed owned `/api/fixture`. Both require the gateway scope to remain valid. |
| Login | `/api/login` accepts only the new gateway token. The global operator token and normal operator cookie do not work. |
| Authenticated reads | `/api/runs` returns one run; `/api/runs/{scoped_run}` and `/api/merchant/{scoped_purchase}` expose only that investigation. `/api/prerequisites` reports the gateway’s own scope/configuration and explicitly leaves connectivity unverified. |
| Authenticated writes | Exactly the scoped run’s `order`, `capture`, `observation`, `reconcile`, and `cancel` actions. No run creation, model investigation, Studio query, administration, fixture changes, or export. |
| Webhook | Public POST `/api/webhooks/paypal` accepts only an event correlated through `resource.supplementary_data.related_ids.order_id` to this purchase’s current persisted order. The **unchanged** event and headers must then pass normal PayPal signature verification. Every duplicate is verified again before durable deduplication. |

Capture accepts only the exact persisted `order_id`; price, currency, supplied
approval state, and payment evidence are rejected. Order creation uses the normal
server-owned USD 29.00 fixture. Callback query values never establish approval.
Independent provider reads and deterministic payment/entitlement checks remain
the merchant service’s responsibility.

The run mode, fixture, promise, invariant, fault, budget, purchase identity, amount,
currency, and creation timestamps are frozen when the gateway starts. Ownership,
sandbox environment, scope hash, order identity, public origin, and expiry are
checked again on every request. A scope change closes access. The one permitted
identity transition is the initial order created through this gateway. If an
order is created elsewhere after startup, create a new explicitly scoped gateway
after reviewing that state instead of widening the old one.

Lifetime is at most 1,800 seconds (default 900). Both wall time and monotonic time
enforce it; a slow body is checked again before starting a mutation. The CLI also
stops its listener at expiry. An already-started provider operation can finish
after expiry; expiry does not undo a sandbox capture. Normal adapter timeouts
still apply. The gateway permits at most eight concurrent request threads, a
10-second socket timeout, 16 KiB of headers, 128 KiB JSON bodies, and 256 scoped
mutations/webhook-verification attempts. Reaching a limit fails closed; it does
not create a fresh credential automatically.

Cookies use `__Host-crashcart_gateway`, `HttpOnly`, `Secure`, `SameSite=Lax`,
`Path=/`, and a remaining-lifetime `Max-Age`, without a Domain attribute. Browser
POST origins must equal the exact configured HTTPS origin. Host and forwarded
headers never authorize an origin. A server-to-server login carrying the private
token, a valid Bearer request, or a webhook may omit Origin; cookie-only writes
may not. Credentials and URLs are never logged. Do not place the gateway token
in a URL, screenshot, recording, evidence receipt, or chat.

## Start only after public-origin approval

First prepare one existing authorized owned sandbox run through the local
operator workflow. Agree the exact external HTTPS origin, route lifetime, and
provider usage separately. The gateway does not verify DNS ownership or create
TLS/ingress. Only an approved TLS terminator/tunnel should reach its loopback
port. The approved origin must be a canonical HTTPS origin without a trailing
slash, port, query, credentials, or path.

The following command is a template, **not a performed deployment**. Set the two
non-secret placeholders to the approved origin and existing run ID. Use the
actual configured local database path. No `.env` edits are made by this command.

```sh
env CRASHCART_PUBLIC_URL="${CRASHCART_GATEWAY_ORIGIN:?Set the approved HTTPS origin}" \
  python3 -m crashcart.verification_gateway \
  --db var/crashcart.sqlite3 \
  --run "${CRASHCART_GATEWAY_RUN:?Set the existing authorized run ID}" \
  --public-origin "$CRASHCART_GATEWAY_ORIGIN" \
  --external-origin-approved \
  --lifetime-seconds 900 \
  --token-file var/verification/gateway-token
```

The approval flag records an operator assertion; it is not permission to create
ingress. `CRASHCART_PUBLIC_URL` must exactly match `--public-origin` in this process
because `MerchantService` uses it for PayPal return/cancel URLs. The normal
adapter’s sandbox gate and credentials remain required. If reusing an existing
order, verify that its previously persisted return URLs already point to the
approved origin; the gateway never rewrites an immutable order request.

The CLI prints only loopback address, chosen ephemeral port, scoped run ID, and
expiry. It creates the token file with exclusive creation and mode `0600` inside
the project’s ignored `var/` directory. It will not overwrite a previous file.
Keep that file private; revocation/expiry makes it unusable. Stop the foreground
gateway process to close its listener early. Neither normal server startup nor
this command starts a worker: use the documented existing worker separately if
the chosen fault/recovery journey needs it. A deliberate process-interruption
fault can terminate this gateway, so treat that as a distinct interruption
experiment with its own recording and recovery plan.

## KERNEL handoff

KERNEL receives **only** this gateway token for application login. The KERNEL
adapter currently calls its bootstrap environment field
`CRASHCART_OPERATOR_TOKEN`; construct a private per-adapter environment whose
value for that field is the gateway token, never the project’s global operator
token. Include only required KERNEL configuration, the exact approved origin,
and the already approved session allowance. Do not mutate the parent process’s
operator environment. Read the token file directly in that local orchestrator;
do not print it or substitute it into a shell command.

The browser’s ordinary observation endpoint continues to store
`browser_kind=LOCAL_BROWSER`. A claim of actual KERNEL execution must come from
the real adapter’s separately correlated session and recording receipt. The
gateway does not upgrade browser-submitted text to trusted KERNEL evidence.
The one-run page still displays ordinary workbench controls; unavailable routes
fail closed. There is no hidden creation, investigation, export, or Studio access.

## Webhook handoff

Register the approved origin’s `/api/webhooks/paypal` only through an authorized
PayPal sandbox application configuration, then supply the real webhook ID to
this process. Event correlation is an early scope filter, never proof of
authenticity. An approved-order resource without the supported related-order
field is rejected, not rewritten or treated as verified. The normal
`PayPalSandbox.verify_webhook` validates the headers and calls PayPal’s signature
verification API. Only its success may reach durable webhook storage and the
scoped reconciliation job. A successful receipt does not by itself confirm a
payment or issue a ticket.

## Reproduce local checks

```sh
python3 -m unittest tests.test_verification_gateway -v
```

The suite uses actual ephemeral loopback HTTP listeners and temporary SQLite
databases. It injects a clearly synthetic provider and denies every socket
connection except `127.0.0.1`. It checks global-credential rejection, one-run
visibility, exact route/body restrictions, origin spoofing, traversal and
symlink rejection, expiry and configuration drift, synthetic normal-service
approval/capture/reconciliation, one-ticket idempotency, and verified-before-
deduplicated webhook handling. A real loopback request also serves the delivered
shop HTML, extracts its same-origin scripts and stylesheets, and checks each
declared asset's exact delivered bytes, MIME type, and strict CSP with and without
authentication. These tests do not prove public reachability,
PayPal signature delivery, KERNEL execution, or sponsor-account readiness.
