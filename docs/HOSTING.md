# Recorded walkthrough hosting

**Current demo:** https://crashcart.52.202.25.181.sslip.io/

Verified 8 November 2026 on the existing Lightsail host. Its existing Docker/Caddy
proxy serves the frozen public export; no additional instance or plan upgrade was
needed. The server holds no CrashCart provider credentials or licensed workspace
bundle. [Configuration, cost, retention and rollback](LIGHTSAIL_SHARED_HOST.md).
[Actual deployment and browser evidence](../evidence/runs/submission-ready/lightsail-hosted-nov8.json).

The hosted page is an interactive recorded example. Results are computed during
export, not on each click. The local `./scripts/judge.sh` command executes both
merchant variants at startup. Neither mode creates a payment or calls AI. The
historical AI section is a separate dated case. Full live merchant/model access
remains outside this hosted deployment.

Trusted HTTPS, the defective failure and healthy pass, both desktop and phone
interactions, HTTP write rejection and the actual downloaded executable ZIP were
exercised. All ten exported files match their frozen hashes. The six earlier
sites retain their routes, HTTP statuses and successful-page hashes. The shared
proxy container/image/start time/mounts and original routing table are unchanged.

Keep access through the 21 December winner announcement, with a 22 December UTC
buffer. The instance has an additive CrashCart retention tag. No automatic
teardown is installed and future uptime is not established by these tests.
Freeze submitted source, video and linked materials after the deadline until
winners are announced. Do not stop/delete this shared host to remove CrashCart.

## Fallback and retained failures

The [GitHub Pages preview](https://himanshu748.github.io/crashcart/) remains
available on an older release. Its current workflow is blocked by an account
billing lock. No Pages settings, unrelated project or existing public site was
removed or replaced. Complete local setup is also an accepted judging path.

The earlier dedicated $7/month Lightsail attempt stopped before SSH and was
cleaned up; [that failure remains recorded](../evidence/runs/submission-ready/aws-attempt-nov8.json).
The current deployment reuses an existing $12/month host, adding no instance base
fee. Existing transfer/tax/account charges still apply. Account-wide $20/$50
budget alerts are configured, not hard caps. Email delivery is untested.

The [dedicated-host plan](AWS_JUDGE_DEPLOY.md) is an alternative, not the deployed
architecture. Render remains excluded. No new PayPal, model or KERNEL execution,
Devpost edit or submission was performed as part of hosting.
