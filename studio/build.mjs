import {build} from 'esbuild';
import {mkdir,copyFile} from 'node:fs/promises';
// Only this explicit browser licence value is embedded. Server credentials and
// the rest of process.env must never become client-side build definitions.
const studioLicenseKey=process.env.AG_STUDIO_LICENSE_KEY;
await mkdir('../web/studio',{recursive:true});
await build({entryPoints:['src/main.tsx'],bundle:true,format:'esm',target:'es2022',outdir:'../web/studio',minify:true,legalComments:'linked',define:{'process.env.NODE_ENV':'"production"','__CRASHCART_AG_STUDIO_LICENSE_KEY__':studioLicenseKey?JSON.stringify(studioLicenseKey):'undefined'},loader:{'.woff2':'file','.woff':'file','.svg':'file'}});
await copyFile('index.html','../web/studio/index.html');
// A separate, read-only Bryntum Community entry keeps the beta SDK out of the core workspace.
await mkdir('../web/deadlines',{recursive:true});
await build({entryPoints:['src/deadlines.ts'],bundle:true,format:'esm',target:'es2022',outdir:'../web/deadlines',entryNames:'main',minify:true,legalComments:'linked',loader:{'.woff2':'file','.woff':'file','.ttf':'file','.svg':'file'}});
// Bryntum recognizes this explicit same-origin aggregate stylesheet and does not fall back to a CDN.
await copyFile('../web/deadlines/main.css','../web/deadlines/scheduler.css');
await copyFile('node_modules/@bryntum/scheduler-community/LICENSE','../web/deadlines/LICENSE.bryntum.txt');
await copyFile('node_modules/@bryntum/core-community/licenses.md','../web/deadlines/THIRD-PARTY-NOTICES.md');
await copyFile('vendor/FONT-AWESOME-LICENSE.txt','../web/deadlines/FONT-AWESOME-LICENSE.txt');
