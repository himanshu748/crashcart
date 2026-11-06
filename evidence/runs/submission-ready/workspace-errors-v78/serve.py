"""Loopback-only LOCAL_TEST response injection; never loads credentials/providers.

The served workspace script is read byte-for-byte from the public checkout.
Run-state/payment evidence is synthetic and cannot establish live acceptance.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'var/github-publication-v1/repository'
LOCAL = Path(__file__).resolve().parent
OUT = ROOT / 'evidence/runs/continuation-v78/final'
MODE_FILE = LOCAL / 'response-mode.json'


def response_mode():
    if not MODE_FILE.exists():
        return {'mode': 'valid', 'target': 'detail'}
    config = json.loads(MODE_FILE.read_text())
    if config.get('mode') not in {'valid', 'structured401', 'HTML502', 'empty503', 'malformed503', 'scalar200'}:
        raise ValueError('unknown response mode')
    if config.get('target', 'detail') not in {'detail', 'all-api', 'post'}:
        raise ValueError('unknown response target')
    return config


def injected_response(mode):
    return {
        'structured401': (401, b'{"error":"Operator access required"}', 'application/json'),
        'HTML502': (502, b'<html><body>LOCAL_TEST upstream unavailable</body></html>', 'text/html'),
        'empty503': (503, b'', 'application/json'),
        'malformed503': (503, b'{', 'application/json'),
        'scalar200': (200, b'[]', 'application/json'),
    }.get(mode)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(PUBLIC))
    from crashcart.store import Store
    db_path = LOCAL / 'synthetic.sqlite3'
    # Avoid silently accumulating fixtures between distinct invocations.
    if db_path.exists():
        raise SystemExit('Existing synthetic DB: preserve it; choose a new harness directory for another run.')
    store = Store(db_path)
    runs = []
    fixtures = {}
    for label, merchant in [('ALPHA', 'defective'), ('BRAVO', 'healthy')]:
        run = store.create_run(f'LOCAL_TEST {label}: USD29 buys one ticket within 60 seconds. Synthetic response-check data; no payment.', mode='LOCAL_TEST', fault={'kind': 'response_loss', 'merchant': merchant})
        purchase = store.purchase_for_run(run['id'])
        store.record_event(run['id'], 'browser', 'customer_observation', {'browser_kind': 'LOCAL_BROWSER', 'url_path': '/', 'visible_text': f'LOCAL_TEST {label} observation: no payment attempted.'}, purchase_id=purchase['id'])
        runs.append(run)
        fixtures[run['id']] = {'run': run, 'purchase': purchase, 'merchant': store.merchant_state(purchase['id']), 'events': store.get_events(run['id']), 'operations': []}
    source = {}
    for name in ['app.js', 'index.html', 'style.css', 'marketing.js']:
        data = (PUBLIC / 'web' / name).read_bytes()
        source[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    (OUT / 'source.json').write_text(json.dumps({'mode': 'LOCAL_TEST', 'source': source, 'script_instrumentation': False, 'provider_calls': 0}, indent=2) + '\n')
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def journal(self, body=None):
            entry = {'at': datetime.now(timezone.utc).isoformat(), 'method': self.command, 'path': urlsplit(self.path).path, 'response_mode': response_mode()}
            if body is not None:
                entry['body'] = body.decode('utf-8', errors='replace')
            with lock:
                with (OUT / 'requests.jsonl').open('a') as f:
                    f.write(json.dumps(entry) + '\n')

        def send(self, status, body, kind='application/json'):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def injection(self, path):
            config = response_mode()
            target = config.get('target', 'detail')
            applies = (target == 'all-api' and path.startswith('/api/')) or (target == 'detail' and path in {'/api/runs/' + run_id for run_id in fixtures}) or (target == 'post' and self.command == 'POST' and path.startswith('/api/'))
            return injected_response(config['mode']) if applies else None

        def do_GET(self):
            self.journal()
            path = urlsplit(self.path).path
            if path == '/healthz':
                return self.send(200, {'status': 'ok', 'database': 'ok', 'mode': 'LOCAL_TEST'})
            if path == '/':
                return self.send(200, (PUBLIC / 'web/index.html').read_bytes(), 'text/html')
            if path in {'/app.js', '/marketing.js', '/style.css'}:
                kind = 'text/css' if path.endswith('css') else 'application/javascript'
                return self.send(200, (PUBLIC / 'web' / path[1:]).read_bytes(), kind)
            injected = self.injection(path)
            if injected:
                return self.send(*injected)
            if path == '/api/prerequisites':
                return self.send(200, {'gateway': {'configured': True, 'missing': []}})
            if path == '/api/runs':
                return self.send(200, {'runs': runs})
            if path.startswith('/api/runs/') and path[len('/api/runs/'):] in fixtures:
                return self.send(200, fixtures[path[len('/api/runs/'):]])
            return self.send(404, {'error': 'LOCAL_TEST_ROUTE_UNAVAILABLE'})

        def do_POST(self):
            size = int(self.headers.get('Content-Length', '0'))
            if size > 8192:
                return self.send(413, {'error': 'LOCAL_TEST_REQUEST_TOO_LARGE'})
            body = self.rfile.read(size)
            self.journal(body)
            injected = self.injection(urlsplit(self.path).path)
            if injected:
                return self.send(*injected)
            return self.send(405, {'error': 'LOCAL_TEST_NO_MUTATIONS'})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    receipt = {'url': f'http://127.0.0.1:{server.server_port}/?run={runs[0]["id"]}', 'pid': os.getpid(), 'mode': 'LOCAL_TEST', 'external_access': False, 'run_ids': {label: run['id'] for label, run in zip(['ALPHA', 'BRAVO'], runs)}, 'mode_file': str(MODE_FILE), 'request_journal': str(OUT / 'requests.jsonl'), 'max_lifetime_seconds': 1200}
    (OUT / 'server.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt), flush=True)
    timer = threading.Timer(1200, server.shutdown)
    timer.daemon = True
    timer.start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        timer.cancel()


if __name__ == '__main__':
    main()
