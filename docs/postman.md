# Executable API verification export

Import `exports/crashcart.postman_collection.json` and the blank
`exports/crashcart.postman_environment.json` into Postman, or run the v2.1
collection with pinned **Newman 6.2.1**. No Postman account or API key is required
for this local runner. The export contains only GET requests and cannot create,
approve, capture or reconcile a payment.

The two folders have different claims:

- **Local smoke** checks the running API/database and the registered workshop's
  2900-minor-unit USD price and fixed 60-second recovery promise. It requires no
  payment credentials and does not prove a sandbox purchase.
- **Observed sandbox evidence** inspects one explicitly selected actual sandbox
  run and reads its merchant entitlement. It requires independent order-retrieval
  evidence containing the correlated completed capture, exact amount, currency,
  purchase IDs, operation journal, timestamp and expected ticket count. Missing
  proof fails assertions; the folder never skips an integration check or falls
  back to recorded/synthetic payment data. Reading stored observations is not
  fresh sandbox execution.

## Reproduce the local checks

Install the pinned runner into a new temporary directory, preserving the lockfile:

```sh
crashcart_runner_dir="$(mktemp -d)"
mkdir -p evidence/runs
crashcart_postman_evidence_dir="$(mktemp -d "$PWD/evidence/runs/postman-XXXXXXXX")"
npm install --prefix "$crashcart_runner_dir" --cache "$crashcart_runner_dir/npm-cache" --ignore-scripts --no-audit --no-fund --save-exact newman@6.2.1
python3 scripts/verify_postman.py --newman "$crashcart_runner_dir/node_modules/.bin/newman" --evidence-dir "$crashcart_postman_evidence_dir"
```

The verification script starts the actual API on an ephemeral loopback port with
a new SQLite database, a private disposable operator token, and all provider
enables set to zero. It runs the smoke folder, then deliberately attempts the
observed-evidence folder with blank credentials and run ID to prove that missing
proof produces a failing exit code. It stops the temporary server afterward.
Loopback binding may require the execution sandbox's normal approval mechanism.

New artifacts go to the fresh `$crashcart_postman_evidence_dir`: CLI output,
machine-readable Newman reports, runner versions, and `execution.json` with exact
commands, exit codes, executed/failed/skipped counts and relevant source hashes.
The local-smoke reports contain blank provider credentials. The script checks
whether relevant source changed during its run.

Historical maintainer runs exercised local smoke, expected missing-proof
rejection and 48 assertions across saved sandbox records. Those private receipts
are not delivered public proof, and reading saved observations creates no new
payment or provider read. Run the collection against your own authorized data
and inspect its actual reports. Newman is a legacy runner for this v2.1 format;
this does not claim support for Postman v12 Native Git v3 collections. See the
official [Newman limitations](https://learning.postman.com/docs/reference/newman-cli/installing-running-newman/).

## Verify a selected real sandbox run

After normal buyer approval, capture and independent reconciliation have already
been performed through the authorized application journey, copy the environment
template to the git-ignored `.env.postman.private.json`. Set these private values:

| Variable | Required value |
| --- | --- |
| `base_url` | The running owned CrashCart API origin |
| `operator_token` | Its operator credential; keep it private |
| `run_id` | The exact observed `LIVE_SANDBOX` or `FRESH_SANDBOX` run ID |
| `expected_ticket_count` | Explicit expected count for this experiment, normally `1` for healthy or `0` for a paid-without-ticket finding |

Use the unchanged collection's **Observed sandbox evidence** folder. With the
runner path established above:

```sh
"$crashcart_runner_dir/node_modules/.bin/newman" run exports/crashcart.postman_collection.json --environment .env.postman.private.json --folder "Observed sandbox evidence" --timeout-request 5000 --reporters cli
```

The first request extracts the selected purchase, order and capture identities;
the second checks the merchant adapter against that selection. The collection
does not request a new provider read. To obtain a new read, use the application's
authorized reconciliation action beforehand and inspect the resulting event.

Keep secrets outside the collection. Do not publish a raw Newman JSON report from
a configured run: it can contain request authorization headers and environment
values. Save the actual CLI outcome and sanitize any detailed artifacts before
adding them to evidence. Actual provider records and independent artifact
inspection remain necessary; passing JavaScript assertions cannot authenticate
fabricated database contents.

**CC-050 remains open through its prerequisite chain.** The local smoke,
missing-proof rejection and observed paid-order collection have run. CC-010 has
historical independently confirmed payment proof; current-source status follows
[development status](../STATUS.md) during revalidation. CC-035's full accepted replay/export chain remains
open. This collection reads observed records; it does not replace an executable
regression or fresh provider verification.
