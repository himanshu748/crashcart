# CrashCart

A customer paid. Their ticket never arrived. CrashCart brings the checkout,
PayPal payment and store delivery records into one investigation so a support
team can find where the purchase broke down.

This build uses an owned workshop store and PayPal Sandbox: USD 29 buys exactly
one ticket within 60 seconds of completed capture. It is a private-workspace
prototype, with a marketing page, investigation workspace, AG Studio records and
a Bryntum delivery-timing view.

**In development. Read [STATUS.md](STATUS.md) for actual verified scope.**
No real payment, AI investigation, KERNEL recording, or AG Studio claim is implied
by a local test. The release boundary is CC-060 in BUILD_CHECKLIST.md.

## Start locally

Prerequisites: Python **3.13.15** with SQLite, Node.js **22.14.0** and npm.
No pip packages are needed. Build the frontend before starting Python: this
source repository intentionally excludes compiled vendor bundles and private
licence-bearing builds. The pinned lockfile supplies the real frontend packages.
See [Studio setup and licensing](docs/studio.md).

```sh
python3 --version  # must report 3.13.15
node --version     # must report v22.14.0
npm ci --ignore-scripts --prefix studio
npm run build --prefix studio
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
[Studio licensing](docs/studio.md#licensing-and-agent-boundary). Render is excluded.

For AI, configure your own OpenAI key and model, or follow the
[explicit Modal setup](docs/investigator.md#authorization-and-configuration).
The public Modal origin is a nonworking `.invalid` placeholder; using an owned
deployment requires a reviewed source allowlist change as well as environment
configuration. No inference credentials or provider allowance are included.

The local application fails explicitly when service configuration is missing.
Do not interpret `configured` as a successful connectivity check. The [sponsor ledger](docs/sponsor-ledger.md) distinguishes implemented
capabilities from historical observations and pending verification.

## Evidence

`BUILD_CHECKLIST.md` defines the acceptance contract; [STATUS.md](STATUS.md)
records the public development status. The maintainer's private evidence archive
binds runtime observations to source hashes. It is intentionally excluded from
source publication, along with `.env`, databases, payment/account receipts,
licence values and checkout recordings. A clean clone starts with its own empty
local database; it does not include the maintainer's saved sandbox database. One curated
historical input tape is included for recorded offline replay; it is not a fresh
payment or a complete acceptance archive.

The tests exercise local synthetic scenarios unless explicitly identified
otherwise. Passing them or publishing source does not establish a successful
sandbox payment, fresh repair verification, hosted deployment or release.
The completion validator in `scripts/check_completion.py` operates on the full
private acceptance archive; it cannot reproduce that evidence from a public
source checkout. Relevant source changes require affected proof to be renewed.
Read [the product contract](docs/product-contract.md) for scope and immutable
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
payment is distinct from a fresh sandbox verification. Final v49 browser and
acceptance verification is still in progress; [STATUS.md](STATUS.md) records the
current evidence and limitations.

Build both frontend entries with the existing Node.js **22.14.0** toolchain:

```sh
npm ci --ignore-scripts --prefix studio
npm run build --prefix studio
npm run test:deadlines --prefix studio
```

The build emits the local SDK, CSS and fonts under `web/deadlines/`; it does not
require a Bryntum account or a commercial trial key. The pinned Community
packages are MIT-licensed. The [build script](studio/build.mjs) copies the installed
Bryntum licence, third-party notices and the
[Font Awesome licence](studio/vendor/FONT-AWESOME-LICENSE.txt) into the generated
`web/deadlines/` assets, alongside linked bundle legal notices. Preserve those
notices when distributing a build. The model test command exercises local
projection logic; a build or passing model tests alone does not verify browser
behavior. See the [sponsor ledger](docs/sponsor-ledger.md) for integration scope.

Historical sandbox and replay observations are summarized in the
[sponsor ledger](docs/sponsor-ledger.md); their private receipts and recordings
are not part of this repository. You can create your own inspection exports and
eligible regression archives through the application. A reduced replay can remove
a timely read that the repaired comparison needs, so a reduced failure alone
must not be presented as proof of recovery.

See [architecture](docs/architecture.md), [invariant and scope](docs/product-contract.md),
[investigator](docs/investigator.md), [offline replay](docs/replay.md),
[Postman](docs/postman.md), and [sponsor ledger](docs/sponsor-ledger.md).

The CI workflow is configured. A source commit or push does not establish that
CI passed; inspect the repository's actual Actions results. Offline unit tests
use synthetic `LOCAL_TEST` transports where needed. Live acceptance checks and
release limitations remain separate in [STATUS.md](STATUS.md). The application
has not been deployed, and source publication does not submit a hackathon entry.
The [Devpost project page](https://devpost.com/software/crashcart-87asqz) is separate
from this source repository; submission and final release remain unfinished.
