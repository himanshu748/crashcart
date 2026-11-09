/* Source-bound offline replay setup/loader. No product timeout is changed. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const {spawn}=require('node:child_process');
const ROOT=path.resolve(__dirname,'../..');const MAX_BYTES=4*1024*1024;
const sha=raw=>crypto.createHash('sha256').update(raw).digest('hex');
function sourceHashes(){const names=JSON.parse(fs.readFileSync(path.join(__dirname,'replay_fixture_sources.json'),'utf8'));if(!Array.isArray(names)||!names.length||new Set(names).size!==names.length)throw Error('Invalid fixture source manifest');return Object.fromEntries(names.map(name=>{if(typeof name!=='string'||path.isAbsolute(name)||name.split('/').includes('..')||path.posix.normalize(name)!==name)throw Error('Fixture source path rejected');return [name,sha(fs.readFileSync(path.join(ROOT,name)))];}));}
function privateRead(file){const fd=fs.openSync(file,fs.constants.O_RDONLY|fs.constants.O_NOFOLLOW);try{const st=fs.fstatSync(fd);if(!st.isFile()||st.uid!==process.getuid()||(st.mode&0o777)!==0o600||st.nlink!==1||st.size>MAX_BYTES)throw Error('Fixture must be an owned regular 0600 file below 4 MiB');return fs.readFileSync(fd,'utf8');}finally{fs.closeSync(fd);}}
function readFixture(file){const wrapper=JSON.parse(privateRead(file));if(wrapper.kind!=='crashcart-ui-replay-fixture-v1'||wrapper.scope!=='recorded-offline-replay'||wrapper.network_calls!==0||typeof wrapper.data_json!=='string'||sha(wrapper.data_json)!==wrapper.data_sha256)throw Error('Invalid replay fixture metadata or content hash');const current=sourceHashes(),saved=wrapper.source_sha256;if(!saved||Object.keys(saved).length!==Object.keys(current).length||Object.entries(current).some(([name,digest])=>saved[name]!==digest))throw Error('STALE_REPLAY_FIXTURE: rerun the separate prepare step against current sources; no stale fallback permitted');const data=JSON.parse(wrapper.data_json);if(!data||data.mode!=='RECORDED_REPLAY'||data.fresh_execution!==false||data.network_calls!==0)throw Error('Fixture offline scope rejected');return data;}
async function prepareFixture(file){
 const python=process.env.CRASHCART_TEST_PYTHON||'python3';
 await new Promise((resolve,reject)=>{
  const child=spawn(python,[path.join(__dirname,'prepare_replay_fixture.py'),'--output',path.resolve(file)],{cwd:ROOT,env:{PATH:process.env.PATH,PYTHONPATH:ROOT,PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
  let out='',err='',timedOut=false;const timer=setTimeout(()=>{timedOut=true;child.kill('SIGTERM');},125000);
  child.stdout.on('data',chunk=>{out+=chunk;if(out.length>8192)child.kill('SIGTERM');});child.stderr.on('data',chunk=>{err+=chunk;if(err.length>16384)child.kill('SIGTERM');});
  child.once('error',error=>{clearTimeout(timer);reject(error);});
  child.once('close',code=>{clearTimeout(timer);if(timedOut)return reject(Error('Separate offline fixture setup exceeded 125-second process supervisor; no retry attempted'));if(code!==0)return reject(Error('Separate replay fixture setup failed ('+code+'): '+err.slice(-4000)));resolve();});
 });
 return readFixture(file);
}
async function loadFixture(){
 const supplied=process.env.CRASHCART_UI_REPLAY_FIXTURE;
 if(supplied)return readFixture(path.resolve(supplied)); // Explicit stale/corrupt files fail; never regenerate silently.
 const fingerprint=sha(JSON.stringify(sourceHashes()));const directory=path.join(os.tmpdir(),'crashcart-ui-replay-'+process.getuid());
 if(!fs.existsSync(directory))fs.mkdirSync(directory,{mode:0o700});
 const info=fs.lstatSync(directory);if(!info.isDirectory()||info.isSymbolicLink()||info.uid!==process.getuid()||(info.mode&0o777)!==0o700)throw Error('Private replay fixture cache directory rejected');
 const file=path.join(directory,fingerprint+'.json');
 if(fs.existsSync(file))return readFixture(file);
 return prepareFixture(file); // Standalone invocation remains reproducible through the same explicit setup script.
}
if(require.main===module){const [action,file]=process.argv.slice(2);if(!['prepare','verify'].includes(action)||!file){console.error('Usage: node tests/helpers/replay_fixture.cjs prepare|verify /absolute/new-fixture.json');process.exitCode=2;}else Promise.resolve(action==='prepare'?prepareFixture(file):readFixture(file)).then(data=>console.log(JSON.stringify({fixture:path.resolve(file),source_bound:true,network_calls:data.network_calls,cases:Object.keys(data.cases).length}))).catch(error=>{console.error(error.message);process.exitCode=1;});}
module.exports={sourceHashes,readFixture,prepareFixture,loadFixture};
