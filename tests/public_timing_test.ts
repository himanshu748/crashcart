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
