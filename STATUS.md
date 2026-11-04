# CrashCart development status

**Verified: 45/60. Zero stale requirements on the frozen accepted build. Project incomplete.** Updated 4 November 2026 (India).

## Current delivery

The public build now includes an interactive product landing page and a keyless recorded investigation. Run `sh scripts/judge.sh`: it recomputes the defective and healthy outcomes, opens the finished investigation, and provides source records and an executable replay. No PayPal, AG Studio, KERNEL or model key is needed for this path.

The curated early-read recording produces **FAIL / paid_without_ticket** for the faulty store and **PASS / ticket_delivered_once_on_time** for the healthy store at +32.261423 seconds. The original late recording remains unchanged and still fails correctly. No invariant, deadline or historical failure was relaxed.

The existing live workspace and sponsor integrations remain separate and require their own configuration, licences and permitted service use. The keyless page does not execute an AI investigation or a fresh payment. Hosted output is computed during site build, local output at app launch.

## Verification

Latest local suite on Python 3.13.15: **367 tests in 115.397s, OK**. Replay suite: **3 tests in 0.858s, OK**. An initial attempt accidentally used unsupported Python 3.9 and failed; its output is retained. No source or assertion was changed for the corrected run. Timing tests: **45 pass, 0 fail**. Build/typecheck, syntax, compilation and clean foundation checks passed. Actual browser checks covered desktop, 390px/320px, keyboard, filtering, details, downloads and reduced-motion override. Independent review passed after fixing the ZIP licence notice. See [exact commands and evidence](docs/JUDGE_VERIFICATION.md).

Current Postman execution passed seven local assertions and 48 assertions against copied historical Sandbox observations (six GETs); missing proof still fails. No new provider call was made. CC-050 remains open through CC-035.

Newly verified: **CC-023**, from actual PayPal Sandbox ingress and independent review. Authentic first delivery and exact-event resend both verified; the controlled invalid-signature probe was rejected without changing counts. One capture operation, one event and the expected zero tickets for the intentionally defective store remained. The private archive now records 45/60; additive keyless code is separately tested and does not inherit live-provider acceptance. Frozen live runtime and prior acceptance source remain unchanged. Historical CC-037 document review and CC-039 synthetic control proof retain their original scope and dates.

## Open acceptance

- Failed: **CC-035**.
- Blocked: **CC-024, CC-036, CC-038, CC-041, CC-052, CC-056, CC-060**.
- Implemented but unverified: **CC-046, CC-048, CC-050, CC-057**.
- In progress: **CC-040, CC-042**. Pending: **CC-059**. Stale: **none** on the frozen build.

[OPEN_CHECKS.md](docs/OPEN_CHECKS.md) records each exact missing result and dependency. Main gaps: current-source healthy process recovery, original fault recording, held-out discovery, fresh repaired purchase, full operator journey and actual public video. All eight old remote-browser grants are consumed. AWS infrastructure under $10/month is now permitted; this does not renew model or browser test usage. No AWS resources or spending were needed for this batch. Render remains excluded.

Part F is not started because Part A cannot pass yet. No prize-lane feature is used to bypass that prerequisite.

## Hosting and submission

The [recorded walkthrough is published on GitHub Pages](https://himanshu748.github.io/crashcart/). [Source CI](https://github.com/himanshu748/crashcart/actions/runs/41802366607) and [deployment](https://github.com/himanshu748/crashcart/actions/runs/41802528629) passed on `ba7ac9c`. Hosted landing, walkthrough, case selection, PayPal filter and 390px layout were exercised. A subsequent native Safari check downloaded both JSON and executable ZIP successfully after allowing this site’s downloads. Their hashes matched the HTTPS artifacts; the ZIP manifest and both replay outcomes passed. The two earlier task-browser timeouts remain recorded separately. This hosts the recorded demonstration, not the live backend. [Hosting details](docs/HOSTING.md).

MIT is present in LICENSE and detected by GitHub. [README](README.md) includes the 60-second path and private Sandbox buyer placeholders. [Demo script](docs/DEMO_SCRIPT.md) is 160 seconds; the owner still needs to record it. [Submission draft](docs/SUBMISSION.md) is prepared and qualified by actual evidence. No final Devpost submission was made; the existing entry remains a draft.

The AG Studio trial is already privately configured and valid through 17 December 2026. No replacement licence is needed. KERNEL has not yet answered the absolute lifetime/billing-bound question. Continuation is authorized, but it does not resolve that technical limit.

The local Safari test completed one USD29 Sandbox payment and authentic notification verification. The exact temporary webhook was deleted and confirmed absent; gateway, worker and tunnel exited in 211.213 seconds, inside the 30-minute window. No KERNEL session, model call or paid service was used. The earlier signed-JSON failure remains preserved. [Sanitized live evidence](evidence/runs/judge-ready/webhook-v55.json).

Next: prepare and independently review a current-source LIVE_SANDBOX healthy process-interruption test for CC-024, then bind a separate one-checkout execution scope. Its historical FRESH_SANDBOX proof used older service/store/PayPal source and cannot be relabelled or promoted. CC-052 remains blocked by CC-024. Safari sign-in is now working; the completed notification window is closed. Declare completion only after **CC-060** passes.
