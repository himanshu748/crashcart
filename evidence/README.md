# Public replay evidence

Two curated historical inputs let a reader reproduce the merchant behavior
without payment credentials, network access or the private acceptance archive.
Their original times, identities, proof modes and fixed 60-second promise are
preserved. Neither is a fresh payment or a new AI investigation.

| Input | Faulty merchant | Healthy merchant | Purpose |
| --- | --- | --- | --- |
| [`early-response-loss-input.json`](runs/paypal-live/early-response-loss-input.json) | `paid_without_ticket`, zero tickets, exit 1 | `ticket_delivered_once_on_time`, one ticket, exit 0 | Same-input repair comparison used by `scripts/judge.sh` |
| [`response-loss-input.json`](runs/paypal-live/response-loss-input.json) | `paid_without_ticket`, zero tickets, exit 1 | `ticket_delivered_late`, exit 1 | Preserved late-read negative example; it is not retimed into a success |

Reproduce both expected outcomes with the
[README commands](../README.md#reproduce-the-comparison). The regression test in
[`tests/test_public_replay.py`](../tests/test_public_replay.py) checks both
merchant variants, retains the late failure and imports separate recorded cases.
The production Store and invariant decide the outcomes; saved verdicts are not
replayed as answers.

The exact earlier input is SHA-256
`07609306e1310420c49e9908ee26b2da361e42028ea6f40b5d19005d47498288`.
The exact original late input is SHA-256
`c82dc46148d2dc985de77d051177c67d1d9c7d7d9a760242d2a3758e3d91f88e`.
The earlier file retains all 12 executable steps and 15 source records. Its
pre-existing payment-source redaction remains declared; the original create-body
hash is not verifiable after that redaction. No missing browser video is invented.

## What is private

The maintainer's acceptance archive contains source-bound verification records,
payment/account receipts, licence details, databases and recordings. Those are
not public artifacts or dependencies of the keyless review. Historical source
labels in the two JSON files do not independently authenticate provider activity.

The strict `scripts/check_completion.py` gate needs the full private canonical
records and their bound artifacts. A public clone cannot reproduce that private
44/60 audit. The public source tests and keyless replay checks are separately
reproducible; they do not close the missing original/fresh-payment evidence.
[STATUS.md](../STATUS.md) and [open checks](../docs/OPEN_CHECKS.md) preserve that
boundary and the remaining work. CC-060 remains the completion gate.
