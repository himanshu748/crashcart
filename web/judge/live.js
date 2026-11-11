(function (root) {
  'use strict';
  const LIMIT_MS = 8 * 60 * 1000;
  const REQUEST_MS = 5000;
  const POLL_MS = 2000;
  const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'EXPIRED']);
  function text(value, limit = 500) { return typeof value === 'string' ? value.replace(/[\u0000-\u001f]/g, ' ').slice(0, limit) : ''; }
  function stateName(value) { const state = text(value).toUpperCase(); return state === 'COMPLETE' ? 'COMPLETED' : state; }
  function availabilityReason(value) {
    const reason = text(value, 400);
    return !reason || /^[A-Z0-9_]+$/.test(reason) ? 'New Sandbox runs are paused here. The saved example is ready.' : reason;
  }
  function maskId(value) {
    const id = text(value, 150).trim();
    return !id ? '' : id.length > 8 ? id.slice(0, 4) + '…' + id.slice(-4) : 'ID recorded';
  }
  function maskKnownIds(value, payment, limit = 500) {
    let result = typeof value === 'string' ? value : '';
    for (const id of [payment?.order_id, payment?.capture_id]) {
      if (typeof id === 'string' && id) result = result.split(id).join(maskId(id));
    }
    return text(result, limit);
  }
  function safeRunId(value) { return typeof value === 'string' && /^[A-Za-z0-9_-]{8,120}$/.test(value) ? value : null; }
  function safeApproval(value) {
    try {
      const url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password || !(url.hostname === 'sandbox.paypal.com' || url.hostname.endsWith('.sandbox.paypal.com'))) return null;
      if (!['/checkoutnow', '/webapps/hermes'].includes(url.pathname)) return null;
      return url.href;
    } catch (_) { return null; }
  }
  function returnContext(query) {
    const params = new URLSearchParams(query);
    const runId = safeRunId(params.get('run'));
    const cancelled = params.get('cancel') === '1';
    return {runId, confirm: Boolean(runId) && !cancelled, cancelled};
  }
  function projectRun(run) {
    run = run || {};
    const state = stateName(run.state);
    const payment = run.payment || {};
    const webhook = run.webhook || {};
    const ai = run.investigation || {};
    const citations = Array.isArray(ai.citations) ? ai.citations : [];
    const captured = payment.status === 'COMPLETED' && Boolean(text(payment.order_id).trim()) && Boolean(text(payment.capture_id).trim());
    const verified = webhook.verified === true;
    const investigated = ['COMPLETE', 'COMPLETED', 'DONE', 'SUCCEEDED'].includes(stateName(ai.status)) && citations.length > 0;
    const verdict = run.verdict && ['PASS', 'FAIL'].includes(run.verdict.verdict) ? run.verdict.verdict : null;
    const finished = state === 'COMPLETED' && captured && verified && investigated && Boolean(verdict);
    const active = {CREATING: 0, AWAITING_APPROVAL: 1, CONFIRMING: 2, PAYMENT_CONFIRMED: 3, WAITING_FOR_WEBHOOK: 3, WAITING_FOR_PROMISE: 4, INVESTIGATING: 4}[state];
    const ticketCount = Array.isArray(run.tickets) ? run.tickets.length : Number.isInteger(run.tickets?.count) && run.tickets.count >= 0 ? run.tickets.count : null;
    return {state, terminal: terminal.has(state), paused: state === 'PAUSED', finished, verdict, signature: text(run.verdict?.signature), ticketCount,
      stages: [
        {id: 'order', done: Boolean(payment.order_id), active: active === 0},
        {id: 'approval', done: captured, active: active === 1},
        {id: 'payment', done: captured, active: active === 2},
        {id: 'webhook', done: verified, active: active === 3},
        {id: 'investigation', done: investigated, active: active === 4},
      ]};
  }
  function projectReplay(data) {
    if (data?.mode !== 'RECORDED_REPLAY' || data.fresh_execution !== false || data.network_calls !== 0 || !/^[a-f0-9]{64}$/.test(data.input_file_sha256 || '')) return null;
    const inputHash = data.cases?.defective?.receipt?.input_sha256;
    if (!/^[a-f0-9]{64}$/.test(inputHash || '')) return null;
    for (const [name, verdict, signature, count] of [['defective', 'FAIL', 'paid_without_ticket', 0], ['healthy', 'PASS', 'ticket_delivered_once_on_time', 1]]) {
      const item = data.cases?.[name], receipt = item?.receipt;
      if (!receipt || receipt.mode !== 'RECORDED_REPLAY' || receipt.fresh_execution !== false || receipt.network_calls !== 0
          || receipt.input_sha256 !== inputHash || receipt.verdict !== verdict || receipt.signature !== signature || receipt.ticket_count !== count
          || ![true, 1].includes(item.purchase?.payment_confirmed) || !text(item.purchase?.capture_completed_at).startsWith('2026-10-22T')
          || item.execution?.invariant?.recovery_seconds !== 60 || !Array.isArray(item.merchant?.tickets) || item.merchant.tickets.length !== count) return null;
    }
    return {missed: data.cases.defective.merchant.tickets.length, recovered: data.cases.healthy.merchant.tickets.length};
  }
  async function requestJSON(fetcher, url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), REQUEST_MS);
    try {
      const response = await fetcher(url, {credentials: 'same-origin', cache: 'no-store', redirect: 'error', ...options, signal: controller.signal});
      const type = response.headers.get('Content-Type') || '';
      if (!response.ok || !type.includes('application/json')) {
        const error = new Error(response.status === 404 ? 'Live runs are not available on this deployment.' : 'The live service could not complete this request.');
        error.status = response.status;
        throw error;
      }
      const body = await response.json();
      if (!body || typeof body !== 'object' || Array.isArray(body)) throw new Error('The live service returned an unreadable reply. No result is assumed.');
      return body;
    } catch (error) {
      if (error instanceof TypeError || error instanceof SyntaxError) throw new Error('The live service could not be reached or returned an unreadable reply. The saved example is ready.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  const exported = {availabilityReason, maskId, maskKnownIds, safeRunId, safeApproval, returnContext, projectRun, projectReplay, requestJSON};
  if (typeof module === 'object' && module.exports) module.exports = exported;
  if (!root.document) return;
  const doc = root.document;
  if (!doc.getElementById('live-start')) return;
  const byId = id => doc.getElementById(id);
  let csrf = '', runId = null, polling = null, started = Date.now(), stopped = false, creating = false, idempotency = null, replayRequested = false, focusApproval = false;
  const returned = returnContext(root.location.search);
  const display = (id, value) => { byId(id).textContent = value; };
  const show = (id, visible) => { byId(id).hidden = !visible; };
  function announce(value) { if (byId('live-status').textContent !== value) display('live-status', value); }
  function stop() { stopped = true; clearTimeout(polling); polling = null; }
  async function loadSavedReplay(paused) {
    if (replayRequested) return;
    replayRequested = true;
    try {
      const data = await requestJSON(root.fetch.bind(root), 'data.json');
      const replay = projectReplay(data);
      if (!replay) return;
      display('live-saved-missed', String(replay.missed));
      display('live-saved-recovered', String(replay.recovered));
      show('live-saved-replay', true);
      display('live-mode', 'Saved replay · separate from the live checkout');
      if (paused) display('live-error-title', 'Live runs paused, showing saved replay');
    } catch (_) { /* The recorded workspace link stays available if the summary cannot load. */ }
  }
  function fallback(message, paused = false) {
    stop();
    byId('live-start').disabled = true;
    show('live-approve', false);
    show('live-cancel', false);
    show('live-error', true);
    display('live-error-title', paused ? 'Live runs paused. The saved example is ready.' : 'This run needs attention');
    display('live-error-copy', message);
    announce(paused ? 'Live runs paused. The saved example is ready.' : message);
    display('live-mode', paused ? 'Saved example available · live runs paused' : 'Live PayPal Sandbox · result not confirmed');
    if (!runId) { show('live-welcome', false); show('live-progress', false); }
    if (paused) {
      display('live-title', 'See how the missing ticket was found.');
      display('live-lead', 'New Sandbox runs are paused. You can still explore the saved payment, investigation and repair comparison.');
    }
    loadSavedReplay(paused);
  }
  function render(run) {
    if (run.mode && run.mode !== 'LIVE_SANDBOX') { fallback('This page only supports PayPal Sandbox runs. Open the saved example instead.'); return; }
    const view = projectRun(run);
    show('live-run', true);
    show('live-welcome', false);
    byId('live-start').disabled = true;
    for (const stage of view.stages) {
      const item = byId('stage-' + stage.id);
      item.dataset.status = stage.done ? 'done' : stage.active ? 'active' : 'waiting';
      const label = item.querySelector('.live-step-state');
      label.textContent = stage.done ? 'Confirmed' : stage.active ? 'In progress' : 'Waiting';
      if (stage.active) item.setAttribute('aria-current', 'step'); else item.removeAttribute('aria-current');
    }
    const payment = run.payment || {};
    if (Number.isInteger(payment.amount) && /^[A-Z]{3}$/.test(payment.currency || '')) display('live-amount', payment.currency + ' ' + (payment.amount / 100).toFixed(2));
    display('live-payment', text(payment.status) || 'Not confirmed');
    display('live-order', maskId(payment.order_id) || 'Not created yet');
    display('live-capture', maskId(payment.capture_id) || 'Not captured yet');
    display('live-webhook', run.webhook?.verified === true ? 'Signature verified' : 'Waiting for verified notification');
    const approval = view.state === 'AWAITING_APPROVAL' ? safeApproval(run.approval_url) : null;
    if (view.state === 'AWAITING_APPROVAL' && !approval) { fallback('A valid PayPal Sandbox approval link was not provided. No payment page has been opened. Use the saved example to continue.'); return; }
    show('live-approve', Boolean(approval));
    if (approval) {
      byId('live-approve').href = approval;
      if (focusApproval) { focusApproval = false; byId('live-approve').focus(); }
    } else byId('live-approve').removeAttribute('href');
    show('live-cancel', !view.terminal && view.state === 'AWAITING_APPROVAL');
    const labels = {CREATING: 'Preparing your Sandbox order…', AWAITING_APPROVAL: 'Your order is ready. Approve the test payment in PayPal Sandbox.', CONFIRMING: 'Checking approval with PayPal and confirming capture…', PAYMENT_CONFIRMED: 'Payment confirmed. Checking its notification…', WAITING_FOR_WEBHOOK: 'Waiting for PayPal’s signed payment notification…', WAITING_FOR_PROMISE: 'Watching the one-minute delivery promise. The faulty store deliberately issues no ticket.', INVESTIGATING: 'DeepSeek is checking the payment and ticket evidence…', COMPLETED: 'Investigation complete. The result is backed by this run’s records.', CANCELLED: 'Checkout cancelled. No further capture is requested by this page.', EXPIRED: 'This run has expired. Open the saved example to continue.', FAILED: 'This run stopped before every check could be confirmed.'};
    announce(maskKnownIds(run.stage_message, payment, 300) || labels[view.state] || 'Waiting for a confirmed update from the server…');
    const steps = Array.isArray(run.investigation?.steps) ? run.investigation.steps : [];
    const list = byId('live-ai-steps');
    list.replaceChildren();
    for (const step of steps) {
      const li = doc.createElement('li');
      const title = doc.createElement('strong'); title.textContent = ({read_provider: 'Read PayPal', read_merchant: 'Check ticket delivery', finish: 'Explain the finding'})[step.action] || text(step.action).replaceAll('_', ' ');
      const summary = doc.createElement('p'); summary.textContent = maskKnownIds(step.summary, payment, 1500);
      li.append(title, summary);
      if (Array.isArray(step.evidence_ids) && step.evidence_ids.length) { const cite = doc.createElement('span'); cite.className = 'live-citation'; cite.textContent = 'Records: ' + step.evidence_ids.map(id => maskKnownIds(id, payment, 120)).join(', '); li.append(cite); }
      list.append(li);
    }
    show('live-investigation', steps.length > 0 || view.state === 'INVESTIGATING' || view.finished);
    if (view.paused) { fallback('The live service is paused. You can still inspect the saved payment, investigation and repair.', true); return; }
    if (view.finished) {
      stop();
      show('live-result', true);
      display('live-result-title', view.verdict === 'FAIL' ? 'Payment confirmed. Delivery missed.' : view.verdict === 'PASS' ? 'The delivery promise was kept.' : 'The records do not establish a result.');
      display('live-result-reason', maskKnownIds(run.verdict.reason, payment, 1200) || 'The deterministic checker evaluated the payment and delivery records.');
      display('live-result-signature', view.signature);
      display('live-result-outcome', view.verdict === 'PASS' ? 'Kept' : 'Not kept');
      display('live-ticket-count', view.ticketCount === null ? 'Not established' : String(view.ticketCount));
      byId('live-result').dataset.verdict = view.verdict;
      const citations = byId('live-citations'); citations.replaceChildren();
      for (const item of run.investigation.citations) {
        const li = doc.createElement('li');
        li.textContent = typeof item === 'string' ? maskKnownIds(item, payment, 800) : [maskKnownIds(item.id, payment, 120), text(item.kind, 120), maskKnownIds(item.summary, payment, 1200)].filter(Boolean).join(' · ');
        citations.append(li);
      }
    } else if (view.terminal) {
      fallback(view.state === 'COMPLETED' ? 'The server did not provide every required payment, webhook and investigation record. No finished result is shown.' : maskKnownIds(run.error?.message, payment, 600) || labels[view.state]);
    }
  }
  async function post(path) {
    if (!csrf) throw new Error('Reload this page to renew your secure session.');
    return requestJSON(root.fetch.bind(root), 'api/live/' + path, {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}, body: '{}'});
  }
  async function poll() {
    if (stopped || !runId) return;
    if (Date.now() - started >= LIMIT_MS) { fallback('This page stopped waiting after eight minutes. No success is assumed. Open the saved example, or reload this run to check its recorded status.'); return; }
    try {
      const run = await requestJSON(root.fetch.bind(root), 'api/live/runs/' + encodeURIComponent(runId));
      if (stopped) return;
      render(run);
      if (!stopped) polling = setTimeout(poll, POLL_MS);
    } catch (error) { fallback(error.name === 'AbortError' ? 'The live service took too long to respond. The saved example is available below.' : error.message); }
  }
  byId('live-start').addEventListener('click', async () => {
    if (creating || stopped || !csrf) return;
    creating = true; focusApproval = true; byId('live-start').disabled = true;
    announce('Preparing your Sandbox order…');
    try {
      idempotency = idempotency || root.crypto.randomUUID();
      const run = await requestJSON(root.fetch.bind(root), 'api/live/runs', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf, 'Idempotency-Key': idempotency}, body: '{}'});
      runId = safeRunId(run.run_id);
      if (!runId) throw new Error('The live service returned an invalid run. No approval link is opened.');
      started = Date.now();
      const url = new URL(root.location.href); url.search = ''; url.searchParams.set('run', runId); root.history.replaceState(null, '', url);
      render(run); await poll();
    } catch (error) { fallback(error.name === 'AbortError' ? 'The order request timed out. No second order will be started automatically. Open the saved example to continue without another request.' : error.message); }
    finally { creating = false; }
  });
  byId('live-cancel').addEventListener('click', async () => {
    clearTimeout(polling); polling = null;
    byId('live-cancel').disabled = true;
    try { await post('runs/' + encodeURIComponent(runId) + '/cancel'); await poll(); }
    catch (error) { fallback(error.message); }
  });
  root.addEventListener('pagehide', stop);
  root.addEventListener('pageshow', event => {
    if (event.persisted && runId && byId('live-error').hidden && byId('live-result').hidden) { stopped = false; poll(); }
  });
  async function initialize() {
    if (root.location.hostname.endsWith('.github.io') || root.location.hostname === 'github.io') { fallback('GitHub Pages hosts the recorded example. New Sandbox checkouts run only on the live-enabled workspace.', true); return; }
    try {
      const config = await requestJSON(root.fetch.bind(root), 'api/live/config');
      if (config.enabled !== true || config.mode !== 'LIVE_SANDBOX' || !text(config.csrf_token)) { fallback(availabilityReason(config.reason), true); return; }
      csrf = config.csrf_token;
      display('live-mode', 'Live PayPal Sandbox · new payment and AI calls after you start');
      runId = returned.runId;
      if (runId) {
        show('live-welcome', false); show('live-run', true);
        if (returned.cancelled) await post('runs/' + encodeURIComponent(runId) + '/cancel');
        else if (returned.confirm) {
          announce('Checking this return with PayPal. The URL alone does not confirm payment.');
          await post('runs/' + encodeURIComponent(runId) + '/confirm');
        }
        await poll();
      } else {
        byId('live-start').disabled = false;
        announce('Ready when you are. Nothing is created until you start.');
      }
    } catch (error) { fallback(error.name === 'AbortError' ? 'The live service did not respond in time. The saved example is ready.' : 'The live service is unavailable here. The saved example works without an account or keys.', true); }
  }
  initialize();
})(typeof window !== 'undefined' ? window : globalThis);
