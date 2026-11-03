# CrashCart development status

This is a public source snapshot, not a deployed or completed release.

Verified locally: **3/60** as of 3 November 2026. The remaining accepted baseline
was 42/60 before the current frontend/dependency changes. Those changes reopened
**39 requirements as stale**; source review and browser revalidation must finish
before they can be restored. No new requirement is accepted by this publication.

## What you can run

- Warm product landing page with an interactive example and a private workspace.
- Owned workshop test-payment investigation, durable SQLite records and deterministic
  payment/ticket checks against exactly one ticket within 60 seconds.
- AG Studio integration and a separate Bryntum Community delivery-timing view.
- Bounded investigator, recorded offline replay and inspection/regression exports.

External capabilities require your own configuration, applicable licences and
authorized usage. Missing access fails explicitly. Local examples never replace
real payment, model, browser or fresh-verification evidence.

## Current verification boundary

Local workbench tests passed 356 Python tests, 35 focused tests, four configured
checks, 71 clean-package checks and 45 timing-model tests. These are local checks,
not fresh PayPal or KERNEL execution. Targeted Bryntum keyboard, pointer, filtering, refresh, HTTP-error and
320px/390px layout checks passed. Two asynchronous loading/navigation defects
were reproduced and repaired. Independent final source/evidence review remains
pending; the complete operator journey and accessibility validation remain open. Private raw evidence, account
receipts, databases, credentials and recordings are intentionally unpublished.

The sole curated historical replay tape under evidence/ is a sanitized test input.
It cannot independently re-establish the private acceptance ledger. The public CI
checks source behavior; the full private artifact gate remains separate and strict.

## Open acceptance work

- Failed: CC-023, CC-035.
- Blocked: CC-024, CC-036, CC-038, CC-041, CC-052, CC-056, CC-060.
- Implemented but unverified: CC-037, CC-039, CC-046, CC-048, CC-050, CC-057.
- In progress: CC-040, CC-042. Pending: CC-059.
- Stale: CC-002, CC-004, CC-005, CC-007 through CC-022, CC-025 through CC-034,
  CC-043 through CC-045, CC-047, CC-049, CC-051, CC-053 through CC-055, CC-058.

Main remaining gates include authentic payment notifications, the required original
failure recording, held-out discovery, fresh repair comparison, complete operator
journey, public demo video and final release. Source publication alone does not
satisfy these gates. No project-complete claim until **CC-060** passes.

Next action: finish current UI/runtime verification and independent evidence review,
then continue the remaining unblocked acceptance work. Render is excluded.
