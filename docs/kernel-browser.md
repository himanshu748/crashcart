# KERNEL browser adapter

`crashcart/kernel_browser.py` implements real HTTPS calls to the fixed `https://api.onkernel.com` service. It is not connected to the investigator or HTTP routes yet. Its unit tests use an injected transport and label those receipts `LOCAL_TEST`. Historical real sessions and recordings were exercised separately; their private receipts are not included in this source checkout. Local adapter tests are not proof of remote execution.

The actual runtime blockers are `KERNEL_API_KEY`, an authorized `CRASHCART_ALLOW_KERNEL=1`, an operator-created usage allowance, and an owned public HTTPS `CRASHCART_PUBLIC_URL` reachable from KERNEL. `CRASHCART_OPERATOR_TOKEN` authenticates the owned application. Localhost, private addresses, private DNS answers, credentials in URLs, arbitrary ports, paths and query strings are rejected. A configured origin is an ownership declaration; it does not establish ownership or reachability by itself. No ingress or account configuration is performed here.

## Current primary API contract

The implementation checked the current official documentation on 2026-10-22:

| Operation | REST contract used | Primary documentation |
| --- | --- | --- |
| Create | `POST /browsers`, response200 with `session_id`; `name`, `tags`, `network.allowed_hosts`, `timeout_seconds` | [Create browser](https://www.kernel.sh/docs/api-reference/browsers/create-a-browser-session) |
| Execute | `POST /browsers/{id}/playwright/execute`, `code` and `timeout_sec`; require `success: true` and a structured `result` | [Playwright API](https://www.kernel.sh/docs/api-reference/browser-playwright/execute-playwrighttypescript-code-against-the-browser) |
| Record | `POST /browsers/{id}/replays`, response201 with `replay_id`; `framerate`, `max_duration_in_seconds`, `record_audio` | [Start recording](https://www.kernel.sh/docs/api-reference/browser-replays/start-a-browser-session-replay-recording) |
| Stop | `POST /browsers/{id}/replays/{replay_id}/stop`, response200 | [Stop recording](https://www.kernel.sh/docs/api-reference/browser-replays/stop-a-browser-session-replay-recording) |
| Download | `GET /browsers/{id}/replays/{replay_id}`, response200 binary MP4 | [Download recording](https://www.kernel.sh/docs/api-reference/browser-replays/download-a-replay-recording) |
| Delete | `DELETE /browsers/{id_or_name}`, response204 | [Delete browser](https://www.kernel.sh/docs/api-reference/browsers/delete-a-browser-session-by-id-or-name) |

The SDK is not installed or required. The stdlib HTTP transport makes one attempt, rejects redirects, bounds response sizes and suppresses raw upstream error bodies, stdout, stderr and headers. A recording response202, unexpected binary format or HTTP failure is incomplete evidence, never a successful download. There is no automatic session creation, payment retry, recording polling or paid fallback.

## Explicit allowance and lifecycle

After actual user authorization, an operator supplies a private JSON file with exactly these fields:

```json
{
  "approval_id": "replace-with-approved-unique-reference",
  "owned_origin": "https://your-owned-merchant.example.com",
  "expires_at": "REPLACE_WITH_AUTHORIZED_TIMEZONE_TIMESTAMP",
  "max_session_seconds": 180,
  "scenarios": ["observe"]
}
```

This example is intentionally unusable. The application must not manufacture the approval or enable flag. Each approval reserves at most one session. An atomic, mode0600 reservation in persistent `var/kernel/` is written before the create request; restarting the adapter cannot reuse it. Failed or ambiguous creation consumes the allowance. Do not reset the ledger to obtain more sessions. Grant expiry must cover the whole bounded session, with a10–300second limit. Monetary pricing/account credits and access through judging must be checked separately before authorization.

```python
from crashcart.kernel_browser import KernelBrowser

adapter = KernelBrowser(allowance_path="var/kernel-allowance.json")
session = adapter.session(run_id=existing_run_id,
                          purchase_id=existing_purchase_id,
                          order_id=existing_order_id,  # None before initial checkout
                          mode="LIVE_SANDBOX")
try:
    with session as browser:
        observation = browser.perform("observe")
finally:
    receipt = session.receipt
```

The context manager starts a browser, authenticates without putting the operator token in the DOM, starts recording, and finally attempts recording stop/download and browser deletion. The token is sent in a fixed code template to the authenticated KERNEL execution service, so use an authorized, suitably scoped operator credential; it is never included in the local receipt. Browser navigation egress is restricted to the exact owned host and fixed sandbox PayPal/PayPal asset hosts. Provider login assets outside that set fail closed and need investigation, not a wildcard expansion.

KERNEL documents `timeout_seconds` as an inactivity limit. This adapter additionally starts a wall-clock watchdog. Cancellation, context exit, KeyboardInterrupt, scenario error and deadline expiry attempt cleanup. Setup requests are serialized with cleanup to avoid deleting a session before a late create returns its ID; individual HTTP timeouts and cleanup can extend wall-clock shutdown. Cleanup errors remain in the receipt. If creation times out, the pre-reserved unique name is used for deletion without inventing a session ID. A failed replay-start response may leave an unknown recording ID; deletion is attempted, and `START_REQUESTED` remains unresolved.

A hard process kill cannot execute Python cleanup. The private reservation and receipt preserve the session name/known IDs, and KERNEL's inactivity timeout provides a secondary bound (active external live-view connections can keep it alive). Operator recovery must inspect/delete that exact session; the module does not promise remote cleanup after a hard kill.

## Closed scenarios and evidence

Only names explicitly included in the allowance are executable:

- `observe`: navigate to the owned `/shop` for the exact run and read visible DOM state.
- `checkout`: verify the existing unpaid USD29 fixture, click the real checkout button, bind the actual returned order to the same purchase, and wait for its sandbox approval page. It returns an awaiting-approval observation, not payment success.
- `confirm_return`: require the actual current owned `/return` URL, matching run and persisted order token, then click the capture control and observe its result. The backend independently checks approval; no fabricated return navigation is used.
- `cancel_return`: inspect an actual owned `/cancel` return for the same run. It does not fabricate buyer cancellation or cancel a payment.

No arbitrary selectors, executable code, target URL or buyer credentials are accepted from a model. For checkout, an authorized operator must complete real sandbox buyer approval through `private_live_view_url()` within the allowance, then invoke `confirm_return` in that same context. The adapter does not automate buyer credential entry or bypass login/approval. All steps must use one session for a complete checkout claim. Closing and opening a new session requires a distinct approved allowance and is a distinct browser journey.

Each observation binds run, purchase, current order, session and recording IDs. The remote script checks the registered `workshop-v1` fixture, amount2900/USD and exact mode using the owned API, then separately reads visible DOM fields and the displayed journal. A ticket ID is recorded only if its card is visible. Observation time and local receipt time are separate. Browser observations alone never decide payment truth: `payment_verdict` remains `NOT_EVALUATED`; independent PayPal and merchant evidence is still required.

Receipts contain allowlisted fields and scrub known secrets, emails, JWTs and URLs from visible text. Live-view, CDP and replay-view URLs never enter receipts. MP4 files stay mode0600 in ignored `var/kernel/`, marked `NOT_REVIEWED`; interruption recordings are `SAVED_PARTIAL`. They may contain buyer PII and must be inspected/redacted before any public evidence export. A JSON receipt or downloaded video does not establish that its pixels show the required behavior. Inspect the recording and independently correlate the actual payment and entitlement.

The application posts `browser_kind: LOCAL_BROWSER` from its frontend; those app events alone do not establish KERNEL provenance. The separate reviewed-artifact importer described in [KERNEL evidence](kernel-evidence.md) preserves remote receipts and original observation times. Importing an earlier recording is not a new execution. No requirement is marked by the adapter or importer.

## Local verification

Run `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_kernel_browser -v`. The injected transport cases cover gates, allowance replay, public target validation, fixed REST shapes, private data handling, exact correlation, partial recordings, real local watchdog dispatch, cancellation, timeout, ambiguous creation and cleanup failures. They establish local adapter behavior only.

Real remote execution needs the operator's own access and an explicitly scoped
usage allowance. A source clone supplies neither. Historical session outcomes,
recordings and current account usage belong to the private operational archive;
they must not be inferred from passing injected-transport tests. See
[development status](../STATUS.md) for current release limits. Local scenario
repairs cannot retroactively establish the cause of an earlier remote failure.
