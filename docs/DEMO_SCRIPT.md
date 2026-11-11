# CrashCart demo — 2 minutes 40 seconds

**Historical preparation document.** For the current public links and submitted video, use [the README](../README.md), [hosting guide](HOSTING.md) and [video check](VIDEO_CHECK.md). Dated checks and unresolved historical findings below retain their original scope.

A recording plan for the owner. This is a script, not an exported video or
CC-059 evidence. Record the current build only after its browser checks pass.
Use your own narration; no generated voice or music is required.

## Before recording

The redesigned local build passes its full suite and isolated Linux checks.
The hosted frontend still serves the earlier build. To use the current local build, run `./scripts/judge.sh --no-open` with
Python 3.13.15 and open `http://127.0.0.1:8766/`. Use a clean browser window
containing only this recorded example, starting at its product landing page. Increase the browser's text size if needed. Keep the
“Recorded example · no new payment” disclosure visible and show the real interactions below.
Do not expose `.env`, developer dashboards, buyer credentials or private licences.

This sequence demonstrates an executed recorded comparison. It does not show a
new AI investigation or fresh payment. The missing original faulty-checkout
video must not be substituted with newly acted footage. The full CC-059 contract
still needs the original and fresh journey described in [open checks](OPEN_CHECKS.md).

## Shot list and narration

| Time | Screen and action | Narration |
| --- | --- | --- |
| 0:00–0:15 | Landing: “The customer paid. So where’s their ticket?” Show the record-connection illustration. | “A customer paid for a workshop ticket. The payment succeeded, but the ticket never arrived. CrashCart helps a store team find where that promise broke.” |
| 0:15–0:30 | Select **1. The payment**, **2. The delivery**, then **3. The repair**. Keep the replay disclosure in frame. | “The promise is specific: one twenty-nine-dollar ticket within sixty seconds of confirmed payment. This demonstration replays historical PayPal test records. No new payment or AI call is happening.” |
| 0:30–0:50 | Choose **Follow a recorded case**, then **Walk through the recorded case**, and frame the comparison just above it. Frame both outcome cards. | “Here is one recorded checkout, run through two merchant versions. The faulty version loses the payment response and leaves the customer with no ticket. The healthy version checks the payment independently and delivers one.” |
| 0:50–1:15 | Select **Missed order**. Show checkout, payment and ticket facts; expand one relevant event. | “A successful payment screen alone cannot prove delivery. CrashCart keeps the customer's page observation, PayPal's payment record and the store's ticket state together. Deterministic rules decide whether the promise was kept.” |
| 1:15–1:35 | Filter to **PayPal**, then **Ticket store**; return to **Everything**. | “The timeline lets a support or engineering team trace the evidence by source. These are saved observations with their original timing, not invented live activity.” |
| 1:35–1:55 | Select **Recovered order (replay)**. Show the one-ticket result and delivery time. Expand **Result details**. | “The repaired comparison uses the same input and the same sixty-second deadline. We change the merchant behavior, not the expected answer. A separate late-read example still fails, so a late ticket cannot be disguised as a recovery.” |
| 1:55–2:15 | **Replay test you can run on your computer, with no payment**. In a terminal run the archive's defective and healthy commands; frame their verdict/signature output. | “The finding travels with an executable replay. The defective merchant fails with a paid-without-ticket result. The healthy merchant passes. Anyone can rerun both locally without an account, key or licence.” |
| 2:15–2:30 | Return to the page and show its limitations; briefly show README's integration table. | “The full workspace adds AG Studio records, Bryntum timing, KERNEL browser evidence and bounded model investigations through Modal. Those integrations have separate access and verification boundaries; this keyless review claims only recorded replay.” |
| 2:30–2:40 | End on both outcome cards and repository URL. | “CrashCart turns a vague ‘I paid, but got nothing’ complaint into inspectable evidence and a repeatable test. Follow the payment. Check the promise.” |

## Recording checklist

- Target **160 seconds**, leaving 20 seconds below the three-minute limit.
- Show actual running controls and terminal output. Do not replace failures with
  edited success cards or narrate an original recording that does not exist.
- Use the README's exact commands. The defective command intentionally exits 1;
  this is the expected reproduced failure, not a demo crash.
- A hosted review displays results computed at site-build time. Say so if using
  it; use the local command/terminal for actual re-execution during the video.
- Watch the exported video, measure its actual duration and inspect every visible
  frame for secrets before uploading. The script's timings do not establish the
  exported video's length.
- The official submission calls for a public YouTube link. The owner still needs
  to record, upload and provide that link; do not submit from this script.

Event requirements: [official rules](https://paypalaihackathon.devpost.com/rules),
checked 4 November 2026. [Submission draft](SUBMISSION.md).
