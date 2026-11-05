# Remaining 13 checks — verification results

5 November 2026. **47/60 verified; no new CC checkmarks.** The owner resumed verification of all open checks. Features remain frozen. This pass executed available offline checks, inspected original evidence and dependencies, and repaired inactive recording preparation. No payment, public test window, recording, model call or remote browser session occurred.

## What actually ran

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
| CC-040 | IN_PROGRESS | CC-036/038 and accepted reduced-witness lineage. Historical fresh proof exists, but service/store/paypal bindings differ from current source and need impact review or a new matched run. |
| CC-041 | BLOCKED | Complete CC-035 export and same meaningful test against faulty/repaired code. Today's matching replay outcomes are supplemental. |
| CC-042 | IN_PROGRESS | Historical fresh repair delivered one ticket in 3.360974s, with later customer-view review. CC-024 is accepted; CC-040/041 and current-source/provenance review remain open. |
| CC-046 | IMPLEMENTED_UNVERIFIED | CC-040 and complete actual Studio comparison across required cases, with synchronized customer/provider/merchant/timeline panels. Saved-case selection is partial proof. |
| CC-048 | IMPLEMENTED_UNVERIFIED | CC-046 and complete start/inspect/cancel/compare/export journey, specified failure states, keyboard and viewport checks. |
| CC-050 | IMPLEMENTED_UNVERIFIED | Collection execution passed again; CC-035 prerequisite remains unmet. |
| CC-056 | BLOCKED | CC-036/042/048, then documented clean-start fresh investigation, finding, export and repair comparison. Keyless replay is a separate path. |
| CC-057 | IMPLEMENTED_UNVERIFIED | CC-050/056 and complete frozen-build acceptance review. This independent audit covers available evidence only. |
| CC-059 | PENDING | Actual inspected video under three minutes, public access and required fresh journey/dependencies. Links, copy and script are prepared; owner retains recording/submission. |
| CC-060 | BLOCKED | All preceding requirements and phase/release reviews. The fresh release audit correctly refuses completion. |

The missing faulty-checkout recording and actual held-out discovery are the dependency roots. Other checks also require fresh-run, workspace, review and video conditions. Historical fresh payments are not silently promoted into current-source proof or new execution.

## Preparation repairs and next action

Inactive private helpers now share the synthetic journal/verdict clock, arm the recorder watchdog before AppKit initialization and independently check recorder heartbeat/PID before order/capture/reconciliation dispatch. Nine offline tests passed in 1.385s on the first resumed attempt; shared Swift watchdog probes exited124 for simulated startup/finalization stalls. Recorder compilation passed. Actual native capture was not executed. Old failed attempts remain preserved; no canonical runtime changed.

Independent review passed for offline preparation only: nine tests in 4.893s, 53 source/snapshot pairs and six log hashes checked; 29 canonical files unchanged. All activation artifacts remain absent. This does not establish actual capture, footage, finalization or live readiness.

Five stale blocker descriptions were corrected without changing states: CC-040 protocol now exists; CC-042 no longer depends on an unaccepted CC-024; CC-046 needs reduced-witness proof rather than misnaming it repair proof; CC-059 links have been inspected; CC-060 now records 47/60.

The owner approved a harmless five-second exact-window capture probe. No capture started: initial window identification failed twice; after the owner confirmed visibility, on-screen matching failed twice again, including after a UI Raise. UI control renders CrashCart while native capture reports no on-screen matching window. The step is stopped and the capture allowance is unused. Next: resolve this visibility mismatch, then inspect actual frames, audio absence and finalization before proposing a scoped recorded Sandbox checkout. Compilation and watchdog probes are not actual recorder proof.

AG Studio is configured through 17 December; no replacement key is needed. Held-out execution still needs independently bound actual-trial inputs and applicable provider/model access and allowance. No new spending/service setup is authorized by this report. Owner video and final Devpost submission remain separate.
