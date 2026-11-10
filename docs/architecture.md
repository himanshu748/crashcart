# Runtime and evidence architecture

CrashCart is a Python 3.13.15 standard-library application with an HTTP API,
same-origin browser UI, a SQLite WAL database and a separate worker process.
There are no runtime pip dependencies. The selected environment is local
development; no hosted deployment or network tunnel exists.

The HTTP operator session is derived from a locally generated secret and held in
an HttpOnly SameSite cookie; a bearer token is available for Postman. Price and
currency are server-owned. Run input selects only the registered owned sandbox
fixture and a typed fault. Creating a run does not initiate payment. Starting
checkout requires explicit sandbox configuration; PayPal supplies the approval
URL. Return parameters are checked against the journal and independently queried
approval status before capture. Cancellation preserves records.

Each semantic create/capture operation stores its body and request ID before
network I/O. Six-hour retries use the same identity/body. The adapter uses only
the sandbox host, one transport attempt, bounded responses and no redirects.
Captured response bytes are sanitized and observed by the harness. With response
loss enabled, the merchant remains unresolved and learns no capture ID until a
separate GET discovers it from the saved order ID.

Healthy capture schedules durable reconciliation before the network call.
The worker claims a leased job atomically; ownership and fencing reject stale
completion. An independent provider read must confirm the correlated capture
before the store can fulfill. A unique ticket per logical purchase makes
duplicate fulfillment idempotent. The defective fixture retains missing delivery
for investigation. Webhook ingress verifies through PayPal's verification API;
only verified identities enqueue recovery. Real webhook delivery is unverified.

The versioned invariant checks identity, exact integer amount/currency, ticket
count, event/observation time and the fixed 60-second deadline. Unknown evidence
stays inconclusive. Observation ordering alone never creates causal links.
The model runtime proposes plans and bounded read tools; it cannot set a verdict,
change a deadline, execute arbitrary URLs, or spend on a payment. Model calls are
disabled by default. Local fake model tests retain LOCAL_TEST provenance.

Replay validates a saved tape, executes the actual Store in an isolated SQLite
namespace with recorded time, and reruns the invariant. It has no live fallback.
Reduction executes candidates and compares the specific paid-without-ticket
signature. Injected unit cases remain LOCAL_TEST. Separately, the actual saved
payment tape has run offline with network access denied, including reduction and
export execution. Those RECORDED_REPLAY results do not create new payments or
close their still-open acceptance dependencies. See [replay](replay.md) for the public recorded input, export commands
and original-versus-reduced timing limitations.

## Read-only merchant adapter

`GET /api/merchant/{purchase_id}` requires operator access and performs a database
read only. A known unpaid purchase returns `known: true`, `ticket_count: 0`,
`tickets: []`, and `status: NOT_DELIVERED`. A missing purchase returns
`known: false`, `ticket_count: null`, `tickets: null`, and
`status: MISSING_PURCHASE`. Paid state is never obtained from a fictional PayPal
entitlement endpoint. `GET /api/runs/{run_id}` joins the stored run, purchase,
operation journal, merchant query and event trace by explicit identities.

`GET /api/runs/{run_id}/export` downloads inspection JSON. It is explicitly not
a runnable regression. `/regression.zip` requires a complete supported source
tape and otherwise fails; it packages replay source, invariant, migration and
manifest. Neither export makes a fresh payment. Review browser free text and
recordings before any separately authorized publication.

## Delivery timing

A separate read-only page uses the pinned Bryntum Community Scheduler beta SDK
to compare eligible saved payment/ticket timings across investigations. Relative
seconds start at each confirmed capture; the fixed 60-second window and actual
ticket timestamps are never editable. The validated projection keeps the saved
server checker verdict and refuses inconsistent identity/time data. It calls
only authenticated same-origin saved-record GET endpoints. Refreshing does not
make a payment, recheck PayPal or invoke a model. The SDK is built into its own
entry so the beta dependency does not enter the core workspace bundle.

## Deliberately unresolved integration gates

The workbench, actual AG Studio workspace, bounded investigator and KERNEL
adapter are implemented. External execution requires the operator's own access,
applicable licences and an explicit bounded allowance. No account, credential,
remote session, paid usage or public endpoint is included in a source checkout.
Historical saved observations and recorded replay do not establish fresh repair
verification, held-out discovery, authentic webhook delivery or a complete
operator journey. [Development status](archive/STATUS.md) lists current release limits.
