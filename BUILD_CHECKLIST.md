# CrashCart: 60-check build contract for Codex

Prepared: 22 October 2026  
Initial status: 0/60 verified. This is a plan, not an implementation report.  
Deployment constraint: Render is excluded.

## 1. What this build must achieve

CrashCart investigates disagreements between the customer's checkout experience, independently observed PayPal sandbox payment state, and the owned merchant's delivered entitlement. It produces an executable reproduction, reduces unnecessary steps, and verifies a repaired merchant against the same business promise.

The initial fixture sells one USD 29 digital workshop ticket. The flagship failure is a successful sandbox capture whose response is lost or whose subsequent merchant processing crashes, leaving the customer without a ticket beyond an explicit recovery deadline.

The application investigates an intentionally defective owned merchant integration. It must not describe that experiment as a newly discovered PayPal vulnerability.

Keep the initial scope to one instrumented merchant, one checkout flow, a small fault grammar, one held-out seeded defect, and one complete repair demonstration. Refund workflows, arbitrary merchant scanning, marketplaces, live-money testing, and automatic production repairs are outside this version. Add them only through an explicit scope revision.

Planned integrations:
- PayPal Sandbox for actual test payments and independently queried payment records.
- AG Studio for investigation widgets, linked evidence, and agent-assisted dashboard interaction.
- KERNEL for the actual browser journey and recording.
- Postman for executable API verification exports.
- APIMatic Context Plugin as a documented development aid.
- Portable web application, backend, database, and worker. No Render dependency.

## 2. How to use this document

1. Put this file in the repository root as BUILD_CHECKLIST.md.
2. Merge the short rules in section 8 into the repository's existing AGENTS.md. Preserve unrelated instructions.
3. Create STATUS.md from section 10. Keep evidence in evidence/CC-NNN/.
4. Give Codex the build prompt in section 9.
5. Work in small batches within one phase. Continue automatically after its gate passes. Reviewers check behavior and evidence, not just the implementation summary.

AGENTS.md is a Codex-supported repository instruction file. BUILD_CHECKLIST.md, STATUS.md, and the evidence layout are project conventions proposed here; Codex does not enforce them automatically. The completion checker in CC-006 must be implemented before it can provide mechanical checks.

A checklist alone cannot guarantee correctness. The combination of explicit outcomes, executable verification, independent review, and inspected artifacts makes unsupported completion claims easier to detect.

## 3. What a checkmark means

Only VERIFIED becomes [x]. Everything else remains [ ].

| State | Meaning |
| --- | --- |
| PENDING | Work has not started. |
| IN_PROGRESS | Implementation or verification is in progress. |
| IMPLEMENTED_UNVERIFIED | Code exists, but the required behavior has not been demonstrated. |
| BLOCKED | A specific external dependency prevents progress. |
| FAILED | A verification attempt contradicted the acceptance condition. |
| STALE | Previously verified evidence was invalidated by a relevant change. |
| VERIFIED | Acceptance was exercised, evidence saved, and the result inspected. |

Use STATUS.md for the current state and blocker of unfinished items. BUILD_CHECKLIST.md is the authoritative list of requirements and verified checkmarks.

Before checking an item:
- Its entire acceptance condition must hold.
- The verification must actually have run or been inspected.
- The proof must use the required mode. A mock cannot satisfy a real sandbox requirement.
- Its verification record must identify the tested source revision, environment, result, and evidence files.
- Relevant prerequisites must be satisfied.
- No unresolved defect may invalidate that item.

An empty test suite, skipped integration test, successful compilation, or screenshot cannot establish behavior it never exercised. Document checks can use an explicit manual inspection; do not invent automated tests for prose.

Keep historical evidence. If relevant code, fixtures, configuration, prompts, or assertions change, reopen affected items and rerun only the verification that change invalidates. Unrelated documentation edits do not require another payment.

Do not change acceptance conditions, remove failed checks, weaken a deadline, or hide a defect merely to obtain a checkmark. A real scope change needs an explicit recorded decision from the user.

## 4. Evidence format

Every checked item needs evidence/CC-NNN/verification.json and the artifacts it references. Multiple items may reference the same real run, but each record must identify the distinct condition that run proves.

Suggested unverified template:

~~~json
{
  "item_id": "CC-010",
  "status": "IMPLEMENTED_UNVERIFIED",
  "mode": null,
  "source_commit": null,
  "relevant_source_hashes": {},
  "run_id": null,
  "command_or_action": null,
  "expected_result": null,
  "observed_result": null,
  "expected_exit_code": null,
  "observed_exit_code": null,
  "executed_at": null,
  "evidence_files": [],
  "dependencies": [],
  "review": {
    "reviewer": null,
    "result": null,
    "evidence": null
  }
}
~~~

Allowed evidence modes should distinguish DOCUMENT_REVIEW, LOCAL_TEST, LIVE_SANDBOX, RECORDED_REPLAY, FRESH_SANDBOX, and SPONSOR_SERVICE. A fresh sandbox run is a new actual sandbox execution with a new approved order; it is not a different label on recorded output.

Store the actual command output or observed action, relevant assertions, and sanitized machine-readable records. Record source hashes for behavior-affecting files. If verification used uncommitted changes, preserve the exact patch or equivalent source snapshot; a commit hash alone would be misleading.

Record credentials only as configured or missing. Do not put secrets, authorization headers, or buyer credentials in public proof. Redact personal data while preserving enough identifiers and amounts to correlate the sandbox experiment. Keep hashes of original artifacts where appropriate.

An expected failing regression test may correctly exit nonzero on the defective merchant. Record the expected and actual outcome, and verify the specific failure signature. An unrelated crash is not equivalent evidence.

The checker can validate record structure, files, hashes, modes, and completion counts. It cannot prove that a truthful-looking narrative is authentic or that the product is useful. Independent execution and artifact inspection remain necessary.

## 5. The 60 checks

### Phase 1: Scope, runnable foundation, and completion rules
**Gate:** A runnable skeleton and a working verification process exist. External prerequisites are known.

- [x] **CC-001. Freeze the product contract.**
  **Done when:** The target user, USD 29 ticket fixture, three sources of truth, explicit recovery deadline, flagship failure, success outcome, integration roles, and exclusions are written down. Render is excluded.
  **Verify:** Inspect the contract against the complete complaint-to-reproduction-to-repair journey. Record unresolved decisions without inventing answers.

- [x] **CC-002. Make the application skeleton runnable.**
  **Done when:** The chosen web application, API, database, and worker start using documented commands with pinned dependency versions, migrations, and a seeded merchant fixture.
  **Verify:** Start from a clean checkout and database. Record startup, health responses, migration success, and the actual commands.

- [x] **CC-003. Install the build execution rules.**
  **Done when:** Repository instructions reference this checklist; STATUS.md records unfinished work; the evidence format and allowed completion states are established. Existing repository rules are preserved.
  **Verify:** Inspect the files and have a fresh Codex session identify the current task, evidence requirement, and completion boundary without relying on previous chat history.

- [x] **CC-004. Prove integration prerequisites early.**
  **Done when:** PayPal sandbox access, model access, AG Studio licensing, and KERNEL access are confirmed with minimal appropriate checks. The owned application is reachable from KERNEL and a webhook delivery path is documented. APIMatic and Postman prerequisites, license expiry, and access through the judging period are recorded.
  **Verify:** Save sanitized connectivity results and exact blockers. Do not mark this complete while a required credential or reachable test target is missing.

- [x] **CC-005. Persist the experiment and payment identities.**
  **Done when:** Migrations store runs, attempts, purchases, semantic operation keys, order IDs, request IDs and bodies, events, invariant versions, fault configurations, and evidence references. Live sandbox and recorded replay data have explicit modes.
  **Verify:** Create a sample run, restart the services, and read it back. Confirm two runs cannot silently share merchant state, fault configuration, or evidence.

- [x] **CC-006. Implement the completion checker.**
  **Done when:** A script validates 60 unique requirement IDs and rejects checked items with missing records, missing artifacts, wrong proof modes, unsatisfied dependencies, or stale relevant hashes. Phase checks reject unfinished requirements in that phase.
  **Verify:** Demonstrate rejection of one unsupported checkmark, one missing artifact, and one stale source hash. Ordinary progress validation must allow an honestly incomplete project. Release validation checks CC-001 through CC-059 before CC-060 can complete.

### Phase 2: One real customer checkout
**Gate:** An actual sandbox purchase delivers exactly one ticket, with independently inspectable records.

- [x] **CC-007. Build the owned merchant fixture.**
  **Done when:** A customer can view the USD 29 workshop ticket, its delivery promise, and an actual entitlement page backed by stored merchant state.
  **Verify:** Walk the browser flow. Confirm an unpaid purchase has no ticket and a displayed ticket corresponds to a real merchant record.

- [x] **CC-008. Create and journal a real sandbox order.**
  **Done when:** The server determines the price and currency, creates the PayPal sandbox order, and persists the order ID and intended operation before capture can start.
  **Verify:** Inspect the actual provider response and operation journal. Altering a client-supplied price must not silently change the server-owned ticket price.

- [x] **CC-009. Complete the buyer approval flow.**
  **Done when:** Real sandbox buyer approval returns to the merchant correctly. Cancellation and abandonment remain explicit non-completed paths.
  **Verify:** Exercise approval and cancellation in a browser. Save the corresponding states and identifiers; a fabricated approval callback does not satisfy this check.

- [x] **CC-010. Capture and independently confirm payment.**
  **Done when:** An approved sandbox order is actually captured and an independent provider read confirms the capture's status, amount, currency, and relation to the purchase.
  **Verify:** Save sanitized actual capture and retrieval records. An HTTP success response without the expected payment object is insufficient.

- [x] **CC-011. Grant the entitlement once.**
  **Done when:** The healthy merchant creates exactly one usable ticket for the confirmed logical purchase. Re-entering fulfillment for that purchase does not create another ticket.
  **Verify:** Query the merchant's entitlement store before and after repeated fulfillment processing. Match the ticket to the confirmed purchase.

- [x] **CC-012. Record the first complete KERNEL checkout.**
  **Done when:** A real KERNEL session performs the complete owned merchant journey through sandbox approval, payment confirmation, and ticket access. Run, browser session, payment, and ticket IDs are correlated.
  **Verify:** Inspect the session recording and independent payment and merchant records. Local browser automation alone cannot establish the KERNEL claim.

### Phase 3: Compare customer, provider, and merchant evidence
**Gate:** CrashCart can demonstrate the core disagreement before substantial dashboard polish.

- [x] **CC-013. Capture what the customer actually sees.**
  **Done when:** Each run records the relevant browser state, navigation events, visible payment or delivery message, and links to its recording at the important transition.
  **Verify:** Compare the recorded customer view with the underlying browser run. A server-side status copied into a UI label is not independent browser evidence.

- [x] **CC-014. Reconcile from the order ID when the capture response is lost.**
  **Done when:** The investigator can retrieve the order, discover its capture, and confirm payment even when the merchant never learned the capture ID.
  **Verify:** Use a real sandbox capture with a deliberately lost merchant-facing response. Show that the persisted order ID is sufficient to find the confirmed payment.

- [x] **CC-015. Read actual merchant delivery state.**
  **Done when:** A documented read-only adapter exposes the fixture's ticket or entitlement state by logical purchase. Unknown and missing records remain distinguishable.
  **Verify:** Compare the adapter response with the underlying merchant store for paid, unpaid, and missing-purchase cases. Do not invent a PayPal entitlement API.

- [x] **CC-016. Correlate events without inventing causality.**
  **Done when:** Browser, provider, and merchant observations join through run, purchase, order, and operation identities. The trace distinguishes event time, observation time, and supported causal relationships.
  **Verify:** Inspect a delayed or reordered observation. The timeline must not claim that timestamp ordering alone proves cause across different systems.

- [x] **CC-017. Evaluate a fixed, time-bounded invariant.**
  **Done when:** Deterministic code checks payment status, integer minor-unit amounts, currency, and ticket count against a versioned invariant and explicit recovery window. It returns pass, fail, or inconclusive.
  **Verify:** Exercise a true mismatch, legitimate delayed delivery within the window, and missing provider evidence. The model cannot change the deadline after seeing the result.

- [x] **CC-018. Produce the first genuine mismatch report.**
  **Done when:** A small controlled fault in the owned fixture leaves a completed sandbox payment with zero tickets beyond the deadline, and the report links all three observations.
  **Verify:** Inspect the actual capture, failed or unresolved customer experience, and merchant query. This first report can be deterministic; AI discovery is verified later.

### Phase 4: Controlled faults and reliable recovery
**Gate:** Failures are deliberate and observable; the investigator's own behavior remains reliable.

- [x] **CC-019. Restrict faults to registered owned targets.**
  **Done when:** Fault controls operate only on registered merchant fixtures in the permitted environment. They cannot modify PayPal's actual provider records or target an arbitrary host.
  **Verify:** An unregistered target is rejected before a network action. A valid owned fixture accepts an explicitly recorded fault configuration.

- [x] **CC-020. Execute a small typed fault grammar.**
  **Done when:** The harness can apply the planned response loss, controlled event delay or duplication, and merchant-process interruption at documented boundaries. Healthy behavior is the default.
  **Verify:** For each supported fault, save its configuration, activation, observed effect, and deactivation. Unsupported faults must produce an explicit error.

- [x] **CC-021. Preserve ambiguous payment outcomes.**
  **Done when:** The investigator records a lost response as unresolved until independent reconciliation establishes payment state. It preserves the faulty merchant's incorrect message as evidence.
  **Verify:** Demonstrate an ambiguous successful capture and a genuinely unsuccessful operation. Neither may be inferred solely from a timeout.

- [x] **CC-022. Preserve payment operation identity across retries.**
  **Done when:** A retry of the same semantic payment operation uses the persisted request ID and body, including after restart. A changed financial operation cannot masquerade as the same retry.
  **Verify:** Exercise a lost-response retry and inspect the operation journal and provider records. Respect the endpoint's documented idempotency support and retention limits.

- [x] **CC-023. Authenticate and deduplicate webhook processing.**
  **Done when:** Real webhook ingress verifies signatures. Controlled duplicate processing uses a distinct fixture path after verification and does not disable external signature checks.
  **Verify:** Save one authentic sandbox event, rejection of an invalid signature, and a repeated-event trace with the expected entitlement count.

- [x] **CC-024. Recover the healthy merchant after interruption.**
  **Done when:** After a crash following payment but before ticket delivery, durable reconciliation establishes payment and fulfills the healthy merchant once within the declared budget.
  **Verify:** Kill and restart the relevant process at the recorded boundary. Inspect the recovered operation and ticket count. The deliberately faulty fixture remains available for investigation.

### Phase 5: A real AI investigation
**Gate:** The agent proposes and tests a hypothesis; deterministic code establishes the result.

- [x] **CC-025. Execute and record real model calls.**
  **Done when:** An actual configured model processes the incident and produces structured output. Sanitized traces retain model identity, input versions, tool exchanges, and observed usage where available.
  **Verify:** Inspect a real invocation. Remove model access in a separate check and confirm the run reports the limitation instead of presenting a canned response as live reasoning.

- [x] **CC-026. Translate a promise into a validated invariant.**
  **Done when:** The agent maps a customer's delivery promise to a bounded schema using actual adapter fields, amount, currency, and timing semantics. Missing information is surfaced.
  **Verify:** Try two meaningfully different promises and one ambiguous input. The proposed invariant must change appropriately and cannot invent an unobservable field.

- [x] **CC-027. Give the investigator bounded tools.**
  **Done when:** Typed tools expose relevant browser, provider, merchant, and controlled-fixture operations. Tool outputs are validated, and the runtime agent cannot directly set a verified verdict.
  **Verify:** Inspect actual calls and reject malformed or out-of-scope requests. Provider objects and page text are treated as data, not new instructions.

- [x] **CC-028. Plan and execute an adaptive investigation.**
  **Done when:** The agent records a hypothesis and bounded experiment before executing it, then uses observations to select or revise subsequent steps.
  **Verify:** Change a relevant incident condition or fixture behavior. Confirm the investigation adapts rather than replaying an unchanged hardcoded diagnosis.

- [x] **CC-029. Ground the diagnosis in evidence.**
  **Done when:** Every substantive finding references the observations and invariant that support it. Reports distinguish an observed mismatch, a hypothesis, and insufficient evidence.
  **Verify:** Remove a necessary observation in a controlled case. The agent must preserve uncertainty instead of inventing the missing payment or delivery fact.

- [x] **CC-030. Bound and stop investigations cleanly.**
  **Done when:** Attempts, execution time, and model or browser usage have explicit budgets. Cancellation, malformed model output, provider errors, and exhausted budgets preserve collected evidence.
  **Verify:** Exercise a budget exhaustion and cancellation. Confirm termination is visible and cannot become a success result through a fallback response.

### Phase 6: Recorded replay, reduction, and executable export
**Gate:** A failure can be reproduced from the delivered artifact, with its provenance intact.

- [x] **CC-031. Save a replayable evidence package.**
  **Done when:** The run captures the required request and response tape, fixture state, fault schedule, invariant version, source versions, and a sanitized artifact manifest with hashes.
  **Verify:** Reconstruct the inputs without relying on the original browser tab, process memory, or undocumented absolute paths.

- [x] **CC-032. Run genuinely offline recorded replay.**
  **Done when:** Replay re-executes merchant behavior from the recorded inputs in an isolated namespace without new PayPal or KERNEL calls. Unsupported interactions fail explicitly.
  **Verify:** Execute with outbound network access disabled. Save the resulting trace and label it RECORDED_REPLAY throughout the UI and export.

- [x] **CC-033. Reduce by executing candidates.**
  **Done when:** The reducer removes unnecessary steps and reruns each accepted candidate while preserving valid prerequisites and the same payment-versus-delivery failure signature.
  **Verify:** Inspect rejected and accepted candidates. Removing buyer approval and causing a capture error must not count as reproducing a completed-payment delivery failure.

- [x] **CC-034. Report bounded reduction and repeatability honestly.**
  **Done when:** Reports include original and reduced sizes, candidate outcomes, search budget, termination reason, and whether repeated replay produced the same failure.
  **Verify:** Run a small predefined repeatability check. Use "smallest reproducer found within the search" and report flakiness when observed.

- [ ] **CC-035. Export a runnable regression artifact.**
  **Done when:** The export includes the fixture or its documented dependency, invariant, fault schedule, recording, versions, commands, and meaningful test outcomes. Offline and fresh sandbox modes are distinct.
  **Verify:** Run the exported regression against the defective fixture. Confirm it fails for the claimed mismatch, with useful output; a generic process error is insufficient.

- [ ] **CC-036. Reproduce from a clean environment.**
  **Done when:** The exported artifact runs using only its documented prerequisites. Offline reproduction needs no payment credentials. Fresh execution clearly exposes any buyer approval step.
  **Verify:** Use a clean directory or disposable environment and execute the export itself. Save its actual output and any unavoidable external prerequisites.

### Phase 7: Held-out discovery and an unchanged test of the repair
**Gate:** The core claim survives an experiment whose answer was withheld from the runtime agent.

- [x] **CC-037. Freeze a held-out evaluation protocol.**
  **Done when:** The investigator version is frozen before a reviewer selects the held-out fixture variation. The seed, expected answer, and relevant defect source are excluded from the runtime agent's context and tools.
  **Verify:** Inspect the actual allowed inputs and fixture metadata for answer leakage. Record the expected mismatch outside the investigator's input path.

- [ ] **CC-038. Discover the held-out seeded defect.**
  **Done when:** The runtime agent finds the withheld mismatch without being supplied the bug identity or causal sequence during the run, and the deterministic checker verifies it.
  **Verify:** Save the full sanitized investigation and reveal the seed only after the verdict. Label this as seeded-defect discovery, not proof of unknown production-bug discovery.

- [x] **CC-039. Pass the clean and inconclusive controls.**
  **Done when:** A healthy merchant with legitimate delayed fulfillment passes, and a case with inadequate payment evidence remains inconclusive. No-failure-found reports disclose search limits.
  **Verify:** Run the predefined controls with unchanged invariants. "No failure found" must not become a universal safety guarantee.

- [ ] **CC-040. Verify the reduced witness in a fresh sandbox run.**
  **Done when:** The reduced scenario is exercised using a new merchant namespace, newly created order, normal buyer approval, and actual new sandbox transaction evidence.
  **Verify:** Compare the original, recorded-replay, and fresh-verification identifiers and semantic outcomes. Reusing the original paid order does not satisfy this check.

- [ ] **CC-041. Repair the merchant without weakening the test.**
  **Done when:** The repaired code passes the same invariant and materially equivalent fault schedule that exposes the defective code. Neither the deadline nor the checker is relaxed.
  **Verify:** Run the same exported regression against both versions. Inspect the diff and show an actual behavior correction rather than suppression of the finding.

- [ ] **CC-042. Verify the repaired flow with a fresh payment.**
  **Done when:** A new approved sandbox purchase under the same meaningful fault completes recovery and delivers exactly one ticket within the unchanged budget.
  **Verify:** Inspect independent payment state, ticket count, fault activation, and final customer experience. Save a direct comparison with the defective run.

### Phase 8: The complete investigation experience in AG Studio
**Gate:** A user can start, understand, inspect, and export an investigation through the actual product.

- [x] **CC-043. Start a new investigation from the product.**
  **Done when:** An operator selects the registered fixture, supplies a promise or incident, sees the relevant budget and invariant, and starts a uniquely identified run.
  **Verify:** Use the UI with new input. Confirm it creates a real backend investigation rather than opening an existing demonstration result.

- [x] **CC-044. Show truthful run states and controls.**
  **Done when:** Queued, running, awaiting approval, completed, failed, cancelled, and inconclusive states appear when applicable. Refreshing reconnects to persisted run state.
  **Verify:** Exercise an approval wait, an interruption, and cancellation. Confirm controls act on the selected run and existing evidence remains readable.

- [x] **CC-045. Build the actual AG Studio investigation workspace.**
  **Done when:** AG Studio renders custom payment-versus-delivery and run-comparison widgets using real investigation data, with a usable theme and layout.
  **Verify:** Inspect the implementation and exercise the running widgets. An ordinary table or dependency entry alone cannot satisfy the promised Studio integration.

- [ ] **CC-046. Link evidence selection across the workspace.**
  **Done when:** Selecting a run or finding synchronizes the customer observation, provider record, merchant entitlement, and timeline. Recorded replay and fresh sandbox provenance are visible.
  **Verify:** Switch between materially different runs and inspect all linked panels. Stale cross-run data or fabricated causal ordering fails this check.

- [x] **CC-047. Make Studio's agent interaction useful.**
  **Done when:** A supported natural-language request queries or changes the actual investigation dashboard using Studio's agent integration, within the configured boundaries.
  **Verify:** Ask for completed payments with missing tickets, change the dataset, and repeat. Inspect the actual returned records and widget changes rather than accepting a canned answer.

- [ ] **CC-048. Finish the operator journey and its error states.**
  **Done when:** Starting, inspecting, cancelling, comparing, and exporting work end to end. Loading, empty, unavailable-provider, and missing-evidence states are legible; essential controls work by keyboard and at the documented viewport sizes.
  **Verify:** Perform one focused browser walkthrough covering the main journey and concrete failure states. Save observed defects and fixes rather than counting screens.

### Phase 9: Sponsor proof, durable orchestration, and portable delivery
**Gate:** Claimed integrations are exercised, and the investigator can survive realistic interruptions.

- [x] **CC-049. Handle KERNEL interruption and recording provenance.**
  **Done when:** Browser session failures are reflected in run state, partial evidence is retained, and recordings remain linked to the correct investigation. A local-browser fallback is labelled accurately.
  **Verify:** Interrupt one KERNEL session and inspect recovery or explicit failure. Confirm a saved session artifact is not presented as a new live run.

- [ ] **CC-050. Execute the Postman export.**
  **Done when:** A valid collection and environment template perform the documented API verification, extract relevant identifiers, and assert meaningful status, amount, and correlation conditions.
  **Verify:** Import and run the actual exported collection. Use fresh or explicitly selected observed IDs, and keep secrets outside the collection.

- [x] **CC-051. Prove APIMatic's actual development contribution.**
  **Done when:** A real Context Plugin interaction informs a concrete PayPal implementation decision, and the sponsor ledger describes that development role accurately.
  **Verify:** Save sanitized request/output evidence and the resulting implementation reference. Do not describe the plugin as a runtime payment verifier.

- [x] **CC-052. Survive duplicate jobs and worker restarts.**
  **Done when:** Durable run state, job ownership, pending approvals, and operation identities prevent an orchestration retry or competing worker from silently duplicating a payment or entitlement action.
  **Verify:** Run one focused concurrent-claim check and terminate a worker at a meaningful boundary. Inspect the resumed run, operation journal, and resulting counts.

- [x] **CC-053. Keep experiments isolated and evidence safe to share.**
  **Done when:** Run namespaces, fault settings, secrets, and recordings remain isolated. Public exports exclude credentials and unnecessary buyer data. Recorded replay cannot accidentally fall through to a live provider.
  **Verify:** Run two successive experiments with different faults, inspect export contents, and prove an unsupported replay interaction fails without an external call.

- [x] **CC-054. Package portable runtime and access instructions.**
  **Done when:** The web application, API, database, and background worker have reproducible startup and configuration instructions on the selected environment. KERNEL and webhook reachability are addressed. Render is absent from runtime dependencies and deployment configuration.
  **Verify:** Start the documented package in a fresh environment or the chosen authorized deployment and exercise its health and reachability checks. Do not substitute a static frontend for the working backend.

### Phase 10: Independent verification and submission-ready handoff
**Gate:** The product can be run and assessed from its delivered artifacts, with no unsupported completion claim.

- [x] **CC-055. Run meaningful automated release checks.**
  **Done when:** The configured build, types, lint where applicable, and focused behavior checks pass. Required test groups execute actual cases, and any unavailable live integration is reported as unverified.
  **Verify:** Save the current-build output and executed/skipped counts. Separate offline CI from controlled sandbox verification; missing credentials cannot silently turn a required integration gate green.

- [ ] **CC-056. Perform the clean-start acceptance walkthrough.**
  **Done when:** A clean checkout or the exact delivered build supports configuration, a real investigation, an inspectable finding, reproduction export, and a repaired comparison using documented steps.
  **Verify:** Use the delivered instructions, not the author's private setup notes. Record the source revision, actual flow, external dependencies, and any missing step.

- [ ] **CC-057. Obtain an independent acceptance review.**
  **Done when:** A reviewer inspects the frozen build, reruns the core regression and export, and challenges fresh-sandbox and sponsor claims. Every blocking finding is resolved or leaves the relevant box open.
  **Verify:** Save the review report with specific criteria, commands, inspected artifacts, and unresolved findings. A second summary of the builder's assertions is not a review.

- [x] **CC-058. Finish the repository and technical explanation.**
  **Done when:** Source, license, setup, architecture, adapter contract, environment template, limitations, reproduction commands, and a truthful sponsor-use ledger are complete. Published repository access is verified when publication is authorized.
  **Verify:** Inspect the actual repository from a clean reader's perspective. If required public access is still pending, keep the relevant release status open rather than claiming submission readiness.

- [ ] **CC-059. Produce the truthful demonstration and handoff materials.**
  **Done when:** The recorded demo stays under three minutes and shows the complaint, actual mismatch evidence, labelled recorded reduction, and fresh repaired result. Submission text and required links describe only demonstrated capabilities.
  **Verify:** Watch the exported video, measure its duration, inspect the links and factual claims, and confirm the required public video access when authorized. A script alone does not count as a completed video.

- [ ] **CC-060. Issue the final evidence-backed release verdict.**
  **Done when:** The release checker validates CC-001 through CC-059, verifies relevant evidence freshness, and writes an inspected final report covering product behavior, actual sandbox runs, recorded replays, integrations, and remaining limitations.
  **Verify:** Complete the release audit before checking this item, then confirm the final count is 60/60. If any required item is blocked, failed, stale, or missing proof, report the exact count and do not declare the project complete. Preparing the handoff does not itself submit the project to Devpost.

## 6. Phase review protocol

Use two roles:

**Builder:** Implements the selected items, runs relevant checks, fixes failures, and assembles evidence.

**Verifier:** Reviews a frozen source snapshot independently, reads acceptance conditions, inspects actual outputs, and reruns the important behaviors. The verifier should not accept the builder's conclusion without proof. Keep it read-only against the source being reviewed; any temporary adversarial checks belong in a separate disposable location.

The coordinator owns the checklist updates. A failed review returns the item to the builder. Review every phase and the high-risk payment, discovery, reproduction, and repair gates. Do not review every small formatting change.

An independent agent is additional scrutiny, not mathematical independence or a guarantee. A real transaction record, executable failing test, and fresh repair verification remain more persuasive than two agreeing narratives.

Freeze the relevant source while a reviewer tests it. Record the reviewed revision. If the builder changes behavior afterward, reopen only the checks that change invalidates.

## 7. Completion checker specification

CC-006 should implement three modes. The names below are proposed interfaces, not commands supplied by this planning file.

- Progress mode validates the checklist structure and evidence behind existing checkmarks. It prints the verified count and open states. An incomplete but honest project is allowed.
- Phase mode requires every requirement and prerequisite of the selected phase to be verified with usable, sufficiently current evidence.
- Release mode requires CC-001 through CC-059, then writes the audit used to decide CC-060. It does not require its own final audit to exist before it can run.

At minimum, reject duplicate or missing requirement IDs, checked items without verification records, missing referenced files, stale relevant hashes, wrong evidence mode, unmet prerequisites, and unresolved review findings that invalidate the claimed condition.

Do not mark work verified because a log file is nonempty. The reviewer and relevant executable checks must establish the claim. A log that says "all good" is not an assertion of the specific payment or delivery outcome.

Use routine progress validation in CI. Keep real sandbox approval-dependent checks in an explicit controlled verification path. Do not make a normal early development commit pretend all 60 requirements are complete.

## 8. Short AGENTS.md block

Merge this into existing repository guidance:

~~~markdown
## CrashCart completion contract

BUILD_CHECKLIST.md defines the agreed scope and acceptance criteria. STATUS.md records current unfinished work and blockers. Start a build session by reading the current status and relevant phase. Read other documents when that work requires them.

Only verified requirements may receive [x]. Code written, a passing build, or a screenshot is insufficient when the requirement calls for runtime or integration behavior. Save the actual verification result and supporting artifacts under evidence/CC-NNN/ and identify the tested source revision.

Distinguish local tests, actual sandbox transactions, recorded replay, and fresh sandbox verification. Never silently replace a required provider integration with a mock. Missing credentials or approval are blockers for that proof, not successful completion.

Implement in small batches within a phase, run the relevant checks, fix failures, update evidence, and obtain phase review. Continue automatically to the next unblocked work when its prerequisites are satisfied. Do not stop at the first implementation or ask for routine confirmation to continue already-authorized work.

Preserve the approved invariant, deadline, fault scope, and acceptance conditions. Do not weaken tests, suppress findings, change the expected answer, or remove requirements to manufacture a pass. Record any proposed scope change separately.

Relevant code, configuration, prompt, fixture, or assertion changes make affected evidence stale. Reopen and reverify those requirements. Do not rerun unrelated expensive checks solely because documentation changed.

The runtime investigator proposes hypotheses and tests. Deterministic code decides payment and entitlement verdicts. A fixed version must pass the same meaningful test that fails on the defective version.

Use only owned registered merchant fixtures and sandbox payments for this build. Render is excluded. Follow existing permissions and spending limits; a build instruction does not authorize new spending, public posting, or account changes beyond the user's authorization.

If blocked, record the exact missing dependency and continue independent authorized work. Ask only for the smallest necessary input once useful unblocked work is exhausted or that input is needed to proceed.

Before ending, update STATUS.md with verified IDs, evidence, failed or blocked IDs, and the next action. Report the verified count accurately. Say "project complete" only after the final release gate passes.
~~~

## 9. Prompts to give Codex

### First build prompt

~~~text
Build CrashCart using AGENTS.md and BUILD_CHECKLIST.md as the acceptance contract.

First inspect the repository, preserve existing work, and initialize STATUS.md with the actual current state. Keep every checklist item unchecked until its acceptance condition has been exercised and the evidence recorded.

Work through the phases in dependency order. Use small implementation batches and relevant verification. At phase boundaries, ask an independent reviewer agent to inspect the frozen source and actual evidence. Resolve findings and continue automatically to the next unblocked work.

Do not stop after scaffolding, UI creation, or a first implementation. Complete the authorized runnable behavior, inspect it, and fix failures. If an external dependency blocks one requirement, record that exact blocker and continue independent work.

Do not silently use mocks for required real integrations. Distinguish original sandbox executions, local recorded replay, and fresh sandbox verification. Keep Render out.

Your final report must state verified N/60, the evidence for new checkmarks, open or stale items, exact blockers, and the next action. Do not call the project complete unless CC-060 passes.
~~~

### Resume prompt

~~~text
Resume CrashCart from the current repository state.

Read AGENTS.md, STATUS.md, and the current phase of BUILD_CHECKLIST.md. Check whether relevant changes invalidated any previously recorded proof. Do not restart completed work without a concrete reason.

Continue with the next unblocked requirement, verify it, save evidence, and update the checklist only when earned. Continue through phase review and into subsequent authorized work. Leave a precise status record if an external blocker or session limit prevents completion.
~~~

### Independent audit prompt

~~~text
Act as CrashCart's independent acceptance verifier.

Treat the builder's summary as an unverified claim. Read the applicable requirements, inspect the frozen source revision, open its evidence, and run the focused checks that can establish or refute the claims.

Prioritize the actual sandbox capture, independent payment and ticket reads, unseen-seed investigation, executable reduction, clean exported reproduction, fresh verification, unchanged repair test, and real sponsor interactions.

Report VERIFIED, FAILED, or UNVERIFIABLE for each reviewed item, with specific evidence. Identify unchecked dependencies and stale source proof. Do not modify application code, rewrite acceptance conditions, or infer success from a green build alone.
~~~

## 10. STATUS.md starting template

~~~markdown
# CrashCart build status

Verified: 0/60
Current phase: 1
Current source revision: not established
Release gate: NOT RUN
Render: excluded

## Current work
- Requirement:
- State:
- Next concrete action:

## Verified in this session
None.

## Blockers
None identified yet. This does not imply credentials or connectivity are configured.

## Failed or stale requirements
None identified yet. No requirements have been verified.

## Evidence and review
- Relevant run IDs:
- Verification records:
- Reviewer result:

## Next session
Start by inspecting the repository and current phase. Preserve existing work.
~~~

At the end of each session, replace the empty fields with actual observations. A useful status report identifies verified IDs, open IDs, tested revision, evidence paths, exact missing prerequisites, and the next executable action.

## 11. Facts behind the plan

The requirements and workflow above are proposed project decisions. The following official sources establish the external behaviors and event obligations used in those decisions, checked on 22 October 2026.

- [Codex repository instructions](https://learn.chatgpt.com/docs/agent-configuration/agents-md): AGENTS.md is discovered as repository guidance. Other filenames here are our conventions.
- [OpenAI guidance on concise instructions and completion boundaries](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra): keep guidance relevant and define whether running, inspecting, and fixing the result is included in completion.
- [PayPal idempotency](https://developer.paypal.com/api/rest/reference/idempotency): supported operations use PayPal-Request-Id; endpoint support and retention matter.
- [PayPal order retrieval](https://developer.paypal.com/api/orders/v2/orders-get): order details can be retrieved by order ID.
- [AG Grid sponsor brief](https://paypalaihackathon.devpost.com/details/aggrid): the sponsor emphasizes AG Studio, custom widgets, layouts, and agent integration.
- [KERNEL sponsor brief](https://paypalaihackathon.devpost.com/details/kernel): browser integration and recordings support the planned journey.
- [APIMatic sponsor brief](https://paypalaihackathon.devpost.com/details/apimatic): the Context Plugin supports PayPal integration development.
- [Hackathon rules](https://paypalaihackathon.devpost.com/rules): a functional accessible build or complete run instructions, public open-source repository, and public YouTube demonstration under three minutes are required for submission readiness.

Recheck provider documentation at implementation time for exact API and SDK behavior. Do not treat this planning document as a substitute for the current endpoint reference.

