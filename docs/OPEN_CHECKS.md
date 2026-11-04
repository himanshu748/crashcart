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
| CC-050 / implemented, unverified | Current exported Postman collection run and CC-035. Historical execution passed 48 assertions; this does not repair its artifact dependency. |
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
- A permitted, bounded real browser/model execution path. No spending or service
  usage is authorized by the current task. Eight previous remote session grants
  are consumed. KERNEL has been asked to clarify an absolute lifetime/billing
  bound; the sent message is not a provider answer.
- The original faulty-checkout recording, or access/authorization to create a
  properly recorded replacement experiment.
- Applicable AG Studio permission for the full sponsor workspace through judging.
  The keyless recorded review must not require or redistribute a private licence.
- The final demonstration video, which the owner will record; review its contents,
  duration and public access before accepting CC-059. Never publish credentials.

Part F remains gated: Part A is incomplete under the no-service/no-spending
constraint. No prize-lane feature is added to bypass these dependencies.
