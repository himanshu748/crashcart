# Submission scope and gates

Decision recorded 4 November 2026: the owner froze features and asked to close only requirements that gate a judgeable Devpost entry. Deferred items remain unchecked in BUILD_CHECKLIST.md. **47/60 verified; project incomplete.** This scope decision does not weaken an invariant or turn a partial result into acceptance.

## Official requirements

The [event requirements](https://paypalaihackathon.devpost.com/) require meaningful PayPal and AI integration, a working build, public source with an open-source licence, documentation and a public YouTube video under three minutes. Complete repository setup instructions or a hosted demo can satisfy runnable access. The [rules](https://paypalaihackathon.devpost.com/rules) remain authoritative. The organizer's 2 November video announcement asks entrants to show PayPal and AI working end to end. A replay alone does not prove a new AI or payment call.

The mappings below are engineering judgments about the submitted, explicitly recorded demonstration; they are not an organizer waiver. Full-workspace claims would require their associated evidence.

## Requested triage

| Check | One-line cause | Devpost gating status and disposition |
| --- | --- | --- |
| CC-035 — FAILED | The regression lacks the matching original faulty-checkout video. | **Not a specific submission gate. Deferred/out of this submission sprint.** A new public product demo is mandatory, but need not be this historical recording. Preserve the failed check. |
| CC-036 — BLOCKED | Complete exported regression depends on CC-035's missing video. | **Runnable access is gating; this full artifact contract is deferred.** Verify the clean-clone keyless path separately; do not call that CC-036 acceptance. |
| CC-038 — BLOCKED | Real held-out defect discovery and confirmation have not been demonstrated. | **Held-out discovery is not required; deferred. Meaningful AI use is required.** Show only the actual historical model/provider investigation and its limits. |
| CC-041 — BLOCKED | Full same-artifact repair comparison depends on the complete CC-035 bundle. | **The displayed repair claim needs proof.** Verify the public recorded pair separately; full original-artifact acceptance is deferred. |
| CC-046 — IMPLEMENTED_UNVERIFIED | Complete AG Studio selection/comparison depends on a fresh reduced witness. | **Not gating for the keyless main entry; deferred.** Do not claim a completed Studio operator journey or select its bonus lane on this evidence. |
| CC-048 — IMPLEMENTED_UNVERIFIED | Full start/inspect/cancel/compare/export flow depends on CC-046. | **Not gating for the limited recorded path; deferred.** Verify actual keyless interactions separately. |
| CC-050 — IMPLEMENTED_UNVERIFIED | Full Postman export acceptance depends on CC-035; current checks use saved observations. | **Not required by Devpost; deferred.** Retain the actual limited Postman result. |
| CC-056 — BLOCKED | Full clean-start fresh investigation/export/repair depends on CC-036/042/048. | **Runnable build is gating, full fresh journey is deferred.** Do not present the replay as a fresh investigation. |
| CC-057 — IMPLEMENTED_UNVERIFIED | Complete independent acceptance review depends on CC-050/055/056. | **Internal release gate, not a Devpost deliverable; deferred.** Independently review this submission package without claiming full acceptance. |
| CC-060 — BLOCKED | All 59 original checks and release review have not passed. | **Internal project-completion gate; deferred.** Never call the project complete or claim 60/60. |

CC-040 and CC-042 (fresh reduced witness and repaired purchase) are also outside this submission sprint. CC-059 remains pending under its original broader acceptance; its **public video deliverable is a submission blocker** until the owner records, uploads to YouTube publicly, and verifies playback. A script is not a video.

## Submission checklist (separate from the 60-check contract)

- Clean-clone execution, keyless runtime and replay pair: evidence is recorded in [SUBMISSION_VERIFICATION.md](SUBMISSION_VERIFICATION.md).
- Sandbox account instructions and safe private buyer placeholders: [README](../README.md#optional-sandbox-test-buyer-path).
- Public repository and MIT licence: verify GitHub metadata and rendered repository licence link.
- Meaningful PayPal and AI: actual historical provider/model evidence must be inspected and described accurately; no new inference in judge mode.
- AWS: deployment plan only until the owner provisions and verifies it. The existing GitHub Pages URL remains the working public link.
- Video: owner must record and publish a YouTube video under three minutes; no public video was created by this sprint.
- Devpost: draft fields only; owner reviews and submits before **13 November 2026, 01:30 IST**. Keep test access through **15 December 2026**.
