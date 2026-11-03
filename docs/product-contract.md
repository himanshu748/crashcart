# CrashCart product contract v1

Frozen before the first experiment, 22 October 2026.

The user is an engineer investigating a customer complaint about a digital purchase
at an instrumented merchant they own. The only registered fixture is `workshop-v1`:
one digital workshop ticket for **USD 29.00 (2900 integer minor units)**.

The business promise is: a provider-confirmed completed capture for this purchase,
in USD for exactly 2900 minor units, delivers exactly one usable merchant ticket
within **60 seconds of the provider's capture completion timestamp**. This is an
initial product decision made before any experiment, not an adjusted test result.
Invariant `ticket-v1` is immutable for a run. Missing or unparseable provider
evidence is inconclusive. Within the recovery window, zero tickets is pending
(inconclusive), not a failure. A second ticket or a wrong amount/currency fails.

Three separately collected observations establish a finding:

1. Customer: actual visible browser text/navigation and a correlated recording.
2. Provider: a separate PayPal Sandbox order read, including capture ID/status,
   amount/currency, purchase association and completion timestamp.
3. Merchant: a read-only query of our SQLite ticket store by logical purchase.

The flagship fault is a successful sandbox capture whose merchant-facing response
is lost, or a process killed after payment and before delivery. The deliberately
defective merchant reports an error or remains unresolved, and never reconciles.
The repaired merchant durably reconciles the saved order, confirms payment and
fulfills once within the same 60-second promise.

The journey is complaint → fixed invariant → bounded hypothesis/experiment →
customer/provider/merchant observations → deterministic verdict → executable
recorded replay → candidate reduction → fresh sandbox reproduction → unchanged
regression against repaired merchant → new sandbox repair verification.

## Integration roles

- PayPal Sandbox performs test payments and independent payment queries.
- KERNEL performs the actual remote browser journey and supplies recordings.
- AG Studio supplies custom investigation widgets, linked panels and bounded
  natural-language dashboard interaction. A local HTML UI is not AG Studio proof.
- An explicitly configured model proposes hypotheses and bounded tool requests;
  it cannot assign a verified verdict or change the accepted invariant.
- Postman executes the exported API verification collection.
- APIMatic Context Plugin informs development decisions; it does not verify payment.
- Python 3.13.15 serves the web/API; SQLite persists identities and leased jobs;
  a separately started Python worker reconciles durable work. All are portable.

Original transactions use LIVE_SANDBOX; a new approved order used to verify a
reproduction or repair uses FRESH_SANDBOX. RECORDED_REPLAY re-executes saved inputs
offline and cannot contact a provider. Synthetic developer tests use LOCAL_TEST
and do not establish either sandbox execution or replay provenance.

## Scope and gates

One merchant, one flow, response loss, event delay/duplication and process
interruption; one held-out seeded defect and one repair comparison. Faults affect
only registered owned fixture behavior. No provider record mutation, arbitrary
hosts, production repairs, refunds, marketplaces or live-money testing.
This experiment is not a discovered PayPal vulnerability. Render is excluded.

Running this source or passing its tests does not authorize spending,
deployment, messaging or further publication. External use needs the operator's
own credentials, sandbox buyer approval, sponsor access, applicable licences,
bounded usage authorization and reachable owned targets. Source publication
supplies none of those rights or provider proof. No unverified rubric or sponsor
eligibility is assumed.

Success is the complete contract in BUILD_CHECKLIST.md, ending at CC-060 with
60/60 accepted evidence records. A locally running prototype is partial progress.
