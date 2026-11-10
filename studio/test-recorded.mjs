import { build } from 'esbuild';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const dir = await mkdtemp(join(tmpdir(), 'crashcart-recorded-tests-'));
try {
  const output = join(dir, 'tests.cjs');
  await build({ entryPoints: ['../tests/studio_recorded_test.ts'], bundle: true,
    platform: 'node', format: 'cjs', jsx: 'automatic',
    nodePaths: [fileURLToPath(new URL('node_modules/', import.meta.url))], outfile: output });
  const result = spawnSync(process.execPath, [output], { stdio: 'inherit' });
  process.exitCode = result.status ?? 1;
} finally {
  await rm(dir, { recursive: true, force: true });
}
