#!/usr/bin/env python3
"""Local paused-mode check only. No host, credentials or provider calls."""
import json
from pathlib import Path
import sys
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11+ required')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from crashcart.judge import prepare_review
from crashcart.public_live import Controller, make_server, private_store

files = prepare_review()
for name in ('index.html', 'product.html', 'demo.html', 'healthz', 'live.html', 'live.js', 'live.css', 'timing.html'):
    assert name in files, name
with tempfile.TemporaryDirectory(prefix='crashcart-paused-preflight-') as folder:
    store = private_store(Path(folder) / 'workspace.sqlite3')
    env = {'CRASHCART_PUBLIC_URL': 'http://127.0.0.1:8767', 'CRASHCART_PUBLIC_LIVE_ENABLED': '0'}
    controller = Controller(store, env, dispatch=lambda *_args: (_ for _ in ()).throw(AssertionError('Provider dispatch forbidden')))
    server = make_server(('127.0.0.1', 0), controller, files)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = 'http://127.0.0.1:' + str(server.server_address[1])
    try:
        for path in ('/', '/product', '/example', '/healthz', '/live.html', '/timing.html'):
            with urlopen(origin + path, timeout=3) as response:
                assert response.status == 200, path
        with urlopen(origin + '/api/live/config', timeout=3) as response:
            config = json.load(response)
            cookie = response.headers['Set-Cookie'].split(';')[0]
        assert config['enabled'] is False and config['mode'] == 'SAVED_REPLAY'
        assert config['reason'] == 'PUBLIC_LIVE_PAUSED'
        request = Request(origin + '/api/live/runs', data=b'{}', method='POST', headers={
            'Content-Type': 'application/json', 'Cookie': cookie,
            'Origin': env['CRASHCART_PUBLIC_URL'], 'X-CSRF-Token': config['csrf_token'],
            'Idempotency-Key': 'paused-preflight-0001'})
        try:
            urlopen(request, timeout=3)
            raise AssertionError('Paused server admitted a checkout')
        except HTTPError as error:
            assert error.code == 503
            assert json.load(error)['error']['code'] == 'PUBLIC_LIVE_PAUSED'
        with urlopen(origin + '/demo.html', timeout=3) as response:
            assert response.status == 200
        print(json.dumps({'public_export_files': len(files), 'static_paths_200': True,
                          'live_default_paused': True, 'checkout_denied': True,
                          'provider_dispatches': 0, 'host_contacted': False}))
    finally:
        server.shutdown()
        server.server_close()
        controller.close()
        thread.join(timeout=3)
