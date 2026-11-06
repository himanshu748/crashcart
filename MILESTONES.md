# CrashCart delivery milestones

Updated **6 November 2026**. **47/60 verified; 13 original checks open; zero stale accepted checks.** Features are frozen. These milestones order work; they neither grant acceptance nor authorize new spending, provider calls or submission.

## Verification resumed — 5 November

The owner has now requested verification of all 13 open CC checks. [Current results](docs/REMAINING_VERIFICATION.md) supersede the deferral and next-action language below. Features remain frozen; no new service allowance or payment/recording window is created by this request. The recorded submission path remains available while original acceptance gaps are resolved.


**Design amendment:** [updated CC descriptions](docs/DESIGN_CONTRACT_UPDATE.md) keep IDs stable and strengthen four open conditions. Current original count is 47/60. The 3 November plan inside the collapsed historical section retains its then-current counts and failures; it is not the active queue. The loading repair is pushed but not hosted because GitHub CI is blocked by the account billing lock.

## Current submission path

| Milestone | State and evidence | Next action / owner |
| --- | --- | --- |
| Runnable, keyless product | Verified clean-clone execution, healthy/faulty replay pair, downloadable regression and hosted access. See [verification](docs/SUBMISSION_VERIFICATION.md). | Preserve the working [HTTPS demo](https://himanshu748.github.io/crashcart/); fix a demonstrated regression if one appears. |
| Honest integration story | Historical actual PayPal recovery and model investigation documented; keyless mode makes no new provider/model calls. See [AI evidence](docs/AI_EVIDENCE.md) and [submission copy](docs/DEVPOST.md). | Keep replay, historical service calls and fresh verification distinct in the recording. |
| Public video | **Pending — required submission deliverable.** The [175-second script](docs/VIDEO_SCRIPT.md) is prepared; no video or public watch URL is verified. | Owner records, inspects actual duration/privacy, uploads Public to YouTube and verifies signed-out playback. |
| Final Devpost entry | **Pending — owner action.** Paste-ready fields exist; a draft is not submitted. | Owner reviews links and video, then submits before 13 November 2026, 01:30 IST. Agent must not submit. |
| Access during judging | Current GitHub Pages access is verified; future uptime is **ongoing/unverified**. | Keep source/demo available through 15 December. Recheck access before submission and during judging. |

## Optional AWS host

Local Docker/Caddy and AWS Budget configuration are verified; an AWS compute instance and public TLS endpoint are **not deployed**. No existing hostname was supplied. This does not block runnable access because the current HTTPS demo and clean-clone path work. Budget emails are configured, but delivery is not verified and alerts are not spending caps. See [AWS plan and current results](docs/AWS_JUDGE_DEPLOY.md). Do not buy a domain or provision infrastructure merely to close this optional milestone.

## Original release backlog — verification resumed, not passed

| Original state | IDs | Boundary |
| --- | --- | --- |
| Failed | CC-035 | Matching original faulty-checkout recording missing; preserve the failure. |
| Blocked | CC-036, CC-038, CC-041, CC-056, CC-060 | Full export, held-out discovery, repair journey and release prerequisites remain unmet. |
| Implemented, unverified | CC-046, CC-048, CC-050, CC-057 | Full linked workspace, operator journey, Postman artifact and complete acceptance review remain unverified. |
| In progress | CC-040, CC-042 | Fresh reduced-witness and repaired-payment experiments remain incomplete. |
| Pending | CC-059 | Public video is active submission work; full original acceptance also requires the broader journey and dependencies. |

The exact causes and original evidence requirements remain in [open checks](docs/OPEN_CHECKS.md). Verification is resumed; execute experiments only when their necessary access, technical bounds and specific authorization exist. CC-060 remains the sole project-completion gate.

## Preserved earlier planning

The following snapshot preserves the earlier milestone mapping and its dated evidence. Its counts, ordering and proposed next actions are historical and superseded by the current submission scope above.

<details>
<summary>Earlier full-release plan — historical, not an active work queue</summary>

# CrashCart completion milestones

Plan updated after the actual **3 November 2026** verification. Canonical progress is **44/60**, with zero stale requirements: CC-037 is verified by `DOCUMENT_REVIEW` and CC-039 by `LOCAL_TEST`. The tables retain all **18 originally mapped IDs**; **16 remain open**. These milestones organize the existing [60-check contract](BUILD_CHECKLIST.md); they do not change its conditions, add checkmarks or create service authorization. [STATUS.md](STATUS.md) remains the current execution ledger. The private acceptance archive retains the actual application readback and independent review; [STATUS.md](STATUS.md) summarizes the scoped results.

The delivery order is payment/recovery → complete recorded original/export → held-out evaluation → unchanged regression and fresh repair → operator journey → clean-start/review → real demonstration → final release. Work follows actual dependencies, not an artificial stop between headings: the held-out protocol, evidence inventory and local handoff preparation can proceed while a provider gate is blocked. Reuse valid existing proof when its source and conditions remain applicable; do not repeat a paid test merely because this plan was added.

## Execution and budget boundaries

The budget labels in the tables apply to every associated next action:

- **L — Local preparation or verification.** Use isolated owned copies and preserve the frozen source/evidence. No provider, model, remote browser, account or public-window action is implied. Local fixtures cannot close a real-integration requirement.
- **R — Real sandbox / remote execution gate.** No PayPal, remote-browser, tunnel or webhook usage allowance is included in this source release. Use owned Sandbox accounts and an exact approved experiment with enforceable session, cost and cleanup bounds. An inactivity timeout alone is not an absolute lifetime limit. No real-money payment, permanent hosting or Render.
- **A — Model execution gate.** No model credits or inference grant are included. Configure an owned endpoint, review the exact data/destination and impose call/time/cost limits before execution. No silent provider fallback.
- **U — Licensed local workspace.** The existing private AG Studio trial was issued through **17 December 2026**; it does not supply public/judge access or a redistribution grant. Saved-record SDK rendering requires no new native query. Verify the delivered licence/access route; keep keys and compiled commercial overlays private. Any new inference still needs A.
- **V — Media and external handoff.** Local copy and shot preparation can continue. Actual footage, privacy review, links and authorized publication must precede a video claim. Generated narration uses **Deepgram only**, after its private access/credits and usage scope are confirmed; no substitute voice provider or billing change is implied. Writing this plan performs no upload, submission or personal attestation; owner-provided facts and actual external actions are handled separately.

One authorized run may support more than one requirement only when it actually exercises each condition and preserves the correct source revision, mode, identifiers and evidence. An original sandbox run, recorded replay, current local read and fresh sandbox verification remain different observations.

## M1 — Authenticate payment notifications and finish recovery

**Outcome:** payment completion can reach the owned store securely, and a crash cannot silently duplicate or lose the promised ticket. Start with the failed authentic-notification path; keep the existing local raw-byte repair and recovery records as dated partial proof.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-023 — Failed** | CC-010, CC-011 · `LIVE_SANDBOX` | **R.** Corrected authentic delivery, invalid-signature rejection and the exact-event resend have not been exercised; earlier real notifications returned 400. | A real Sandbox event passes signature verification; a deliberately invalid signature is rejected; resending that exact verified event leaves the expected single entitlement and a clear duplicate trace. | Finish a source-bound ingress/cleanup preflight, resolve the remote lifetime/cost finding, then seek one concrete authorized notification experiment. Remove only the newly created subscription/window and verify cleanup. |
| **CC-024 — Blocked** | CC-014, CC-020, CC-022, CC-023 · `LIVE_SANDBOX` | **L first; R if new execution is required.** CC-023 is open. Historical process-kill/restart recovery exists but is not full acceptance. | An actual meaningful post-payment/pre-ticket process termination and restart recovers the same logical operation and delivers exactly one ticket within the unchanged 60-second promise. | Inspect the existing actual recovery and its source/mode compatibility after CC-023 passes. Use its real mode/date; do not relabel fresh evidence as an original run. Repeat only missing or invalidated behavior under an authorized matching experiment. |
| **CC-052 — Blocked** | CC-005, CC-022, CC-024 · `LOCAL_TEST` or `LIVE_SANDBOX` | **L; R only for a required real financial boundary.** CC-024 is open. Overlapping health-job claims are not financial-action concurrency proof. | A focused competing-claim test plus meaningful worker termination/resume preserves ownership, pending approval and operation identities; final payment and ticket counts have no silent duplicate action. | Map existing lease/fencing and actual restart evidence to the financial boundary. Exercise the uncovered overlap/retry path in an isolated owned fixture; inspect the resumed journal and counts. |

## M2 — Deliver a complete recorded original and runnable export

**Outcome:** another engineer can run the actual failure from the delivered artifact, including its required recording or resolvable hash-bound recording reference.

The original faulted-checkout recording was never captured. A healthy KERNEL recording, later replay or JSON tape cannot replace it. Preserve that failure. If it cannot be recovered, prepare a **distinct, newly authorized and fully recorded original defective case**, then have an independent reviewer decide whether that complete case satisfies the unchanged export requirement. Never backdate it or present it as the missing historical recording.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-035 — Failed** | CC-031, CC-033, CC-034 · `RECORDED_REPLAY` | **L inventory; R to collect missing actual original evidence.** Existing exports fail the recording condition. | Export contains the fixture/dependency, immutable invariant, meaningful fault schedule, required recording/reference, versions and commands. It executes against the defective fixture and fails for the claimed mismatch, not a generic error. | Inventory the original recording/reference first. If absent, prepare the distinct complete-case capture and review path above; package its actual correlated evidence without changing the old missing-recording result. |
| **CC-036 — Blocked** | CC-035 · `RECORDED_REPLAY` | **L after the complete artifact exists.** Clean execution alone cannot cure CC-035's missing content. | The actual delivered export verifies and runs in a fresh directory using only documented prerequisites, without payment credentials; any fresh-run buyer approval remains explicit. | Extract the accepted export into a new disposable directory, verify its manifest, execute the documented command and inspect its exact failure signature and prerequisites. |

## M3 — Freeze and exercise a held-out evaluation

**Outcome:** the investigator can discover a seeded mismatch without receiving the answer, while healthy and insufficient-evidence cases remain distinct. **M3 is partial:** the frozen protocol/input boundary and predefined local controls passed CC-037/039; **CC-038 still requires actual `LIVE_SANDBOX` discovery**. The withheld variation remains sealed. Local intercepted requests and known control outcomes are not model discovery.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-037 — Verified (document review)** | CC-028, CC-029, CC-030 · `DOCUMENT_REVIEW` | **L — verified documentary proof.** The actual immutable freeze preceded independent private selection and review of exact selected-run metadata, contexts and tools. No live discovery, actual inference or seed reveal occurred. | The investigator version is frozen before reviewer selection; seed, expected mismatch and relevant defect source are outside the runtime agent's allowed input and tools. Actual input paths are inspected for leakage. | Preserve the sealed variation and reviewed boundary. Re-review changed inputs or configuration; inspect future real customer receipts for leakage and provenance before any authorized CC-038 trial. |
| **CC-038 — Blocked** | CC-018, CC-028, CC-029, CC-037 · `LIVE_SANDBOX` | **R + A.** The protocol is accepted, but the actual withheld runtime investigation and its bounded service grants are missing. Synthetic local receipts and intercepted replies do not establish LIVE provenance or discovery. | The bounded runtime agent finds the withheld mismatch without the bug identity or causal sequence in its context; deterministic evidence verifies it before the reviewer reveals the seed. | Use the accepted protocol to prepare the precise owned-fixture run, real customer-receipt provenance, redacted model payload, budget and stop conditions. Resolve R/A gates before execution; retain the full sanitized investigation and reveal only after its durable authorized verdict. |
| **CC-039 — Verified (local controls)** | CC-017, CC-037 · `LOCAL_TEST` or `LIVE_SANDBOX` | **L — verified local controls.** Four fresh post-freeze processes exercised actual held-out gating and production reconciliation/fulfillment with synthetic provider facts, prescribed intercepted replies and a logical clock. No external inference, provider/browser/payment operation or wall-clock fulfillment claim. | Under unchanged invariants, legitimate delayed healthy fulfillment passes and inadequate payment evidence stays inconclusive. A no-failure-found result states its actual search limits. | Retain the exact local control traces retained in the private acceptance archive, unchanged invariant and four-call/180-second limits. Repeat only invalidated controls after relevant changes; preserve their LOCAL_TEST provenance and scoped conclusions. |

## M4 — Pass the unchanged test, then verify fresh repair

**Outcome:** the defective and repaired merchants face the same meaningful promise, followed by new actual Sandbox purchases with new identities. CC-041 can proceed after M2 without waiting for unrelated held-out work; CC-040 and CC-042 have their additional dependencies below.

The public late-read tape still correctly fails the healthy variant with `ticket_delivered_late`. A separately preserved early-read witness passed its recorded comparison but lacks the required original fault recording. Neither result may be rewritten or silently substituted to manufacture a repaired pass.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-041 — Blocked** | CC-035 · `RECORDED_REPLAY` | **L after M2.** The complete recording/export prerequisite is missing; the late-read healthy failure remains real. | The same exported regression fails defective and passes repaired code with the unchanged invariant, deadline and materially equivalent fault schedule. The source diff shows the behavior correction. | Use the complete accepted original/export, inspect the repair diff and execute both variants against the exact same input. Keep any late-read failure open; do not relax the checker or change timestamps. |
| **CC-040 — In progress** | CC-034, CC-036, CC-038 · `FRESH_SANDBOX` | **R.** Clean accepted export and held-out discovery are open. Older separate payments do not establish this reduced witness. | The reduced scenario executes in a new merchant namespace with a newly created order, normal buyer approval and independent new Sandbox evidence. Original, replay and fresh IDs/outcomes are compared. | Once M2/M3 prerequisites pass, prepare the exact reduced schedule and a new approved purchase; inspect semantic equivalence and actual provider/ticket/customer observations. |
| **CC-042 — In progress** | CC-024, CC-040, CC-041 · `FRESH_SANDBOX` | **R.** Earlier fresh recoveries are partial historical proof; the prerequisite comparison chain is unfinished. | A new approved purchase under the same meaningful fault recovers and delivers exactly one ticket within 60 seconds, with independent payment state, fault activation and final customer experience. | Check whether existing source-bound fresh evidence supplies any unchanged condition. Execute the missing comparison with new identities after the prerequisites; inspect it directly against the defective run. |

## M5 — Complete the store team's operator journey

**Outcome:** selecting, investigating, cancelling, comparing and exporting form one usable experience. Keep the interface customer-facing; sponsor and acceptance details stay in documentation.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-046 — Implemented, proof incomplete** | CC-016, CC-040, CC-045 · `SPONSOR_SERVICE` | **U + L.** The required fresh comparison in CC-040 is missing. Saved-case rendering already has local proof. | Switching materially different required runs synchronizes browser, provider, ticket and timeline panels, with correct replay/fresh provenance and no stale cross-run data or fabricated causality. | After the comparison exists, switch between its actual cases in the real licensed Studio and inspect all linked records and labels. No new native query is needed solely to test selection. |
| **CC-048 — Implemented, proof incomplete** | CC-043, CC-044, CC-045, CC-046, CC-047 · `SPONSOR_SERVICE` | **U + L; R/A only for an authorized missing live step.** Selected UI groups passed; the complete required journey has not. | One focused real-browser walkthrough completes start, inspect, cancel, compare and export, including loading, empty, unavailable-provider and missing-evidence states; essential controls work by keyboard at documented sizes. | Use the accepted actual comparison and documented entry point. Exercise the whole sequence at desktop/390px/320px and relevant reduced-motion behavior; retain failures and repaired repeats. Record AT/zoom/engine limits rather than implying blanket accessibility. |

## M6 — Finish exported API proof, clean start and independent review

**Outcome:** a new reader can run the delivered build and a reviewer can challenge the complete result. The Postman evidence review can begin as soon as M2 supplies its missing export dependency.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-050 — Implemented, proof incomplete** | CC-010, CC-035 · `LOCAL_TEST`, `LIVE_SANDBOX` or `FRESH_SANDBOX` | **L for local saved-record reads.** Existing 48-assertion Newman execution is real but CC-035 remains open. No new PayPal read is implied. | The actual collection/template executes its meaningful status, amount and correlation assertions with explicit observed IDs and no exported secrets. | After CC-035, inspect the existing actual collection run and source bindings; reuse valid dated proof. Repeat only an affected collection/data path, using selected owned records and keeping authorization headers/private environments out of public artifacts. |
| **CC-056 — Blocked** | CC-036, CC-042, CC-048, CC-054 · `FRESH_SANDBOX` | **L preparation; U + R/A for missing authorized execution.** Export, repaired comparison and complete operator prerequisites are open. | A clean checkout or exact delivered build supports documented configuration, real investigation, finding, reproduction export and repaired comparison without the author's hidden setup notes. | Follow the public [quickstart](README.md), including npm build before Python startup. Use the delivered access/licence route, account for the public model placeholder and empty database, and record each actual step and missing dependency. |
| **CC-057 — Implemented, proof incomplete** | CC-050, CC-055, CC-056 · `DOCUMENT_REVIEW` | **L for independent review; valid U/R/A scope for any agreed rerun.** Focused reviews exist, but CC-050/056 and the full acceptance review remain open. | A separate reviewer inspects frozen source, reruns the core regression/export, challenges fresh/Sandbox/sponsor claims and leaves no blocking finding hidden behind a summary. | Freeze the delivered revision and evidence, give the reviewer exact artifacts and acceptance conditions, resolve findings, then re-review any affected proof before accepting the requirement. |

## M7 — Record the real demonstration and finish the handoff

**Outcome:** a viewer sees the customer problem, actual mismatch, labelled reduction and fresh repaired result in a truthful video under three minutes. The product story and shot plan are prepared; [STATUS.md](STATUS.md#submission-preparation) records the actual draft state. Prepared copy is not a recorded demo or final entry.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-059 — Pending** | CC-038, CC-040, CC-042, CC-048, CC-058 · `DOCUMENT_REVIEW` | **L + V.** Required actual discovery/fresh repair/operator proof, exported video and verified public video link are missing. | Watch the actual exported video, measure duration below 180 seconds, inspect every claim/link and verify required authorized public access. The video shows the required functioning journey, not a montage that implies unrun steps. | Prepare privacy-cleared footage only from actual accepted evidence and actions; record the missing fresh scenes after prerequisites. Edit the product story, use Deepgram only if generated narration is authorized, and complete the required public link/access check under the applicable publication grant. |

Use the owner's already supplied eligibility, project-history, feedback/consent and agreement facts as provided; do not repeat those requests. Check the current official form and any remaining required attestation before the applicable authorized action. Public source, a published project page, a draft form and the final hackathon submission are different states. Root owns the actual external/form work; writing this plan performs none and does not establish portal state.

## M8 — Inspect the final release verdict

**Outcome:** every original acceptance condition has current, usable evidence and the final report supports a truthful completion claim.

| Requirement and current state | Direct dependencies · allowed proof | Blocker / budget | Observable exit | Next concrete action |
| --- | --- | --- | --- | --- |
| **CC-060 — Blocked** | All CC-001 through CC-059 · `DOCUMENT_REVIEW` | **L.** The 15 other open requirements and their applicable phase/evidence reviews are not complete. This plan artifact does not close them. | Release validation passes CC-001–CC-059 with relevant evidence freshness; an independent inspection accepts the actual final report; canonical CC-060 then passes and progress reads 60/60 with no failed, blocked, stale or missing requirement. | Once the preceding gates actually pass, run the release checker, inspect its written report and source/evidence hashes, resolve failures, and only then accept CC-060. Devpost submission remains a separate action. |

Planned final commands, **not executed as completion proof by this document**:

```sh
python3 scripts/check_completion.py progress
python3 scripts/check_completion.py release --report evidence/CC-060/release-report.json
```

Until the final gate passes, report the actual verified total and exact open IDs. Relevant source, configuration, fixture, prompt or assertion changes reopen only the proof they invalidate. Keep original failed attempts and their modes, dates and identities.

## Proposed after release — SaaS roadmap, outside the 60 checks

These four ideas are **proposed and unimplemented**. They are not CC-061 onward, do not change the current acceptance contract and are not authorized builds, accounts, spending, deployments or provider connections. Choose scope with the user after the existing release gate; retain owned Sandbox testing unless production use is separately agreed.

| Proposed milestone | User outcome | Meaningful acceptance before claiming it works |
| --- | --- | --- |
| **S1 — Workspace onboarding and access isolation** | A store team can start its own workspace and invite the right people. | Two independent test workspaces survive restart; member/role changes have deliberate rules. An unauthorized member cannot read or change the other workspace through guessed case IDs, exports, recordings or investigator tools. Revocation/logout invalidates access, and the happy onboarding path is verified by keyboard and on a narrow screen. No multi-tenant claim from a shared global operator token. |
| **S2 — Provider connection health** | An operator knows whether payment, model and browser access is configured, recently verified, expired or unavailable. | A private connection setup distinguishes missing configuration from actual connectivity, exposes a real last-checked time, reports a controlled failure accurately and offers recovery without exposing secrets. Health checks make no unintended payment/model/browser operation and obey approved call/cost limits. Licence/access expiry is handled explicitly. |
| **S3 — Reviewed support handoff and notifications** | A confirmed incident reaches the team's chosen support destination with its evidence links. | A human reviews the exact incident payload and authorized destination. One real successful send returns a stored external receipt; duplicate triggers create one external item; a failed send shows a retryable state without false success. Minimized data, destination isolation and revocation are exercised. Zapier may fit, but no sponsor/API integration is claimed until its real delivery is tested. |
| **S4 — Recurring owned-flow reliability checks** | A team can schedule bounded test purchases or recorded checks and notice a missed promise. | One authorized scheduled owned-flow check and one controlled failure actually execute, retain correct fresh/replay modes, and respect per-workspace concurrency, call, time and cost controls. Pause prevents new dispatch; active cleanup and failure-tail limits are tested. Notification receipts and retention/deletion work across isolated workspaces. No unattended production charge or inherited blanket spending permission. |

</details>
