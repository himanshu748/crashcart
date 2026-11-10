# Sponsor-prize STOP report

Prepared 10 November 2026, 16:28 IST. Branch: `sponsor-prizes-nov10`. Runtime/source tested: `244bd112916aad1e954f28a5efc3ab477966f54a`. Subsequent report-only changes do not change that runtime. Remote main remains `1cc49d9e2ff7156e36ed11155b787eca7261c214`.

**Nothing pushed, merged, deployed, messaged or edited on Devpost/YouTube. No new PayPal, model or KERNEL call. No spending or billing change.** The existing submission remains the submitted entry; this work does not create another entry or close a CC requirement.

## What is ready locally

| Item | Result |
| --- | --- |
| AG Studio | Actual pinned3.0.0 SDK, five evidence panels, matching theme, comparison, source filters and native Agent Framework. Public adapter uses labelled local filters; historical AI is separate. Missing licence serves a clear gate without SDK or records. Actual browser/Caddy render and queries passed. **Not deployed; public licence coverage pending.** |
| Presentation | README103lines; historical checklists archived with links/checker preserved. Four full-width public pages checked at1920/1440/390; footer motion control, first-click repair and smooth result navigation fixed. |
| Backend 1 | Hash-pinned public8November failure trace shown first, with saved hypotheses/citations and deterministic FAIL. Earlier23/26October delivered case secondary;22October repair input remains explicitly separate. |
| Backend 2 | Context-local socket audit guard blocks and measures replay connections; nested/concurrent tests pass. Healthy replay applies the repaired Store rule to saved input, not MerchantService. |
| Backend 3 | Proven transient read failure now resumes at+2seconds with attempt<29. Original failure remains. Only TIMEOUT/TRANSPORT_ERROR retry; permanent errors do not. |
| Backend 4 | StructuredModel plus exact OpenAIModel alias; default provider remains OpenAI. Studio description provider-neutral. |
| Backend 5 | Ruff 150→0; mypy 1→0. Behavior-neutral statement expansion/unused cleanup and UTC-offset narrowing. CI Ruff check prepared. |
| Backend 6 |41-line judge architecture map; historical workspace guide preserved. Snapshot ZIP **skipped** because scripts/tests/receipts still reference16 tracked Python snapshot files. No module/snapshot deletion. |
| Backend 7 | Shared redaction with exact output/bounds tests; one model-ID constant; deduplicated promise projection; GET type-only diagnostics; core version0.2.0; documented production/security boundaries without changing cookie or webhook semantics. |

`invariant.py` is byte-identical: `01c7007132e939716f5236322f40b175058981d21334c7add57dd4bb20007fea`. Both replay inputs are unchanged. No deadline, validator or payment verdict was relaxed.

## Final verification

Fresh local Git clone of the unpublished feature branch, no `.env`, npm modules or compiled licensed assets. Python3.13.15 selected with `PATH=/opt/homebrew/opt/python@3.13/libexec/bin:$PATH`.

```sh
python3 -m unittest discover -s tests
# Ran 594 tests in177.430s — OK
./scripts/test-judge.sh
# Ran 17 tests in6.562s — OK
python3 -m crashcart.replay run evidence/runs/paypal-live/early-response-loss-input.json --merchant defective
# exit 1 / FAIL / paid_without_ticket / 0 tickets / measured network_calls=0
python3 -m crashcart.replay run evidence/runs/paypal-live/early-response-loss-input.json --merchant healthy
# exit 0 / PASS / ticket_delivered_once_on_time / 1 ticket / measured network_calls=0
./scripts/judge.sh --no-open --port 0
# Both outcomes recomputed at launch. No new payment or service call.
```

Actual fresh-clone HTTP: `/demo.html`, `/product`, `/example`, `/healthz` all200; extensionless routes serve directly. Served CSS exactly matches final source. Missing-licence standalone entry also rendered its gate and served no SDK/data.

- `node --test tests/test_*.cjs`:91/91.
- Studio recorded adapter6/6; query presentation7/7; timing45/45; typecheck and actual SDK build passed.
- Ruff 0.14.3: All checks passed. mypy 1.18.2: no issues in32 source files.
- `./scripts/check_links.sh`:23/23 public200,17 local files, zero failures. Public checks concern the unchanged hosted release.
- Both local Caddy templates validated using official Caddy2.11.9 with loopback HTTP/admin disabled. Direct aliases200, writes405, core CSP unchanged; explorer-specific nonce/hash policy rendered the actual SDK. No live-host/TLS configuration was changed or verified.

A real final390px expanded-record failure was preserved before fixing it: panel351px expanded to1604px. Current source: document390/390, panel351/351; JSON297/1550 with its own scrolling. Fresh-clone keyboard ArrowRight moved that focused code scroller while page width stayed390. Reduced motion and keyboard disclosures passed; settings restored. Desktop1440 stays1440wide. The failing capture remains private under `var/sponsor-ui-review/`; it was not relabelled as a pass.

[Desktop AI evidence](images/crashcart-recorded-ai-desktop-expanded.jpg) · [Mobile expanded evidence](images/crashcart-recorded-ai-mobile-expanded.jpg) · [Product layout](images/crashcart-product-wide.png). Private Studio capture: `var/sponsor-ui-review/final-studio-reviewed.jpg`. Local Studio preview, while this session's server remains running: <http://127.0.0.1:8779/explorer/>.

Generic secret scan flagged16 deliberate local/test credentials, independently reviewed; binary/oversized omissions remain a stated limit. Exact current-private-value scan covered1195 reachable blobs through the backend/doc revision, with no match; subsequent CSS/config/report changes were checked separately. No MP4, `.env`, licence key, licensed compiled explorer or dependency directory is tracked. This does not certify unknown historical credential formats.

## Sponsor decisions and licence handling

- **AG Grid:** currently off. AG Grid's [6 November post](https://www.ag-grid.com/blog/build-a-payments-dashboard-without-building-a-dashboard/) promises judging-period keys. Existing private trial ends17 December; coverage through22 December is not confirmed. A recent licensing-mail search in the entrant account found no matching new message; it does not establish absence in every account. Key stays in private build environment; generated licensed assets stay ignored. A configured key marker is not entitlement proof.
- **Bryntum:** keep on. Actual MIT Community Scheduler remains in the unchanged public video at2:10–2:20. Additional timing web page skipped to protect scope/core; no commercial trial introduced.
- **KERNEL/Postman:** keep unchanged.
- **APIMatic:** keep off. Dated manual Context Plugin Python skill-pack use exists; registered-plugin invocation/generated runtime SDK is not established and sponsor acceptance of the limited claim is unconfirmed. Claim form not sent.
- **Channel3/Render:** keep off. No real Channel3 integration or Render migration.
- Video remains [the existing2:45 public video](https://www.youtube.com/watch?v=gFWje84_wEA). No cut/upload proposed. At most one Sponsor Prize can be won alongside a Grand or Honourable Mention.

## Exact actions proposed on the owner's exact `submit`

Only before **12 November 2026, 21:00 IST**:

1. Push `sponsor-prizes-nov10`, open a PR to main with this evidence, and check CI. No force-push, tag or default-branch change.
2. Merge only the reviewed/tested tree after required CI is green.
3. Deploy the17-file recorded core release from merged main to the existing Lightsail site and Pages mirror. Apply only the prepared CrashCart direct-route changes; preserve the other hosts and existing core CSP. No provider keys, worker, new instance or paid plan.
4. Update the **existing** Devpost entry from `docs/DEVPOST.md`, retain the repo/demo/video links, and add the prepared Product/AI screenshots. Preserve Submitted status and Bryntum/KERNEL/Postman selections; AG Grid/APIMatic/Channel3/Render remain off at this stage. No second submission or video change.
5. Send the prepared licence question in `docs/STUDIO_RELEASE.md` to the AG Grid team in the [official PayPal Developer Discord](https://discord.com/invite/sJ2G6DyvSK), linked by the [sponsor page](https://paypalaihackathon.devpost.com/details/aggrid). Public project URL/version/expiry only, no keys or payment records. Use an existing accessible account/channel; stop if joining, CAPTCHA, new legal terms or identity verification needs the owner.
6. **Only if** a free official key or explicit vendor coverage through22 December is obtained before the freeze: configure it privately, rebuild/test, deploy only the recorded explorer to Lightsail with the documented minimal route-specific CSP, verify actual public SDK/queries and core URLs, then publish its README/Devpost link, add AG Studio to Built With and select AG Grid. Otherwise leave the explorer unpublished and AG Grid off; do not substitute a mock or claim qualification.
7. Verify hosted URLs, Submitted status, source publication and fresh-clone judge/replay outcomes. Preserve the existing host through22 December. Make no further external/default-branch changes after the freeze.

No new payment, paid model call, KERNEL usage, webhook registration, licence purchase, billing, DNS/firewall change, YouTube upload or unrelated posting is included. Any newly required access/billing/security change is outside this action set.

## Commits and files

Local commits before this report-only update:

```text
596d544 docs: scope local sponsor-prize preparation
406c953 docs: shorten judge path and archive development checklists
31860a7 feat: prepare recorded Studio explorer and polish judge pages
5e52875 feat: show recorded failure-case AI investigation first
10814a7 fix: measure and block connections during recorded replay
22084b2 fix: resume bounded recovery after transient payment reads
43767f6 refactor: name structured model transport independently of provider
43f0617 chore: establish clean lint baseline without changing payment rules
4225599 docs: map judge path and preserve referenced history
0ce8361 refactor: share model safeguards and clarify production boundaries
c21cfab docs: prepare sponsor changes and clarify recorded investigations
244bd11 fix: contain expanded evidence on mobile and prepare direct routes
```

Changed file paths (including archive renames; generated builds excluded):

```text
.github/workflows/ci.yml
.gitignore
AGENTS.md
README.md
crashcart/__init__.py
crashcart/hosted_live.py
crashcart/investigator.py
crashcart/judge.py
crashcart/kernel_evidence.py
crashcart/model_allowance.py
crashcart/model_ids.py
crashcart/model_transport.py
crashcart/monitor_connectors.py
crashcart/monitor_ingress.py
crashcart/monitor_server.py
crashcart/monitor_store.py
crashcart/promise.py
crashcart/recorded_ai.py
crashcart/recorded_studio.py
crashcart/recording.py
crashcart/redaction.py
crashcart/replay.py
crashcart/replay_workspace.py
crashcart/server.py
crashcart/studio_agent.py
crashcart/worker.py
deploy/judge/Caddyfile.recorded-studio
deploy/judge/Caddyfile.shared-static
docs/ARCHITECTURE.md
docs/DEVPOST.md
docs/LIVE_FLOW.md
docs/REMAINING_VERIFICATION.md
docs/RULES_READINESS.md
docs/SECURITY_BOUNDARIES.md
docs/SPONSOR_PRIZE_RUN_LOG.md
docs/SPONSOR_PRIZE_STOP.md
docs/SPONSOR_SUBMISSION_DRAFT.md
docs/STUDIO_RELEASE.md
docs/WORKSPACE.md
docs/WORKSPACE_ARCHITECTURE.md
docs/archive/BUILD_CHECKLIST.md
docs/archive/MILESTONES.md
docs/archive/STATUS.md
docs/evidence.md
docs/images/crashcart-product-wide.png
docs/images/crashcart-recorded-ai-desktop-expanded.jpg
docs/images/crashcart-recorded-ai-desktop.jpg
docs/images/crashcart-recorded-ai-mobile-expanded.jpg
docs/images/crashcart-recorded-ai-mobile.jpg
docs/kernel-browser.md
docs/postman.md
docs/replay.md
docs/sponsor-ledger.md
docs/studio.md
evidence/README.md
evidence/runs/submission-ready/ai-failure-nov8-summary.json
pyproject.toml
scripts/check_completion.py
studio/build-recorded.mjs
studio/build.mjs
studio/package.json
studio/src/main.tsx
studio/src/query-agent.ts
studio/src/query-widget.tsx
studio/src/recorded.ts
studio/src/style.css
studio/test-recorded.mjs
tests/helpers/ui_vm.cjs
tests/studio_recorded_test.ts
tests/test_completion.py
tests/test_judge.py
tests/test_judge_ui.cjs
tests/test_model_naming.py
tests/test_recorded_ai.py
tests/test_recorded_studio.py
tests/test_replay_network.py
tests/test_shared_model_polish.py
tests/test_worker_recovery.py
web/judge/app.js
web/judge/demo.html
web/judge/index.html
web/judge/integrations.html
web/judge/product.html
web/judge/style.css
```
