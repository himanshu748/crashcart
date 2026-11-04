"""Read-only judge entry: actual offline replay, exports and HTTP restrictions."""
import hashlib
import http.client
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
import zipfile

from crashcart.judge import INPUT, INPUT_SHA256, export_site, make_server, prepare_review
from crashcart.replay import ReplayError, verify_manifest


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
            self.assertEqual('PASS',data['cases']['healthy']['receipt']['verdict'])
            self.assertEqual('FAIL',data['cases']['defective']['receipt']['verdict'])
            self.assertEqual(set(self.files),set(receipt['sha256']))
            for name,digest in receipt['sha256'].items():
                self.assertEqual(digest,hashlib.sha256((target/name).read_bytes()).hexdigest())
            with self.assertRaisesRegex(ValueError,'already exists'):
                export_site(target)

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
