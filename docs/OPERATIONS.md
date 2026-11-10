# Keep the recorded demo online

Primary demo: <https://crashcart.32.193.44.79.sslip.io/>. Keep this instance,
its attached static IP and certificate storage running through **22 December 2026**.
There is no scheduled teardown. The owner approved this independent **$12/month
base Lightsail plan** on 10 November; taxes and transfer overages are separate.

## Health

```sh
curl --fail --silent --show-error https://crashcart.32.193.44.79.sslip.io/healthz
```

Expected: HTTP 200, `"status": "recorded-demo"`, `"scope": "static-asset-serving"`
and `"live_services_checked": false`. This checks static serving, not PayPal or AI.
`/product`, `/example` and `/integrations` serve directly, without HTML redirects.

## Dedicated host

- Lightsail instance: `crashcart-demo-nov10`, `us-east-1a`, Ubuntu 24.04,
  `small_3_0` (2GB RAM, 2vCPU, 60GB disk).
- Attached static IP: `crashcart-demo-nov10-ip`, `32.193.44.79`.
- Container: `crashcart-demo`, Docker restart policy `unless-stopped`.
- Initial deployed source: `fc3e2432699e4ecd5ac62019883769aca00ce5ec`.
- Exactly 17 public files at `/opt/crashcart/site`, mounted read-only at `/srv`.
- [Applied Caddy configuration](../deploy/judge/Caddyfile.dedicated-static):
  `/opt/crashcart/Caddyfile`; TLS state at `/opt/crashcart/caddy-data` and
  `/opt/crashcart/caddy-config`. Only HTTP/HTTPS is public; SSH is operator-IP-only.
- Caddy image: `caddy:2.11.9-alpine@sha256:0bbb055bda6793c999bde78b1b5ce3e89f829fb031af2cf50056ea1246559fee`.

No CrashCart worker, provider keys, AG Studio licence or model service runs here.
The site replays saved records. The optional licensed explorer is **not deployed**.
The hostname uses public `sslip.io` DNS; local replay is the fallback if DNS fails.

## Inspect and restart

Use your private SSH identity and saved host fingerprint; never disable host-key
checking. First connection used explicit first-use trust against the AWS-assigned
IP; it was not an independently authenticated fingerprint. Subsequent connections
remain strictly pinned. Refresh an expired temporary SSH certificate through AWS;
do not reset a changed host key automatically.

On this dedicated host:

```sh
sudo docker inspect crashcart-demo --format '{{.State.Status}} {{.HostConfig.RestartPolicy.Name}}'
sudo docker logs --tail 50 crashcart-demo
sudo docker start crashcart-demo     # only if stopped
# If it is running but unresponsive, restart this dedicated container:
sudo docker restart crashcart-demo
```

Rerun the public health check after any restart. Preserve certificate directories
and the existing site. A future release needs a separate reviewed update and
post-deploy link/replay checks; the private initial installer deliberately refuses
an existing deployment. Do not prune/delete resources or replace the site with a
live worker.

The initial Lightsail user-data wrapper ran the Bash script under `sh` and failed.
Setup succeeded through an explicit `sudo bash -s` SSH invocation after the owner
approved resuming. This does not require rebuilding the instance.

## Other public copies

The [previous shared host](LIGHTSAIL_SHARED_HOST.md) remains intact; its firewall,
applications and proxy were not changed for this release. Do not restart its
shared proxy to repair the new dedicated demo.

The [Pages mirror](https://himanshu748.github.io/crashcart/) publishes through the
**Recorded walkthrough** workflow after successful **Source behavior** CI on main.
Inspect the deployment result before claiming that mirror has updated.
