"""Synthetic provider transport regression; no actual PayPal call or payment."""
from copy import deepcopy
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from crashcart.paypal import PayPalError
from crashcart.service import MerchantService
from crashcart.store import Store
from crashcart.worker import work
from tests.test_service import FakePayPal


class WorkerRecoveryTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'recovery.sqlite3'
        self.store = Store(self.path)
        self.provider = FakePayPal()
        self.service = MerchantService(self.store, lambda: self.provider)
        self.run = self.store.create_run('Synthetic worker recovery', fault={'kind': 'response_loss', 'merchant': 'healthy'})
        self.order = self.service.create_order(self.run['id'])
        self.provider.order['status'] = 'APPROVED'
        # Provider-side completion only: merchant still has no confirmed payment
        # or ticket until a subsequent independent read returns usable evidence.
        self.provider.capture_order(self.order['order_id'], {}, 'synthetic-capture')

    def jobs(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM jobs WHERE run_id=? ORDER BY semantic_key', (self.run['id'],))]

    def cycle(self):
        with patch('crashcart.service.MerchantService', return_value=self.service), redirect_stdout(io.StringIO()):
            work(self.path, once=True)

    def test_transient_read_failure_requeues_then_recovers_at_original_cadence(self):
        self.assert_transient_recovery('TIMEOUT')

    def test_transport_failure_uses_the_same_bounded_recovery(self):
        self.assert_transient_recovery('TRANSPORT_ERROR')

    def assert_transient_recovery(self, code):
        now = time.time()
        with patch('crashcart.worker.time.time', return_value=now) as clock, \
                patch.object(self.provider, 'get_order', side_effect=[
                    PayPalError(code, 'Synthetic read interruption', ambiguous=True),
                    deepcopy(self.provider.order),
                ]) as read:
            self.store.enqueue(self.run['id'], 'reconcile', {'attempt': 0}, semantic_key='recovery-0')
            self.cycle()
            self.assertEqual(1, read.call_count)
            self.assertFalse(self.store.get_purchase(self.run['purchase_id'])['payment_confirmed'])
            self.assertEqual(0, self.store.merchant_state(self.run['purchase_id'])['ticket_count'])
            jobs = self.jobs()
            self.assertEqual(['recovery-0', 'recovery-1'], [job['semantic_key'] for job in jobs])
            self.assertEqual(['FAILED', 'PENDING'], [job['state'] for job in jobs])
            self.assertEqual(now + 2, jobs[1]['available_at'])
            self.assertIn('"attempt":1', jobs[1]['payload_json'].replace(' ', ''))
            clock.return_value = now + 1.99
            self.cycle()
            self.assertEqual(1, read.call_count, 'Recovery must not execute before the existing two-second interval')
            clock.return_value = now + 2
            self.cycle()
            self.assertEqual(2, read.call_count)
            self.assertEqual(['FAILED', 'COMPLETED'], [job['state'] for job in self.jobs()])
            self.assertEqual(1, self.store.merchant_state(self.run['purchase_id'])['ticket_count'])
            self.assertTrue(self.store.get_purchase(self.run['purchase_id'])['payment_confirmed'])
            self.assertIn('job_failed', [event['event_type'] for event in self.store.get_events(self.run['id'])])
            self.cycle()
            self.assertEqual(2, read.call_count, 'Successful recovery must not add another provider request')
            self.assertEqual(1, self.store.merchant_state(self.run['purchase_id'])['ticket_count'])

    def test_error_at_attempt_29_remains_failed_without_attempt_30(self):
        with patch.object(self.provider, 'get_order', side_effect=PayPalError('TIMEOUT', 'Synthetic final interruption')) as read:
            self.store.enqueue(self.run['id'], 'reconcile', {'attempt': 29}, semantic_key='recovery-29')
            self.cycle()
        self.assertEqual(1, read.call_count)
        self.assertEqual(['recovery-29'], [job['semantic_key'] for job in self.jobs()])
        self.assertEqual('FAILED', self.jobs()[0]['state'])
        self.assertEqual(0, self.store.merchant_state(self.run['purchase_id'])['ticket_count'])

    def test_other_errors_do_not_start_a_new_recovery_chain(self):
        with patch.object(self.provider, 'get_order', side_effect=ValueError('Synthetic programmer/configuration error')):
            self.store.enqueue(self.run['id'], 'reconcile', {'attempt': 0}, semantic_key='recovery-0')
            self.cycle()
        self.assertEqual(['recovery-0'], [job['semantic_key'] for job in self.jobs()])
        self.assertEqual('FAILED', self.jobs()[0]['state'])

    def test_sandbox_disabled_does_not_requeue(self):
        self.assert_permanent_failure('SANDBOX_DISABLED')

    def test_missing_configuration_does_not_requeue(self):
        self.assert_permanent_failure('MISSING_CONFIGURATION')

    def test_invalid_payment_evidence_does_not_requeue(self):
        self.assert_permanent_failure('INVALID_PAYMENT_EVIDENCE')

    def assert_permanent_failure(self, code):
        with patch.object(self.provider, 'get_order', side_effect=PayPalError(code, 'Synthetic permanent failure')) as read:
            self.store.enqueue(self.run['id'], 'reconcile', {'attempt': 0}, semantic_key='recovery-0')
            self.cycle()
            self.cycle()
        self.assertEqual(1, read.call_count)
        self.assertEqual(['recovery-0'], [job['semantic_key'] for job in self.jobs()])
        self.assertEqual('FAILED', self.jobs()[0]['state'])
        self.assertFalse(self.store.get_purchase(self.run['purchase_id'])['payment_confirmed'])
        self.assertEqual(0, self.store.merchant_state(self.run['purchase_id'])['ticket_count'])

    def test_inconclusive_read_retains_existing_cadence(self):
        now = time.time()
        self.provider.order['status'] = 'APPROVED'
        self.provider.order['purchase_units'][0].pop('payments')
        with patch('crashcart.worker.time.time', return_value=now):
            self.store.enqueue(self.run['id'], 'reconcile', {'attempt': 0}, semantic_key='recovery-0')
            self.cycle()
        jobs = self.jobs()
        self.assertEqual(['recovery-0', 'recovery-1'], [job['semantic_key'] for job in jobs])
        self.assertEqual(['COMPLETED', 'PENDING'], [job['state'] for job in jobs])
        self.assertEqual(now + 2, jobs[1]['available_at'])
        self.assertFalse(self.store.get_purchase(self.run['purchase_id'])['payment_confirmed'])
        self.assertEqual(0, self.store.merchant_state(self.run['purchase_id'])['ticket_count'])


if __name__ == '__main__':
    unittest.main()
