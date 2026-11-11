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
  assert.deepEqual(query, {runId: 'run_12345678', confirm: true, cancelled: false});
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

test('returning with an opaque run alone requires server-side confirmation, never a URL-derived success', () => {
  assert.deepEqual(live.returnContext('?run=run_12345678'), {runId: 'run_12345678', confirm: true, cancelled: false});
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
