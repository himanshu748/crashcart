# CrashCart: the judge-facing architecture

The local judge recomputes recorded input at launch; the hosted pages show
results computed at site build. Neither needs accounts or provider calls.
A separately configured private workspace can run Sandbox checkout and AI.
AI proposes which evidence to inspect; deterministic code decides the verdict.

## Core payment and judge path

| Module | Responsibility |
| --- | --- |
| `paypal.py` | Sandbox Orders v2 create/capture/get and PayPal webhook-signature verification. |
| `service.py` | Coordinates owned test-store checkout, independent reconciliation and fulfilment. |
| `store.py` | SQLite journal, payment confirmation, idempotent tickets, events and durable jobs. |
| `invariant.py` | Pinned, unchanged decision rules: correlated payment, one ticket and the fixed 60-second promise. |
| `promise.py` | Validates the supported customer promise; proposals cannot relax the fixed contract. |
| `faults.py` | Typed, bounded fault schedules for the registered owned merchant fixture. |
| `replay.py` | Applies recorded steps and the repaired merchant rule to an isolated real Store; does not re-run MerchantService. |
| `replay_workspace.py` | Imports actual replay results into a separate saved-case namespace with provenance. |
| `judge.py` | Keyless, read-only public example and static export; never starts the live worker. |
| `recorded_studio.py` | Optional licensed SDK explorer over those exported recorded rows, with a clear licence gate. |
| `server.py` | Authenticated private workspace API, saved records and owned-store test checkout routes. |
| `worker.py` | Leased background jobs for bounded investigation and checkout recovery. |
| `investigator.py` | Bounded model/tool loop that selects evidence; final verdict remains deterministic. |

## Optional operator tooling

| Module family | Responsibility and boundary |
| --- | --- |
| `monitor_*` | Local store-scoped monitoring preview and signed Shopify/WooCommerce readers; no real store connected. |
| `kernel_*` | Authorized remote-browser session control and recorded browser-evidence validation. |
| `verification_gateway.py` | Temporary run-scoped HTTPS verification boundary, not permanent public access. |
| `hosted_live.py` | Separately authorized protected live workspace; not the public recorded site. |
| `studio_agent.py` | Authenticated bounded queries over saved records for the private AG Studio workspace. |
| `model_transport.py` / `model_allowance.py` | Provider transport limits and durable inference allowance accounting. |
| `held_out.py` | Offline held-out evaluation tooling, separate from the curated judge example. |

No optional tool is needed by `./scripts/judge.sh`. The public repair comparison
is recorded execution, not a new purchase or a fresh deployed-merchant test.
See [replay semantics](replay.md), [live-flow evidence](LIVE_FLOW.md), and the
[historical workspace description](WORKSPACE_ARCHITECTURE.md).
