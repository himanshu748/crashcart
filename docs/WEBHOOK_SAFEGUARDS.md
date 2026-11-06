# Webhook safeguards and local recovery

These checks cover the local monitoring service. They do not establish a deployed endpoint or authentic store connection. No order deadline, payment validator or original CC acceptance condition changes. No provider, hosting, payment or spending is needed for these local probes.

## Acceptance for this batch

All six checks have source-bound local execution and independent correctness/security review. These are supplemental local checks; original CC acceptance remains 47/60.

- [x] **WH-001 — Bounded requests:** slow requests cannot create unlimited handler threads; excess connections receive a retryable response, timeouts release capacity, and normal requests recover.
- [x] **WH-002 — Bounded callback rate:** global and per-store admission run before expensive body/provider work; arbitrary routes and unsigned IDs cannot allocate unlimited limiter state. Rejection and refill/recovery are exercised.
- [x] **WH-003 — Durable duplicates:** identical observations under varied delivery IDs have bounded receipts and no repeated business mutation. Every acknowledged ID retains its conflict check during retention; saturation is rejected, never silently acknowledged.
- [x] **WH-004 — Safe retention:** trusted receiver time governs expiry; count limits fail closed without evicting unexpired identities. Migration, parallel arrivals and restart preserve retained mappings. Receipt maintenance never prunes business records or changes deadlines.
- [x] **WH-005 — Retry and failure:** actual HTTP rejects saturation before provider invocation and recovers after capacity is available. Uncommitted observations never receive success. Body/header failures and signature/merchant rejection remain fail closed.
- [x] **WH-006 — Local backup and rollback:** the documented command backs up an active local database consistently, refuses overwrite, restores order/deadline/acknowledgement through authenticated HTTP and excludes sessions. A killed uncommitted writer rolls back; integrity and saved facts are inspected.

PM-002/003/004/006/008/009/010 stay open where they require authentic delivery, installation, customer accounts, intended hosting or billing. Passing these local checks cannot establish production readiness or a complete SaaS.

### Scope of pre-provider rejection

WH-005's pre-provider saturation statement concerns the handler/global/store admission limits in WH-001/002. Durable receipt capacity in WH-003/004 is evaluated after authenticity verification; a signature-verification call can therefore occur before that storage rejection. It still returns non-success with no false acknowledgement. Receipt counts are not a provider-call budget or a verification cache. This precision note records the intended admission stages before any WH acceptance is marked; no validator, test or original CC/PM acceptance condition was relaxed.

## Delivery and retry rules

Only acknowledge after accepted facts are durable. Capacity rejection uses a non-success response so the sender can retry. Shopify documents a five-second response window and repeated delivery; PayPal documents non-2xx retries over three days. Do not promise retries forever or recovery of events never received. See [Shopify delivery verification](https://shopify.dev/docs/apps/build/webhooks/verify-deliveries) and [PayPal webhook integration](https://developer.paypal.com/api/rest/webhooks/rest/).

## Verified local defaults

Default: 16 active handler threads. A watchdog closes request sockets after ten seconds from admission, including slow header/body delivery. This does not cancel database/provider work already executing or guarantee real-time scheduling. Excess connections receive 503 before thread creation. SQLite busy wait defaults to two seconds, validated above zero and no greater than five; no business deadline changes.

Callbacks share a global bucket (burst 60, refill 10/second) and per-registered-store buckets (burst 20, refill 2/second across providers). At most 256 store buckets are retained. Only idle, fully replenished buckets may expire after 600 seconds; a full table refuses a new key instead of resetting another store's budget. Delivery IDs and forwarded-address headers cannot create identities. Body size remains 128 KiB. Ambiguous framing and duplicate security headers fail closed.

Receipts are retained for 30 days from first receiver arrival; duplicates do not extend expiry. Defaults: 32 acknowledged IDs per normalized facts hash, 10,000 per store/kind, 100,000 globally. Every acknowledged ID retains its conflict check during retention. Capacity exhaustion receives 503, never false success. Same-content aliases do not repeat business mutation. Authenticity is still verified before acceptance.

Expiry is lazy on startup, ingress or explicit maintenance, not a scheduled deletion deadline. No unexpired identity is evicted. Migration conservatively gives legacy rows a full receiver-time window; over-cap legacy databases may remain over limits until expiry while new admissions fail closed. After expiry, the old ID-conflict guarantee ends; immutable payment facts, original associations and order chronology still protect business state. Receipt maintenance never deletes business history or automatically shrinks SQLite file bytes.

These application bounds do not establish production denial-of-service resistance, deployed proxy configuration, indefinite storage limits or authentic delivery. A configured secret is not connection proof.

## Private backups

Use Python 3.13.15. Backups contain order/payment facts and need the same access protection as the active database; this command does not encrypt them.

```sh
python3 scripts/monitor_backup.py var/monitor.sqlite3 var/backups/monitor-before-change.sqlite3
```

The command uses SQLite's consistent backup API, creates a new file with mode `0600`, checks integrity, monitoring-table presence and foreign-key consistency, and refuses existing destinations. An unrelated or empty database cannot receive a success result. Its progress callback imposes a ten-second backup deadline. It creates the final destination directory with mode `0700` when missing; intermediate and existing directories retain their normal permissions. Use a private parent path. Failure retains any partial destination for inspection and never certifies it as a restore point.

To restore, stop monitoring first and preserve the active database. Copy the selected backup to a new path, then start with that path:

```sh
python3 scripts/monitor_backup.py var/backups/monitor-before-change.sqlite3 var/monitor-restored.sqlite3
python3 -m crashcart.monitor_server --db var/monitor-restored.sqlite3 --port 8790
```

Sign in again and inspect orders, deadlines and alerts. Sessions are not stored in the database. These local probes do not establish host-reboot recovery, physical-disk durability, off-site backups or a deployed disaster-recovery plan.

## Evidence — 6 November 2026

[Source snapshot, commands, actual outputs, browser observations and both independent reviews](../evidence/runs/submission-ready/monitor-v2.json). Full suite: **456 tests in 103.486s, OK**; replay: **3 tests in 1.295s, OK**; existing UI: **14 pass, 0 fail**. Each independent reviewer reran all 89 monitoring tests with resource warnings treated as errors. The security run blocked non-loopback socket connections and observed zero attempts.

The actual default receiver rejected a 33rd same-content alias with 503/Retry-After while retaining one order and one alert. Initial browser pressure reached 16 active slots, retained the displayed record and produced the busy message in the DOM before recovery. Screenshot inspection later found that notice below the viewport. Its sticky repair was verified through ordinary validation, real connection loss, session recovery and acknowledgement on desktop/390px phone, including measured visibility and unobscured focus. The exact combined pressure/notice screenshot after repair remains **unverified**: a short window expired before assertion and a replacement pressure harness hit a connection reset; that follow-up stopped after two attempts. Backend saturation proof is not relabelled as fresh combined pixel proof. Synthetic facts and local signatures remain distinct from real provider execution.

Initial deep-JSON failure, incomplete parallel-import attempt and connection-warning run remain recorded. No original failure was removed and no validator or order deadline was weakened.

A fresh local Git clone of committed source `ee088df` also passed the documented monitoring CLI (page/login/empty stores) without a private environment file or provider credentials. A separate fresh-clone probe passed store creation and the backup command. [CLI proof](../evidence/runs/submission-ready/monitor-v2/clean-clone-cli.json) · [store/backup proof](../evidence/runs/submission-ready/monitor-v2/clean-clone.json). Temporary processes and data were removed.
