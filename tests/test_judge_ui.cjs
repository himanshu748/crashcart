// LOCAL_TEST: run the delivered page script with injected responses and a small
// DOM test double. Real browser/layout verification is recorded separately.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../web/judge/app.js'),'utf8');
const message='The saved investigation could not be opened. Reload this page to try again. No new payment or AI request was made.';
function element(){return {textContent:'',hidden:false,checked:false,dataset:{},handlers:{},classList:{add(){},remove(){},toggle(){},contains(){return false;}},addEventListener(type,fn){this.handlers[type]=fn;},setAttribute(name,value){this[name]=value;},focus(){},scrollIntoView(){}};}
async function load(fetchResult){
 const nodes=new Map();const byId=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};byId('review').hidden=true;
 const stories=['payment','delivery','repair'].map(stage=>({...element(),dataset:{story:stage}}));
 const cases=['defective','healthy'].map(variant=>({...element(),dataset:{case:variant}}));
 const links=[element(),element()];
 const calls=[];const document={getElementById:byId,documentElement:element(),querySelector:()=>element(),querySelectorAll:selector=>selector==='button[data-story]'?stories:selector==='[data-case]'?cases:selector==='a[href="#investigation"]'?links:[],createElement:()=>element()};
 const context=vm.createContext({document,window:{location:{hash:''},matchMedia:()=>({matches:false,addEventListener(){}})},fetch:async(...args)=>{calls.push(args);return fetchResult();}});
 vm.runInContext(source,context,{filename:'web/judge/app.js'});
 await new Promise(setImmediate);
 return {nodes,stories,cases,calls,links};
}
async function expectRecoverableFailure(response){
 const page=await load(response);
 assert.equal(page.nodes.get('load-state').textContent,message);
 assert.ok(page.links.every(link=>link.href==='#load-state'),'demo links must lead to visible recovery instead of a hidden result');
 assert.equal(page.nodes.get('load-state').hidden,false);
 assert.equal(page.nodes.get('review').hidden,true,'incomplete results remain hidden');
 for(const button of page.stories)assert.doesNotThrow(()=>button.handlers.click(),'walkthrough remains usable after failed data');
 for(const button of page.cases)assert.doesNotThrow(()=>button.handlers.click(),'case controls cannot render incomplete data');
 assert.equal(page.calls.length,1,'failure does not automatically retry or request a live action');
 assert.equal(page.calls[0][0],'data.json');
}
test('Unavailable response explains recovery without provider claims',()=>expectRecoverableFailure(()=>new Response('<html>unavailable</html>',{status:503})));
test('Malformed JSON does not expose parser jargon',()=>expectRecoverableFailure(()=>new Response('{',{status:200})));
test('Disconnected network leaves an understandable safe state',()=>expectRecoverableFailure(()=>{throw new TypeError('Failed to fetch');}));
test('Invalid comparison never displays a successful result',()=>expectRecoverableFailure(()=>new Response(JSON.stringify({mode:'LOCAL_TEST',fresh_execution:true}),{status:200})));
test('Partially parsed case is discarded before walkthrough reuse',()=>expectRecoverableFailure(()=>new Response(JSON.stringify({mode:'RECORDED_REPLAY',fresh_execution:false,cases:{defective:{receipt:{signature:'paid_without_ticket'}},healthy:{receipt:{signature:'ticket_delivered_once_on_time'}}}}),{status:200})));
