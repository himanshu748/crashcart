# Presentation review — local candidate, stopped before publication

11 November 2026, 20:27 IST. Branch `fix/judge-presentation-nov11`, based on
`f0c3324500cfdf0c957093503b9056bbcb66fc1b`. Changes are local and uncommitted.
No payment, provider/model/TTS call, spending or external write occurred.
The public site, video, gallery and submitted entry remain unchanged.

## Ready locally

1. **Captions:** actual Studio inventory has two Published subtitle tracks:
   English (United States), Manual and Automatic. Manual offers Unpublish;
   Automatic offers Delete, not Unpublish. The exact backup/removal/readback
   steps are in [CAPTION_CLEANUP_PLAN.md](CAPTION_CLEANUP_PLAN.md). Nothing saved.
2. **Saved payment:** the new example card shows USD 29.00, COMPLETED, completion
   time, public Sandbox order/capture IDs and both Orders v2 routes. The source
   is the already-public hash-bound 8 November proof. It distinguishes the
   adapter's POST route from the saved independent GET confirmation, with
   credentials and buyer fields excluded. [Case notes](LIVE_FLOW.md).
3. **Filter:** In the demo now includes PayPal, DeepSeek and Bryntum. The
   relative timing.html link resolves on the dedicated host and Pages prefix.
4. **Mobile:** the Case column narrows and the 120-second chart fits at 390/360px.
   The ticket at 32.26s is visible immediately. The table stays usable. Fixed a
   separate reduced-motion issue where the SDK wrapper remained opacity zero.
5. **Transitions:** ordinary Chrome reproduced 11/12 errors, isolated to native
   cross-document transitions. Removing only that opt-in fixes them. In-page
   motion stays. [Browser report](PRESENTATION_BROWSER_CHECK.md).
6. **Gallery:** seven actual light-UI browser captures: Product, landing,
   PayPal evidence, recorded AI finding, separate repair, actual Bryntum and
   mobile payment evidence. No synthetic screen, metric or buyer data.
7. **Optional cut:** a complete, inspected 2:45 / 9.49MB local MP4 opens on the
   actual evidence card. The original Deepgram AAC packets are identical;
   Bryntum 2:10–2:20 remains. Full decoding and Chrome playback/seek tests pass.
   [Video plan and prospective field changes](PRESENTATION_VIDEO_PLAN.md).

The evidence-first cut is feasible before the deadline and is the prepared
candidate if the owner likes it. Keeping the current video plus the new evidence
gallery image remains a lower-risk alternative. Neither option contains fresh
PayPal approval footage: no such 8 November checkout recording exists.

## What actually passed

All commands used Python 3.13.15 where Python is required. Private logs are under
`var/judge-presentation-nov11/qa/final/`; media are in the sibling `video/` folder.
These are local review artifacts, not hosted URLs or committed public evidence.

| Command / journey | Actual result |
| --- | --- |
| `python3.13 -m unittest discover -s tests` | 605 tests, 115.065s, OK |
| `PYTHON=python3.13 ./scripts/test-judge.sh` | 18 tests, 3.672s, OK |
| `PYTHON=python3.13 node --test tests/test_workspace_api.cjs tests/test_background_ui.cjs tests/test_judge_ui.cjs tests/test_site_illustration.cjs tests/test_judge_motion.cjs` | 128 passed, 0 failed/skipped |
| `npm run test:deadlines --prefix studio` | 45 passed |
| `npm run test:public-timing --prefix studio` | 8 passed |
| `npm run build --prefix studio`; `npm run build:timing --prefix studio` | TypeScript and builds passed; repeat timing build byte-identical |
| `ruff check crashcart` | All checks passed |
| `mypy --ignore-missing-imports crashcart` | No issues in 34 source files |
| Compileall; JS syntax; verify_foundation.py | Passed, clean local database and worker/HTTP entry exercised |
| `PYTHON=python3.13 ./scripts/judge.sh --no-open --port 8961` | Recomputed both outcomes; root, demo, product, example, integrations, timing, healthz HTTP200 |
| Fresh static export and frozen app | Exactly 44 served files, HTTP200/MIME/hash or replay semantics verified |
| Static root and /crashcart/ prefix | 44/44 each; 137 HTML links/anchors, 8 CSS resources, actual image decoding passed |
| Chrome 157 + official Playwright Firefox 159 Gecko | Four normal/reduced profiles, normal/rapid navigation, zero console/page errors |
| Native Safari 27.0.1 Private Browsing | Local evidence/timing rendered; timing console empty; current public landing and 2:45 video loaded signed out |
| Desktop/mobile and keyboard | Filter, disclosures, saved case selection, retry, chart marker, no page overflow; 1440/390/360px |

Exact replay command (run separately for defective and healthy):

```sh
python3.13 -m crashcart.replay run \
  evidence/runs/paypal-live/early-response-loss-input.json --merchant defective
# exit 1 / FAIL / paid_without_ticket / ticket_count 0 / network_calls 0
python3.13 -m crashcart.replay run \
  evidence/runs/paypal-live/early-response-loss-input.json --merchant healthy
# exit 0 / PASS / ticket_delivered_once_on_time / ticket_count 1 / network_calls 0
```

The new payment projection adds four Python and nine UI regression tests.
Read-only integration review found no blocking issue. The invariant SHA remains
`01c7007132e939716f5236322f40b175058981d21334c7add57dd4bb20007fea`;
both replay fixtures are unchanged. Historical 47/60 is not advanced.

Private harness failures were retained, not presented as product failures or
silently called passes: a milestone's intentionally zero-width wrapper was the
wrong visual-readiness target; offscreen lazy images were not yet loaded at
networkidle; the first video seek harness stalled. Corrected tests exercised the
painted marker, decoded actual image URLs and ran the playable MP4 respectively.
One browser-control read timed out and resumed from fresh state. No check was
weakened and no timeout/deadline/payment rule was changed.

Read-only public checks also passed: dedicated host and Pages each returned
47/47 HTTP200 (44 served files plus root/product/example). Both still serve
the prior release, with no new payment card. Their static healthz bodies are
valid recorded-demo JSON; existing MIME types are text/plain and
application/octet-stream respectively, not a new JSON endpoint claim.

## One external action per exact submit, in this order

1. **Current-video caption cleanup only:** download private backups, unpublish
   its Manual track and delete its Automatic track (the only removal option),
   then refresh Studio and verify the unchanged watch URL signed out. No upload.
   This is the only action authorized by the next exact submit.
2. **Publish source for review:** commit the reviewed local patch, push only
   fix/judge-presentation-nov11 and open a PR. Inspect CI; do not merge.
3. **Merge that PR only**, after green checks and expected-head verification.
   Existing main-to-Pages automation may publish as its normal consequence;
   read back its result, do not trigger an additional workflow under this gate.
4. **Dedicated-host deployment only:** stage the merged-main 44-file static
   export on the existing dedicated instance, preserve the previous release,
   validate config and atomically switch only CrashCart's release. Verify public
   routes, filter and mobile/signed-out UI; rollback on failure. No instance,
   billing, DNS or firewall change. If SSH needs a new IP rule, stop for that
   separate access approval. Do not redeploy an already matching Pages release.
5. **Devpost gallery only:** replace the seven old screenshots with the prepared
   seven light-UI captures/captions, preserving the existing video, text, links,
   prize selections and submission. Save once; refresh signed out and inspect
   every image. This is not approval for any video change.
6. **Optional new video upload only, after local cut review:** publish the shown
   evidence-first candidate as a new video and check its watch URL signed out.
   Leave the current video, Devpost and source links unchanged at this gate.
7. **Devpost video field only:** after verified playback, replace only the
   existing submission's video URL with the verified new URL. Save once and read
   it back signed out. No sponsor, Built With, personal or legal-answer changes.
8. **Source video links:** prepare the exact README/site-link diff after a real
   new watch URL exists. Its push/PR, merge and any needed host deployment each
   require their own subsequent submit; no future URL is invented now.

No action in this list is currently executed or cumulatively approved. A submit
consumes only the next explicitly reported action; stop again after verifying
it. No tag, branch deletion, sponsor message, AG Grid question, payment or model
call is included. Stop external/default-branch changes at 12 November 21:00 IST.

## Remaining limits

- Caption cleanup and all publication are still pending. YouTube may regenerate
  automatic captions; the prepared removal is not a claim of a permanent switch.
- The optional MP4 was checked locally in installed Chrome, not uploaded or
  verified on YouTube. Existing public-video Safari playback does not prove the
  new candidate's future transcoding.
- Native Safari checks are focused/manual; the rapid-navigation and complete
  normal/reduced-motion matrix were automated in Chrome and Gecko.
- Hosted byte matching, CI for this branch and submitted-gallery readback can
  only be verified after their corresponding gates. Current live URLs remain on
  the prior release.
