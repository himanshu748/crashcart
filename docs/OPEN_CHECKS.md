# Remaining acceptance work

Reviewed 5 November 2026. The frozen private build has **47/60 verified** and
zero stale requirements. CC-023 and CC-024 were accepted after actual Sandbox execution and independent review.
CC-052 combines its reviewed local concurrency proof with the now-satisfied recovery prerequisite.
The public repository includes reproducible source tests and curated replay
inputs; it excludes the private acceptance archive. Additive judge-access work
has separate public tests and does not inherit live-provider acceptance.


**Current priority:** features are frozen and non-gating original experiments are deferred. This page describes what is still missing from the original contract; it is not an instruction to resume those experiments. The active submission work is the public video and owner submission. [Submission gates](SUBMISSION_GATES.md) separates those tasks from full CC acceptance; [milestones](../MILESTONES.md) gives the current order.

## Deferred failed requirement

| Check | Root cause / current result | Exact next evidence |
| --- | --- | --- |
| CC-035 | The regression reproduces the failure, but its original faulty-checkout recording is absent. | Recover the original hash-bound recording, or record a new authorized faulty checkout and export its matching regression. An unrelated healthy recording or local replay video is insufficient. |

## Original checks and their missing evidence

| Check / state | Missing acceptance evidence or prerequisite |
| --- | --- |
| CC-040 / in progress | New namespace, order, buyer approval and transaction for the reduced witness; depends on CC-036 and CC-038. |
| CC-042 / in progress | Fresh repaired purchase, equivalent fault and unchanged promise, with provider, ticket and browser result; remaining dependencies are CC-040 and CC-041; CC-024 is satisfied. |
| CC-059 / pending | An exported public video under three minutes showing the required original and fresh journey; script alone is insufficient. Depends on CC-038, CC-040, CC-042, CC-048 and CC-058. |
| CC-046 / implemented, unverified | Complete actual Studio selection/comparison with provenance and no stale cross-case data; depends on CC-040. Recorded-only comparison is supplemental. |
| CC-048 / implemented, unverified | Complete operator start/inspect/cancel/compare/export, keyboard and responsive states; depends on CC-046. |
| CC-050 / implemented, unverified | CC-035. Current exported collection was rerun on 4 November: 7 local assertions and 48 assertions across six GETs of copied historical Sandbox records passed; missing proof failed as expected. This is stored-observation inspection, not a fresh provider call. |
| CC-057 / implemented, unverified | Independent complete acceptance review; depends on CC-050, CC-055 and CC-056. Partial review is not full acceptance. |
| CC-036 / blocked | Complete regression from a clean environment; depends on the missing recording in CC-035. |
| CC-038 / blocked | Real agent discovery of the still-undisclosed seeded defect and deterministic confirmation. Protocol CC-037 is accepted; known-case queries are not discovery. |
| CC-041 / blocked | Same meaningful regression fails defective and passes repaired, with complete CC-035 artifact. A newly executed recorded pair is useful but does not replace the recording. |
| CC-056 / blocked | Full clean-start fresh investigation, export and repair comparison; depends on CC-036, CC-042 and CC-048. Keyless replay access is a different, explicitly labelled path. |
| CC-060 / blocked | All earlier checks and required independent phase/release reviews. Project incomplete. |

## Dependencies for the deferred full release

- A usable owned Sandbox buyer and its actual approval for required new test payments.
- A technically bounded real browser/model execution path. Continuation is authorized; AWS infrastructure under
  $10/month is allowed. Eight previous remote session grants are consumed; no new paid session has started.
  The unresolved provider-enforced lifetime/billing limit still prevents KERNEL execution. KERNEL has been asked to clarify an absolute lifetime/billing
  bound; the sent message is not a provider answer.
- The original faulty-checkout recording, or access/authorization to create a
  properly recorded replacement experiment.
- AG Studio licence access is already resolved: the privately configured trial expires
  17 December 2026, after judging. No new key is requested. Full sponsor-workspace
  acceptance still needs the operator journey above; the keyless page does not
  require or redistribute this licence.
- The final demonstration video, which the owner will record; review its contents,
  duration and public access before accepting CC-059. Never publish credentials.

CC-023 is now verified: authentic first event and provider resend each returned
200 after signature verification; a controlled invalid-signature probe returned
400 without state changes. The intentionally defective merchant retained zero
tickets, one capture operation and one verified event. Exact webhook deletion and
process/tunnel cleanup passed. [Sanitized evidence](../evidence/runs/judge-ready/webhook-v55.json).
The old signature failure remains recorded. Safari buyer sign-in succeeded;
that notification checkout and its temporary window are consumed and closed.

CC-024 now proves recovery after an actual USD29 Sandbox capture and process exit 86 before ticket creation. The restarted worker delivered exactly one ticket in 4.067743 seconds from capture, with the original operation identities and 60-second deadline unchanged. All processes and the tunnel stopped within 141.658 seconds. [Sanitized recovery evidence](../evidence/runs/judge-ready/recovery-v56.json).

CC-052 is accepted using the existing 17-group LOCAL_TEST concurrency/restart evidence and the satisfied CC-024 prerequisite. Actual competing workers, SIGKILL and lease-expiry recovery retained one ticket with synthetic provider replies. This does not establish simultaneous real capture-POST behavior. The earlier interrupted recovery attempt remains recorded and is not a pass.

Part F and all other feature work remain frozen by the owner. The deferred original release backlog is not a prerequisite for writing or recording the narrower, accurately labelled submission demonstration. It remains a prerequisite for claiming CC-060 or project completion.
