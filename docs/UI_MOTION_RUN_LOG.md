# Landing and motion pass — 10 November 2026

All times are IST. Branch: `ui-motion-nov10`, based on main `f703225`.
This is local presentation work. No push, PR, merge, deployment or submission edit is authorized until its own exact `submit`.

## Scope

The public landing entry is `web/judge/index.html`; the separate `web/index.html` is the private workspace and is preserved. The public landing now explains the missing-ticket problem through a payment-to-delivery illustration and a four-part scroll story. The demo and product retain their saved records, wording, deterministic verdicts and controls. Only their presentation is animated.

- Self-hosted Manrope and Instrument Serif, with original SIL OFL notices.
- Locally vendored GSAP/ScrollTrigger 3.15.1, with the complete no-charge standard licence and provenance. GSAP is not MIT. No external CDN, tracker, model or payment call.
- Actual product screenshots converted to bounded WebP images; lazy loading is retained.
- `font-src 'self'` is the only prepared CSP addition. Static deployment configurations are not deployed.
- Desktop uses pinned/scrubbed panels; smaller screens keep the visual and its explanation together without pinning. Native cross-document transitions are progressive enhancement.
- The hero is a time-compressed illustration: $29, a 60-second promise, zero tickets, then a separate repaired replay with one ticket at 32.26 seconds. The 22 October replay and 8 November AI case are explicitly separate.
- The recorded badge remains beside the primary call to action; the footer explains the saved/live boundary.

## Log

- 18:14 — First corrected Lighthouse audit passed mobile 97/96/100/100 and desktop 100/100/100/100. Every required motion script returned HTTP 200. Initial failed audits were retained: mobile 61, contrast failures, a favicon 404, and an invalid desktop audit with motion.js not loaded. Thresholds and throttling were not weakened.
- 18:18 — Captured the existing public landing at 375, 768, 1280 and 1920 pixels. Earlier desktop captures clipped by the legacy screenshot API were rejected and retaken with actual matching viewport/bitmap dimensions.
- 18:20 — Corrected a stale viewport capability binding; its two unsuccessful sizing attempts were not counted as responsive proof. A new documented capability handle applied the requested dimensions.
- 18:22 — Actual browser checks exercised all four scroll-story panels and reverse scrolling. The page's Reduce motion switch removes pinning and restores every panel to the accessibility tree. A reviewer found an OS-reduced-motion gap in asynchronously rendered demo steps; the shared guard, queued-frame check and reversible context ownership were repaired. Six new control/cleanup regressions pass.
- 18:24 — Product marker motion was converted from width/left updates to transforms without changing the illustration rule or values. Browser inspection caught overflow from its full-width transform carrier; bounded chart clipping fixed it. Product, recorded example and integrations fit at 375, 768, 1280 and 1920 pixels with document width equal to viewport width.
- 18:25 — The repair button selects the recovered recorded case in one activation: 1 ticket at 32.26 seconds; the missed order remains 0 tickets. Keyboard activation of the AI evidence tabs works. Under the page motion toggle, freshly selected facts have no transform and no number-overlay clones.
- 18:27 — Native recording preflight twice returned `EXACT_CAPTURE_WINDOW_NOT_UNIQUE`, matches 0. No recording began. Asked the owner to bring the exact local CrashCart Safari window forward and keep the Mac unlocked; independent checks continued.
- 18:30 — A full-opacity hero keeps every label readable while cards translate/scale. The ticket card changes state to red at the illustrated deadline. Final Lighthouse release audit: mobile 100/100/100/100, desktop 100/100/100/100; mobile LCP 1351.58 ms, desktop LCP 531.95 ms, initial transfer 328907 bytes. All four scripts loaded; runtime error absent. Private HTML/JSON reports and traces are retained.
- 18:31 — Focused Python checks: 21/21 passed. Motion/illustration JavaScript checks: 18/18 passed. Invariant SHA-256 remains `01c7007132e939716f5236322f40b175058981d21334c7add57dd4bb20007fea`.
- 18:32 — Committed the feature as `50ee0b2`. Whitespace review exposed upstream spaces/empty final lines in the vendored files; preserved notices and normalized only that whitespace in `5f99441`, with exact local file hashes added to provenance. Full diff whitespace check then passed. No check was suppressed.
- 18:33 — A fresh local clone at `5f99441` has no .env, keys or installed project packages. Started the full source CI-equivalent suite, lint/types, replays and optional Studio checks. The retained first run failed one of 598 tests; see the repair below.
- 18:34 — Owner confirmed Safari visible. The resumed native capture preflight still found no exact window; a read-only diagnostic returned no Safari windows from the native on-screen capture inventory. Recording remains unverified. No full-display capture or screenshot montage was substituted.

## Approval boundary

New-head GitHub CI cannot run until the feature branch is pushed. A local suite pass is not remote CI. Push, PR, merge, dedicated-host deployment, Pages publication and Devpost edits remain separate gated actions. Nothing public has changed.

The original 47/60 acceptance count is historical and unchanged. No CC requirement is closed by this presentation pass.

- 18:37 — The first fresh clone returned 503 from the actual `/recorded/` integration test (597/598 passed). Cause: its 17-member exact asset boundary had not been updated for the new presentation files. Fixed it by sharing the explicit public-asset constants between judge and workspace server. The namespace now has exactly 32 allowed members, adds only WOFF2/WebP/SVG MIME types, and retains byte limits, read-only POST rejection and private-route isolation. The failed run remains retained.
- 18:37 — Focused namespace/asset checks: 13/13 passed. Committed the repair as `d980422` and cloned it into a new directory.
- 18:41 — Corrected fresh clone: 598 Python tests in 133.537s, 17 judge checks in 3.005s, 97 JavaScript tests, Ruff clean, mypy clean in 33 source files, compile/syntax/foundation/prerequisites checks all pass. Studio typecheck/build passes; 45 timing, 7 presentation and 6 recorded-explorer tests pass (58 total). No test or deadline weakened.
- 18:42 — A separate fresh keyless clone, without `.env` or `studio/node_modules`, starts with `./scripts/judge.sh --no-open --port 8911`. Landing/product/example/health/font/vendor-script responses return 200. Both replay commands retain their required exits: defective 1 / FAIL / paid_without_ticket / 0 tickets; healthy 0 / PASS / ticket_delivered_once_on_time / 1 ticket. Both measured network_calls=0.
- 18:44 — Exact final-runtime clean-clone Lighthouse: mobile 100/100/100/100, desktop 100/100/100/100, mobile LCP 1352.46ms, desktop LCP 474.26ms, transfer 328903 bytes, every motion script 200. All 22 public presentation assets together total 408128 bytes, below 1.5MB including lazy media and the other public pages.
- 18:44 — Actual clean-clone browser checks confirmed the hero completes at 60s, the missing state turns red, keyboard skip navigation focuses main with a visible outline, and all four desktop panels reach opacity1 with all other panels opacity0 during forward scrolling. Reverse scrolling restores the earlier panels. No console warnings/errors observed.
- 18:45 — Independent final source review found no blocker. Reviewer reran 13 namespace/asset tests successfully and confirmed unchanged payment/replay/invariant source, exact immutable allowlist, unchanged size limits and POST405.
- 18:46 — Native capture diagnosis isolated the on-screen inventory filter: optionAll uniquely finds the exact Safari window while optionOnScreenOnly does not. Prepared and compiled a bounded, window-only ScreenCaptureKit recorder, audio/microphone off, 30-second process watchdog and 20-second encoded capture. No full-display fallback.
- 18:46–18:49 — Two actual recordings captured the correct CrashCart window, but native pointer actions failed with `noWindowsAvailable`, so the requested scrolling did not occur. The first video has 20.018 seconds and no audio stream; this is not accepted as scroll proof or as proof of60fps. Both originals and the UI errors remain private. Stopped that step after two failures and asked the owner to put Safari on the active Desktop/Space. No third recording attempt made.
- 18:50 — Remote main remains f703225; the remote ui-motion-nov10 branch does not exist. All changes remain local. Screenshots at all four requested widths are saved under docs/images/ui-motion-nov10/.

## Current result

Runtime source: d980422; release-gate configuration d99f47b. The runtime/test/web/studio/scripts trees are byte-identical to the successful fresh-clone suite after those source checks. The owner explicitly redirected recording to the browser; that actual scroll clip is now recorded and frame-reviewed. Remote CI remains pending the gated branch push, and no public deployment has occurred.

Private audit HTML/JSON/traces, full command logs, failed captures and capture diagnostics remain outside tracked source in the task's local QA directory. The screenshots contain only public product content. No credentials, AG Studio licence bundles or videos are committed.

- 18:52 — Owner explicitly requested browser/Hyperframes recording and no computer use. Ended the computer-use part and made no further computer-use calls. The installed Playwright CLI skill wrapper returned `playwright-cli: command not found` once; used the official pinned Playwright1.65.0 library in private tooling instead, following the [documented recordVideo API](https://playwright.dev/docs/videos).
- 18:55 — Actual browser recording succeeded, with all requests restricted to127.0.0.1:8911. No screenshot montage, fixture mutation, clock virtualization or synthetic motion. Also exercised the real `(prefers-reduced-motion: reduce)` branch through browser context emulation: all four panels opacity1/transformnone, no pinning, replay illustration hidden. No macOS settings changed.
- 18:57 — A second browser recording omitted still-screenshot readbacks during filming. Measured1288 requestAnimationFrame intervals: median16.7ms, p9516.7ms, maximum33.4ms, one interval over25ms. This is scoped browser timing, not a universal rendered-FPS guarantee. The browser video encoder is25fps; no duplicated/interpolated60fps claim is made.
- 19:00 — Exported consecutive source seconds1.8–21.8 as dist/crashcart-landing-motion-20s.mp4:20.000s,1920×1080,500frames,25fps,5751904bytes, no audio. Full decode passed. Inspected extracted frames showing the actual AI screenshot,32.26s repair and sponsor section; this is the accepted20-second scroll clip. Original browser files and rejected native clips are preserved locally; MP4 is gitignored and not uploaded.
- 19:04 — Prepared Pages as manual-only publication on this branch to preserve the separate deployment approval. It requires main and successful Source behavior CI for the exact commit, then runs judge/replay/asset checks before export. YAML parses, shell syntax passes, and5 synthetic shell-guard cases reject missing/invalid/zero CI counts and accept positive counts. This is local configuration proof; no remote workflow was dispatched. Committed291cf55. Dedicated-host deployment also remains separate.

- 19:11 — Tightened the prepared manual Pages guard to require the latest push CI result for the exact main commit. Missing, failed or cancelled runs fail closed; an older success cannot bypass a newer failure. Five offline conclusion/argument cases pass. Commit d99f47b; no GitHub workflow run or publication.
