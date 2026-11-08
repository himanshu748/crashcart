# Private PayPal Sandbox workspace — deployment candidate

This is a reviewable candidate, **not a deployed service**. The recorded public demo stays independent. This image provides authenticated PayPal Sandbox checkout, durable recovery and queued Modal investigations. AG Studio, Bryntum, KERNEL, webhooks, direct synchronous analysis and replay import are deliberately unavailable here. Optional view links explain this scope and return to the core workspace. No production-money checkout is supported.

Deployment requires separate owner approval for host credentials, the exact model allowance and up to eight Sandbox cases. Secret-free image and runtime probes have run on the shared host without provider credentials, public ports or provider calls. They do not establish live deployment. [Actual checks, retained failures and cleanup](../../evidence/runs/submission-ready/live-host-candidate-nov8/proof.json).

## Boundaries

- Only `workshop-v1`, actual Sandbox modes and approved fault types; process-interruption faults are disabled. The deterministic 60-second delivery rule is unchanged.
- Every case consumes one of eight persistent grants **before** creation. Failure, cancellation and restart never refund one. A crash between creation and grant binding leaves a quarantined record and consumed slot; it is hidden from hosted lists, reads and dispatch without blocking other granted cases. One case's order is protected by the existing payment-operation idempotency. Do not delete the database to obtain more grants.
- The existing private version-1 model ledger must already exist: 24 calls, $1 ceiling, 40,000 microUSD reserved per dispatch. Runtime never initializes, resets or refunds it. Preserve historical ledgers; any separately authorized allowance needs its own reviewed bootstrap outside this service. Unknown `RESERVED` dispatches block new work.
- All mutations except login need an operator token/cookie. Cookie is Secure, HttpOnly and SameSite Strict. Cross-origin mutations are rejected. The access token is a high-entropy private password; never put it in a URL.
- An explicit timezone-aware window end is required, no later than `2026-12-23T00:00:00Z` (through 22 December UTC). New work stops at expiry; the CLI also exits at expiry. Docker's private PID namespace stops its remaining local processes. A provider request already accepted remotely cannot be undone or un-billed by this timer.
- API and worker have a combined 384 MiB memory cap, 0.35 CPU quota and 128 PID cap; read-only roots, non-root UID/GID 10001, dropped capabilities, no-new-privileges and OOM score 500. Two child worker roles keep model waiting separate from checkout recovery. These are configuration limits, not measured hosting performance.
- API listens on port 8765 **inside its container**, with no published port. Use only the existing `embodiweave-net` network already attached to `ew-proxy`; add no proxy network/interface. The new hostname is `workspace-crashcart.52.202.25.181.sslip.io`.
- No `.env`, credential, ledger, evidence archive or private licensed JS bundle is copied into the image. The private credential file is an explicit read-only host mount; state and the ledger directory are writable mounts because atomic ledger replacement and locking require the directory.

## Local candidate checks

```sh
python3.13 -W error::ResourceWarning -m unittest tests.test_hosted_live -v
```

These tests use temporary SQLite, synthetic credentials/ledgers and loopback HTTP. They exercise authorization, strict request parsing, scope, permanent concurrent case limits, restart and quarantined partial creations, cancellation, missing/corrupt/unknown ledger rejection, independent worker claims, ambiguous-analysis non-retry, delayed-payment journaling after disconnect, overload recovery and Caddy in-place installation safeguards. They do not establish a hosted deployment or provider success.

## Prepared operator commands — after approval

Run in the reviewed repository checkout on the **existing** host, using its already approved, host-key-pinned SSH connection. Preserve the other applications, proxy interfaces and existing recorded CrashCart route. Do not open a new inbound application port.

Preflight immediately before launch:

```sh
awk '/MemAvailable:/ {if ($2 < 786432) exit 1; print}' /proc/meminfo
df -Pk .
docker inspect ew-proxy --format '{{json .NetworkSettings.Networks}}'
docker network inspect embodiweave-net --format '{{.Name}}'
docker version --format '{{.Server.Version}}'
docker compose version
```

Stop if available RAM is below 768 MiB, disk is insufficient, the proxy/network differs or other apps are unhealthy. Do not pull a base image. Set these non-secret values explicitly; `CRASHCART_PYTHON_IMAGE` must be an already-present reviewed Python 3.13 **digest**, not a tag:

```sh
export CRASHCART_LIVE_TAG=REVIEWED_SOURCE_REVISION
export CRASHCART_PYTHON_IMAGE=python@sha256:REVIEWED_ALREADY_PRESENT_DIGEST
export CRASHCART_PROXY_NETWORK=embodiweave-net
export CRASHCART_LIVE_STATE_DIR=/srv/crashcart-live/state
export CRASHCART_LIVE_CREDENTIAL_FILE=/srv/crashcart-live/private/runtime.env
docker image inspect "$CRASHCART_PYTHON_IMAGE" --format '{{.Id}}'
```

The owner stages the approved `runtime.env` using `runtime.env.example` as its field list. Use the owned PayPal Sandbox app, the same approved exact Modal origin/base pin and fixed model, a fresh high-entropy workspace password, and the approved expiry. No key is entered into an image build argument, Compose environment, repository or command line. The owner also supplies the already reviewed private v1 ledger at `state/model-allowance/allowance.json`, preserving its existing metadata and entries. The runtime will fail closed without it.

For **new** private directories/files only (do not overwrite a previous state or ledger):

```sh
sudo install -d -o 10001 -g 10001 -m 700 /srv/crashcart-live/state /srv/crashcart-live/state/model-allowance /srv/crashcart-live/private
# Stage the approved credential and ledger files privately before continuing.
sudo chown 10001:10001 "$CRASHCART_LIVE_CREDENTIAL_FILE" "$CRASHCART_LIVE_STATE_DIR/model-allowance/allowance.json"
sudo chmod 600 "$CRASHCART_LIVE_CREDENTIAL_FILE" "$CRASHCART_LIVE_STATE_DIR/model-allowance/allowance.json"
```

Validate Compose, then build offline; a missing cached base is a blocker, not permission to download:

```sh
docker compose -f deploy/live/compose.yaml config --quiet
docker build --network=none --pull=false --build-arg "PYTHON_IMAGE=$CRASHCART_PYTHON_IMAGE" -f deploy/live/Dockerfile -t "crashcart-live:$CRASHCART_LIVE_TAG" .
docker image inspect "crashcart-live:$CRASHCART_LIVE_TAG" --format '{{.Id}} {{.Config.User}}'
docker compose -f deploy/live/compose.yaml up -d --no-build --pull never
```

Before exposing the hostname, inspect health/resource settings without printing credential content:

```sh
docker compose -f deploy/live/compose.yaml ps
docker compose -f deploy/live/compose.yaml exec -T api python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8765/healthz",timeout=2).status)'
docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}\t{{.PIDs}}'
docker compose -f deploy/live/compose.yaml ps -q | xargs docker inspect --format '{{.Name}} memory={{.HostConfig.Memory}} pids={{.HostConfig.PidsLimit}} cpu={{.HostConfig.NanoCpus}} oom={{.HostConfig.OomScoreAdj}} readonly={{.HostConfig.ReadonlyRootfs}} ports={{json .HostConfig.PortBindings}}'
```

For Caddy, discover both the **existing host-mounted configuration path** and its path inside `ew-proxy` from `docker inspect ew-proxy`. Do not assume paths, replace a bind-mounted file's inode, or replace the complete configuration with the fragment. Docker file bind mounts retain the original inode, so an atomic rename on the host would leave Caddy reading old bytes.

Set `CADDY_HOST_CONFIG` and `CADDY_CONTAINER_CONFIG` to those verified absolute paths. The following sequence prepares an append-only complete candidate, copies it to a temporary container path, validates it with the existing Caddy binary and then performs a checksum/CAS-guarded **in-place** write with fsync. The installer locks the original inode, refuses changed source/current checksums, preserves every old byte, saves an exclusive 0600 durable backup and never reloads automatically. If the current file changes, rebuild and revalidate; do not bypass the checksum. No other host block or global option is changed. `flock` coordinates only cooperating writers: use a quiet deployment window with no other configuration editors. After writing, the installer checks the pathname against the still-open inode again; if it changed, it restores the original bytes through that open handle and fails without touching the substituted path.

```sh
set -euo pipefail
export CADDY_COMBINED="${CADDY_HOST_CONFIG}.crashcart-live.pending"
export CADDY_BACKUP="${CADDY_HOST_CONFIG}.before-crashcart-live"
export CADDY_CONTAINER_PENDING=/tmp/crashcart-live-Caddyfile.pending
export CADDY_OLD_SHA=$(sudo sha256sum "$CADDY_HOST_CONFIG" | cut -d ' ' -f 1)
sudo python3 - "$CADDY_HOST_CONFIG" "$CADDY_COMBINED" deploy/live/Caddyfile.fragment <<'PYCODE'
import os, pathlib, sys
old, output, fragment = map(pathlib.Path, sys.argv[1:])
data = old.read_bytes() + b'\n' + fragment.read_bytes()
fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
with os.fdopen(fd, 'wb') as handle:
    handle.write(data); handle.flush(); os.fsync(handle.fileno())
PYCODE
export CADDY_VALIDATED_SHA=$(sudo sha256sum "$CADDY_COMBINED" | cut -d ' ' -f 1)
sudo docker cp "$CADDY_COMBINED" "ew-proxy:$CADDY_CONTAINER_PENDING"
docker exec ew-proxy caddy validate --config "$CADDY_CONTAINER_PENDING" --adapter caddyfile
# Continue only after the exact candidate validates. Existing relative imports,
# if any, must also resolve in this validation location; a failure blocks install.
sudo python3 deploy/live/install_caddy.py "$CADDY_HOST_CONFIG" "$CADDY_COMBINED" "$CADDY_OLD_SHA" "$CADDY_VALIDATED_SHA" "$CADDY_BACKUP"
docker exec ew-proxy caddy validate --config "$CADDY_CONTAINER_CONFIG" --adapter caddyfile
docker exec ew-proxy caddy reload --config "$CADDY_CONTAINER_CONFIG" --adapter caddyfile
curl --fail --silent --show-error https://workspace-crashcart.52.202.25.181.sslip.io/healthz
```

Run these as sequential checked steps: any failed validation/checksum/write stops the sequence before reload. Before reload, independently compare the host and container configuration checksums and inode identities against the installed target; stop if either differs. Confirm the container sees the new hostname through its original mounted configuration and all previous hostnames still return their prior service. A local write failure attempts restoration in the same inode; power loss can still leave a partial on-disk write, requiring restoration from the durable backup **in place**, followed by validation. Never rename a backup over a file bind mount.

## Acceptance after launch

Inspect the workspace in an actual browser: login, create one approved Sandbox case, approve with the test buyer, capture, inspect the deterministic delivery finding, queue one bounded investigation, reload to see its durable result, and export the same records. Independently read back case count, exact ledger counts/cost and resource/OOM status. Record observed outcomes rather than treating HTTP 202, a container health check or an AI explanation as proof of payment/delivery. All provider actions consume the explicit approved allowance.

Check that unauthenticated reads of private records and mutations are rejected, that the existing public replay still works, and that every other host route remains healthy. Test cap/window failure states locally; do not spend eight hosted cases just to exercise exhaustion.

To stop only these new services:

```sh
docker compose -f deploy/live/compose.yaml stop
```

Retain the private state/ledger for accounting. To remove exposure, remove only the new hostname block from the complete Caddy configuration, validate and reload it, then confirm the original routes. Do not remove networks, volumes, shared proxy containers, existing app containers or the recorded demo. No automatic credential deletion/revocation is performed; the owner handles retention after the approved window.
