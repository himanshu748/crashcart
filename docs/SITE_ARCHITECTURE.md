# CrashCart site structure

The owner chose a multi-page site on 9 November 2026. AGENTS.md contains no single-page requirement.

| Page | Purpose | Primary action |
| --- | --- | --- |
| Home | Explain the paid-but-not-delivered problem and who CrashCart helps. | Open the recorded example. |
| Product | Explain payment, delivery and the promise through an interactive illustration. | Inspect the working example. |
| Integrations | Show the existing tools' actual data flow and setup boundaries. | Explore the example or configure the existing workspace locally. |
| Recorded Example | Follow the saved payment, compare the missed and recovered order, inspect and download records. | Inspect or run the saved replay. |
| Workspace | Start and manage real owned test checkouts and background investigations with private configuration. | Open a case; approve and confirm payment explicitly. |

Public pages live in `web/judge/`; the source directory name is internal. Exported URLs are `index.html`, `product.html`, `integrations.html` and `demo.html`. Relative links must work under `/crashcart/` as well as at a domain root. The connected server's `/recorded/` namespace serves only the fixed public replay bundle, never the merchant's private database. POST is rejected; private API authentication stays in force.

The four-page candidate has 87 passing focused frontend tests, 16 passing judge/replay tests and actual HTTP coverage of the fixed public namespace. Browser checks exercised real page navigation, the illustration’s inclusive deadline, integration filters, saved case switching, PayPal filtering, keyboard navigation, 390/320-pixel layouts and the shared motion preference. These are local candidate checks, not a deployed update or new original CC acceptance. On continuation, a fresh frozen-source run passed 560 Python tests. Actual workspace navigation and its390px layout passed through the production Handler with synthetic data, and the current image passed35 Linux tests with networking disabled and all43 runtime hashes matching. Earlier full-suite failures remain recorded and unexplained; no deadline changed. The hosted update and original final release gate remain open.
