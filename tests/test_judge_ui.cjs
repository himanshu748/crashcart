/* Delivered recorded-page behavior; local replay fixtures, never providers. */
const {test,before}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs'),path=require('node:path');
const {ROOT,loadJudge,response}=require('./helpers/ui_vm.cjs');
// Exercise the validator against actual canonical replay output. Generated IDs
// intentionally differ between the two imports. No live adapters or env loader.
const {loadFixture}=require('./helpers/replay_fixture.cjs');
let genuine;
before(async()=>{genuine=await loadFixture();});
const historySource=JSON.parse(fs.readFileSync(path.join(ROOT,'evidence/runs/submission-ready/ai-historical-summary.json'),'utf8'));
const history=()=>({...structuredClone(historySource),mode:'RECORDED_AI_INVESTIGATION',fresh_execution:false});
const reviewData=(h=undefined)=>{const d=structuredClone(genuine);if(h!==undefined)d.historical_ai=h;return d;};
async function expectRecoverableFailure(fetcher){const p=await loadJudge(fetcher);assert.match(p.nodes.get('load-state').textContent,/couldn’t open.*saved records/i);assert.match(p.nodes.get('load-state').textContent,/No payment or AI request was made/);assert.equal(p.nodes.get('load-state').hidden,false);assert.equal(p.nodes.get('review').hidden,true);assert.ok(p.links.every(link=>link.href==='#load-state'));for(const button of [...p.stories,...p.cases])await assert.doesNotReject(button.trigger('click'));assert.equal(p.calls.length,1);assert.equal(p.calls[0][0],'data.json');}
test('Unavailable response explains recovery without provider claims',()=>expectRecoverableFailure(()=>new Response('<html>unavailable</html>',{status:503})));
test('Malformed JSON does not expose parser jargon',()=>expectRecoverableFailure(()=>new Response('{',{status:200})));
test('Disconnected network leaves a safe usable state',()=>expectRecoverableFailure(()=>{throw TypeError('Failed to fetch');}));
test('Invalid comparison never displays successful results',()=>expectRecoverableFailure(()=>response({mode:'LOCAL_TEST',fresh_execution:true})));
test('Partially parsed case is discarded before walkthrough reuse',()=>expectRecoverableFailure(()=>response({mode:'RECORDED_REPLAY',fresh_execution:false,cases:{defective:{receipt:{signature:'paid_without_ticket'}},healthy:{receipt:{signature:'ticket_delivered_once_on_time'}}}})));
test('actual canonical replay accepts both genuine outcomes despite generated identity differences',async()=>{const p=await loadJudge(()=>response(genuine));assert.equal(p.ui.validReview(genuine),true);assert.notEqual(genuine.cases.defective.purchase.run_id,genuine.cases.healthy.purchase.run_id);assert.notEqual(genuine.cases.defective.purchase.order_id,genuine.cases.healthy.purchase.order_id);assert.equal(p.nodes.get('review').hidden,false);assert.equal(p.nodes.get('defective-count').textContent,'0');assert.equal(p.nodes.get('healthy-count').textContent,'1');assert.match(p.nodes.get('facts').textContent,/USD 29\.00 confirmed/);assert.doesNotMatch(p.nodes.get('facts').textContent,/2900\.00/);await p.cases[1].trigger('click');assert.match(p.nodes.get('download-case').href,/healthy\.json$/);assert.equal(p.calls.length,1);});
for(const change of ['canonical-input','promise','missing-network','receipt-network','receipt-fresh','receipt-mode','execution-network','deadline','ticket-purchase','merchant-run','merchant-order','receipt-purchase','source-map','verdict-source','event-run','missing-timezone'])test('reject changed/uncorrelated replay: '+change,async()=>{const d=reviewData(),h=d.cases.healthy;if(change==='canonical-input')h.receipt.input_sha256='f'.repeat(64);if(change==='promise')d.invariant.recovery_seconds=900;if(change==='missing-network')delete d.network_calls;if(change==='receipt-network')h.receipt.network_calls=1;if(change==='receipt-fresh')h.receipt.fresh_execution=true;if(change==='receipt-mode')h.receipt.mode='LOCAL_TEST';if(change==='execution-network')h.execution.network_calls=1;if(change==='deadline')h.execution.deadline=new Date(Date.parse(h.purchase.capture_completed_at)+900000).toISOString();if(change==='ticket-purchase')delete h.merchant.tickets[0].purchase_id;if(change==='merchant-run')h.merchant.run_id='foreign';if(change==='merchant-order')h.merchant.order_id='foreign';if(change==='receipt-purchase')h.receipt.purchase_id='foreign';if(change==='source-map')h.receipt.identity_mapping[d.recorded_source.order_id]='foreign';if(change==='verdict-source')h.events.find(e=>e.event_type==='invariant_result').payload.source_ids.order_id='foreign';if(change==='event-run')h.events[0].run_id='foreign';if(change==='missing-timezone')h.purchase.capture_completed_at=h.purchase.capture_completed_at.replace(/Z$/,'');await expectRecoverableFailure(()=>response(d));});
test('recorded AI knowledge progression preserves original data and never calls providers',async()=>{const h=history(),before=JSON.stringify(h),p=await loadJudge(()=>response(reviewData(h)));assert.equal(p.nodes.get('review').hidden,false);assert.equal(p.nodes.get('ai-story-panel').hidden,false);assert.equal(p.nodes.get('ai-unavailable').hidden,true);assert.match(p.nodes.get('ai-known').textContent,/No payment or ticket records/);await p.aiSteps[1].trigger('click');assert.match(p.nodes.get('ai-known').textContent,/PayPal had confirmed/);assert.equal(p.nodes.get('ai-reasoning').textContent,h.trace[1].exact_model_excerpt);await p.aiSteps[2].trigger('click');assert.match(p.nodes.get('ai-takeaway').textContent,/3\.42 seconds/);assert.equal(JSON.stringify(h),before);assert.equal(p.calls.length,1);});
for(const change of ['missing','fresh','same-case','wrong-tools','missing-payment-read','invented-time'])test('invalid optional AI history leaves checkout working: '+change,async()=>{let h=history();if(change==='missing')h=null;if(change==='fresh')h.fresh_execution=true;if(change==='same-case')h.same_case_as_public_faulty_replay=true;if(change==='wrong-tools')h.trace[1].action='capture_payment';if(change==='missing-payment-read')h.actual_operations.paypal_existing_order_gets=0;if(change==='invented-time')h.deterministic_result.delivery_latency_seconds=null;const p=await loadJudge(()=>response(reviewData(h)));assert.equal(p.nodes.get('review').hidden,false);assert.equal(p.nodes.get('ai-story-panel').hidden,true);assert.equal(p.nodes.get('ai-unavailable').hidden,false);for(const button of p.aiSteps)await assert.doesNotReject(button.trigger('click'));assert.equal(p.calls.length,1);});

test('recorded page shares the public site motion preference across page loads',async()=>{const saved=new Map([['crashcart-reduce-motion','1']]);const storage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value)};const first=await loadJudge(()=>response(genuine),{storage});assert.equal(first.nodes.get('reduce-motion').checked,true);assert.equal(first.document.documentElement.classList.contains('reduce-motion'),true);first.nodes.get('reduce-motion').checked=false;await first.nodes.get('reduce-motion').trigger('change');assert.equal(saved.get('crashcart-reduce-motion'),'0');assert.equal(first.document.documentElement.classList.contains('reduce-motion'),false);const second=await loadJudge(()=>response(genuine),{storage});assert.equal(second.nodes.get('reduce-motion').checked,false);assert.equal(first.calls.length,1);assert.equal(second.calls.length,1);});
test('blocked preference storage leaves the recorded page and its motion control usable',async()=>{const storage={getItem(){throw Error('storage blocked');},setItem(){throw Error('storage blocked');}};const p=await loadJudge(()=>response(genuine),{storage});assert.equal(p.nodes.get('review').hidden,false);p.nodes.get('reduce-motion').checked=true;await assert.doesNotReject(p.nodes.get('reduce-motion').trigger('change'));assert.equal(p.document.documentElement.classList.contains('reduce-motion'),true);assert.equal(p.calls.length,1);});


test('repair story selects the repaired result on the first activation and remains repeatable', async()=>{
  const p=await loadJudge(()=>response(genuine));
  await p.stories[2].trigger('click');
  assert.equal(p.stories[2].getAttribute('aria-pressed'),'true');
  assert.match(p.nodes.get('selected-name').textContent,/Recovered order/);
  assert.match(p.nodes.get('facts').textContent,/1 ticket/);
  assert.match(p.nodes.get('facts').textContent,/Kept/);
  assert.match(p.nodes.get('story-description').textContent,/32\.26 seconds/);
  await p.stories[2].trigger('click');
  assert.match(p.nodes.get('facts').textContent,/1 ticket/);
  await p.stories[1].trigger('click');
  assert.match(p.nodes.get('selected-name').textContent,/Missed order/);
  assert.match(p.nodes.get('facts').textContent,/0 tickets/);
  assert.equal(p.calls.length,1);
});

test('See what happened focuses without an instant jump and scrolls to the result, respecting motion preference',async()=>{
  const p=await loadJudge(()=>response(genuine));
  const button=p.cases[1]; button.classList.add('select-case');
  await button.trigger('click');
  assert.equal(p.document.activeElement,p.nodes.get('evidence-title'));
  assert.equal(p.nodes.get('evidence-title').focusOptions.preventScroll,true);
  assert.equal(p.nodes.get('evidence').scrollOptions.block,'start');
  assert.equal(p.nodes.get('evidence').scrollOptions.behavior,'smooth');
  p.nodes.get('reduce-motion').checked=true;
  await p.nodes.get('reduce-motion').trigger('change');
  await button.trigger('click');
  assert.equal(p.nodes.get('evidence').scrollOptions.behavior,'auto');
  assert.equal(p.calls.length,1);
});

test('8 November failure investigation is shown first with cited evidence and no fresh call', async()=>{
  const p=await loadJudge(()=>response(genuine));
  assert.equal(p.nodes.get('failure-ai-panel').hidden,false);
  assert.equal(p.nodes.get('failure-ai-unavailable').hidden,true);
  await p.failureSteps[1].trigger('click');
  assert.match(p.nodes.get('failure-answer').textContent,/PayPal confirmed/);
  await p.failureSteps[2].trigger('click');
  assert.match(p.nodes.get('failure-verdict').textContent,/FAIL \/ paid_without_ticket/);
  for(const id of genuine.failure_ai.trace[2].findings.flatMap(f=>f.evidence_ids)) assert.match(p.nodes.get('failure-citations').textContent,new RegExp(id));
  assert.equal(p.calls.length,1);
});
test('invalid failure trace leaves the recorded comparison usable and hides its panel',async()=>{
  const data=structuredClone(genuine); data.failure_ai.trace[1].action='capture_payment';
  const p=await loadJudge(()=>response(data));
  assert.equal(p.nodes.get('failure-ai-panel').hidden,true);
  assert.equal(p.nodes.get('review').hidden,false);
  assert.equal(p.calls.length,1);
});

/* Workspace routing is exercised against the actual delivered HTML controls and
   their ancestry. This remains a synthetic DOM test, not keyboard/browser proof. */
function assertView(page,view){
  assert.equal(page.nodes.get('failure-case').hidden,view!=='failure');
  assert.equal(page.nodes.get('comparison-case').hidden,view!=='comparison');
  assert.equal(page.nodes.get('workspace-failure-button').getAttribute('aria-pressed'),String(view==='failure'));
  assert.equal(page.nodes.get('workspace-comparison-button').getAttribute('aria-pressed'),String(view==='comparison'));
}

test('workspace opens on the actual November investigation without borrowing October purchase facts',async()=>{
  const data=reviewData(),before=JSON.stringify(data),p=await loadJudge(()=>response(data));
  assertView(p,'failure');
  assert.equal(p.nodes.get('workspace-failure-button').disabled,false);
  assert.equal(p.nodes.get('workspace-comparison-button').disabled,false);
  assert.match(p.nodes.get('workspace-case-date').textContent,/8 November 2026/);
  assert.equal(p.nodes.get('workspace-payment-state').textContent,'Confirmed');
  assert.doesNotMatch(p.nodes.get('workspace-payment-state').textContent,/USD|29\.00/);
  const format=timestamp=>new Date(timestamp).toLocaleString(undefined,{dateStyle:'medium',timeStyle:'medium',timeZone:'UTC'})+' UTC';
  assert.equal(p.nodes.get('workspace-payment-time').textContent,format(data.failure_ai.payment_completed_at));
  assert.notEqual(p.nodes.get('workspace-payment-time').textContent,format(data.cases.defective.purchase.capture_completed_at));
  assert.equal(p.nodes.get('workspace-ticket-count').textContent,'0 tickets');
  assert.equal(p.nodes.get('workspace-promise').textContent,'60-second promise');
  assert.equal(p.nodes.get('workspace-deadline').textContent,'Missed · due '+format(data.failure_ai.deterministic_result.deadline));
  assert.equal(JSON.stringify(data),before,'Presentation must not mutate recorded input');
  assert.equal(p.calls.length,1);assert.equal(p.calls[0][0],'data.json');
});

test('workspace case controls are actual semantic buttons linked to distinct delivered panes',async()=>{
  const p=await loadJudge(()=>response(genuine));
  const controls=p.document.querySelectorAll('[data-workspace-view]');
  assert.equal(controls.length,2);
  for(const control of controls){
    assert.equal(control.tagName,'BUTTON');assert.equal(control.getAttribute('type'),'button');
    const pane=p.nodes.get(control.getAttribute('aria-controls'));
    assert.ok(pane);assert.equal(pane.dataset.workspacePane,control.dataset.workspaceView);
    control.focus();assert.equal(p.document.activeElement,control);
  }
  assert.equal(p.nodes.get('failure-question').closest('[data-workspace-pane]'),p.nodes.get('failure-case'));
  assert.equal(p.nodes.get('facts').closest('[data-workspace-pane]'),p.nodes.get('comparison-case'));
});

test('saved next-step journey leads to a separately labelled October repair, then preserves November state',async()=>{
  const p=await loadJudge(()=>response(genuine)),next=p.nodes.get('workspace-next-step');
  assert.equal(p.nodes.get('workspace-step-label').textContent,'Recorded step 1 of 3');
  assert.equal(p.nodes.get('workspace-evidence-count').textContent,'No records read yet');
  await next.trigger('click');
  assert.equal(p.nodes.get('workspace-step-label').textContent,'Recorded step 2 of 3');
  assert.equal(p.nodes.get('workspace-evidence-count').textContent,'1 supporting record');
  await next.trigger('click');
  assert.equal(p.nodes.get('workspace-step-label').textContent,'Recorded step 3 of 3');
  assert.equal(p.nodes.get('workspace-evidence-count').textContent,'2 supporting records');
  assert.match(p.nodes.get('workspace-next-note').textContent,/different recorded order.*22 October/);
  await next.trigger('click');
  assertView(p,'comparison');assert.match(p.nodes.get('workspace-case-date').textContent,/22 October 2026/);
  assert.equal(p.document.activeElement,p.nodes.get('evidence-title'));
  assert.equal(p.nodes.get('evidence-title').focusOptions.preventScroll,true);
  assert.equal(p.nodes.get('comparison-case').scrollOptions.block,'start');
  assert.equal(p.nodes.get('comparison-case').scrollOptions.behavior,'smooth');
  assert.match(p.nodes.get('selected-name').textContent,/Recovered order/);
  assert.match(p.nodes.get('facts').textContent,/1 ticket/);
  assert.match(p.nodes.get('story-description').textContent,/32\.26 seconds/);
  assert.match(p.nodes.get('comparison-case').textContent,/Different order/);
  await p.nodes.get('workspace-failure-button').trigger('click');
  assertView(p,'failure');assert.equal(p.nodes.get('workspace-ticket-count').textContent,'0 tickets');
  assert.match(p.nodes.get('failure-verdict').textContent,/FAIL \/ paid_without_ticket/);
  await p.failureSteps[0].trigger('click');
  assert.equal(p.nodes.get('workspace-step-label').textContent,'Recorded step 1 of 3');
  assert.equal(p.calls.length,1,'Navigation and replay selection must not fetch or call providers');
});

for(const change of ['missing','missing-payment','payment-no-timezone','missing-deadline','deadline-no-timezone','non-60s-interval','invariant-version','invalid-trace'])test('workspace falls back safely when optional November projection is unavailable: '+change,async()=>{
  const data=reviewData();
  if(change==='missing')delete data.failure_ai;
  if(change==='missing-payment')delete data.failure_ai.payment_completed_at;
  if(change==='payment-no-timezone')data.failure_ai.payment_completed_at=data.failure_ai.payment_completed_at.replace(/Z$/,'');
  if(change==='missing-deadline')delete data.failure_ai.deterministic_result.deadline;
  if(change==='deadline-no-timezone')data.failure_ai.deterministic_result.deadline=data.failure_ai.deterministic_result.deadline.replace(/Z$/,'');
  if(change==='non-60s-interval')data.failure_ai.deterministic_result.deadline=new Date(Date.parse(data.failure_ai.payment_completed_at)+61000).toISOString();
  if(change==='invariant-version')data.failure_ai.deterministic_result.invariant_version='ticket-v2';
  if(change==='invalid-trace')data.failure_ai.trace[1].action='capture_payment';
  const p=await loadJudge(()=>response(data));
  assert.equal(p.nodes.get('review').hidden,false);assertView(p,'comparison');
  assert.equal(p.nodes.get('workspace-failure-button').disabled,true);
  assert.equal(p.nodes.get('workspace-comparison-button').disabled,false);
  assert.equal(p.nodes.get('workspace-notice').hidden,false);
  assert.match(p.nodes.get('workspace-notice').textContent,/saved AI case is unavailable.*recorded repair/);
  await p.nodes.get('workspace-failure-button').trigger('click');assertView(p,'comparison');
  await p.cases[1].trigger('click');assert.match(p.nodes.get('facts').textContent,/1 ticket/);
  assert.equal(p.calls.length,1);
});

for(const anchor of ['investigation','evidence','timeline','technical-result'])test('legacy comparison deep link reveals its pane before scrolling: #'+anchor,async()=>{
  const p=await loadJudge(()=>response(genuine),{url:'https://example.test/project/demo.html#'+anchor});
  assertView(p,'comparison');
  const target=p.nodes.get(anchor);
  assert.equal(target.scrollOptions.block,'start');assert.equal(target.scrollOptions.behavior,'auto');
  for(let parent=target.parentElement;parent;parent=parent.parentElement){if(parent.tagName==='DETAILS')assert.equal(parent.open,true);}
  assert.equal(p.calls.length,1);
});

test('November deep link selects the saved investigation and later hash changes reveal comparison details',async()=>{
  const p=await loadJudge(()=>response(genuine),{url:'https://example.test/project/demo.html#failure-ai-title'});
  assertView(p,'failure');assert.equal(p.nodes.get('failure-ai-title').scrollOptions.block,'start');
  p.context.window.location.hash='#timeline';await p.dispatchWindow('hashchange');
  assertView(p,'comparison');
  assert.equal(p.document.querySelector('.order-records').open,true);
  assert.equal(p.nodes.get('timeline').scrollOptions.block,'start');
  p.context.window.location.hash='#failure-citations';await p.dispatchWindow('hashchange');
  assertView(p,'failure');
  assert.equal(p.nodes.get('failure-citations').closest('details').open,true);
  assert.equal(p.nodes.get('failure-citations').scrollOptions.block,'start');
  assert.equal(p.calls.length,1);
});

for(const anchor of ['faq','downloads','ai-title'])test('secondary deep link opens enclosing disclosures: #'+anchor,async()=>{
  const p=await loadJudge(()=>response(genuine),{url:'https://example.test/project/demo.html#'+anchor});
  const target=p.nodes.get(anchor);
  assert.equal(target.scrollOptions.block,'start');
  let disclosures=0;for(let parent=target.parentElement;parent;parent=parent.parentElement){if(parent.tagName==='DETAILS'){disclosures++;assert.equal(parent.open,true);}}
  assert.ok(disclosures>0,'The target must really be inside a delivered disclosure');
  assert.equal(p.calls.length,1);
});

test('unavailable November deep link leaves the valid comparison visible instead of scrolling into a hidden case',async()=>{
  const data=reviewData();delete data.failure_ai;
  const p=await loadJudge(()=>response(data),{url:'https://example.test/project/demo.html#failure-ai-title'});
  assertView(p,'comparison');assert.equal(p.nodes.get('workspace-notice').hidden,false);
  assert.equal(p.nodes.get('failure-ai-title').scrollOptions,undefined);
  assert.equal(p.calls.length,1);
});

test('failed records do not enable workspace controls or allow a saved next step',async()=>{
  const p=await loadJudge(()=>response({mode:'LOCAL_TEST',fresh_execution:true}));
  assert.equal(p.nodes.get('review').hidden,true);
  assert.equal(p.nodes.get('workspace-failure-button').disabled,true);
  assert.equal(p.nodes.get('workspace-comparison-button').disabled,true);
  await p.nodes.get('workspace-next-step').trigger('click');
  for(const control of p.document.querySelectorAll('[data-workspace-view]'))await control.trigger('click');
  assert.equal(p.nodes.get('review').hidden,true);assert.equal(p.calls.length,1);
});
