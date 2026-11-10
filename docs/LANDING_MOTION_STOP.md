# Landing polish — ready for local review

10 November 2026, 21:49 IST. Branch: `landing-motion-nov10`.
Runtime tested from a fresh local clone: `941974b5bc8c9270c41f77d9a525b7a8c9c44a6f`.
No push, PR, merge, deployment, deletion, Devpost or sponsor change occurred.

## Small patch to PR #5

The existing motion landing stays. Only its HTML and 14 lines of CSS changed:

- “Try interactive demo” and “Watch 2:45 demo” accurately describe the existing destinations. The demo stays relative, so the same export works independently on Pages and the dedicated host.
- Recording disclosure is in the footer; the illustrated and saved product states retain their replay labels. No new live-payment or model-call claim.
- Mobile layout takes effect immediately while GSAP removes the old desktop pin, including when resizing an actively pinned story. Content stays in flow; overflow is not hidden.
- A specific footer-heading rule prevents mobile page-heading styles from enlarging the note. Mobile spacing separates the action buttons and visual.

No JavaScript, backend, recorded data, invariant, deadline, sponsor choice or AG Grid question changed.

## Before and after

Actual browser captures, each 1000px high. Before means PR #5's current Pages source; the host's older landing was audited separately.

| Width | Before | Hero | Mid-scroll | Footer |
| --- | --- | --- | --- | --- |
| 360px | [Before](images/landing-motion-nov10/before-360.png) | [After](images/landing-motion-nov10/after-360-hero.jpg) | [After](images/landing-motion-nov10/after-360-middle.jpg) | [After](images/landing-motion-nov10/after-360-footer.jpg) |
| 1920px | [Before](images/landing-motion-nov10/before-1920.png) | [After](images/landing-motion-nov10/after-1920-hero.jpg) | [After](images/landing-motion-nov10/after-1920-middle.jpg) | [After](images/landing-motion-nov10/after-1920-footer.jpg) |

Additional local screenshots at 375, 768 and 1280px are retained in the ignored QA directory. All five widths have document and body widths equal to their viewport. The immediately resized 360/375/768px layouts also fit before GSAP's asynchronous cleanup completes.

Keyboard skip navigation focuses the main content. Both the page switch and OS reduced-motion emulation expose every story panel, remove desktop pinning, and show the final illustration without replay animation. OS fallback was exercised at 360 and 1920px. No page/console errors or failed page responses; 25 local links/routes checked, including `/product`, `/example`, `/integrations`, `/demo.html`, `/healthz`, fragments and the licence. The existing YouTube link was played signed out during the audit; measured duration 165.021s.

## Lighthouse 13.6.0, fresh clone

Default mobile and desktop presets; no threshold or throttling change. All four required local scripts loaded successfully. Reports are local and not uploaded.

| Metric | Mobile | Desktop |
| --- | ---: | ---: |
| Performance | 96 | 100 |
| Accessibility | 100 | 100 |
| Best Practices | 100 | 100 |
| SEO | 100 | 100 |
| LCP | 2097.87ms | 324.83ms |
| CLS | 0.00605 | 0.00913 |
| Initial transfer | 329,421 bytes | 329,421 bytes |

The 22 presentation assets total 408,646 bytes. Layout shift is small but not claimed to be zero. Detailed reports and browser outputs are under `var/landing-motion-nov10/qa/` in the private parent workspace.

## Fresh-clone checks

Python 3.13.15, Node 26.12.0. Local environment differs from GitHub's pinned Node 22.14.0; remote CI must still run after the gated push. The unchanged `judge.sh` was launched before installing optional Studio packages, without an `.env`, keys or licence:

```sh
PATH="/opt/homebrew/opt/python@3.13/libexec/bin:/opt/homebrew/bin:$PATH" ./scripts/judge.sh --no-open --port 8914
# CrashCart recorded review: http://127.0.0.1:8914/demo.html#investigation
# Both outcomes recomputed at launch. No new payment or service call.
# Press Ctrl+C to stop.
```

The initial system-Python rejection is retained in the host plan; it was resolved using the supported interpreter, without changing the script or version check.

| Command | Actual result |
| --- | --- |
| `python3 -m unittest discover -v` | 598 tests, OK, 123.758s |
| `./scripts/test-judge.sh` | 17 tests, OK, 2.867s |
| `node --test tests/test_workspace_api.cjs tests/test_background_ui.cjs tests/test_judge_ui.cjs tests/test_site_illustration.cjs tests/test_judge_motion.cjs` | 97 passed, 0 failed |
| `ruff check crashcart` | All checks passed |
| `mypy crashcart --ignore-missing-imports` | No issues, 33 files |
| `npm ci --ignore-scripts --prefix studio` and `npm run build --prefix studio` | Passed |
| `npm run test:deadlines --prefix studio` | 45 passed |
| `npm run test:presentation --prefix studio` | 7 passed |
| `npm run test:recorded --prefix studio` | 6 passed |

Compileall, all CI JavaScript syntax checks, foundation and prerequisites also pass. Same saved input and unchanged rules:

```sh
python3 -m crashcart.replay run evidence/runs/paypal-live/early-response-loss-input.json --merchant defective
# exit 1 / FAIL / paid_without_ticket / 0 tickets / network_calls=0
python3 -m crashcart.replay run evidence/runs/paypal-live/early-response-loss-input.json --merchant healthy
# exit 0 / PASS / ticket_delivered_once_on_time / 1 ticket / network_calls=0
```

The invariant SHA-256 remains `01c7007132e939716f5236322f40b175058981d21334c7add57dd4bb20007fea`. No CC requirement or historical 47/60 count was changed.

## Scroll recording

Local ignored artifact: `dist/crashcart-landing-scroll-20s.mp4`.
Actual Playwright browser video, with consecutive source seconds trimmed; no screenshot montage, synthetic product states, audio or upload. H.264, 1920×1080, 20.000s, 500 frames at 25fps, 4,525,026 bytes. Full decode passed. Hero, saved investigation, repair and Bryntum frames were inspected.

One isolated browser session measured requestAnimationFrame intervals with median 16.7ms, p95 16.8ms, maximum 16.8ms and zero intervals above 25ms. This is not a universal FPS guarantee; video encoding is 25fps. Recording reported no external page requests or page errors.

## Deployment and next gate

[Dedicated-host deployment and rollback](LANDING_HOST_PLAN.md). The candidate's static export and Caddy configuration were prepared and validated locally. No remote preflight or deployment has occurred; activation must recheck the existing host over pinned SSH. Both sites will use the same merged-source export.

Remote main remains `2aa20c5`. Existing branches `imgbot`, `ship/devpost`, `sponsor-prizes-nov10`, `ui-motion-nov10` are retained. This feature branch is local only. New PR URL, merge URL and new-head CI are pending publication.

The next exact `submit` authorizes **only pushing `landing-motion-nov10` and opening its PR**, then reading CI results. Merge, Pages publication, dedicated-host deployment and each branch deletion remain separate gates in the host plan. No public action is included in this STOP report.
