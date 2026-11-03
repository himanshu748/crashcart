# Offline replay and reduction

This module re-executes payment confirmation and entitlement writes in a new SQLite database using the actual `Store` implementation, then runs the frozen `ticket-v1` invariant. It never reads a saved verdict. It imports no network client or live provider adapter and cannot fall through to PayPal or KERNEL.

The public checkout includes one curated historical response-loss input tape at
`evidence/runs/paypal-live/response-loss-input.json`. Its original source mode,
identities and times are preserved. Executing it now is **recorded replay**, not
a new transaction or fresh repair verification. Raw provider receipts and
recordings remain private. The tape's schema and hashes cannot independently
authenticate its historical origin. Synthetic unit fixtures remain `LOCAL_TEST`.

The invariant and recorded schedule stay fixed for both merchant variants. If
the first usable reconciliation is after the deadline, even the healthy variant
must fail late. A reduced tape can preserve defective failure while removing a
timely read required for healthy recovery. Never rewrite a timestamp or claim a
healthy pass to make a comparison look successful.

## API and provenance

`package_run(run, purchase, operations, events, source_hashes)` accepts rows from `Store` and the `MerchantService` event journal. It requires:

- The fixed `workshop-v1` fixture, unchanged `ticket-v1` invariant, and defective `response_loss` or `process_interrupt` fault.
- Both `order.create` and `order.capture` journal entries with distinct request IDs and original body hashes. An unredacted body must match its original SHA-256; the empty capture body cannot claim redaction. The sanitized request retains payment identities, intent and amounts. Buyer/return metadata is excluded and redacted top-level fields are listed. Replay explicitly reports an original hash as `unverifiable_after_redaction` when those fields prevent reconstruction; it does not call that hash verified.
- Provider `order_created` and actual `APPROVED` `pre_capture_read` records; harness `capture_transport_response`; provider `independent_order_read`; actual browser `customer_observation`; merchant `entitlement_read`; and harness `fault_activated` records. Interruption additionally requires the recorded `process_exit_boundary`.
- Matching run, purchase, order and capture identities, exactly one completed USD 29.00 capture, timezone-aware observation timestamps, and source-file hashes using relative paths.

`LOCAL_TEST` source must carry `synthetic: true`; replay and export keep that mode. Actual `LIVE_SANDBOX` or `FRESH_SANDBOX` source carries `synthetic: false`; its offline result is labelled `RECORDED_REPLAY`, never fresh sandbox. Schema validation cannot authenticate whether supplied observations truly came from a provider. Inspect the original service receipts and source provenance independently. A source hash is not proof of a transaction.

The package schema uses only allowlisted data fields and step types. Unknown interactions, changed invariants, missing observations, mismatched identities, duplicate JSON keys, oversized input, and absolute/traversing manifest paths are rejected. Browser text receives limited conventional credential/email redaction; inspect actual exported content before any authorized publication. The package stores sanitized browser observations; it does not claim to include an original browser video that was never recorded.

## Execution and clock

`replay(package, merchant="defective", steps=None)` executes the ordered steps in a fresh temporary database. A private instance of the Store module receives the recorded clock, without changing the application's shared clock. All confirmation constraints, ticket uniqueness and fulfillment guards execute against the real SQLite implementation. Original source identities remain in the tape; the output identifies their mapping into the isolated replay namespace.

At capture, the response-loss branch preserves unresolved merchant state. The interruption branch additionally reopens the durable Store at the recorded after-capture boundary. This is an offline simulation of process interruption, not proof that an operating-system process was killed. Independent recorded retrieval confirms payment. The defective merchant leaves delivery absent; the healthy merchant invokes `Store.fulfill` at that **same recorded retrieval time**. Repeated reconciliation still produces one ticket.

The fixed evaluation time must equal the latest captured merchant payload's `observed_at`. The output names that observation. A journal envelope appended later cannot extend the state-observation horizon, and later executable provider interactions require a subsequent merchant observation. A later browser observation is preserved as source evidence only and is excluded from executable steps beyond that horizon. A pre-order browser observation may have no order ID only before the first recorded order creation, with run and purchase identities still matched. Advancing only `evaluate_at` is rejected, so a three-second observation cannot become evidence of missing delivery beyond 60 seconds. The final merchant state is queried from the replay database at that bound time, including after reduction removes display steps.

Source records must retain chronological order. Exactly one fault activation must occur after observed approval and before the capture response in both source order and time. A process interruption additionally requires exactly one boundary after that response and before recovery/entitlement observations; response loss cannot claim this process boundary.

Healthy delivery cannot be backdated: if the first usable recorded reconciliation occurs after the 60-second deadline, healthy replay fails with `ticket_delivered_late`. A package without a timely read needs a new actual observation/run to establish timely recovery; changing timestamps would invalidate evidence.

## Reduction and command line

`reduce_package(package, max_candidates=16, repeats=3)` performs a bounded single-deletion search. Every candidate is validated; executable candidates run in their own database. Removing create, buyer approval or capture is rejected. Removing independent reconciliation yields inconclusive payment evidence and cannot preserve the target failure. Browser/merchant display steps may be removed while their original evidence remains in the source tape.

The report includes original/reduced sizes, candidate acceptance/rejection, budget, termination reason, and repeated failure signatures. Attempted candidates and actual executions are counted separately; a rejected prerequisite deletion is not reported as an executed merchant run. It describes the result as **smallest reproducer found within the search**; it does not claim global minimality. Replays verify that the paid-without-ticket signature persists, not merely any nonzero exit. Reduction can remove a timely redundant observation while preserving the defective failure; rerun the healthy comparison on the reduced artifact and report any resulting late-recovery failure honestly.

```sh
python3 -m crashcart.replay run input.json --merchant defective
python3 -m crashcart.replay run input.json --merchant healthy
python3 -m crashcart.replay reduce input.json --budget 16 --repeats 3
python3 -m crashcart.replay export input.json regression.zip
```

Exit codes are `0` for invariant PASS, `1` for invariant FAIL, `2` for INCONCLUSIVE, and `3` for invalid replay input. A meaningful defective result prints `signature: paid_without_ticket`. The healthy command uses the exact same input, invariant and schedule.

`export_package(package, destination)` refuses to overwrite an existing artifact. The zip contains the sanitized input, exact replay/Store/invariant sources, migration, README and SHA-256 manifest. Extract it into a clean folder, verify the manifest, and use the bundled commands with Python 3.11+; only the standard library is needed. Credentials and external setup are unnecessary for offline replay.

From the repository root, replay the included curated input directly:

```sh
python3 -m crashcart.replay run evidence/runs/paypal-live/response-loss-input.json --merchant defective
python3 -m crashcart.replay run evidence/runs/paypal-live/response-loss-input.json --merchant healthy
```

A defective paid-without-ticket result intentionally exits `1`; inspect its
specific signature rather than treating every nonzero result as reproduction.
The healthy result depends on the unchanged recorded timing and may also fail
late. Neither command makes a provider call or proves a new checkout.

To exercise a standalone export, choose a fresh temporary directory:

```sh
crashcart_repo="$PWD"
crashcart_replay_dir="$(mktemp -d)"
python3 -m crashcart.replay export evidence/runs/paypal-live/response-loss-input.json "$crashcart_replay_dir/regression.zip"
unzip "$crashcart_replay_dir/regression.zip" -d "$crashcart_replay_dir/extracted"
cd "$crashcart_replay_dir/extracted"
python3 -m crashcart.replay verify-manifest .
python3 -m crashcart.replay run input.json --merchant defective
```

The generated archive contains the standalone replay runtime, not the repository
test suite. Run tests separately from the source repository:

```sh
cd "$crashcart_repo"
python3 -m unittest tests.test_replay tests.test_replay_workspace -v
```

The tests include network-denied replay, unsupported-interaction refusal, namespace isolation, late-recovery control, duplicate reconciliation, bounded reduction, and execution of an exported artifact from a clean temporary directory. Adversarial cases reject a forged evaluation horizon, late/reordered fault boundaries and mismatched reconstructable request hashes. Synthetic defective execution must exit 1 for the specific mismatch and the same synthetic healthy scenario must exit 0. These local assertions do not close actual sandbox or sponsor requirements.

## Saving replay in the investigation workspace

```sh
python3 -m crashcart.replay_workspace input.json --db path/to/workspace.sqlite3 --merchant defective
```

This offline command validates and actually re-executes the supplied tape before
atomically persisting the resulting run, payment, operations, ticket state and
events. It does not import a caller-supplied verdict. An interrupted import rolls
back all new rows. Repeating the same input/variant/implementation reuses the
sealed result without another replay; if those saved rows changed, import fails
instead of overwriting them. Different merchant variants have separate run IDs.

Normal authenticated `/api/runs`, `/api/runs/{id}`, `/api/merchant/{purchase}` and
inspection-export reads now expose the saved result. No new read overlays,
provider adapters or UI fixtures are used. Original recorded browser text and
observation clocks remain source evidence; replayed merchant state comes from
the real offline Store execution. Every event retains its source record hash and
original payload. No causal links are invented. The recorded clock, current
import timestamp and current workspace read timestamp are distinct.

A finished import attempt seals the exact input tape and actual execution result.
The replay_imported event exposes original IDs, source/implementation hashes,
input hash and explicit provenance. Source order/capture IDs are mapped to
`replay_order_...`/`replay_capture_...` aliases in workspace rows, so they cannot
collide with or change the original paid purchase. Recomputed replay ticket and
request IDs remain separate; original IDs/payloads remain in the sealed source.
Replayed confirmation is not a new independent network read. Schema labels do
not authenticate the original service data; inspect its historical receipts.

LOCAL_TEST input stays LOCAL_TEST. Actual recorded sandbox input produces
RECORDED_REPLAY, never LIVE_SANDBOX or FRESH_SANDBOX. Normal order/capture/reconcile
routes reject both offline modes before provider construction. Import adds no
jobs and changes no original run, financial identity, attempt or usage allowance.
Only explicitly selected destination workspaces are written; the command does
not load private provider configuration.

The normal regression.zip download checks the sealed input hash, mode and
namespace before exporting that exact tape. If a reduced tape was imported, its
reduced steps remain reduced; the importer does not silently restore a full tape.
The exported archive keeps LOCAL_TEST or RECORDED_REPLAY mode and the original
source mode. It is suitable for offline reruns, not proof of a fresh checkout.

Run `python3 -m unittest tests.test_replay_workspace tests.test_replay -v` for
persistence, restart, rollback, namespace, duplicate, original-source, guarded
payment-route and real loopback read/download checks. The historical input test
replays the included saved tape without contacting PayPal or modifying an
original payment database. Actual Studio walkthrough receipts and recordings
remain in the maintainer's private archive. Source tests and local exports do
not establish a new sandbox payment or close the unfinished operator journey.
