# Importing reviewed KERNEL evidence

KERNEL observations are collected in a private adapter receipt and recording. The local importer attaches an operator-reviewed receipt to its existing run without creating a browser, payment, ticket or fresh verification. There is no HTTP import endpoint. Public browser observations still identify themselves as LOCAL_BROWSER.

The review manifest is a local operator attestation, not a provider signature. Independently inspect the source freeze, reservation, receipt, recording and run identities before constructing it. Pin the receipt, recording, reservation and source-freeze hashes and the recording size. Keep the manifest and video private. A hash alone does not authenticate the claimed execution.

Validate without importing:

```sh
python scripts/import_kernel_evidence.py --db /absolute/path/to/copied.sqlite3 --artifact-root /absolute/path/to/project --manifest /absolute/path/to/private-review.json
```

Add `--apply` to persist the validated observations atomically. Repeating an identical import is idempotent; altered artifacts or conflicting reuse must fail. Exercise this on an isolated database copy before operating on an active dataset. Keep the original database and artifacts unchanged for audit.

Imported records retain the browser observation time as `event_time`, adapter receipt time in the payload, and local import time as `observed_at`. These clocks belong to different systems; timestamp ordering does not establish causality. The initial observation may have no order ID. An import must not fill that gap with an order created later.

Prior sandbox execution is explicitly labeled `PRIOR_SANDBOX_EXECUTION`; LOCAL_TEST records remain local test evidence. The investigator and dashboard retain this distinction. A missing captured page message stays missing, even when a server record or a navigation path suggests what happened. Session and replay IDs plus recording hash identify the private artifact; the UI does not expose private filesystem paths or authenticated live URLs.

A completed import proves local validation and persistence only. CC-012 requires separate complete real KERNEL checkout and independent payment, ticket and recording verification; an import alone cannot establish it. CC-013 and CC-016 retain their own full acceptance conditions. Imported recordings are not fresh sandbox verification.

## Captured browser labels

A newly reviewed manifest can opt into `"browser_projection": "captured-fields-v2"`. This version projects the exact captured `run_state`, `provider_title`, `merchant_title` and `verdict` strings into a separate redacted `observed_fields` object. They come from DOM reads in the immutable adapter receipt, not from the merchant database or a newly calculated result. A captured delivery label is customer-view evidence, never independent payment proof.

The page message remains separate, including when it is empty. Older manifests default to `message-v1`, preserving existing payloads, identity ordering and idempotence. A v2 manifest cannot upgrade an existing v1 import in place; conflicting reuse is rejected. Use a fresh isolated database copy when evaluating the new projection and preserve the prior copy and manifest.

## Watching a private saved checkout

Local operators may explicitly enable `CRASHCART_ALLOW_PRIVATE_RECORDINGS=1` on a server bound to loopback. The run API then returns path-free availability metadata. `GET /api/runs/<run-id>/recording` still requires the existing operator session or bearer authorization; the URL alone grants no access. The source must be the run's unique imported `kernel-video-v1` reference, agree with its KERNEL observation hash/size, remain inside the owned project `var/` directory, and pass regular-file, no-alias, bounded-size, MP4-header and SHA256 checks. Symlinks, hardlinks, path escapes, wrong kinds, missing files and changed bytes fail closed. Strict single byte ranges support native video seeking.

The dashboard's Watch saved checkout control opens native video controls only on request, with no autoplay or preload. It labels the recording as a private earlier checkout. This is local operator access, not public video publication or a fresh verification. The gateway gains no additional route. Raw private paths and live-session URLs are never sent in recording availability metadata. A whole-recording privacy review is still required before any separately authorized public release.

## Separate browser session outcomes

A newly reviewed manifest may use `"browser_projection": "execution-fields-v3"`. It retains the same exact redacted captured DOM fields as v2 and additionally projects the receipt's independently recorded browser `status` and `recording_state` into `browser_execution`. The optional issue is reduced to a fixed allowlisted category; arbitrary error text, URLs, credentials and orchestration strings are never projected. This metadata says whether browser evidence collection finished; it never changes payment state, the stored ticket or the deterministic delivery verdict.

The workspace shows a separate browser-session notice. A partial recording is labelled before it is opened and again above the player. An earlier failed browser session can coexist with a legitimately completed payment and ticket; neither result overwrites the other. Existing saved observations without execution metadata disclose that the browser-session outcome is unavailable, rather than assuming completion.

Existing `message-v1` and `captured-fields-v2` event payloads remain byte-identical and idempotent. New projection versions cannot rewrite an existing session import. Evaluate v3 using a new isolated copy and a new explicitly reviewed manifest, retaining the original database, manifest, receipt and private video. No new browser or payment is created by that local import.
