# Recorded walkthrough verification — 4 November 2026

Source: `0e6bee2` for judge access, `f878402` for public replay. Later hosting and documentation commits do not change these runtime files. Python 3.13.15, Node 22.14.0. No real service credentials or new payment were used.

| Exact command | Observed result |
| --- | --- |
| `python3 -m unittest discover -v` | Ran 367 tests in 55.789s; OK; exit 0 |
| `python3 -m unittest tests.test_public_replay -v` | Ran 3 tests in 0.329s; OK; exit 0 |
| `npm run build --prefix studio` | TypeScript check and build; exit 0 |
| `npm run test:deadlines --prefix studio` | tests 45; pass 45; fail 0; exit 0 |
| `python3 -m compileall -q crashcart scripts tests` | exit 0 |
| `node --check web/app.js` | exit 0 |
| `node --check web/marketing.js` | exit 0 |
| `node --check web/judge/app.js` | exit 0 |
| `python3 scripts/verify_foundation.py` | Clean setup/migrate twice/worker/health/web; assertions PASS; exit 0 |
| `python3 -m crashcart prerequisites` | exit 0; external services unconfigured, connectivity not verified |

The final full-suite run follows the mobile text-spacing correction. The prior run (367 tests in 66.012s, OK) is retained privately.

## Actual replay outcomes

`python3 -m crashcart.replay run evidence/runs/paypal-live/early-response-loss-input.json --merchant defective` returns FAIL / paid_without_ticket / 0 tickets / exit 1.

The same command with `--merchant healthy` returns PASS / ticket_delivered_once_on_time / 1 ticket / exit 0, delivery at +32.261423 seconds. The input and 60-second rule are identical. The original late input remains unchanged and its healthy variant still fails with ticket_delivered_late. All three cases have regression coverage.

## Browser and independent review

Real browser checks covered 1280px, 390px and 320px layouts, walkthrough state changes, Enter/Space, failed/repaired selection, PayPal filtering (4 of 15 records), expandable details and case-specific downloads. No horizontal overflow at 390/320px and no warning/error logs were observed. The in-product Reduce motion control produced animation:none and 0s transitions while interactions still worked; the OS preference itself was not toggled. A missing space on mobile was fixed and rechecked. Two incorrect automation locators were recorded and corrected from inspected DOM roles/IDs.

The actual browser-downloaded ZIP was extracted and both replay commands executed: expected exits 1 and 0. Its README carries the exact MIT notice. Independent review executed 11 judge/replay tests in 2.114s, OK, with no external network/DNS or environment-file reads observed. It found and resolved a missing licence notice in judge-specific packaging, then accepted the final one-space HTML correction. Executable replay core and validators remain unchanged.

These are local and recorded-replay results, not fresh Sandbox proof. **This recorded-review batch remained 44/60; newly verified requirement IDs in that batch: none.** The original fault recording and live gates in [OPEN_CHECKS.md](OPEN_CHECKS.md) remain open. Part F is gated by Part A.

Private raw logs, browser captures, source hashes and review receipts are retained under `evidence/runs/judge-ready-v53/` in the owner's acceptance archive; they are not required to run the public tests or included as private raw evidence in this repository.

## Hosted readback

[Source CI](https://github.com/himanshu748/crashcart/actions/runs/41802366607) passed on `ba7ac9c`: 367 tests in 47.094s, OK; 45 timing tests passed, 0 failed. [Pages deployment](https://github.com/himanshu748/crashcart/actions/runs/41802528629) succeeded. The [public landing page](https://himanshu748.github.io/crashcart/) was inspected in a real browser: site-build disclosure, animated walkthrough controls, repaired-case selection, 4-of-15 PayPal filtering and 390px no-overflow layout worked. No warning/error console logs were observed.

Hosted JSON download verification initially timed out twice (download event, then the browser's file-link download helper); that step stopped under the two-attempt rule. Those failures remain recorded.

A separate native Safari check on 4 November completed both UI downloads after granting the site's download permission. Safari listed the JSON (130,204 bytes) and ZIP (25,516 bytes) as complete. Both were byte-identical to the HTTPS artifacts fetched and tested independently. The ZIP's seven-file manifest passed, its MIT notice was present, and its defective/healthy commands produced the expected exits 1/0 and signatures above. This verifies Safari delivery, not a resolution of the earlier task-browser limitation.

- JSON SHA-256: `de463f4bb83d4436292c6879f17abcdeab999970e829d2690158152217510067`
- ZIP SHA-256: `8d436ff1043743f8408e7a67c6438acff2770dda54cb406447019f65a511091f`

Sanitized receipts are in [hosted-downloads-v54.json](../evidence/runs/judge-ready/hosted-downloads-v54.json). Native download readback, exact downloaded files and execution logs remain in the private `evidence/runs/continuation-v54/` archive. The download check left acceptance at 44/60; it accepted no new CC requirement.


## Current-source recheck

On 4 November the unchanged public runtime was rerun with Python 3.13.15:

```sh
env PATH=/opt/homebrew/opt/python@3.13/libexec/bin:/opt/homebrew/bin:/usr/bin:/bin PYTHON=/opt/homebrew/opt/python@3.13/libexec/bin/python3 python3 -m unittest discover -v
# Ran 367 tests in 56.845s — OK
env PATH=/opt/homebrew/opt/python@3.13/libexec/bin:/opt/homebrew/bin:/usr/bin:/bin PYTHON=/opt/homebrew/opt/python@3.13/libexec/bin/python3 python3 -m unittest tests.test_public_replay -v
# Ran 3 tests in 1.703s — OK
```

These are the exact commands for this Mac. Other supported installations can use `python3` directly, after confirming version 3.11 or newer and making the same interpreter available to child processes. The first recheck accidentally resolved macOS Python 3.9.6 and failed (367 tests; three failures and three errors). Its log is retained; no product source, assertions or deadlines were changed before the corrected pass.

The current Postman export also passed seven local assertions and 48 assertions across six GETs of copied historical Sandbox records. Missing proof produced the expected failing exit with 14 assertion failures and no skips. No provider requests or payments occurred. CC-050 still depends on CC-035. See [the sanitized execution summary](../evidence/runs/judge-ready/postman-v54.json).


## Later actual notification verification

CC-023 passed on 4 November in a separate actual PayPal Sandbox checkout through local Safari. It is not a replay of the keyless page. First authentic delivery and its targeted resend each passed signature verification (HTTP 200); the resend was a duplicate. A locally initiated invalid-signature probe against the real ingress returned HTTP 400 and changed no counts. One completed USD29 capture, one event and zero tickets for the intentionally defective merchant were independently inspected. Cleanup removed only the newly created webhook and confirmed its absence; all processes and tunnel stopped in 211.213 seconds. No KERNEL or model call was made.

[Sanitized receipts](../evidence/runs/judge-ready/webhook-v55.json) distinguish the negative probe from provider-origin delivery. Exact raw event bytes, source snapshots, prior failure and independent review remain in the private `evidence/CC-023/live-v55/` acceptance packet. Current acceptance is **45/60**. CC-024 still needs a current-source recovery experiment; its old mode/source cannot be relabelled.

After accepting CC-023, the same explicit Python 3.13.15 commands above were rerun: `unittest discover -v` reported **367 tests in 115.397s, OK**, and `unittest tests.test_public_replay -v` reported **3 tests in 0.858s, OK**. Logs are retained in the private `evidence/runs/continuation-v55/` archive. No public runtime source changed in this acceptance update.
