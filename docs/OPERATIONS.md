# Keep the recorded demo online

Keep the existing host, address, certificate storage and site files available through **22 December 2026**. There is no scheduled teardown. This is a shared host; CrashCart adds no instance or paid service.

## Health

```sh
curl --fail --silent --show-error https://crashcart.52.202.25.181.sslip.io/healthz
```

Expected: HTTP 200 with JSON containing `"status":"recorded-demo"`, `"scope":"static-asset-serving"` and `"live_services_checked":false`. This checks that the public static release is being served. It does not check PayPal or an AI provider and makes no provider call.

Also check the [recorded example](https://crashcart.52.202.25.181.sslip.io/demo.html). It must show a missing ticket and a separate recovered-order replay. The keyless local command remains available if the host or its DNS is unavailable.

## What serves the site

The existing `embodiweave-demo` Lightsail instance in `us-east-1` serves CrashCart through its shared Caddy container, `ew-proxy`. The static site is mounted at `/data/crashcart/site-b0e304a` inside that container. No CrashCart worker, payment credentials or model keys run on this public host.

## Restart and recovery

Use the existing verified SSH access; do not disable host-key checks. Inspect before taking action:

```sh
sudo docker inspect ew-proxy --format '{{.State.Status}}'
sudo docker logs --tail 50 ew-proxy
```

If the existing proxy container is **stopped**, start it:

```sh
sudo docker start ew-proxy
```

Then rerun the public health and link checks. There is no separate CrashCart process to restart. If the shared proxy is running but unresponsive, coordinate with the host owner before `sudo docker restart ew-proxy`: that action briefly affects the other applications on the same proxy. A static release update normally needs **no restart, reload or Caddy configuration change**.

Publish updates with a validated same-volume directory exchange and retain the previous release. Do not run global Compose shutdown/prune, delete the host or volume, or replace the shared proxy configuration to repair one page. [Existing-host details](LIGHTSAIL_SHARED_HOST.md).

GitHub Pages is published by the repository’s **Recorded walkthrough** workflow after the **Source behavior** workflow succeeds on main. Inspect the workflow’s result before claiming that mirror has updated.
