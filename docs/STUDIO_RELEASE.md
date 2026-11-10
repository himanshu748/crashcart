# Recorded Studio release — prepared, not deployed

This optional explorer is a local feature-branch build. Main, the public sites,
the submitted entry and video remain unchanged. Public release needs the owner's
exact `submit` instruction and an applicable vendor entitlement.

## Local preflight

Use Python 3.11+ (tested 3.13.15), the pinned npm lockfile, and a licence supplied
privately to the build process. `npm run build:recorded --prefix studio` reads
only `AG_STUDIO_LICENSE_KEY`. Its ignored output embeds that browser licence;
never commit it or publish it in a build log. It contains no PayPal, model or
operator credentials.

```sh
npm run typecheck --prefix studio
npm run test:recorded --prefix studio
npm run test:presentation --prefix studio
python3 -m unittest tests.test_recorded_studio tests.test_judge -q
python3 -m crashcart.recorded_studio --output var/studio-release
python3 -m crashcart.recorded_studio --serve --port 8769
```

The export refuses existing destinations and returns exact file hashes and its
matching explorer CSP. No host is contacted. There are no private API routes.
The loopback server rejects writes. The records endpoint contains the two
recomputed saved variants and a separate earlier historical AI summary.

Without a build, or with a build declared unlicensed, `/explorer/` shows an
access message and serves neither SDK files nor record data. The declaration
establishes key configuration, not entitlement: the vendor SDK still validates
the key. Never publish an invalid build as a working explorer.

## Deployment delta for later approval

Retain the default review and downloads; add only `explorer/`. The keyless ZIP
stays vendor-free. Keep both existing sites working. This extension is intended
for the existing Lightsail static host, not a new service or Render migration.

Only explorer HTML needs the extra CSP from its export: a matching style nonce,
the pinned 3.0.0 color-sensor hash, same-origin fonts and data images. Scripts
and connections remain same-origin. No unsafe-inline, unsafe-eval, wildcard or
remote-font permission is proposed. Other pages retain their strict policy.
Use the exact policy from the final export, not a nonce from another export.

The [prepared Caddy template](../deploy/judge/Caddyfile.recorded-studio) is not
an applied change. Replace its nonce placeholder from the export and validate
the complete shared config before reload. It internally rewrites `/product`,
`/example` and `/integrations`. The local Python server already serves those
extensionless routes directly. Pages directory aliases remain compatible.

The template passed local Caddy 2.11.9 validation and an HTTP-only loopback
preflight: eight routes returned 200, extensionless pages served directly,
writes returned 405, and actual Studio rendered with its route-specific CSP.
The temporary proxy was stopped. This does not establish live-host HTTPS or
compatibility with that host's complete shared configuration. A future
authorized deployment must preserve the other applications, validate that full
configuration and inspect actual HTTPS headers and public URLs.

## Licence decision

AG Grid's [6 November announcement](https://www.ag-grid.com/blog/build-a-payments-dashboard-without-building-a-dashboard/)
says entries need no licence during judging and AG Grid will provide the key.
No judging-period key has been delivered/configured here. The existing private
trial ends 17 December; it does not establish coverage through 22 December.
Local evaluation is separate from a permitted public release. No key is in Git.

Prepared message for the official AG Grid hackathon channel, **not sent**:

> CrashCart is already submitted to the PayPal AI Hackathon. We use AG Studio
> 3.0.0 with five custom evidence panels, a themed layout and the native Agent
> Framework over clearly labelled recorded checkout data. Your 6 November post
> says you will provide judging-period keys. How should we obtain the key and
> confirm public read-only demo access through 22 December 2026? Our private
> trial ends 17 December. We will keep the key outside source control.
> Project: https://devpost.com/software/crashcart-87asqz

Do not select AG Grid until a permitted public explorer is visible and tested.
Bryntum's existing public video segment stays unchanged.
