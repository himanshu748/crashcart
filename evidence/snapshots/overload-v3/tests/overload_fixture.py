"""Owned-loopback browser fixture; never changes application guard settings."""
from __future__ import annotations
import argparse
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import http.client
import json
from pathlib import Path
import select
import socket
import sys
import threading
import time

from crashcart.monitor_server import make_server
from crashcart.monitor_store import MonitorStore

LOCAL_TOKEN = 'local-overload-proof-fixture-only'
APP_FILES = ['crashcart/monitor_server.py', 'crashcart/monitor_ingress.py',
    'crashcart/monitor_store.py', 'crashcart/monitor_connectors.py',
    'web/monitor/index.html', 'web/monitor/style.css', 'web/monitor/app.js']


def utc_now():
    return datetime.now(timezone.utc).isoformat()


class OverloadFixture:
    def __init__(self, output, *, max_pressure_seconds=180, renew_after=6,
                 connect=socket.create_connection):
        if not .2 <= max_pressure_seconds <= 180 or not .1 <= renew_after <= 6:
            raise ValueError('Invalid bounded fixture duration')
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.connect = connect
        self.max_pressure_seconds = max_pressure_seconds
        self.renew_after = renew_after
        self.events = []
        self.clients = {}
        self.opened = self.connection_errors = self.recycled = 0
        self.provider_calls = 0
        self.stop_pressure = threading.Event()
        self.worker = None
        self.thread = None
        self.server = None
        self.domain = MonitorStore(self.output / 'synthetic.sqlite3')
        store = self.domain.create_store('Example store · local verification',
            'woocommerce', 'https://overload.example.test', 60)
        self.store_id = store['id']
        now = datetime.now(timezone.utc)
        paid = (now - timedelta(minutes=2)).isoformat()
        self.domain.upsert_order(self.store_id, 'local-order', display_number='EXAMPLE-101',
            currency='USD', total_minor=2900, payment_references=['LOCAL-CAPTURE'],
            fulfillment_status='unfulfilled', fulfilled_at=None,
            updated_at=paid, event_id='local-order-event')
        self.domain.record_payment(self.store_id, capture_id='LOCAL-CAPTURE',
            reference='LOCAL-CAPTURE', currency='USD', amount_minor=2900,
            completed_at=paid, event_id='local-payment-event')
        self.domain.scan(now.isoformat())
        self.baseline = self.facts()
        self.write('baseline', self.baseline)

    def write(self, name, data):
        target = self.output / (name + '.json')
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(data, indent=2) + '\n')
        temporary.replace(target)

    def event(self, name, **values):
        self.events.append({'event': name, 'at': utc_now(), **values})
        if len(self.events) <= 300:
            self.write('events', self.events)

    def facts(self):
        return {'orders': self.domain.orders(self.store_id),
                'alerts': self.domain.alerts(self.store_id)}

    def stats(self):
        with self.server._admission_lock:
            return {'active': self.server.active_handlers,
                    'peak': self.server.peak_handlers,
                    'limit': self.server.ingress_limits.max_handlers}

    def start(self):
        def no_provider(*args, **kwargs):
            self.provider_calls += 1
            raise AssertionError('Provider execution forbidden in local fixture')
        self.server = make_server(self.domain.path, port=0,
            environ={'CRASHCART_MONITOR_TOKEN': LOCAL_TOKEN}, paypal_factory=no_provider)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        root = Path(__file__).resolve().parents[1]
        self.write('server', {'mode': 'LOCAL_TEST; synthetic facts; no provider calls',
            'url': f'http://127.0.0.1:{self.server.server_port}',
            'limits': asdict(self.server.ingress_limits),
            'source_sha256': {f: hashlib.sha256((root / f).read_bytes()).hexdigest() for f in APP_FILES},
            'fixture_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'max_pressure_seconds': self.max_pressure_seconds})
        self.event('server_started', **self.stats())
        return self

    def probe(self):
        c = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=.5)
        try:
            c.request('GET', '/healthz')
            response = c.getresponse()
            return {'status': response.status, 'retry_after': response.getheader('Retry-After'),
                    'body': json.loads(response.read())}
        finally:
            c.close()

    @staticmethod
    def close_client(client):
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client.close()

    def begin(self):
        if self.worker is not None:
            raise RuntimeError('Only one pressure owner is allowed')
        end = time.monotonic() + 3
        while self.stats()['active'] and time.monotonic() < end:
            time.sleep(.01)
        if self.stats()['active']:
            raise RuntimeError('Cannot begin while another handler is active')
        self.worker = threading.Thread(target=self._maintain, daemon=True)
        self.worker.start()
        return self.assert_saturated('ready', timeout=8)

    def _maintain(self):
        started = time.monotonic()
        next_open = 0.0
        try:
            while not self.stop_pressure.is_set() and time.monotonic() - started < self.max_pressure_seconds:
                now = time.monotonic()
                # An OS-connected socket is not necessarily an admitted handler.
                for client in list(self.clients):
                    readable, _, _ = select.select([client], [], [], 0)
                    if readable:
                        self.close_client(client)
                        del self.clients[client]
                # Replace at most one lease per cycle; never drain all slots together.
                if self.clients:
                    oldest = min(self.clients, key=self.clients.get)
                    if now - self.clients[oldest] >= self.renew_after and now >= next_open:
                        self.close_client(oldest)
                        del self.clients[oldest]
                        self.recycled += 1
                if len(self.clients) < self.server.ingress_limits.max_handlers and now >= next_open:
                    next_open = now + .1  # At most ten connection attempts per second.
                    client = None
                    try:
                        client = self.connect(('127.0.0.1', self.server.server_port), timeout=.3)
                        client.sendall((f'POST /api/login HTTP/1.1\r\nHost: 127.0.0.1:{self.server.server_port}\r\n'
                                        'Content-Length: 1000\r\n\r\n').encode())
                        self.clients[client] = time.monotonic()
                        self.opened += 1
                    except OSError:
                        if client is not None:
                            self.close_client(client)
                        self.connection_errors += 1
                self.stop_pressure.wait(.01)
        except BaseException as error:
            self.event('pressure_worker_failed', error=type(error).__name__)
        finally:
            for client in list(self.clients):
                self.close_client(client)
                del self.clients[client]
            self.event('pressure_ended', opened=self.opened, connection_errors=self.connection_errors,
                       recycled=self.recycled, elapsed=time.monotonic() - started)

    def assert_saturated(self, name, *, timeout=2):
        end = time.monotonic() + timeout
        while time.monotonic() < end and not self.stop_pressure.is_set():
            before = self.stats()
            if before['active'] == before['limit']:
                try:
                    response = self.probe()
                except (OSError, http.client.HTTPException):
                    time.sleep(.02)
                    continue
                after = self.stats()
                if response['status'] == 503 and response['retry_after'] == '1' and after['active'] == after['limit']:
                    proof = {'at': utc_now(), 'before': before, 'after': after,
                             'probe': response, 'provider_calls': self.provider_calls}
                    self.write(name, proof)
                    return proof
            time.sleep(.02)
        raise RuntimeError('Saturation was not confirmed by counters and HTTP 503')

    def release(self):
        self.stop_pressure.set()
        if self.worker:
            self.worker.join(timeout=2)
            if self.worker.is_alive():
                raise RuntimeError('Pressure worker did not stop')
        end = time.monotonic() + 3
        while self.stats()['active'] and time.monotonic() < end:
            time.sleep(.01)
        proof = {'at': utc_now(), 'handlers': self.stats(), 'probe': self.probe(),
                 'facts_unchanged': self.facts() == self.baseline,
                 'provider_calls': self.provider_calls}
        if proof['handlers']['active'] or proof['probe']['status'] != 200 or not proof['facts_unchanged']:
            raise RuntimeError('Receiver did not recover with unchanged facts')
        self.write('released', proof)
        return proof

    def close(self):
        self.stop_pressure.set()
        if self.worker:
            self.worker.join(timeout=2)
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            end = time.monotonic() + 2
            while self.stats()['active'] and time.monotonic() < end:
                time.sleep(.01)
            self.write('cleanup', {'closed': True, **self.stats(), 'clients': len(self.clients),
                'worker_alive': bool(self.worker and self.worker.is_alive()),
                'provider_calls': self.provider_calls, 'facts_unchanged': self.facts() == self.baseline})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    fixture = OverloadFixture(args.output)
    try:
        fixture.start()
        print(json.dumps({'url': f'http://127.0.0.1:{fixture.server.server_port}', 'mode': 'LOCAL_TEST'}), flush=True)
        processed = set()
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline and not (fixture.output / 'stop').exists():
            for name in ['start', 'desktop-before', 'desktop-after', 'phone-before', 'phone-after', 'release']:
                if name in processed or not (fixture.output / name).exists():
                    continue
                if name == 'start':
                    fixture.begin()
                elif name == 'release':
                    fixture.release()
                else:
                    fixture.assert_saturated(name)
                processed.add(name)
            time.sleep(.02)
    except BaseException as error:
        fixture.write('failure', {'at': utc_now(), 'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        fixture.close()


if __name__ == '__main__':
    main()
