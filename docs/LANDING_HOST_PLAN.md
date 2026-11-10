# Landing alignment: deployment and rollback

Prepared locally on `landing-motion-nov10`, 10 November 2026.
No deployment, push, PR, merge, branch deletion or submission edit has occurred.

## Small change to prepare

Keep PR #5's landing, typography, motion, screenshots and recorded inputs.
Move the landing's disclosure text to its existing footer disclosure; retain
accurate recorded/replay labels on the product visual and destination pages.
Use “Try interactive demo” and “Watch 2:45 demo”, without implying new provider
calls. Check 360px, reduced motion and Lighthouse before proposing publication.
No invariant, payment rule, replay fixture, sponsor selection or AG Grid question
is in scope.

The dedicated host will receive the **same complete static export** as Pages,
not a separately maintained landing. Local work does not change either site.

## Gates, in order

Each action below requires its own exact `submit` after its STOP report:

1. Push `landing-motion-nov10` and open its PR together.
2. Merge after CI is green.
3. Publish Pages from that exact merged main revision and read it back.
4. Deploy that same revision to the dedicated host and read it back.
5. Delete remote `imgbot`.
6. Delete remote `ship/devpost`.
7. Delete remote `sponsor-prizes-nov10`.
8. Delete remote `ui-motion-nov10`.
9. Prepare the separate AGENTS relocation PR; its publication remains gated.

No Devpost, video, sponsor or default-branch changes are bundled into deployment.

## Dedicated-host release procedure (not executed)

Target: `https://crashcart.32.193.44.79.sslip.io/`.
Existing installation: `/opt/crashcart`, container `crashcart-demo`, with the
site mounted read-only at `/srv` and persistent HTTPS certificate storage.
Recheck these installation facts over strictly pinned SSH before mutation;
stop if they differ. Reuse the existing identity and accepted host-key pin.
Do not change firewall, DNS, instance size, image or billing.

1. From a clean checkout of the approved **merged main SHA**, run the local
   suite, both replays and `./scripts/judge.sh`. Export once using the supported
   Python, without credentials:

   ```sh
   python3 -m crashcart.judge --export-site "$RELEASE/site"
   ```

   `$RELEASE` is a new local release directory. Record hashes of every exported
   file. The export must match the Pages artifact for this same revision.
2. Inspect the existing container mounts, image and configuration. Copy the
   existing Caddyfile and release metadata into a new root-owned backup
   directory `/opt/crashcart/backups/landing-<SHA>`. Retain the old site files
   and certificate directories without altering them.
3. Transfer **only the static export** into a new directory
   `/opt/crashcart/site/releases/<SHA>`. Verify every transferred file against
   the local hashes before activating it. No `.env`, keys, source checkout,
   dependencies or licensed Studio bundle belongs in this upload.
4. Prepare a candidate from `deploy/judge/Caddyfile.dedicated-static`, changing
   only `root * /srv` to `root * /srv/releases/<SHA>`. Its `font-src 'self'`
   permits the existing self-hosted fonts. Preserve GET/HEAD-only access,
   private-route exclusion, CSP and direct public-route rewrites.
5. Validate the candidate using the existing pinned Caddy image with networking
   disabled. Stop if validation fails. Preserve the validation output.
6. Write the candidate into the existing host Caddyfile **in place**, preserving
   its inode because Docker bind-mounts that file. Restart `crashcart-demo`;
   the configured Caddy admin endpoint is off, so this is a brief restart,
   not a claimed zero-downtime reload. Do not recreate the instance/container.
7. Verify trusted HTTPS, `/`, `/product`, `/example`, `/integrations`,
   `/demo.html`, `/healthz`, fonts and motion assets. Compare all static bytes
   with the reviewed export. Check the recorded interactions, 360px and
   reduced motion in a fresh browser. Retain the host through 22 December.

## Rollback (part of the separately approved deployment)

If activation or public readback fails, stop further rollout. Restore the
backed-up Caddyfile **in place**, flush it to disk, then run:

```sh
sudo docker restart crashcart-demo
```

Verify the old index hash and the public routes against the pre-deploy snapshot.
The old site remains at `/opt/crashcart/site`; the old configuration points back
there. Retain the candidate release, backups and failure output. Delete nothing,
touch no certificates, and make no automatic second deployment attempt.

## Local preflight and current stop

The first local `./scripts/judge.sh --no-open --port 8912` attempt exited 1:
`CrashCart requires Python 3.11 or newer`. The operator invoked system Python
instead of the available supported Python. That failed attempt remains recorded.
The owner authorized resumption with the supported interpreter. Python 3.13.15
then launched the unchanged script successfully in both the worktree and a clean
local clone, with no credentials. See [the local review](LANDING_MOTION_STOP.md).

Runtime commit: `941974b5bc8c9270c41f77d9a525b7a8c9c44a6f`.
Its static export contains 32 review files plus `.nojekyll`, including only the
explicit public presentation assets and saved observations. Its candidate
Caddyfile passed local Caddy validation. No SSH connection or remote validation
was performed. The old initial-deploy script is deliberately not reused: it
requires the original 17-file release and refuses an existing installation.

The release will be regenerated from the approved merged main revision before
its separately gated deployment; this local candidate does not authorize any
remote mutation. Existing Pages and dedicated-host content remain unchanged.
This document is the deploy/rollback plan, not a deployment receipt.
