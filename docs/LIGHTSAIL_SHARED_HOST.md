# CrashCart on the existing Lightsail host

**Previous shared-host URL (retained; no longer the primary demo):** https://crashcart.52.202.25.181.sslip.io/

Verified 8 November 2026. This serves the interactive **recorded demo**: replay
results computed during export and a separate historical AI investigation.
It does not host the merchant API, accept payments or run new AI calls.
[Deployment evidence](../evidence/runs/submission-ready/lightsail-hosted-nov8.json).

## Deployment and cost

The existing `embodiweave-demo` instance in `us-east-1` already hosts several
applications. Its `ew-proxy` Caddy container serves the public export from
`/data/crashcart/site-b0e304a`, within its persistent data volume. The
[exact-host configuration](../deploy/judge/Caddyfile.shared-static) adds only
CrashCart's hostname. No global settings or earlier application routes changed.

There is no new permanent container, network, listener, instance, disk or load
balancer. The existing proxy was validated and reloaded without restarting it.
All six earlier route objects and HTTP responses were preserved, including the
existing protected and retired pages. All ten served export files match their
frozen release hashes; no private files or symlinks are in that export.

The existing host costs **$12/month base**, already incurred for its other apps.
CrashCart adds **$0 in instance base fees**; no plan upgrade was made. Existing
transfer limits, taxes and account charges still apply. The account-wide $20/$50
alerts were read back; email delivery is untested and alerts are not hard caps.

DNS uses the same public-IP-based `sslip.io` pattern as the other sites. A trusted
Let's Encrypt certificate was observed, expiring 6 February 2027. Existing Caddy
certificate storage and renewal remain in use. This is not an uptime guarantee
or ownership of the `sslip.io` domain. The local runnable build remains available
without that DNS service.

## Verification boundaries

Trusted HTTPS 200, POST 405, `.env` 404, live-API 404 and a traversal probe passed.
Actual browser checks covered the landing story, repaired case, PayPal filter,
three historical AI steps, Enter/Space, 390/320px layouts and reduced motion.
The download-event wait timed out; the browser's direct-download API saved the
ZIP. Its bytes matched HTTPS, and manifest/defective/healthy commands returned
the expected exits 0/1/0.

Two Mac suite failures exposed separate fixture bugs: discontinuous mocked
clocks and a webhook body sent with a GET health probe. Both are retained. After
the repairs, a separate isolated Linux run passed all 491 tests with networking
disabled. This does not establish a passing full Mac run or live-provider proof.

An extra-container topology was abandoned after a routing guard detected an added
private route. BusyBox returned the full table; the default gateway had not
changed. That container/network was removed and the exact original table restored.
The final design adds neither. Docker reordered mount metadata, and Caddy's
automatic config-file hide path depended on where its candidate was adapted.
Complete mount objects match; adapting at the actual deployment path matches the
active configuration. No handler, permission or existing route was ignored.

## Export and maintenance

From the public source with Python 3.11+:

```sh
python3 -m crashcart.judge --export-site /tmp/crashcart-public-site
python3 -m unittest tests.test_judge tests.test_public_replay -v
```

Only the public export belongs in the served subtree. Never upload `.env`, private
databases, acceptance archives, licensed bundles or provider keys. Administration
requires a verified SSH connection. AWS temporary certificates expire; refresh
them rather than bypassing host verification. Multiplexing needs a short private
socket path on macOS, such as a directory created under `/tmp` with mode 0700.

Read-only checks on the host:

```sh
sudo docker exec ew-proxy caddy version
sudo docker exec ew-proxy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
sudo docker inspect ew-proxy --format '{{.Id}} {{.Image}} {{.State.StartedAt}}'
```

The bind-mounted configuration is `/opt/embodiweave/source/deploy/Caddyfile`;
the original backup is private at
`/opt/crashcart/private/proxy-before-crashcart.Caddyfile`. An authorized update
must compare its expected checksum, preserve other routes, validate the complete
candidate, write that bind-mounted file in place, then reload:

```sh
sudo docker exec ew-proxy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Do not restart/recreate the proxy, run global Compose shutdown/prune, or change
other apps to update CrashCart. The standalone Compose plan is for a dedicated
host and was not used here.

## Retention and removal

Additive `CrashCartMode=RecordedDemo` and `CrashCartRetainThrough=2026-12-22`
tags are present; existing tags remain. Keep the host, address, DNS, certificate
volume and export through the winner announcement, with the 22 December UTC
buffer. No automatic deletion is installed; future uptime remains unverified.
Freeze submitted source/video/linked material after the deadline until winners
are announced. Keeping the unchanged service running includes certificate renewal.

After 23 December UTC, remove only CrashCart's exact-host block and subtree after
backup and validation. **Do not stop/delete this instance or its shared Caddy
volume:** other apps depend on them. Restoring the entire old backup can erase
later unrelated changes; confirm checksums and ownership before any rollback.
Temporary operator SSH access is cleaned up separately from the running demo.
