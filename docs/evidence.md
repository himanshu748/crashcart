# Evidence and completion validation

This is a maintainer guide for a **full private acceptance workspace**. The public
source checkout intentionally excludes canonical verification records and bound
operational artifacts, apart from the single curated historical replay input.
Paths and JSON below describe records to create during an actual verification;
they are examples, not claims that those files are delivered or passed. Public CI
runs source tests and frontend checks; it does not run the private artifact gate.
See [development status](archive/STATUS.md) and the [public evidence boundary](../evidence/README.md).

The checklist owns the acceptance conditions; the coordinator owns checkmarks.
Implementation, successful builds, synthetic unit-test fixtures and screenshots
cannot establish an unexercised runtime condition. The checker validates the
shape, provenance bindings, freshness and prerequisites of a claim. It cannot
authenticate an invented narrative or decide whether a test is meaningful.
An independent reviewer must inspect actual artifacts and rerun important cases.

## Commands

From the repository root, using the documented Python runtime:

```sh
python3 scripts/check_completion.py progress
python3 scripts/check_completion.py phase --phase 1
python3 scripts/check_completion.py release --report evidence/CC-060/release-report.json
python3 -m unittest discover -s tests -p 'test_completion.py' -v
```

Exit 0 means the selected mechanical gate passed. Exit 1 means invalid claims or
unfinished requirements prevent that gate. Invalid command arguments use exit 2.
Progress permits a truthful incomplete project and reports open record states.
A checked requirement must have valid evidence, and every fixed prerequisite
must also have valid evidence. Phase mode requires all six phase requirements
and independent phase review. Release requires CC-001 through CC-059 and their
phase reviews. It writes an audit even on failure; `ok: false` is never a release.
Release deliberately does not inspect CC-060's own record, preventing circular
dependence on the audit it is about to generate.

The JSON object in `scripts/requirements.json` fixes each item's permitted proof
modes and dependencies. A verification record cannot choose a weaker mode or
omit prerequisites. Changes to these rules require deliberate review; every
verified record binds their current SHA-256. The rules do not authorize scope
changes. A requirement's acceptance text is hashed separately from its checkbox,
so checking a box does not invalidate a run. Other prose edits do not change this
item's acceptance hash.

## Verification records

Each checked requirement needs `evidence/CC-NNN/verification.json` and every file
it references. Paths are relative to the repository root. Absolute paths,
parent traversal, and symlinks escaping the root fail validation. The example
below is a schema illustration, not evidence to copy as a completed claim:

```json
{
  "item_id": "CC-006",
  "status": "VERIFIED",
  "mode": "LOCAL_TEST",
  "source_commit": null,
  "source_snapshot": "evidence/snapshots/foundation-run",
  "relevant_source_hashes": {
    "scripts/requirements.json": "<actual sha256>",
    "scripts/check_completion.py": "<actual sha256>",
    "tests/test_completion.py": "<actual sha256>"
  },
  "acceptance_sha256": "<actual per-item acceptance hash>",
  "run_id": "<actual run identifier>",
  "environment": {
    "python": "<actual interpreter version>",
    "platform": "<actual operating system>",
    "workspace": "<description of isolated run directory>"
  },
  "command_or_action": "python3 -m unittest discover -s tests -p 'test_completion.py' -v",
  "expected_result": "Named rejection tests pass; honest incomplete progress is allowed",
  "observed_result": "<actual inspected result and executed count>",
  "expected_exit_code": 0,
  "observed_exit_code": 0,
  "executed_at": "<actual ISO 8601 timestamp with timezone>",
  "evidence_files": ["evidence/CC-006/tests.log"],
  "evidence_sha256": {"evidence/CC-006/tests.log": "<actual sha256>"},
  "dependencies": ["CC-003"],
  "result": {
    "outcome": "PASS",
    "assertions": [
      {
        "name": "Unsupported checkmark, absent artifact and stale source are rejected",
        "passed": true,
        "evidence": "evidence/CC-006/tests.log"
      }
    ]
  },
  "review": null
}
```

`source_snapshot` is a **string directory path**, not an object. The directory
mirrors each file in `relevant_source_hashes`: for example,
`evidence/snapshots/foundation-run/scripts/check_completion.py` contains the exact
bytes tested. Preserve all behavior-affecting source, configuration, fixtures,
prompts and assertions for that requirement. Record every relevant hash, including
`scripts/requirements.json`. A snapshot containing only policy metadata cannot
substantiate a runtime claim; the independent reviewer checks source coverage.
Snapshots must live under `evidence/` and must never include secrets.

For an unborn repository, use `source_commit: null` plus the snapshot. A committed
checkout may supply its full 40-character SHA without a snapshot only when the
commit contains each tested file with exactly the declared hash. Uncommitted
changes require the snapshot even when a base commit exists. Do not claim a clean
commit as the tested source when a working tree supplied different code.

Obtain the current acceptance hashes without constructing a new definition:

```python
from pathlib import Path
from scripts.check_completion import checklist_items, digest

root = Path.cwd()
items, errors = checklist_items((root / "docs/archive/BUILD_CHECKLIST.md").read_text())
assert not errors
acceptance_sha256 = items["CC-006"]["acceptance_sha256"]
rules_sha256 = digest(root / "scripts/requirements.json")
```

Each structured assertion names the actual condition inspected, says whether it
passed, and references a hashed artifact containing its supporting output.
Generic text such as "all good" is not meaningful proof. An expected failing
regression may record matching nonzero expected and actual exit codes, but its
assertions and raw output must prove the specific expected mismatch rather than
an unrelated crash. Only explicit document inspection may omit exit codes.

Unverified records may use any honest open state: `PENDING`, `IN_PROGRESS`,
`IMPLEMENTED_UNVERIFIED`, `BLOCKED`, `FAILED`, or `STALE`. Keep their checkboxes
open, record exact blockers in STATUS.md, and preserve prior artifacts. An
unchecked item with a record still claiming `VERIFIED` is inconsistent and fails.

## Proof modes

- `DOCUMENT_REVIEW`: actual inspection of a written contract, protocol or artifact.
- `LOCAL_TEST`: executed local behavior; no implication of an actual provider call.
- `LIVE_SANDBOX`: actual original sandbox execution and independent provider data.
- `RECORDED_REPLAY`: replay of captured inputs, with no new payment or browser call.
- `FRESH_SANDBOX`: a new owned namespace, order, approval and actual transaction.
- `SPONSOR_SERVICE`: actual model, KERNEL, Studio or other sponsor interaction.

The allowed set for each item is explicit in the rules. Labels alone do not prove
origin: preserve sanitized provider/session identifiers and real output. For
fresh verification, the reviewer compares the original and new run, namespace,
order and capture IDs. Model access, sandbox access and sponsor licenses cannot
be substituted by a mock while retaining a provider mode. Unit-test receipts in
`tests/test_completion.py` are deliberately synthetic adversarial checker inputs;
they are not product, provider or release proof.

## Independent review

Routine batch records may have `review: null`. Once reviewed, use a bound review
artifact and the following structure. CC-057 and CC-060 require an independent
review explicitly. Any supplied nonpassing review or unresolved blocking finding
invalidates that item's checkmark.

```json
{
  "reviewer": "<reviewer identity>",
  "independent": true,
  "result": "PASS",
  "evidence": "evidence/reviews/foundation-review.txt",
  "findings": []
}
```

Include that review artifact in the item's `evidence_files` and `evidence_sha256`.
Findings use `id`, `severity` (`blocking` for a blocker), and `status` (`open` or
`resolved`). Save commands, actual outcomes, frozen source hashes, inspected
artifacts and resolutions in the review artifact. Do not use a second summary of
the builder's claims as independent review.

For a completed phase, save `evidence/reviews/phase-N.json` with the review fields
above plus `item_ids` containing all six phase IDs and `verification_sha256`
mapping each ID to the current hash of its verification.json. A changed record
makes that phase review stale. Partial phase review may be saved as a report and
attached to the individually reviewed requirements, but cannot pass the phase.
The phase 10 release review initially covers CC-055 through CC-059: it cannot
require a CC-060 audit that has not been generated yet.

After a successful release audit, a reviewer inspects the report and only then
creates CC-060's record. That record additionally sets `release_report` to the
root-relative audit path and includes it among hashed evidence files. Progress
validation then confirms 60/60, including the report's successful first-59 result
and unchanged verification-record hashes. The release report also freezes every
phase-review JSON and its referenced inspection artifact by SHA-256. A later
failed review, deleted review, or changed review artifact reopens CC-060 even if
all 59 individual verification records remain unchanged. Completing this local gate does not
publish, deploy, spend, commit, push or submit anything.
