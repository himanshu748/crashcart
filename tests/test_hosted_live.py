"""Synthetic loopback/SQLite candidate checks, never live provider proof."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from crashcart import hosted_live as live
from crashcart.model_transport import MODAL_MODEL
from crashcart.monitor_ingress import IngressLimits
from crashcart.paypal import PayPalError

TOKEN = 'synthetic-hosted-operator-token-at-least32'

class HostedLiveTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name);self.db=self.root/'workspace.sqlite3'
        parent=self.root/'model-allowance';parent.mkdir(mode=0o700);self.ledger=parent/'allowance.json'
        self.ledger.write_text(json.dumps({'version':1,'call_limit':24,'ceiling_micro_usd':1000000,'calls':[]}));self.ledger.chmod(0o600)
        self.env={'CRASHCART_OPERATOR_TOKEN':TOKEN,'PAYPAL_CLIENT_ID':'synthetic-client','PAYPAL_CLIENT_SECRET':'synthetic-secret',
            'MODAL_API_KEY':'synthetic-model-key','MODAL_MODEL':MODAL_MODEL,'MODAL_BASE_URL':'https://synthetic.us-east.modal.direct',
            'MODAL_ALLOWED_ORIGIN':'https://synthetic.us-east.modal.direct','CRASHCART_MODEL_PROVIDER':'modal',
            'CRASHCART_MODEL_ALLOWANCE_PATH':str(self.ledger),'CRASHCART_PUBLIC_URL':live.PUBLIC_URL,'CRASHCART_ALLOW_SANDBOX':'1',
            'CRASHCART_ALLOW_MODEL':'1','CRASHCART_ALLOW_KERNEL':'0','CRASHCART_ALLOW_PROCESS_INTERRUPT':'0',
            'CRASHCART_EVALUATION_MODE':'ordinary','CRASHCART_LIVE_WINDOW_EXPIRES_AT':'2026-12-15T23:59:59Z'}
        clock=patch.object(live,'_now',return_value=datetime(2026,11,8,tzinfo=timezone.utc));clock.start();self.addCleanup(clock.stop)
        env=patch.dict(os.environ,{**self.env,'OPENAI_API_KEY':'','OPENAI_MODEL':'','KERNEL_API_KEY':'','AG_STUDIO_LICENSE_KEY':'','PAYPAL_WEBHOOK_ID':''})
        env.start();self.addCleanup(env.stop)
        original=socket.socket.connect
        def loopback(sock,address):
            if not isinstance(address,tuple) or address[0]!='127.0.0.1':raise AssertionError('External connections forbidden')
            return original(sock,address)
        network=patch.object(socket.socket,'connect',loopback);network.start();self.addCleanup(network.stop)
        self.server=None;self.thread=None;self.addCleanup(self.stop)
    def start(self,**kwargs):
        self.server=live.make_server(self.db,self.env,host='127.0.0.1',port=0,**kwargs)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def stop(self):
        if self.server:self.server.shutdown();self.server.server_close();self.server=None
        if self.thread:self.thread.join(3);self.thread=None
    def request(self,method='GET',path='/healthz',body=None,*,auth=False,cookie=None,origin=None):
        headers={}
        if auth:headers['Authorization']='Bearer '+TOKEN
        if cookie:headers['Cookie']=cookie
        if origin:headers['Origin']=origin
        raw=None
        if method not in {'GET','HEAD'}:raw=json.dumps({} if body is None else body).encode();headers['Content-Type']='application/json'
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=5)
        try:
            connection.request(method,path,body=raw,headers=headers);response=connection.getresponse()
            return response.status,response.read(),dict(response.getheaders())
        finally:connection.close()
    def create(self):
        status,raw,_=self.request('POST','/api/runs',{'promise':'USD 29 buys one ticket within 60 seconds','mode':'LIVE_SANDBOX','fault':{'kind':'none','merchant':'healthy'}},auth=True)
        self.assertEqual(status,201);return json.loads(raw)
    def test_auth_login_cookie_and_cross_origin(self):
        self.start();self.assertEqual(self.request(path='/')[0],200);self.assertEqual(self.request(path='/api/runs')[0],401)
        for method in ('POST','PUT','PATCH','DELETE'):
            for path in ('/api/runs','/api/webhooks/paypal','/api/studio/query','/unknown'):
                self.assertEqual(self.request(method,path)[0],401)
        self.assertEqual(self.request('POST','/api/login',{'token':'incorrect'})[0],401)
        status,body,headers=self.request('POST','/api/login',{'token':TOKEN},origin=live.PUBLIC_URL)
        self.assertEqual(status,200);self.assertTrue(json.loads(body)['authenticated'])
        for flag in ('Secure','HttpOnly','SameSite=Strict'):self.assertIn(flag,headers['Set-Cookie'])
        self.assertEqual(self.request(path='/api/runs',cookie=headers['Set-Cookie'].split(';')[0])[0],200)
        self.assertEqual(self.request('POST','/api/login',{'token':TOKEN},origin='https://foreign.invalid')[0],403)
    def test_scope_and_disabled_features_and_queue_without_inference(self):
        self.start();base={'promise':'USD 29 buys one ticket within 60 seconds','mode':'LIVE_SANDBOX'}
        for change in ({'mode':'LOCAL_TEST'},{'mode':'RECORDED_REPLAY'},{'fixture_id':'another-store'},{'fault':{'kind':'process_interrupt','merchant':'healthy'}}):
            self.assertEqual(self.request('POST','/api/runs',{**base,**change},auth=True)[0],403)
        run=self.create();self.assertEqual(run['invariant']['recovery_seconds'],60)
        for path in (f'/api/runs/{run["id"]}/investigate','/api/studio/query','/api/webhooks/paypal'):
            self.assertEqual(self.request('POST',path,auth=True)[0],403)
        with patch('crashcart.investigator.Investigation',side_effect=AssertionError('No inference on enqueue')):
            status,raw,_=self.request('POST',f'/api/runs/{run["id"]}/investigation-job',auth=True)
        self.assertEqual(status,202);self.assertEqual(json.loads(raw)['job']['state'],'PENDING')
        self.assertEqual(json.loads(self.ledger.read_text())['calls'],[])
    def test_case_cap_is_concurrent_and_durable(self):
        self.start()
        def create(_):return self.request('POST','/api/runs',{'promise':'USD 29 buys one ticket within 60 seconds'},auth=True)[0]
        with ThreadPoolExecutor(max_workers=4) as pool:outcomes=list(pool.map(create,range(12)))
        self.assertEqual(outcomes.count(201),8);self.assertEqual(outcomes.count(429),4)
        self.stop();self.start();self.assertEqual(create(None),429)
        status,raw,_=self.request(path='/api/runs',auth=True)
        self.assertEqual(status,200);self.assertEqual(len(json.loads(raw)['runs']),8)
    def test_failed_order_consumes_case_slot_without_refund(self):
        self.start();run=self.create()
        with patch('crashcart.paypal.PayPalSandbox.create_order',side_effect=PayPalError('TIMEOUT','Synthetic failure',ambiguous=True)) as provider:
            self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/order',auth=True)[0],503)
            self.assertEqual(provider.call_count,1)
        for _ in range(7):self.create()
        self.assertEqual(self.request('POST','/api/runs',{'promise':'One ticket'},auth=True)[0],429)
    def test_ungranted_records_rejected_on_actions_and_restart(self):
        self.start();run=self.server.store.create_run('Unapproved',mode='LOCAL_TEST')
        with patch('crashcart.paypal.PayPalSandbox.create_order',side_effect=AssertionError('No provider call')):
            for action in ('order','capture','reconcile','investigation-job'):
                self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/{action}',auth=True)[0],403)
        self.stop()
        self.start();self.assertEqual(self.request(path='/api/runs',auth=True)[1],b'{"runs": []}')
    def test_expiry_blocks_new_actions_and_allows_cancellation(self):
        self.start();run=self.create()
        with patch.object(live,'_now',return_value=datetime(2026,12,16,tzinfo=timezone.utc)):
            status,raw,_=self.request('POST','/api/runs',{'promise':'Another'},auth=True)
            self.assertEqual(status,503);payload=json.loads(raw)
            self.assertEqual(payload['code'],'LIVE_WINDOW_EXPIRED');self.assertNotIn('LIVE_',payload['error'])
            self.assertIn('Contact the workspace owner',payload['error'])
            self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/order',auth=True)[0],503)
            self.assertEqual(self.request()[0],503)
            self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/cancel',auth=True)[0],200)
            with self.assertRaisesRegex(live.HostedLiveError,'LIVE_WINDOW_EXPIRED'):live.Runtime(self.env)
    def test_provider_scope_and_missing_pins_fail_before_bind(self):
        changes=[{'CRASHCART_MODEL_PROVIDER':'openai'},{'MODAL_MODEL':'other'},
            {'MODAL_ALLOWED_ORIGIN':'https://different.modal.run'},{'CRASHCART_ALLOW_MODEL':'0'},
            {'CRASHCART_ALLOW_SANDBOX':'0'},{'CRASHCART_ALLOW_KERNEL':'1'},
            {'CRASHCART_ALLOW_PROCESS_INTERRUPT':'1'},{'CRASHCART_EVALUATION_MODE':'held-out'},
            {'KERNEL_API_KEY':'forbidden'},{'AG_STUDIO_LICENSE_KEY':'forbidden'},
            {'PAYPAL_WEBHOOK_ID':'forbidden'},{'OPENAI_API_KEY':'forbidden'},
            {'CRASHCART_PUBLIC_URL':'https://another.invalid'},
            {'CRASHCART_LIVE_WINDOW_EXPIRES_AT':'2027-01-01T00:00:00Z'},
            {'CRASHCART_LIVE_WINDOW_EXPIRES_AT':'2026-12-01'},
            {'CRASHCART_MODEL_ALLOWANCE_PATH':'relative.json'}]
        for change in changes:
            with self.subTest(change=list(change)),patch.object(live,'BoundedHTTPServer',side_effect=AssertionError('Must reject before binding')):
                with self.assertRaises(live.HostedLiveError):live.make_server(self.db,{**self.env,**change},host='127.0.0.1',port=0)
    def test_existing_allowance_is_required_and_unknown_blocks(self):
        self.ledger.unlink()
        with self.assertRaises(live.HostedLiveError):live.Runtime(self.env)
        self.assertFalse(self.ledger.exists())
        self.ledger.write_text('{broken');self.ledger.chmod(0o600)
        with self.assertRaises(live.HostedLiveError):live.Runtime(self.env)
        self.assertEqual(self.ledger.read_text(),'{broken')
        state={'version':1,'call_limit':24,'ceiling_micro_usd':1000000,'calls':[{'call':1,'state':'RESERVED','reserved_micro_usd':40000,'started_at':'2026-11-08T00:00:00Z','request_sha256':'a'*64,'request_bytes':100}]}
        self.ledger.write_text(json.dumps(state))
        with self.assertRaisesRegex(live.HostedLiveError,'LIVE_MODEL_ALLOWANCE_UNRESOLVED'):live.Runtime(self.env)
        self.assertEqual(json.loads(self.ledger.read_text()),state)
    def test_credentials_permissions_and_literal_parsing(self):
        path=self.root/'credentials';path.write_text('MODAL_API_KEY="$(never-execute)"\n');path.chmod(0o600)
        self.assertEqual(live.read_credentials(path),{'MODAL_API_KEY':'$(never-execute)'})
        path.chmod(0o644)
        with self.assertRaisesRegex(live.HostedLiveError,'PERMISSIONS'):live.read_credentials(path)
        path.chmod(0o600);path.write_text('MODAL_API_KEY=one\nMODAL_API_KEY=two')
        with self.assertRaisesRegex(live.HostedLiveError,'INVALID'):live.read_credentials(path)
        path.write_text('AWS_SECRET_ACCESS_KEY=forbidden')
        with self.assertRaisesRegex(live.HostedLiveError,'INVALID'):live.read_credentials(path)
        link=self.root/'link';link.symlink_to(path)
        with self.assertRaises(live.HostedLiveError):live.read_credentials(link)
    def test_ingress_overload_slow_body_and_recovery(self):
        self.start(limits=IngressLimits(max_handlers=1,request_timeout=.2))
        slow=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=3);self.addCleanup(slow.close)
        slow.sendall(('POST /api/login HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n{').encode())
        until=time.monotonic()+1
        while not self.server.active_handlers and time.monotonic()<until:time.sleep(.005)
        self.assertEqual(self.server.active_handlers,1)
        self.assertEqual(self.request()[0],503)
        until=time.monotonic()+2
        while self.server.active_handlers and time.monotonic()<until:time.sleep(.01)
        self.assertEqual(self.server.active_handlers,0);self.assertEqual(self.request()[0],200)
        self.assertEqual(self.server.peak_handlers,1)
    def test_analysis_and_recovery_claim_independently(self):
        self.start();run=self.create();store=self.server.store
        store.enqueue(run['id'],'investigate',{},semantic_key='investigation-v1')
        store.enqueue(run['id'],'reconcile',{'attempt':0},semantic_key='recovery-0')
        analysis=live._claim_role(store,'analysis','investigate')
        recovery=live._claim_role(store,'recovery','reconcile')
        self.assertEqual(analysis['kind'],'investigate');self.assertEqual(recovery['kind'],'reconcile')
        self.assertEqual(analysis['attempts'],1);self.assertEqual(recovery['attempts'],1)
        self.assertNotEqual(analysis['id'],recovery['id'])
    def test_reclaimed_analysis_never_reissues_inference(self):
        self.start();run=self.create();store=self.server.store
        store.enqueue(run['id'],'investigate',{},semantic_key='investigation-v1')
        first=live._claim_role(store,'first','investigate')
        with store.connect(write=True) as db:db.execute('UPDATE jobs SET lease_until=? WHERE id=?',(time.time()-1,first['id']))
        with patch('crashcart.investigator.Investigation',side_effect=AssertionError('No ambiguous retry')):
            self.assertTrue(live.worker_cycle(store,self.server.runtime,'next','investigate'))
        from crashcart.worker import investigation_job
        job=investigation_job(store,run['id'])
        self.assertEqual(job['state'],'FAILED');self.assertEqual(job['result']['status'],'INTERRUPTED')
        self.assertEqual(json.loads(self.ledger.read_text())['calls'],[])
    def test_duplicate_json_is_rejected_without_slot(self):
        self.start();connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        try:
            connection.request('POST','/api/runs',body=b'{"promise":"one","promise":"two"}',headers={'Authorization':'Bearer '+TOKEN,'Content-Type':'application/json'})
            response=connection.getresponse();self.assertEqual(response.status,400);response.read()
        finally:connection.close()
        with self.server.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM hosted_live_case_grants').fetchone()[0],0)
    def test_default_ingress_stays_sixteen_handlers_ten_seconds(self):
        self.start();self.assertEqual(self.server.ingress_limits.max_handlers,16);self.assertEqual(self.server.ingress_limits.request_timeout,10)

    def test_crash_between_creation_and_binding_quarantines_only_partial_record(self):
        self.start();earlier=self.create();store=self.server.store
        original=store.create_run
        partial=[]
        def crash_after_commit(*args,**kwargs):
            partial.append(original(*args,**kwargs))
            raise RuntimeError('Synthetic crash after create commit before grant binding')
        with patch.object(store,'create_run',side_effect=crash_after_commit):
            self.assertEqual(self.request('POST','/api/runs',{'promise':'One ticket'},auth=True)[0],500)
        orphan=partial[0]
        store.enqueue(orphan['id'],'reconcile',{},semantic_key='orphan-never-dispatched')
        self.stop();self.start();store=self.server.store
        self.assertEqual(self.request(path=f'/api/runs/{earlier["id"]}',auth=True)[0],200)
        status,raw,_=self.request(path='/api/runs',auth=True)
        self.assertEqual(status,200);self.assertEqual([row['id'] for row in json.loads(raw)['runs']],[earlier['id']])
        for path in (f'/api/runs/{orphan["id"]}',f'/api/runs/{orphan["id"]}/export',f'/api/merchant/{orphan["purchase_id"]}'):
            self.assertEqual(self.request(path=path,auth=True)[0],403)
        with patch('crashcart.paypal.PayPalSandbox.create_order',side_effect=AssertionError('Quarantined record must never dispatch')):
            self.assertEqual(self.request('POST',f'/api/runs/{orphan["id"]}/order',auth=True)[0],403)
            self.assertFalse(live.worker_cycle(store,self.server.runtime,'recovery','reconcile'))
        for _ in range(6):self.create()
        self.assertEqual(self.request('POST','/api/runs',{'promise':'No ninth case'},auth=True)[0],429)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM hosted_live_case_grants').fetchone()[0],8)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM hosted_live_case_grants WHERE run_id IS NULL').fetchone()[0],1)
        self.assertIsNotNone(store.get_run(orphan['id']))
    def test_delayed_order_survives_ingress_disconnect_with_one_journal(self):
        self.start(limits=IngressLimits(request_timeout=.2));run=self.create();store=self.server.store
        entered=threading.Event();release=threading.Event()
        self.addCleanup(release.set)
        response={'id':'ORDER-DELAYED','status':'CREATED','links':[{'rel':'approve','href':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-DELAYED'}]}
        def delayed(*args):
            entered.set()
            if not release.wait(3):raise AssertionError('Test failed to release synthetic response')
            return response
        with patch('crashcart.paypal.PayPalSandbox.create_order',side_effect=delayed) as creates,patch('crashcart.paypal.PayPalSandbox.get_order',return_value=response):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.request,'POST',f'/api/runs/{run["id"]}/order',auth=True)
                self.assertTrue(entered.wait(1))
                with self.assertRaises((http.client.RemoteDisconnected,ConnectionResetError)):future.result(timeout=2)
                release.set()
            until=time.monotonic()+2
            while self.server.active_handlers and time.monotonic()<until:time.sleep(.01)
            self.assertEqual(self.server.active_handlers,0)
            self.assertEqual(store.purchase_for_run(run['id'])['order_id'],'ORDER-DELAYED')
            operations=store.get_operations(run['purchase_id'])
            self.assertEqual(len(operations),1);self.assertEqual(operations[0]['state'],'COMPLETED')
            original_request_id=operations[0]['request_id']
            self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/order',auth=True)[0],200)
            self.assertEqual(creates.call_count,1)
            self.assertEqual(store.get_operations(run['purchase_id'])[0]['request_id'],original_request_id)
            events=store.get_events(run['id'])
            self.assertEqual(sum(event['event_type']=='order_created' for event in events),1)
    def test_delayed_capture_survives_disconnect_without_second_payment(self):
        from tests.test_service import FakePayPal
        self.start(limits=IngressLimits(request_timeout=.2));run=self.create();store=self.server.store
        fake=FakePayPal();entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def delayed(*args):
            entered.set()
            if not release.wait(3):raise AssertionError('Test failed to release synthetic capture')
            return fake.capture_order(*args)
        with patch('crashcart.paypal.PayPalSandbox.create_order',side_effect=fake.create_order),patch('crashcart.paypal.PayPalSandbox.get_order',side_effect=fake.get_order),patch('crashcart.paypal.PayPalSandbox.capture_order',side_effect=delayed):
            self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/order',auth=True)[0],200)
            fake.order['status']='APPROVED'
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(self.request,'POST',f'/api/runs/{run["id"]}/capture',{'order_id':'ORDER_TEST'},auth=True)
                self.assertTrue(entered.wait(1))
                with self.assertRaises((http.client.RemoteDisconnected,ConnectionResetError)):future.result(timeout=2)
                release.set()
            until=time.monotonic()+2
            while self.server.active_handlers and time.monotonic()<until:time.sleep(.01)
            self.assertEqual(self.server.active_handlers,0)
            capture=[operation for operation in store.get_operations(run['purchase_id']) if operation['semantic_key']=='order.capture']
            self.assertEqual(len(capture),1);self.assertEqual(capture[0]['state'],'COMPLETED')
            original_id=capture[0]['request_id']
            self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/capture',{'order_id':'ORDER_TEST'},auth=True)[0],200)
            self.assertEqual(sum(call[0]=='capture' for call in fake.calls),1)
            self.assertEqual([operation['request_id'] for operation in store.get_operations(run['purchase_id']) if operation['semantic_key']=='order.capture'],[original_id])
            self.assertEqual(store.merchant_state(run['purchase_id'])['ticket_count'],1)
            self.assertEqual(sum(event['event_type']=='capture_transport_response' for event in store.get_events(run['id'])),1)
    def test_maximum_window_includes_twenty_second_december(self):
        exact={**self.env,'CRASHCART_LIVE_WINDOW_EXPIRES_AT':'2026-12-23T00:00:00Z'}
        self.assertEqual(live.Runtime(exact).expires,datetime(2026,12,23,tzinfo=timezone.utc))
        with self.assertRaisesRegex(live.HostedLiveError,'LIVE_WINDOW_INVALID'):
            live.Runtime({**exact,'CRASHCART_LIVE_WINDOW_EXPIRES_AT':'2026-12-23T00:00:00.001Z'})
    def test_optional_views_explain_scope_without_fake_sdk(self):
        self.start()
        for path in ('/studio/index.html','/deadlines/index.html','/monitor/index.html'):
            status,raw,headers=self.request(path=path)
            self.assertEqual(status,200);self.assertIn('text/html',headers['Content-Type'])
            self.assertIn(b'optional report builder',raw);self.assertIn(b"href='/'",raw)
    def test_cancelled_pending_analysis_cannot_be_claimed(self):
        self.start();run=self.create();store=self.server.store
        self.request('POST',f'/api/runs/{run["id"]}/investigation-job',auth=True)
        self.assertEqual(self.request('POST',f'/api/runs/{run["id"]}/cancel',auth=True)[0],200)
        with patch('crashcart.investigator.Investigation',side_effect=AssertionError('No inference after cancellation')):
            self.assertFalse(live.worker_cycle(store,self.server.runtime,'analysis','investigate'))
        from crashcart.worker import investigation_job
        self.assertEqual(investigation_job(store,run['id'])['state'],'CANCELLED')
    def test_failed_case_creation_consumes_permanent_slot(self):
        self.start()
        with patch.object(self.server.store,'create_run',side_effect=ValueError('Synthetic setup failure')):
            self.assertEqual(self.request('POST','/api/runs',{'promise':'One ticket'},auth=True)[0],400)
        for _ in range(7):self.create()
        self.assertEqual(self.request('POST','/api/runs',{'promise':'Another'},auth=True)[0],429)
        self.stop();self.start()
        self.assertEqual(self.request('POST','/api/runs',{'promise':'Another'},auth=True)[0],429)

class CaddyInPlaceTests(unittest.TestCase):
    def setUp(self):
        import importlib.util
        module_path=Path(__file__).resolve().parents[1]/'deploy/live/install_caddy.py'
        spec=importlib.util.spec_from_file_location('candidate_caddy_installer',module_path)
        self.installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.installer)
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup);self.root=Path(folder.name)
        self.target=self.root/'Caddyfile';self.original=b'old.example.invalid {\n respond "Existing service"\n}\n'
        self.target.write_bytes(self.original)
        self.combined=self.root/'pending';self.candidate=self.original+b'\n'+module_path.with_name('Caddyfile.fragment').read_bytes()
        self.combined.write_bytes(self.candidate);self.backup=self.root/'backup'
    def install(self):
        return self.installer.install_validated(self.target,self.combined,self.installer.digest(self.original),self.installer.digest(self.candidate),self.backup)
    def test_install_keeps_file_bind_mount_inode_and_every_existing_byte(self):
        alias=self.root/'simulated-file-bind';os.link(self.target,alias);inode=self.target.stat().st_ino
        self.assertEqual(self.install(),self.installer.digest(self.candidate))
        self.assertEqual(self.target.stat().st_ino,inode);self.assertEqual(alias.read_bytes(),self.candidate)
        self.assertTrue(self.target.read_bytes().startswith(self.original))
        self.assertEqual(self.backup.read_bytes(),self.original);self.assertEqual(self.backup.stat().st_mode&0o777,0o600)
    def test_changed_current_or_validated_candidate_is_rejected_before_write(self):
        self.target.write_bytes(self.original+b'# concurrent change')
        with self.assertRaisesRegex(ValueError,'Current configuration changed'):self.install()
        self.assertEqual(self.target.read_bytes(),self.original+b'# concurrent change');self.assertFalse(self.backup.exists())
        self.target.write_bytes(self.original);self.combined.write_bytes(self.candidate+b'# different candidate')
        with self.assertRaisesRegex(ValueError,'Validated candidate changed'):self.install()
        self.assertEqual(self.target.read_bytes(),self.original);self.assertFalse(self.backup.exists())
    def test_modified_previous_route_and_reused_backup_are_rejected(self):
        self.candidate=self.candidate.replace(b'Existing service',b'Wrong service');self.combined.write_bytes(self.candidate)
        with self.assertRaisesRegex(ValueError,'Only the reviewed'):self.install()
        self.assertEqual(self.target.read_bytes(),self.original)
        self.candidate=self.original+b'\n'+Path(self.installer.__file__).with_name('Caddyfile.fragment').read_bytes();self.combined.write_bytes(self.candidate)
        self.backup.write_bytes(b'previous backup')
        with self.assertRaises(FileExistsError):self.install()
        self.assertEqual(self.target.read_bytes(),self.original);self.assertEqual(self.backup.read_bytes(),b'previous backup')
    def test_path_renamed_during_write_restores_open_inode_without_touching_substitute(self):
        original_inode=self.target.stat().st_ino
        displaced=self.root/'displaced-Caddyfile';substitute=b'Unrelated substituted configuration'
        real=self.installer._replace_in_place;calls=[]
        def rename_after_first_write(handle,data):
            calls.append(data);real(handle,data)
            if len(calls)==1:
                self.target.rename(displaced)
                self.target.write_bytes(substitute)
        with patch.object(self.installer,'_replace_in_place',side_effect=rename_after_first_write):
            with self.assertRaisesRegex(ValueError,'path identity changed'):self.install()
        self.assertEqual(len(calls),2)
        self.assertEqual(displaced.stat().st_ino,original_inode)
        self.assertEqual(displaced.read_bytes(),self.original)
        self.assertNotEqual(self.target.stat().st_ino,original_inode)
        self.assertEqual(self.target.read_bytes(),substitute)
        self.assertEqual(self.backup.read_bytes(),self.original)
    def test_local_write_failure_restores_same_inode_and_keeps_backup(self):
        inode=self.target.stat().st_ino;real=self.installer._replace_in_place;calls=[]
        def fail_once(handle,data):
            calls.append(data)
            if len(calls)==1:
                handle.seek(0);handle.write(b'partial');handle.flush()
                raise OSError('Synthetic write failure')
            return real(handle,data)
        with patch.object(self.installer,'_replace_in_place',side_effect=fail_once):
            with self.assertRaisesRegex(OSError,'Synthetic write failure'):self.install()
        self.assertEqual(len(calls),2);self.assertEqual(self.target.stat().st_ino,inode)
        self.assertEqual(self.target.read_bytes(),self.original);self.assertEqual(self.backup.read_bytes(),self.original)

if __name__=='__main__':unittest.main()
