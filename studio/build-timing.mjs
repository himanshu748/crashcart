import {build} from 'esbuild';
import {mkdir,copyFile,readFile,writeFile,readdir} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const out='../web/judge/assets/vendor/bryntum';
await mkdir(out,{recursive:true});
// MIT Community Scheduler reads saved rows by default; optional owner-scoped live rows use same-origin GET only.
// No AG Studio import, licence key, environment embedding or remote asset is allowed.
// Emit escaped string literals so upstream template whitespace is preserved
// without introducing trailing-whitespace errors in the committed bundle.
await build({entryPoints:['src/public-timing.ts'],bundle:true,format:'esm',target:'es2022',outdir:out,entryNames:'timing',minify:true,legalComments:'linked',supported:{'template-literal':false},
  loader:{'.woff2':'file','.woff':'file','.ttf':'file','.svg':'file'},metafile:true}).then(async result=>{
  if(Object.keys(result.metafile.inputs).some(n=>n.includes('ag-studio')))throw Error('AG Studio cannot enter the public bundle');
});
await copyFile(out+'/timing.css',out+'/scheduler.css');
await copyFile('node_modules/@bryntum/scheduler-community/LICENSE',out+'/LICENSE.txt');
await copyFile('node_modules/@bryntum/core-community/licenses.md',out+'/THIRD-PARTY-NOTICES.txt');
await copyFile('vendor/FONT-AWESOME-LICENSE.txt',out+'/FONT-AWESOME-LICENSE.txt');
const files={};
for(const name of (await readdir(out)).sort())if(name!=='manifest.json'){
 const raw=await readFile(out+'/'+name);files[name]={bytes:raw.length,sha256:createHash('sha256').update(raw).digest('hex')};
}
await writeFile(out+'/manifest.json',JSON.stringify({sdk:'@bryntum/scheduler-community',version:'8.0.0-beta.1',license:'MIT',source:'studio/src/public-timing.ts',default_source:'RECORDED_REPLAY',optional_owner_scoped_live:true,live_status_route:'/api/live/timing',files},null,2)+'\n');
console.log('Built keyless MIT Bryntum timing assets without service keys.');
