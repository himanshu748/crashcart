/* CrashCart workspace. Same-origin JSON API; no credentials are stored here. */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const enc = encodeURIComponent;
  const params = new URLSearchParams(location.search);
  const path = location.pathname;
  const isLanding = (path === '/' || path === '/index.html') && params.get('view') === 'home';
  const entryPage = path === '/shop' ? 'shop' : path === '/return' ? 'return' : path === '/cancel' ? 'cancel' : 'desk';
  const returnToken = entryPage === 'return' ? params.get('token') : null;

  let pageMode = entryPage;
  let selected = params.get('run') || null;

  /* Motion: one class drives every optional animation. */
  const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
  const syncMotion = () => document.documentElement.classList.toggle('js-motion', !motionQuery.matches);
  syncMotion();
  motionQuery.addEventListener?.('change', syncMotion);

  /* ---------- Plain-language labels ---------- */
  const modeInfo = (mode) => new Map([
    ['LIVE_SANDBOX', {tone: 'live', label: 'Test checkout · PayPal Sandbox', short: 'Test checkout'}],
    ['FRESH_SANDBOX', {tone: 'live', label: 'Repair check · new PayPal Sandbox checkout', short: 'Repair check'}],
    ['RECORDED_REPLAY', {tone: 'replay', label: 'Replay of a saved checkout · no new payment', short: 'Saved replay'}],
    ['LOCAL_TEST', {tone: 'example', label: 'Example data · simulated, no payment', short: 'Example data'}],
  ]).get(mode) || {tone: 'unknown', label: 'Unknown check type', short: 'Unknown type'};

  const faultLabel = (kind) => new Map([
    ['none', 'Normal checkout'],
    ['response_loss', 'PayPal’s reply gets lost'],
    ['event_delay', 'Delayed delivery'],
    ['event_duplicate', 'Delivery event arrives twice'],
    ['process_interrupt', 'Store stops mid-delivery'],
  ]).get(kind) || 'Unknown problem';

  const statusLabel = (value) => new Map([
    ['created', 'Ready to start'], ['running', 'In progress'], ['awaiting_approval', 'Waiting for buyer approval'],
    ['approved', 'Approved by the buyer'], ['completed', 'Completed'], ['failed', 'Needs attention'],
    ['cancelled', 'Stopped'], ['inconclusive', 'More evidence needed'], ['blocked', 'Needs setup'],
    ['pending', 'Waiting'], ['unresolved', 'Not confirmed yet'], ['delivered', 'Ticket delivered'],
    ['not_delivered', 'No ticket delivered'], ['missing_purchase', 'Purchase not found'], ['not_started', 'Not started'],
    ['needs_input', 'More information needed'], ['budget_exhausted', 'Assistant limit reached'],
    ['awaiting_payment', 'Waiting for payment'], ['interrupted', 'Interrupted'],
  ]).get(String(value ?? '').toLowerCase()) || 'Status not available';

  const stateTone = (state) => new Map([
    ['completed', 'ok'], ['delivered', 'ok'], ['failed', 'bad'], ['not_delivered', 'bad'],
    ['inconclusive', 'warn'], ['blocked', 'warn'], ['unresolved', 'warn'], ['budget_exhausted', 'warn'],
    ['running', 'live'], ['awaiting_approval', 'live'], ['pending', 'live'],
  ]).get(String(state ?? '').toLowerCase()) || '';

  const sourceLabel = (value) => new Map([
    ['browser', 'Checkout page'], ['provider', 'PayPal'], ['merchant', 'Store'], ['checker', 'Delivery check'],
    ['investigator', 'Assistant'], ['model', 'Assistant'], ['operator', 'Workspace'], ['system', 'Workspace'],
    ['worker', 'Delivery service'], ['harness', 'Test controls'],
  ]).get(value) || 'Other';

  const serviceLabel = (key) => new Map([
    ['paypal', 'PayPal test payments'], ['webhook', 'Payment notifications'], ['model', 'AI assistant'],
    ['kernel', 'Remote browser'], ['studio', 'Records explorer'],
  ]).get(key) || 'Other service';

  // Only known generated example titles are reworded. Merchant-written text is shown as written.
  const generatedTitles = new Map([
    ['LOCAL_TEST A: USD29 buys one ticket within60seconds of completed payment.', 'One ticket within 60 seconds of a completed $29 payment.'],
    ['LOCAL_TEST B: isolated approval wait; USD29 buys one ticket within60seconds of completed payment.', 'Waiting for the buyer to approve: one ticket within 60 seconds of a completed $29 payment.'],
    ['Fresh repair verification: recover a lost capture response and issue exactly one ticket.', 'Check the repair: recover a lost PayPal reply and issue exactly one ticket.'],
    ['Lost capture response: payment completed but the workshop ticket is missing.', 'PayPal’s reply was lost: the customer paid, but no workshop ticket arrived.'],
    ['Recover a real sandbox payment after the merchant process exits before ticket delivery, preserving exactly one ticket within 60 seconds.', 'Recover a test payment after the store stops before delivery, and still issue exactly one ticket within 60 seconds.'],
    ['A completed USD 29 payment must produce exactly one workshop ticket within 60 seconds. Early independent read, then deadline verification.', 'A completed $29 payment must produce exactly one workshop ticket within 60 seconds. Check the payment first, then check delivery at the deadline.'],
    ['LOCAL_TEST UI interaction: one workshop ticket within 60 seconds; unpaid fixture, no provider call.', 'Interface check with example data: one workshop ticket within 60 seconds. No payment is made.'],
  ]);
  const displayPromise = (value) => generatedTitles.get(value) ?? String(value ?? '');

  function readableText(value) {
    let result = String(value ?? '');
    for (const [pattern, replacement] of [
      [/LOCAL_TEST UI interaction/gi, 'Interface check with example data'], [/LOCAL_TEST/gi, 'Example data'],
      [/FRESH_SANDBOX/g, 'Repair check'], [/LIVE_SANDBOX/g, 'Test checkout'], [/RECORDED_REPLAY/g, 'Saved replay'],
      [/Fresh repair verification/gi, 'Check the repair'], [/capture response/gi, 'PayPal reply'],
      [/confirmed capture/gi, 'confirmed payment'], [/capture completion/gi, 'payment confirmation'], [/\bcaptured?\b/gi, 'payment'],
      [/persisted/gi, 'saved'], [/correlated/gi, 'linked'], [/\bsandbox\b/gi, 'test'], [/merchant process/gi, 'store process'],
      [/\bmerchant\b/gi, 'store'], [/\bprovider\b/gi, 'PayPal'], [/entitlements?/gi, 'ticket'],
      [/independent read/gi, 'payment check'], [/independent retrieval/gi, 'a separate payment check'],
      [/fixed recovery (window|deadline)/gi, '60-second delivery deadline'], [/deterministic verdict/gi, 'delivery result'],
      [/invariant/gi, 'delivery promise'], [/fixture/gi, 'test store'], [/reconcil(e|ed|iation)/gi, 'payment check'],
    ]) result = result.replace(pattern, replacement);
    return result;
  }

  const eventLabels = new Map([
    ['run_created', 'Case created'], ['purchase_created', 'Purchase saved'], ['run_cancelled', 'Case stopped'],
    ['customer_observation', 'Checkout page recorded'], ['order_created', 'Checkout created'], ['order_creation_requested', 'Checkout requested'],
    ['order_unresolved', 'Payment status needs checking'], ['independent_order_read', 'Payment checked with PayPal'],
    ['capture_started', 'Payment confirmation started'], ['capture_requested', 'Payment confirmation requested'],
    ['capture_transport_response', 'PayPal reply recorded'], ['capture_unresolved', 'Payment confirmation interrupted'],
    ['capture_confirmed', 'Payment confirmed'], ['capture_completed', 'Payment completed'], ['ticket_created', 'Ticket issued'],
    ['ticket_issued', 'Ticket issued'], ['ticket_fulfilled', 'Ticket delivered'], ['merchant_observation', 'Store tickets checked'],
    ['entitlement_read', 'Store tickets checked'], ['invariant_result', 'Delivery promise checked'], ['inconclusive', 'More evidence needed'],
    ['fault_applied', 'Test problem applied'], ['fault_activated', 'Test problem started'], ['fault_deactivated', 'Test problem ended'],
    ['response_loss', 'PayPal reply lost'], ['process_exit_boundary', 'Store stopped mid-delivery'], ['pre_capture_read', 'Buyer approval checked'],
    ['model_request', 'Assistant asked a question'], ['model_response', 'Assistant replied'], ['model_plan', 'Assistant proposed a next step'],
    ['tool_observation', 'Assistant step recorded'], ['investigation_started', 'Assistant started'], ['investigation_finished', 'Assistant finished'],
    ['investigation_ended', 'Assistant finished'], ['investigation_stopped', 'Assistant stopped'], ['investigation_failed', 'Assistant couldn’t finish'],
    ['cancelled', 'Assistant stopped'], ['customer_message', 'Checkout message recorded'], ['kernel_recorded_observation', 'Remote browser session recorded'],
  ]);
  const eventLabel = (type) => eventLabels.get(type) || 'Other activity recorded';

  const verdictTitles = new Map([['PASS', 'Promise kept'], ['FAIL', 'Promise broken'], ['INCONCLUSIVE', 'More evidence needed']]);
  const verdictReasons = new Map([
    ['ticket_delivered_once_on_time', 'PayPal confirmed the payment, and exactly one ticket arrived within 60 seconds.'],
    ['paid_without_ticket', 'PayPal confirmed the payment, but no ticket arrived within 60 seconds.'],
    ['ticket_delivered_late', 'The ticket arrived, but after the 60-second deadline.'],
    ['duplicate_tickets', 'The store issued more than one ticket for the same payment.'],
    ['payment_amount_mismatch', 'The confirmed amount doesn’t match the $29 ticket price.'],
    ['payment_currency_mismatch', 'The payment wasn’t made in US dollars.'],
    ['within_recovery_window', 'The 60-second delivery window is still open, so a missing ticket isn’t a failure yet.'],
    ['stale_merchant_observation', 'The store was last checked before the deadline. Check again after it passes.'],
    ['unconfirmed_payment', 'PayPal hasn’t confirmed this payment yet.'],
    ['payment_not_completed', 'PayPal doesn’t show a completed payment.'],
    ['missing_provider_evidence', 'The payment still needs to be checked with PayPal.'],
    ['missing_merchant_evidence', 'The store has no record of this purchase.'],
    ['missing_correlation_identity', 'Some references needed to match the payment to a ticket are missing.'],
    ['correlation_mismatch', 'The payment and the store records point to different purchases.'],
    ['missing_capture_identity', 'The reference for the confirmed payment is missing.'],
    ['malformed_payment', 'The payment amount or currency is missing or unreadable.'],
    ['missing_observation_time', 'A payment or delivery time is missing its time zone.'],
    ['future_observation', 'A record is dated later than this check.'],
    ['observation_precedes_payment', 'The store was checked before the payment completed.'],
    ['malformed_merchant_evidence', 'The ticket count doesn’t match the saved ticket records.'],
    ['malformed_ticket_identity', 'A ticket reference is missing or belongs to another purchase.'],
    ['duplicated_ticket_observation', 'The same ticket was recorded twice. That doesn’t prove two tickets exist.'],
    ['invalid_ticket_time', 'The ticket’s issue time can’t be checked against the payment.'],
    ['invalid_evaluation_time', 'The check needs a valid time and time zone.'],
  ]);

  /* ---------- API ---------- */
  class ApiError extends Error {
    constructor(message, {status = 0, code = null, uncertain = false} = {}) {
      super(message);
      this.status = status; this.code = code; this.uncertain = uncertain;
    }
  }

  async function api(url, body) {
    const init = body !== undefined
      ? {method: 'POST', credentials: 'same-origin', headers: {'Content-Type': 'application/json', Accept: 'application/json'}, body: JSON.stringify(body)}
      : {credentials: 'same-origin', headers: {Accept: 'application/json'}};
    let res;
    try { res = await fetch(url, init); }
    catch { throw new ApiError('NETWORK_UNAVAILABLE', {uncertain: true}); }
    let data;
    try { data = await res.json(); }
    catch { throw new ApiError('HTTP_RESPONSE_UNAVAILABLE', {status: res.status, uncertain: true}); }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new ApiError('HTTP_RESPONSE_UNAVAILABLE', {status: res.status, uncertain: true});
    if (!res.ok) {
      throw new ApiError(typeof data.error === 'string' ? data.error : `HTTP_${res.status}`, {
        status: res.status, code: data.code ?? null,
        uncertain: data.ambiguous === true || [502, 503, 504].includes(res.status),
      });
    }
    return data;
  }

  function errorMessage(error) {
    const raw = String(error?.message ?? error ?? '');
    if (error?.status === 401) return 'Your session has ended. Sign in again to continue.';
    if (raw === 'NETWORK_UNAVAILABLE' || /Failed to fetch|NetworkError|Load failed/i.test(raw)) return 'We lost the connection to your workspace. Check your connection and try again.';
    if (raw === 'HTTP_RESPONSE_UNAVAILABLE') return 'We couldn’t read the reply from your workspace. Refresh the page to see the latest saved records.';
    if (/BUDGET_EXHAUSTED/.test(raw)) return 'The assistant reached its limit for this case. Everything it found so far is saved.';
    if (/CRASHCART_ALLOW_SANDBOX|SANDBOX_DISABLED/i.test(raw)) return 'Test payments are turned off in this workspace. Ask your workspace owner to turn them on.';
    if (/PAYPAL_CLIENT|PAYPAL_NOT|PAYPAL.*CONFIGURATION/i.test(raw)) return 'PayPal test payments aren’t set up yet. Ask your workspace owner to connect PayPal Sandbox.';
    if (/OPENAI_|MODEL_USAGE_NOT_AUTHORIZED|MODEL_BUDGET|STUDIO_CALL_ALLOWANCE|MODEL_NOT_CONFIGURED/i.test(raw)) return 'The assistant isn’t available yet. Your workspace owner needs to turn on model access and set a usage allowance.';
    if (/MISSING_CONFIGURATION|Missing configuration/i.test(raw)) return 'This service needs setting up first. Ask your workspace owner to connect it.';
    if (/PUBLIC_URL/i.test(raw)) return 'The address PayPal returns buyers to isn’t set up. Ask your workspace owner to configure it.';
    if (/Invalid operator token/i.test(raw)) return 'That access key wasn’t accepted. Check it and try again.';
    if (/Operator access required/i.test(raw)) return 'Sign in to your workspace to continue.';
    if (/Unknown run/i.test(raw) || error?.status === 404) return 'We couldn’t find that case. Choose another one from the list.';
    if (error?.status === 403) return 'You don’t have access to that case. Choose another one from the list.';
    if (error?.status === 429) return 'Too many requests in a short time. Wait a moment, then try again.';
    if (/HTTP_|TRANSPORT_|INVALID_|MALFORMED_|MISSING_|NOT_AUTHORIZED|_ERROR|Internal error|\b[A-Z]+(?:_[A-Z0-9]+)+\b/.test(raw)) return 'That didn’t work. Try again, or send the details below to your workspace owner.';
    return readableText(raw || 'That didn’t work. Please try again.');
  }

  /* ---------- Small DOM helpers ---------- */
  function text(id, value) { const el = $(id); if (el) el.textContent = value ?? ''; }
  function node(tag, value, cls) { const n = document.createElement(tag); if (value !== undefined && value !== null) n.textContent = value; if (cls) n.className = cls; return n; }
  function observedTime(value) {
    const date = new Date(value);
    if (!value || Number.isNaN(date.getTime())) return 'time not recorded';
    return date.toLocaleString(undefined, {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short'});
  }
  function money(amount, currency) {
    const n = Number(amount);
    if (!Number.isFinite(n) || typeof currency !== 'string' || !/^[A-Z]{3}$/.test(currency)) return 'Price unavailable';
    try { return new Intl.NumberFormat(undefined, {style: 'currency', currency}).format(n / 100) + ` ${currency}`; }
    catch { return `${(n / 100).toFixed(2)} ${currency}`; }
  }
  const shortId = (id) => String(id ?? '').slice(-8);

  /* ---------- State ---------- */
  let current = null;
  let prereqs = null;
  let active = false;
  let creating = false;
  const cancelPending = new Set();
  const unresolved = new Map();
  const acknowledgedJobs = new Map();
  let selectionIntent = 0;
  let createIntent = 0;
  let createUnresolved = false;
  let capabilities = null;
  const stoppedRuns = new Set();
  let listSignature = null;
  let renderSignature = null;
  let refreshGeneration = 0;
  let focusSelectedRun = false;
  let timelineSource = 'all';
  let recordingKey = null;
  let lastVerdictKey = null;
  let messageKind = '';
  let polling = false;
  let workspaceReady = false;
  let landedOnce = false;

  /* ---------- Views ---------- */
  function setView(view) {
    document.body.dataset.view = view;
    $('boot').hidden = true;
    $('landing').hidden = view !== 'landing';
    $('login-panel').hidden = view !== 'login';
    $('offline-panel').hidden = view !== 'offline';
    $('workspace').hidden = view !== 'workspace';
    const home = document.querySelector('.nav-home'), desk = $('nav-desk');
    home.toggleAttribute('aria-current', view === 'landing'); if (view === 'landing') home.setAttribute('aria-current', 'page');
    desk.toggleAttribute('aria-current', view !== 'landing'); if (view !== 'landing') desk.setAttribute('aria-current', 'page');
    document.title = view === 'landing' ? 'CrashCart · Find out why a paid order wasn’t delivered'
      : view === 'login' ? 'Sign in · CrashCart' : 'Cases · CrashCart';
  }

  function updateLinks() {
    const runQuery = selected ? `?run=${enc(selected)}` : '';
    document.querySelectorAll('.brand, .footer-brand, .nav-home').forEach((link) => { link.href = `/?view=home${selected ? '&run=' + enc(selected) : ''}`; });
    for (const id of ['nav-desk', 'hero-open', 'closing-open', 'shop-back']) { const el = $(id); if (el) el.href = '/' + runQuery; }
    $('studio-link').href = '/studio/index.html' + runQuery;
    $('delivery-timing-link').href = '/deadlines/index.html' + runQuery;
    $('merchant-link').href = '/shop' + runQuery;
  }

  function showLogin(error) {
    workspaceReady = false;
    setView('login');
    if (error) showError(error, 'login');
    $('token').focus();
  }

  function showOffline(error) {
    setView('offline');
    text('offline-message', errorMessage(error) + ' Nothing was changed.');
    text('offline-code', String(error?.message ?? ''));
    $('offline-details').hidden = !error?.message;
  }

  /* ---------- Messages ---------- */
  function setMessage(value, tone = 'info', kind = '') {
    const el = $('message');
    el.textContent = value || '';
    el.dataset.tone = tone;
    messageKind = value ? kind : '';
    if (tone !== 'error') { $('error-details').hidden = true; text('error-code', ''); }
  }
  function clearMessage() { setMessage(''); }

  function showError(error, target = 'workspace') {
    const raw = String(error?.message ?? error ?? '');
    if (target === 'login') {
      text('login-message', errorMessage(error));
      text('login-error-code', raw); $('login-error-details').hidden = !raw;
      return;
    }
    if (target === 'new-run') {
      text('new-run-message', errorMessage(error));
      text('new-run-error-code', raw); $('new-run-error-details').hidden = !raw;
      return;
    }
    setMessage(errorMessage(error), 'error', 'error');
    text('error-code', raw); $('error-details').hidden = !raw;
  }

  function handleActionError(error) {
    if (error?.status === 401) { showLogin(error); return; }
    if (error?.uncertain) {
      setMessage('We didn’t get a clear answer, so we can’t tell whether that went through. The displayed records are the last successfully loaded view, which may be older. Refresh or check the saved status before another payment action.', 'warn', 'uncertain');
      text('error-code', String(error.message ?? '')); $('error-details').hidden = false;
      safeRefresh();
      return;
    }
    showError(error);
  }

  /* ---------- Selection ---------- */
  function selectRun(id, {focus = true} = {}) {
    if (!id) return;
    selectionIntent++;
    const picker = $('case-picker'); if (picker && window.matchMedia('(max-width: 860px)').matches) picker.open = false;
    if (id === selected && current && current.run.id === id && pageMode === 'desk') { $('run-title').focus(); return; }
    selected = id;
    pageMode = 'desk';
    history.replaceState(null, '', `/?run=${enc(id)}`);
    current = null; renderSignature = null; lastVerdictKey = null; refreshGeneration++;
    timelineSource = 'all';
    closeRecording(); recordingKey = null;
    hideCancelConfirm();
    clearMessage();
    text('copy-status', '');
    $('case').hidden = true; $('empty').hidden = true; $('loading-case').hidden = false;
    $('storefront').hidden = true; $('flow-banner').hidden = true; $('skip-case').hidden = true;
    focusSelectedRun = focus;
    markListSelection();
    updateLinks();
    syncActionButtons();
  }

  function markListSelection() {
    document.querySelectorAll('.run-row').forEach((row) => {
      if (row.dataset.runId === selected) row.setAttribute('aria-current', 'true'); else row.removeAttribute('aria-current');
    });
  }

  function showEmpty(kind = 'none') {
    current = null;
    $('case').hidden = true; $('loading-case').hidden = true; $('empty').hidden = false;
    $('storefront').hidden = true; $('flow-banner').hidden = true; $('skip-case').hidden = true;
    if (kind === 'missing') {
      text('empty-title', 'We couldn’t open that case');
      text('empty-copy', 'It may have been removed, or it isn’t shared with you. Choose another case from the list, or start a new check.');
    } else if (pageMode === 'shop') {
      text('empty-title', 'Choose a case to see its store page');
      text('empty-copy', 'The store page shows a case the way the buyer sees it. Pick a case from the list first.');
    } else {
      text('empty-title', 'Choose a case, or start a new check');
      text('empty-copy', 'A check follows one test purchase from payment to delivery and tells you whether the promise was kept.');
    }
    syncActionButtons();
  }

  /* ---------- Refresh ---------- */
  const identity = (value) => typeof value === 'string' && value.length > 0 && value === value.trim();
  const sameRecord = (event, run, purchase) => event?.run_id === run.id
    && (event.purchase_id == null || event.purchase_id === purchase.id)
    && (event.order_id == null || event.order_id === purchase.order_id);
  function validDetails(details, runId) {
    if (!details || typeof details !== 'object') return false;
    const {run, purchase, merchant, events} = details;
    return !!run && run.id === runId && identity(run.purchase_id)
      && !!purchase && identity(purchase.id) && purchase.id === run.purchase_id && purchase.run_id === runId
      && !!merchant && merchant.run_id === runId && merchant.purchase_id === purchase.id && merchant.order_id === purchase.order_id
      && Number.isInteger(merchant.ticket_count) && merchant.ticket_count >= 0 && Array.isArray(merchant.tickets)
      && merchant.tickets.length === merchant.ticket_count
      && merchant.tickets.every((ticket) => identity(ticket?.id) && ticket.purchase_id === purchase.id)
      && Array.isArray(events) && events.every((event) => event && sameRecord(event, run, purchase)
        && (event.event_type !== 'invariant_result' || correlatedVerdict(event, run, purchase)));
  }
  function correlatedVerdict(event, run, purchase) {
    const finding = event?.payload, ids = finding?.source_ids;
    return event?.run_id === run.id && event.purchase_id === purchase.id && event.order_id === purchase.order_id
      && !!ids && ids.run_id === run.id && ids.purchase_id === purchase.id && ids.order_id === purchase.order_id
      && ['PASS', 'FAIL', 'INCONCLUSIVE'].includes(finding.verdict);
  }

  async function refresh() {
    const generation = ++refreshGeneration, runId = selected;
    const [prereqData, list] = await Promise.all([api('/api/prerequisites'), api('/api/runs')]);
    if (generation !== refreshGeneration || runId !== selected) return false;
    createUnresolved = false;
    if (!creating) { $('new-run-submit').disabled = false; text('new-run-submit', 'Create check'); }
    prereqs = prereqData;
    renderServices(prereqData);
    renderList(Array.isArray(list.runs) ? list.runs : []);
    if (!runId) { showEmpty(); markSynced(); return true; }
    let details;
    try { details = await api(`/api/runs/${enc(runId)}`); }
    catch (error) {
      if (generation !== refreshGeneration || runId !== selected) return false;
      if (error.status === 404 || error.status === 403) { showEmpty('missing'); showError(error); return false; }
      throw error;
    }
    if (generation !== refreshGeneration || runId !== selected) return false;
    if (!validDetails(details, runId)) { current = null; renderSignature = null; $('case').hidden = true; syncActionButtons(); throw new ApiError('HTTP_RESPONSE_UNAVAILABLE', {uncertain: true}); }
    settleReadback(runId, details);
    const acknowledged = acknowledgedJobs.get(runId);
    if (!details.investigation_job && acknowledged) details.investigation_job = acknowledged;
    current = details;
    const next = JSON.stringify([pageMode, details.run.updated_at, details.run.state, details.run.cancel_requested, details.run.execution,
      details.purchase.updated_at, details.purchase.payment_state, details.purchase.payment_confirmed, details.merchant.ticket_count,
      details.merchant.tickets, details.merchant.observed_at, details.events.map((e) => e.id), details.recording, details.investigation_job]);
    if (next !== renderSignature) { renderSignature = next; render(details); }
    else syncActionButtons(details);
    if (messageKind === 'queued' && details.investigation_job) clearMessage();
    markSynced();
    return true;
  }

  async function safeRefresh() {
    try { return (await refresh()) === true; }
    catch (error) { if (error?.status === 401) showLogin(error); else markSyncFailed(); return false; }
  }

  function markSynced() {
    const now = new Date();
    text('sync-status', 'Updated ' + now.toLocaleTimeString(undefined, {hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short'}));
  }
  function markSyncFailed() { text('sync-status', 'Couldn’t refresh. Showing the last saved view.'); }

  /* ---------- Sidebar ---------- */
  function renderServices(data) {
    const list = $('prerequisites');
    list.replaceChildren();
    if (!data || typeof data !== 'object') return;
    for (const [key, value] of Object.entries(data)) {
      const configured = value?.configured === true;
      const li = node('li');
      const state = node('span', configured ? 'Details saved' : 'Needs setup', 'service-state');
      state.dataset.configured = String(configured);
      li.append(node('span', serviceLabel(key)), state);
      list.append(li);
    }
  }

  function renderList(runs) {
    text('run-count', String(runs.length));
    const signature = JSON.stringify([selected, runs.map((r) => [r.id, r.state, r.promise, r.mode, r.cancel_requested])]);
    if (signature === listSignature) { filterRuns(); return; }
    listSignature = signature;
    const focused = document.activeElement?.matches?.('.run-row') ? document.activeElement.dataset.runId : null;
    const list = $('runs');
    list.replaceChildren();
    if (!runs.length) {
      list.append(node('li', 'No cases yet. Start a new check to follow a test purchase from payment to delivery.', 'help'));
    }
    for (const run of runs) {
      const li = node('li');
      const button = node('button', null, 'run-row');
      button.type = 'button';
      button.dataset.runId = run.id;
      const stopped = run.cancel_requested || String(run.state).toLowerCase() === 'cancelled';
      button.dataset.tone = stopped ? '' : stateTone(run.state);
      if (run.id === selected) button.setAttribute('aria-current', 'true');
      const meta = node('span', null, 'run-meta');
      const dot = node('span', null, 'run-dot'); dot.setAttribute('aria-hidden', 'true');
      meta.append(dot, node('span', `${stopped ? 'Stopped' : statusLabel(run.state)} · ${modeInfo(run.mode).short} · ${shortId(run.id)}`));
      button.append(node('span', displayPromise(run.promise), 'run-promise'), meta);
      button.addEventListener('click', () => { selectRun(run.id); safeRefresh(); });
      li.append(button);
      list.append(li);
    }
    if (focused) [...document.querySelectorAll('.run-row')].find((b) => b.dataset.runId === focused)?.focus();
    filterRuns();
  }

  function filterRuns() {
    const query = $('run-search').value.trim().toLocaleLowerCase();
    const rows = [...document.querySelectorAll('.run-row')];
    let shown = 0;
    for (const row of rows) {
      const hide = !!query && !`${row.textContent} ${row.dataset.runId}`.toLocaleLowerCase().includes(query);
      row.parentElement.hidden = hide;
      if (!hide) shown++;
    }
    $('search-status').hidden = !query;
    text('search-status', shown ? `Showing ${shown} of ${rows.length}` : 'No cases match that search.');
  }

  /* ---------- Case helpers ---------- */
  const isStopped = (run) => !!run.cancel_requested || String(run.state).toLowerCase() === 'cancelled' || stoppedRuns.has(run.id);
  const jobActive = (job) => job?.state === 'PENDING' || job?.state === 'RUNNING';
  function latestVerdict(events, run, purchase) {
    return [...events].reverse().find((e) => e.event_type === 'invariant_result' && correlatedVerdict(e, run, purchase)) || null;
  }
  const providerRead = (events) => [...events].reverse().find((e) => e.event_type === 'independent_order_read') || null;
  const isResumable = (p) => !!p.order_id && p.payment_state === 'AWAITING_APPROVAL' && p.payment_confirmed !== 1;
  const returnMatches = (p) => pageMode === 'return' && !!returnToken && p.order_id === returnToken;
  function oneTicket(merchant, purchase) {
    if (merchant.ticket_count !== 1 || !Array.isArray(merchant.tickets) || merchant.tickets.length !== 1) return null;
    const t = merchant.tickets[0];
    if (!t || !t.id || t.purchase_id !== purchase.id) return null;
    return t;
  }

  /* ---------- Buttons ---------- */
  function syncActionButtons(data = current) {
    const ids = ['checkout', 'capture', 'reconcile', 'investigate', 'cancel-run', 'shop-checkout'];
    const matched = !!data && data.run.id === selected;
    $('busy').hidden = !active && !(matched && jobActive(data.investigation_job));
    if (!matched) { for (const id of ids) $(id).disabled = true; return; }
    const {run, purchase} = data;
    const stopped = isStopped(run);
    const running = jobActive(data.investigation_job) || run.execution?.active === true || (!run.execution && String(run.state).toLowerCase() === 'running');
    const locked = active || running || stopped || cancelPending.has(run.id);
    const resumable = isResumable(purchase);

    const checkoutLabel = resumable ? 'Resume test checkout' : 'Start test checkout';
    text('checkout', checkoutLabel);
    const awaitingReadback = unresolved.has(run.id);
    const checkoutDisabled = awaitingReadback || locked || purchase.payment_confirmed === 1 || (!!purchase.order_id && !resumable);
    $('checkout').disabled = checkoutDisabled;
    text('shop-checkout', resumable ? 'Continue to PayPal (test)' : 'Pay with PayPal (test)');
    $('shop-checkout').disabled = checkoutDisabled;

    const showCapture = returnMatches(purchase) && purchase.payment_confirmed !== 1;
    $('capture').hidden = !showCapture;
    $('capture').disabled = awaitingReadback || locked || !showCapture;

    $('reconcile').disabled = locked || !purchase.order_id;
    $('investigate').disabled = awaitingReadback || locked || !!data.investigation_job;
    text('investigate', data.investigation_job ? 'Assistant asked' : 'Ask the assistant');

    $('cancel-run').disabled = stopped || cancelPending.has(run.id);
    text('cancel-run', stopped ? 'Case stopped' : cancelPending.has(run.id) ? 'Stopping…' : 'Stop this case');
    if (stopped) hideCancelConfirm();

    // Highlight the single most useful next action.
    for (const id of ['checkout', 'capture', 'reconcile', 'investigate']) $(id).classList.remove('is-primary-step');
    const primary = recommendedAction(data);
    if (primary && !$(primary).disabled && !$(primary).hidden) $(primary).classList.add('is-primary-step');
  }

  function recommendedAction(data) {
    const {run, purchase, events} = data;
    if (isStopped(run) || jobActive(data.investigation_job)) return null;
    if (returnMatches(purchase) && purchase.payment_confirmed !== 1) return 'capture';
    if (!purchase.order_id || isResumable(purchase)) return 'checkout';
    const verdict = latestVerdict(events, run, purchase);
    if (!verdict || verdict.payload.verdict === 'INCONCLUSIVE') return 'reconcile';
    if (verdict.payload.verdict === 'FAIL' && !data.investigation_job) return 'investigate';
    return null;
  }

  /* ---------- Render ---------- */
  function render(data) {
    const {run, purchase, merchant, events} = data;
    const stopped = isStopped(run);
    $('loading-case').hidden = true; $('empty').hidden = true; $('case').hidden = false; $('skip-case').hidden = false;
    $('case').dataset.runId = run.id;

    const mode = modeInfo(run.mode);
    text('mode-ribbon', mode.label); $('mode-ribbon').dataset.tone = mode.tone;
    text('run-title', displayPromise(run.promise));
    text('run-state', stopped ? 'Stopped' : statusLabel(run.state));
    $('run-state').dataset.tone = stopped ? '' : stateTone(run.state);
    const version = run.fault?.merchant === 'healthy' ? 'Repaired store' : run.fault?.merchant === 'defective' ? 'Current store' : 'Store version not recorded';
    const delay = run.fault?.kind === 'event_delay' && Number.isInteger(run.fault.delay_seconds) ? ` (${run.fault.delay_seconds}s)` : '';
    text('provenance', `${faultLabel(run.fault?.kind)}${delay} · ${version}`);
    text('run-short', shortId(run.id));
    text('run-id', run.id);
    text('invariant', 'Promise: one $29 workshop ticket within 60 seconds of a confirmed payment.');

    renderBudget(run.budget);
    renderVerdict(data);
    renderProgress(data);
    renderNext(data);
    renderFlow(data);
    renderStore(data);
    renderWitnesses(data);
    renderAssistant(data);
    renderTimeline(run.id, events);
    renderRecords(data);
    syncActionButtons(data);
    syncRecoveryNotice(data);

    if (focusSelectedRun && !$('workspace').hidden) { focusSelectedRun = false; $('run-title').focus({preventScroll: false}); }
  }

  function renderBudget(budget) {
    const parts = [];
    if (Number.isInteger(budget?.max_attempts) && budget.max_attempts > 0) parts.push(`${budget.max_attempts} steps`);
    if (Number.isFinite(budget?.max_seconds) && budget.max_seconds > 0) parts.push(`up to ${budget.max_seconds} seconds`);
    if (Number.isInteger(budget?.max_model_calls) && budget.max_model_calls > 0) parts.push(`${budget.max_model_calls} model calls`);
    text('case-budget', parts.length ? `Assistant limits for this case: ${parts.join(', ')}.` : 'Assistant limits for this case weren’t recorded.');
  }

  function renderVerdict({run, purchase, events}) {
    const result = latestVerdict(events, run, purchase);
    const panel = $('verdict-panel');
    const verdict = result ? result.payload.verdict : 'NONE';
    const key = `${run.id}:${result?.id ?? 'none'}`;
    panel.classList.toggle('is-new', lastVerdictKey !== null && lastVerdictKey !== key && !!result);
    lastVerdictKey = key;
    panel.dataset.verdict = verdict;
    if (result) {
      text('verdict-title', verdictTitles.get(verdict));
      const sig = result.payload.signature, reason = result.payload.reason;
      text('verdict', verdictReasons.get(sig) || (reason ? errorMessage(reason) : 'No reason was recorded with this result.'));
    } else {
      text('verdict-title', 'Not checked yet');
      text('verdict', purchase.order_id ? 'Check payment and delivery to see whether the promise was kept.' : 'Start the test checkout. Once there’s a payment, CrashCart can check delivery.');
    }
  }

  function setStep(step, status, label) {
    const li = document.querySelector(`#progress [data-step="${step}"]`);
    li.dataset.status = status;
    li.querySelector('.progress-state').textContent = label;
    if (status === 'current') li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
  }

  function renderProgress({run, purchase, events, investigation_job: job}) {
    if (!purchase.order_id) setStep('checkout', 'current', 'Not started');
    else if (isResumable(purchase)) setStep('checkout', 'current', 'Waiting for buyer approval');
    else setStep('checkout', 'done', 'Created');

    if (purchase.payment_confirmed === 1) setStep('payment', 'done', 'Confirmed by PayPal');
    else if (!purchase.order_id) setStep('payment', 'pending', 'Not yet');
    else if (providerRead(events)) setStep('payment', 'warn', 'Not confirmed yet');
    else setStep('payment', isResumable(purchase) ? 'pending' : 'current', 'Not confirmed yet');

    const result = latestVerdict(events, run, purchase);
    if (result?.payload.verdict === 'PASS') setStep('delivery', 'ok', 'Promise kept');
    else if (result?.payload.verdict === 'FAIL') setStep('delivery', 'fail', 'Promise broken');
    else if (result) setStep('delivery', 'warn', 'More evidence needed');
    else setStep('delivery', purchase.payment_confirmed === 1 ? 'current' : 'pending', 'Not checked');

    if (!job) setStep('assistant', 'pending', 'Not asked');
    else if (job.state === 'PENDING') setStep('assistant', 'current', 'Queued');
    else if (job.state === 'RUNNING') setStep('assistant', 'current', 'Working');
    else if (job.state === 'COMPLETED') setStep('assistant', 'done', 'Finished');
    else if (job.state === 'CANCELLED') setStep('assistant', 'warn', 'Stopped');
    else if (job.state === 'FAILED') setStep('assistant', 'warn', 'Couldn’t finish');
    else setStep('assistant', 'pending', 'Status unknown');
  }

  function renderNext(data) {
    const {run, purchase, events} = data;
    const job = data.investigation_job;
    const result = latestVerdict(events, run, purchase);
    let copy;
    if (isStopped(run)) copy = 'This case is stopped. Its records stay available to read and download. To test again, start a new check.';
    else if (jobActive(job)) copy = 'The assistant is working through this case in the background. You can leave this page; its progress is saved.';
    else if (returnMatches(purchase) && purchase.payment_confirmed !== 1) copy = 'If you approved the payment on PayPal, confirm it here. CrashCart never confirms a payment for you, and it checks with PayPal first.';
    else if (!purchase.order_id) copy = 'Start the test checkout. You’ll approve the payment yourself on PayPal’s test site, then come back here to confirm it.';
    else if (isResumable(purchase)) copy = 'This checkout is waiting for approval on PayPal. Resume it to finish approving, or check its status first.';
    else if (purchase.payment_confirmed !== 1) copy = 'Check the payment with PayPal before doing anything else. A missing reply doesn’t mean the payment failed.';
    else if (!result) copy = 'The payment is confirmed. Check delivery to see whether the ticket arrived on time.';
    else if (result.payload.verdict === 'FAIL') copy = job ? 'The promise was broken. The assistant’s notes are below, and the records are ready to download.' : 'The promise was broken. Ask the assistant to trace where the delivery went wrong, or download the records.';
    else if (result.payload.verdict === 'PASS') copy = 'The promise was kept. The records are ready to download if you need them.';
    else copy = 'There isn’t enough evidence yet. Check payment and delivery again, ideally once the 60-second window has closed.';
    text('next-copy', copy);
    const returnedElsewhere = pageMode === 'return' && !returnMatches(purchase);
    $('capture-help').hidden = !returnedElsewhere;
    text('capture-help', returnedElsewhere ? 'This return link doesn’t match the checkout saved for this case, so there’s no payment to confirm from here.' : '');
  }

  function renderFlow({purchase}) {
    const banner = $('flow-banner');
    let title = '', body = '', tone = '';
    if (pageMode === 'return') {
      if (!returnMatches(purchase)) {
        tone = 'warn'; title = 'This return link doesn’t match this case';
        body = 'The checkout reference in the link isn’t the one saved for this case, so nothing can be confirmed from here. Your saved records haven’t changed.';
      } else if (purchase.payment_confirmed === 1) {
        tone = 'ok'; title = 'This payment is already confirmed';
        body = 'There’s nothing more to confirm. See below for whether the ticket arrived.';
      } else {
        title = 'You’re back from PayPal';
        body = 'Coming back here doesn’t confirm anything on its own. If you approved the payment, use Confirm test payment below.';
      }
    } else if (pageMode === 'cancel') {
      tone = 'warn'; title = 'Returned through the cancellation link';
      body = purchase.payment_confirmed === 1
        ? 'The saved records confirm this payment. This cancellation link does not undo it or decide whether the ticket arrived; check the delivery records below.'
        : 'This link does not establish whether payment completed. Check the saved order with PayPal before deciding what the customer is owed.';
    }
    banner.hidden = !title;
    banner.dataset.tone = tone;
    banner.replaceChildren();
    if (title) banner.append(node('h2', title), node('p', body));
  }

  function renderStore({purchase, merchant}) {
    const show = pageMode === 'shop';
    $('storefront').hidden = !show;
    if (!show) return;
    text('store-price', money(purchase.amount, purchase.currency));
    let status = '';
    if (purchase.payment_confirmed === 1) status = oneTicket(merchant, purchase) ? 'Paid. Your ticket is ready.' : 'Paid. No ticket has been issued yet.';
    else if (isResumable(purchase)) status = 'Waiting for approval on PayPal.';
    text('store-status', status);
  }

  function renderWitnesses(data) {
    const {purchase, merchant, events} = data;

    // Checkout page (browser observation; never proof of payment)
    const customer = [...events].reverse().find((e) => e.source === 'browser' && e.payload) || null;
    const p = customer?.payload || {};
    const browserPath = typeof p.url_path === 'string' ? p.url_path : '';
    const page = new Map([['/', 'Workspace'], ['/shop', 'Store page'], ['/checkoutnow', 'PayPal test checkout'], ['/return', 'Back from PayPal'], ['/cancel', 'Returned through cancellation link']]).get(browserPath) || 'Recorded page';
    const kind = new Map([['LOCAL_BROWSER', 'Your browser'], ['KERNEL', 'Remote browser']]).get(p.browser_kind) || (p.browser_kind ? 'Unrecognised browser' : 'Browser not recorded');
    text('customer-title', customer ? page : 'Nothing recorded yet');
    const prior = new Map([['PRIOR_SANDBOX_EXECUTION', 'Saved from an earlier test payment'], ['PRIOR_LOCAL_TEST_EXECUTION', 'Saved from an earlier run with example data']]).get(p.provenance);
    const seen = prior ? customer.event_time : customer?.observed_at;
    text('browser-source', customer ? `${kind} · ${prior ? prior + ' · seen ' + observedTime(seen) + ' · imported ' + observedTime(customer.observed_at) : 'seen ' + observedTime(seen)}` : '');
    text('customer-detail', customer
      ? (typeof p.visible_text === 'string' && p.visible_text ? p.visible_text
        : p.observed_fields && Object.keys(p.observed_fields).length ? 'No separate page message was recorded. The labels below were read from the saved checkout.'
        : 'The page text wasn’t captured. Visiting a page doesn’t confirm approval or delivery.')
      : 'What the buyer sees is recorded after each step. A page message is a clue, not proof of payment.');
    const fields = $('customer-fields'); fields.replaceChildren();
    for (const [key, label] of [['run_state', 'Checkout state'], ['provider_title', 'Payment shown'], ['merchant_title', 'Ticket shown'], ['verdict', 'Delivery message']]) {
      if (typeof p.observed_fields?.[key] === 'string' && p.observed_fields[key]) fields.append(node('dt', label), node('dd', p.observed_fields[key]));
    }
    fields.hidden = !fields.childElementCount;
    renderBrowserExecution(data);
    renderRecording(data);

    // PayPal
    const read = providerRead(events);
    text('provider-title', read ? (purchase.payment_confirmed === 1 ? 'Payment confirmed' : 'Payment not confirmed yet') : 'Not checked with PayPal yet');
    text('provider-detail', read
      ? `${statusLabel(purchase.payment_state)} · checked ${observedTime(read.observed_at)}. ${purchase.payment_confirmed === 1 ? money(purchase.amount, purchase.currency) + '.' : ''}`.trim()
      : purchase.order_id ? 'Use Check payment and delivery to ask PayPal directly. A missing reply doesn’t mean the payment failed.' : 'There’s no checkout yet, so there’s nothing to check.');

    // Store
    const ticket = oneTicket(merchant, purchase);
    text('merchant-title', merchant.known ? `${merchant.ticket_count} ${merchant.ticket_count === 1 ? 'ticket' : 'tickets'}` : 'Purchase not found in the store');
    text('merchant-detail', merchant.observed_at ? `${statusLabel(merchant.status)} · checked ${observedTime(merchant.observed_at)}.` : 'The store hasn’t been checked yet.');
    $('ticket-card').hidden = !ticket;
    if (ticket) {
      text('ticket-id', ticket.id);
      text('ticket-time', `Issued ${observedTime(ticket.created_at)}`);
    }
  }

  function savedBrowserExecution(data) {
    const obs = [...data.events].reverse().find((e) => e.source === 'browser' && e.event_type === 'kernel_recorded_observation' && e.payload?.browser_kind === 'KERNEL');
    return obs ? {present: true, ...(obs.payload.browser_execution || {})} : null;
  }

  function renderBrowserExecution(data) {
    const execution = savedBrowserExecution(data), notice = $('browser-execution');
    notice.hidden = !execution;
    if (!execution) return;
    const summary = new Map([['OBSERVED', 'Remote browser session recorded.'], ['FAILED', 'The remote browser session couldn’t finish.'], ['INCOMPLETE', 'The remote browser session ended early.'], ['CANCELLED', 'The remote browser session was stopped.'], ['TIMED_OUT', 'The remote browser session ran out of time.']]).get(execution.status) || 'The outcome of this browser session wasn’t recorded.';
    const issue = execution.status === 'OBSERVED' ? '' : new Map([['checkout_step_failed', 'A checkout step couldn’t be completed.'], ['time_limit', 'It hit its time limit.'], ['connection_lost', 'It lost its connection.'], ['interrupted', 'It was interrupted.'], ['identity_check_failed', 'It couldn’t match the expected checkout.'], ['access_failed', 'It couldn’t open the checkout.']]).get(execution.issue) || '';
    const partial = execution.recording_state === 'SAVED_PARTIAL';
    text('browser-execution', [summary, issue, partial ? 'Only part of the checkout was recorded.' : '', 'Payment and tickets are checked separately.'].filter(Boolean).join(' '));
    notice.dataset.tone = execution.status === 'OBSERVED' && !partial ? 'neutral' : 'warning';
  }

  /* ---------- Recording ---------- */
  function closeRecording(restoreFocus = false) {
    const video = $('customer-recording-video');
    video.pause(); video.removeAttribute('src'); video.load();
    $('customer-recording-panel').hidden = true;
    $('watch-recording').setAttribute('aria-expanded', 'false');
    if (restoreFocus && !$('watch-recording').hidden) $('watch-recording').focus();
  }

  function renderRecording(data) {
    const execution = savedBrowserExecution(data);
    const partial = execution?.recording_state === 'SAVED_PARTIAL';
    const saved = data.recording, available = saved?.availability === 'available';
    const key = `${data.run.id}:${saved?.sha256 || saved?.availability || 'none'}`;
    if (recordingKey !== key) { closeRecording(); recordingKey = key; }
    $('watch-recording').hidden = !available;
    text('watch-recording', partial ? 'Watch partial recording' : 'Watch saved checkout');
    text('saved-checkout-title', partial ? 'Saved checkout (partial)' : 'Saved checkout');
    text('recording-privacy', partial
      ? 'A partial recording from an earlier test checkout, private to this workspace. It may stop before the payment or ticket outcome. Watching it doesn’t make a payment.'
      : 'Recorded during an earlier test checkout, private to this workspace. Watching it doesn’t make a payment.');
    const note = $('customer-recording-note');
    note.hidden = !saved;
    text('customer-recording-note', available ? (partial ? 'Partial recording available: the session ended early.' : 'A recording of this checkout is available.')
      : saved?.availability === 'disabled' ? 'Recordings are turned off in this workspace.' : 'No recording is attached to this case.');
  }

  /* ---------- Assistant ---------- */
  function jobMessage(job) {
    if (!job) return '';
    const simulated = job.result?.model_mode === 'LOCAL_TEST';
    const prefix = simulated ? 'Simulated assistant with example data. ' : '';
    if (job.state === 'PENDING') return 'The assistant is queued. You can leave this page; it will pick up the case and save its progress.';
    if (job.state === 'RUNNING') return 'The assistant is working through this case in the background. You can leave this page.';
    if (job.state === 'CANCELLED') return 'The assistant was stopped. Everything recorded so far is saved.';
    if (job.state === 'FAILED') return prefix + 'The assistant couldn’t finish. Saved records are still available. Ask your workspace owner to check its connection before you start a new check.';
    if (job.state === 'COMPLETED') {
      const status = job.result?.status;
      if (status === 'COMPLETED') return prefix + 'The assistant finished. Its steps are in Activity. The payment and ticket records decide the result, not the assistant.';
      if (status === 'BUDGET_EXHAUSTED') return prefix + 'The assistant reached its limit before finishing. Everything it found so far is saved.';
      if (status === 'INTERRUPTED') return prefix + 'The assistant was interrupted before it finished. It won’t retry on its own. Saved records are still available.';
      return prefix + 'The assistant stopped without a full answer. Saved records are still available.';
    }
    return 'We can’t tell what the assistant is doing right now. Saved payment and ticket records are still available.';
  }

  function jobFinding(job, run, purchase) {
    const result = job?.result, finding = result?.final_verdict, ids = finding?.source_ids;
    if (job?.state !== 'COMPLETED' || result?.status !== 'COMPLETED' || !ids || ids.run_id !== run.id || ids.purchase_id !== purchase.id || ids.order_id !== purchase.order_id || !['PASS', 'FAIL', 'INCONCLUSIVE'].includes(finding.verdict)) return '';
    const description = verdictReasons.get(finding.signature);
    return description ? `What it found: ${description}` : '';
  }

  function renderAssistant({run, purchase, investigation_job: job}) {
    const note = $('investigator-note');
    note.dataset.mode = job?.result?.model_mode || 'UNKNOWN';
    let message;
    if (job) message = jobMessage(job);
    else if (run.execution?.state === 'interrupted') message = 'The assistant stopped before its reply could be confirmed. It won’t retry on its own. Saved records are still available.';
    else {
      const ready = prereqs?.model?.configured === true;
      message = 'Not asked yet. When you ask, the assistant reads the payment and store records in the background and suggests where the delivery went wrong. You can stop it at any time.'
        + (ready ? '' : ' Its connection hasn’t been set up in this workspace yet.');
    }
    text('investigator-note', message);
    const finding = job ? jobFinding(job, run, purchase) : '';
    $('investigator-finding').hidden = !finding;
    text('investigator-finding', finding);
  }

  /* ---------- Activity ---------- */
  function renderTimeline(runId, allEvents) {
    const total = allEvents.length;
    const events = allEvents.filter((e) => timelineSource === 'all' || e.source === timelineSource || (timelineSource === 'investigator' && e.source === 'model'));
    text('trace-count', `${events.length} of ${total} ${total === 1 ? 'entry' : 'entries'}`);
    document.querySelectorAll('.trace-filters button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.source === timelineSource)));
    const timeline = $('timeline');
    const firstPaint = timeline.dataset.timelineRunId !== runId;
    if (firstPaint) { timeline.replaceChildren(); timeline.dataset.timelineRunId = runId; }
    if (!events.length) {
      timeline.replaceChildren(node('p', total ? 'Nothing recorded from this source.' : 'No activity yet. Creating a check doesn’t take a payment; activity appears once you start the test checkout.', 'help'));
      return;
    }
    timeline.querySelector(':scope > .help')?.remove();
    const existing = new Map([...timeline.querySelectorAll(':scope > .event')].map((row) => [row.dataset.eventId, row]));
    for (const [index, e] of events.entries()) {
      const id = String(e.id);
      let row = existing.get(id);
      if (!row) {
        row = node('details', null, 'event' + (firstPaint ? '' : ' is-new'));
        row.dataset.eventId = id;
        row.dataset.source = e.source;
        const summary = node('summary', null, 'event-head');
        const time = node('time', observedTime(e.observed_at), 'event-time');
        if (e.observed_at) time.dateTime = e.observed_at;
        summary.append(node('span', sourceLabel(e.source), 'event-source'), node('strong', eventLabel(e.event_type)), time);
        const pre = node('pre', JSON.stringify({id: e.id, run_id: e.run_id, purchase_id: e.purchase_id, order_id: e.order_id, operation_id: e.operation_id, event_time: e.event_time, observed_at: e.observed_at, caused_by: e.caused_by, payload: e.payload}, null, 2));
        pre.tabIndex = 0;
        pre.setAttribute('aria-label', `Original record: ${eventLabel(e.event_type)}`);
        row.append(summary, pre);
      }
      if (timeline.children[index] !== row) timeline.insertBefore(row, timeline.children[index] || null);
      existing.delete(id);
    }
    for (const row of existing.values()) row.remove();
  }

  /* ---------- Records ---------- */
  function renderRecords(data) {
    const {run, purchase, merchant, events} = data;
    $('export').href = `/api/runs/${enc(run.id)}/export`;
    const result = latestVerdict(events, run, purchase);
    const eligible = run.fault?.merchant === 'defective' && ['response_loss', 'process_interrupt'].includes(run.fault?.kind)
      && purchase.payment_confirmed === 1 && merchant.ticket_count === 0 && result?.payload.verdict === 'FAIL'
      && !!providerRead(events) && events.some((e) => e.event_type === 'capture_transport_response');
    $('regression').hidden = !eligible;
    $('regression').href = `/api/runs/${enc(run.id)}/regression.zip`;
    text('regression-note', eligible ? 'If the replay test can’t be built from these records, the download explains why.'
      : 'A replay test becomes available when a lost PayPal reply or a stopped store leaves a confirmed payment without its ticket.');
    $('merchant-link').href = `/shop?run=${enc(run.id)}`;
    $('studio-link').href = `/studio/index.html?run=${enc(run.id)}`;
    $('delivery-timing-link').href = `/deadlines/index.html?run=${enc(run.id)}`;
    const browser = [...events].reverse().find((e) => e.source === 'browser') || null;
    text('journal', JSON.stringify({
      run: {id: run.id, promise: run.promise, state: run.state, mode: run.mode, fault: run.fault, budget: run.budget, execution: run.execution || null},
      assistant_job: data.investigation_job || null,
      purchase_id: purchase.id, order_id: purchase.order_id, capture_id: purchase.capture_id, payment_state: purchase.payment_state,
      merchant_status: merchant.status, browser, delivery_result: result?.payload || null, operations: data.operations,
    }, null, 2));
  }

  function syncRecoveryNotice(data = current) {
    if (!data || data.run.id !== selected) return;
    const {run, purchase, merchant} = data;
    if (['response_loss', 'process_interrupt'].includes(run.fault?.kind) && purchase.payment_confirmed === 1 && merchant.ticket_count === 1
      && ['', 'capture', 'uncertain', 'returned'].includes(messageKind)) {
      setMessage('Payment confirmed, and the store recovered: one workshop ticket was issued.', 'info', 'recovered');
    }
  }

  /* ---------- Observations ---------- */
  async function observe(actionName, runId = selected) {
    if (!current || current.run.id !== runId || runId !== selected || isStopped(current.run)) return;
    const visible = [$('run-state').textContent, $('verdict-title').textContent, $('verdict').textContent, $('merchant-title').textContent, $('message').textContent]
      .filter(Boolean).join(' | ').slice(0, 4000);
    try {
      await api(`/api/runs/${enc(runId)}/observation`, {browser_kind: 'LOCAL_BROWSER', url_path: location.pathname.slice(0, 4000), visible_text: visible, action: actionName});
    } catch { /* An unsaved observation never blocks the merchant's next step. */ }
  }

  /* ---------- Actions and authoritative readback ---------- */
  function mutationEntry(runId, kind) {
    if (!unresolved.has(runId)) unresolved.set(runId, new Map());
    const entry = {acknowledged: false, uncertain: false};
    unresolved.get(runId).set(kind, entry);
    return entry;
  }
  function settleReadback(runId, details) {
    const purchase = details.purchase, operations = Array.isArray(details.operations) ? details.operations : [];
    // Reconstructed from durable operations too: a reload is not permission to
    // repeat a payment whose earlier transport outcome remains unresolved.
    for (const [kind, semantic] of [['order', 'order.create'], ['capture', 'order.capture']]) {
      const pending = operations.find((op) => op.semantic_key === semantic && ['INTENDED', 'PENDING', 'IN_FLIGHT', 'UNRESOLVED'].includes(op.state));
      if (pending && (kind === 'order' ? !purchase.order_id : purchase.payment_confirmed !== 1)) {
        if (!unresolved.get(runId)?.has(kind)) mutationEntry(runId, kind).uncertain = true;
      }
    }
    const entries = unresolved.get(runId);
    if (entries) {
      for (const [kind] of entries) {
        const failed = operations.some((op) => op.semantic_key === (kind === 'order' ? 'order.create' : 'order.capture') && op.state === 'FAILED');
        if ((kind === 'order' && (identity(purchase.order_id) || failed))
          || (kind === 'capture' && (purchase.payment_confirmed === 1 || failed))
          || kind === 'reconcile' || (kind === 'investigation-job' && details.investigation_job)) entries.delete(kind);
      }
      if (!entries.size) unresolved.delete(runId);
    }
    if (details.investigation_job) acknowledgedJobs.delete(runId);
  }
  async function mutate(runId, kind, body) {
    const entry = mutationEntry(runId, kind);
    try {
      const result = await api(`/api/runs/${enc(runId)}/${kind}`, body);
      entry.acknowledged = true;
      if (kind === 'investigation-job' && identity(result.job?.id) && ['PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED'].includes(result.job.state)
        && !stoppedRuns.has(runId) && !cancelPending.has(runId)) {
        acknowledgedJobs.set(runId, result.job);
        if (current?.run.id === runId && selected === runId && !isStopped(current.run) && !current.investigation_job) {
          current.investigation_job = result.job; renderAssistant(current); syncActionButtons();
        }
      }
      return result;
    } catch (error) {
      entry.uncertain = error?.uncertain === true;
      if (!entry.uncertain) {
        unresolved.get(runId)?.delete(kind);
        if (!unresolved.get(runId)?.size) unresolved.delete(runId);
      }
      throw error;
    }
  }
  async function action(fn) {
    if (active || !selected || !current || current.run.id !== selected) return;
    const runId = selected;
    active = true; clearMessage(); syncActionButtons();
    try { await fn(runId); }
    catch (error) { if (stillMine(runId)) handleActionError(error); }
    finally { active = false; syncActionButtons(); }
  }
  const stillMine = (runId) => selected === runId && !stoppedRuns.has(runId) && !cancelPending.has(runId) && !(current?.run.id === runId && isStopped(current.run));

  function safeApprovalUrl(value) {
    if (typeof value !== 'string' || !value) return null;
    try {
      const url = new URL(value, location.href);
      if ((url.protocol === 'https:' && (url.hostname === 'sandbox.paypal.com' || url.hostname.endsWith('.sandbox.paypal.com'))) || url.origin === location.origin) return url.href;
    } catch { /* fall through */ }
    return null;
  }
  async function startCheckout(runId) {
    if (unresolved.has(runId)) return;
    let order;
    try { order = await mutate(runId, 'order', {}); }
    catch (error) { await safeRefresh(); await observe('checkout_unavailable', runId); throw error; }
    const fresh = await safeRefresh();
    if (!stillMine(runId)) return;
    if (!fresh || unresolved.has(runId)) { setMessage('The checkout request was received, but we could not refresh its saved status. Refresh the records before continuing; do not start another checkout.', 'warn', 'uncertain'); return; }
    await observe('leaving_for_buyer_approval', runId);
    if (!stillMine(runId)) return;
    const url = safeApprovalUrl(order.approval_url);
    if (url) { setMessage('Taking you to PayPal to approve the test payment…'); location.assign(url); }
    else setMessage('The saved checkout was checked. There’s no new approval to give.');
  }
  $('checkout').addEventListener('click', () => action(startCheckout));
  $('shop-checkout').addEventListener('click', () => action(startCheckout));
  $('capture').addEventListener('click', () => action(async (runId) => {
    if (!current || current.purchase.order_id !== returnToken || unresolved.has(runId)) return;
    let result;
    try { result = await mutate(runId, 'capture', {order_id: returnToken}); }
    catch (error) {
      await safeRefresh();
      if (error.uncertain && stillMine(runId)) {
        setMessage('The payment reply was lost, so the outcome is uncertain. Refresh the saved records or check payment and delivery before considering another payment action.', 'warn', 'uncertain');
        text('error-code', String(error.message ?? '')); $('error-details').hidden = false;
        return;
      }
      throw error;
    }
    const fresh = await safeRefresh();
    if (!stillMine(runId)) return;
    if (!fresh) { setMessage('The payment request received a reply, but the saved view could not be refreshed. Do not repeat the payment; refresh or check its status.', 'warn', 'uncertain'); return; }
    setMessage(result.message ? readableText(result.message) : 'Payment request answered. The saved payment and delivery records are shown below.', 'info', 'capture');
    syncRecoveryNotice(); await observe('capture_result', runId); await safeRefresh();
  }));
  $('reconcile').addEventListener('click', () => action(async (runId) => {
    await mutate(runId, 'reconcile', {});
    const fresh = await safeRefresh();
    if (!stillMine(runId)) return;
    if (!fresh) { setMessage('The status check received a reply, but we could not refresh the saved view. The displayed records may be older; refresh before another payment action.', 'warn', 'uncertain'); return; }
    setMessage('Checked with PayPal and the store. The saved result above was refreshed.', 'info', 'checked');
    syncRecoveryNotice(); await observe('reconciliation_result', runId); await safeRefresh();
  }));
  $('investigate').addEventListener('click', () => action(async (runId) => {
    if (unresolved.has(runId)) return;
    await mutate(runId, 'investigation-job', {});
    if (!stillMine(runId)) return;
    const fresh = await safeRefresh();
    if (!stillMine(runId)) return;
    if (!fresh) setMessage('The assistant request was saved. Its last acknowledged status is shown; progress could not be refreshed. No second request will be sent automatically.', 'warn', 'queued');
    else clearMessage(); // Persisted assistant status is rendered in its own panel.
  }));

  /* Stop: stays available while other work runs, with a confirmation step. */
  function hideCancelConfirm() { $('cancel-confirm').hidden = true; $('cancel-run').setAttribute('aria-expanded', 'false'); }
  $('cancel-run').addEventListener('click', () => {
    if (!current || current.run.id !== selected || isStopped(current.run)) return;
    const open = $('cancel-confirm').hidden;
    $('cancel-confirm').hidden = !open;
    $('cancel-run').setAttribute('aria-expanded', String(open));
    if (open) $('cancel-yes').focus();
  });
  $('cancel-no').addEventListener('click', () => { hideCancelConfirm(); $('cancel-run').focus(); });
  $('cancel-confirm').addEventListener('keydown', (e) => { if (e.key === 'Escape') { hideCancelConfirm(); $('cancel-run').focus(); } });
  $('cancel-yes').addEventListener('click', async () => {
    if (!current || current.run.id !== selected || cancelPending.has(selected)) return;
    const runId = current.run.id;
    cancelPending.add(runId);
    hideCancelConfirm();
    syncActionButtons();
    try {
      await api(`/api/runs/${enc(runId)}/cancel`, {});
      stoppedRuns.add(runId);
      await safeRefresh();
      if (selected === runId) setMessage('Case stopped. No more actions will run here, and every saved record is still available. Stopping doesn’t refund or reverse a payment.', 'info', 'stopped');
    } catch (error) {
      if (selected === runId) handleActionError(error);
    } finally {
      cancelPending.delete(runId);
      syncActionButtons();
      if (selected === runId) $('cancel-run').focus();
    }
  });

  /* ---------- Ticket copy ---------- */
  $('copy-ticket').addEventListener('click', async () => {
    const ticket = current && current.run.id === selected ? oneTicket(current.merchant, current.purchase) : null;
    if (!ticket) return;
    const runId = current.run.id;
    try { await navigator.clipboard.writeText(ticket.id); if (selected === runId) text('copy-status', 'Ticket reference copied.'); }
    catch { if (selected === runId) text('copy-status', 'Copying isn’t available here. Select the reference above to copy it.'); }
  });

  /* ---------- Recording controls ---------- */
  $('watch-recording').addEventListener('click', () => {
    if (!current || current.run.id !== selected || current.recording?.availability !== 'available') return;
    if (!$('customer-recording-panel').hidden) { closeRecording(true); return; }
    const video = $('customer-recording-video');
    video.autoplay = false; video.preload = 'none';
    video.src = `/api/runs/${enc(current.run.id)}/recording`;
    $('customer-recording-panel').hidden = false;
    $('watch-recording').setAttribute('aria-expanded', 'true');
    text('recording-status', 'Press play to watch the saved checkout.');
    video.focus();
  });
  $('close-recording').addEventListener('click', () => closeRecording(true));
  $('customer-recording-video').addEventListener('error', () => { if ($('customer-recording-video').getAttribute('src')) text('recording-status', 'The recording couldn’t be loaded. Refresh and try again.'); });
  $('customer-recording-video').addEventListener('loadedmetadata', () => text('recording-status', 'Recording ready. Use the controls to play or skip through it.'));
  window.addEventListener('pagehide', () => closeRecording());

  /* ---------- Filters and search ---------- */
  $('run-search').addEventListener('input', filterRuns);
  document.querySelectorAll('.trace-filters button').forEach((button) => button.addEventListener('click', () => {
    timelineSource = button.dataset.source;
    if (current && current.run.id === selected) { $('timeline').dataset.timelineRunId = ''; renderTimeline(current.run.id, current.events); }
  }));

  /* Capabilities are server-owned; configured keys do not grant a fault. */
  const knownFaults = ['none', 'response_loss', 'event_delay', 'event_duplicate', 'process_interrupt'];
  function allowedFault(kind) {
    return knownFaults.includes(kind) && (capabilities ? capabilities.faults.includes(kind) : kind !== 'process_interrupt');
  }
  function applyCapabilities(value) {
    capabilities = value && Array.isArray(value.faults) && value.faults.every((kind) => knownFaults.includes(kind))
      && Number.isInteger(value.max_promise_chars) && value.max_promise_chars > 0 && value.max_promise_chars <= 4000
      ? {faults: [...value.faults], max_promise_chars: value.max_promise_chars} : null;
    for (const option of Array.from($('fault').options || [])) { option.hidden = option.disabled = !allowedFault(option.value); }
    if (!allowedFault($('fault').value)) $('fault').value = capabilities?.faults[0] || 'none';
    $('promise').maxLength = capabilities?.max_promise_chars || 1000;
  }

  /* ---------- New check dialog ---------- */
  const dialog = $('new-case-dialog');
  let dialogOpener = null;
  const notice = node('p', '', 'dialog-notice'); notice.id = 'new-run-notice'; notice.hidden = true;
  $('new-run-message').before(notice);

  function openNewCase(event) {
    createIntent++;
    applyCapabilities(capabilities);
    dialogOpener = event?.currentTarget || document.activeElement;
    text('new-run-message', ''); $('new-run-error-details').hidden = true;
    const paypalReady = prereqs?.paypal?.configured === true;
    notice.hidden = paypalReady;
    notice.textContent = paypalReady ? '' : 'PayPal test payments aren’t set up in this workspace yet. You can create the check, but the test checkout won’t start until your workspace owner connects PayPal Sandbox.';
    $('delay-field').hidden = $('fault').value !== 'event_delay';
    if (typeof dialog.showModal === 'function') dialog.showModal(); else dialog.setAttribute('open', '');
    $('promise').focus();
  }
  function closeNewCase() {
    if (typeof dialog.close === 'function') dialog.close(); else dialog.removeAttribute('open');
  }
  dialog.addEventListener('close', () => { createIntent++; (dialogOpener && document.contains(dialogOpener) ? dialogOpener : $('new-case-open')).focus(); });
  $('new-case-open').addEventListener('click', openNewCase);
  $('empty-new').addEventListener('click', openNewCase);
  $('new-case-close').addEventListener('click', closeNewCase);
  $('new-case-cancel').addEventListener('click', closeNewCase);
  $('fault').addEventListener('change', () => { $('delay-field').hidden = $('fault').value !== 'event_delay'; });

  $('new-run').addEventListener('submit', async (event) => {
    event.preventDefault();
    if (creating || createUnresolved) return;
    const submittedIntent = createIntent, submittedSelection = selectionIntent;
    text('new-run-message', ''); $('new-run-error-details').hidden = true;
    const promise = $('promise').value.trim();
    if (!promise) { text('new-run-message', 'Describe what should happen, or what went wrong.'); $('promise').focus(); return; }
    const maxPromise = capabilities?.max_promise_chars || 1000;
    if (promise.length > maxPromise) { text('new-run-message', `Keep the description under ${maxPromise.toLocaleString()} characters.`); $('promise').focus(); return; }
    const fault = {kind: $('fault').value, merchant: $('merchant').value};
    if (!allowedFault(fault.kind)) { text('new-run-message', 'That test is not available in this workspace. Choose a supported test.'); applyCapabilities(capabilities); return; }
    if (fault.kind === 'event_delay') {
      const delay = Number($('delay').value);
      if (!Number.isInteger(delay) || delay < 1 || delay > 120) { text('new-run-message', 'Choose a whole number of seconds from 1 to 120.'); $('delay').focus(); return; }
      fault.delay_seconds = delay;
    }
    const mode = document.querySelector('input[name="mode"]:checked')?.value || 'LIVE_SANDBOX';
    creating = true;
    $('new-run-submit').disabled = true; text('new-run-submit', 'Creating…');
    let run;
    try {
      run = await api('/api/runs', {promise, mode, fault, fixture_id: $('fixture').value});
    } catch (error) {
      if (error.uncertain) createUnresolved = true;
      if (submittedIntent !== createIntent || submittedSelection !== selectionIntent) { listSignature = null; safeRefresh(); return; }
      if (error.status === 401) { closeNewCase(); showLogin(error); }
      else if (error.uncertain) {
        text('new-run-message', 'We didn’t get a clear answer, so the check may or may not have been created. Close this and look for it in your list before trying again.');
        text('new-run-error-code', String(error.message ?? '')); $('new-run-error-details').hidden = false;
        listSignature = null; safeRefresh();
      } else showError(error, 'new-run');
      return;
    } finally {
      creating = false;
      $('new-run-submit').disabled = createUnresolved; text('new-run-submit', createUnresolved ? 'Refresh the case list first' : 'Create check');
    }
    if (!identity(run?.id)) { text('new-run-message', 'The check was saved, but we couldn’t read its reference. Look for it in your list.'); listSignature = null; safeRefresh(); return; }
    if (submittedIntent !== createIntent || submittedSelection !== selectionIntent) {
      listSignature = null; await safeRefresh();
      if (!current || !isStopped(current.run)) setMessage('Your new check was saved in the case list. Your current selection was kept; open the new check from the list when ready.', 'info', 'created-later');
      return;
    }
    dialogOpener = null;
    closeNewCase();
    selectRun(run.id);
    await safeRefresh();
    await observe('investigation_created', run.id);
    await safeRefresh();
  });

  /* ---------- Sign in ---------- */
  $('login').addEventListener('submit', async (event) => {
    event.preventDefault();
    text('login-message', ''); $('login-error-details').hidden = true;
    const token = $('token').value;
    if (!token) { text('login-message', 'Enter your access key.'); $('token').focus(); return; }
    $('login-submit').disabled = true; text('login-submit', 'Signing in…');
    try {
      await api('/api/login', {token});
      $('token').value = '';
      await openWorkspace();
    } catch (error) {
      if (error.status === 401) showError(new ApiError('Invalid operator token', {status: 0}), 'login');
      else showError(error, 'login');
    } finally {
      $('login-submit').disabled = false; text('login-submit', 'Sign in');
    }
  });

  $('offline-retry').addEventListener('click', () => { $('boot').hidden = false; $('offline-panel').hidden = true; openWorkspace(); });

  /* ---------- Boot ---------- */
  async function openWorkspace() {
    if (selected) { $('loading-case').hidden = false; $('empty').hidden = true; }
    try {
      await refresh();
    } catch (error) {
      if (error?.status === 401 || error?.status === 403) showLogin();
      else showOffline(error);
      return;
    }
    setView('workspace');
    workspaceReady = true;
    api('/healthz').then((d) => {
      applyCapabilities(d.capabilities);
      const ok = d.status === 'ok' && d.database === 'ok';
      text('health', ok ? 'Workspace online' : 'Workspace needs attention');
      $('health').dataset.tone = ok ? 'ok' : 'warn';
      $('health').hidden = false;
    }).catch(() => { applyCapabilities(null); text('health', 'Workspace status unavailable'); $('health').dataset.tone = 'warn'; $('health').hidden = false; });
    if (!landedOnce) {
      landedOnce = true;
      if (selected && current && pageMode === 'cancel') await observe('returned_via_cancel_link');
      else if (selected && current && pageMode === 'return') {
        if (current.purchase.payment_confirmed !== 1 && returnMatches(current.purchase)) messageKind = 'returned';
        syncRecoveryNotice();
        await observe('buyer_returned');
      }
      if (focusSelectedRun && current) { focusSelectedRun = false; $('run-title').focus(); }
    }
  }

  function poll() {
    if (!workspaceReady || document.hidden || $('workspace').hidden || active || polling || creating) return;
    polling = true;
    refresh().catch((error) => { if (error?.status === 401) showLogin(error); else markSyncFailed(); }).finally(() => { polling = false; });
  }
  setInterval(poll, 5000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) poll(); });

  applyCapabilities(null);
  const casePicker = $('case-picker');
  if (casePicker) casePicker.open = !window.matchMedia('(max-width: 860px)').matches;
  updateLinks();
  if (isLanding) {
    setView('landing');
  } else {
    focusSelectedRun = !!selected;
    openWorkspace();
  }
})();
