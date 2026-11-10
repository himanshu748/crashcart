# CrashCart — 2:45 product walkthrough

This is the edit used for the submission video. It shows the current app displaying the completed **8 November PayPal Sandbox + AI investigation**, followed by a **separate healthy recorded replay**. It does not show a new payment, a new AI call or original buyer-approval footage. The existing case has no original checkout recording; do not describe this screen capture as one.

The video retains its existing spoken narration and burned-in captions. The 10 November edit replaces only 2:10–2:20 with an actual browser recording of the delivery-timing view; its original caption and separate-replay label remain visible. No new narration was generated for the insert.

| Time | Screen and action | Burned-in narration |
| --- | --- | --- |
| 0:00–0:10 | Actual landing page, headline and checkout illustration. | “I paid, but my ticket never arrived.” |
| 0:10–0:20 | Landing product story. | A successful payment can still become a broken promise. CrashCart helps support and engineering find the missing step. |
| 0:20–0:35 | Open the saved 8 November case. Show its $29/one-ticket/60-second promise and result. | This real Sandbox checkout ran on 8 November. We are opening its saved results; no new payment or AI call is happening. |
| 0:35–0:50 | Show payment and ticket witnesses. Filter Activity to PayPal. | The test store lost the payment reply. PayPal confirms the charge. The store still has no ticket. |
| 0:50–1:05 | Show the Assistant section and its actual finding. Filter Activity to Assistant. | DeepSeek investigated this same order. It chose to read PayPal, then the ticket records. |
| 1:05–1:25 | Open the actual saved assistant steps. Each explains which record it asked to check. Keep technical details closed. | First, check PayPal: did the payment complete? Then check the store: did this customer get a ticket? The assistant connects those facts; a fixed check decides whether the promise was kept. |
| 1:25–1:40 | Return to the fixed-rule verdict and payment/ticket summary. | The customer paid, but the ticket missed its one-minute promise. This order needs attention. |
| 1:40–1:55 | Open the account-free recorded example. Select Recovered order (replay). | For the repair, we switch to a different recorded checkout. Its faulty and healthy versions use the same payment and one-minute promise. |
| 1:55–2:10 | Show one ticket at 32.26 seconds. Open the delivery records. | The recovered order creates one ticket in 32.26 seconds. One payment. One ticket. Delivered before the promised minute. |
| 2:10–2:20 | Show the existing Bryntum delivery-timing chart with both canonical recorded cases. Briefly filter to the healthy case, then return to both. The ticket marker is at 32.261423 seconds, inside the same 60-second window. | The missing-ticket case needs attention. The recovered order keeps the same one-minute promise. |
| 2:20–2:35 | Show the replay download and return to the landing page. | Small sellers need an answer they can share, not another successful-payment screen. Take the case and its runnable comparison with you. |
| 2:35–2:45 | End on the product with repository address and invitation to open the recorded walkthrough. | Try the recorded walkthrough with no account. For a new test purchase, connect your own PayPal Sandbox and AI account. Follow the payment. Check the promise. |

## Recording boundaries

- The ten-second timing insert uses Bryntum Scheduler Community 8.0.0-beta.1, distributed under MIT. Playwright records the actual view over locally executed faulty and healthy versions of the unchanged public recorded input. No payment, AI request, credentials or store connection is involved.
- Playwright captures the running app. The completed case is read from a private SQLite backup; all new payment/model actions are disabled. Sign-in happens before recording and no key appears in the video.
- The 8 November case, its saved AI investigation and the separate healthy public replay retain their real outcomes. Captions explain the investigation in customer language; raw record IDs and tool names stay in the repository. No progress animation is staged and no failed outcome is changed into a pass.
- Public demo: <https://crashcart.52.202.25.181.sslip.io/>. Source: <https://github.com/himanshu748/crashcart>. The local capture uses the same app source, not a live provider connection.
- Runtime, file size and actual frame inspection are in [VIDEO_CHECK.md](VIDEO_CHECK.md). The final MP4 is [public on YouTube](https://www.youtube.com/watch?v=gFWje84_wEA). The Devpost form is prepared separately and must not be submitted before the owner's new approval.
