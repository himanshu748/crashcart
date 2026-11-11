"""Injected local transports test the public boundary, not live-provider proof."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import http.client
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from crashcart.public_live import Controller, LiveError, approval_link, make_server, private_store
from crashcart.model_ids import DEEPSEEK_MODEL_ID
from crashcart.paypal import PayPalError
from crashcart.service import MerchantService
from crashcart.store import Store
from tests.test_service import FakePayPal
from tests.test_model_allowance import terminal


class CompletedTestProvider(FakePayPal):
    def capture_order(self, *args):
        super().capture_order(*args)
        stamp = (datetime.now(timezone.utc) - timedelta(seconds=61)).isoformat()
        self.order['purchase_units'][0]['payments']['captures'][0]['update_time'] = stamp
        return deepcopy(self.order)


class SyntheticInvestigation:
    def __init__(self, store, service):
        self.store, self.service = store, service

    def run(self, run_id):
        evidence = []
        for tool in ['read_provider', 'read_merchant']:
            event = self.store.record_event(run_id, 'investigator', 'tool_observation',
                                           {'tool': tool, 'result': {'synthetic_test': True}})
            evidence.append(event['id'])
        self.store.record_event(run_id, 'investigator', 'model_plan', {'plan': {'tool': 'finish',
            'findings': [{'kind': 'observed', 'claim': 'Synthetic cited result.', 'evidence_ids': evidence}]}})
        return {'status': 'COMPLETED', 'model_mode': 'LIVE_MODEL',
                'final_verdict': self.service.reconcile(run_id)}


class PublicLiveFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name) / 'private.sqlite')
        ledger = Path(self.directory.name) / 'allowance.json'
        ledger.write_text(json.dumps({'version': 1, 'call_limit': 24, 'ceiling_micro_usd': 1000000, 'calls': []}))
        ledger.chmod(0o600)
        self.env = {'CRASHCART_PUBLIC_LIVE_ENABLED': '1', 'CRASHCART_PUBLIC_LIVE_AUTHORIZED_RUNS': '8',
            'CRASHCART_PUBLIC_LIVE_AUTHORIZED_UNTIL': '2026-12-22T00:00:00Z',
            'CRASHCART_PUBLIC_SESSION_SECRET': 'synthetic-session-secret-at-least-32-characters',
            'CRASHCART_PUBLIC_URL': 'https://crashcart.32.193.44.79.sslip.io',
            'CRASHCART_ALLOW_SANDBOX': '1', 'CRASHCART_ALLOW_MODEL': '1',
            'CRASHCART_MODEL_PROVIDER': 'modal', 'MODAL_MODEL': DEEPSEEK_MODEL_ID,
            'MODAL_API_KEY': 'synthetic-model-credential',
            'MODAL_BASE_URL': 'https://synthetic.modal.run', 'MODAL_ALLOWED_ORIGIN': 'https://synthetic.modal.run',
            'PAYPAL_CLIENT_ID': 'synthetic-app-id', 'PAYPAL_CLIENT_SECRET': 'synthetic-app-secret',
            'PAYPAL_WEBHOOK_ID': 'synthetic-webhook-id', 'CRASHCART_MODEL_ALLOWANCE_PATH': str(ledger)}
        self.dispatches = []
        self.provider = CompletedTestProvider()
        self.service = MerchantService(self.store, lambda: self.provider)
        self.controller = Controller(self.store, self.env, dispatch=lambda *args: self.dispatches.append(args),
            service_factory=lambda store: self.service, investigation_factory=SyntheticInvestigation)
        self.addCleanup(self.controller.close)
        self.owner, self.csrf, self.cookie = self.controller.session(None, create=True)
        self.cookie_header = self.cookie.split(';')[0]

    def start(self, key='synthetic-request-key-001'):
        with patch.dict('os.environ', {'CRASHCART_PUBLIC_URL': self.controller.origin}):
            status = self.controller.start(self.owner, '203.0.113.5', key)
            self.controller.run_create(status['run_id'])
        return status['run_id']

    def hook(self, run_id):
        purchase = self.store.purchase_for_run(run_id)
        event = {'id': 'event-synthetic-hook', 'event_type': 'PAYMENT.CAPTURE.COMPLETED',
                 'resource': {'id': 'CAPTURE_TEST', 'supplementary_data': {'related_ids': {'order_id': purchase['order_id']}}}}
        self.service.webhook({'test': 'verified'}, event, raw_body=json.dumps(event).encode())


class PublicLiveSessionTests(PublicLiveFixture):
    def test_signed_session_creation_and_validation_do_not_read_or_write_storage(self):
        with patch.object(self.store, 'connect', side_effect=AssertionError('Session storage forbidden')):
            owner, csrf, cookie = self.controller.session(None, create=True)
            self.assertRegex(cookie, r'crashcart_judge=v1\.')
            self.assertEqual((owner, csrf, None), self.controller.session(cookie.split(';')[0]))

    def test_signed_session_tampering_expiry_and_other_server_secret_are_rejected(self):
        token = self.cookie_header.split('=', 1)[1]
        self.assertRegex(token, r'^v1\.[0-9]+\.[A-Za-z0-9_-]+\.[a-f0-9]{64}$')
        parts = token.split('.')
        for index in (1, 2, 3):
            changed = list(parts)
            changed[index] = ('9' if changed[index][0] != '9' else '8') + changed[index][1:]
            with self.subTest(index=index), self.assertRaises(LiveError) as caught:
                self.controller.session('crashcart_judge=' + '.'.join(changed))
            self.assertEqual(401, caught.exception.status)
        with patch.object(self.controller, 'clock', return_value=int(parts[1])):
            with self.assertRaises(LiveError):
                self.controller.session(self.cookie_header)
        # A valid MAC alone must not permit a lifetime beyond two hours.
        expires = int(self.controller.clock()) + 7201
        payload = f'v1.{expires}.{parts[2]}'
        forged_long = payload + '.' + self.controller.digest('session:' + payload)
        with self.assertRaises(LiveError):
            self.controller.session('crashcart_judge=' + forged_long)
        other = Controller(self.store, {**self.env, 'CRASHCART_PUBLIC_SESSION_SECRET': 'different-private-secret-at-least-32-bytes'},
                           dispatch=lambda *_args: None)
        self.addCleanup(other.close)
        with self.assertRaises(LiveError):
            other.session(self.cookie_header)

    def test_session_owner_and_csrf_survive_restart_but_are_unique_per_nonce(self):
        other = Controller(self.store, self.env, dispatch=lambda *_args: None)
        self.addCleanup(other.close)
        self.assertEqual((self.owner, self.csrf, None), other.session(self.cookie_header))
        owner, csrf, cookie = other.session(None, create=True)
        self.assertNotEqual(owner, self.owner)
        self.assertNotEqual(csrf, self.csrf)
        self.assertNotEqual(cookie, self.cookie)
        self.assertNotIn(self.env['CRASHCART_PUBLIC_SESSION_SECRET'], cookie)
        self.assertNotIn(self.owner, cookie)
        # Unpublished, unsigned legacy cookies fail closed.
        with self.assertRaises(LiveError):
            other.session('crashcart_judge=' + 'a' * 54)


class PublicLiveTests(PublicLiveFixture):
    def test_manual_start_only_idempotent_and_correlated_to_owner(self):
        run_id = self.start()
        again = self.controller.start(self.owner, '203.0.113.5', 'synthetic-request-key-001')
        self.assertEqual(run_id, again['run_id'])
        self.assertEqual(1, len(self.dispatches))
        self.assertEqual(1, len(self.provider.calls))
        self.assertEqual('AWAITING_APPROVAL', again['state'])
        foreign, _, _ = self.controller.session(None, create=True)
        with self.assertRaises(LiveError) as caught:
            self.controller.status(run_id, foreign)
        self.assertEqual(404, caught.exception.status)
        self.assertEqual([], self.controller.timing(foreign)['cases'])

    def test_terminal_confirm_is_read_only_after_run_expiry_or_live_pause(self):
        run_id = self.start()
        initial_dispatches = list(self.dispatches)
        initial_calls = list(self.provider.calls)
        for state in ('COMPLETED', 'FAILED', 'CANCELLED', 'EXPIRED'):
            with self.store.connect(write=True) as db:
                db.execute("UPDATE public_live_runs SET state=?,expires_at=? WHERE run_id=?", (state, 0, run_id))
            self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '0'
            with self.subTest(state=state):
                result = self.controller.confirm(run_id, self.owner)
                self.assertEqual(state, result['state'])
        self.assertEqual(initial_dispatches, self.dispatches)
        self.assertEqual(initial_calls, self.provider.calls)

    def test_reserved_checkout_confirms_after_new_admission_capacity_is_used_but_not_if_paused(self):
        run_id = self.start()
        self.env['CRASHCART_PUBLIC_LIVE_AUTHORIZED_RUNS'] = '1'
        self.assertFalse(self.controller.configuration()['enabled'])
        self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '0'
        before = list(self.dispatches)
        with self.assertRaises(LiveError) as caught:
            self.controller.confirm(run_id, self.owner)
        self.assertEqual('PUBLIC_LIVE_PAUSED', caught.exception.code)
        self.assertEqual(before, self.dispatches)
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))
        self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '1'
        self.assertEqual('CONFIRMING', self.controller.confirm(run_id, self.owner)['state'])
        self.assertEqual((run_id, 'confirm'), self.dispatches[-1])

    def test_return_parameters_alone_never_allow_a_capture(self):
        run_id = self.start()
        self.controller.confirm(run_id, self.owner)
        self.controller.run_confirm(run_id)
        self.assertEqual('FAILED', self.controller.status(run_id, self.owner)['state'])
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))

    def test_complete_chain_keeps_signature_gate_and_real_finish_findings(self):
        run_id = self.start()
        self.provider.order['status'] = 'APPROVED'
        self.controller.confirm(run_id, self.owner)
        original = self.service.reconcile
        def reconcile(identity):
            result = original(identity)
            self.hook(identity)
            return result
        with patch.object(self.service, 'reconcile', side_effect=reconcile):
            self.controller.run_confirm(run_id)
        status = self.controller.status(run_id, self.owner)
        self.assertEqual('COMPLETED', status['state'])
        self.assertEqual(('FAIL', 'paid_without_ticket'), (status['verdict']['verdict'], status['verdict']['signature']))
        self.assertTrue(status['webhook']['verified'])
        self.assertEqual(0, status['tickets']['count'])
        self.assertEqual({'read_provider', 'read_merchant'}, {citation['kind'] for citation in status['investigation']['citations']})
        finish = status['investigation']['steps'][-1]
        self.assertEqual('finish', finish['action'])
        self.assertEqual(2, len(finish['evidence_ids']))

    def test_missing_notification_cannot_be_reported_complete_or_call_ai(self):
        run_id = self.start()
        self.provider.order['status'] = 'APPROVED'
        self.controller.confirm(run_id, self.owner)
        now = [self.controller.clock()]
        self.controller.clock = lambda: now[0]
        self.controller.sleep = lambda seconds: now.__setitem__(0, now[0] + seconds)
        with patch.object(SyntheticInvestigation, 'run', side_effect=AssertionError('Must not call AI')):
            self.controller.run_confirm(run_id)
        status = self.controller.status(run_id, self.owner)
        self.assertEqual('FAILED', status['state'])
        self.assertFalse(status['webhook']['verified'])
        self.assertEqual('WEBHOOK_NOT_CONFIRMED', status['error']['code'])
        self.assertEqual('demo.html', status['replay_url'])

    def test_paypal_error_is_terminal_with_fallback_not_success(self):
        run_id = self.start()
        self.provider.order['status'] = 'APPROVED'
        self.controller.confirm(run_id, self.owner)
        with patch.object(self.provider, 'capture_order', side_effect=PayPalError('TIMEOUT', 'synthetic timeout')):
            self.controller.run_confirm(run_id)
        status = self.controller.status(run_id, self.owner)
        self.assertEqual('FAILED', status['state'])
        self.assertIsNone(status['verdict'])
        self.assertEqual('demo.html', status['replay_url'])

    def test_kill_switch_stops_new_and_inflight_dispatch(self):
        run_id = self.start()
        self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '0'
        self.assertFalse(self.controller.configuration()['enabled'])
        with self.assertRaises(LiveError):
            self.controller.confirm(run_id, self.owner)
        self.controller.run_confirm(run_id)
        self.assertEqual('FAILED', self.controller.status(run_id, self.owner)['state'])
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))

    def test_existing_model_ledger_is_required_before_payment_and_never_reset(self):
        self.env.pop('CRASHCART_MODEL_ALLOWANCE_PATH')
        self.assertFalse(self.controller.configuration()['enabled'])
        with self.assertRaises(LiveError):
            self.start()
        self.assertEqual([], self.dispatches)
        self.assertEqual([], self.provider.calls)

    def test_pending_and_cancelled_runs_keep_their_full_legacy_capacity_hold(self):
        ledger = Path(self.env['CRASHCART_MODEL_ALLOWANCE_PATH'])
        data = json.loads(ledger.read_text())
        data['calls'] = [terminal(index) for index in range(1, 22)]
        ledger.write_text(json.dumps(data))
        first = self.controller.start(self.owner, '203.0.113.5', 'synthetic-capacity-first')
        for cancelled in (False, True):
            if cancelled:
                self.controller.cancel(first['run_id'], self.owner)
            with self.subTest(cancelled=cancelled), self.assertRaises(LiveError):
                self.controller.start(self.owner, '203.0.113.6', 'synthetic-capacity-second')
        self.assertEqual(1, len(self.dispatches))
        self.assertEqual([], self.provider.calls)
        self.assertEqual(first['run_id'], self.controller.start(self.owner, '203.0.113.5', 'synthetic-capacity-first')['run_id'])
        data['calls'].append(terminal(22, state='RESERVED'))
        ledger.write_text(json.dumps(data))
        self.assertEqual(first['run_id'], self.controller.start(self.owner, '203.0.113.5', 'synthetic-capacity-first')['run_id'])

    def test_separate_controllers_cannot_overbook_pending_legacy_calls(self):
        ledger = Path(self.env['CRASHCART_MODEL_ALLOWANCE_PATH'])
        data = json.loads(ledger.read_text())
        data['calls'] = [terminal(index) for index in range(1, 19)]
        ledger.write_text(json.dumps(data))
        other = Controller(self.store, self.env, dispatch=lambda *args: self.dispatches.append(args))
        self.addCleanup(other.close)
        def admit(index):
            controller = self.controller if index % 2 else other
            try:
                return controller.start(self.owner, f'203.0.113.{index+1}', f'synthetic-parallel-{index:016d}')['run_id']
            except LiveError:
                return None
        with ThreadPoolExecutor(max_workers=4) as pool:
            result = list(pool.map(admit, range(4)))
        self.assertEqual(2, sum(identity is not None for identity in result))
        self.assertEqual(2, len(self.dispatches))

    def test_known_usage_cost_is_reserved_before_another_checkout(self):
        ledger = Path(self.env['CRASHCART_MODEL_ALLOWANCE_PATH'])
        data = json.loads(ledger.read_text())
        data['calls'] = [terminal(1, cost=900001)]
        ledger.write_text(json.dumps(data))
        with self.assertRaises(LiveError):
            self.controller.start(self.owner, '203.0.113.5', 'synthetic-capacity-cost')
        self.assertEqual([], self.dispatches)

    def test_cancel_and_expiry_do_not_resume_payment_work(self):
        run_id = self.start()
        self.controller.cancel(run_id, self.owner)
        self.controller.run_confirm(run_id)
        self.assertEqual('CANCELLED', self.controller.status(run_id, self.owner)['state'])
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))

    def test_projection_omits_raw_provider_payer_secrets_and_foreign_runs(self):
        run_id = self.start()
        self.provider.order['payer'] = {'email_address': 'private-payer@example.invalid'}
        data = json.dumps(self.controller.status(run_id, self.owner))
        self.assertNotIn('private-payer', data)
        self.assertNotIn('synthetic-app-secret', data)
        self.assertNotIn('provider_response', data)
        self.assertEqual(run_id, self.controller.timing(self.owner)['cases'][0]['run_id'])

    def test_no_paypal_live_or_foreign_approval_destination(self):
        for value in ['https://www.paypal.com/checkoutnow?token=abc', 'https://sandbox.paypal.com.evil.test/checkoutnow',
                      'javascript:alert(1)', '//sandbox.paypal.com/checkoutnow', 'https://user@sandbox.paypal.com/checkoutnow']:
            with self.subTest(value=value), self.assertRaises(LiveError):
                approval_link(value)

    def test_hard_worker_timeout_kills_and_reaps_a_real_local_child(self):
        run_id = self.start()
        proc = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'], start_new_session=True)
        self.addCleanup(lambda: proc.poll() is None and proc.kill())
        wait = proc.wait
        def bounded_wait(timeout=None):
            return wait(timeout=.05 if timeout is not None else None)
        with patch('crashcart.public_live.subprocess.Popen', return_value=proc), patch.object(proc, 'wait', side_effect=bounded_wait):
            self.controller._child(run_id, 'create')
        self.assertIsNotNone(proc.returncode)
        self.assertEqual('FAILED', self.controller.status(run_id, self.owner)['state'])
        self.assertEqual('RUN_TIMEOUT', self.controller.status(run_id, self.owner)['error']['code'])

    def test_investigation_without_both_observed_citations_cannot_finish(self):
        run_id = self.start()
        self.provider.order['status'] = 'APPROVED'
        self.controller.confirm(run_id, self.owner)
        original = self.service.reconcile
        def reconcile(identity):
            result = original(identity)
            self.hook(identity)
            return result
        class UncitedInvestigation(SyntheticInvestigation):
            def run(inner, identity):
                return {'status': 'COMPLETED', 'model_mode': 'LIVE_MODEL',
                        'final_verdict': inner.service.reconcile(identity)}
        self.controller.investigation_factory = UncitedInvestigation
        with patch.object(self.service, 'reconcile', side_effect=reconcile):
            self.controller.run_confirm(run_id)
        status = self.controller.status(run_id, self.owner)
        self.assertEqual('FAILED', status['state'])
        self.assertIsNone(status['verdict'])


class PublicLiveHTTPTests(PublicLiveFixture):
    def setUp(self):
        super().setUp()
        self.server = make_server(('127.0.0.1', 0), self.controller, {
            'index.html': ('text/html', b'<h1>Saved example</h1>'),
            'data.json': ('application/json', b'{"mode":"RECORDED_REPLAY"}')})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, *, headers=None, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def post(self, path, **extra):
        headers = {'Cookie': self.cookie_header, 'X-CSRF-Token': self.csrf, 'Origin': self.controller.origin,
                   'Content-Type': 'application/json', 'Idempotency-Key': 'synthetic-http-action-001', **extra}
        return self.request('POST', path, headers=headers, body='{}')

    def test_more_than_512_cookieless_config_gets_do_not_exhaust_or_grow_session_storage(self):
        with self.store.connect() as db:
            before = {row[0]: db.execute('SELECT COUNT(*) FROM "' + row[0] + '"').fetchone()[0]
                      for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for index in range(520):
            status, headers, raw = self.request('GET', '/api/live/config')
            self.assertEqual(200, status, f'cookieless request {index + 1}')
            self.assertTrue(json.loads(raw)['csrf_token'])
            self.assertIn('HttpOnly', headers['Set-Cookie'])
        with self.store.connect() as db:
            after = {row[0]: db.execute('SELECT COUNT(*) FROM "' + row[0] + '"').fetchone()[0]
                     for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(before, after)
        self.assertEqual([], self.dispatches)
        self.assertEqual([], self.provider.calls)

    def test_expired_cookie_recovery_changes_csrf_and_cannot_open_prior_private_case(self):
        run_id = self.start()
        expiry = int(self.cookie_header.split('=', 1)[1].split('.')[1])
        with patch.object(self.controller, 'clock', return_value=expiry):
            status, headers, body = self.request('GET', '/api/live/config', headers={'Cookie': self.cookie_header})
            self.assertEqual(200, status)
            fresh = headers['Set-Cookie'].split(';')[0]
            self.assertNotEqual(fresh, self.cookie_header)
            self.assertNotEqual(self.csrf, json.loads(body)['csrf_token'])
            self.assertEqual(401, self.request('GET', '/api/live/runs/' + run_id,
                                             headers={'Cookie': self.cookie_header})[0])
            self.assertEqual(403, self.post('/api/live/runs', Cookie=fresh)[0])
        self.assertEqual(1, len(self.dispatches))
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))

    def test_completed_case_http_remains_readable_and_confirm_does_not_dispatch_when_paused(self):
        run_id = self.start()
        self.controller.update(run_id, 'COMPLETED')
        self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '0'
        before = list(self.dispatches)
        status, _, body = self.request('GET', '/api/live/runs/' + run_id,
                                       headers={'Cookie': self.cookie_header})
        self.assertEqual(200, status)
        self.assertEqual('COMPLETED', json.loads(body)['state'])
        status, _, body = self.post('/api/live/runs/' + run_id + '/confirm')
        self.assertEqual(202, status)
        self.assertEqual('COMPLETED', json.loads(body)['state'])
        self.assertEqual(before, self.dispatches)
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))

    def test_return_redirect_marks_owned_navigation_but_never_captures(self):
        run_id = self.start()
        before = list(self.dispatches)
        status, headers, _ = self.request('GET', '/return?run=' + run_id + '&token=UNTRUSTED',
                                          headers={'Cookie': self.cookie_header})
        self.assertEqual(303, status)
        self.assertEqual('/live.html?run=' + run_id + '&approval_return=1', headers['Location'])
        self.assertNotIn('UNTRUSTED', headers['Location'])
        status, headers, _ = self.request('GET', '/cancel?run=' + run_id, headers={'Cookie': self.cookie_header})
        self.assertEqual(303, status)
        self.assertEqual('/live.html?run=' + run_id + '&cancel=1', headers['Location'])
        self.assertEqual(before, self.dispatches)
        self.assertFalse(any(call[0] == 'capture' for call in self.provider.calls))
        foreign, _, cookie = self.controller.session(None, create=True)
        self.assertNotEqual(foreign, self.owner)
        self.assertEqual(404, self.request('GET', '/return?run=' + run_id,
                                         headers={'Cookie': cookie.split(';')[0]})[0])

    def test_config_is_safe_and_http_cookie_has_expiry_scope_and_csrf(self):
        status, headers, raw = self.request('GET', '/api/live/config')
        self.assertEqual(200, status)
        config = json.loads(raw)
        self.assertTrue(config['enabled'])
        self.assertTrue(config['csrf_token'])
        for part in ['HttpOnly', 'SameSite=Lax', 'Secure', 'Max-Age=7200']:
            self.assertIn(part, headers['Set-Cookie'])
        for secret in ['synthetic-app-secret', 'synthetic-model-credential', 'synthetic-webhook-id']:
            self.assertNotIn(secret, raw.decode())

    def test_csrf_origin_cookie_and_owner_are_all_enforced(self):
        for extra in [{'X-CSRF-Token': 'wrong'}, {'Cookie': ''}, {'Origin': 'https://evil.example'}]:
            with self.subTest(extra=extra):
                status, _, _ = self.post('/api/live/runs', **extra)
                self.assertIn(status, [401, 403])
        self.assertEqual([], self.dispatches)
        status, _, raw = self.post('/api/live/runs')
        self.assertEqual(202, status)
        run_id = json.loads(raw)['run_id']
        self.assertEqual(401, self.request('GET', '/api/live/runs/' + run_id)[0])
        self.assertEqual(200, self.request('GET', '/api/live/runs/' + run_id, headers={'Cookie': self.cookie_header})[0])

    def test_forwarded_headers_cannot_reset_client_quota(self):
        for index in range(3):
            self.assertEqual(202, self.post('/api/live/runs', **{'Idempotency-Key': f'synthetic-http-{index:016d}',
                'X-Forwarded-For': f'203.0.113.{index}'})[0])
        self.assertEqual(429, self.post('/api/live/runs', **{'Idempotency-Key': 'synthetic-http-fourth',
            'X-Forwarded-For': '198.51.100.9'})[0])
        self.assertEqual(400, self.post('/api/live/runs', **{'X-CrashCart-Client-IP': '198.51.100.8'})[0])

    def test_webhook_missing_signature_rejected_before_any_provider_call(self):
        status, _, _ = self.post('/api/live/webhook')
        self.assertEqual(400, status)
        self.assertEqual([], self.provider.webhook_inputs)
        self.assertEqual([], self.dispatches)

    def webhook_post(self, order_id='UNKNOWN', *, capture='CAPTURE_TEST'):
        event = {'id': 'SYNTHETIC_EVENT', 'event_type': 'PAYMENT.CAPTURE.COMPLETED',
                 'resource': {'id': capture, 'supplementary_data': {'related_ids': {'order_id': order_id}}}}
        return self.request('POST', '/api/live/webhook', headers={
            'Content-Type': 'application/json', 'Paypal-Auth-Algo': 'SHA256withRSA',
            'Paypal-Cert-Url': 'https://api.sandbox.paypal.com/v1/notifications/certs/SYNTHETIC',
            'Paypal-Transmission-Id': 'SYNTHETIC', 'Paypal-Transmission-Sig': 'SYNTHETIC',
            'Paypal-Transmission-Time': '2026-11-11T00:00:00Z'}, body=json.dumps(event))

    def test_unknown_or_paused_webhook_never_spawns_provider_verification(self):
        with patch('crashcart.public_live.subprocess.Popen') as spawn:
            self.assertEqual(400, self.webhook_post()[0])
            self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '0'
            self.assertEqual(503, self.webhook_post()[0])
            spawn.assert_not_called()

    def test_known_webhook_attempts_are_bounded_and_still_need_real_verification(self):
        run_id = self.start()
        self.controller.confirm(run_id, self.owner)
        order = self.store.purchase_for_run(run_id)['order_id']
        proc = Mock(returncode=1)
        proc.communicate.return_value = (b'', None)
        with patch('crashcart.public_live.subprocess.Popen', return_value=proc) as spawn:
            self.assertEqual(400, self.webhook_post(order)[0])
            self.assertEqual(400, self.webhook_post(order)[0])
            self.assertEqual(429, self.webhook_post(order)[0])
            self.assertEqual(2, spawn.call_count)
        self.assertFalse(self.controller.status(run_id, self.owner)['webhook']['verified'])

    def test_no_operator_api_or_private_file_surface(self):
        for path in ['/api/runs', '/.env', '/state.sqlite', '/%2e%2e/.env', '/api/live/runs/run_' + 'a' * 32]:
            with self.subTest(path=path):
                self.assertIn(self.request('GET', path)[0], [401, 404])

    def test_saved_json_bytes_remain_available_while_live_runs_are_paused(self):
        self.env['CRASHCART_PUBLIC_LIVE_ENABLED'] = '0'
        status, headers, body = self.request('GET', '/data.json')
        self.assertEqual(200, status)
        self.assertEqual('application/json', headers['Content-Type'])
        self.assertEqual({'mode': 'RECORDED_REPLAY'}, json.loads(body))


class PrivateDatabaseTests(unittest.TestCase):
    def test_rejects_existing_shared_database_before_changing_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite'
            Store(path)
            path.chmod(0o644)
            with self.assertRaises(LiveError):
                private_store(path)
            self.assertEqual(0o644, path.stat().st_mode & 0o777)

    def test_rejects_hardlinks_and_group_writable_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite'
            Store(path)
            path.chmod(0o600)
            alias = Path(directory) / 'alias.sqlite'
            os.link(path, alias)
            with self.assertRaises(LiveError):
                private_store(path)
            alias.unlink()
            path.parent.chmod(0o770)
            with self.assertRaises(LiveError):
                private_store(path)
            path.parent.chmod(0o700)

    def test_new_database_is_private_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.sqlite'
            private_store(path)
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
            alias = Path(directory) / 'alias.sqlite'
            alias.symlink_to(path)
            with self.assertRaises(LiveError):
                private_store(alias)


if __name__ == '__main__':
    unittest.main()
