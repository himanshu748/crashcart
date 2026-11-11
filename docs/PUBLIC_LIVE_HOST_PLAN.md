# Public Sandbox workspace: prepared host plan

Prepared 12 November 2026 IST. **Not deployed. No host connection, resource,
credential transfer, webhook registration or provider call was performed.**
The target remains the existing dedicated host:
<https://crashcart.32.193.44.79.sslip.io/>. No new instance, plan, DNS, firewall,
certificate storage or billing change is included. Every external step below
requires its own applicable `submit` gate; this document is not that approval.

## What would change

Keep Caddy serving the approved static replay directly, including `/healthz`.
Add a loopback-only Python 3.11+ service for `/api/live/*`, `/return` and `/cancel`.
The new `crashcart.public_live` entry point can also serve the frozen judge
export, but Caddy does not depend on it for the public replay. If Python stops,
static pages remain available and API failures point to the saved replay.

The reviewed export currently contains **47 files**, including `live.html`,
`live.js` and `live.css`; the existing 44 files are retained. Pages stays static.
The actual Bryntum view starts with saved records and loads an owner's live
rows only on request. The server session cookie controls access to those rows.

Prepared files in `deploy/public-live/`:

- `crashcart-public-live.service`: unprivileged process, private state, finite
  resources and whole-control-group stop, including detached child sessions.
- `runtime.env.example`: no secrets; live switch and provider permissions off.
- `Caddyfile.template`: unchanged static CSP, finite ingress/proxy timeouts,
  narrow API routes, overwritten client-IP header and static fallback.
- `render_caddy.py`: refuses any network mode except verified `host`.
- `preflight.py`: local paused-mode check with no real provider dispatch.

## 1. Inspect first; do not switch

Use the existing accepted SSH host-key pin and identity. Do not use
`StrictHostKeyChecking=no`, accept a replacement fingerprint automatically, or
open SSH access under this plan. If access fails twice, stop and report.
The following commands are for the **existing host**, after inspection access is
within the current authorization. Keep outputs private where they expose host
paths; do not print environment contents or a complete `docker inspect` object.

```sh
sudo docker inspect --format '{{.HostConfig.NetworkMode}}' crashcart-demo
sudo docker inspect --format '{{.Image}}' crashcart-demo
sudo docker inspect --format '{{json .Mounts}}' crashcart-demo
sudo docker exec crashcart-demo caddy version
sudo readlink -f /opt/crashcart/site/current
sudo sha256sum /opt/crashcart/Caddyfile
/usr/bin/python3 --version
systemctl --version
sudo ss -ltnp '( sport = :8767 )'
```

**Topology gate:** Caddy must already use Docker `host` networking and receive
connections directly. With bridge networking, its `127.0.0.1` is not the host's
loopback. The backend rejects non-loopback binds and untrusted forwarded client
IPs. Stop and prepare a separately reviewed topology change if the inspection
shows a bridge, another proxy, an unknown mount, a conflicting port, Python
older than 3.11, or an unexpected Caddy version. Do not replace the upstream with
`host.docker.internal`, broaden the Python bind or recreate the container as an
automatic workaround. The current network mode is **not yet verified**.

Caddy's `/srv` bind must contain the full `site` parent directory, not a single
release. Its Caddyfile bind must be `/opt/crashcart/Caddyfile`. The certificate
volumes and container image remain untouched. Record the exact current static
root and active revision before replacing anything.

## 2. Local release and preflight

Use an explicitly approved, immutable source SHA. The commands below build
artifacts locally and do not connect or mutate the host:

```sh
CC_SHA=<APPROVED_FULL_40_CHARACTER_SHA>
CC_RELEASE_DIR=<NEW_PRIVATE_LOCAL_RELEASE_DIRECTORY>
mkdir -p "$CC_RELEASE_DIR"
git archive --format=tar "$CC_SHA" | gzip -n > "$CC_RELEASE_DIR/source.tar.gz"
# Run from a clean checkout of that same SHA, with Python 3.11+:
python3 deploy/public-live/preflight.py
python3 -m crashcart.judge --export-site "$CC_RELEASE_DIR/site"
python3 deploy/public-live/render_caddy.py --network-mode host --sha "$CC_SHA" > "$CC_RELEASE_DIR/Caddyfile"
```

`--network-mode host` is permitted only after recording that exact inspection
result; it is not an instruction to change Docker networking. Hash both the
source archive and every exported static file. Scan the source archive and
export for secrets before proposing transfer. The archive contains tracked
source, never `.git`, `.env`, private state, credentials or an MP4. No npm
installation, model bundle or licensed Studio workspace is required on the host.

Preflight also requires the full existing suite, judge checks, JavaScript tests,
TypeScript, lint/types and both canonical replay outcomes. The current local
paused check reports 47 files, all six advertised paths 200, checkout admission
denied and zero provider dispatches. Judge checks: 18/18 passed. This is **local
proof**, not Linux/systemd/Caddy or live PayPal/AI verification.

Validate the candidate using the **exact installed Caddy image digest**, not an
unpinned new image. With that existing image locally available, use:

```sh
CC_CADDY_IMAGE=<RECORDED_EXISTING_CADDY_IMAGE_ID>
docker run --rm --network none \
  --mount type=bind,src="$CC_RELEASE_DIR/Caddyfile",dst=/etc/caddy/Caddyfile,readonly \
  "$CC_CADDY_IMAGE" caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Do not pull another image or claim validation if the installed image is
unavailable. Validate the unit using `systemd-analyze verify` on the host before
installing it. Caddy and Linux unit validation remain pending actual inspection.

## 3. Stage privately, still paused — gated

After approval, transfer the verified archive, static export, candidate Caddyfile
and the reviewed unit with pinned SSH. Transfer no secret inside either archive.
On the host, use new paths containing the approved SHA and retain all old paths:

```sh
CC_SHA=<APPROVED_FULL_40_CHARACTER_SHA>
CC_STAGE=<VERIFIED_PRIVATE_UPLOAD_DIRECTORY>
sudo install -d -m 0755 /opt/crashcart/public-live/releases
sudo install -d -m 0755 "/opt/crashcart/public-live/releases/$CC_SHA"
sudo tar -xzf "$CC_STAGE/source.tar.gz" -C "/opt/crashcart/public-live/releases/$CC_SHA"
sudo install -d -m 0755 "/opt/crashcart/site/releases/$CC_SHA"
sudo cp -a "$CC_STAGE/site/." "/opt/crashcart/site/releases/$CC_SHA/"
# Verify every transferred checksum before continuing.
getent passwd crashcart-live
# If absent, create only this unprivileged service identity:
# sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin crashcart-live
sudo install -d -m 0700 /etc/crashcart
sudo install -o root -g root -m 0600 "$CC_STAGE/runtime.env.paused" /etc/crashcart/public-live.env
sudo install -o root -g root -m 0644 "$CC_STAGE/crashcart-public-live.service" /etc/systemd/system/crashcart-public-live.service
sudo ln -s "/opt/crashcart/public-live/releases/$CC_SHA" "/opt/crashcart/public-live/current-$CC_SHA"
sudo mv -T "/opt/crashcart/public-live/current-$CC_SHA" /opt/crashcart/public-live/current
sudo systemd-analyze verify /etc/systemd/system/crashcart-public-live.service
sudo systemctl daemon-reload
sudo systemctl enable --now crashcart-public-live
curl --fail --max-time 3 http://127.0.0.1:8767/healthz
curl --fail --max-time 3 http://127.0.0.1:8767/api/live/config
```

The paused environment uses `CRASHCART_PUBLIC_LIVE_ENABLED=0`, authorized runs 0,
`CRASHCART_ALLOW_SANDBOX=0`, `CRASHCART_ALLOW_MODEL=0` and no credentials. Config
must return `enabled:false`, `mode:SAVED_REPLAY`, reason `PUBLIC_LIVE_PAUSED`.
Never use an operator access token in the public proxy or expose an operator API.

Before activation, verify loopback-only port 8767, root-owned read-only source,
private state mode 0700 and database mode 0600. Repeatedly starting a service
must not initialize/reset the model ledger, grant more runs or resume a payment.

## 4. Proxy switch — separate STOP and submit

Back up the existing Caddyfile and active-root information to a new private
backup directory, then validate the candidate with the exact existing image.
Only after approval, write the candidate into the existing bind-mounted file
**in place**, preserving its inode, and restart only `crashcart-demo`. The
candidate points `/srv/releases/<SHA>` at the verified static files. Do not
replace Docker mounts, network, certificates, container or any other host app.

```sh
CC_BACKUP=/opt/crashcart/backups/public-live-<APPROVED_SHA>
sudo install -d -m 0700 "$CC_BACKUP"
sudo cp -p /opt/crashcart/Caddyfile "$CC_BACKUP/Caddyfile"
sudo cp -p "$CC_STAGE/Caddyfile" "$CC_BACKUP/Caddyfile.candidate"
# The exact-image validation above must pass before this gated switch:
sudo sh -c 'cat "$1" > /opt/crashcart/Caddyfile' sh "$CC_BACKUP/Caddyfile.candidate"
sudo sync /opt/crashcart/Caddyfile
sudo docker restart crashcart-demo
```

Check trusted HTTPS and HTTP 200 on `/`, `/product`, `/example`, `/integrations`,
`/demo.html`, `/timing.html`, `/live.html` and `/healthz`; compare static hashes.
Check `/api/live/config` is paused. Stop Python deliberately and verify all
static paths remain 200 while live requests return a bounded replay fallback;
restart Python still paused. A static `/healthz` 200 does **not** prove live API
health. Check desktop/mobile, keyboard and reduced motion in a clean browser.

Client-IP verification is mandatory before any allowance is enabled: send a
spoofed `X-CrashCart-Client-IP` to a local non-provider integration harness and
confirm Caddy overwrites it with the connection's `remote_host`. Never trust
client-supplied `Forwarded` or `X-Forwarded-For`. Do not create a real checkout
just to verify proxy forwarding.

## 5. Credentials, webhook and live activation — still pending

The default remains paused. A later approved activation requires private
PayPal **Sandbox** app credentials, one separately scoped real webhook
registration at `https://crashcart.32.193.44.79.sslip.io/api/live/webhook`, the
existing authorized Modal credential and its exact allowed origin/model, a
stable random session secret of at least 32 characters, and an existing,
reviewed model-allowance ledger. Copy credentials only to the root-owned 0600
environment file; the service account's private ledger belongs in its state
directory with its stable sibling lock file. Never print, commit, reset or
recreate an allowance to regain consumed calls.

Webhook registration/removal is a separate external action within an explicit
PayPal approval. This preparation neither registers a subscription nor reuses
an old expired webhook grant. Keep its ID private in `PAYPAL_WEBHOOK_ID`.
Enabling requires the owner-approved remaining run allowance and expiry;
configured caps cannot exceed 8 total runs, 3/IP/hour, 8/day, three model calls
per run, and $1/day reserved allowance. These caps are ceilings, **not** spend
authorization. Do not use the maximums merely because the code permits them.

Editing the environment file does not update a running process. A reviewed
environment change requires `systemctl restart crashcart-public-live`. This
kills all phase children; interrupted attempts remain recorded and charged.
No new run or retry is authorized by restart. Fresh successful PayPal, webhook,
AI and Bryntum verification remains a distinct step, not inferred from preflight.

## Emergency stop and rollback

First `sudo systemctl stop crashcart-public-live`. `KillMode=control-group`,
`TimeoutStopSec=10` and `SendSIGKILL=yes` terminate/reap the service's remaining
phase and webhook children even though they start separate Unix sessions.
Confirm `systemctl show -p ActiveState -p SubState -p ControlGroup
crashcart-public-live` and inspect that control group for remaining processes.
Do not claim Linux reaping verified until this is exercised on the actual host.

Restore the saved Caddyfile **in place**, then restart Caddy:

```sh
sudo sh -c 'cat "$1" > /opt/crashcart/Caddyfile' sh "$CC_BACKUP/Caddyfile"
sudo sync /opt/crashcart/Caddyfile
sudo docker restart crashcart-demo
```

Verify previous static hashes and all old public routes. Preserve the source,
releases, backups, database, reservations and model ledger; delete nothing and
refund nothing. Do not disable certificates, host uptime or the recorded replay.
Keep the public demo reachable through 22 December 2026. Investigate one failed
switch before any retry; after two failures, stop and report the exact cause.

## Primary configuration references

[Caddy server timeouts](https://caddyserver.com/docs/caddyfile/options),
[proxy/header semantics](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy),
[body-size bound](https://caddyserver.com/docs/caddyfile/directives/request_body),
[proxy error handling](https://caddyserver.com/docs/caddyfile/directives/handle_errors),
and [systemd control-group killing](https://www.freedesktop.org/software/systemd/man/latest/systemd.kill.html).
