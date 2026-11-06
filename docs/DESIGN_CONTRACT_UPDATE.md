# Design decision amendment — 6 November 2026

The owner requested CC IDs and descriptions aligned with the new design decisions, then requested a stale-item audit. Existing **CC-001–CC-060 IDs remain stable** so historical artifacts and dependencies do not point at different requirements. No requirement is removed, renumbered or marked done by this edit.

## Current product surfaces

- **Public entry:** a warm, user-facing landing page with an interactive keyless recorded investigation, case comparison, inspectable records and executable download. It makes no new payment or model call.
- **Configured workspace:** new investigations, AG Studio, linked evidence, cancellation, comparison and export with configured services. The keyless page is not its substitute.
- **Recording and fresh verification:** actual case-linked footage and new test payments retain their original proof requirements. Partial footage and historical replay remain labelled as such.

Features remain frozen. This amendment clarifies existing product behavior and verification coverage; it does not authorize new services, payments, recording, deployment or submission.

## Updated CC descriptions

| CC IDs | Current design description | Supporting checks |
| --- | --- | --- |
| CC-001, CC-043, CC-058 | Customer problem first; separate Explore recorded example from Start a new investigation; concise product-story documentation. | DV-01, DV-08, DV-12 |
| CC-032, CC-035, CC-036 | Keyless replay/export access, with exact provenance and the original matching-artifact requirement retained. | DV-03, DV-07, DV-14 |
| CC-040, CC-041, CC-042 | Distinguish saved comparisons, proof of the repair and a genuinely new repaired purchase. | DV-03, DV-08, DV-12 |
| CC-044, CC-048 | Plain-language states, recovery, keyboard/phone usability and reduced-motion behavior on the correct surface. | DV-04–06, DV-08–13 |
| CC-045, CC-047 | Actual Studio widgets and agent interaction are separate from the keyless recorded page. | DV-12 |
| CC-046, CC-049, CC-053 | Selected-case records, download and footage stay linked; unavailable or partial evidence remains explicit and private. | DV-02, DV-03, DV-12–14 |
| CC-054, CC-055, CC-056 | Separate keyless access, configured runtime, local verification, CI and hosted behavior. | DV-01–11, DV-12 |
| CC-057, CC-059, CC-060 | Review source-bound evidence; tell a truthful product story; retain video and full release gates. | All applicable DV rows; original CC prerequisites still apply |

The updated descriptions appear directly beneath the corresponding CC IDs in BUILD_CHECKLIST.md. Ten open entries also have clearer titles. Four open requirements have additive acceptance clarifications:

- **CC-046:** selected footage/download identity and readable labels with exact provenance available.
- **CC-048:** distinct recorded entry, reduced motion, recovery without invented results or payment retries; explicit keyboard/phone/motion and assistive-technology scope.
- **CC-056:** exercise the keyless path as well as the original configured acceptance journey.
- **CC-059:** product-story presentation and accurate identification of recorded, historical and fresh segments in the actual exported video.

No original requirement is weakened: the USD29 amount, one-ticket promise, 60-second deadline, real provider proof, recording, held-out discovery, sponsor execution and all dependencies remain. A script is not a video; a recorded comparison is not a fresh repaired payment.

## Freshness and evidence

The 47 checked requirements retain identical title/Done when/Verify hashes and original source-bound evidence. Their new design descriptions explain the applicable surface; they do not claim that an old run verified the new public page. The 13 open requirements stay open; changed acceptance in an open entry must be proved against the new text before it can be checked. No old verification record is rewritten to simulate that proof.

At the v74 amendment, DV-01–07 retained dated limited results, DV-11 had local error/recovery evidence, and DV-08–10/DV-12–14 were open. The subsequent [v75 local copy review](../evidence/runs/submission-ready/product-readability-v75.json) now passes DV-08 and rechecks affected interactions; DV-09/10 and DV-12–14 remain unchecked. The GitHub billing lock means the hosted script is older than the pushed repair; **hosted DV-11 remains unverified**, rather than being presented as current. See [hosting readback](../evidence/runs/submission-ready/hosting-blocker-v72.json).

The audit compares all 60 IDs, acceptance hashes and checkbox states, checks unchanged rules/source, runs completion validation, and obtains independent review. [Audit receipt](../evidence/runs/submission-ready/design-contract-v74.json). This is documentation/acceptance review, not new runtime or provider proof. Count: **47/60**; project incomplete.

## Current freshness follow-through — v76

All 60 private/public acceptance entries still match and the original validator reports 47/60 with no stale checked records. The v76 selected-state CSS amendment was separately reverified for affected local selection/focus/layout behavior; historical hosted results were not transferred to it. Obsolete active copy-review, suite and CC-042 blocker wording was corrected. OS-motion and screen-reader coverage remains explicitly partial in [DESIGN_VERIFICATION.md](DESIGN_VERIFICATION.md). [Current source-bound audit](../evidence/runs/submission-ready/accessibility-v76.json).
