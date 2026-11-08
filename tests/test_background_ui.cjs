const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/app.js'),'utf8');
const start=source.indexOf('function investigationJobMessage(');
const end=source.indexOf('\nfunction renderInvestigationJob(',start);
const context=vm.createContext({});vm.runInContext(source.slice(start,end),context);
test('queued and running never claim finished analysis or successful delivery',()=>{
 for(const state of ['PENDING','RUNNING']){
  const text=context.investigationJobMessage({state});
  assert.match(text,/leave this page/);assert.doesNotMatch(text,/finished|payment confirmed|ticket delivered/i);
 }
});
test('failed, cancelled and missing final results retain uncertainty',()=>{
 assert.match(context.investigationJobMessage({state:'FAILED'}),/could not finish/);
 assert.match(context.investigationJobMessage({state:'CANCELLED'}),/stopped/);
 assert.match(context.investigationJobMessage({state:'COMPLETED',result:{}}),/unavailable/);
 assert.equal(context.investigationJobMessage(null),'');
});
test('local simulated analysis stays labelled and never decides payment',()=>{
 const text=context.investigationJobMessage({state:'COMPLETED',result:{status:'COMPLETED',model_mode:'LOCAL_TEST'}});
 assert.match(text,/simulated assistant/);assert.match(text,/records decide the delivery result/);
 assert.doesNotMatch(context.investigationJobMessage({state:'COMPLETED',result:{status:'COMPLETED',model_mode:'LIVE_MODEL'}}),/simulated/);
});
for(const alreadyFinished of [false,true])test('background lifecycle never leaves a stale queue acknowledgement: '+alreadyFinished,async()=>{
 const handler=source.split('\n').find(line=>line.startsWith("$('investigate').addEventListener"));
 let click,main='',note='',state=alreadyFinished?'COMPLETED':'PENDING';
 const c=vm.createContext({selected:'owned-test-case',$:()=>({addEventListener:(_event,fn)=>{click=fn;}}),action:fn=>fn(),api:async()=>({job:{state:'PENDING'}}),refresh:async()=>{note=state==='COMPLETED'?'Assistant finished':'Assistant queued';},text:(_id,value)=>{main=value;},investigationJobMessage:job=>job.state==='PENDING'?'Assistant queued':'Assistant finished'});
 vm.runInContext(handler,c);await click();
 state='COMPLETED';await c.refresh();
 assert.equal(note,'Assistant finished');assert.notEqual(main,'Assistant queued','an older202 acknowledgement must not override the current persisted job state');
});

for(const mismatch of [null,'run_id','purchase_id','order_id'])test('finding is presented only for the selected case: '+mismatch,()=>{
 const c=vm.createContext({verdictReasons:new Map([['paid_without_ticket','Payment received without a ticket']])});
 const end=source.indexOf('\nfunction renderInvestigationJob(');vm.runInContext(source.slice(source.indexOf('function investigationFinding('),end),c);
 const run={id:'run-owned'},purchase={id:'purchase-owned',order_id:'ORDEROWNED'};
 const ids={run_id:run.id,purchase_id:purchase.id,order_id:purchase.order_id};if(mismatch)ids[mismatch]='foreign';
 const job={result:{status:'COMPLETED',final_verdict:{verdict:'FAIL',signature:'paid_without_ticket',source_ids:ids}}};
 const finding=c.investigationFinding(job,run,purchase);
 if(mismatch)assert.equal(finding,'');else assert.match(finding,/Investigation finding: Payment received without a ticket/);
 assert.equal(purchase.id,'purchase-owned');assert.equal(purchase.payment_confirmed,undefined,'finding must not mutate merchant payment state');
});
