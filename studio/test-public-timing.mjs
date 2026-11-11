import {build} from 'esbuild';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawnSync} from 'node:child_process';
const dir=await mkdtemp(join(tmpdir(),'crashcart-public-timing-'));
try {
 const output=join(dir,'tests.mjs');
 await build({entryPoints:['../tests/public_timing_test.ts'],bundle:true,platform:'node',format:'esm',outfile:output});
 const result=spawnSync(process.execPath,[output],{stdio:'inherit'});process.exitCode=result.status??1;
} finally {await rm(dir,{recursive:true,force:true});}
