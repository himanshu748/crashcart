import { build } from 'esbuild';
import { mkdir, writeFile } from 'node:fs/promises';

// This is an optional local overlay, not part of the keyless replay bundle.
// Only the explicit browser licence is embedded. Never commit this output.
const key = process.env.AG_STUDIO_LICENSE_KEY?.trim();
const outdir = '../web/studio-recorded';
await mkdir(outdir, { recursive: true });
await build({
  entryPoints: ['src/main.tsx'], bundle: true, format: 'esm', target: 'es2022',
  outdir, minify: true, legalComments: 'linked',
  define: {
    'process.env.NODE_ENV': '"production"',
    '__CRASHCART_RECORDED_STUDIO__': 'true',
    '__CRASHCART_AG_STUDIO_LICENSE_KEY__': key ? JSON.stringify(key) : 'undefined',
  },
  loader: { '.woff2': 'file', '.woff': 'file', '.svg': 'file' },
});
await writeFile(`${outdir}/index.html`, '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="csp-nonce" content="__STYLE_NONCE__"><title>Checkout explorer | CrashCart</title><link rel="stylesheet" href="./main.css"><script type="module" src="./main.js"></script></head><body><div id="root"></div></body></html>');
await writeFile(`${outdir}/recorded-studio-build.json`, JSON.stringify({ version: 1, licensed: Boolean(key) }) + '\n');
console.log(`Recorded explorer built. Licence configured: ${Boolean(key)}. Output is private and gitignored.`);
