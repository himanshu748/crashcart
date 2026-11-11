# Submission scope and gates

**Historical preparation document.** For the current public links and submitted video, use [the README](../README.md), [hosting guide](HOSTING.md) and [video check](VIDEO_CHECK.md). Dated checks and unresolved historical findings below retain their original scope.

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

Evidence reviewed through 5 November 2026. These task states do not add CC checkmarks or establish organizer acceptance. A recorded integration and a fresh execution are different forms of proof.

| Task | State | Evidence and next action |
| --- | --- | --- |
| Clean-clone build and keyless runtime | Verified | [Commands, outputs and browser inspection](SUBMISSION_VERIFICATION.md). |
| Faulty/healthy replay and unchanged deadline | Verified | [Replay test output](../evidence/runs/submission-ready/replay-v62.log): faulty fails, timely healthy passes, original late healthy still fails. |
| Public source and OSI licence | Verified | [GitHub metadata](../evidence/runs/submission-ready/github-metadata.json), [About licence readback](../evidence/runs/submission-ready/github-license.txt), root MIT LICENSE. |
| Sandbox credential instructions | Verified document | [README](../README.md#run-your-own-sandbox-checkout) has account roles, variable names and safe private placeholders; no live access is included. |
| Meaningful PayPal and AI evidence | Historically exercised; documented | [Actual Sandbox recovery](../evidence/runs/judge-ready/recovery-v56.json) and [actual model investigation](AI_EVIDENCE.md). Different cases; keyless mode makes no new payment/model calls. Show this distinction in the video. |
| Submission fields and video script | Prepared | [DEVPOST.md](DEVPOST.md), [SUBMISSION.md](SUBMISSION.md), [175-second script](VIDEO_SCRIPT.md). Prepared copy is not a completed video or submitted form. |
| Public YouTube video under three minutes | **Pending — required** | Owner records, checks actual exported duration and privacy, uploads Public and verifies signed-out playback. A script does not satisfy this task or CC-059. |
| Final Devpost submission | **Pending — owner only** | Owner checks the real video/demo/source links and submits before 13 November 2026, 01:30 IST. The agent must not submit. |
| Free access throughout judging | Ongoing | The [current Lightsail demo](https://crashcart.52.202.25.181.sslip.io/) is verified now. Retain access through the 21 December winner announcement, with the 22 December UTC buffer; future uptime remains unverified. Keep the runnable source fallback. |

### Optional AWS deployment

The [local Docker/Caddy image](../evidence/runs/submission-ready/container-verified-v62.json) and [USD20/USD50 Budget configuration](../evidence/runs/submission-ready/budget-verified-v62.json) are verified. Budget email delivery is unverified. The recorded demo is now verified on an existing shared Lightsail host, with no new instance base fee. [Actual deployment and limits](LIGHTSAIL_SHARED_HOST.md). The dedicated-host plan remains an alternative; AWS is not required for the runnable access path. Alerts are notifications, not spending caps. Render stays excluded.
