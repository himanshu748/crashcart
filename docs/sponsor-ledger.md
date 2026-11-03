# CrashCart integrations

CrashCart follows a purchase from browser checkout to payment to ticket delivery.
A store's support or engineering team can inspect the same investigation across
these records, ask a bounded question and preserve a supported defect as a
repeatable check. Each integration has a specific job in that workflow.

This build serves one registered workshop store and uses test payments.
Multi-tenant SaaS, production payments and general merchant onboarding are not
implemented. [Development status and release limits](../STATUS.md).

## What powers the product

| Technology | Customer task | Implementation and proof boundary |
| --- | --- | --- |
| **PayPal** | Establish whether the customer actually paid, then compare payment to delivery | Real Sandbox approval, capture and independent payment retrieval are implemented. Historical owned-store checks include a paid/zero-ticket failure and successful delivery. Authentic notification delivery/resend/signature checks and a complete fresh repair journey remain open. |
| **AG Grid: AG Studio** | Inspect linked browser, payment, ticket, comparison and timeline records; ask questions over saved cases | Actual pinned Studio 3.0.0, five registered widgets and four historical model-backed queries over changing saved data. A vendor trial was exercised privately; the source checkout includes no licence value or permission to use that private trial. Configure your own entitlement where required. Delivered licensed access and the full operator journey remain open. |
| **Bryntum Community Scheduler** | Compare delivery timing across investigations and open the original case | Actual MIT-licensed `@bryntum/scheduler-community` 8.0.0-beta.1 powers the separate read-only Delivery timing page. Model checks and an SDK/CSP feasibility render have run. Final source-bound browser verification and acceptance review are pending. |
| **KERNEL** | Inspect a real browser checkout and its recording alongside payment and delivery | Actual owned sandbox sessions and correlated recordings were exercised historically; one complete recorded checkout delivered one ticket in 3.898776 seconds. Saved playback is distinct from a new checkout. Remote usage needs a new explicit bounded allowance; no live session is included in a source checkout. |
| **Modal + DeepSeek** | Propose evidence-grounded hypotheses and bounded investigations | Actual historical model calls queried copied saved records. Deterministic code, rather than model prose, decides payment and ticket outcomes. The public Modal origin is a nonworking placeholder requiring a reviewed owned-origin source change; OpenAI supports your own key/model. No maintainer credentials or inference allowance are included. |
| **APIMatic Context Plugin** | Improve the development-time PayPal integration | Sponsor-linked API/SDK guidance and an offline serialization probe informed explicit credentials, journal-owned request IDs and deliberate retries. The runtime adapter is handwritten Python; it is not an APIMatic-generated SDK. |
| **Postman** | Exercise the API and inspect linked records | An executable v2.1 collection supports local API checks. Historical execution included 48 assertions over saved actual sandbox records. Reading saved records is not a new PayPal request. No Postman cloud connection is needed for the local collection. |

The historical observations above are summaries from the maintainer's private
evidence archive. Raw payment/account receipts, licences, databases, recordings
and that acceptance archive are intentionally not published. The one curated
historical replay input included for offline source tests is labelled separately. They are not links
to public proof, a claim of fresh provider execution or a final release pass.
Local fixtures and model tests remain explicitly synthetic. Source publication,
a build or a sponsor logo does not establish runtime integration behavior.

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
bundling removed an observed CDN fallback. These checks do not establish final
keyboard/responsive behavior or fresh sandbox execution; final browser and
acceptance verification are still pending.

Build and run instructions are in [README](../README.md#delivery-timing).
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
