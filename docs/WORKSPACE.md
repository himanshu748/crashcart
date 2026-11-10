# Full workspace guide

These optional views are separate from the account-free recorded demo.

## Full workspace and optional live test payments

The core payment-and-AI workspace uses Python **3.13.15** with SQLite and needs no pip or Node packages. Start with [the five-minute guide](JUDGE_GUIDE.md). Optional Studio and delivery-timing views additionally use Node.js **22.14.0** and npm; build those only when you need them. Compiled vendor bundles and private licence-bearing builds stay out of Git. See [Studio setup and licensing](studio.md).

The workspace’s **Investigate** action queues durable work; run the background worker against the same database to process it. Reloading does not repeat inference, and interrupted calls require review. The [bounded KERNEL observer](kernel-runner.md) can record an existing owned checkout under an explicit grant; reviewed browser evidence then joins the same case. It never starts or captures a payment.

```sh
python3 --version  # must report 3.13.15
python3 -m crashcart setup
python3 -m crashcart migrate
python3 -m crashcart serve
```

In another terminal in the same directory:

```sh
python3 -m crashcart worker
```

Open <http://127.0.0.1:8765>. For operator access, copy your locally generated
`CRASHCART_OPERATOR_TOKEN` from `.env` into the password field. It is sent only to
this local server and stored in an HttpOnly session cookie. Never publish `.env`.
The merchant fixture and health endpoint are public; investigation records require
operator access. The default binding is loopback. This development server is not
a production deployment.

```sh
curl --fail http://127.0.0.1:8765/healthz
python3 -m crashcart prerequisites
python3 -m unittest discover -v
```

`.env.example` documents configuration. A database is created under `var/`, with
idempotent migrations from `migrations/`. A different isolated database can be
selected with `--db /path/to/file.sqlite3`. All processes for one experiment must
use the same database. Avoid copying a live SQLite file without its WAL; use
SQLite's backup API.

## External prerequisites

Real sandbox checkout needs PayPal sandbox app credentials and an actual sandbox
buyer approval. KERNEL requires a reachable owned HTTPS application, browser
access and a recording. Webhooks require a registered ID and reachable HTTPS
ingress. Model and remote browser usage require configured access and explicit
usage authorization. AG Studio needs its actual package, license and supported
agent integration for the full acceptance contract. AG Studio is commercial:
obtain your own applicable licence or follow the vendor's local-evaluation terms.
The maintainer's private trial key and licensed build are not included. A licence
value supplied as `AG_STUDIO_LICENSE_KEY` during compilation becomes part of that
browser bundle; keep private licence-bearing output out of public source and
follow the vendor's redistribution terms. See
[Studio licensing](studio.md#licensing-and-agent-boundary). Render is excluded.

For AI, configure your own OpenAI key and model, or follow the
[explicit Modal setup](investigator.md#authorization-and-configuration).
Configure the identical owned origin in `MODAL_BASE_URL` and
`MODAL_ALLOWED_ORIGIN`; canonical `modal.run` and tenant/region `modal.direct`
origins are supported. The `.invalid` default is for injected local tests only.
For a bounded owner test, both API and worker can share the existing private
`CRASHCART_MODEL_ALLOWANCE_PATH` ledger. No inference credentials or provider
allowance are included.

The local application fails explicitly when service configuration is missing.
Do not interpret `configured` as a successful connectivity check. The [sponsor ledger](sponsor-ledger.md) distinguishes implemented
capabilities from historical observations and pending verification.

## Optional sandbox test-buyer path

The keyless path above is the complete recorded demonstration. To attempt a new
checkout, use the full workspace with **your own PayPal Sandbox app and accounts**:

1. In [PayPal Developer](https://developer.paypal.com/), use a Sandbox **Business**
   account for the merchant, a Sandbox app for its client ID/secret, and a separate
   Sandbox **Personal** account for buyer approval. Use test funds only.
2. Run the full-workspace setup above. Put the app's values in the local `.env`
   fields `PAYPAL_CLIENT_ID` and `PAYPAL_CLIENT_SECRET`. Keep the generated
   `CRASHCART_OPERATOR_TOKEN` private. The application uses the Sandbox API.
3. After the account owner authorizes the test, set `CRASHCART_ALLOW_SANDBOX=1`
   locally, start both server and worker, and create an investigation. Leave
   model and KERNEL enable flags at zero unless separately configured and
   authorized. Their keys are not needed to sign in as the test buyer.
4. Choose **Start test checkout** and approve with the Sandbox Personal buyer.
   Return to CrashCart and confirm the approved payment. Inspect the independent
   payment read and the ticket record; do not infer success from the return URL.
5. A complete remote-browser, notification or AI verification also needs its
   [external prerequisites](#external-prerequisites). These remaining proofs
   cannot be completed by this recorded judge mode.

Use the following as a **private handoff template**, not values to commit here:

| Item | Placeholder for the owner to fill privately |
| --- | --- |
| Sandbox merchant/app owner | `<YOUR_SANDBOX_BUSINESS_ACCOUNT>` |
| Sandbox client ID | `<SET_PAYPAL_CLIENT_ID_IN_LOCAL_ENV>` |
| Sandbox client secret | `<SET_PAYPAL_CLIENT_SECRET_IN_LOCAL_ENV>` |
| Sandbox buyer email | `<YOUR_SANDBOX_PERSONAL_EMAIL>` |
| Sandbox buyer password | `<SHARE_PRIVATELY_NOT_IN_GIT>` |
| Owned test-store URL | `<AUTHORIZED_LOCAL_OR_HTTPS_STORE_URL>` |

Never put a real PayPal password, usable test-buyer login, API key or licence in
this README, Git, screenshots or public video. Judge access to the recorded
review needs none of those values. If private live access is offered, communicate
its test-only credentials through the submission's private testing instructions.

## Evidence

`BUILD_CHECKLIST.md` defines the acceptance contract; [STATUS.md](STATUS.md)
records the public development status. The maintainer's private evidence archive
binds runtime observations to source hashes. It is intentionally excluded from
source publication, along with `.env`, databases, payment/account receipts,
licence values and checkout recordings. The normal workspace starts with its own empty database; it does not include the
maintainer's saved database. Judge mode instead creates two isolated cases from
the curated earlier recording. Two historical input tapes are included: the
earlier repair comparison and the original late-read negative example. Neither
is a fresh payment or a complete acceptance archive.

The tests exercise local synthetic scenarios unless explicitly identified
otherwise. Passing them or publishing source does not establish a successful
sandbox payment, fresh repair verification, hosted deployment or release.
The completion validator in `scripts/check_completion.py` operates on the full
private acceptance archive; it cannot reproduce that evidence from a public
source checkout. Relevant source changes require affected proof to be renewed.
Read [the product contract](product-contract.md) for scope and immutable
timing semantics.

## Local workbench journey

The dashboard presents payment and delivery in plain language: **Promise kept**, **Promise broken** or **More evidence needed**. **Check payment status** reads the saved checkout through the existing payment service; **Start test checkout** still requires buyer approval. **Original records & technical details** retains unchanged investigation titles, proof modes, payment references and browser sources. **Recorded page text** preserves the original captured text verbatim. These disclosures do not create new evidence, and readable labels do not change payment decisions.

Open `/?view=home` for the landing page even while signed in. Both CrashCart home links retain the selected investigation; **Open your workspace** returns to it. The UI calls `LIVE_SANDBOX` an **Initial test checkout**, `FRESH_SANDBOX` **Repair verification · new test checkout**, and `RECORDED_REPLAY` a **Replay of a saved checkout**. API/export proof modes retain their exact technical values. Replay does not make a new payment; repair verification requires a separate test payment.

1. Create an investigation with the fixed workshop fixture and a controlled fault.
2. Start sandbox checkout. If access is disabled or missing, the UI shows the
   limitation and the run remains inconclusive. No example payment is substituted.
3. With authorized sandbox access configured, follow the provider's actual buyer
   approval URL, return, and choose Confirm approved payment. The server reads
   approval independently; callback parameters do not establish it.
4. Reconcile payment and inspect recorded browser views, provider records and the
   stored ticket. For healthy recovery, keep the worker running. Inspect raw
   operation IDs and the timeline under their recorded provenance.
5. Ask investigator only after model access/allowance is authorized. Missing access
   is recorded. Cancel preserves collected evidence. Refresh restores run state.
6. Download inspection JSON for any run. Recorded defective response-loss or
   interruption failures also offer an offline regression ZIP. Healthy runs retain
   inspection export. A replay uses recorded inputs; it creates no new payment.

## Delivery timing

Open **Delivery timing** from the workspace, or visit
<http://127.0.0.1:8765/deadlines/index.html> after signing in to the workspace.
Add `?run=run_…` to retain a selected investigation. The view compares each saved
checkout relative to its own confirmed payment: the fixed 60-second ticket
window, recorded ticket times and the saved server result. Case details link
back to the investigation and AG Studio records.

The real `@bryntum/scheduler-community` **8.0.0-beta.1** component powers this
read-only chart. Its separate page keeps the beta dependency out of the core
workspace. It loads up to 60 returned investigations, including the selected case
when available, with search and saved-result filters and a 120-second or
five-minute chart range. Ticket times outside that range remain in case details.
A table also exposes case selection and timings. Unconfirmed payments or
inconsistent identities, dates or records receive an explanation and no chart
anchor; the browser never calculates a replacement payment verdict.

The page uses authenticated, same-origin `GET /api/runs` and
`GET /api/runs/:id` reads. Refreshing reads saved records; it does not contact
PayPal, start a checkout, run a model or change delivery. Viewing a saved test
payment is distinct from a fresh sandbox verification. Historical local browser checks cover saved-record selection, filters and
keyboard interactions. These do not establish a complete fresh checkout and
repair comparison; [STATUS.md](STATUS.md) records the current boundaries.

Build both frontend entries with the existing Node.js **22.14.0** toolchain:

```sh
npm ci --ignore-scripts --prefix studio
npm run build --prefix studio
npm run test:deadlines --prefix studio
```

The build emits the local SDK, CSS and fonts under `web/deadlines/`; it does not
require a Bryntum account or a commercial trial key. The pinned Community
packages are MIT-licensed. The [build script](../studio/build.mjs) copies the installed
Bryntum licence, third-party notices and the
[Font Awesome licence](../studio/vendor/FONT-AWESOME-LICENSE.txt) into the generated
`web/deadlines/` assets, alongside linked bundle legal notices. Preserve those
notices when distributing a build. The model test command exercises local
projection logic; a build or passing model tests alone does not verify browser
behavior. See the [sponsor ledger](sponsor-ledger.md) for integration scope.

Historical sandbox and replay observations are summarized in the
[sponsor ledger](sponsor-ledger.md); their private receipts and recordings
are not part of this repository. You can create your own inspection exports and
eligible regression archives through the application. A reduced replay can remove
a timely read that the repaired comparison needs, so a reduced failure alone
must not be presented as proof of recovery.

See [architecture](architecture.md), [invariant and scope](product-contract.md),
[investigator](investigator.md), [offline replay](replay.md),
[Postman](postman.md), and [sponsor ledger](sponsor-ledger.md).

The CI workflow is configured. A source commit or push does not establish that
CI passed; inspect the repository's actual Actions results. Offline unit tests
use synthetic `LOCAL_TEST` transports where needed. Live acceptance checks and
release limitations remain separate in [STATUS.md](STATUS.md). The hosted recorded review serves build-time results; the live checkout backend is separate.
The [Devpost entry](https://devpost.com/software/crashcart-87asqz) was submitted on 10 November 2026. Submission does not close the remaining internal acceptance checks.

## Submission materials

[Verified clean-clone path](SUBMISSION_VERIFICATION.md) · [Submission scope](SUBMISSION_GATES.md) · [Shared Lightsail hosting](LIGHTSAIL_SHARED_HOST.md) · [Video script](VIDEO_SCRIPT.md) · [Devpost draft](DEVPOST.md). The current recorded demo is verified on the existing Lightsail host. The [public video](https://www.youtube.com/watch?v=gFWje84_wEA) is available. The [Devpost entry](https://devpost.com/software/crashcart-87asqz) was submitted on 10 November 2026.
