const $ = (id) => document.getElementById(id);
let selected = new URLSearchParams(location.search).get('run');
let landingView = location.pathname === '/' && new URLSearchParams(location.search).get('view') === 'home';
document.querySelector(landingView ? '.nav-home' : '.nav-desk')?.setAttribute('aria-current','page');
const testType = mode => new Map([['LIVE_SANDBOX','Initial test checkout'],['FRESH_SANDBOX','Repair verification · new test checkout'],['RECORDED_REPLAY','Replay of a saved checkout'],['LOCAL_TEST','Example data · no payment']]).get(mode) || 'Unknown test type';
const faultLabel = kind => new Map([['none','No fault introduced'],['response_loss','Lost payment response'],['event_delay','Delayed delivery'],['event_duplicate','Repeated delivery event'],['process_interrupt','Interrupted store process']]).get(kind) || 'Unknown fault';
const statusLabel = value => new Map([['created','Ready to start'],['running','In progress'],['awaiting_approval','Waiting for approval'],['completed','Completed'],['failed','Needs attention'],['cancelled','Stopped'],['inconclusive','More evidence needed'],['blocked','Needs setup'],['pending','Waiting'],['unresolved','Not yet confirmed'],['delivered','Ticket delivered'],['not_delivered','No ticket delivered'],['missing_purchase','Purchase not found'],['not_started','Not started'],['needs_input','More information needed'],['budget_exhausted','Investigation limit reached'],['awaiting_payment','Waiting for payment']]).get(String(value).toLowerCase()) || 'Status not available';
const sourceLabel = value => new Map([['browser','Browser'],['provider','PayPal'],['merchant','Store'],['checker','Delivery check'],['investigator','Assistant'],['operator','Workspace'],['model','Assistant'],['system','Workspace'],['worker','Delivery service'],['harness','Test controls']]).get(value) || 'Other activity';
// Only known generated example titles receive copy changes. User-authored text is preserved.
const generatedTitles = new Map([
  ['LOCAL_TEST A: USD29 buys one ticket within60seconds of completed payment.','One ticket within 60 seconds of a completed USD 29 payment.'],
  ['LOCAL_TEST B: isolated approval wait; USD29 buys one ticket within60seconds of completed payment.','Waiting for buyer approval: one ticket within 60 seconds of a completed USD 29 payment.'],
  ['Fresh repair verification: recover a lost capture response and issue exactly one ticket.','Check the repair: recover a lost payment response and issue exactly one ticket.'],
  ['Lost capture response: payment completed but the workshop ticket is missing.','Lost payment response: payment completed but the workshop ticket is missing.'],
  ['Recover a real sandbox payment after the merchant process exits before ticket delivery, preserving exactly one ticket within 60 seconds.','Recover a test payment after the store stops before delivery, with exactly one ticket within 60 seconds.'],
  ['A completed USD 29 payment must produce exactly one workshop ticket within 60 seconds. Early independent read, then deadline verification.','A completed USD 29 payment must produce exactly one workshop ticket within 60 seconds. Check payment status, then check delivery at the deadline.'],
  ['LOCAL_TEST UI interaction: one workshop ticket within 60 seconds; unpaid fixture, no provider call.','Interface check · test data: one workshop ticket within 60 seconds; no payment made.'],
]);
const displayPromise = value => generatedTitles.get(value) ?? String(value ?? '');
function readableText(value){
  let result=String(value??'');
  for(const [pattern,replacement] of [
    [/LOCAL_TEST UI interaction/gi,'Interface check · test data'],[/LOCAL_TEST/gi,'Test data'],
    [/FRESH_SANDBOX/g,'New test checkout'],[/LIVE_SANDBOX/g,'Initial test checkout'],[/RECORDED_REPLAY/g,'Saved checkout replay'],
    [/Fresh repair verification/gi,'Check the repair'],[/capture response/gi,'payment response'],[/confirmed capture/gi,'confirmed payment'],[/capture completion/gi,'payment confirmation'],[/\bcapture\b/gi,'payment'],[/persisted/gi,'saved'],[/correlated/gi,'linked'],
    [/sandbox/gi,'test'],[/merchant process/gi,'store process'],[/merchant/gi,'store'],[/provider/gi,'payment service'],[/entitlements?/gi,'ticket'],
    [/independent read/gi,'payment status check'],[/independent retrieval/gi,'a separate payment status check'],[/fixed recovery (window|deadline)/gi,'60-second delivery deadline'],
    [/deterministic verdict/gi,'delivery result'],[/invariant/gi,'delivery promise'],[/fixture/gi,'test store'],[/reconcil(e|ed|iation)/gi,'check payment status'],
  ])result=result.replace(pattern,replacement);
  return result;
}
const eventLabels = new Map([
  ['run_created','Investigation created'],['purchase_created','Purchase saved'],['run_cancelled','Investigation stopped'],['customer_observation','Browser view recorded'],
  ['order_created','Checkout created'],['order_creation_requested','Checkout requested'],['order_unresolved','Payment status needs checking'],['independent_order_read','PayPal status checked'],
  ['capture_started','Payment confirmation started'],['capture_requested','Payment confirmation requested'],['capture_transport_response','Payment response recorded'],['capture_unresolved','Payment confirmation interrupted'],
  ['capture_confirmed','Payment confirmed'],['capture_completed','Payment completed'],['ticket_created','Ticket issued'],['ticket_issued','Ticket issued'],['merchant_observation','Ticket records checked'],
  ['invariant_result','Delivery promise checked'],['inconclusive','More evidence needed'],['fault_applied','Test interruption applied'],['response_loss','Payment response lost'],
  ['model_request','Assistant request sent'],['model_response','Assistant response received'],['model_plan','Next investigation step proposed'],['tool_observation','Investigation step recorded'],
  ['investigation_started','Investigation started'],['investigation_finished','Investigation finished'],['investigation_stopped','Investigation stopped'],['investigation_failed','Investigation could not finish'],['cancelled','Investigation stopped'],['customer_message','Checkout message recorded'],['entitlement_read','Ticket records checked'],['fault_activated','Test interruption started'],['fault_deactivated','Test interruption ended'],['pre_capture_read','Buyer approval checked'],['process_exit_boundary','Store interruption recorded'],['ticket_fulfilled','Ticket delivered'],['investigation_ended','Investigation finished'],
]);
function eventLabel(type){return eventLabels.get(type)||'Additional activity recorded';}
const verdictLabels = new Map([['PASS','Promise kept'],['FAIL','Promise broken'],['INCONCLUSIVE','More evidence needed']]);
const verdictReasons = new Map([
  ['ticket_delivered_once_on_time','Payment confirmed. Exactly one ticket arrived within 60 seconds.'],['paid_without_ticket','Payment confirmed, but no ticket arrived within 60 seconds.'],
  ['ticket_delivered_late','The ticket arrived after the 60-second deadline.'],['duplicate_tickets','More than one ticket was issued for the same payment.'],
  ['payment_amount_mismatch','The confirmed payment amount does not match the USD 29 ticket price.'],['payment_currency_mismatch','The payment was not made in the required currency, USD.'],
  ['within_recovery_window','The 60-second delivery window is still open. A missing ticket is not yet a failure.'],['stale_merchant_observation','Check the store again after the delivery deadline before deciding whether the ticket is missing.'],
  ['unconfirmed_payment','PayPal has not independently confirmed this payment.'],['payment_not_completed','PayPal does not show a completed payment.'],
  ['missing_provider_evidence','A separate payment status check is needed.'],['missing_merchant_evidence','The store purchase record is missing.'],
  ['missing_correlation_identity','Some references needed to link the payment and ticket are missing.'],['correlation_mismatch','The payment and store records refer to different purchases.'],
  ['missing_capture_identity','A reference for the confirmed payment is missing.'],['malformed_payment','The payment amount or currency is missing or unreadable.'],
  ['missing_observation_time','A payment or delivery timestamp is missing its time zone.'],['future_observation','A record has a timestamp later than this check.'],
  ['observation_precedes_payment','The available store records were checked before payment completed.'],['malformed_merchant_evidence','The ticket count and saved ticket records do not agree.'],
  ['malformed_ticket_identity','A ticket reference is missing or belongs to another purchase.'],['duplicated_ticket_observation','Repeated records of one ticket cannot prove that multiple tickets exist.'],
  ['invalid_ticket_time','The ticket’s creation time cannot be verified against the payment and store records.'],['invalid_evaluation_time','The check needs a valid time and time zone.'],
]);
function errorMessage(value){
  const raw=String(value??'');
  if(raw==='HTTP_RESPONSE_UNAVAILABLE')return 'Couldn’t load this update. Refresh the page.';
  if(/BUDGET_EXHAUSTED/.test(raw))return 'The investigation stopped at its configured limit. Saved evidence remains available.';
  if(/CRASHCART_ALLOW_SANDBOX|SANDBOX_DISABLED/i.test(raw))return 'Test payments are disabled for this workspace. Ask your workspace owner to enable them.';
  if(/PAYPAL_CLIENT|PAYPAL_NOT|PAYPAL.*CONFIGURATION/i.test(raw))return 'Test payments are not set up. Ask your workspace owner to connect the test payment account.';
  if(/OPENAI_|MODEL_USAGE_NOT_AUTHORIZED|MODEL_BUDGET|STUDIO_CALL_ALLOWANCE|MODEL_NOT_CONFIGURED/i.test(raw))return 'The assistant is not ready. Your workspace owner needs to enable model access and a usage allowance.';
  if(/MISSING_CONFIGURATION|Missing configuration/i.test(raw))return 'This service needs setup. Ask your workspace owner to connect it.';
  if(/PUBLIC_URL/i.test(raw))return 'The checkout return address is not set up. Ask your workspace owner to configure it.';
  if(/Invalid operator token/i.test(raw))return 'That access key was not accepted. Check it and try again.';
  if(/Operator access required/i.test(raw))return 'Sign in to your workspace to continue.';
  if(/Unknown run/i.test(raw))return 'This investigation could not be found. Choose another saved investigation.';
  if(/Failed to fetch|NetworkError|Load failed/i.test(raw))return 'Connection lost. Check your connection and try again.';
  if(/HTTP_|TRANSPORT_|INVALID_|MALFORMED_|MISSING_|NOT_AUTHORIZED|BUDGET_EXHAUSTED|_ERROR|Internal error|\b[A-Z]+(?:_[A-Z0-9]+)+\b/.test(raw))return 'This action could not finish. Try again, or share the error details with your workspace owner.';
  return readableText(raw||'This action could not finish. Please try again.');
}
function showError(error,target='message'){
  const raw=String(error?.message??error??'');text(target,errorMessage(raw));
  const login=target==='login-message';text(login?'login-error-code':'error-code',raw);$(login?'login-error-details':'error-details').hidden=false;
}
function investigationJobMessage(job){
  if(!job)return '';
  const prefix=job.result?.model_mode==='LOCAL_TEST'?'Example data · simulated assistant. ':'';
  if(job.state==='PENDING')return 'Assistant queued. You can leave this page and come back to its saved progress.';
  if(job.state==='RUNNING')return 'The assistant is checking this checkout in the background. You can leave this page.';
  if(job.state==='CANCELLED')return 'Assistant stopped. Saved records remain available.';
  if(job.state==='FAILED')return prefix+'The assistant could not finish. Saved records remain available. Check the assistant connection before starting a new investigation.';
  if(job.state==='COMPLETED'&&job.result?.status==='COMPLETED')return prefix+'Assistant finished. Open Activity to follow what it checked. Payment and ticket records decide the delivery result.';
  return 'Assistant status is unavailable. Saved payment and ticket records remain available.';
}
function investigationFinding(job,run,purchase){
  const result=job?.result, finding=result?.final_verdict, ids=finding?.source_ids;
  if(result?.status!=='COMPLETED'||!ids||ids.run_id!==run.id||ids.purchase_id!==purchase.id||ids.order_id!==purchase.order_id||!['PASS','FAIL','INCONCLUSIVE'].includes(finding.verdict))return '';
  const description=verdictReasons.get(finding.signature);
  return description?` Investigation finding: ${description}`:'';
}
function renderInvestigationJob(job,run,purchase){
  if(!job)return;
  text('investigator-note',investigationJobMessage(job)+investigationFinding(job,run,purchase));
  $('investigator-note').dataset.mode=job.result?.model_mode||'UNKNOWN';
  $('investigator-note').hidden=false;
}
let current = null;
let recordingKey = null;
let active = false;
let listSignature = null;
let renderSignature = null;
let refreshGeneration = 0;
let cancelPending = null;
let focusSelectedRun = false;
let timelineSource = 'all';
function selectRun(id){timelineSource='all';text('copy-status','');$('error-details').hidden=true;selected=id;history.replaceState(null,'',`/?run=${id}`);current=null;renderSignature=null;refreshGeneration++;focusSelectedRun=true;text('message','');text('investigator-note','');$('investigator-note').hidden=true;$('case').hidden=true;$('empty').hidden=false;syncActionButtons();}
async function api(path, body) {
  const res = await fetch(path, body !== undefined ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : {});
  let data;
  try { data = await res.json(); }
  catch { throw new Error('HTTP_RESPONSE_UNAVAILABLE'); }
  if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('HTTP_RESPONSE_UNAVAILABLE');
  if (!res.ok) throw new Error(data.error || 'The request could not finish.');
  return data;
}
function text(id,value){$(id).textContent=value;}
function node(tag,value,cls){const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;}
function observedTime(value){const date=new Date(value);return !value||Number.isNaN(date.getTime())?'Observation time unavailable':date.toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'short'});}
function renderTimeline(runId,events){
  const total=events.length;events=events.filter(e=>timelineSource==='all'||e.source===timelineSource);
  text('trace-count',`${events.length} of ${total} events`);
  document.querySelectorAll('.trace-filters button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.source===timelineSource)));
  const timeline=$('timeline');
  if(timeline.dataset.timelineRunId!==runId){timeline.replaceChildren();timeline.dataset.timelineRunId=runId;}
  const existing=new Map([...timeline.querySelectorAll(':scope > .event')].map(row=>[row.dataset.eventId,row]));
  if(!events.length){timeline.replaceChildren(node('p',total?'No recorded events from this source.':'No activity yet. Starting an investigation does not create a payment.','help'));return;}
  timeline.querySelector(':scope > .help')?.remove();
  for(const [index,e] of events.entries()){
    const id=String(e.id);let details=existing.get(id);
    if(!details){details=node('details','','event');details.dataset.eventId=id;const summary=node('summary','','event-head');summary.append(node('span',sourceLabel(e.source),'event-source'),node('strong',eventLabel(e.event_type)),node('time',observedTime(e.observed_at),'event-time'));summary.querySelector('time').dateTime=e.observed_at;details.append(summary,node('pre',JSON.stringify({id:e.id,run_id:e.run_id,purchase_id:e.purchase_id,order_id:e.order_id,operation_id:e.operation_id,event_time:e.event_time,observed_at:e.observed_at,caused_by:e.caused_by,payload:e.payload},null,2)));}
    if(timeline.children[index]!==details)timeline.insertBefore(details,timeline.children[index]||null);
    existing.delete(id);
  }
  for(const row of existing.values())row.remove();
}
function syncRecoveryNotice(data=current){
  if(!data||data.run.id!==selected)return;
  const message=$('message').textContent;
  if(['response_loss','process_interrupt'].includes(data.run.fault.kind)&&data.purchase.payment_confirmed===1&&data.merchant.ticket_count===1&&(!message||message==='Payment could not be confirmed. No ticket is available yet.'||message==='Connection interrupted while confirming payment. Reconnect to check the saved order.'||message.startsWith('Returned from PayPal.')))
    text('message','Payment confirmed. Recovery issued one workshop ticket.');
}
function syncActionButtons(data=current){
  const context=selected?`?run=${encodeURIComponent(selected)}`:'';
  $('studio-link').href='/studio/index.html'+context;
  $('delivery-timing-link').href='/deadlines/index.html'+context;
  $('merchant-link').href='/shop'+context;
  $('start-button').disabled=active;
  const matched=!!data&&data.run.id===selected;
  if(!matched){$('busy').hidden=!active;for(const id of ['checkout','capture','reconcile','investigate','cancel-run'])$(id).disabled=true;return;}
  const {run,purchase}=data;
  const cancelled=!!run.cancel_requested||run.state==='cancelled';
  const queued=data.investigation_job?.state==='PENDING'||data.investigation_job?.state==='RUNNING';
  const running=queued||run.execution?.active===true||(!run.execution&&String(run.state).toLowerCase()==='running');
  const unavailable=active||running||cancelled;
  $('busy').hidden=!(active||running);
  $('cancel-run').disabled=cancelled||cancelPending===run.id;
  const resumable=!!purchase.order_id&&purchase.payment_state==='AWAITING_APPROVAL'&&purchase.payment_confirmed!==1;
  text('checkout',resumable?'Resume test checkout':'Start test checkout');
  $('checkout').disabled=unavailable||purchase.payment_confirmed===1||(!!purchase.order_id&&!resumable);
  $('reconcile').disabled=unavailable||!purchase.order_id;
  $('investigate').disabled=unavailable||!!data.investigation_job;
  text('investigate',data.investigation_job?'Assistant requested':'Investigate');
  if(data.investigation_job?.state==='PENDING')text('run-state','Assistant queued');
  $('capture').disabled=unavailable||purchase.payment_confirmed===1;
}
async function action(fn){if(active)return;active=true;$('error-details').hidden=true;text('error-code','');text('message','');$('busy').hidden=false;syncActionButtons();try{await fn();}catch(e){showError(e);}finally{active=false;$('busy').hidden=true;syncRecoveryNotice();syncActionButtons();}}
async function refresh(){
  const generation=++refreshGeneration, runId=selected;
  const [prereqs,data]=await Promise.all([api('/api/prerequisites'),api('/api/runs')]);
  if(generation!==refreshGeneration||runId!==selected)return;
  $('login-panel').hidden=true;$('home-actions').hidden=!landingView;$('workspace').hidden=landingView;document.body.classList.toggle('workspace-open',!landingView);document.querySelector('.nav-desk').toggleAttribute('aria-current',!landingView);if(!landingView)document.querySelector('.nav-desk').setAttribute('aria-current','page');if(location.pathname==='/shop')document.body.classList.add('is-shop');
  $('open-workspace').href=selected?`/?run=${encodeURIComponent(selected)}`:'/';document.querySelectorAll('.brand,.footer-brand').forEach(link=>{link.href=`/?view=home${selected?'&run='+encodeURIComponent(selected):''}`;});
  document.body.classList.toggle('has-selection',!!runId);$('skip-case').hidden=!runId||landingView;text('workspace-title','Investigations');document.querySelector('.nav-home').toggleAttribute('aria-current',landingView);if(landingView)document.querySelector('.nav-home').setAttribute('aria-current','page');
  $('prerequisites').replaceChildren();
  for(const [name,p] of Object.entries(prereqs)) $('prerequisites').append(node('span',`${new Map([['paypal','Test payments'],['webhook','Payment notifications'],['model','AI assistant'],['kernel','Remote browser'],['studio','Records workspace']]).get(name)||'Additional service'} · ${p.configured?'Connection details saved':'Needs setup'}`,'integration'));
  text('run-count',`${data.runs.length} ${data.runs.length===1?'investigation':'investigations'}`);
  const signature=JSON.stringify([selected,data.runs.map(r=>[r.id,r.state,r.promise,r.mode])]);
  if(signature!==listSignature){
  listSignature=signature;
  const focusedRun=document.activeElement?.matches('.run-row')?document.activeElement.dataset.runId:null;
  $('runs').replaceChildren();
  if(!data.runs.length)$('runs').append(node('p','No saved investigations yet.','help'));
  for(const run of data.runs){const b=node('button','','run-row'+(selected===run.id?' selected':''));b.type='button';b.dataset.runId=run.id;b.title=displayPromise(run.promise);if(selected===run.id)b.setAttribute('aria-current','true');b.append(node('span',displayPromise(run.promise),'run-promise'),node('small',`${statusLabel(run.state)}. ${testType(run.mode)}. Case ${run.id.slice(-8)}`));b.addEventListener('click',()=>action(async()=>{selectRun(run.id);await refresh();}));$('runs').append(b);}
  if(focusedRun){const restore=[...document.querySelectorAll('.run-row')].find(b=>b.dataset.runId===focusedRun);restore?.focus();}
  }
  filterRuns();
  if(runId){const details=await api(`/api/runs/${runId}`);if(generation!==refreshGeneration||runId!==selected||details.run.id!==runId)return;current=details;const next=JSON.stringify([current.run.updated_at,current.run.id,current.purchase.updated_at,current.events.map(e=>e.id),current.merchant.tickets,current.recording,current.investigation_job]);if(next!==renderSignature){renderSignature=next;render(current);}}
}
function closeRecording(restoreFocus=false){
  const video=$('customer-recording-video');video.pause();video.removeAttribute('src');video.load();
  $('customer-recording-panel').hidden=true;$('watch-recording').setAttribute('aria-expanded','false');
  if(restoreFocus&&!$('watch-recording').hidden)$('watch-recording').focus();
}
function savedBrowserExecution(data){
  const observation=[...data.events].reverse().find(e=>e.source==='browser'&&e.event_type==='kernel_recorded_observation'&&e.payload.browser_kind==='KERNEL');
  return observation?{present:true,...observation.payload.browser_execution}:null;
}
function renderBrowserExecution(data){
  const execution=savedBrowserExecution(data),notice=$('browser-execution');
  notice.hidden=!execution;
  if(!execution)return;
  const summaries=new Map([['OBSERVED','Browser session recorded.'],['FAILED',"Browser session couldn't finish."],['INCOMPLETE','Browser session ended early.'],['CANCELLED','Browser session was stopped.'],['TIMED_OUT','Browser session ran out of time.']]);
  const issues=new Map([['checkout_step_failed','A checkout step could not be completed.'],['time_limit','The browser reached its time limit.'],['connection_lost','The browser lost its connection.'],['interrupted','The browser was interrupted.'],['identity_check_failed','The browser could not match the expected checkout.'],['access_failed','The browser could not open the checkout.']]);
  const summary=summaries.get(execution.status)||'The outcome of this saved browser session is unavailable.';
  const partial=execution.recording_state==='SAVED_PARTIAL';
  const detail=execution.status==='OBSERVED'?'':issues.get(execution.issue)||'';
  text('browser-execution',[summary,detail,partial?'Only part of the checkout was recorded.':'','Payment and ticket records are checked separately.'].filter(Boolean).join(' '));
  notice.dataset.tone=execution.status==='OBSERVED'&&!partial?'neutral':'warning';
}
function renderRecording(data){
  const execution=savedBrowserExecution(data),partial=execution?.recording_state==='SAVED_PARTIAL';
  const saved=data.recording,available=saved?.availability==='available';
  const nextKey=`${data.run.id}:${saved?.sha256||saved?.availability||'none'}`;
  if(recordingKey!==nextKey){closeRecording();recordingKey=nextKey;}
  $('watch-recording').hidden=!available;
  const recordingLabel=partial?'Watch partial checkout':'Watch saved checkout';
  const arrow=node('span','↗');arrow.setAttribute('aria-hidden','true');
  $('watch-recording').replaceChildren(document.createTextNode(recordingLabel+' '),arrow);
  text('saved-checkout-title',partial?'Saved checkout (partial)':'Saved checkout');
  text('recording-privacy',partial?'Partial recording from an earlier test checkout · private to this workspace. It may not show the final payment or ticket outcome. Watching it does not make a new payment.':'Saved from an earlier test checkout · private to this workspace. Watching it does not make a new payment.');
  $('customer-recording-note').hidden=false;
  text('customer-recording-note',available?(partial?'Private partial recording · the browser session ended early.':'Private recording · saved during an earlier checkout.'):saved?.availability==='disabled'?'Saved recordings are unavailable in this workspace.':'No playable checkout recording is attached to this case.');
}
function render(data){
  const {run,purchase,merchant,events}=data;
  $('empty').hidden=true;$('case').hidden=false;
  $('case').dataset.runId=run.id;text('run-id',run.id);text('run-title',displayPromise(run.promise));text('run-state',statusLabel(run.state));$('run-state').dataset.state=run.state;$('merchant-link').href=`/shop?run=${run.id}`;$('studio-link').href=`/studio/index.html?run=${run.id}`;$('delivery-timing-link').href=`/deadlines/index.html?run=${encodeURIComponent(run.id)}`;
  text('provenance',`${testType(run.mode)} · ${run.fault.merchant==='healthy'?'repair enabled':'delivery issue simulated'}`);
  const budget = run.budget;
  const budgetLabel = Number.isInteger(budget?.max_attempts) && budget.max_attempts > 0 && Number.isFinite(budget?.max_seconds) && budget.max_seconds > 0 ? `${budget.max_attempts} steps, up to ${budget.max_seconds} seconds` : 'limits not recorded';
  text('invariant','One $29 ticket, delivered within 60 seconds of confirmed payment.');
  text('case-budget',`Investigation limits: ${budgetLabel}.`);
  const cancelled=!!run.cancel_requested||run.state==='cancelled';
  syncActionButtons(data);
  $('export').href=`/api/runs/${run.id}/export`;
  const returned=location.pathname==='/return'&&new URLSearchParams(location.search).get('token')===purchase.order_id;
  $('capture').hidden=!returned;
  const customer=[...events].reverse().find(e=>e.source==='browser');
  const browserPath=typeof customer?.payload.url_path==='string'?customer.payload.url_path:'';
  const browserPage=new Map([['/','Investigation dashboard'],['/shop','Store page'],['/checkoutnow','Test checkout page'],['/return','Payment return page'],['/cancel','Approval cancellation page']]).get(browserPath)||'Recorded page';
  const rawBrowserKind=typeof customer?.payload.browser_kind==='string'?customer.payload.browser_kind:'';
  const knownBrowserKind=new Map([['LOCAL_BROWSER','Recorded local browser'],['KERNEL','Recorded remote browser']]).get(rawBrowserKind);
  const browserKind=knownBrowserKind||(rawBrowserKind?'Unrecognized browser source':'Browser source not recorded');
  text('customer-title',customer?browserPage:'Not observed');
  const priorExecution=new Map([['PRIOR_SANDBOX_EXECUTION','Saved from an earlier test payment'],['PRIOR_LOCAL_TEST_EXECUTION','Saved from an earlier local test · test data']]).get(customer?.payload.provenance);
  const browserTime=priorExecution?customer.event_time:customer?.observed_at;
  const browserProvenance=priorExecution?`${priorExecution}. Observed ${observedTime(browserTime)}. Imported ${observedTime(customer.observed_at)}. Reviewed saved record.`:`${observedTime(browserTime)}`;
  text('browser-source',customer?`${browserKind}. ${browserPath?'Page address saved':'Page address not recorded'}. ${browserProvenance}`:'Source unavailable');
  text('customer-detail',customer?(customer.payload.visible_text||(Object.keys(customer.payload.observed_fields||{}).length?'No separate page message was recorded. The labels above were read from the saved checkout.':'Visible page text was not captured. Navigation alone does not confirm approval or delivery.')):'No browser view has been saved.');
  const captured=customer?.payload.observed_fields,fields=$('customer-fields');fields.replaceChildren();
  for(const [key,label] of [['run_state','Checkout state'],['provider_title','Payment on the page'],['merchant_title','Ticket on the page'],['verdict','Delivery message']]){
    if(typeof captured?.[key]==='string'&&captured[key])fields.append(node('dt',label),node('dd',captured[key]));
  }
  fields.hidden=!fields.childElementCount;
  renderBrowserExecution(data);
  renderRecording(data);
  const provider=[...events].reverse().find(e=>e.event_type==='independent_order_read');
  text('provider-title',provider?(purchase.payment_confirmed?'Payment confirmed':'Payment not yet confirmed'):'Not checked with PayPal');
  text('provider-detail',provider?`${statusLabel(purchase.payment_state)} · checked ${observedTime(provider.observed_at)}. Payment references are in Original records.`:'Check payment status after checkout. An unanswered request does not mean the payment failed.');
  text('merchant-title',merchant.known?`${merchant.ticket_count} ${merchant.ticket_count===1?'ticket':'tickets'}`:'Unknown purchase');
  text('merchant-detail',`${statusLabel(merchant.status)} · checked ${observedTime(merchant.observed_at)}.`);
  $('ticket-card').hidden=merchant.ticket_count!==1;
  if(merchant.ticket_count===1){text('ticket-id',merchant.tickets[0].id);text('ticket-time',`Issued ${observedTime(merchant.tickets[0].created_at)}`);}
  const result=[...events].reverse().find(e=>e.event_type==='invariant_result');
  $('regression').hidden=!(run.fault.merchant==='defective'&&['response_loss','process_interrupt'].includes(run.fault.kind)&&purchase.payment_confirmed===1&&merchant.ticket_count===0&&result?.payload.verdict==='FAIL'&&provider&&events.some(e=>e.event_type==='capture_transport_response'));
  text('regression-note',$('regression').hidden?'A replay test becomes available when a lost payment response or interrupted store causes a confirmed payment to miss its ticket.':'Reruns this saved failure on your computer. No new payment takes place.');
  $('regression').href=`/api/runs/${run.id}/regression.zip`;
  syncRecoveryNotice(data);
  $('verdict').dataset.verdict=result?result.payload.verdict:'INCONCLUSIVE';
  text('verdict',result?`${verdictLabels.get(result.payload.verdict)||'More evidence needed'}: ${verdictReasons.get(result.payload.signature)||errorMessage(result.payload.reason)}`:(purchase.order_id?'Check payment status to see the result.':'Start a test checkout to check ticket delivery.'));
  renderTimeline(run.id,events);
  text('journal',JSON.stringify({run:{id:run.id,promise:run.promise,state:run.state,mode:run.mode,fault:run.fault,execution:run.execution||null},assistant_job:data.investigation_job||null,purchase_id:purchase.id,order_id:purchase.order_id,capture_id:purchase.capture_id,payment_state:purchase.payment_state,merchant_status:merchant.status,browser:customer||null,delivery_result:result?.payload||null,operations:data.operations},null,2));
  if(run.execution?.state==='interrupted'){text('investigator-note','The assistant stopped before its response could be confirmed. Saved records remain available.');$('investigator-note').dataset.mode='UNKNOWN';$('investigator-note').hidden=false;}
  renderInvestigationJob(data.investigation_job,run,purchase);
  if(focusSelectedRun){focusSelectedRun=false;$('run-title').focus();}
}
async function observe(actionName){if(!selected||!current||current.run.id!==selected||current.run.cancel_requested)return;await api(`/api/runs/${selected}/observation`,{browser_kind:'LOCAL_BROWSER',url_path:location.pathname,visible_text:[$('run-state').textContent,$('verdict').textContent,$('merchant-title').textContent,$('message').textContent].join(' | '),action:actionName});}
$('login').addEventListener('submit',async(e)=>{e.preventDefault();try{await api('/api/login',{token:$('token').value});$('token').value='';$('error-details').hidden=true;text('error-code','');if(landingView){landingView=false;history.replaceState(null,'',selected?`/?run=${encodeURIComponent(selected)}`:'/');}await refresh();}catch(e){showError(e,'login-message');}});
$('watch-recording').addEventListener('click',()=>{
  if(!current||current.run.id!==selected||current.recording?.availability!=='available')return;
  if(!$('customer-recording-panel').hidden){closeRecording(true);return;}
  const video=$('customer-recording-video');video.autoplay=false;video.preload='none';
  video.src=`/api/runs/${encodeURIComponent(current.run.id)}/recording`;
  $('customer-recording-panel').hidden=false;$('watch-recording').setAttribute('aria-expanded','true');
  text('recording-status','Press Play to watch the saved checkout.');video.focus();
});
$('close-recording').addEventListener('click',()=>closeRecording(true));
$('customer-recording-video').addEventListener('error',()=>text('recording-status','The saved checkout could not be loaded. Refresh and try again.'));
$('customer-recording-video').addEventListener('loadedmetadata',()=>text('recording-status','Saved checkout ready. Use the video controls to play or seek.'));
function filterRuns(){
  const query=$('run-search').value.trim().toLocaleLowerCase();let shown=0;const rows=[...document.querySelectorAll('.run-row')];
  for(const row of rows){row.hidden=!!query&&!`${row.textContent} ${row.dataset.runId}`.toLocaleLowerCase().includes(query);if(!row.hidden)shown++;}
  $('search-status').hidden=!query;text('search-status',shown?`${shown} of ${rows.length} investigations`:'No matching investigations. Try another search.');
}
$('run-search').addEventListener('input',filterRuns);
for(const button of document.querySelectorAll('.trace-filters button'))button.addEventListener('click',()=>{timelineSource=button.dataset.source;if(current&&current.run.id===selected)renderTimeline(current.run.id,current.events);});
$('copy-ticket').addEventListener('click',async()=>{
  if(!current||current.run.id!==selected||current.merchant.ticket_count!==1)return;
  const runId=current.run.id,ticketId=current.merchant.tickets[0].id;
  try{await navigator.clipboard.writeText(ticketId);if(selected===runId)text('copy-status','Ticket reference copied.');}
  catch{if(selected===runId)text('copy-status','Copy unavailable. Select the ticket reference above to copy it manually.');}
});
$('fault').addEventListener('change',()=>{$('delay-field').hidden=$('fault').value!=='event_delay';});
$('new-run').addEventListener('submit',(e)=>{e.preventDefault();action(async()=>{const fault={kind:$('fault').value,merchant:$('merchant').value};if(fault.kind==='event_delay')fault.delay_seconds=Number($('delay').value);const run=await api('/api/runs',{promise:$('promise').value,mode:$('mode').value,fault,fixture_id:$('fixture').value});selectRun(run.id);await refresh();await observe('investigation_created');await refresh();});});
$('checkout').addEventListener('click',()=>action(async()=>{try{const order=await api(`/api/runs/${selected}/order`,{});await refresh();await observe('leaving_for_buyer_approval');if(order.approval_url)location.href=order.approval_url;else text('message','The saved payment has been checked. No new approval was requested.');}catch(e){await refresh();showError(e);await observe('checkout_unavailable');throw e;}}));
$('capture').addEventListener('click',()=>action(async()=>{let result;try{result=await api(`/api/runs/${selected}/capture`,{order_id:new URLSearchParams(location.search).get('token')});}catch(e){if(e instanceof TypeError)throw new Error('Connection interrupted while confirming payment. Reconnect to check the saved order.');throw e;}await refresh();if(result.message)text('message',readableText(result.message));syncRecoveryNotice();await observe('capture_result');await refresh();}));
$('reconcile').addEventListener('click',()=>action(async()=>{await api(`/api/runs/${selected}/reconcile`,{});await refresh();await observe('reconciliation_result');await refresh();}));
$('investigate').addEventListener('click',()=>action(async()=>{if(!selected)return;const runId=selected;await api(`/api/runs/${runId}/investigation-job`,{});if(selected!==runId)return;await refresh();if(selected!==runId)return;}));
$('cancel-run').addEventListener('click',async()=>{if(!current||current.run.id!==selected||cancelPending)return;const runId=current.run.id;cancelPending=runId;syncActionButtons();try{await api(`/api/runs/${runId}/cancel`,{});await refresh();if(selected===runId)text('message','Investigation stopped. Saved evidence remains available.');}catch(e){if(selected===runId)showError(e);}finally{cancelPending=null;syncActionButtons();}});
api('/healthz').then(d=>text('health',d.status==='ok'&&d.database==='ok'?'● Workspace connected':'Workspace connection needs attention')).catch(e=>text('health','Workspace unavailable. Check your connection and refresh.'));
refresh().then(async()=>{if(selected&&location.pathname==='/cancel'){text('message','Buyer approval cancelled. This purchase is not completed.');await observe('buyer_cancelled');}else if(selected&&location.pathname==='/return'){if(current?.purchase.payment_confirmed!==1)text('message','Returned from PayPal. Check buyer approval before confirming this payment.');syncRecoveryNotice();await observe('buyer_returned');}}).catch(e=>{if($('workspace').hidden){$('login-panel').hidden=false;showError(e,'login-message');}else showError(e);});
setInterval(()=>{if(!document.hidden&&!$('workspace').hidden)refresh().catch(e=>showError(e));},5000);
