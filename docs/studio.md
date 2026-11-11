# Evidence Studio — optional local tooling

AG Studio is **not part of the public submission experience or selected sponsor claim**.
Its optional local integration is documented here for developers. The account-free
recorded workspace and its replay command do not require it.

CrashCart embeds the actual `ag-studio` and `ag-studio-react` 3.0.0 packages. The
React workspace reads authenticated saved investigations from the same local
server. It does not make a payment or refresh PayPal when a run is selected.

## Recorded explorer (local access, not deployed)

The optional `/explorer/` page uses the **actual pinned AG Studio SDK** and the same five evidence panels as the private workspace. It reads only exported replay rows. The two case variants share the saved input; the repair is not a new purchase. The native Agent Framework runs three explicit browser filters. Its panel says **no AI call**; arbitrary questions are unsupported. A separate disclosure shows the genuine earlier saved AI investigation, clearly identified as another case.

```sh
npm ci --ignore-scripts --prefix studio
# Configure AG_STUDIO_LICENSE_KEY privately in this process, never in Git.
npm run build:recorded --prefix studio
python3 -m crashcart.recorded_studio --serve --port 8769
```

Open <http://127.0.0.1:8769/explorer/>. No operator key, PayPal key or model key is read by this server. Without a licensed build, the route shows an explicit access message and serves no SDK or record data. The ordinary recorded example remains usable. A build marker records configuration presence, not vendor validation or public redistribution permission.

To prepare a **private, local** static release (never commit it):

```sh
python3 -m crashcart.recorded_studio --output var/studio-release
```

The default `judge.sh` and its exported replay ZIP remain package-free and do not include Studio. A public deployment is gated on owner approval and an applicable vendor entitlement. See [release preparation](STUDIO_RELEASE.md).

## Private workspace: build and open

Python 3.13.15 runs the application. Building Studio additionally requires
Node.js 22.14.0 and npm. The lockfile pins the frontend toolchain and packages.

```sh
npm ci --ignore-scripts --prefix studio
npm run build --prefix studio
python3 -m crashcart serve
```

Open <http://127.0.0.1:8765/studio/index.html>. The checkout workbench and Studio
share the local operator session. If signed out, enter the local operator token
in the password field; never include that token in a URL or public artifact.

Build output under `web/studio/` is the application loaded by Python. Compiled
vendor bundles are intentionally excluded from this source repository; build
locally before serving it. Editable sources and the build script live in `studio/`. A successful build establishes type and bundle
compatibility, not widget behavior; actual browser checks are recorded separately.

## Evidence views

Five instances of the registered custom evidence widget display the selected recorded browser view,
independently saved provider record, current stored ticket, comparison run, and
event trace. Browser kind and recorded path distinguish operator, merchant and
return pages; an unknown source stays unknown. Source IDs and observation times
remain visible. Selecting a new run
clears the previous data while loading; an old response cannot overwrite the
latest selection. The comparison is a separate execution, with its own mode and
identity. Selecting two records does not establish equivalent fault schedules.

`LOCAL_BROWSER` is a local browser observation. `LIVE_SANDBOX` and
`FRESH_SANDBOX` label actual sandbox runs; `RECORDED_REPLAY` consumes saved input.
Refreshing records does not produce fresh provider verification. Event order
does not establish causality; the trace exposes recorded causal IDs separately.

Inspection JSON is available for every run. Eligible defective missing-ticket
runs offer the existing offline regression ZIP. Its original and reduced timing
limitations remain described in [replay documentation](replay.md).

## Licensing and agent boundary

AG Studio is commercial software. Follow the vendor's
[licensing and local-evaluation instructions](https://www.ag-grid.com/studio/react/licence-install/)
for your own optional build. The vendor's [6 November hackathon announcement](https://www.ag-grid.com/blog/build-a-payments-dashboard-without-building-a-dashboard/)
describes judging-period licence arrangements. No Studio deployment or licence
entitlement is offered as part of this public submission. Private trial keys and
licence-bearing compilation overlays are not included in this repository.
Do not remove vendor watermarks or warnings.

`studio/build.mjs` reads only the explicitly named `AG_STUDIO_LICENSE_KEY` build
variable for licensing; it does not export the rest of the server environment.
That value is embedded in the browser bundle when provided. Keep private
licence-bearing build output out of public source and follow the vendor's
redistribution terms. Delivered licensed access and the full operator journey
still require separate verification.

“Ask a question” opens Studio's native Agent Framework chat and the registered
Answers widget. A message sends one authenticated request to
`POST /api/studio/query`. The server allows only a closed set of filters over an
owned saved-record snapshot; deterministic code computes rows and counts. The
assistant cannot create a payment, change a ticket, run arbitrary SQL, or decide
the payment invariant. “Show answers” makes results accessible on small
screens without the chat panel consuming their width.

The server requires the selected provider configuration described in
[investigator setup](investigator.md#authorization-and-configuration),
`CRASHCART_ALLOW_MODEL=1`, and a positive `CRASHCART_STUDIO_MODEL_MAX_CALLS`
allowance before model use. OpenAI Responses remains the default; explicitly
selected Modal uses the owned DeepSeek Chat Completions endpoint. Both share the
same no-redirect/no-retry transport and 65,536-byte UTF-8 request limit. A
parent-enforced total deadline terminates and reaps the isolated HTTP worker,
including for slowly arriving headers or body; private credentials travel over
stdin only. Closing the local request cannot guarantee upstream cancellation
or erase usage already incurred. Model
output is bounded to 1,024 tokens and 4,096 characters. Actual provider, protocol,
endpoint origin, returned model/response IDs and reported usage remain in the
saved receipt even when a response is rejected. A malformed, truncated or
reasoning-only response cannot produce dashboard rows. Every submission gets a new request ID, including
repeated wording. The backend reserves the request before sending it and does
not retry automatically. A result carries its model source, response ID, dataset
hash, snapshot time, request ID, and underlying evidence references. Selecting
another investigation or refreshing records clears the prior result and rejects
late responses. LOCAL_TEST receipts show an explicit test-data banner before the
result, and retain their model/request provenance in an expandable section.
Native Stop stops waiting and applying results; an already sent
model request may still finish and consume its reserved allowance.

Injected local test responses remain `LOCAL_TEST`. Historical maintainer tests
also exercised four actual model-backed native queries over changing copied
saved records. Those private traces are not included in this checkout, and
neither selecting a record nor running a local test establishes a new provider
call. See [development status](archive/STATUS.md) for remaining verification limits.

## Content Security Policy

The server supplies a fresh random nonce for Studio's documented `styleNonce`
property on every Studio HTML response. The nonce in the HTML matches the
response's `style-src` directive. The [AG Studio security guide](https://www.ag-grid.com/studio/react/security/)
documents this mechanism for generated theme styles.

The pinned 3.0.0 SDK also creates a color-change sensor style without attaching
that nonce. Its exact content is the following 101 UTF-8 bytes, with no trailing
newline:

`@property --ag-studio-color-change { syntax: '<color>'; inherits: true; initial-value: transparent; }`

Studio HTML therefore permits that one source expression in addition to `'self'`
and its fresh nonce:

`'sha256-ydedGqCb79ipYJuuWRyOTMrKbkjYWv8WIjG7SRdnEPU='`

[CSP's inline hash matching rules](https://www.w3.org/TR/CSP3/#match-element-to-source-list)
bind the allowed style to its exact UTF-8 content. An added newline or changed
declaration has a different hash and is not allowed by this expression. This
exception is specific to the inspected 3.0.0 sensor; an SDK upgrade requires
reviewing the emitted bytes and policy again.

Scripts remain same-origin. Other generated Studio styles still require the
nonce. Ordinary workbench pages, assets, APIs and the scoped verification gateway
retain their existing strict policy without this hash or a nonce. No
`unsafe-inline`, `unsafe-eval`, wildcard source or external font loading is added.
Response-policy tests and actual browser enforcement checks are separate proof.
