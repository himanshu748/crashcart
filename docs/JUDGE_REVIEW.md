# CrashCart from a judge's first visit

Reviewed 8 November 2026 against the [official rules](https://paypalaihackathon.devpost.com/rules), live Devpost judging criteria and sponsor pages. This is an engineering assessment, not an organizer ruling or prediction of scores.

The problem is clear: a payment can complete while an order remains unfulfilled. PayPal is central to the implementation. The public walkthrough explains that problem and its failure/repair comparison. Its biggest weakness is that a visitor cannot experience the full PayPal-plus-AI workflow or sponsor workspace from that recorded page. Adding sponsor names would not fix that gap.

## What each integration contributes

| Integration | Useful work | Available experience and limits |
| --- | --- | --- |
| PayPal REST APIs | OAuth, order creation/capture, durable request identity, independent retrieval, authenticated payment notifications and exact purchase/amount/ticket correlation. | Recorded comparison and historical authentic webhook/recovery results. This is a handwritten API adapter, not a PayPal SDK. |
| Modal + DeepSeek | Chooses the next evidence read; deterministic code decides the outcome. Operator-requested investigations now run in a durable background worker. | Historical real model sequence in [AI evidence](AI_EVIDENCE.md); new queue and endpoint configuration tested locally with injected replies. No current hosted inference claimed. |
| AG Studio | Actual SDK with linked custom widgets, saved-record queries and a native agent harness. | Separate configured Records workspace; not loaded by the keyless page. Licence and full operator access still need provision. |
| Bryntum Community Scheduler | Actual SDK plots payment-relative promises and ticket milestones and links to their investigations. | Separate Delivery timing page; refuses uncorrelated data rather than inventing a timeline. Full operator journey remains open. |
| KERNEL | Explicitly granted remote browser observation and recording, correlated to the existing checkout. | New [observation runner](kernel-runner.md) calls the actual bounded adapter. Tests inject KERNEL replies; no fresh session was run. Review is required before receipt import. |
| Postman / Newman | Actual collection checks API health and selected purchase/payment/ticket identities. Missing payment proof fails instead of being skipped. | Runnable local collection, no cloud account. It makes no new payment or provider request. |
| APIMatic Context Plugin | Development-time PayPal API guidance and serialization work. | Supporting development work; no generated SDK runs in the product. Do not claim a runtime integration or strong standalone prize case. |

AG Studio and Bryntum do useful work in the browser. Postman is a developer tool. They should not become artificial background tasks merely to make every sponsor appear active. Render remains excluded; Modal is a model host, not a listed event tool sponsor.

## Connected operator workflow

1. Checkout and verified PayPal notifications persist payment facts in the shared database. The recovery worker independently rechecks unresolved payment before fulfilment.
2. **Investigate** enqueues one durable background request. The worker uses the existing bounded investigator, model authorization and evidence tools. Reload does not submit another inference.
3. Saved model plans, observations and deterministic findings are available through the same authenticated API used by the main workspace and AG Studio. Bryntum requires independently confirmed, correlated payment facts before plotting; an AI suggestion cannot manufacture them.
4. A separately authorized KERNEL observation can be reviewed and imported into that same case. Neither AI nor page reload can start a paid browser session.
5. Postman checks the linked records without creating a checkout.

Server and worker must use the same database and private configuration:

```sh
python3 -m crashcart serve --db var/crashcart.sqlite3 --port 8765
# In a second terminal:
python3 -m crashcart worker --db var/crashcart.sqlite3
```

Enable only explicitly authorized provider usage. One background investigation is allowed per case. Failed/interrupted dispatches are retained and never automatically replayed. The existing synchronous API remains available for separately authorized operator work. [Model configuration](investigator.md) explains exact Modal origin pinning.

## Assessment against the rubric

- **Technological implementation:** substantive payment/recovery logic and historical real AI use. The recorded entry alone does not show the full integration operating now.
- **Design:** current source has a product-first landing page and clearer workflow. Public hosting still serves an older build because GitHub is billing-locked.
- **Potential impact:** a specific merchant pain and credible mechanism. No connected merchant store, adoption or measured business impact is established. Shopify matching, installation and accounts remain unfinished.
- **Innovation:** correlation and reproducible failure recovery are the concrete mechanism. Market novelty is not established.
- **Presentation:** the missing public end-to-end video and inaccessible configured sponsor screens are material weaknesses. Use the [video script](VIDEO_SCRIPT.md); show historical AI as a separate dated case, and actual sponsor screens when they run.

[AG Grid's guidance](https://paypalaihackathon.devpost.com/details/aggrid) favors custom widgets, polish and its agent framework. Existing code fits that direction, but a page loading none of it is insufficient demonstration. [Bryntum's lane](https://paypalaihackathon.devpost.com/details/bryntum) rewards useful scheduling/timeline use; the delivery timeline fits, subject to working access.

## Tests and remaining work

```sh
./scripts/test-judge.sh
python3 -m unittest discover -v
node --test tests/test_*ui.cjs tests/test_workspace_api.cjs
npm run typecheck --prefix studio
npm run test:deadlines --prefix studio
```

Local tests use injected provider/model replies where specified. They do not establish fresh PayPal, model or KERNEL execution. [Historical webhook result](../evidence/runs/judge-ready/webhook-v55.json), [recovery](../evidence/runs/judge-ready/recovery-v56.json) and [AI](AI_EVIDENCE.md) keep their original dates and scope.

Next: restore public publication, provide the configured sponsor workspace and end-to-end video, then verify owned test-store data with separately authorized provider use. Original acceptance remains **47/60**; no original requirement is closed by this review.
