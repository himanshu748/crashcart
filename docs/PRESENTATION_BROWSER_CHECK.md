# Document-navigation compatibility check

11 November 2026 · local presentation branch, not a deployed-site claim.

Ordinary Chrome reproduced the review's `InvalidStateError` messages; these were
not confined to the in-app browser. The frozen `f0c3324` site emitted 11 errors
with normal motion and 12 with reduced motion during the tested route sequence.
The pages remained readable, but the native document-transition opt-in was noisy.

A controlled comparison served that same source while removing only
`@view-transition { navigation: auto; }` from its CSS response. Both Chrome profiles
then emitted zero errors. The source repair removes that opt-in and its unused
snapshot animation rules. Navigation uses the browser's normal document load;
existing in-page GSAP entrances, scroll story, comparison motion and reduced-motion
fallbacks remain intact.

| Browser | Frozen source: normal / reduced errors | Repaired final source: normal / reduced errors |
| --- | --- | --- |
| Installed Google Chrome 157.0.8103.39 | 11 / 12 | 0 / 0 |
| Firefox 159.0, official Playwright Gecko build 1572 | 0 / 0 | 0 / 0 |

The Firefox download is a real Gecko browser, not Chromium emulation; this result
is not a claim about a separately installed stable Firefox application. No WebKit
emulation is being reported as Safari. Actual Safari results are recorded by the
main presentation review.

Native Safari 27.0.1 was also exercised in an actual Private Browsing window.
The final local saved-payment card rendered with USD 29.00, COMPLETED, public
Sandbox IDs, both routes and the no-new-call label. Navigation to Integrations
and the actual timing SDK view loaded. Safari's JavaScript Console on the timing
page showed no messages. This is a focused manual check, not an automated
equivalent of Chrome/Gecko's rapid-navigation and motion matrix.

The existing public hosted landing also loaded signed out in that private
window. The current YouTube watch URL played signed out with a visible Sign in
link and 2:45 duration. Screenshots are `safari-private-public-home.jpg`,
`safari-private-youtube.jpg`, `safari-private-timing-console.jpg` and the saved
console accessibility text under the private browser-artifact folder. The host
still serves the prior public build; the local fixes have not been deployed.

Final checks used the freshly restarted local judge site on port 8960: Home →
Product → Demo workspace → Integrations → Delivery timing, followed by four quick
Home → Product → Integrations cycles. Each of the four browser/motion profiles
kept nonblank headings and the expected navigation destination, with zero console
warnings/errors and zero uncaught page errors. Chrome cancelled favicon requests
when navigation was deliberately interrupted (`net::ERR_ABORTED`); documents and
content loaded. Firefox recorded no failed requests.

Separate interaction checks passed in all four profiles: the normal landing story
and user-triggered replay still animate; reduced motion leaves the story readable,
hides the replay control and displays its final 60-second clock; the healthy case
still displays one ticket at 32.26 seconds. `node --test tests/test_judge_motion.cjs`
passed all six tests, without test changes.

Private reproduction artifacts are under
`var/judge-presentation-nov11/qa/browsers/`: `check-browsers.mjs`, `baseline.json`,
`baseline-firefox.json`, `isolated-no-native.json`, `final-frozen.json`,
`motion-preservation.json` and browser screenshots. An initial chart-readiness
assertion targeted Bryntum's intentionally zero-width milestone wrapper; the
corrected check waits for the painted `.delivery-ticket` child and settled wrapper
opacity. The original attempt is preserved. Chart visual/mobile validation is a
separate presentation check; DOM readiness alone is not visual proof.
