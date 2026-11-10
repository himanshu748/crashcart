"""Optional Studio packaging: real replay data, licence gate and read-only HTTP."""
from copy import deepcopy
from datetime import datetime
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

from crashcart import judge, recorded_studio as studio


class RecordedStudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original_open = io.open

        def no_env(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)) and Path(path).name == '.env':
                raise AssertionError('Recorded export must not read .env')
            return original_open(path, *args, **kwargs)

        with patch.object(socket.socket, 'connect', side_effect=AssertionError('No outgoing request')), \
                patch('socket.create_connection', side_effect=AssertionError('No outgoing request')), \
                patch('io.open', side_effect=no_env):
            cls.base = judge.prepare_review(exported=True)
        cls.review = json.loads(cls.base['data.json'][1])

    def build(self, directory, licensed=True):
        """Synthetic compiled assets test packaging, not actual SDK execution."""
        directory.mkdir()
        (directory / studio.BUILD_MARKER).write_text(json.dumps({'version': 1, 'licensed': licensed}))
        (directory / 'index.html').write_text('<!doctype html><html><head><meta name="csp-nonce" content="__STYLE_NONCE__">'
                                             '<link rel="stylesheet" href="./main.css"></head><body>'
                                             '<script src="./main.js"></script></body></html>')
        (directory / 'main.js').write_text('/* synthetic packaging test only */')
        (directory / 'main.css').write_text('/* synthetic packaging test only */')
        return directory

    def prepare(self, assets):
        with patch.object(studio.judge, 'prepare_review', return_value=dict(self.base)):
            return studio.prepare_recorded_site(assets)

    def test_actual_replay_projection_and_source_links(self):
        data = studio.project_records(self.review)
        self.assertEqual({'version', 'runs', 'details', 'rows', 'dataset_sha256', 'snapshot_at', 'historical_ai'}, set(data))
        self.assertEqual('recorded-studio-v1', data['version'])
        self.assertEqual(self.review['historical_ai'], data['historical_ai'])
        self.assertFalse(data['historical_ai']['same_case_as_public_faulty_replay'])
        self.assertEqual([0, 1], [row['ticket_count'] for row in data['rows']])
        for variant, run, row in zip(('defective', 'healthy'), data['runs'], data['rows']):
            case = self.review['cases'][variant]
            self.assertEqual(case['receipt']['run_id'], run['id'])
            self.assertEqual({**case['execution']['fault'], 'merchant': case['receipt']['merchant_variant']}, run['fault'])
            self.assertEqual(variant, run['fault']['merchant'])
            self.assertEqual('RECORDED_REPLAY', run['mode'])
            self.assertIn('within 60 seconds', run['promise'])
            self.assertEqual(2900, row['amount'])
            self.assertEqual('COMPLETED', row['payment_state'])
            detail = data['details'][run['id']]
            self.assertEqual([{key: ticket[key] for key in ('id', 'created_at')} for ticket in case['merchant']['tickets']],
                             detail['merchant']['tickets'])
            ids = {event['id'] for event in detail['events']}
            self.assertTrue(all(value in ids for value in row['source_ids'].values()))
            for original, projected in zip(case['events'], detail['events']):
                self.assertEqual(original['payload'], projected['payload'])
                self.assertNotIn('payload_json', projected)
            self.assertNotIn('confirmation_json', detail['purchase'])
        healthy = data['details'][data['runs'][1]['id']]
        captured = datetime.fromisoformat(healthy['purchase']['capture_completed_at'].replace('Z', '+00:00'))
        delivered = datetime.fromisoformat(healthy['merchant']['tickets'][0]['created_at'].replace('Z', '+00:00'))
        self.assertAlmostEqual(32.261423, (delivered - captured).total_seconds())
        expected = hashlib.sha256(json.dumps(data['rows'], sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        self.assertEqual(expected, data['dataset_sha256'])

    def test_unknown_storage_fields_are_omitted_and_credential_payloads_rejected(self):
        review = deepcopy(self.review)
        review['cases']['defective']['purchase']['private_token'] = 'PRIVATE_SENTINEL'
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(studio.project_records(review)))
        for key in ('password', 'AG_STUDIO_LICENSE_KEY', 'authorization', 'client_secret'):
            review = deepcopy(self.review)
            review['cases']['defective']['events'][0]['payload']['nested'] = [{key: 'PRIVATE_SENTINEL'}]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'Credential-like'):
                studio.project_records(review)
        for mutate in (lambda case: case['receipt'].update(network_calls=1),
                       lambda case: case['receipt'].update(mode='LIVE_SANDBOX'),
                       lambda case: case['purchase'].update(run_id='other'),
                       lambda case: case['merchant'].update(ticket_count=1),
                       lambda case: case['events'][0].update(run_id='other')):
            review = deepcopy(self.review)
            mutate(review['cases']['defective'])
            with self.assertRaises(ValueError):
                studio.project_records(review)

    def test_absent_or_unlicensed_sdk_never_leaves_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            for assets in (Path(folder) / 'missing', self.build(Path(folder) / 'unlicensed', False)):
                files = self.prepare(assets)
                self.assertEqual({'explorer/index.html'}, set(files) - set(self.base))
                self.assertIn(b'not an AG Studio dashboard', files['explorer/index.html'][1])
                self.assertIsNone(studio._nonce(files))
                for name, original in self.base.items():
                    self.assertEqual(original, files[name])

    def test_licensed_assets_keep_default_bundle_identical_and_do_not_read_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            assets = self.build(Path(folder) / 'compiled')
            with patch.dict(os.environ, {'PAYPAL_CLIENT_SECRET': 'PRIVATE_SENTINEL',
                                         'AG_STUDIO_LICENSE_KEY': 'PRIVATE_SENTINEL'}):
                files = self.prepare(assets)
            self.assertEqual({'explorer/index.html', 'explorer/main.js', 'explorer/main.css', 'explorer/records.json'}, set(files) - set(self.base))
            for name, original in self.base.items():
                self.assertEqual(original, files[name])
            self.assertNotIn(b'__STYLE_NONCE__', files['explorer/index.html'][1])
            self.assertTrue(studio._nonce(files))
            self.assertEqual(studio.project_records(self.review), json.loads(files['explorer/records.json'][1]))
            for _, body in files.values():
                self.assertNotIn(b'PRIVATE_SENTINEL', body)

    def test_malformed_manifest_unsafe_assets_and_data_override_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            for index, declaration in enumerate(({'version': True, 'licensed': True}, {'version': 1, 'licensed': 'true'},
                                                 {'version': 1, 'licensed': True, 'key': 'no'}, [])):
                assets = self.build(Path(folder) / str(index))
                (assets / studio.BUILD_MARKER).write_text(json.dumps(declaration))
                with self.subTest(declaration=declaration), self.assertRaisesRegex(ValueError, 'build declaration'):
                    self.prepare(assets)
            for index, filename in enumerate(('records.json', '.env', 'secret.pem')):
                assets = self.build(Path(folder) / ('bad-' + str(index)))
                (assets / filename).write_text('{}')
                with self.subTest(filename=filename), self.assertRaises(ValueError):
                    self.prepare(assets)
            assets = self.build(Path(folder) / 'symlink')
            (assets / 'linked.js').symlink_to(assets / 'main.js')
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                self.prepare(assets)
            assets = self.build(Path(folder) / 'incomplete')
            (assets / 'main.js').unlink()
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                self.prepare(assets)

    def test_export_refuses_overwrite_and_returns_exact_explorer_policy(self):
        with tempfile.TemporaryDirectory() as folder:
            assets = self.build(Path(folder) / 'compiled')
            target = Path(folder) / 'export'
            with patch.object(studio.judge, 'prepare_review', return_value=dict(self.base)):
                result = studio.export_site(target, assets)
            self.assertTrue(result['studio_available'])
            self.assertTrue((target / '.nojekyll').is_file())
            self.assertIn(studio.COLOR_SENSOR_HASH, result['explorer_content_security_policy'])
            self.assertNotIn('unsafe-', result['explorer_content_security_policy'])
            self.assertNotIn('https:', result['explorer_content_security_policy'])
            for name, digest in result['sha256'].items():
                self.assertEqual(digest, hashlib.sha256((target / name).read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError, 'already exists'):
                studio.export_site(target, assets)

    def test_real_http_is_loopback_read_only_and_limits_csp_to_explorer_document(self):
        with tempfile.TemporaryDirectory() as folder:
            files = self.prepare(self.build(Path(folder) / 'compiled'))
            server = studio.make_server(files, port=0)
            self.assertEqual('127.0.0.1', server.server_address[0])
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()

            def request(path, method='GET'):
                connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                connection.request(method, path)
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result

            try:
                for path in ('/', '/demo.html', '/healthz', '/explorer/records.json', '/explorer/main.js'):
                    status, headers, _ = request(path)
                    self.assertEqual(200, status, path)
                    self.assertNotIn('nonce-', headers['Content-Security-Policy'])
                status, headers, _ = request('/explorer')
                self.assertEqual(308, status)
                self.assertEqual('/explorer/', headers['Location'])
                for path in ('/explorer/', '/explorer/index.html?view=recorded'):
                    status, headers, body = request(path)
                    self.assertEqual(200, status)
                    self.assertEqual(files['explorer/index.html'][1], body)
                    self.assertEqual(studio.explorer_policy(studio._nonce(files)), headers['Content-Security-Policy'])
                status, headers, body = request('/explorer/', 'HEAD')
                self.assertEqual(200, status)
                self.assertEqual(b'', body)
                self.assertEqual(len(files['explorer/index.html'][1]), int(headers['Content-Length']))
                for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                    self.assertEqual(405, request('/explorer/records.json', method)[0], method)
                for path in ('/.env', '/api/runs', '/explorer/../data.json', '/explorer/%2e%2e/data.json'):
                    self.assertEqual(404, request(path)[0], path)
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
