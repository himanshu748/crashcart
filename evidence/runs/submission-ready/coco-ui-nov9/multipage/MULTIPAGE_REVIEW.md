# Multi-page review

**Source review only.** I read and wrote files. Nothing was executed: no browser,
render, test, server, export, shell, SQL, provider call or deploy. Every "works"
below means "reads correctly in the source", not "observed running".

## Outcome

The four public pages and their shared assets are written. The workspace nav change
from the previous pass is kept as it was.

| File | State |
| --- | --- |
| `web/judge/index.html` | Rewritten as Home (was a copy of the old single page) |
| `web/judge/product.html` | New (was empty) |
| `web/judge/integrations.html` | New (was empty) |
| `web/judge/demo.html` | Edited in place: header, breadcrumb trail, hero copy, two links, one id, page end, footer |
| `web/judge/style.css` | Additive block before the reduced-motion rules. No existing rule edited |
| `web/judge/site.js` | New (was empty) |
| `web/judge/app.js`, `web/app.js` | Not edited |
| `web/index.html`, `web/style.css`, `web/marketing.js` | Not edited in this pass |

## Demo: controller hooks checked against `web/judge/app.js`

I read all 300 lines of `web/judge/app.js` and checked each hook it uses against the
edited `demo.html`.

- Still there and unchanged: every `byId` target (`reduce-motion`, `selected-name`,
  `download-case`, `facts`, `technical-result`, `source-filter`, `timeline-count`,
  `timeline`, `story-copy`, `story-counter`, `story-status`, `story-title`,
  `story-description`, `ai-*`, `evidence`, `evidence-title`, `review`, `load-state`,
  `execution-note`, `defective-count`, `healthy-count`, `healthy-time`,
  `defective-finding`), `.promise`, `.compare-card`, `.case-switch [data-case]`,
  `.select-case`, `.order-records`, `button[data-story]`, `[data-ai-step]`.
- `[data-case]` is queried page-wide. No new element on any page uses `data-case`,
  `data-story` or `data-ai-step`.
- `fail()` rewrites every `a[href="#investigation"]` to `#load-state`. The hero CTA
  keeps `href="#investigation"`, and the new trail link uses the same href, so both
  get redirected on a failed load. That's intended.
- `app.js` never touches the nav, so the header change can't affect it.
- `data.json`, `downloads/*.json`, `downloads/replay.zip` and `LICENSE` stay relative.
  `style.css` and `app.js` are still loaded relatively, and `site.js` isn't loaded on
  the demo.
- Ids kept: `how`, `faq`, `faq-*`, `investigation`, `product-title`. Id added:
  `downloads`, on the downloads section.
- Text changes a check might match on: the demo `h1` now reads "One paid order. Follow
  it to the missing ticket." (it used to be the Home headline), the eyebrow reads
  "Recorded example · one PayPal test checkout", the secondary CTA points at
  `product.html` instead of `#how`, and the header nav has `aria-label="Main"` instead
  of "On this page". The in-page anchors moved into the trail. If any of the 15 judge
  checks matches the old headline or the old nav label, it will need updating.

## Navigation

- Every page has the same `nav.bar-nav[aria-label="Main"]` with four relative links
  (`index.html`, `product.html`, `integrations.html`, `demo.html`). The current page
  has `aria-current="page"` and is styled as a filled pill. The brand is a link to
  `index.html`.
- Product, Integrations and the demo have a breadcrumb (`← Home`) and an "On this page"
  list. Those three also end with a previous/next `nav.page-end`. Every footer repeats
  the four links.
- There are no root-absolute (`/…`) URLs on the public pages, so they should resolve
  under a GitHub project subpath. I haven't checked this in a browser.
- On purpose, the public pages have no Workspace link. On a GitHub Pages export,
  `../` would leave the project. The workspace is described in the footer instead.

## Product illustration (`#sim`, driven by `site.js`)

- Four store behaviours (pills with `aria-pressed`), a native range input (0 to 90s,
  `aria-valuetext`), an `<output>` clock and a Play/Pause button. The rule is the real
  one: exactly one ticket within 60s. The times are made up, and both the tag and the
  foot note say so.
- The verdict region is `aria-live="polite"`, and its text only changes when the
  scenario or state changes, so dragging the slider doesn't flood screen readers.
- Without JS, the controls stay `hidden`. The static markup and the CSS defaults show
  the end state of the first scenario (90s, no ticket, broken).
- Motion: Play uses `requestAnimationFrame` (6s for 90 illustrated seconds). With
  reduced motion it jumps to the end. Turning the toggle on mid-play stops playback.
- Known rough edge: with reduced motion on and the slider already at 90s, pressing
  Play shows no visible change.
- The "where to look next" hint is labelled as example wording written by us, not
  model output.

## Integrations

- There are seven cards, matching the brief's stack facts. Each says what the piece
  does, where it runs and where it stops. Filter pills set `hidden` on cards, and
  `#int-count` (`role="status"`) reports how many are shown. Without JS, the filter
  row stays hidden and every card shows.
- Copy I tightened while reviewing: KERNEL now says only "remote test checkout and
  records it". Postman says only "API responses and the records it exports". The
  Postman note no longer says the downloads are all JSON, since one is a ZIP.
- Modal is described as the host, never as a sponsor. Shopify/WooCommerce are marked
  Preview and "never connected to a real store". There are no testimonials, pricing,
  customer counts or sign-up flows on any page.

## Layout (source reasoning, not visual check)

- At 860px and below: cards, splits, sim records and limits go to one column, and the
  header nav takes its own scrolling row (an existing rule).
- At 520px and below: `int-dl` stacks, Play and page-end buttons go full width, and the
  sim track keeps 34px side margins so the `Paid` and `No ticket` labels at the ends
  shouldn't overflow at 320px.
- I fixed one specificity bug in review: `.sim-verdict p` would have overridden the
  amber verdict title in the waiting and on-track states. It's now
  `p:not(.sim-verdict-title)`.

## Carried over from the previous pass (not re-verified)

- `web/index.html` lines 27 to 35: Home / Product / Integrations / Example / Workspace,
  with the page links pointing at `recorded/*.html`. I re-read the lines and they
  match. There's still no `data-home` attribute in the lines I read (1 to 90). I didn't
  read the rest of the file.
- `web/style.css` nav additions: not re-read in this pass.
