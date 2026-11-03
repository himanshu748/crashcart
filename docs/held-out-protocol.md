# Held-out evaluation protocol — candidate preparation

Status: **DRAFT, NOT THE FINAL FREEZE.** No held-out seed has been selected.
CC-037 and CC-039 remain unaccepted. The actual real-model prerequisites
CC-028/029 and the accepted CC-030 execution limits must hold before final
protocol acceptance. This document does not change BUILD_CHECKLIST.md or its
dependency rules.

The experiment asks whether the runtime investigator can discover a deliberately
seeded payment-versus-ticket mismatch from observations without receiving the
selected defect, its source, or the expected answer. It cannot establish unknown
production-bug discovery or universal checkout safety.

## Freeze and independent selection order

1. Complete the real-model adaptation and evidence-grounding prerequisites.
   Freeze the investigator, prompt, schemas, tool adapters, invariant, dependency
   versions, execution limits and model configuration. Save source hashes and
   the actual model identity. Changes affecting inputs or behavior require a new
   freeze and a new independently selected variation.
2. Before selection, fix the case procedure, comparison criteria and controls
   below. An independent reviewer who did not implement the investigator then
   selects a variation within the existing approved fixture and fault scope.
   Do not use a previously disclosed example as an unseen variation.
3. Put the selected seed, fixture variation, expected mismatch, relevant defect
   source and selection receipt in a reviewer-only location outside the runtime
   model's inputs and tools. Record a salted commitment before execution. Keep
   the salt private until reveal because the seed space is small. The runtime
   has no file-reading tool or access to this envelope. No such envelope is
   created by the preparation command.
4. Independently inspect the exact allowed inputs, prompt, schema, fixture
   metadata and every tool adapter. Save the permitted surface and hashes.
   Restrict the run to a neutral promise, opaque identities, the registered
   fixture, customer observations and independent payment/store reads. The
   declared tool schema may list supported fault families; it must not disclose
   which variation the reviewer selected.
5. Execute only after the required account access and separately bounded usage
   authorization are available. Save the exact sanitized model inputs/outputs,
   tool exchanges, response identities, actual token usage, source hashes and
   deterministic verdict. Preserve failed and inconclusive attempts.
6. After the verdict is durable, reveal the reviewer envelope and verify its
   earlier commitment. Compare the discovered observations and deterministic
   mismatch with the withheld expectation. Reviewer hindsight must not rewrite
   the expected answer, input, deadline, invariant or fault schedule.

## Input isolation and contamination handling

The current investigator builds its initial context from an allowlist and does
not directly pass `run.fault`. However, browser text and the user promise are
untrusted inputs and can disclose an answer. In particular, the current dashboard
observation contains the application's verdict label. That observation is
unsuitable for a held-out evaluation even though it is a valid saved product
observation for other purposes.

Use separately reviewed customer-only observations from the checkout and ticket
page. The reviewer must trace each permitted browser event to its original
receipt/recording; an event ID allowlist alone does not establish provenance.
Do not admit the investigation dashboard, fault controls, selected merchant
variant, deterministic verdict, reviewer expectation, seed, defect source,
operator notes or old diagnosis into the runtime input.

The production boundary is `crashcart/held_out.py`. The preparation script imports
its pure input auditor. Ordinary investigation behavior remains available only
in an ordinary process. A held-out evaluation must use a separate newly started
process with trusted launch configuration:

```sh
CRASHCART_EVALUATION_MODE=held_out
CRASHCART_HELD_OUT_POLICY=/absolute/private/reviewed-policy.json
CRASHCART_HELD_OUT_POLICY_SHA256=<independently-recorded-sha256-of-exact-policy-bytes>
```

These variables never come from an HTTP body, run metadata, model context or
model-provider environment override. The policy is mandatory: an absent,
malformed, writable, shared, symlinked or digest-mismatched policy blocks the
investigation. Supplying policy settings without held-out mode also blocks.
The owner must set its permissions to `0400`. A dedicated process must have no
reviewer envelope or seed files accessible through its runtime tools. This is a
trusted application/process boundary, not a Python sandbox against an operator
who can replace code, alter environment variables or edit the database.

The strict `held-out-policy-v1` JSON object contains exactly the fields declared
by `POLICY_FIELDS` in `crashcart/held_out.py`. The reviewer supplies:

- `run_id`, `purchase_id`, `order_id` (nullable), `fixture_id`, `proof_mode`, the
  exact `neutral_promise`, unchanged `invariant`, and complete stored `budget`.
- `model_configuration`: exact `provider`, `protocol`, `endpoint_origin`,
  `endpoint` and `configured_model`; `response_model` is the separately frozen
  actual response identity. Credentials are never policy fields.
- `input_version`, `system_sha256`, `schema_sha256`, `schema_name`,
  `max_output_tokens` and `source_hashes`. `sha` hashes canonical JSON, including
  the system string. `source_hashes()` covers every runtime Python module,
  migration, requirements file and pinned Python version. It does not single
  out the defect source or disclose source content to the model.
- One to five `customer_receipts`, each with the complete original `event`, its
  canonical `event_sha256`, an absolute `receipt_path`, and the exact file-byte
  `receipt_sha256`. Independently review the receipt/recording and its linkage to
  this event; a hash or matching event ID is not proof that review occurred.

There is no policy field for a seed, expected answer, expected verdict, selected
fault, defect envelope or secret canary. The neutral promise is fixed to the
public contract. Customer events must identify this exact run/purchase/order,
have nonempty text and originate on `/checkout` or `/ticket`; dashboard sources
are excluded. Each complete stored event and external receipt is rechecked for
changes. Only these predeclared browser events are read; other saved browser
records remain unchanged and are outside the permitted source list.

The common `Investigation.run` entry point used by HTTP and Python callers
checks the binding before creating the model. It persists the policy digest
against the run, so a later launch cannot silently bind a new policy to it.
Every context and tool observation is audited before use. Browser projections
must match the approved full event exactly; provider/merchant identities must
match the run. Known answer/fault cues in nested external keys, values and arrays
are rejected. Prior plans and fault proposals are allowed only through actual
validated in-run model and tool receipts. Fabricated context entries receive no
exemption. Model proposals never activate a fault.

Immediately before transport, the shared model client audits the exact request
bytes after `Request` construction, including destination, model, system prompt,
schema, context and output limit. The HTTP helper repeats the check before
starting its worker. A direct model/Studio/transport call outside the guarded
investigator scope is blocked in a held-out process. Policy, customer and prior model/tool receipt bindings are rechecked when the
response returns and before accepting the final outcome. Response identity drift
also stops the run while preserving reported usage. An injected model replacement
cannot bypass this path; LOCAL_TEST uses the real `OpenAIModel` class with an
intercepted transport, and remains LOCAL_TEST.

A rejected run ends explicitly INCONCLUSIVE with a `HELD_OUT_*` reason. Its
original stored observations remain unchanged; rejected tool observations retain
a diagnostic receipt and original hash under the ordinary secret-redaction
rules. A rejected trial cannot be resumed for held-out credit even after its
input is corrected. The existing call/time budgets, unresolved-attempt handling
and cancellation rules remain in force. The gate neither grants model/payment
usage nor resets an allowance. Known-cue scanning cannot prove absence of
arbitrary semantic leakage; independent input review is still required.

This implementation and its intercepted-transport checks are local enforcement
proof only. They do not select a seed, freeze the final experiment, execute a
real model or satisfy CC-037/039 acceptance.
If contamination is found, stop and label the attempt unsuitable for held-out
credit. Preserve the original input and observation unchanged. Do not silently
remove clues from already-recorded evidence and call the same attempt unseen.
After an isolated boundary correction and new investigator freeze, an independent
reviewer must select a new undisclosed variation.

## Predefined controls and unchanged acceptance

All cases retain `ticket-v1`: USD 29.00, exactly one ticket, and a 60-second
deadline measured from confirmed capture. Use separate run/purchase namespaces.
The following preparation cases are public controls, not the held-out seed:

| Control | Fixed observations | Required result |
| --- | --- | --- |
| Legitimate waiting | Completed payment, zero tickets at capture +30 seconds | INCONCLUSIVE, `within_recovery_window` |
| Legitimate delayed delivery | Completed payment, one ticket created at +45 seconds, observed at +46 seconds | PASS, `ticket_delivered_once_on_time` |
| Inadequate payment evidence | No persisted order or independently established capture | INCONCLUSIVE; never infer paid from browser text |
| Late-delivery negative guard | One ticket created at +61 seconds, observed at +62 seconds | FAIL, `ticket_delivered_late` |

The preparation harness executes the actual Store and Investigation using an
injected, prescribed LOCAL_TEST strategy and synthetic payment observations.
It constructs these timestamped states; it does not run the production delayed
fulfillment scheduler, wait 45 real seconds, or prove real provider behavior.
The stored fault metadata is a deliberate synthetic exclusion challenge, not a
claim that this harness activated that fault. The selected metadata must remain
absent from model contexts. The positive control is limited to deterministic
state handling and context isolation.

The same approved invariant and bounds must also govern the later real-model
evaluation and fresh repair comparison. Record the number of scenarios, actual
calls, time limit, stop reason and unresolved evidence. A pass means no failure
was found within that recorded search; it is not a universal safety guarantee.
Budget exhaustion or an unfinished investigation remains inconclusive.

## Reproduce this preparation

From the repository root with the project's pinned Python 3.13.15 and only the
standard library. Other Python versions have not been verified for this batch:

```sh
python3 -m unittest tests.test_held_out_gate tests.test_held_out_inputs -v
crashcart_heldout_dir="$(mktemp -d)"
python3 scripts/verify_held_out_inputs.py --output "$crashcart_heldout_dir/attempt"
```

Choose a new output directory for every attempt; existing receipts are never
overwritten. The harness uses temporary databases and never opens saved project
payment state. Socket creation/connection are denied, with the guard exercised
before execution. Reports contain all captured LOCAL_TEST contexts, preserved
browser observations, rejected contamination, controls, interpreter and source
hashes. No credentials, actual model calls, provider transactions, KERNEL
sessions, final seed selection or requirement acceptance occur.
