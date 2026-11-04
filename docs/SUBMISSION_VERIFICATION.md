# Submission-path verification

**Verified 47/60 in the original contract. No new CC acceptance claimed.** This is a separate verification of runnable submission access. Tested source: public main `fba4ffd64e9a8a1dc41602a443aec6ac02119343`, freshly cloned from GitHub on 4 November 2026. The clean clone had no tracked changes. Subsequent submission packaging changes are documentation and isolated deployment configuration; runtime sources, fixtures and assertions remain unchanged.

## Clean clone and commands actually run

```sh
git clone https://github.com/himanshu748/crashcart.git var/submission-v61/clean-clone
cd var/submission-v61/clean-clone
env PATH=/opt/homebrew/opt/python@3.13/libexec/bin:/opt/homebrew/bin:/usr/bin:/bin PYTHON=/opt/homebrew/opt/python@3.13/libexec/bin/python3 python3 -m unittest discover -v
```

[Full output](../evidence/runs/submission-ready/full-suite-retry.log):

```text
Ran 367 tests in 60.294s

OK
```

```sh
env PATH=/opt/homebrew/opt/python@3.13/libexec/bin:/opt/homebrew/bin:/usr/bin:/bin python3 -m unittest discover -s tests -p 'test_public_replay.py' -v
```

[Replay output](../evidence/runs/submission-ready/replay.log):

```text
Ran 3 tests in 0.167s

OK
```

These tests block outgoing socket connections, preserve both tape hashes and the 60-second rule, assert that the faulty replay fails and the timely healthy replay passes, and assert that the original late healthy recording still fails. Actual CLI results and the independently downloaded ZIP are in [runtime-result.json](../evidence/runs/submission-ready/runtime-result.json):

| Input | Merchant | Observed verdict | Exit |
| --- | --- | --- | --- |
| Curated early read | Faulty | FAIL / paid_without_ticket | 1 (expected) |
| Same curated input | Healthy | PASS / ticket_delivered_once_on_time | 0 |
| Original late read | Healthy | FAIL / ticket_delivered_late | 1 (expected) |

No timing or validator change was made during this verification.

## Build and startup

```sh
npm ci --ignore-scripts --prefix studio
npm run build --prefix studio
npm run test:deadlines --prefix studio
python3 -m compileall -q crashcart scripts tests
node --check web/app.js
node --check web/marketing.js
node --check web/judge/app.js
python3 scripts/verify_foundation.py
python3 -m crashcart prerequisites
env PYTHON=/opt/homebrew/opt/python@3.13/libexec/bin/python3 sh scripts/judge.sh --no-open --port 8911
```

Fresh dependency installation: 31 packages, zero reported vulnerabilities. [Typecheck/build](../evidence/runs/submission-ready/build-retry.log) passed. [Timing projection tests](../evidence/runs/submission-ready/deadlines.log): 45 pass, zero fail. This run used Node **26.12.0**, not the pinned CI version 22.14.0; it establishes this local environment only. Python was **3.13.15**, SQLite **3.54.1**. Keyless mode itself does not need Node or npm.

[Foundation output](../evidence/runs/submission-ready/foundation.log) confirms fresh migrations, an actual local server, health response, fixture and served document. [Prerequisite output](../evidence/runs/submission-ready/prerequisites.log) confirms provider/model/Studio credentials were absent. This does not establish a licensed Studio session or a provider call.

The app served HTTP200; results said `computed_when: app launch`, `RECORDED_REPLAY`, zero service calls and no fresh execution. The downloaded ZIP ran successfully in a separate temporary directory with the expected two outcomes. The [verification script](../evidence/runs/submission-ready/verify_runtime.py) records the exact operations; it was run from the fresh clone, with its results directory one level above.

## Actual browser and hosted checks

In the clean-clone app, the browser rendered the finished investigation. Selecting the repaired replay updated the ticket count to one, delivery to 32.26 seconds and the download URL to the healthy record. Filtering PayPal showed four of 15 observations; expanding the independent payment read exposed its record. [Browser state](../evidence/runs/submission-ready/browser-keyless.txt) and [screenshot](../evidence/runs/submission-ready/judge-browser.png) preserve the result. Earlier responsive/keyboard/reduced-motion checks remain described in [JUDGE_VERIFICATION.md](JUDGE_VERIFICATION.md); no UI source changed here.

The existing [GitHub Pages demo](https://himanshu748.github.io/crashcart/) returned both expected outcomes via HTTPS. [Fresh readback](../evidence/runs/submission-ready/hosted-readback.json) labels computation at **site build**. It is not an AWS deployment or hosted AI service.

## Documentary gates

- The [README Sandbox section](../README.md#optional-sandbox-test-buyer-path) identifies Business merchant/app and Personal buyer accounts, local environment variable names, test-only buyer approval and private placeholders. No usable credentials are committed.
- GitHub reports a public repository and MIT SPDX identifier: [metadata](../evidence/runs/submission-ready/github-metadata.json). The actual rendered **About → Resources → MIT license** link was inspected: [browser readback](../evidence/runs/submission-ready/github-license.txt). Root [LICENSE](../LICENSE) contains MIT text.
- [SUBMISSION.md](SUBMISSION.md) exists and is checked against the observed product. [AI_EVIDENCE.md](AI_EVIDENCE.md) explains the real historical PayPal-plus-model investigation; keyless replay performs neither new inference nor payment.
- The public video and owner submission remain undone. See [submission gates](SUBMISSION_GATES.md).

## Preserved failed attempt

The first dependency extraction exhausted local disk space (`ENOSPC`). The simultaneous first full-suite attempt consequently errored and exited120; the first app launch could not create a temporary directory. Only this attempt's incomplete `node_modules` directory was removed. The second suite, dependency installation, build and app launch passed after space became available. Private raw failed logs remain under `var/submission-v61/results/`; their failure summary is retained publicly. No source, expected result or deadline was changed to address the environmental failure.
