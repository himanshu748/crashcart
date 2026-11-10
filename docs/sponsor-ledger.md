# CrashCart integrations

CrashCart follows a purchase from browser checkout to payment to ticket delivery.
A store's support or engineering team can inspect the same investigation across
these records, ask a bounded question and preserve a supported defect as a
repeatable check. Each integration has a specific job in that workflow.

This build serves one registered workshop store and uses test payments.
Multi-tenant SaaS, production payments and general merchant onboarding are not
implemented. [Development status and release limits](archive/STATUS.md).

## What powers the product

| Technology | Customer task | Implementation and proof boundary |
| --- | --- | --- |
| **PayPal** | Establish whether the customer actually paid, then compare payment to delivery | Real Sandbox approval, capture and independent payment retrieval are implemented. Historical owned-store checks include a paid/zero-ticket failure and successful delivery. Authenticated notification delivery, exact-event resend and bad-signature rejection passed in the historical [CC-023 check](../evidence/runs/judge-ready/webhook-v55.json). A complete fresh repair journey remains open. |
| **AG Grid: AG Studio** | Inspect linked browser, payment, ticket, comparison and timeline records; ask questions over saved cases | Actual pinned Studio 3.0.0, five custom evidence panels, a registered Answers widget and native Agent Framework. Four historical private model-backed queries exist. The source includes a recorded explorer with explicitly local browser filters, not new model calls. It is not deployed or selected for the prize. AG Grid promises judging-period keys; delivered/configured coverage through 22 December remains pending. [Local setup and limits](studio.md). |
| **Bryntum Community Scheduler** | Compare delivery timing across investigations and open the original case | Actual MIT-licensed `@bryntum/scheduler-community` 8.0.0-beta.1 powers the separate read-only Delivery timing page. Projection tests and actual local SDK rendering, saved-case filtering and keyboard selection have been exercised. Full fresh/operator acceptance remains open. |
| **KERNEL** | Inspect a real browser checkout and its recording alongside payment and delivery | Actual owned sandbox sessions and correlated recordings were exercised historically; one complete recorded checkout delivered one ticket in 3.898776 seconds. Saved playback is distinct from a new checkout. The [observation-only operator runner](kernel-runner.md) now invokes the bounded adapter for an existing owned checkout. Remote usage needs an explicit bounded allowance; no live session is included in a source checkout. |
| **Modal + DeepSeek** | Propose evidence-grounded hypotheses and bounded investigations | The [8 November local flow](LIVE_FLOW.md) completed a fresh Sandbox checkout followed by three real model requests on that same case: read PayPal, read tickets, finish with citations. Deterministic code retained paid_without_ticket. Exact owned origins and the existing shared allowance were enforced. This is not hosted live access or a fresh repair pass. Historical copied-record tests remain separate. No maintainer keys or inference allowance are included. |
| **APIMatic Context Plugin** | Improve the development-time PayPal integration | Sponsor-linked API/SDK guidance and an offline serialization probe informed explicit credentials, journal-owned request IDs and deliberate retries. The runtime adapter is handwritten Python using PayPal REST APIs; it is not a PayPal SDK or an APIMatic-generated SDK. |
| **Postman** | Exercise the API and inspect linked records | An executable v2.1 collection supports local API checks. Historical execution included 48 assertions over saved actual sandbox records. Reading saved records is not a new PayPal request. No Postman cloud connection is needed for the local collection. |

The historical observations above are summaries from the maintainer's private
evidence archive. Raw payment/account receipts, licences, databases, recordings
and that acceptance archive are intentionally not published. The two curated
historical replay inputs are public: the earlier recording supports the same-input
failure/repair comparison, and the original late-read recording remains a negative
example. Current execution of those files can be reproduced with the README
commands. Historical integration summaries are not a claim of fresh provider
execution or a final release pass.
Local fixtures and model tests remain explicitly synthetic. Source publication,
a build or a sponsor logo does not establish runtime integration behavior.

## Keyless review versus the configured workspace

`./scripts/judge.sh` executes both recorded merchant variants when the local app
starts and serves their results through a separate read-only interface. It
imports no live adapter, starts no worker and does not load `.env`. The page
shows saved checkout, payment and store observations plus the locally recomputed
verdicts. It makes no PayPal, KERNEL or model call and does not use AG Studio or
Bryntum packages. Those SDKs remain substantive integrations in the separately
configured full workspace; the plain review UI is not presented as their output.

A static export performs the replay once during its build. A hosted visitor
inspects those results and can download the executable regression; browser
refresh does not run Python or create another payment. The historical original
fault video remains unavailable. Recorded source labels and hashes do not
independently authenticate a provider observation.

Modal hosts the owned model endpoint used in historical AI checks. It is **not**
one of the event's listed tool sponsors. No free model allowance or current
endpoint access is bundled with this public repository.

## Delivery timing with Bryntum

A support operator can scan saved checkouts against the same ticket deadline,
find a broken promise and open the investigation or AG Studio records. Each
eligible row starts at its own confirmed payment. The chart compares seconds
after payment; it does not present an invented calendar timestamp.

The immutable 60-second window and recorded ticket milestones cannot be dragged,
resized or edited. Promise kept, promise broken and needs-evidence labels come
from the matching saved server checker event. The client does not calculate a
replacement payment verdict. Unconfirmed payments, conflicting identities,
wrong amounts/currencies or inconsistent timestamps receive an explanation and
no timing anchor.

`/deadlines/index.html` uses the actual pinned Community Scheduler package and
same-version Core/Grid/Engine Community dependencies. Their installed licences
are MIT. This is a **beta SDK**, isolated from the core workspace entry. CSS,
Font Awesome code and fonts are bundled locally under the application's existing
self-only Content Security Policy. No Bryntum account, commercial evaluation or
licence key is needed for these Community packages.

The view performs authenticated same-origin GET reads of saved records, four
details at a time, with a 30-second load deadline. It shows up to 60 returned
investigations, including the selected case when available. Search, saved-result
filters and a 120-second or five-minute chart range are local display controls.
A table exposes the same cases and timing text; case details retain ticket times
outside the chart range. Refresh does not recheck PayPal or create a payment,
ticket, model request or recording.

The projection has 45 passing synthetic tests and was checked against two saved
paid/healthy records and the original saved paid/zero-ticket record. A real SDK
render with synthetic data established CSP feasibility after local Font Awesome
bundling removed an observed CDN fallback. Later local browser checks exercised filtering and keyboard case selection on
the public build. Those checks do not establish a complete fresh operator
journey or fresh sandbox execution.

Build and run instructions are in [workspace guide](WORKSPACE.md#delivery-timing).
Implementation: [build script](../studio/build.mjs),
[read-only controller](../studio/src/deadlines.ts) and
[validated projection](../studio/src/deadlines-model.ts).
The build copies the installed Bryntum MIT licence, third-party notices,
[Font Awesome licence](../studio/vendor/FONT-AWESOME-LICENSE.txt) and linked bundle
legal notices into the generated `web/deadlines/` assets. Preserve them with any
redistributed build. Compiled vendor bundles are not committed here. This
implementation does not itself establish prize eligibility.

## Additional sponsor fit

The official Resources readback on **3 November 2026** listed ten tool sponsors;
PayPal is the host and required core integration. The customer workflow guides
which additional technologies fit. The current implementation adds Bryntum;
four other optional tools remain unintegrated.

| Tool | Useful customer capability | Current decision |
| --- | --- | --- |
| [Zapier](https://paypalaihackathon.devpost.com/details/zapier) | After operator review, send a confirmed incident to a chosen support system and retain its external receipt | Not integrated. It needs an authorized account/destination and duplicate-safe delivery proof. No send button claims otherwise. |
| [Elastic](https://paypalaihackathon.devpost.com/details/elastic) | Search related incidents using complaint text and exact payment references | Not integrated. Existing local search serves the current record volume; a real service requires access filtering, synchronization/deletion and retrieval proof. |
| [Astropods](https://paypalaihackathon.devpost.com/details/astropods) | Operate a bounded investigator with real execution traces | Not integrated. A runtime migration adds deployment, credentials and cost boundaries while core live-proof gates remain open. |
| [Channel3](https://paypalaihackathon.devpost.com/details/channel3) | Discover and enrich products for shopping | Not integrated. Recommendations do not answer why the owned workshop purchase produced no ticket. |
| [Render](https://paypalaihackathon.devpost.com/details/render) | Hosting | Excluded from this project. |

APIMatic and Postman support integration quality. No new account, commercial
trial, external support handoff or paid provider execution was introduced by the
Bryntum feature. Sponsor use establishes neither a prize nor a submitted entry;
CC-060 remains the completion gate.

## Event resources

The product is for store teams; event eligibility and submission work stay
outside its interface. Official organizer guidance emphasizes a clear audience
and problem, an end-to-end PayPal and AI demonstration, runnable access or setup,
protected keys and a public video under three minutes. Source publication does
not supply a hosted product, video, new test payment or completed entry. Consult
the current event rules for eligibility and sponsor-prize conditions.

Official references: [rules](https://paypalaihackathon.devpost.com/rules),
[Resources](https://paypalaihackathon.devpost.com/resources),
[updates](https://paypalaihackathon.devpost.com/updates),
[AG Grid](https://paypalaihackathon.devpost.com/details/aggrid),
[APIMatic](https://paypalaihackathon.devpost.com/details/apimatic),
[Bryntum](https://paypalaihackathon.devpost.com/details/bryntum),
[KERNEL](https://paypalaihackathon.devpost.com/details/kernel) and
[Postman](https://paypalaihackathon.devpost.com/details/postman).

## Access and freeze — reviewed 8 November

Keep the demonstrated build and credentials/trials through the 21 December winner announcement, with a 22 December UTC buffer. Freeze submitted source, video and links after the deadline until then. Hosting is optional. The public video and submitted entry were verified on 10 November. The public walkthrough remains recorded; it is not a live PayPal/AI service. The private AG trial ends 17 December; the [6 November vendor announcement](https://www.ag-grid.com/blog/build-a-payments-dashboard-without-building-a-dashboard/) promises judging-period keys, with actual delivery and extended coverage still to confirm. [Current readiness and source](RULES_READINESS.md).
