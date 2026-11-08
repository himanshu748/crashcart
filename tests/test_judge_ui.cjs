// LOCAL_TEST: run the delivered page script with injected responses and a small
// DOM test double. Real browser/layout verification is recorded separately.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../web/judge/app.js'),'utf8');
const message='The saved investigation could not be opened. Reload this page to try again. No new payment or AI request was made.';
function element(){return {textContent:'',hidden:false,checked:false,dataset:{},handlers:{},children:[],append(...items){this.children.push(...items);},replaceChildren(...items){this.children=items;},classList:{add(){},remove(){},toggle(){},contains(){return false;}},addEventListener(type,fn){this.handlers[type]=fn;},setAttribute(name,value){this[name]=value;},focus(){},scrollIntoView(){}};}
async function load(fetchResult){
 const nodes=new Map();const byId=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};byId('review').hidden=true;byId('ai-story-panel').hidden=true;byId('ai-unavailable').hidden=false;
 const stories=['payment','delivery','repair'].map(stage=>({...element(),dataset:{story:stage}}));
 const cases=['defective','healthy'].map(variant=>({...element(),dataset:{case:variant}}));
 const aiSteps=[0,1,2].map(i=>({...element(),dataset:{aiStep:String(i)}}));
 const links=[element(),element()];
 const calls=[];const document={getElementById:byId,documentElement:element(),querySelector:()=>element(),querySelectorAll:selector=>selector==='button[data-story]'?stories:selector==='[data-case]'?cases:selector==='a[href="#investigation"]'?links:selector==='[data-ai-step]'?aiSteps:[],createElement:()=>element()};
 const context=vm.createContext({document,window:{location:{hash:''},matchMedia:()=>({matches:false,addEventListener(){}})},fetch:async(...args)=>{calls.push(args);return fetchResult();}});
 vm.runInContext(source,context,{filename:'web/judge/app.js'});
 await new Promise(setImmediate);
 return {nodes,stories,cases,aiSteps,calls,links};
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

const historySource=JSON.parse(fs.readFileSync(path.join(__dirname,'../evidence/runs/submission-ready/ai-historical-summary.json'),'utf8'));
function history(){return {...structuredClone(historySource),mode:'RECORDED_AI_INVESTIGATION',fresh_execution:false};}
function reviewData(recordedHistory){
 const payment='2026-10-22T09:31:52Z';
 const variant=healthy=>({receipt:{signature:healthy?'ticket_delivered_once_on_time':'paid_without_ticket',ticket_count:healthy?1:0},purchase:{capture_completed_at:payment},merchant:{tickets:healthy?[{created_at:'2026-10-22T09:32:24.261423Z'}]:[]},execution:{deadline:'2026-10-22T09:32:52Z'},events:[]});
 return {mode:'RECORDED_REPLAY',fresh_execution:false,computed_when:'app launch',computed_at:payment,cases:{healthy:variant(true),defective:variant(false)},historical_ai:recordedHistory};
}
test('recorded AI stages expose the actual knowledge progression without mutating the case',async()=>{
 const h=history(),before=JSON.stringify(h);
 const page=await load(()=>new Response(JSON.stringify(reviewData(h)),{status:200}));
 assert.equal(page.nodes.get('review').hidden,false);assert.equal(page.nodes.get('ai-story-panel').hidden,false);
 assert.equal(page.nodes.get('ai-unavailable').hidden,true);
 assert.match(page.nodes.get('ai-known').textContent,/No payment or ticket observations/);
 page.aiSteps[1].handlers.click();assert.match(page.nodes.get('ai-known').textContent,/PayPal had confirmed/);
 assert.equal(page.nodes.get('ai-reasoning').textContent,h.trace[1].exact_model_excerpt);
 page.aiSteps[2].handlers.click();assert.match(page.nodes.get('ai-takeaway').textContent,/3.42 seconds/);
 assert.equal(JSON.stringify(h),before);assert.equal(page.calls.length,1,'story selections must not call a model or provider');
});
for(const change of ['missing','fresh','same-case','wrong-tools','missing-payment-read','invented-time'])test('unusable optional AI history leaves the recorded checkout working: '+change,async()=>{
 let h=history();if(change==='missing')h=null;if(change==='fresh')h.fresh_execution=true;if(change==='same-case')h.same_case_as_public_faulty_replay=true;if(change==='wrong-tools')h.trace[1].action='capture_payment';if(change==='missing-payment-read')h.actual_operations.paypal_existing_order_gets=0;if(change==='invented-time')h.deterministic_result.delivery_latency_seconds=null;
 const page=await load(()=>new Response(JSON.stringify(reviewData(h)),{status:200}));
 assert.equal(page.nodes.get('review').hidden,false,'the checkout comparison remains usable');
 assert.equal(page.nodes.get('ai-story-panel').hidden,true,'no unsupported AI story appears');
 assert.equal(page.nodes.get('ai-unavailable').hidden,false);
 for(const button of page.aiSteps)assert.doesNotThrow(()=>button.handlers.click());
 assert.equal(page.calls.length,1);
});
