"""Local recovery probes; no store or provider execution."""
from contextlib import closing
import json
import os
from pathlib import Path
import select
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from crashcart.monitor_server import make_server
from crashcart.monitor_store import MonitorStore


class MonitorRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'monitor.sqlite3'
        self.domain = MonitorStore(self.path)
        self.sid = self.domain.create_store('Local recovery fixture', 'woocommerce',
                        'https://recovery.example.test/shop', 60)['id']
        self.domain.upsert_order(self.sid, 'local-order', display_number='EXAMPLE',
            currency='USD', total_minor=2900, payment_references=['local-capture'],
            fulfillment_status='unfulfilled', fulfilled_at=None,
            updated_at='2026-11-06T00:00:01+00:00', event_id='local-order-event')
        self.domain.record_payment(self.sid, capture_id='local-capture', reference='local-capture',
            currency='USD', amount_minor=2900, completed_at='2026-11-06T00:00:00+00:00',
            event_id='local-payment-event')
        self.domain.scan('2026-11-06T00:01:01+00:00')
        self.alert = self.domain.alerts(self.sid)[0]
        self.domain.acknowledge_alert(self.sid, self.alert['id'])
        self.before_orders = self.domain.orders(self.sid)
        self.before_alerts = self.domain.alerts(self.sid)

    def server(self, path):
        srv = make_server(path, port=0, start_scanner=False,
            environ={'CRASHCART_MONITOR_TOKEN': 'local-recovery-fixture-access-only'})
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        def stop():
            srv.shutdown();srv.server_close();thread.join(timeout=3)
        self.addCleanup(stop)
        return f'http://127.0.0.1:{srv.server_port}'

    def request(self, base, path, data=None, cookie=None):
        headers = {'X-CrashCart-Request': '1'}
        if cookie:headers['Cookie'] = cookie
        raw = json.dumps(data).encode() if data is not None else None
        if raw is not None:headers['Content-Type'] = 'application/json'
        try:response = urlopen(Request(base+path, raw, headers), timeout=3)
        except HTTPError as error:response = error
        with response:return response.status, json.loads(response.read()), response.headers.get('Set-Cookie')

    def test_online_backup_restores_facts_deadline_ack_but_not_sessions(self):
        original = self.server(self.path)
        status, _, cookie = self.request(original, '/api/login', {'token':'local-recovery-fixture-access-only'})
        self.assertEqual(status, 200)
        backup = Path(self.tmp.name) / 'backup.sqlite3'
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/monitor_backup.py'), str(self.path), str(backup)]
        with closing(sqlite3.connect(self.path)) as pending_writer:
            pending_writer.execute('BEGIN IMMEDIATE')
            pending_writer.execute("UPDATE monitor_orders SET display_number='NOT_COMMITTED_TO_BACKUP'")
            copied = subprocess.run(command, capture_output=True, text=True, timeout=15)
            pending_writer.rollback()
        self.assertEqual(copied.returncode, 0, copied.stderr)
        self.assertEqual(json.loads(copied.stdout)['integrity_check'], 'ok')
        refused = subprocess.run(command, capture_output=True, text=True, timeout=15)
        self.assertEqual(refused.returncode, 1)
        self.assertIn('Backup not completed', refused.stderr)
        self.domain.upsert_order(self.sid, 'later-order', display_number='LATER',
            currency='USD', total_minor=100, payment_references=[], fulfillment_status='unfulfilled',
            fulfilled_at=None, updated_at='2026-11-06T00:02:00+00:00', event_id='later-event')
        restored = self.server(backup)
        self.assertEqual(self.request(restored, '/api/stores', cookie=cookie)[0], 401)
        status, _, new_cookie = self.request(restored, '/api/login', {'token':'local-recovery-fixture-access-only'})
        self.assertEqual(status, 200)
        status, orders, _ = self.request(restored, f'/api/stores/{self.sid}/orders', cookie=new_cookie)
        self.assertEqual(status, 200);self.assertEqual(orders['orders'], self.before_orders)
        status, alerts, _ = self.request(restored, f'/api/stores/{self.sid}/alerts', cookie=new_cookie)
        self.assertEqual(status, 200);self.assertEqual(alerts['alerts'], self.before_alerts)
        self.assertIsNotNone(alerts['alerts'][0]['acknowledged_at'])
        self.assertEqual(orders['orders'][0]['deadline_at'], '2026-11-06T00:01:00.000000+00:00')
        with closing(sqlite3.connect(backup)) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_backup_exclusive_lock_fails_within_bound_and_keeps_source(self):
        backup = Path(self.tmp.name) / 'busy-backup.sqlite3'
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/monitor_backup.py'), str(self.path), str(backup)]
        with closing(sqlite3.connect(self.path)) as locked:
            locked.execute('BEGIN EXCLUSIVE')
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 1)
            self.assertIn('Backup not completed (TimeoutError)', result.stderr)
            self.assertNotIn('\"status\": \"ok\"', result.stdout)
            locked.rollback()
        self.assertTrue(backup.exists())
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.domain.orders(self.sid), self.before_orders)
        self.assertEqual(self.domain.alerts(self.sid), self.before_alerts)

    def test_backup_does_not_certify_empty_or_corrupt_unrelated_files(self):
        for label, raw in [('empty', b''), ('corrupt', b'not a SQLite database')]:
            with self.subTest(label=label):
                source = Path(self.tmp.name) / (label + '.sqlite3')
                destination = Path(self.tmp.name) / (label + '-copy.sqlite3')
                source.write_bytes(raw)
                result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / 'scripts/monitor_backup.py'), str(source), str(destination)], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 1)
                self.assertIn('Backup not completed', result.stderr)
                self.assertEqual(result.stdout, '')
                self.assertEqual(source.read_bytes(), raw)
                self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == 'posix', 'SIGKILL recovery probe requires POSIX')
    def test_killed_uncommitted_writer_rolls_back_saved_facts(self):
        code = """import sqlite3,sys
connection=sqlite3.connect(sys.argv[1])
connection.execute('BEGIN IMMEDIATE')
connection.execute("UPDATE monitor_orders SET display_number='UNCOMMITTED'")
print('transaction-open',flush=True)
sys.stdin.read()
"""
        process = subprocess.Popen([sys.executable,'-c',code,str(self.path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            ready,_,_ = select.select([process.stdout],[],[],5)
            self.assertTrue(ready,'Writer did not open its transaction within five seconds')
            self.assertEqual(process.stdout.readline().strip(),b'transaction-open')
            process.kill();process.communicate(timeout=5)
            self.assertEqual(process.returncode,-signal.SIGKILL)
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=5)
        recovered = MonitorStore(self.path)
        self.assertEqual(recovered.orders(self.sid),self.before_orders)
        self.assertEqual(recovered.alerts(self.sid),self.before_alerts)
        with closing(sqlite3.connect(self.path)) as db:self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        recovered.scan('2026-11-06T00:10:00+00:00')
        self.assertEqual(len(recovered.alerts(self.sid)),1)
        self.assertEqual(recovered.alerts(self.sid)[0]['deadline_at'],self.alert['deadline_at'])


if __name__ == '__main__':unittest.main()
