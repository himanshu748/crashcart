# Remaining 13 checks — verification results

**6 November design amendment:** current CC wording is in [BUILD_CHECKLIST](../BUILD_CHECKLIST.md) and the [decision map](DESIGN_CONTRACT_UPDATE.md). CC-046/048/056/059 have additive design acceptance; all 13 open states remain open. Dated attempts and next actions below are historical, superseded by the top of STATUS.md. No prior capture grant is renewed.

5 November 2026. **47/60 verified; no new CC checkmarks.** The owner resumed verification of all open checks. Features remain frozen. The v65 pass executed available offline checks, inspected original evidence and dependencies, and repaired inactive recording preparation. No payment, public test window, recording, model call or remote browser session occurred.

## Capture follow-through — v66

The separately approved ten-second native capture probe passed with 115 frames / 7.691667 seconds, no audio, clean decoding and finalization within the ten-second process budget. The failed five-second readiness probe remains preserved. Start/end frames were independently inspected. Both grants are consumed; the private videos were not uploaded. [Sanitized receipt](../evidence/runs/submission-ready/capture-v66.json).

This established short-capture behavior for the then-frozen recorder only. CC-035 still needs an actual recorded faulty checkout. Nine offline guards passed, Developer access and existing Sandbox buyer authentication were observed, and a unique preparation window was identified. The reviewed proposal subsequently received approval for the single attempt below. Any repaired recorder requires new actual-capture verification; the prior short pass does not transfer to changed code.

## Recorded-checkout attempt — v66 failure

After a separate scoped approval, the attempt stopped before checkout with `RECORDER_HEARTBEAT_STALE` in 53.639 seconds. All four owned child processes were confirmed absent; no order, capture or merchant operation exists. The private partial video has 710 frames / 51.525 seconds and no audio, but 26 decode timestamp warnings. It is not checkout proof. The encoder counter lagged final media and cannot establish whether real frame delivery stalled. An offline repair now uses valid advancing captured-frame callbacks and passes ten focused tests plus compilation; the five-second freshness guard remains unchanged. At this v66 checkpoint actual capture with the new binary was unverified; the later v68 probe and v69 failure below supersede that checkpoint. The one-attempt grant is consumed; further capture/payment needs applicable authorization.

## What actually ran — v65

| Verification | Observed result | Acceptance limit |
| --- | --- | --- |
| Public source `d13b37d`, `python3 -m unittest discover -v` | 367 tests in 70.969s, OK | Offline suite; does not accept missing integrations. |
| `python3 -m unittest tests.test_public_replay -v` | 3 tests in 0.285s, OK | Timely healthy passes; defective and original late healthy still fail. |
| Existing regression ZIP, extracted to a new directory with network-disabled child processes | Manifest passes; defective exits 1 / `paid_without_ticket`; healthy exits 0 / `ticket_delivered_once_on_time` | Matching original faulty-checkout recording remains missing. |
| Actual Newman collection against disposable local API | 7 smoke assertions passed; missing-proof case exits 1 with 14 assertion failures as expected | No provider call. |
| Same collection against copies of historical Sandbox cases | 48 assertions across six GETs passed; original files and copied rows unchanged | Stored observations, not new payment/provider reads. |
| Read-only held-out preflight | Exit 2 / `BLOCKED_MISSING_ACTUAL_TRIAL_INPUTS`; 24 frozen runtime hashes match | Same-trial receipts, bound policy and execution readiness missing. No seed/answer opened. |
| Original release checker | Exit 1; `ok: false`; 47/60 | Twelve earlier requirements unverified; phase 6–10 release reviews absent. |

[Sanitized execution receipt](../evidence/runs/submission-ready/remaining-checks-v65.json) records commands, source/artifact hashes and results. Private raw artifacts remain in `evidence/runs/verification-v65/`. The failing release audit is preserved.

## Every open check

| Check | State | What prevents acceptance |
| --- | --- | --- |
| CC-035 | FAILED | Matching original faulty-checkout recording is absent. Need that contemporaneous recording or a properly recorded replacement checkout with matching export. |
| CC-036 | BLOCKED | Requires complete CC-035 artifact. Today's clean-directory run verifies the available ZIP only. |
| CC-038 | BLOCKED | Actual undisclosed-seed LIVE_SANDBOX investigation, deterministic confirmation and controlled reveal. Accepted protocol and known-case model calls do not establish discovery. |
| CC-040 | IN_PROGRESS | CC-036/038 and accepted reduced-witness lineage. The v69 source-impact review retained historical fresh proof only; changed source still lacks current timing/orchestration and matched-run proof. |
| CC-041 | BLOCKED | Complete CC-035 export and same meaningful test against faulty/repaired code. Today's matching replay outcomes are supplemental. |
| CC-042 | IN_PROGRESS | Historical repair delivered one ticket in 3.360974s. Independent v69 impact review retains it as historical partial support only; new Store locking/queries mean current timing and agent orchestration remain unproven. CC-024 is accepted; CC-040/041 remain open. |
| CC-046 | IMPLEMENTED_UNVERIFIED | CC-040 and complete actual Studio comparison across required cases, with synchronized customer/provider/merchant/timeline panels. Saved-case selection is partial proof. |
| CC-048 | IMPLEMENTED_UNVERIFIED | CC-046 and complete start/inspect/cancel/compare/export journey, specified failure states, keyboard and viewport checks. |
| CC-050 | IMPLEMENTED_UNVERIFIED | Collection execution passed again; CC-035 prerequisite remains unmet. |
| CC-056 | BLOCKED | CC-036/042/048, then documented clean-start fresh investigation, finding, export and repair comparison. Keyless replay is a separate path. |
| CC-057 | IMPLEMENTED_UNVERIFIED | CC-050/056 and complete frozen-build acceptance review. This independent audit covers available evidence only. |
| CC-059 | PENDING | Actual inspected video under three minutes, public access and required fresh journey/dependencies. Links, copy and script are prepared; owner retains recording/submission. |
| CC-060 | BLOCKED | All preceding requirements and phase/release reviews. The fresh release audit correctly refuses completion. |

The missing faulty-checkout recording and actual held-out discovery are the dependency roots. Other checks also require fresh-run, workspace, review and video conditions. Historical fresh payments are not silently promoted into current-source proof or new execution.

## Preserved v65 preparation history

Inactive private helpers now share the synthetic journal/verdict clock, arm the recorder watchdog before AppKit initialization and independently check recorder heartbeat/PID before order/capture/reconciliation dispatch. Nine offline tests passed in 1.385s on the first resumed attempt; shared Swift watchdog probes exited124 for simulated startup/finalization stalls. Recorder compilation passed. Actual native capture was not executed. Old failed attempts remain preserved; no canonical runtime changed.

Independent review passed for offline preparation only: nine tests in 4.893s, 53 source/snapshot pairs and six log hashes checked; 29 canonical files unchanged. All activation artifacts remain absent. This does not establish actual capture, footage, finalization or live readiness.

Five stale blocker descriptions were corrected without changing states: CC-040 protocol now exists; CC-042 no longer depends on an unaccepted CC-024; CC-046 needs reduced-witness proof rather than misnaming it repair proof; CC-059 links have been inspected; CC-060 now records 47/60.

The owner approved a harmless five-second exact-window capture probe. No capture started: initial window identification failed twice; after the owner confirmed visibility, on-screen matching failed twice again, including after a UI Raise. UI control renders CrashCart while native capture reports no on-screen matching window. The step is stopped and the capture allowance is unused. Next: resolve this visibility mismatch, then inspect actual frames, audio absence and finalization before proposing a scoped recorded Sandbox checkout. Compilation and watchdog probes are not actual recorder proof.

AG Studio is configured through 17 December; no replacement key is needed. Held-out execution still needs independently bound actual-trial inputs and applicable provider/model access and allowance. No new spending/service setup is authorized by this report. Owner video and final Devpost submission remain separate.

## Current recorder diagnostic — v68

The earlier capture blocker is resolved for a bounded harmless probe of the repaired binary: independent review passed, video is 67.143333 seconds / 997 frames / no audio, full decode emits no warnings, and process exit took 68.190 seconds. The five-second freshness guard is unchanged (maximum observed age 0.174427 seconds). Covering the window was exercised only for the final approximately seven seconds; return happened after capture. This does not prove a 600-second recording or a checkout. The one-use grant is consumed and all probe processes are stopped. [Scoped receipt](../evidence/runs/submission-ready/capture-v68.json).

**All 13 requirement states above remain unchanged; 47/60 verified.** Next: prepare and review a fresh recorded Sandbox checkout before obtaining its scoped execution authorization. No old attempt, payment or recording allowance is reused.

## Historical repair review — v69

[Scoped source and evidence review](../evidence/runs/submission-ready/repair-impact-v69.json) passed, including frozen dependencies/assertions and independent local tests. It preserves the original execution date and records the changed purchase updated_at timestamp. This adds historical partial support, not current provider/timing proof or a CC checkmark. The subsequently approved v69 attempt failed before checkout, as recorded below.

## Recorded-checkout attempt — v69 failure

The approved attempt failed on the unchanged five-second captured-frame guard and closed in 87.881 seconds. Read-only records contain no order, capture, operation, event, ticket or job; all four owned processes are absent. Private video has 1,209 frames / 81.551667 seconds, no audio and 33 timestamp warnings. The original stream error was discarded, so its cause is unknown; Safari’s later pattern error has no proven causal relation. The grant is consumed, and two failed recorded-checkout attempts remain preserved. No automatic live retry is planned. [Independent failed-attempt accounting](../evidence/runs/submission-ready/checkout-failure-v69.json).

**47/60; no new CC IDs.** Next: offline lifecycle diagnostics and local Safari response tests. All original acceptance conditions and unchecked items remain unchanged.

## Offline diagnostics — v70

The isolated recorder now preserves original lifecycle errors separately from cleanup errors. Swift 6 final compilation, 12 lifecycle assertions (including 1,000 concurrent transitions), unchanged frame-admission checks and both bounded watchdog probes pass. Independent review accepts diagnostic behavior only; the new capture binary has never run.

Actual Safari locally reproduced the exact pattern error for an HTML 502 API response, while valid JSON rendered normally. An isolated error-handling candidate passed six tests and browser checks for a clear connection message and recovery. This does not establish the historical v69 response or recorder cause. Neither candidate is promoted into accepted or public application source. [Scoped results](../evidence/runs/submission-ready/diagnostics-v70.json). **47/60; no new checks.**
