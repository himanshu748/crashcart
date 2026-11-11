'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const live = require('../web/judge/live.js');

test('only PayPal Sandbox HTTPS approval destinations are allowed', () => {
  assert.equal(live.safeApproval('https://www.sandbox.paypal.com/checkoutnow?token=TESTORDER'), 'https://www.sandbox.paypal.com/checkoutnow?token=TESTORDER');
  for (const url of ['https://www.paypal.com/checkoutnow', 'javascript:alert(1)', 'https://sandbox.paypal.com.evil.test/', 'https://user:pass@sandbox.paypal.com/', 'http://sandbox.paypal.com/', '//sandbox.paypal.com/']) {
    assert.equal(live.safeApproval(url), null, url);
  }
});

test('run IDs and returned approval tokens are not treated as authorization', () => {
  assert.equal(live.safeRunId('run_12345678'), 'run_12345678');
  assert.equal(live.safeRunId('../../admin'), null);
  assert.equal(live.safeRunId('x'), null);
  const query = live.returnContext('?run=run_12345678&token=TESTORDER');
  assert.deepEqual(query, {runId: 'run_12345678', confirm: false, cancelled: false});
  assert.deepEqual(live.returnContext('?run=run_12345678&cancel=1'), {runId: 'run_12345678', confirm: false, cancelled: true});
  assert.equal(live.returnContext('?token=TESTORDER').confirm, false);
});

test('a completed state without provider, webhook and investigation evidence is never presented as finished', () => {
  for (const run of [
    {state: 'complete'},
    {state: 'complete', payment: {status: 'COMPLETED'}, webhook: {verified: false}, investigation: {status: 'complete'}},
    {state: 'complete', payment: {status: 'COMPLETED'}, webhook: {verified: true}, investigation: {status: 'failed'}},
  ]) assert.equal(live.projectRun(run).finished, false);
});

test('the finished view repeats the server verdict and cannot turn a failed delivery into success', () => {
  const run = {state: 'complete', payment: {status: 'COMPLETED', order_id: 'TEST_ORDER', capture_id: 'TEST_CAPTURE'}, webhook: {verified: true}, investigation: {status: 'complete', citations: ['payment:1', 'tickets:1']}, verdict: {verdict: 'FAIL', signature: 'paid_without_ticket'}, tickets: []};
  const projected = live.projectRun(run);
  assert.equal(projected.finished, true);
  assert.equal(projected.verdict, 'FAIL');
  assert.equal(projected.signature, 'paid_without_ticket');
  assert.equal(projected.ticketCount, 0);
  assert.equal(projected.stages.find(s => s.id === 'payment').done, true);
  assert.equal(projected.stages.find(s => s.id === 'webhook').done, true);
});

test('unknown, cancelled, failed and paused states have explicit safe views', () => {
  assert.equal(live.projectRun({state: 'new_unknown_provider_state'}).finished, false);
  assert.equal(live.projectRun({state: 'cancelled'}).terminal, true);
  assert.equal(live.projectRun({state: 'failed'}).terminal, true);
  assert.equal(live.projectRun({state: 'paused'}).paused, true);
});

test('live page is usable without scripts and has explicit payment action, status and recorded escape route', () => {
  const html = fs.readFileSync(path.join(__dirname, '../web/judge/live.html'), 'utf8');
  assert.match(html, /<h1[^>]*>/);
  assert.match(html, /id="live-start"[^>]*disabled/);
  assert.match(html, /aria-live="polite"/);
  assert.match(html, /<noscript>/);
  assert.match(html, /href="demo.html"/);
  assert.doesNotMatch(html, /<script(?![^>]*src=)[^>]*>/);
});

test('opening an opaque run alone is read-only and never treats a URL as approval', () => {
  assert.deepEqual(live.returnContext('?run=run_12345678'), {runId: 'run_12345678', confirm: false, cancelled: false});
  const projected = live.projectRun({state: 'AWAITING_APPROVAL', payment: {status: 'APPROVED', order_id: 'TESTORDER'}});
  assert.equal(projected.finished, false);
  assert.equal(projected.stages.find(s => s.id === 'payment').done, false);
});

test('real response shape preserves cents, zero tickets and cited FAIL without browser verdict computation', () => {
  const source = {mode: 'LIVE_SANDBOX', run_id: 'run_12345678', state: 'COMPLETED', payment: {amount: 2900, currency: 'USD', status: 'COMPLETED', order_id: 'TEST_ORDER', capture_id: 'TEST_CAPTURE'}, webhook: {verified: true}, investigation: {status: 'COMPLETED', citations: [{id: 'capture:1', kind: 'paypal', summary: 'Capture completed'}]}, verdict: {verdict: 'FAIL', signature: 'paid_without_ticket', reason: 'No ticket after the unchanged promise'}, tickets: {count: 0}};
  const before = JSON.stringify(source);
  assert.equal(live.projectRun(source).finished, true);
  assert.equal(live.projectRun(source).ticketCount, 0);
  assert.equal(JSON.stringify(source), before);
  source.investigation.citations = [];
  assert.equal(live.projectRun(source).finished, false);
});

test('requests use bound session, no-store and abort signals; HTTP/HTML failure cannot masquerade as API success', async () => {
  let options;
  const response = await live.requestJSON(async (_url, supplied) => { options = supplied; return {ok: true, status: 200, headers: new Headers({'Content-Type': 'application/json'}), json: async () => ({enabled: false})}; }, 'api/live/config');
  assert.deepEqual(response, {enabled: false});
  assert.equal(options.credentials, 'same-origin');
  assert.equal(options.cache, 'no-store');
  assert.equal(options.redirect, 'error');
  assert(options.signal instanceof AbortSignal);
  for (const response of [
    {ok: false, status: 404, headers: new Headers({'Content-Type': 'text/html'})},
    {ok: true, status: 200, headers: new Headers({'Content-Type': 'text/html'})},
    {ok: false, status: 401, headers: new Headers({'Content-Type': 'application/json'})},
  ]) await assert.rejects(live.requestJSON(async () => response, 'api/live/config'));
});

test('a finished result needs the actual order and capture identifiers, not only a status word', () => {
  const run = {state: 'COMPLETED', payment: {status: 'COMPLETED'}, webhook: {verified: true}, investigation: {status: 'COMPLETED', citations: ['payment:1', 'tickets:1']}, verdict: {verdict: 'FAIL', signature: 'paid_without_ticket'}, tickets: {count: 0}};
  assert.equal(live.projectRun(run).finished, false);
});


test('malformed API envelopes cannot drive a checkout or a finished screen', async () => {
  for (const body of [null, [], 'COMPLETED']) {
    await assert.rejects(live.requestJSON(async () => ({ok: true, status: 200, headers: new Headers({'Content-Type': 'application/json'}), json: async () => body}), 'api/live/config'), /unreadable reply/);
  }
});

test('paused fallback accepts only the saved, offline, same-input repair comparison', () => {
  const makeCase = (variant, verdict, signature, count) => ({receipt: {mode: 'RECORDED_REPLAY', fresh_execution: false, network_calls: 0, input_sha256: 'a'.repeat(64), verdict, signature, ticket_count: count}, purchase: {payment_confirmed: true, capture_completed_at: '2026-10-22T09:31:52Z'}, execution: {invariant: {recovery_seconds: 60}}, merchant: {tickets: Array.from({length: count}, () => ({}))}});
  const original = {mode: 'RECORDED_REPLAY', fresh_execution: false, network_calls: 0, input_file_sha256: 'a'.repeat(64), cases: {defective: makeCase('defective', 'FAIL', 'paid_without_ticket', 0), healthy: makeCase('healthy', 'PASS', 'ticket_delivered_once_on_time', 1)}};
  assert.deepEqual(live.projectReplay(original), {missed: 0, recovered: 1});
  for (const change of [
    data => {data.mode = 'LIVE_SANDBOX';},
    data => {data.fresh_execution = true;},
    data => {data.network_calls = 1;},
    data => {data.cases.healthy.receipt.input_sha256 = 'b'.repeat(64);},
    data => {data.cases.healthy.merchant.tickets = [];},
    data => {data.cases.healthy.receipt.signature = 'ticket_delivered_late';},
    data => {data.cases.defective.purchase.capture_completed_at = '2026-11-08T09:23:15Z';},
    data => {data.cases.healthy.execution.invariant.recovery_seconds = 61;},
  ]) {const data = structuredClone(original);change(data);assert.equal(live.projectReplay(data), null);}
});

test('fallback understands SQLite confirmed flags and canonical replay hashes without conflating raw-file bytes', () => {
  const receipt = {mode: 'RECORDED_REPLAY', fresh_execution: false, network_calls: 0, input_sha256: 'a'.repeat(64)};
  const item = (verdict, signature, count) => ({receipt: {...receipt, verdict, signature, ticket_count: count}, purchase: {payment_confirmed: 1, capture_completed_at: '2026-10-22T09:31:52Z'}, execution: {invariant: {recovery_seconds: 60}}, merchant: {tickets: Array.from({length: count}, () => ({}))}});
  assert.deepEqual(live.projectReplay({mode: 'RECORDED_REPLAY', fresh_execution: false, network_calls: 0, input_file_sha256: 'b'.repeat(64), cases: {defective: item('FAIL', 'paid_without_ticket', 0), healthy: item('PASS', 'ticket_delivered_once_on_time', 1)}}), {missed: 0, recovered: 1});
});

test('payment identifiers are masked for the visible workspace; approval URLs retain their separate strict validation', () => {
  assert.equal(live.maskId('4HJ31244AH4428038'), '4HJ3…8038');
  assert.equal(live.maskId('9U732141TN8280908'), '9U73…0908');
  assert.equal(live.maskId('short'), 'ID recorded');
  assert.equal(live.maskId(null), '');
});

test('known PayPal IDs are masked inside investigation prose and citations without changing the source records', () => {
  const payment = {order_id: '4HJ31244AH4428038', capture_id: '9U732141TN8280908'};
  const raw = 'Capture9U732141TN8280908 confirms order4HJ31244AH4428038.';
  assert.equal(live.maskKnownIds(raw, payment), 'Capture9U73…0908 confirms order4HJ3…8038.');
  assert.equal(raw, 'Capture9U732141TN8280908 confirms order4HJ31244AH4428038.');
  assert.equal(payment.capture_id, '9U732141TN8280908');
});


test('availability codes stay out of customer-facing copy', () => {
  assert.equal(live.availabilityReason('PUBLIC_LIVE_PAUSED'), 'New Sandbox runs are paused here. The saved example is ready.');
  assert.equal(live.availabilityReason('New runs resume later.'), 'New runs resume later.');
});

// Execute the shipped controller with a minimal DOM boundary. These tests prove
// request gating and view state, not real provider or browser execution.
async function controllerHarness({query = '', config = {enabled: false, mode: 'SAVED_REPLAY', csrf_token: 'TEST_CSRF'}, run, afterConfirm, confirmStatus = 202} = {}) {
  const vm = require('node:vm');
  const html = fs.readFileSync(path.join(__dirname, '../web/judge/live.html'), 'utf8');
  const nodes = new Map(), calls = [], history = [], timers = new Map();
  let timer = 0, confirmed = false;
  class Node {
    constructor(id = '') { this.id = id; this.hidden = false; this.disabled = false; this.textContent = ''; this.dataset = {}; this.children = []; this.attributes = {}; this.handlers = {}; }
    setAttribute(key, value) { this.attributes[key] = String(value); }
    removeAttribute(key) { delete this.attributes[key]; }
    addEventListener(key, callback) { this.handlers[key] = callback; }
    querySelector() { return this.label || (this.label = new Node()); }
    replaceChildren(...values) { this.children = values; }
    append(...values) { this.children.push(...values); }
    focus() { document.activeElement = this; }
  }
  for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    const node = new Node(match[1]);node.hidden = /\bhidden(?:\s|>)/.test(match[0]);node.disabled = /\bdisabled(?:\s|>)/.test(match[0]);nodes.set(node.id, node);
  }
  const document = {getElementById: id => nodes.get(id), createElement: () => new Node()};
  const location = {href: 'http://127.0.0.1:8767/live.html' + query, hostname: '127.0.0.1', search: query};
  const window = {document, location, crypto: {randomUUID: () => 'TEST-IDEMPOTENCY'}, addEventListener() {},
    history: {replaceState(_state, _title, value) {const next = new URL(value);location.href = next.href;location.search = next.search;history.push(next.search);}},
    async fetch(url, options) {
      const method = options.method || 'GET';calls.push({url, method, headers: options.headers});
      let body, status = 200;
      if (url === 'api/live/config') body = config;
      else if (url.endsWith('/confirm')) {confirmed = true;body = {accepted: true};status = confirmStatus;}
      else if (url.startsWith('api/live/runs/')) body = confirmed && afterConfirm ? afterConfirm : run;
      else body = {};
      return {ok: status >= 200 && status < 300, status, headers: new Headers({'Content-Type': 'application/json'}), json: async () => body};
    }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../web/judge/live.js'), 'utf8'), {
    window, URL, URLSearchParams, AbortController, Date,
    setTimeout(callback, delay) {timers.set(++timer, {callback, delay});return timer;}, clearTimeout(id) {timers.delete(id);},
  }, {filename: 'live.js'});
  for (let i = 0; i < 3; i++) await new Promise(setImmediate);
  return {nodes, calls, history, location, timers};
}
function completedControllerRun() {
  return {mode: 'LIVE_SANDBOX', run_id: 'run_12345678', state: 'COMPLETED', payment: {amount: 2900, currency: 'USD', status: 'COMPLETED', order_id: 'TEST_ORDER', capture_id: 'TEST_CAPTURE'}, webhook: {verified: true}, investigation: {status: 'COMPLETED', steps: [], citations: [{id: 'record:1', summary: 'Synthetic controller boundary only'}]}, verdict: {verdict: 'FAIL', signature: 'paid_without_ticket'}, tickets: {count: 0}};
}
function awaitingControllerRun() {
  return {mode: 'LIVE_SANDBOX', run_id: 'run_12345678', state: 'AWAITING_APPROVAL', payment: {status: 'CREATED', order_id: 'TEST_ORDER'}, approval_url: 'https://www.sandbox.paypal.com/checkoutnow?token=TEST_ORDER'};
}

test('only the explicit approval-return marker requests server confirmation', () => {
  assert.equal(live.returnContext('?run=run_12345678&approval_return=1').confirm, true);
  assert.equal(live.returnContext('?run=run_12345678&approval_return=true').confirm, false);
  assert.equal(live.returnContext('?approval_return=1&token=TEST_ORDER').confirm, false);
  assert.equal(live.returnContext('?run=run_12345678&approval_return=1&cancel=1').confirm, false);
});

test('completed owner result reopens read-only even when new admission is disabled', async () => {
  const h = await controllerHarness({query: '?run=run_12345678', run: completedControllerRun()});
  assert.equal(h.nodes.get('live-result').hidden, false);
  assert.equal(h.nodes.get('live-error').hidden, true);
  assert.deepEqual(h.calls.map(c => [c.method, c.url]), [['GET', 'api/live/runs/run_12345678']]);
});

test('bare active run links and reloads never POST confirm despite an available allowance', async () => {
  const h = await controllerHarness({query: '?run=run_12345678', config: {enabled: true, mode: 'LIVE_SANDBOX', csrf_token: 'TEST_CSRF'}, run: awaitingControllerRun()});
  assert.equal(h.calls.filter(c => c.method === 'POST').length, 0);
  assert.equal(h.nodes.get('live-approve').hidden, false);
});

test('an already reserved owner run can confirm after new admission is exhausted', async () => {
  const h = await controllerHarness({query: '?run=run_12345678&approval_return=1', run: awaitingControllerRun(), afterConfirm: completedControllerRun()});
  assert.equal(h.calls.filter(c => c.url.endsWith('/confirm') && c.method === 'POST').length, 1);
  assert.equal(h.nodes.get('live-result').hidden, false);
  assert.equal(h.calls.find(c => c.method === 'POST').headers['X-CSRF-Token'], 'TEST_CSRF');
});

test('terminal results ignore stale approval-return markers and require no active configuration', async () => {
  const h = await controllerHarness({query: '?run=run_12345678&approval_return=1', run: completedControllerRun()});
  assert.equal(h.nodes.get('live-result').hidden, false);
  assert.equal(h.calls.some(c => c.method === 'POST'), false);
});

test('a failed callback confirmation is not retried by reloading its cleaned run URL', async () => {
  const h = await controllerHarness({query: '?run=run_12345678&approval_return=1', run: awaitingControllerRun(), confirmStatus: 503});
  assert.equal(h.calls.filter(c => c.method === 'POST').length, 1);
  assert.equal(new URL(h.location.href).searchParams.has('approval_return'), false);
  assert.equal(h.nodes.get('live-result').hidden, true);
  const reload = await controllerHarness({query: h.location.search, run: awaitingControllerRun()});
  assert.equal(reload.calls.some(c => c.method === 'POST'), false);
});

test('cancel remains an explicit owner action when a bare run view has not loaded a CSRF token', async () => {
  const h = await controllerHarness({query: '?run=run_12345678', run: awaitingControllerRun()});
  await h.nodes.get('live-cancel').handlers.click();
  assert.equal(h.calls.filter(c => c.method === 'POST' && c.url.endsWith('/cancel')).length, 1);
  assert.equal(h.calls.some(c => c.url.endsWith('/confirm')), false);
});

test('a repeated callback for an already confirming run resumes GET polling without another confirm', async () => {
  const h = await controllerHarness({query: '?run=run_12345678&approval_return=1', run: {...awaitingControllerRun(), state: 'CONFIRMING'}});
  assert.equal(h.calls.some(c => c.method === 'POST'), false);
  assert.equal(h.nodes.get('live-error').hidden, true);
});
