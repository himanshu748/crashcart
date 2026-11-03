/* Actual isolated Chromium -> actual scoped gateway. LOCAL_TEST provider only. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createHash} from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import {createRequire} from 'node:module';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.CRASHCART_PLAYWRIGHT_MODULE || 'playwright');
const output = path.join(root, 'evidence/runs/gateway-ui-v1');
fs.mkdirSync(output, {recursive: true});
const attempt = fs.readdirSync(output).filter(name => /^attempt-\d+\.json$/.test(name)).length + 1;
const viewportName = process.env.CRASHCART_GATEWAY_VIEWPORT || 'desktop';
assert(['desktop', 'mobile'].includes(viewportName), 'Use desktop or mobile viewport');
const viewport = viewportName === 'mobile' ? {width: 390, height: 844} : {width: 1440, height: 1050};
const origin = 'https://gateway.example.test';
const sources = ['crashcart/__init__.py', 'tests/__init__.py', 'crashcart/verification_gateway.py', 'tests/test_verification_gateway.py',
  'crashcart/server.py', 'crashcart/config.py', 'crashcart/service.py', 'crashcart/store.py',
  'crashcart/faults.py', 'crashcart/paypal.py', 'crashcart/invariant.py',
  'migrations/001_initial.sql', 'web/index.html', 'web/app.js', 'web/style.css',
  'scripts/verify_gateway_ui.mjs'];
const hashes = Object.fromEntries(sources.map(name => [name, createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex')]));
const assertions = [], responses = [], errors = [], unexpectedNetwork = [];
const check = (name, value) => { assert(value, name); assertions.push({name, passed: true}); };
let browser, child, gatewayInfo, driverStderr = '';

const driver = `
import json, os, sys, tempfile, threading
from crashcart.store import Store
from crashcart.service import MerchantService
from crashcart.verification_gateway import VerificationGateway
from tests.test_verification_gateway import FakePayPal
import socket
def forbidden(*args, **kwargs):
    raise AssertionError("Synthetic gateway driver forbids outbound sockets")
socket.socket.connect = forbidden
os.environ["CRASHCART_PUBLIC_URL"] = "https://gateway.example.test"
os.environ["CRASHCART_ALLOW_SANDBOX"] = "0"
os.environ["CRASHCART_ALLOW_MODEL"] = "0"
with tempfile.TemporaryDirectory(prefix="crashcart-gateway-browser-local-") as folder:
    store = Store(folder + "/test.sqlite3")
    run = store.create_run("LOCAL_TEST: synthetic gateway checkout", fault={"kind":"none", "merchant":"healthy"})
    other = store.create_run("LOCAL_TEST: private other investigation", fault={"kind":"none", "merchant":"healthy"})
    provider = FakePayPal()
    server = VerificationGateway(store, run_id=run["id"], public_origin=os.environ["CRASHCART_PUBLIC_URL"],
        external_origin_approved=True, service=MerchantService(store, lambda: provider))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    print(json.dumps({"kind":"ready", "port":server.server_port, "token":server.token,
        "run_id":run["id"], "purchase_id":run["purchase_id"], "other_id":other["id"]}), flush=True)
    try:
        for line in sys.stdin:
            command = json.loads(line)
            if command["action"] == "approve":
                provider.order["status"] = "APPROVED"
                print(json.dumps({"kind":"approved"}), flush=True)
            elif command["action"] == "state":
                purchase = store.purchase_for_run(run["id"])
                print(json.dumps({"kind":"state", "purchase":purchase, "merchant":store.merchant_state(purchase["id"]),
                    "other_purchase":store.purchase_for_run(other["id"]),
                    "provider_calls":[call[0] for call in provider.calls], "run_count":len(store.list_runs())}), flush=True)
            elif command["action"] == "stop":
                break
    finally:
        server.revoke()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
`;

const queue = [], waiting = [];
const receive = () => queue.length ? Promise.resolve(queue.shift()) : new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error('Synthetic driver response timed out')), 15000);
  waiting.push(value => {clearTimeout(timer); resolve(value);});
});
function ask(action) {
  child.stdin.write(JSON.stringify({action}) + '\n');
  return receive();
}
function forward(request) {
  const target = new URL(request.url());
  const headers = {...request.headers(), host: target.host};
  delete headers.connection;
  return new Promise((resolve, reject) => {
    const upstream = http.request({hostname: '127.0.0.1', port: gatewayInfo.port,
      path: target.pathname + target.search, method: request.method(), headers}, response => {
      const chunks = [];
      response.on('data', part => chunks.push(part));
      response.on('end', () => resolve({status: response.statusCode,
        headers: Object.fromEntries(Object.entries(response.headers).map(([key, value]) => [key, Array.isArray(value) ? value.join('\n') : value])),
        body: Buffer.concat(chunks)}));
    });
    upstream.setTimeout(10000, () => upstream.destroy(new Error('Loopback forwarding timed out')));
    upstream.on('error', reject);
    upstream.end(request.postDataBuffer());
  });
}

const receipt = {mode: 'LOCAL_TEST', actual_browser: true, actual_loopback_gateway: true,
  provider: 'Injected FakePayPal; no PayPal or KERNEL request', logical_origin: origin,
  transport: 'Playwright routes logical HTTPS browser requests to an actual HTTP loopback gateway. No TLS terminator, public ingress or tunnel was created.',
  fixture_mode_note: 'The temporary run uses the gateway-required LIVE_SANDBOX mode; injected FakePayPal and socket denial make this entire test LOCAL_TEST. No temporary record enters the application database.',
  viewport_name: viewportName, viewport,
  source_hashes: hashes, assertions, responses, errors, unexpected_network: unexpectedNetwork,
  started_at: new Date().toISOString(), attempt};

try {
  child = spawn(process.env.CRASHCART_PYTHON || 'python3', ['-u', '-c', driver], {
    cwd: root, env: {PATH: process.env.PATH, PYTHONPATH: root, PYTHONUNBUFFERED: '1'}, stdio: ['pipe', 'pipe', 'pipe']});
  let buffered = '';
  child.stdout.on('data', data => {
    buffered += data.toString();
    for (;;) {
      const position = buffered.indexOf('\n');
      if (position < 0) break;
      const line = buffered.slice(0, position); buffered = buffered.slice(position + 1);
      const value = JSON.parse(line);
      if (waiting.length) waiting.shift()(value); else queue.push(value);
    }
  });
  child.stderr.on('data', data => {
    driverStderr += data.toString();
    errors.push('Synthetic driver emitted stderr; inspect sanitized driver_stderr in this receipt');
  });
  gatewayInfo = await receive();
  assert.equal(gatewayInfo.kind, 'ready');
  receipt.identity = {run_id: gatewayInfo.run_id, purchase_id: gatewayInfo.purchase_id};
  browser = await chromium.launch({headless: true, executablePath: process.env.CRASHCART_CHROMIUM});
  receipt.browser = await browser.version();
  const context = await browser.newContext({viewport, reducedMotion: 'reduce',
    isMobile: viewportName === 'mobile', hasTouch: viewportName === 'mobile', serviceWorkers: 'block'});
  await context.route('**/*', async route => {
    const request = route.request(), target = new URL(request.url());
    if (target.origin === origin) {
      try {
        const result = await forward(request);
        responses.push({method: request.method(), path: target.pathname, status: result.status});
        await route.fulfill(result);
      } catch {errors.push('Loopback route failed'); await route.abort();}
    } else if (target.origin === 'https://www.sandbox.paypal.com' && target.pathname === '/checkoutnow') {
      check('Checkout navigation contains the persisted synthetic order', target.searchParams.get('token') === 'ORDER_SCOPED');
      await route.fulfill({status: 200, contentType: 'text/html', body: '<!doctype html><title>LOCAL_TEST approval fixture</title><h1>Synthetic PayPal approval</h1><p>No provider connection.</p><button id="fixture-approve">Approve local fixture</button>'});
    } else {
      unexpectedNetwork.push({origin: target.origin, path: target.pathname});
      await route.abort();
    }
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + '/shop?run=' + gatewayInfo.run_id);
  await page.getByRole('heading', {name: 'Open your investigation desk.'}).waitFor();
  check('Page identity is the actual scoped CrashCart shop', page.url() === origin + '/shop?run=' + gatewayInfo.run_id && await page.title() === 'CrashCart — payment meets promise');
  await page.screenshot({path: path.join(output, `attempt-${attempt}-${viewportName}-entry.png`), fullPage: false});
  check('Real frontend requests are unauthenticated before gateway login', responses.some(r => r.path === '/api/runs' && r.status === 401));
  await page.keyboard.press('Tab');
  check('Keyboard skip navigation is available', await page.locator('.skip').evaluate(element => element === document.activeElement));
  await page.getByLabel('Operator token').fill(gatewayInfo.token);
  await page.getByRole('button', {name: 'Open workspace'}).click();
  await page.locator('#run-id').filter({hasText: gatewayInfo.run_id}).waitFor();
  check('Gateway login opens the actual scoped shop page', await page.locator('#workspace').isVisible());
  check('Only the authorized run appears in history', await page.locator('.run-row').count() === 1);
  check('Unpaid fixture has no ticket', await page.locator('#merchant-title').innerText() === '0 tickets');
  const cookies = await context.cookies(origin);
  const cookie = cookies.find(value => value.name === '__Host-crashcart_gateway');
  check('Logical HTTPS browser accepts Secure HttpOnly SameSite cookie', cookie?.secure && cookie.httpOnly && cookie.sameSite === 'Lax' && cookie.path === '/');
  check('Browser never receives a global operator cookie', !cookies.some(value => value.name === 'crashcart_session'));
  await page.getByRole('button', {name: 'Start sandbox checkout'}).click();
  await page.waitForURL('https://www.sandbox.paypal.com/checkoutnow?token=ORDER_SCOPED');
  await page.locator('#fixture-approve').waitFor();
  check('Actual checkout button reaches explicitly synthetic approval page', await page.title() === 'LOCAL_TEST approval fixture');
  await page.goto(origin + '/cancel?run=' + gatewayInfo.run_id + '&token=ORDER_SCOPED');
  await page.locator('#message').filter({hasText: 'Buyer approval cancelled.'}).waitFor();
  check('Cancel return has no ticket or enabled capture', await page.locator('#merchant-title').innerText() === '0 tickets' && await page.locator('#capture').isHidden());
  await page.reload();
  await page.getByRole('button', {name: 'Resume sandbox checkout'}).waitFor();
  check('Refresh preserves the unapproved order identity', (await page.locator('#provenance').innerText()).includes('ORDER_SCOPED'));
  await page.getByRole('button', {name: 'Resume sandbox checkout'}).click();
  await page.waitForURL('https://www.sandbox.paypal.com/checkoutnow?token=ORDER_SCOPED');
  const resumed = await ask('state');
  check('Resume uses the same unapproved order without another create or capture', resumed.purchase.order_id === 'ORDER_SCOPED' && resumed.provider_calls.filter(c => c === 'create').length === 1 && resumed.provider_calls.filter(c => c === 'capture').length === 0);
  await page.locator('#fixture-approve').click();
  assert.equal((await ask('approve')).kind, 'approved');
  await page.goto(origin + '/return?run=' + gatewayInfo.run_id + '&token=ORDER_SCOPED&PayerID=LOCAL_TEST');
  await page.locator('#capture').waitFor({state: 'visible'});
  check('Secure session survives simulated cross-site approval return', await page.locator('#login-panel').isHidden());
  await page.getByRole('button', {name: 'Confirm approved payment'}).click();
  await page.locator('#ticket-card').waitFor({state: 'visible'});
  await page.locator('#busy').waitFor({state: 'hidden'});
  const ticket = await page.locator('#ticket-id').innerText();
  check('Actual merchant service renders exactly one synthetic ticket', /^ticket_/.test(ticket) && await page.locator('#merchant-title').innerText() === '1 ticket');
  check('Unchanged deterministic invariant renders PASS', (await page.locator('#verdict').innerText()).startsWith('PASS:'));
  const state = await ask('state');
  check('Displayed ticket matches independent SQLite read', state.merchant.ticket_count === 1 && state.merchant.tickets[0].id === ticket);
  check('Only one synthetic create and capture occurred', state.provider_calls.filter(c => c === 'create').length === 1 && state.provider_calls.filter(c => c === 'capture').length === 1);
  check('Other purchase has no provider identity or payment', state.other_purchase.order_id === null && state.other_purchase.payment_confirmed === 0);
  receipt.result = {order_id: state.purchase.order_id, capture_id: state.purchase.capture_id, ticket_id: ticket, provider_calls: state.provider_calls};
  await page.reload();
  await page.locator('#ticket-id').filter({hasText: ticket}).waitFor();
  check('Refresh restores the same persisted order and ticket', (await page.locator('#provenance').innerText()).includes('ORDER_SCOPED'));
  check('Completed capture cannot be repeated from the frontend', await page.locator('#capture').isDisabled());
  await page.screenshot({path: path.join(output, `attempt-${attempt}-${viewportName}-complete.png`), fullPage: true});
  const denials = await page.evaluate(async other => {
    const targets = ['/api/runs/' + other, '/api/studio/query', '/api/runs'];
    const requests = [fetch(targets[0]), fetch(targets[1], {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}), fetch(targets[2], {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'})];
    return Promise.all(requests.map(async result => (await result).status));
  }, gatewayInfo.other_id);
  check('Actual cookie cannot open other run, Studio or create-run route', denials.every(status => status === 404));
  const after = await ask('state');
  check('Denied requests preserve two original runs and one capture', after.run_count === 2 && after.provider_calls.filter(c => c === 'capture').length === 1);
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#ticket-card').scrollIntoViewIfNeeded();
  await page.screenshot({path: path.join(output, `attempt-${attempt}-mobile.png`), fullPage: false});
  check('Scoped merchant remains usable without mobile horizontal overflow', await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  check('Reduced-motion preference remains respected', await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches && document.getAnimations().length === 0));
  check('No unhandled browser or gateway errors', errors.length === 0);
  check('No external network request escaped the isolated routes', unexpectedNetwork.length === 0);
  for (const name of sources) {
    assert.equal(createHash('sha256').update(fs.readFileSync(path.join(root, name))).digest('hex'), hashes[name], 'Behavior source changed during execution: ' + name);
    const dest = path.join(output, `source-attempt-${attempt}`, name);
    fs.mkdirSync(path.dirname(dest), {recursive: true});
    fs.copyFileSync(path.join(root, name), dest);
  }
  check('Frozen source hashes matched throughout execution', true);
  receipt.status = 'PASS';
} catch (error) {
  receipt.status = 'FAIL';
  receipt.failure = String(error?.message || error).replaceAll(gatewayInfo?.token || 'UNSET_TOKEN_SENTINEL', '[REDACTED]');
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
  if (child && child.exitCode === null) {
    child.stdin.end(JSON.stringify({action: 'stop'}) + '\n');
    await new Promise(resolve => {child.once('exit', resolve); setTimeout(() => {if (child.exitCode === null) child.kill(); resolve();}, 3000).unref();});
  }
  receipt.finished_at = new Date().toISOString();
  if (driverStderr) receipt.driver_stderr = driverStderr.replaceAll(gatewayInfo?.token || 'UNSET_TOKEN_SENTINEL', '[REDACTED]');
  fs.writeFileSync(path.join(output, `attempt-${attempt}.json`), JSON.stringify(receipt, null, 2));
  console.log(JSON.stringify({status: receipt.status, assertions: assertions.length, mode: receipt.mode,
    evidence: `evidence/runs/gateway-ui-v1/attempt-${attempt}.json`, failure: receipt.failure}));
}
