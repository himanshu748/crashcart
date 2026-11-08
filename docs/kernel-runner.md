# Observe an owned checkout with KERNEL

`run_kernel_checkout.py` connects CrashCart's existing bounded browser adapter to
an operator command. It opens **one remote browser**, records the existing owned
workshop checkout, then closes the browser and saves a private receipt/video.
The fixed `observe` scenario reads the selected case; it does not create an
order, sign in as a buyer, approve or capture a payment, or decide payment truth.

This is a configured operator tool, not part of the account-free recorded demo.
Running it can consume KERNEL credits. A valid grant is necessary but this guide
does not grant usage, spending or public exposure. No new provider execution is
claimed by the synthetic tests accompanying this command.

## Before running

- Use Python 3.11 or newer and an **existing** CrashCart SQLite database. The
  selection must be an uncancelled `LIVE_SANDBOX` or `FRESH_SANDBOX` run for the
  registered owned `workshop-v1` store. Recorded and local-test selections fail.
- The selected merchant must already be reachable at the **owned public HTTPS
  origin** in `CRASHCART_PUBLIC_URL`. The command does not start a server or
  tunnel. Verify that the remote target serves the same run and purchase as the
  local database. The adapter checks that identity again in the remote page.
- Privately export `KERNEL_API_KEY`, `CRASHCART_OPERATOR_TOKEN`,
  `CRASHCART_PUBLIC_URL` and `CRASHCART_ALLOW_KERNEL=1` into the command's
  environment. The script does not discover credentials or load `.env`.
- Supply an explicitly authorized, unexpired allowance JSON with `observe` in
  its existing `scenarios` list. The adapter enforces its origin, expiry,
  ten-to-300-second session bound and one-use reservation. It does not renew or
  manufacture a grant. Keep the same durable state directory so a used approval
  cannot be reused by accident. Follow the existing approved allowance process;
  no approval file is included in the public repository.

Replace the example run ID and private grant path with your actual authorized
selection; do not paste keys into this command or a public transcript:

```sh
python3 scripts/run_kernel_checkout.py \
  --db var/crashcart.sqlite3 \
  --run-id run_YOUR_EXISTING_32_HEX_ID \
  --allowance /absolute/private/path/to/approved-observation.json \
  --state-dir var/kernel
```

To inspect arguments without opening a session:

```sh
python3 scripts/run_kernel_checkout.py --help
```

## What the result means

An `OBSERVED_UNREVIEWED` result means the observation and private recording were
saved and the adapter reported cleanup succeeded. It includes the private
receipt path, the execution mode and `payment_verdict: NOT_EVALUATED`. It does
not print live-view/CDP URLs, session tokens, raw provider errors or credentials.
`INCOMPLETE` means cleanup or recording did not finish successfully; inspect the
private receipt and resolve that resource state before another authorized run.
Errors and interruptions are nonzero exits. Grants stay consumed after ambiguous
creation or failure, as in the existing adapter.

The receipt is **not automatically imported** into the investigation. Review its
run/purchase/recording identity and private artifacts first, then use
`scripts/import_kernel_evidence.py` with the required reviewed manifest. Its
validation-only default can be inspected before `--apply`. Reviewed browser
observations then belong to the same case that the investigator and AG Studio
read; the private recording remains separate from public submission media.
No payment state or delivery verdict is changed by the observer or importer.

## Local wiring check

```sh
python3 -m unittest tests.test_kernel_entrypoint tests.test_kernel_browser -v
```

These checks use injected KERNEL replies and synthetic video bytes, with network
connections blocked. They exercise the actual adapter/session lifecycle,
identity and grant rejection, cancellation, resource cleanup and private output.
They establish local wiring only. A fresh allowed KERNEL observation, a decoded
provider recording and reviewed import still require their own real execution
and evidence.
