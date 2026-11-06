# Overload notice: exact local verification

This is a local verification procedure for the existing monitoring UI. It does not exercise a real shop, PayPal payment or public endpoint. The application source and its default limits are unchanged.

- [x] **OV-001 — Exact overload visibility and recovery:** one isolated fixture confirms the default 16-handler limit and real retryable HTTP 503 before and after desktop/phone captures. The actual busy notice is frontmost and entirely within each viewport; the order remains loaded with one alert. Releasing the clients restores HTTP 200, clears the browser notice and preserves business facts. Cleanup leaves no active handlers, clients or worker. An independent reviewer inspects source-bound screenshots, measurements and results.

## Why the setup changed

The earlier short request window could finish before the browser capture. A replacement helper could overlap with the server helper's clients, mistook connected sockets for admitted handlers, and aborted on the first connection reset. Both failed attempts remain recorded in [the historical result](../evidence/runs/submission-ready/monitor-v2/browser-visible/pressure-followup-failures.json).

The replacement fixture owns its server and clients together. It waits for actual handler counters plus an independent HTTP 503, retries refused connections within a bounded budget, and renews client leases one at a time. It never replaces the application's response or edits the page to manufacture an error.

## Run the fixture

Use Python 3.13.15 from the repository root:

```sh
python3 -m tests.overload_fixture --output var/overload-proof-new-run
```

The output directory must not already exist. The fixture prints its loopback URL. Open it and sign in with the explicitly test-only `LOCAL_TOKEN` from the fixture source. This server contains synthetic example data and receives no provider credentials.

Create a `start` file in that output directory after the page has loaded. Wait for `ready.json`: both handler observations must equal 16 and the independent probe must return HTTP 503 with `Retry-After: 1`. Then refresh the browser and inspect the actual busy message.

Create `desktop-before` and `desktop-after` marker files around the desktop capture, and `phone-before` and `phone-after` around the phone capture. Each generates a fresh counter/503 receipt. Save actual screenshots, DOM observations and read-only visibility measurements. The completed run uses 1280 × 720 and 390 × 844 viewports.

Create `release` and wait for `released.json`: zero active handlers, HTTP 200 and unchanged facts. Refresh the page and inspect recovery. Create `stop` to close the owned server and inspect `cleanup.json`.

Pressure lasts at most 180 seconds, with at most 16 owned pressure-client slots and ten connection attempts per second. Short-lived readiness probes and browser requests additionally exercise rejection. The overall fixture session is capped at 300 seconds. The production ten-second socket watchdog remains active; leases are renewed without changing it. No external target URL is accepted.

## Proof boundaries

The before/after receipts are independent HTTP probes, not captured browser-network responses. They establish saturation at those observations, not uninterrupted saturation between them. The order must remain in the page; it need not fit within every screenshot alongside the notice.

Browser Resource Timing was unavailable through the read-only inspection surface. That optional inspection error is recorded; no browser-network trace is claimed. Real-store delivery, deployed HTTPS, physical-phone behaviour and production load resistance remain outside this check.

## Result

**Verified locally after independent review.** The receiver reached 16 handlers and returned HTTP 503 at each capture boundary. The notice was legible, frontmost and entirely within the 1280 × 720 desktop and 390 × 844 phone viewports. Pressure recycled 224 leases over 89.043 seconds. Release returned HTTP 200 with zero active handlers and unchanged facts. Browser recovery cleared the notice and retained one order and one alert. Cleanup left zero clients, workers and provider calls.

[Source-bound screenshots, measurements, recovery, commands and independent review](../evidence/runs/submission-ready/overload-v3.json). Full suite: **459 tests in 113.127s, OK**. Replay: **3 tests in 0.357s, OK**. The earlier failures remain unchanged; this is a fresh pass.
