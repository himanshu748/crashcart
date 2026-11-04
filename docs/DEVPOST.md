# CrashCart — paste-ready Devpost copy

Draft for the owner. **Do not submit automatically.** The required public YouTube video still awaits recording and upload. AWS is planned, not deployed. The sections below distinguish the working recorded demonstration from separately exercised integrations.

## Project name

CrashCart

## Tagline

Find where a successful payment becomes a broken promise.

## Inspiration

“I paid, but my ticket never arrived” is one incident with three perspectives: what the customer saw, what the payment provider confirmed, and what the store delivered. A successful charge answers only the second question.

CrashCart starts with a concrete customer promise and brings those perspectives together. The aim is to give support and engineering the same inspectable evidence, then turn the failure into a test they can rerun against a repaired merchant.

## What it does

CrashCart investigates an owned workshop checkout with a simple promise: one $29 ticket within 60 seconds of completed payment. It correlates checkout observations, PayPal payment state and ticket records, then uses deterministic rules to decide whether that promise was kept.

The public walkthrough opens a finished investigation without accounts, keys or licences. Inspect the faulty checkout: payment completed, but the ticket is missing. Switch to the healthy merchant: the same historical input produces one ticket within the unchanged deadline. Filter the timeline by source, open individual records and download an executable replay.

The hosted walkthrough displays replay results computed when the site was built. Running the keyless app locally recomputes both merchant outcomes. Neither path creates a new payment or calls an AI model.

The separately configured workspace uses AI to choose what evidence to inspect next. In a historical real DeepSeek investigation, the model requested an existing PayPal Sandbox payment, then matching merchant ticket records before finishing. It cited those observations; deterministic code made the final decision. That recorded AI investigation is a different case from the faulty checkout in the public walkthrough.

## How we built it

Python and SQLite hold purchases, payment-operation identities, observations, tickets and resumable jobs. A worker can recover interrupted fulfillment without treating a lost response as a failed payment. The PayPal Sandbox integration creates and captures orders, retrieves payment state independently and verifies payment notifications.

The AI investigator uses structured, bounded tool calls. Actual historical investigations used DeepSeek-V4.1-Flash served through Modal. The model proposes hypotheses and selects observations; it cannot replace fixed payment and delivery rules with its own verdict.

The replay engine runs the merchant's confirmation and fulfillment code against preserved input and a recorded clock. Faulty and healthy variants share the same promise. A separate late-delivery case remains a failure, protecting the 60-second deadline.

The full workspace also integrates AG Studio for linked evidence widgets and questions over saved cases, Bryntum Community Scheduler for delivery timing, KERNEL for remote checkout browser sessions and recordings, and Postman for executable API checks. These tools have separate configuration and verification boundaries; they are not loaded by the keyless walkthrough. Modal supplies model hosting and is not an event tool sponsor.

## Challenges we ran into

The hardest boundary was between a payment completing and the merchant knowing it completed. A response can disappear while the payment remains valid. Recovery must check the existing operation and deliver exactly once, rather than create a second charge or ticket.

Timing exposed an important mistake: an earlier healthy replay delivered after the deadline. We preserved that failure and added a separately recorded earlier observation for the comparison. The same unchanged rule accepts timely delivery and rejects the original late case.

AI needed an equally clear boundary. In a controlled historical experiment, removing the provider observation made payment and capture timing uncertain. The model preserved that uncertainty, and the deterministic result stayed inconclusive. Missing evidence was not permission to invent a successful payment.

## Accomplishments that we're proud of

The central failure is understandable without installing a payment SDK or sharing credentials: one recorded checkout, two merchant outcomes, and evidence the reader can inspect and rerun.

Separate real Sandbox tests verified authentic payment notifications and exact-event resend, and rejected an invalid signature without changing state. Another test stopped checkout after capture, before ticket creation; a restarted worker checked the same payment and delivered exactly one ticket in 4.07 seconds. These are specific, retained test results—not a claim that every workflow or production failure is solved.

## What we learned

A payment result, a page message and a delivered ticket are different facts. Keeping them separate makes recovery easier to reason about. We also learned to preserve a failed test when it exposes a timing problem: changing the deadline would hide the problem rather than fix the product.

AI is useful here when it asks for the next relevant observation and explains what remains unknown. The final financial and entitlement decision belongs to deterministic code.

## What's next

Broaden the evidence model beyond workshop tickets, test the workflow with merchant support teams, and improve handoff into their existing incident tools. The next validation work is the complete fresh investigation and repair journey; held-out discovery and the full operator workflow remain open. Features are frozen for this submission. The prototype does not claim production readiness or measured customer impact.

## Built with

Python, SQLite, JavaScript, TypeScript, PayPal Sandbox, AG Studio, Bryntum Community Scheduler, KERNEL, Modal, DeepSeek, Postman, Newman, unittest.

## Try-it links

- Interactive recorded walkthrough: https://himanshu748.github.io/crashcart/
- Public source and setup: https://github.com/himanshu748/crashcart
- Historical AI evidence: https://github.com/himanshu748/crashcart/blob/main/docs/AI_EVIDENCE.md
- Optional Sandbox instructions: https://github.com/himanshu748/crashcart#optional-sandbox-test-buyer-path

## Video URL — owner action required

**Awaiting the owner's actual public YouTube watch URL.** Record the [175-second script](VIDEO_SCRIPT.md), inspect the export and verify signed-out access. Do not paste this placeholder into the video field or submit without the required video.

## Prize selection notes — not part of the project story

- **Best Use of PayPal + AI:** target. PayPal supplies payment evidence; the [historical real model trace](AI_EVIDENCE.md) shows observation-dependent tool selection in the same investigation workflow. The keyless walkthrough makes no AI calls.
- **Most Impactful:** target. The [public replay tests](../tests/test_public_replay.py) demonstrate a concrete paid-without-ticket problem and timely healthy comparison. No adoption, support-time saving or commercial impact has been measured.
- **AG Grid / Bryntum lanes:** do not present the keyless demo as proof of these optional full-workspace experiences. Their complete operator journey remains unverified; this submission scope adds no sponsor features to claim those lanes.

The organizers determine eligibility. Video, repository and final form must agree with these claims. Submission deadline: **13 November 2026, 01:30 IST**. Judging ends **15 December 2026, 21:30 IST**. Sources: [event](https://paypalaihackathon.devpost.com/) and [rules](https://paypalaihackathon.devpost.com/rules), checked 4 November 2026.
