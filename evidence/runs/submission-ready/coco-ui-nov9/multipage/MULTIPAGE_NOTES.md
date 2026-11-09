# Multi-page notes

Nothing here was executed. Every statement comes from reading or writing source, or
from viewing `landing-final-desktop.jpg`. The other two JPEGs weren't reopened in this
pass. Root still has to wire the export and server routes and run the checks.

## Routes

The public pages sit next to each other in `web/judge/` and link to each other with
bare relative filenames, so they work at whatever URL prefix root mounts them on
(`/recorded/…` on the server, a GitHub project subpath on export).

| Page | File | Purpose | Primary action |
| --- | --- | --- | --- |
| Home | `web/judge/index.html` | The problem in one screen, who decides, where to go next | "Follow a recorded case" → `demo.html` |
| Product | `web/judge/product.html` | How a check works, with an interactive 60-second-rule illustration, plus the four workspace steps | "See it on saved records" → `demo.html` |
| Integrations | `web/judge/integrations.html` | Seven stack pieces: what each does, where it runs, where it stops, and what we don't claim | "See what the public example shows" → `demo.html` |
| Recorded example | `web/judge/demo.html` | The accepted recorded investigation, with its `app.js` and `data.json` | "Walk through the recorded case" → `#investigation` |
| Workspace | `web/index.html` (unchanged here) | Separate authenticated dashboard. Its nav already links `recorded/product.html`, `recorded/integrations.html`, `recorded/demo.html` | n/a |

For root to decide: if `/recorded/` should also serve Home, map `recorded/` (or
`recorded/index.html`) to `web/judge/index.html`. The workspace nav has no link to it
today: its Home link is the workspace's own `/?view=home`.

Back links: Product and Integrations have a breadcrumb to Home, plus previous/next
(Home ← Product → Integrations → Recorded example → Home). The demo has a breadcrumb
plus "← Integrations" and "Back to Home".

## Interactions

- **All pages:** the header nav is plain links with `aria-current="page"` on the current
  page, and the same four links repeat in the footer. There's a skip link, and `main`
  is focusable. Nothing needs JS to navigate.
- **Reduce motion (Home, Product, Integrations):** `site.js` respects the OS setting and
  the `#reduce-motion` checkbox, and remembers the checkbox in `localStorage` key
  `crashcart-reduce-motion` (falling back silently if storage is blocked). The demo
  keeps its own `app.js` motion handling and doesn't read that key, so a choice made on
  Home doesn't carry into the demo.
- **Home motion:** the four ledger rows rise in once on load, with no loop. The
  existing reduced-motion rules switch this off.
- **Product `#sim`:** scenario pills (Misses the reply, Checks PayPal itself, Delivers
  late, Delivers twice) use `aria-pressed`. There's a 0 to 90s range slider (arrow keys
  and Home/End are native), an `<output>` clock and Play/Pause. The verdict is
  announced through a polite live region only when it changes. The times are
  illustrative and labelled as such. The rule (one ticket within 60s of payment)
  matches `app.js`.
- **Integrations filter:** All / In the public example / In a configured workspace /
  Preview, as `aria-pressed` pills, with a `role="status"` count. It hides cards with
  `hidden`. Without JS, every card shows and the filter row stays hidden.
- **Demo:** all controller behaviour is unchanged (story steps, case switch, source
  filter, saved AI steps, downloads). The new trail link `#investigation` is rewritten
  to `#load-state` by `app.js` if the records fail to load, the same as the hero CTA.

## Changed files

- `web/judge/index.html`: rewritten as Home (no `app.js`).
- `web/judge/product.html`, `web/judge/integrations.html`: new.
- `web/judge/demo.html`: brand became a link; nav is now the four pages; added the
  breadcrumb/on-this-page trail; new eyebrow, `h1` text and lead (`#product-title`
  kept); secondary CTA `#how` → `product.html`; one link in the `#how` lead; added
  `id="downloads"`; added page-end nav and footer links. No controller id, class,
  `data-*` hook or relative asset path was removed or renamed.
- `web/judge/style.css`: additive block for the nav current state, trail, page
  heroes, bands, link cards, split cards, sim, integration cards, limits list, page end
  and the Home load animation, plus 860px and 520px rules. Existing rules are unchanged.
- `web/judge/site.js`: new. Motion preference, Product sim and Integrations filter.
  Each part is guarded so it only runs where its markup exists. No network request.
- `MULTIPAGE_REVIEW.md`, `MULTIPAGE_NOTES.md`: rewritten for this pass.
- Not touched: `web/judge/app.js`, `web/app.js`, `web/index.html`, `web/style.css`,
  `web/marketing.js`, `data.json`, `downloads/`.

## Unverified limits

- Not rendered at 320, 390 or laptop widths, and not checked under a real GitHub
  project subpath. Layout claims come from reading the CSS.
- The 73 frontend tests, the 15 judge checks and the 551 full suite were not run. Text
  that changed on the demo (the `h1`, the eyebrow, the nav `aria-label` "On this page"
  becoming "Main", the `#how` CTA) could break text- or selector-based checks written
  for the old single page.
- The old `web/judge/index.html` was the full recorded page, and it now is Home
  without `app.js`. Any check that loads `index.html` and expects the recorded case
  must point at `demo.html` instead.
- The public pages deliberately have no Workspace link (see the review). Root may add
  one if the served layout makes a relative link safe.
- No keyboard or screen-reader pass was done in a browser. Focus order and live-region
  behaviour are reasoned from markup.
- No payment, PayPal, Modal/DeepSeek, AG Studio, Bryntum, KERNEL, Postman, store,
  deploy or billing action took place. The integration copy states capabilities from
  the brief only. Nothing claims fresh execution, health or verification.
