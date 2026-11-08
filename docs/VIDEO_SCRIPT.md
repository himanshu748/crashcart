# CrashCart video — 2 minutes 55 seconds

**Owner recording plan, not a completed video.** Target 175 seconds: problem 15s, product demonstration 120s, PayPal implementation 30s, close 10s. Export below three minutes, watch the whole export and check its actual duration before uploading publicly to YouTube. The owner submits the final link.

## Prepare the real screens

- The public [CrashCart](https://himanshu748.github.io/crashcart/) currently serves an older build because GitHub Actions is billing-locked. Rehearse the latest labels below using `./scripts/judge.sh`, then confirm that same source is hosted before recording the public URL. AWS is not deployed.
- Open [the historical AI explanation](https://github.com/himanshu748/crashcart/blob/main/docs/AI_EVIDENCE.md) in a second tab, after this document is published. It describes a **different historical case** from the faulty checkout. Never imply that its model run investigated the public faulty replay.
- Have the [Sandbox recovery evidence](https://github.com/himanshu748/crashcart/blob/main/evidence/runs/judge-ready/recovery-v56.json) and [README integration table](https://github.com/himanshu748/crashcart#what-powers-crashcart) ready.
- Make the recorded-example labels and text legible. Hide notifications and unrelated tabs. Do not show credentials, account dashboards, private licences or `.env`. Use your own narration; no music or generated voice is required.

The hosted page is interactive, but its replay results were computed **during site build**. Clicking controls does not start a payment, AI call or Python replay. Local `sh scripts/judge.sh` recomputes both variants at startup. Describe these modes accurately.

## Shot list and narration

| Time | Shot and real action | Narration |
| --- | --- | --- |
| 0:00–0:15 · Problem | Landing headline and checkout illustration. | “A customer paid for a workshop ticket. The payment succeeded, but the ticket never arrived. Support sees a complaint; engineering sees a successful charge. CrashCart brings them to the same evidence.” |
| 0:15–0:33 · Product | Click **Payment**, **The gap** and **The repair**. Keep the recorded-example disclosure visible. | “The promise is one twenty-nine-dollar ticket within sixty seconds of payment. This hosted walkthrough uses saved Sandbox evidence and replay results computed when the site was built. I am interacting with the product; no new payment or AI call is happening.” |
| 0:33–0:53 | Choose **See a missing order**, then **Follow the missed order**. Show payment and missing-ticket facts. | “The faulty merchant loses the payment response. PayPal's record says payment completed, but the store has no ticket. CrashCart checks payment and delivery separately, so a successful charge cannot stand in for a fulfilled order.” |
| 0:53–1:13 | Filter to **PayPal**, then **Ticket store**. Expand an event and return to **All sources**. | “I can follow the evidence by source, open a record and compare its timing. The customer's page, the payment provider and the merchant can disagree. Keeping those observations separate makes the gap visible.” |
| 1:13–1:34 | Select **Repaired replay**. Show one ticket and delivery time; expand **Developer details**. | “The healthy merchant checks the payment independently and creates exactly one ticket. It passes in about thirty-two seconds, with the same recorded input and sixty-second deadline. An older late-delivery example still fails; the rule has not been loosened.” |
| 1:34–1:48 | Open **Can I run the example myself?**, then click **Download the runnable example** and show the completed download. Return to both outcome cards. | “The evidence can leave the dashboard as an executable replay. Run both merchants locally without an account or key. This is a repeatable comparison, not proof of a newly deployed repair.” |
| 1:48–2:10 · Recorded AI | Open **AI_EVIDENCE.md**, showing its table and exact model excerpt. Label: **Recorded AI investigation · 26 October · different historical case**. | “Here is a separate real AI investigation from October twenty-sixth. DeepSeek, hosted on Modal, requested an existing Sandbox payment, then matching ticket records before finishing. Its response says payment alone cannot establish delivery. The model chooses evidence; deterministic code makes the final decision.” |
| 2:10–2:15 | Return to the hosted comparison. | “The keyless walkthrough does not rerun that model.” |
| 2:15–2:45 · PayPal | Show README's PayPal role, then sanitized recovery evidence. Emphasize capture, independent read, one ticket and 4.067743s. | “PayPal is the payment source of truth. The full workspace creates and captures Sandbox orders, reads their state independently, and verifies payment notifications. In a separate real test, we stopped checkout after capture, before ticket creation. A restarted worker checked the same payment and delivered one ticket in about four seconds. That test validates recovery in our owned store, using Sandbox funds only.” |
| 2:45–2:55 · Close | End on the hosted page, with its URL and repository visible. | “CrashCart turns ‘I paid, but got nothing’ into evidence a team can inspect and a test it can rerun. Follow the payment. Check the promise.” |

## Before upload

1. Perform the actions in the actual published app. Fix or rerecord a failed control or download; do not splice in a fabricated success.
2. Keep historical AI, recorded replay and separate actual Sandbox recovery distinct. Do not narrate held-out discovery, a fresh repaired purchase or a complete live operator journey; those checks remain open.
3. Rehearse and shorten pauses rather than exceeding 175 seconds. Measure the exported file: script timings do not establish its actual duration.
4. Watch the complete export for legibility, truthful labels, audio and privacy. Add no unlicensed music or third-party material.
5. Upload to **YouTube, Public**, and test the watch link while signed out. Paste the real URL into Devpost. No video URL exists yet; this script does not satisfy that requirement.

Sources: [requirements](https://paypalaihackathon.devpost.com/) and [rules](https://paypalaihackathon.devpost.com/rules), reviewed 4 November 2026. The organizer's 2 November guidance asks entrants to show PayPal and AI working. This script labels historical evidence; it does not promise an eligibility determination.
