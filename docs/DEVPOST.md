# CrashCart

## Tagline

Find the missing step between a PayPal payment and delivery.

## Inspiration

“Payment complete” should mean a customer is about to receive what they bought. Sometimes it means a merchant has a support problem they cannot yet explain. The payment record, checkout page and delivery system each tell only part of the story. CrashCart brings them together around the customer's promise.

## What it does

CrashCart helps small merchants investigate “I paid, but nothing arrived.” The prototype follows a $29 workshop purchase with a clear promise: one ticket within 60 seconds of payment.

Open the account-free recorded walkthrough, inspect the missing ticket, filter the timeline by source and compare the recovered order. The healthy 32.26-second repair uses a separate saved checkout input, not a new purchase. Its faulty and healthy variants use the same payment input and deadline. The healthy variant applies a repaired fulfil-on-confirmed-reconciliation rule to saved input; it does not re-run the merchant service. Download the replay to run both outcomes locally.

The completed 8 November 2026 run used real PayPal Sandbox Orders v2 create, capture and get, followed by real DeepSeek calls through Modal on that same order. DeepSeek checked PayPal, checked ticket records and cited the missing delivery. The recorded failure investigation shows its three saved steps and citations before the earlier successful case. Showing that saved result starts no new payment or model call. The public walkthrough is recorded; it is not a live merchant connection.

## How we built it

Python, SQLite and a background worker keep payment requests, purchases, observations and tickets connected. Through PayPal’s Sandbox APIs, the server creates and captures orders, checks payments independently and verifies payment notifications.

DeepSeek-V4.1-Flash, served through Modal, chooses which payment and ticket records to read and explains its findings. Fixed rules decide whether payment and delivery meet the promise.

Bryntum Community Scheduler compares saved ticket times with the delivery window; the video shows this actual view at 2:10–2:20. It is separate from the public website's simpler timeline. KERNEL supported remote checkout experiments; Postman/Newman provide executable API checks.

## Challenges

A lost reply made a successful purchase look unfinished. We had to connect the payment and store records without trusting a checkout-page message or issuing duplicates. The repair still had to keep the customer’s original one-minute promise.

## Accomplishments

One customer complaint becomes a readable payment-to-delivery story and a test anyone can rerun without credentials. A real Sandbox test also recovered after checkout stopped following capture, delivering exactly one ticket in about four seconds. The separate 8 November run connected real payment evidence with AI-selected investigation steps.

## What we learned

A successful payment and a delivered order are different facts. AI helps decide where to look next; it should not invent the answer when records are missing.

## What's next

Validate Shopify and WooCommerce connections with owned stores, broaden delivery promises and test the workflow with merchant support teams. General merchant onboarding and production payments remain future work.

## Built with

Python, SQLite, JavaScript, TypeScript, PayPal Sandbox REST (Orders v2, webhook verification), Modal, DeepSeek, Postman, Newman, Bryntum Community Scheduler.

## Try-it links

- Recorded walkthrough: https://crashcart.52.202.25.181.sslip.io/
- GitHub Pages recorded-demo mirror: https://himanshu748.github.io/crashcart/
- Source and local setup: https://github.com/himanshu748/crashcart
- Completed payment-and-AI run: https://github.com/himanshu748/crashcart/blob/main/docs/LIVE_FLOW.md
- Video: https://www.youtube.com/watch?v=gFWje84_wEA
