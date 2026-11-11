# Recorded walkthrough hosting

**Primary demo:** <https://crashcart.32.193.44.79.sslip.io/>

**GitHub Pages mirror:** <https://himanshu748.github.io/crashcart/>

Both public sites serve the recorded judge experience. They hold no PayPal or
model credentials, start no checkout and make no AI requests. The current
published video is the [2:45 Deepgram-narrated walkthrough](https://www.youtube.com/watch?v=3MIzDpFmRl0).

The static site computes both repair outcomes during export. A visitor inspects
those saved results; clicking or refreshing does not run Python. To recompute
them locally with no keys or packages, run `./scripts/judge.sh` as documented in
[the README](../README.md#try-it-in-60-seconds).

The hosted page opens the 8 November saved AI investigation. The local command
opens the separate 22 October comparison: faulty with no ticket, repaired with
one ticket at 32.26 seconds. Both cases are available in the same workspace.

## Operation and publication

The dedicated Lightsail instance, static IP and certificate storage must remain
available through **22 December 2026**. No automatic teardown is configured.
The owner approved the existing $12/month base plan; this document authorizes
no spending or billing change. See [health, restart and host configuration](OPERATIONS.md).

Pages publication is manual and separate from merging. Dedicated-host publication
uses the same reviewed static artifact, with a retained previous release and
configuration backup. See [deployment and rollback](LANDING_HOST_PLAN.md).
A successful check establishes availability at that time, not future uptime.

The keyless Bryntum timing page being prepared on the cleanup branch is **local
only** until its own release is approved. No AG Studio bundle is publicly served.

## Previous shared host

[The November shared-host deployment](LIGHTSAIL_SHARED_HOST.md) is historical.
Its URL is no longer the advertised demo. Preserve its receipts and unrelated
applications; do not stop its instance or restart its shared proxy as part of
this cleanup. Earlier AWS and browser failures remain dated historical records.
