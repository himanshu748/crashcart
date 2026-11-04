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

These are local and recorded-replay results, not fresh Sandbox proof. **44/60 remains unchanged; newly verified requirement IDs: none.** The original fault recording and live gates in [OPEN_CHECKS.md](OPEN_CHECKS.md) remain open. Part F is gated by Part A.

Private raw logs, browser captures, source hashes and review receipts are retained under `evidence/runs/judge-ready-v53/` in the owner's acceptance archive; they are not required to run the public tests or included as private raw evidence in this repository.
