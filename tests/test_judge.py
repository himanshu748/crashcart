"""Read-only judge entry: actual offline replay, exports and HTTP restrictions."""
import hashlib
from html.parser import HTMLParser
import http.client
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urljoin, urlsplit
import zipfile

from crashcart.judge import (AI_HISTORY, AI_HISTORY_SHA256, INPUT, INPUT_SHA256,
                            PAGE_ALIASES, export_site, historical_ai, make_server, prepare_review)
from crashcart.replay import ReplayError, verify_manifest


class _PublicPage(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids, self.duplicates, self.links, self.current = set(), [], [], set()
        self.h1_count, self.in_title, self.title = 0, False, ''
        self.inline = []
        self.refresh = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == 'meta' and attrs.get('http-equiv', '').lower() == 'refresh':
            self.refresh.append(attrs.get('content'))
        if attrs.get('id'):
            if attrs['id'] in self.ids:
                self.duplicates.append(attrs['id'])
            self.ids.add(attrs['id'])
        self.h1_count += tag == 'h1'
        if tag == 'title':
            self.in_title = True
        if tag == 'a' and attrs.get('aria-current') == 'page':
            self.current.add(attrs.get('href'))
        for attribute in ('href', 'src'):
            if attribute in attrs:
                self.links.append((tag, attrs[attribute]))
        if tag == 'style' or tag == 'script' and not attrs.get('src'):
            self.inline.append(tag)
        self.inline.extend(name for name in attrs if name == 'style' or name.startswith('on'))

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


class JudgeReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original_open = io.open
        def no_private_env(path, *args, **kwargs):
            if isinstance(path, (str, bytes, os.PathLike)) and Path(path).name == '.env':
                raise AssertionError('Judge mode must not read .env')
            return original_open(path, *args, **kwargs)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('No outgoing request allowed')), \
                patch('socket.create_connection', side_effect=AssertionError('No outgoing request allowed')), \
                patch('io.open', side_effect=no_private_env), \
                patch.dict(os.environ, {'PAYPAL_CLIENT_SECRET':'DO_NOT_EXPOSE_PROVIDER_SECRET',
                                        'KERNEL_API_KEY':'DO_NOT_EXPOSE_BROWSER_SECRET',
                                        'OPENAI_API_KEY':'DO_NOT_EXPOSE_MODEL_SECRET'}):
            cls.files = prepare_review()
        cls.data = json.loads(cls.files['data.json'][1])

    def test_same_input_runs_both_real_variants_under_network_denial(self):
        data = self.data
        self.assertEqual('RECORDED_REPLAY', data['mode'])
        self.assertFalse(data['fresh_execution'])
        self.assertEqual('app launch', data['computed_when'])
        cases = data['cases']
        for variant, verdict, signature, count in (
                ('defective','FAIL','paid_without_ticket',0),
                ('healthy','PASS','ticket_delivered_once_on_time',1)):
            item = cases[variant]
            self.assertEqual((verdict, signature, count), (item['receipt']['verdict'],item['receipt']['signature'],len(item['merchant']['tickets'])))
            self.assertTrue(item['purchase']['payment_confirmed'])
            self.assertEqual(60, item['execution']['invariant']['recovery_seconds'])
            self.assertEqual(0,item['receipt']['network_calls'])
            self.assertFalse(item['receipt']['fresh_execution'])
        self.assertEqual(cases['defective']['receipt']['input_sha256'],cases['healthy']['receipt']['input_sha256'])
        self.assertEqual(cases['defective']['execution']['deadline'],cases['healthy']['execution']['deadline'])
        self.assertNotEqual(cases['defective']['receipt']['run_id'],cases['healthy']['receipt']['run_id'])
        self.assertNotEqual(cases['defective']['receipt']['purchase_id'],cases['healthy']['receipt']['purchase_id'])
        self.assertEqual(INPUT_SHA256,hashlib.sha256(self.files['downloads/input.json'][1]).hexdigest())
        self.assertEqual(INPUT.read_bytes(),self.files['downloads/input.json'][1])

    def test_downloads_match_rendered_data_without_credentials(self):
        for variant in ('defective','healthy'):
            self.assertEqual(self.data['cases'][variant],json.loads(self.files[f'downloads/{variant}.json'][1]))
        for _, content in self.files.values():
            self.assertNotIn(b'DO_NOT_EXPOSE_',content)
        self.assertEqual(15,len(self.data['original_records']))

    def test_historical_ai_is_an_explicit_separate_recorded_case(self):
        summary = json.loads(AI_HISTORY.read_bytes())
        ai = self.data['historical_ai']
        self.assertEqual('RECORDED_AI_INVESTIGATION', ai['mode'])
        self.assertFalse(ai['fresh_execution'])
        self.assertFalse(ai['same_case_as_public_faulty_replay'])
        self.assertEqual(AI_HISTORY_SHA256, hashlib.sha256(AI_HISTORY.read_bytes()).hexdigest())
        self.assertEqual(AI_HISTORY_SHA256, ai['source_summary_sha256'])
        for key in ('provider', 'model', 'investigation_started_at', 'investigation_finished_at',
                    'historical_capture_date', 'actual_operations', 'deterministic_result'):
            self.assertEqual(summary[key], ai[key], key)
        self.assertEqual(['read_provider', 'read_merchant', 'finish'], [step['action'] for step in ai['trace']])
        self.assertEqual([0, 1, 2], [len(step['evidence_categories_before_response']) for step in ai['trace']])
        self.assertEqual(3, ai['actual_operations']['model_calls'])
        self.assertEqual(1, ai['actual_operations']['paypal_existing_order_gets'])
        self.assertEqual(0, ai['actual_operations']['new_payments'])
        self.assertIn('different historical case', ai['limits'][0])
        self.assertIn('private provider receipts', ai['limits'][-1])
        for original, projected in zip(summary['trace'], ai['trace']):
            expected = {key: value for key, value in original.items() if key != 'wire_response_sha256'}
            self.assertEqual(expected, projected)

    def test_historical_ai_projection_has_no_private_bindings_or_unknown_fields(self):
        ai = self.data['historical_ai']
        self.assertEqual({'mode', 'fresh_execution', 'same_case_as_public_faulty_replay', 'provider',
                          'model', 'investigation_started_at', 'investigation_finished_at',
                          'historical_capture_date', 'actual_operations', 'trace',
                          'deterministic_result', 'source_summary_sha256', 'limits'}, set(ai))
        encoded = json.dumps(ai)
        for binding in json.loads(AI_HISTORY.read_bytes())['private_source_bindings']:
            self.assertNotIn(binding['path'], encoded)
            self.assertNotIn(binding['sha256'], encoded)
        for forbidden in ('private_source_bindings', 'wire_response_sha256', 'endpoint',
                          'capture_id', 'order_id', 'purchase_id', 'response_id', 'historical_verification'):
            self.assertNotIn('"' + forbidden + '"', encoded)

    def test_changed_historical_ai_source_prevents_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            changed = Path(folder) / 'ai.json'
            changed.write_bytes(AI_HISTORY.read_bytes() + b' ')
            with self.assertRaisesRegex(ReplayError, 'historical AI summary changed'):
                historical_ai(changed)
            with patch('crashcart.judge.AI_HISTORY', changed), \
                    patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')):
                with self.assertRaisesRegex(ReplayError, 'historical AI summary changed'):
                    prepare_review()

    def test_historical_ai_scope_and_sequence_are_validated_independently_of_hash(self):
        original = json.loads(AI_HISTORY.read_bytes())
        mutations = [
            lambda value: value.update(new_verification_claim=True),
            lambda value: value.update(public_judge_mode_calls_model=True),
            lambda value: value.update(same_case_as_public_faulty_replay=True),
            lambda value: value['actual_operations'].update(new_payments=1),
            lambda value: value['actual_operations'].update(paypal_existing_order_gets=True),
            lambda value: value['trace'].reverse(),
            lambda value: value['trace'][0].update(step=True),
            lambda value: value['trace'][0].update(evidence_categories_before_response=['future evidence']),
            lambda value: value['trace'][1].pop('exact_model_excerpt'),
            lambda value: value.update(investigation_started_at='2026-10-26T14:16:46'),
            lambda value: value.update(investigation_finished_at='2026-10-25T14:17:01Z'),
        ]
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'ai.json'
            for mutate in mutations:
                value = json.loads(json.dumps(original))
                mutate(value)
                raw = json.dumps(value).encode()
                source.write_bytes(raw)
                # Bind this synthetic byte sequence solely to exercise semantic
                # validation; it is not relabelled as historical evidence.
                with self.subTest(mutation=mutate), patch('crashcart.judge.AI_HISTORY_SHA256', hashlib.sha256(raw).hexdigest()):
                    with self.assertRaisesRegex(ReplayError, 'unsupported scope or shape'):
                        historical_ai(source)

    def test_downloaded_zip_is_executable_with_expected_pair(self):
        with tempfile.TemporaryDirectory() as folder:
            with zipfile.ZipFile(io.BytesIO(self.files['downloads/replay.zip'][1])) as archive:
                archive.extractall(folder)
            self.assertEqual('PASS',verify_manifest(folder)['result'])
            for variant, expected, signature in [('defective',1,'paid_without_ticket'),('healthy',0,'ticket_delivered_once_on_time')]:
                completed = subprocess.run([sys.executable,'-m','crashcart.replay','run','input.json','--merchant',variant],
                    cwd=folder,env={'PATH':os.environ.get('PATH','')},capture_output=True,text=True,timeout=30)
                self.assertEqual(expected,completed.returncode,completed.stderr)
                self.assertEqual(signature,json.loads(completed.stdout)['signature'])

    def test_exact_mit_notice_survives_static_and_zip_distribution(self):
        root=Path(__file__).resolve().parents[1]
        licence=(root/'LICENSE').read_bytes()
        self.assertEqual(licence,self.files['LICENSE'][1])
        self.assertIn(b'href="LICENSE"',self.files['index.html'][1])
        with zipfile.ZipFile(io.BytesIO(self.files['downloads/replay.zip'][1])) as archive:
            readme=archive.read('README.md')
            self.assertTrue(readme.endswith(licence))
            self.assertEqual(1,readme.count(licence))
            manifest=json.loads(archive.read('manifest.json'))
            self.assertEqual(hashlib.sha256(readme).hexdigest(),manifest['files']['README.md'])
            for name in ('crashcart/replay.py','crashcart/store.py','crashcart/invariant.py','migrations/001_initial.sql'):
                self.assertEqual((root/name).read_bytes(),archive.read(name))

    def test_separate_pages_have_real_subpath_safe_navigation_and_resources(self):
        pages = ('index.html', 'product.html', 'integrations.html', 'demo.html')
        parsed = {}
        for name in pages:
            page = _PublicPage()
            page.feed(self.files[name][1].decode('utf-8'))
            parsed[name] = page
            self.assertEqual(page.h1_count, 1, name)
            self.assertEqual(page.duplicates, [], name)
            self.assertEqual(page.inline, [], name)
            self.assertEqual(page.current, {name}, name)
        self.assertEqual(len({page.title.strip() for page in parsed.values()}), len(pages))
        prefix = '/crashcart/'
        for name, page in parsed.items():
            linked_pages = set()
            for tag, target in page.links:
                self.assertTrue(target, (name, tag))
                url = urlsplit(urljoin('https://example.test' + prefix + name, target))
                if url.netloc != 'example.test':
                    self.assertEqual(tag, 'a', (name, target))
                    self.assertIn(url.scheme, ('http', 'https'), (name, target))
                    continue
                self.assertTrue(url.path.startswith(prefix), (name, target))
                member = url.path.removeprefix(prefix) or 'index.html'
                self.assertIn(member, self.files, (name, target))
                if member in pages:
                    linked_pages.add(member)
                    if url.fragment:
                        self.assertIn(url.fragment, parsed[member].ids, (name, target))
            self.assertEqual(linked_pages, set(pages), name)
            scripts = [target for tag, target in page.links if tag == 'script']
            self.assertEqual(scripts, ['app.js'] if name == 'demo.html' else ['site.js'], name)

    def test_changed_example_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            changed=Path(folder)/'input.json'
            changed.write_bytes(INPUT.read_bytes()+b' ')
            with self.assertRaisesRegex(ReplayError,'historical input changed'):
                prepare_review(changed)

    def test_static_export_executes_and_labels_build_time(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'site'
            with patch.object(socket.socket,'connect',side_effect=AssertionError('Network forbidden')):
                receipt=export_site(target)
            data=json.loads((target/'data.json').read_text())
            self.assertEqual('site build',data['computed_when'])
            self.assertEqual(self.data['historical_ai'], data['historical_ai'])
            self.assertEqual('PASS',data['cases']['healthy']['receipt']['verdict'])
            self.assertEqual('FAIL',data['cases']['defective']['receipt']['verdict'])
            self.assertEqual(set(self.files),set(receipt['sha256']))
            for name,digest in receipt['sha256'].items():
                self.assertEqual(digest,hashlib.sha256((target/name).read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,'already exists'):
                export_site(target)

    def test_static_health_and_alias_targets_work_at_root_and_project_subpath(self):
        class StaticHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass

        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'crashcart'
            with patch.object(socket.socket, 'connect', side_effect=AssertionError('Export must stay offline')):
                export_site(target)
            for prefix, directory in (('/', target), ('/crashcart/', target.parent)):
                with self.subTest(prefix=prefix):
                    def handler(*args, **kwargs):
                        return StaticHandler(*args, directory=str(directory), **kwargs)
                    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
                    thread = threading.Thread(target=server.serve_forever, daemon=True)
                    thread.start()
                    try:
                        def request(path):
                            client = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                            try:
                                client.request('GET', path)
                                response = client.getresponse()
                                return response.status, dict(response.getheaders()), response.read()
                            finally:
                                client.close()
                        status, _, raw = request(prefix + 'healthz')
                        self.assertEqual(status, 200)
                        self.assertEqual(json.loads(raw), {
                            'status': 'recorded-demo', 'service': 'crashcart',
                            'scope': 'static-asset-serving', 'live_services_checked': False,
                        })
                        for alias, canonical in PAGE_ALIASES.items():
                            status, headers, _ = request(prefix + alias)
                            self.assertEqual(status, 301)
                            self.assertEqual(headers['Location'], prefix + alias + '/')
                            status, _, body = request(prefix + alias + '/')
                            self.assertEqual(status, 200)
                            self.assertEqual(body, self.files[alias + '/index.html'][1])
                            page = _PublicPage()
                            page.feed(body.decode())
                            self.assertEqual(page.inline, [])
                            self.assertEqual(page.refresh, ['0; url=../' + canonical])
                            self.assertEqual(page.links, [('link', '../' + canonical), ('a', '../' + canonical)])
                            resolved = urlsplit(urljoin('http://127.0.0.1' + prefix + alias + '/', '../' + canonical))
                            self.assertEqual(resolved.path, prefix + canonical)
                            status, _, document = request(resolved.path)
                            self.assertEqual(status, 200)
                            self.assertEqual(document, self.files[canonical][1])
                            # The canonical example loads its original relative data URL.
                            status, _, data = request(urlsplit(urljoin(resolved.geturl(), 'data.json')).path)
                            self.assertEqual(status, 200)
                            self.assertEqual(json.loads(data)['mode'], 'RECORDED_REPLAY')
                    finally:
                        server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_http_only_serves_frozen_allowlist_and_rejects_live_actions(self):
        server=make_server(self.files,port=0)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def request(method,path):
                connection=http.client.HTTPConnection('127.0.0.1',server.server_address[1],timeout=5)
                connection.request(method,path)
                response=connection.getresponse();result=(response.status,dict(response.getheaders()),response.read())
                connection.close();return result
            for name in self.files:
                status,headers,body=request('GET','/'+name)
                self.assertEqual(200,status,name)
                self.assertEqual(self.files[name][1],body,name)
                self.assertEqual('nosniff',headers['X-Content-Type-Options'])
                if name.startswith('downloads/'):
                    self.assertIn('attachment',headers['Content-Disposition'])
            self.assertEqual(self.files['index.html'][1],request('GET','/')[2])
            for alias, canonical in PAGE_ALIASES.items():
                status, headers, body = request('GET', '/' + alias)
                self.assertEqual(status, 200)
                self.assertNotIn('Location', headers)
                self.assertEqual(body, self.files[canonical][1])
                self.assertNotIn(b'http-equiv="refresh"', body)
                self.assertIn("base-uri 'none'", headers['Content-Security-Policy'])
                status, headers, _ = request('GET', '/' + alias + '/')
                self.assertEqual(status, 308)
                self.assertEqual(headers['Location'], '/' + alias)
            self.assertIn("base-uri 'none'", request('GET', '/product.html')[1]['Content-Security-Policy'])
            status, headers, body = request('GET', '/healthz')
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'application/json')
            self.assertEqual(json.loads(body)['status'], 'recorded-demo')
            for path in ('/.env','/../.env','/%2e%2e/.env','/api/runs','/shop','/api/health','/downloads/unknown.json'):
                self.assertEqual(404,request('GET',path)[0],path)
            for method in ('POST','PUT','PATCH','DELETE'):
                self.assertEqual(405,request(method,'/api/runs')[0],method)
            self.assertEqual(self.files['data.json'][1],request('GET','/data.json')[2])
            status,headers,body=request('HEAD','/data.json')
            self.assertEqual((200,b''),(status,body))
            self.assertEqual(str(len(self.files['data.json'][1])),headers['Content-Length'])
        finally:
            server.shutdown();server.server_close();thread.join(timeout=5)

    def test_shell_command_exports_without_keys_or_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'from-command'
            root=Path(__file__).resolve().parents[1]
            result=subprocess.run(['sh',str(root/'scripts/judge.sh'),'--export-site',str(target)],cwd=folder,
                env={'PATH':os.environ.get('PATH',''),'PYTHON':sys.executable},capture_output=True,text=True,timeout=30)
            self.assertEqual(0,result.returncode,result.stderr)
            self.assertEqual('RECORDED_REPLAY',json.loads(result.stdout)['mode'])
            self.assertEqual('site build',json.loads((target/'data.json').read_text())['computed_when'])
            self.assertFalse((Path(folder)/'.env').exists())


if __name__=='__main__':unittest.main()
