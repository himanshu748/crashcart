# Source-bound UI replay fixtures

UI tests consume actual keyless replay output rather than launching an opaque
Python `-c` command while the test module is loading. Setup is strictly offline;
no environment-file loader or live adapter is imported, and socket/DNS calls
are blocked. Both original outcomes are computed by the existing replay code.
Generated runtime IDs may differ between cases; the UI validates canonical
input identity and source mappings rather than literal cross-case IDs.

Run the setup separately before the final UI checks:

```sh
node tests/helpers/replay_fixture.cjs prepare /absolute/new-fixture.json
CRASHCART_UI_REPLAY_FIXTURE=/absolute/new-fixture.json node --test tests/test_workspace_api.cjs tests/test_background_ui.cjs tests/test_judge_ui.cjs
```

The output parent must already exist. A fixture is an exclusive new 0600 file;
setup never overwrites one. The metadata contains a data hash and before/after
hashes of the exact generator, input and helper files listed in
`replay_fixture_sources.json`. The loader recomputes those hashes and rejects
stale, corrupted, incorrectly scoped or unsafe-permission files. An explicitly
supplied bad fixture never falls back to automatic regeneration. Source binding
is provenance, not authentication of the original provider observations.

```sh
node tests/helpers/replay_fixture.cjs verify /absolute/existing-fixture.json
```

Standalone `node --test tests/test_judge_ui.cjs` remains reproducible: without
`CRASHCART_UI_REPLAY_FIXTURE`, the loader uses an owned 0700 temporary cache keyed
by current source hashes. If its current fixture is absent it invokes the same
setup script, then verifies it. Existing invalid cache entries fail closed.
The async setup hook completes before the unchanged UI assertions run.

Setup has its own explicit 120-second bound and 125-second subprocess supervisor.
These bounds apply only to offline fixture preparation. The 60-second ticket
promise, 180-second AI deadline, payment validators and all negative UI assertions
remain unchanged. No setup failure, recorded application failure or earlier test
failure is erased by preparing a new fixture.
