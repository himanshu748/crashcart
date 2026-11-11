import test from 'node:test';
import assert from 'node:assert/strict';
import {spawnSync} from 'node:child_process';
import {publicTimingRows} from '../studio/src/public-timing-model';
const p=spawnSync(process.env.PYTHON??'python3',['-c','from crashcart.judge import prepare_review; import sys; sys.stdout.buffer.write(prepare_review()["data.json"][1])'],{cwd:'..',encoding:'utf8'});
assert.equal(p.status,0,p.stderr);const original=JSON.parse(p.stdout);
const copy=()=>structuredClone(original);
test('actual keyless replay projects zero tickets and one inside the unchanged minute',()=>{
 const rows=publicTimingRows(original);assert.deepEqual(rows.map(r=>[r.verdict,r.ticketCount]),[['FAIL',0],['PASS',1]]);
 assert.equal(rows[1].ticketOffsetsMs[0],32261.423);assert.equal(rows[1].ticketTimes[0],original.cases.healthy.merchant.tickets[0].created_at);
});
test('rejects non-recorded and network-enabled input',()=>{for(const [k,v] of [['mode','LIVE_SANDBOX'],['fresh_execution',true],['network_calls',1]]){const d=copy();d[k]=v;assert.throws(()=>publicTimingRows(d));}});
test('rejects a changed sixty-second promise',()=>{const d=copy();d.invariant.recovery_seconds=61;assert.throws(()=>publicTimingRows(d));});
test('rejects mismatched saved outcomes rather than correcting them',()=>{const d=copy();d.cases.healthy.receipt.ticket_count=0;assert.throws(()=>publicTimingRows(d));});
test('rejects a foreign purchase',()=>{const d=copy();d.cases.healthy.merchant.purchase_id=d.cases.defective.purchase.id;assert.throws(()=>publicTimingRows(d));});
test('rejects a forged saved checker result',()=>{const d=copy();d.cases.healthy.events.find((e:any)=>e.event_type==='invariant_result').payload.verdict='FAIL';assert.throws(()=>publicTimingRows(d));});
test('rejects delivery outside the saved observation',()=>{const d=copy();d.cases.healthy.merchant.tickets[0].created_at='2026-10-23T00:00:00Z';assert.throws(()=>publicTimingRows(d));});
test('preserves input and recorded timing precision',()=>{const before=JSON.stringify(original);publicTimingRows(original);assert.equal(JSON.stringify(original),before);});

// Synthetic adapter fixtures only; never appended to deployed records.
import {liveTimingRows} from '../studio/src/public-timing-model';
const liveCase = () => ({run_id:'run_'+'1'.repeat(32),reference:'Sandbox checkout 1',
 payment_completed_at:'2026-11-11T12:00:00.123456Z',deadline:'2026-11-11T12:01:00.123456Z',
 ticket_created_at:null as string|null,ticket_count:0,verdict:null as any,state:'WAITING_FOR_PROMISE',webhook_verified:true});
const live = (c=liveCase()) => ({mode:'LIVE_SANDBOX',cases:[c]});
test('live projection caps the observed missing gap without computing a verdict or leaking payer fields',()=>{
 const input={...live(),payer:{email:'private@example.invalid'}};
 const [early]=liveTimingRows(input,Date.parse('2026-11-11T12:00:10Z'));
 assert.equal(early.modeLabel,'LIVE SANDBOX');assert.equal(early.verdict,null);assert.equal(early.missingPaidCase,true);
 assert(Math.abs(early.gapOffsetMs-9876.544)<0.001);assert.equal('payer' in early,false);
 const [late]=liveTimingRows(input,Date.parse('2026-11-11T12:02:00Z'));assert.equal(late.gapOffsetMs,60000);assert.equal(late.verdict,null);
 assert.equal(liveTimingRows({mode:'LIVE_SANDBOX',cases:[]}).length,0);
});
test('live projection retains real ticket time and deterministic verdict',()=>{
 const c=liveCase();c.ticket_count=1;c.ticket_created_at='2026-11-11T12:00:32.384879Z';
 c.verdict={verdict:'PASS',signature:'ticket_delivered_once_on_time',reason:'Exactly one ticket delivered.'};c.state='COMPLETED';
 const [row]=liveTimingRows(live(c));assert.equal(row.ticketOffsetsMs[0],32261.423);assert.equal(row.verdict,'PASS');assert.equal(row.missingPaidCase,false);
});
test('unpaid live cases stay in the list without invented chart times',()=>{
 const c=liveCase();Object.assign(c,{payment_completed_at:null,deadline:null,state:'AWAITING_APPROVAL',webhook_verified:false});
 const [row]=liveTimingRows(live(c));assert.equal(row.timingAvailable,false);assert.equal(row.paymentAt,null);assert.equal(row.gapOffsetMs,0);assert.equal(row.verdict,null);
});
test('live projection rejects invalid IDs, UTC, changed deadlines, counts and unsafe costs',()=>{
 for(const patch of [{run_id:'../other'},{deadline:'2026-11-11T12:01:01.123456Z'},
  {payment_completed_at:'2026-02-30T12:00:00Z'},{payment_completed_at:'2026-11-11T12:00:00-01:00'},
  {ticket_count:1},{ticket_created_at:'2026-11-11T12:00:20Z'},{model_cost_usd:Infinity},{cost_usd:-1},
  {webhook_verified:'yes'},{state:'invented'},{reference:'bad\nreference'}]){
   assert.throws(()=>liveTimingRows(live({...liveCase(),...patch} as any)));
 }
 assert.throws(()=>liveTimingRows({...live(),mode:'RECORDED_REPLAY'}));
 assert.throws(()=>liveTimingRows({mode:'LIVE_SANDBOX',cases:[liveCase(),liveCase()]}));
 assert.throws(()=>liveTimingRows(live(),Infinity));
});
