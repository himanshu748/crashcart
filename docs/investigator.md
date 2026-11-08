# Bounded investigation runtime

`Investigation(store, service).run(run_id)` asks the configured model for a
brief hypothesis and one next action, records the plan, executes a validated
read-only action, and supplies that observation on the next turn. The model can
adapt its next action to the observation. It cannot submit payments, approve a
buyer checkout, mutate provider records, activate faults, deliver tickets, or
set the payment verdict.

The registered tools are `read_provider`, `read_merchant`, `read_browser`, and
`propose_fault`. `finish` stops the planning loop. Fault proposals require the
registered `workshop-v1` fixture and remain proposals for the operator. Browser
and provider data are explicitly untrusted. Unknown fields, tools, run IDs,
faults and unsupported finding references are rejected before dispatch.

The approved `ticket-v1` invariant is supplied unchanged. Prompt version
`investigator-v4` uses the versioned `crashcart_investigator_wire_v4` schema.
The model returns only `requested_values` (six required nullable fields),
`hypothesis`, `tool`, `arguments` and `findings`. Requested values are amount in
minor units, currency, ticket count, deadline, timing trigger and delivery kind.
It must not return adapter paths, version constants, classifications or lists
of missing fields. Unknown/missing fields, wrong types and out-of-bounds values
are rejected; no value is defaulted, coerced, corrected or inferred by code.
Hypotheses and claims must have 1–1000 characters; at most eight findings fit the
wire schema, matching the existing runtime checks.

`project_requested_values` preserves all six values exactly and derives only
fixed metadata: the approved observation paths, proposal version, compatible/
ambiguous/unsupported classification and exact null-field list. `capture_completed`
maps timing start to `provider.capture_completed_at`; every other trigger,
including null, maps it to null. Requested buyer approval, order creation or
checkout return remains unchanged as a descriptive value. The other fixed paths
are `provider.amount`, `provider.currency`, `merchant.ticket_count` and
`merchant.tickets[].created_at`. A known conflict remains unsupported even when
other requested values are null. The resulting complete plan passes the existing
`validate_plan` before tools. Invalid actions, null fault proposals, empty claims,
unknown evidence IDs and incompatible arguments are never repaired.

The original sanitized wire text is retained before projection in `wire_response`
and a `model_wire` event, with wire version, character count and SHA-256. Text is
stored in lossless chunks of at most 4000 characters to respect the existing
trace string bound; concatenating `text_chunks` recovers it. The full derived
`plan` and separate `projection` receipt identify `promise-projection-v1`, source
wire hash and derived field names. Schema/value/action failures retain their wire
receipt with no derived plan or tool dispatch. Injected overlength/nontext outputs
are explicitly omitted and rejected. The shared transport rejects malformed
JSON/refusal before this boundary; those early failures retain available model
metadata only, not output text. No output is retried or converted from an old
format. Old v2/v3 responses remain failed under their original validators and are
also rejected as v4 wire input.

The prompt recognizes ordinary number words, singular workshop-ticket wording
and exact stated USD dollar-to-cent conversion. A/an/one workshop ticket requests
one ticket, but does not supply missing price, currency, deadline or timing.
For this owned checkout, confirmed/completed payment denotes completed provider
capture; explicit buyer approval, order creation or checkout return still retain
their different timing semantics. Absent observed records do not make explicitly
requested values missing. These are instructions to the model, not proof that a
model followed them. Ambiguous/unsupported plans stop as `NEEDS_INPUT` before
any tool. No diagnosis or fixed tool order is prescribed.

Requested values and derived metadata never replace the stored run invariant,
`DEFAULT_INVARIANT` or evaluator arguments. Local projection and supplied-plan
checks establish validation, provenance and stopping behavior only. Actual model
interpretation of different requests and ambiguous input still needs fresh
bounded evidence after independent review.
Only `crashcart.invariant.evaluate` returns PASS, FAIL or INCONCLUSIVE. An
unfinished, cancelled, budget-exhausted or failed investigation ends as
INCONCLUSIVE, retaining its collected evidence.

## Authorization and configuration

Actual model calls require an explicitly authorized `CRASHCART_ALLOW_MODEL=1`
and the selected provider's private configuration. `CRASHCART_MODEL_PROVIDER`
defaults to `openai`, which requires `OPENAI_API_KEY` and `OPENAI_MODEL` and uses
the fixed OpenAI Responses endpoint. Selecting `modal` requires `MODAL_API_KEY`,
`MODAL_MODEL=deepseek-ai/DeepSeek-V4.1-Flash`, `MODAL_ALLOWED_ORIGIN` and
`MODAL_BASE_URL`. Set the two origin values privately to the identical owned
Modal deployment origin, for example `https://your-deployment.modal.run`.
Only canonical lowercase HTTPS origins with one DNS label before `.modal.run`
or a tenant and region before `.modal.direct` are accepted. Paths, trailing slashes, ports, queries, fragments, user information
and non-Modal hosts are rejected before a request is constructed. The operator's
allowlist pin is server configuration; it cannot be changed by a model response
or a browser request.

No code edit or maintainer endpoint is needed to configure an owned Modal
server. The non-routable `MODAL_ORIGIN` constant remains solely for explicitly
injected local tests, which receive no credential and remain `LOCAL_TEST`.
It is rejected for actual model calls. A configured origin establishes neither
ownership, connectivity nor current usage authorization: the operator must own
the deployment and separately authorize the bounded call allowance before
setting `CRASHCART_ALLOW_MODEL=1`. Existing held-out policy, call, token and
time budgets still apply; there is no arbitrary-origin fallback.

The fixed `/v1/chat/completions` route uses the combined proxy credential as a
server-only Bearer value. No CLI login, management token or unrelated provider
credential is substituted.

For the owner's bounded Modal verification, set `CRASHCART_MODEL_ALLOWANCE_PATH`
to the absolute path of the existing private v1 ledger in **both** the API and
worker processes. The provider transport then reserves against the same
24-call / USD1 history before each request. Runtime code cannot create or reset
the ledger. Each attempt reserves USD0.04; errors consume their reservation,
and an unresolved dispatch blocks further calls. Reservations use a stable
process lock and fsynced atomic writes. The ledger stores request hashes and
usage metadata, never credentials or model content. Lock acquisition is bounded;
reservation time comes out of the existing request deadline. This is a specific
operator allowance guard, not a general billing system or a provider-side
spending cap. An unset variable retains the existing per-run limits; it does
not grant permission for inference or unlimited public use.

The shared endpoint's published rates were checked on 8 November 2026:
USD0.30 per million input tokens and USD1.20 per million output tokens. The
ledger counts uncached input conservatively; estimates are not an invoice.
[Modal model and Shared Endpoint pricing](https://modal.com/library/deepseek/deepseek-v4-1-flash).

The shared `model_transport` module sends one strict JSON-schema request. Modal
uses `response_format`, `reasoning_effort: none`, `stream: false`, and bounded
`max_tokens`; OpenAI retains Responses `text.format`, `store: false`, and bounded
`max_output_tokens`. There are no redirects, retries, protocol downgrades or
response-repair calls. Serialized UTF-8 request bodies are capped at 65,536 bytes;
responses at 1 MiB; output at 1,024 tokens and 16,000 structured-text characters.
The total request deadline deducts preparation time from the caller's remaining
budget. A short-lived standard-library worker owns HTTP. Its parent enforces
the remaining deadline across DNS, TLS, headers and body, kills the worker's
private process group on timeout, and reaps it before returning. The worker
receives credentials only through stdin; it inherits no credential environment
and puts no credentials in its command line or logs. No local HTTP worker or
socket remains after timeout. An upstream model may already have accepted the
request; disconnecting cannot guarantee remote cancellation or zero billing.
Observed response IDs and usage are retained on late complete responses;
otherwise usage remains unknown and the attempt is still consumed.

Actual returned model/response IDs, reported token usage, provider, protocol,
endpoint origin, and request size/hash are retained, including on failed responses
when available. Chat prompt/completion counts map to input/output counts; absent
usage stays unknown. Destination configuration is also saved before the network
attempt, so an unresolved attempt retains its intended provider. Refusal,
truncation, multiple choices, tool calls, reasoning-only content, invalid usage,
duplicate JSON keys and malformed output fail explicitly. Reasoning is never
parsed for a replacement action. Plan validation still controls all tool authority.

Possessing credentials does not enable calls. Real requests are disallowed for
LOCAL_TEST and RECORDED_REPLAY investigations; injected test models remain
LOCAL_TEST. Passing a transport to `OpenAIModel` forces that instance to
LOCAL_TEST and omits authentication even when production credentials are
present. Such a model is rejected before reservation or invocation for live
and fresh runs; recorded replays retain their explicit network prohibition.
Credentials, buyer details and email addresses are excluded from
model inputs and traces; all newly named Modal credentials are redacted. Error
codes never include raw HTTP bodies or secrets. This transport batch performed
no real model invocation; endpoint access and live acceptance remain separate.

## Budgets, durability and cancellation

Each run permits at most four model attempts/calls and 180 seconds; stricter
stored run budgets apply. A database transaction reserves each attempt before
network execution. Attempts and input versions survive restart, and restarting
does not reset the call budget or elapsed window. An unresolved prior model
attempt blocks a second call until an operator resolves its provenance.

Cancellation and remaining time are checked before model and tool operations
and after their results. An active HTTP operation may finish before the next
cancellation checkpoint; its response and any actual usage are retained, and
the next operation does not run. HTTP calls use a timeout bounded by the
remaining budget. Cancellation cannot erase an already performed request.

Attempts retain input versions, sanitized contexts, response metadata, plan,
tool arguments and observation references. Events record the plan before the
tool observation. Observed findings must cite collected event IDs. Those
references establish traceability, not automatic proof that model prose is
correct; independent acceptance review remains required.

## Verification boundary and official sources

Run `python3 -m unittest tests.test_model_transport tests.test_investigator tests.test_studio_agent -v`. These tests use injected
LOCAL_TEST models and provider fixtures with external network access forbidden.
Owned loopback HTTP servers additionally exercise dripping headers/body,
total deadlines, worker termination/reaping, private credential transport and
redirect rejection. They
exercise changed-observation adaptation, malformed output, prompt injection,
scope violations, missing evidence, budget exhaustion, cancellation, durable
attempts and the transport request shape. They are not real model-call proof,
sandbox payment proof, or KERNEL proof. No real model invocation was performed
while implementing this module.

The implementation follows the fetched official [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
for Responses `text.format` with strict JSON schemas, and the official
[Responses create reference](https://developers.openai.com/api/reference/resources/responses/methods/create).
Refusal, incomplete output and invalid structured data are explicit failures.

## Held-out production boundary

A separate process launched with `CRASHCART_EVALUATION_MODE=held_out` requires
an owner-only read-only policy file and its out-of-band digest. The policy binds
one run, complete budgets/invariant, neutral promise, configured and actual
response model identities, prompt/schema/source freeze, and full reviewed customer
receipts. Missing/corrupt policy, another run, freeze drift or changed receipts
stop before model transport. The digest is durably bound to the run.

`Investigation.run` gates every caller; shared `model_transport.complete` and
`http` also refuse out-of-scope requests in that process. The final request is
checked after serialization and Request construction, including its exact
system/schema/context/model/destination. Prior plans and fault proposals require
actual validated in-run receipts. Approved customer text is preserved exactly;
contaminated input is rejected without scrubbing and reusing the trial. A rejected
trial remains INCONCLUSIVE, retains original evidence and cannot be restarted
for held-out credit. Cancellation, spent attempts and elapsed time retain their
existing semantics. Ordinary mode retains its existing behavior.

The local preparation harness imports the same auditor. Gate tests execute the
production Investigation and HTTP dispatch with intercepted transports and
synthetic receipts. No provider/model calls, final seed selection or acceptance
are implied. See [the held-out protocol](held-out-protocol.md) for policy fields,
launch controls, reviewer responsibilities and final acceptance prerequisites.

## Recorded model failures and v4 evaluation boundary

Real calls01,03,04and05 under model-v26/live are preserved. They failed for a
null fault proposal, empty finding claim, or inconsistent timing/missing-field
metadata. Their exact plans remain negative fixtures under tests/fixtures/.
The old full validator still rejects each original defect; v4 additionally
rejects each old wire format. None is converted to a successful result.

The v4 wire design removes redundant derived metadata from the model's task.
It does not repair semantic values or action arguments. Previous real traces,
consumed attempts and per-run/global allowances remain unchanged. Fresh actual
model evaluation is required; no earlier failure is counted as improved-model
proof. Production held-out gating has local enforcement tests; independently frozen
selection and actual held-out discovery remain separate unfinished work.
