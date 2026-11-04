# How the AI investigated a real Sandbox payment

CrashCart uses AI to decide which evidence to inspect next. Deterministic code decides whether the payment and ticket satisfy the promise. These are separate responsibilities: a persuasive model answer cannot turn missing payment evidence into a pass.

This page describes an **actual historical model investigation performed on 26 October 2026**, using DeepSeek-V4.1-Flash served by Modal. It is a different case from the defective checkout shown in the public replay. The [public judge mode](https://himanshu748.github.io/crashcart/) makes no model calls and does not reproduce this AI execution.

## What actually ran

The authenticated product investigation endpoint made three actual model calls. The model selected a provider read, then a merchant read, then finished. Its provider read made one real PayPal Sandbox order GET, with OAuth authentication, for an existing payment. Merchant observations came from a controlled copy of the historical store records. No new checkout or payment occurred during this investigation.

The promise stayed fixed: one USD29 workshop ticket within 60 seconds of completed capture. The recorded payment had completed on 23 October; the actual model investigation happened three days later.

| Step | Evidence available before the model response | Actual model action | What changed in its reasoning |
| --- | --- | --- | --- |
| 1 | The customer promise, with no collected observations | Read the payment provider | Payment completion and delivery timing were still unknown. |
| 2 | PayPal confirmed the exact USD29 capture | Read the merchant | A completed payment alone did not establish ticket delivery. |
| 3 | Provider confirmation plus one matching delivered ticket | Finish | The model calculated approximately 3.42 seconds between capture and delivery and cited both observations. |

An exact excerpt from the second model response captures the important decision:

> Provider capture is confirmed complete; merchant ticket delivery records have not yet been observed, so fulfillment timing cannot be evaluated.

The deterministic checker independently returned `PASS / ticket_delivered_once_on_time`. A separate actual unpaid comparison preserved uncertainty when neither a capture nor a ticket existed. In another controlled experiment, withholding the entire provider observation produced an explicit uncertainty response and a deterministic `INCONCLUSIVE / missing_correlation_identity`, rather than an invented payment fact.

## Evidence and provenance

The [sanitized machine-readable summary](../evidence/runs/submission-ready/ai-historical-summary.json) includes the actual step sequence, timestamps, result, verification counts and SHA-256 bindings to the retained private artifacts. It removes the endpoint address, account and payment identifiers, buyer information and credentials. The private artifact hashes establish provenance bindings; they do not let a public reader independently authenticate the provider calls without the underlying private records.

The paid investigation's original read-only verification passed **22/22 checks**. An independent review inspected the outbound contexts, model responses, saved plans and tool observations. It confirmed that plans preceded observations, the paid and unpaid comparisons used the same system instructions, schema and invariant, and no prior verdict or expected answer entered the model contexts. The additional withheld-provider experiment passed eight structural checks and 28 independent checks. These are dated historical results, not newly executed tests.

The implementation is available in [the investigator](../crashcart/investigator.py), with configuration and execution boundaries in [the investigator documentation](investigator.md). The private acceptance archive records this historical scope under CC-028 and CC-029; the public summary does not create a new acceptance result.

## What this establishes—and what remains unproven

This is evidence of meaningful AI use in the same product workflow as an actual PayPal Sandbox read: the model used a real payment observation to choose a subsequent merchant observation and ground its findings. It supports describing the integration as historically exercised. It does **not** establish that a new customer payment was created during the AI run, that the model discovered an undisclosed defect, or that the public faulty replay was investigated by that model invocation. It also does not establish repeated stochastic reliability, a fresh repaired checkout, or a currently running hosted AI service.

For a demo, show this as **“Recorded AI investigation · 26 October”**, separately from the interactive recorded checkout. Suggested narration: “In this earlier real model run, DeepSeek checked the existing Sandbox payment, then requested the matching ticket records before drawing a conclusion. CrashCart's deterministic checker made the final decision. Today's keyless walkthrough replays saved evidence; it does not call the model.”

The event requires meaningful PayPal and AI use and a working demonstration. This evidence explains the historical integration; it is not an organizer ruling that a particular video or entry satisfies those requirements. Record the working product and label the historical segment clearly.
