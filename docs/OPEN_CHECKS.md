# Remaining acceptance work

Reviewed 4 November 2026. The frozen private build has **44/60 verified** and
zero stale requirements. No open requirement was promoted by this review.
The public repository includes reproducible source tests and curated replay
inputs; it excludes the private acceptance archive. Additive judge-access work
has separate public tests and does not inherit live-provider acceptance.

## Failed requirements first

| Check | Root cause / current result | Exact next evidence |
| --- | --- | --- |
| CC-023 | The earlier webhook verifier reserialized signed JSON. Current code preserves the original bytes. Fresh local raw-body and PayPal-adapter regressions passed: 27 tests, 0 failures. | Authentic corrected PayPal notification, exact-event resend, bad-signature rejection, and inspected ticket count. Local injected responses cannot accept this check. |
| CC-035 | The regression reproduces the failure, but its original faulty-checkout recording is absent. | Recover the original hash-bound recording, or record a new authorized faulty checkout and export its matching regression. An unrelated healthy recording or local replay video is insufficient. |

## Remaining checks, in requested order

| Check / state | Missing acceptance evidence or prerequisite |
| --- | --- |
| CC-040 / in progress | New namespace, order, buyer approval and transaction for the reduced witness; depends on CC-036 and CC-038. |
| CC-042 / in progress | Fresh repaired purchase, equivalent fault and unchanged promise, with provider, ticket and browser result; depends on CC-024, CC-040 and CC-041. |
| CC-059 / pending | An exported public video under three minutes showing the required original and fresh journey; script alone is insufficient. Depends on CC-038, CC-040, CC-042, CC-048 and CC-058. |
| CC-046 / implemented, unverified | Complete actual Studio selection/comparison with provenance and no stale cross-case data; depends on CC-040. Recorded-only comparison is supplemental. |
| CC-048 / implemented, unverified | Complete operator start/inspect/cancel/compare/export, keyboard and responsive states; depends on CC-046. |
| CC-050 / implemented, unverified | CC-035. Current exported collection was rerun on 4 November: 7 local assertions and 48 assertions across six GETs of copied historical Sandbox records passed; missing proof failed as expected. This is stored-observation inspection, not a fresh provider call. |
| CC-057 / implemented, unverified | Independent complete acceptance review; depends on CC-050, CC-055 and CC-056. Partial review is not full acceptance. |
| CC-024 / blocked | Actual payment interruption/restart recovery; supporting historical proof exists, but CC-023 remains unmet. |
| CC-036 / blocked | Complete regression from a clean environment; depends on the missing recording in CC-035. |
| CC-038 / blocked | Real agent discovery of the still-undisclosed seeded defect and deterministic confirmation. Protocol CC-037 is accepted; known-case queries are not discovery. |
| CC-041 / blocked | Same meaningful regression fails defective and passes repaired, with complete CC-035 artifact. A newly executed recorded pair is useful but does not replace the recording. |
| CC-052 / blocked | CC-024. Seventeen additional local competing-worker/restart groups passed with synthetic payment replies and exactly one ticket; actual provider recovery remains distinct. |
| CC-056 / blocked | Full clean-start fresh investigation, export and repair comparison; depends on CC-036, CC-042 and CC-048. Keyless replay access is a different, explicitly labelled path. |
| CC-060 / blocked | All earlier checks and required independent phase/release reviews. Project incomplete. |

## Owner and external dependencies

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

CC-023 can be exercised independently through local Safari without KERNEL. A
scoped notification-only harness is being prepared; it is not activated. Safari
control recovered after two timeouts, but Developer still redirects to sign-in; authenticated buyer access is unconfirmed.
No fresh payment, public window or webhook has started. This is an access and
verification blocker, not a request for another blanket approval.

Part F remains gated: Part A is incomplete while the required live-provider evidence remains blocked. No prize-lane feature is added to bypass these dependencies.
