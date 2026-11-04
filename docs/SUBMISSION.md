# CrashCart — Devpost draft

Prepared for the PayPal AI Hackathon. **Draft only: do not submit.**
The owner still needs to record/upload the video and resolve the live-evidence
and access gaps in [OPEN_CHECKS.md](OPEN_CHECKS.md). A recorded repair comparison
is not a claim that every acceptance check or the final release gate has passed.

## Tagline

Find where a successful payment becomes a broken promise.

## Inspiration

“I paid, but my ticket never arrived” sits between three views of a purchase:
what the customer saw, what the payment provider confirmed, and what the store
actually delivered. A successful capture answers only one of those questions.
CrashCart starts with the customer's promise and brings the evidence together
so support and engineering can investigate the same incident.

## What it does

CrashCart follows an owned workshop checkout from payment to ticket delivery.
The promise is deliberately concrete: one $29 ticket within 60 seconds of
confirmed payment. It compares the checkout observation, independently recorded
PayPal state and the store's ticket record, then preserves the finding as an
executable replay.

The keyless review opens a finished investigation with two outcomes. The faulty
merchant leaves a confirmed payment without a ticket. The healthy merchant
rechecks payment and creates exactly one ticket within the unchanged deadline.
Both outcomes are re-executed from the same historical input when the local app
starts. Readers can inspect the timeline, filter by source and download the
records or replay. No account, API key or commercial licence is needed for that
recorded path.

The full workspace also supports authorized test checkouts, linked AG Studio
records, a Bryntum delivery-timing view and bounded AI investigations. The AI
proposes hypotheses and tests; deterministic code decides payment and ticket
verdicts. These live integrations are distinct from the keyless review, which
makes no fresh payment, remote-browser or AI request.

## How it's built

A Python backend and worker use SQLite to keep purchases, immutable operation
identities, observations, tickets and resumable jobs together. The PayPal Sandbox
adapter creates and captures owned-store orders and retrieves payment state
independently. An explicit fault harness models a lost response or interrupted
merchant without describing it as a PayPal vulnerability.

The replay engine executes the merchant's actual confirmation and fulfillment
rules in a new local namespace. It retains the original input, clock and promise;
saved verdict labels are not inputs. The public examples include both a timely
healthy recovery and an older late-read case that correctly remains a failure.

AG Studio supplies the full workspace's linked evidence widgets and saved-record
query surface. Bryntum Community Scheduler plots ticket timing against the fixed
delivery window. KERNEL supplies remote browser sessions and recordings for
configured experiments. Historical AI calls used an owned Modal-hosted DeepSeek
endpoint. Postman's exported collection checks the API and correlated records.
The keyless review is a separate, read-only Python and browser entry point that
needs none of those external accounts or SDK licences.

## Challenges

The difficult part was keeping payment truth separate from the customer's page
and the merchant's local assumptions. Losing a response does not mean losing the
payment, and retrying an operation must not create another entitlement. Durable
request identities, independent payment reads and one-ticket fulfillment make
those boundaries explicit.

Evidence timing mattered just as much. An earlier public replay delivered a
healthy ticket too late. We kept that failure and its timestamps intact, then
added a separately recorded earlier observation for the meaningful repair
comparison. The same rule rejects late delivery and accepts timely delivery.

Real-provider proof also has limits: authentic webhook verification and the
complete freshly recorded repair journey remain open. We expose those gaps
rather than treating a local test or attractive screenshot as a live pass.

## Accomplishments

- A finished, keyless recorded investigation that a reader can run locally and
  understand without setting up payment, model or browser-service accounts.
- One unchanged input that fails the faulty merchant and passes the healthy
  merchant, with an executable regression test for both outcomes.
- The original late-read failure preserved as a separate negative test.
- Durable local concurrency and restart checks that retain exactly one ticket;
  their synthetic provider responses are explicitly distinguished from actual
  payment recovery.
- A product workflow that connects customer, payment and delivery evidence while
  keeping automatic payment verdicts outside model-generated prose.

These are implementation and scoped verification results, not claims of
production readiness, customer adoption, full acceptance or a deployed repair.

## What's next

Complete authentic notification verification and the original/fresh checkout
recordings; finish the operator acceptance journey and public video. After those
gates pass, evaluate a narrowly scoped sponsor-powered improvement. Broader
merchant onboarding, team access and support-system handoff are future work,
not capabilities of this single-store prototype.

## Built with

Python, SQLite, JavaScript, TypeScript, PayPal Sandbox, AG Studio, Bryntum
Community Scheduler, KERNEL, Modal, DeepSeek, Postman/Newman and unittest.
APIMatic Context Plugin informed development-time API integration; the runtime
adapter is handwritten Python. Modal is the model hosting provider, not a listed
hackathon tool sponsor. The recorded review itself uses Python's standard
library and browser HTML/CSS/JavaScript.

## Prize lanes and supporting evidence

These are target lanes, not eligibility determinations or prize claims. The
current official criteria cover technological implementation, design, potential
impact, innovation and presentation. The organizers determine eligibility.

| Target lane | Product reason and one line of evidence | Remaining boundary |
| --- | --- | --- |
| Best Use of PayPal + AI | Payment state is central to every verdict; `crashcart/paypal.py` and `crashcart/investigator.py` separate provider observations from model hypotheses, and the public replay executes the payment-to-ticket comparison. | Historical model evidence is private; the keyless review does not run AI, and complete fresh discovery/repair proof remains open. |
| Most Impactful | A specific support problem—paid but no ticket—becomes an inspectable failure and repair comparison; `tests/test_public_replay.py` exercises both outcomes with the same promise. | No customer validation, adoption or measured support-time reduction is claimed. |
| Best Use of AG Grid | `studio/src/` implements actual AG Studio evidence widgets and saved-record queries in the full workspace. | The keyless review does not load AG Studio. Applicable licensed judge access and the complete operator proof remain separate; do not claim this lane solely from the keyless page. |
| Best Use of Bryntum | `studio/src/deadlines.ts` uses the actual Community Scheduler and `deadlines-model.ts` validates payment-relative timing; the timing suite exercises the projection. | The keyless review is not the Bryntum view. Record and verify the configured full-workspace interaction before presenting it as a demonstrated sponsor lane. |

## Testing instructions and links

- [Public repository](https://github.com/himanshu748/crashcart)
- [Keyless setup and 60-second path](../README.md#try-the-product-in-60-seconds)
- [Recorded replay commands](../README.md#reproduce-the-comparison)
- [Optional test-buyer path](../README.md#optional-sandbox-test-buyer-path)
- [Exact open checks](OPEN_CHECKS.md)
- [Video shot list](DEMO_SCRIPT.md) — the public video URL is still missing.
- [Existing Devpost project page](https://devpost.com/software/crashcart-87asqz)

Do not paste a hosted URL until its actual published page and downloads have
been read back. A static hosted review displays build-time replay results; the
local command executes the replay. Neither is a hosted live-payment backend.
Keep judge access free through the end of judging and retain the runnable source.
Do not publish real test-buyer or service credentials with the source.

Official dates checked on 4 November 2026: submissions close **13 November 2026,
01:30 IST** (12 November, noon Pacific). Judging ends **15 December 2026,
21:30 IST** (08:00 Pacific). Use the [official rules](https://paypalaihackathon.devpost.com/rules)
and [event page](https://paypalaihackathon.devpost.com/) if organizer guidance changes.
