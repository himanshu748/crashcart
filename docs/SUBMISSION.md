# CrashCart — Devpost draft

Prepared for the PayPal AI Hackathon. **Draft only: the owner submits.**
Features are frozen. The current submission scope is a working recorded
demonstration with honest historical integration evidence, not completion of
every original development check. [STATUS.md](../STATUS.md) separates submission
gates from deferred checks; unverified requirements remain unchecked.

[DEVPOST.md](DEVPOST.md) contains the paste-ready fields and working try-it links.
[VIDEO_SCRIPT.md](VIDEO_SCRIPT.md) is the current 175-second recording plan.
The owner must still record, upload and verify the actual public YouTube video.
A recorded repair comparison does not establish full acceptance or a fresh
repaired payment. AWS remains a plan, not a deployed service.

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

In a separate historical real AI investigation, DeepSeek requested an existing
PayPal Sandbox payment and then matching ticket records before finishing.
The [sanitized trace and model excerpt](AI_EVIDENCE.md) show observation-dependent
reasoning. That historical healthy case is different from the public faulty
replay; its model calls are not rerun by the keyless page.

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

Authentic Sandbox webhook delivery and exact-event resend now pass signature
verification, while an invalid-signature probe is rejected without state changes.
We also tested the moment a store can lose its place: immediately after a real
$29 Sandbox payment, before creating the ticket. After the checkout process
stopped, a restarted worker checked the payment independently and delivered one
ticket in 4.07 seconds from capture. It used the same order and operation identities;
the customer's 60-second promise never changed. The complete freshly recorded
repair journey remains open and is tracked separately.

## Accomplishments

- A finished, keyless recorded investigation that a reader can run locally and
  understand without setting up payment, model or browser-service accounts.
- One unchanged input that fails the faulty merchant and passes the healthy
  merchant, with an executable regression test for both outcomes.
- The original late-read failure preserved as a separate negative test.
- Recovery after an actual PayPal Sandbox payment and a process interruption:
  one ticket delivered in 4.07 seconds, without creating another payment operation.
- Competing-worker and restart checks that retain one ticket through a worker
  kill and lease expiry. These local tests use synthetic provider replies and
  complement the separate actual Sandbox recovery.
- A product workflow that connects customer, payment and delivery evidence while
  keeping automatic payment verdicts outside model-generated prose.

These are implementation and scoped verification results, not claims of
production readiness, customer adoption, full acceptance or a deployed repair.

## What's next

Record the working product and its clearly labelled historical AI evidence,
then provide the public video and complete the owner's submission. Features
remain frozen. Future validation includes the complete fresh investigation and
repair journey; held-out discovery and full operator acceptance remain open.
Broader merchant onboarding, team access and support-system handoff are future
work, not capabilities of this single-store prototype.

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
| Best Use of PayPal + AI | Payment state is central to every verdict; [historical real AI evidence](AI_EVIDENCE.md) shows the model selecting a real existing-order read and then matching merchant evidence. | Different historical case from the faulty replay; no new checkout during that investigation. The keyless review does not run AI. Private artifact hashes are provenance bindings, not independently accessible provider receipts. |
| Most Impactful | A specific support problem—paid but no ticket—becomes an inspectable failure and repair comparison; `tests/test_public_replay.py` exercises both outcomes with the same promise. | No customer validation, adoption or measured support-time reduction is claimed. |
| AG Grid — not claimed by this submission scope | `studio/src/` implements actual AG Studio evidence widgets and saved-record queries in the full workspace. | The keyless review does not load AG Studio; complete operator proof remains unverified. |
| Bryntum — not claimed by this submission scope | `studio/src/deadlines.ts` uses the Community Scheduler and `deadlines-model.ts` validates payment-relative timing. | The keyless review is not the Bryntum view; this scope does not present its full-workspace journey as verified. |

## Testing instructions and links

- [Public repository](https://github.com/himanshu748/crashcart)
- [Current runnable build and setup](https://github.com/himanshu748/crashcart#run-it-locally)
- [Older hosted recorded preview](https://himanshu748.github.io/crashcart/)
- [Keyless setup and 60-second path](../README.md#try-the-product-in-60-seconds)
- [Recorded replay commands](../README.md#reproduce-the-comparison)
- [Optional test-buyer path](../README.md#optional-sandbox-test-buyer-path)
- [Exact open checks](OPEN_CHECKS.md)
- [Current video shot list](VIDEO_SCRIPT.md) — the public YouTube URL is still missing.
- [Paste-ready Devpost fields](DEVPOST.md)
- [Historical PayPal-plus-AI explanation](AI_EVIDENCE.md)
- [Existing Devpost project page](https://devpost.com/software/crashcart-87asqz)

The GitHub Pages URL above is the older hosted preview. The current runnable
build is linked separately. Do not advertise an AWS URL until that deployment
and its downloads have been verified.
The hosted review displays build-time replay results; the local command executes
the replay. Neither is a hosted live-payment backend.
Keep access free through the 21 December winner announcement and retain the runnable source.
Do not publish real test-buyer or service credentials with the source.

The owner must watch the exported video, verify a duration under three minutes,
upload it publicly to YouTube and test signed-out access before adding the link
to Devpost. The official guidance emphasizes showing PayPal and AI working;
label the recorded AI segment as historical and distinct from the replay. The
organizers decide whether the finished entry satisfies their requirements.

Official dates checked on 4 November 2026: submissions close **13 November 2026,
01:30 IST** (12 November, noon Pacific). Judging ends **15 December 2026,
21:30 IST** (08:00 Pacific). Use the [official rules](https://paypalaihackathon.devpost.com/rules)
and [event page](https://paypalaihackathon.devpost.com/) if organizer guidance changes.

## Access and freeze — reviewed 8 November

Keep the demonstrated build and credentials/trials through the 21 December winner announcement, with a 22 December UTC buffer. Freeze submitted source, video and links after the deadline until then. Hosting is optional. The required public video and complete PayPal-plus-AI access remain open; the private AG trial ends 17 December. [Current readiness and source](RULES_READINESS.md).
