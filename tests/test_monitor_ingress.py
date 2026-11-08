"""Bounded local ingress probes; no external services or provider calls."""
import base64
from contextlib import closing
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from crashcart.monitor_ingress import IngressLimits, WebhookLimiter
from crashcart.monitor_server import make_server, _prefix
from crashcart.monitor_store import MonitorStore, ReceiptCapacityError
TOKEN='local-ingress-test-token-32characters'

class LimiterTests(unittest.TestCase):
    def test_limits_fail_closed(self):
        for args in [{'max_handlers':0},{'max_handlers':True},{'global_burst':-1},{'store_per_second':float('nan')},{'request_timeout':11},{'global_per_second':0},{'max_store_buckets':5000}]:
            with self.subTest(args=args),self.assertRaises(ValueError):IngressLimits(**args)
        with self.assertRaises(ValueError):WebhookLimiter(clock=lambda:float('nan'))
    def test_global_refill_and_constant_state(self):
        now=[0.0];lim=WebhookLimiter(IngressLimits(global_burst=2,global_per_second=1),clock=lambda:now[0])
        self.assertEqual([lim.global_admit() for _ in range(3)],[0,0,1]);now[0]=1
        self.assertEqual(lim.global_admit(),0);self.assertEqual(lim.stores,{})
    def test_store_isolation_bounded_state_and_idle_recovery(self):
        now=[0.0];lim=WebhookLimiter(IngressLimits(store_burst=1,store_per_second=1,max_store_buckets=2,idle_seconds=2),clock=lambda:now[0])
        self.assertEqual(lim.store_admit('registered-a'),0);self.assertEqual(lim.store_admit('registered-a'),1)
        self.assertEqual(lim.store_admit('registered-b'),0);self.assertEqual(lim.store_admit('registered-c'),1)
        self.assertEqual(len(lim.stores),2);now[0]=2
        self.assertEqual(lim.store_admit('registered-c'),0);self.assertEqual(len(lim.stores),1)

class IngressHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'monitor.sqlite3';db=MonitorStore(self.path)
        self.a=db.create_store('Store A','woocommerce','https://a.example.test',60)
        self.b=db.create_store('Store B','woocommerce','https://b.example.test',60)
        self.now=[0.0];self.calls=[];self.factories=[];self.server=None;self.thread=None
    def tearDown(self):
        if self.server:self.server.shutdown();self.server.server_close()
        if self.thread:self.thread.join(timeout=2)
        self.tmp.cleanup()
    def start(self,**changes):
        env={'CRASHCART_MONITOR_TOKEN':TOKEN}
        for item in [self.a,self.b]:
            env.update({_prefix(item['id'])+key:value for key,value in {'ALLOW_SANDBOX':'1','PAYPAL_CLIENT_ID':'local-client','PAYPAL_CLIENT_SECRET':'local-secret','PAYPAL_WEBHOOK_ID':'local-webhook','PAYPAL_MERCHANT_ID':'LOCAL-MERCHANT'}.items()})
        def factory(values):
            self.factories.append(True);owner=self
            class Verifier:
                def verify_webhook(self,headers,event,*,raw_body):owner.calls.append(raw_body);return False
            return Verifier()
        self.server=make_server(self.path,port=0,environ=env,paypal_factory=factory,start_scanner=False,ingress_limits=IngressLimits(**changes),ingress_clock=lambda:self.now[0])
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def headers(self):
        return {'Paypal-Auth-Algo':'SHA256withRSA','Paypal-Cert-Url':'https://api-m.sandbox.paypal.com/v1/notifications/certs/LOCALFIXTURE','Paypal-Transmission-Id':'local-transmission','Paypal-Transmission-Sig':base64.b64encode(b'local-signature').decode(),'Paypal-Transmission-Time':'2026-11-06T10:00:00Z'}
    def payload(self):return json.dumps({'id':'local-event','event_type':'PAYMENT.CAPTURE.PENDING'}).encode()
    def request(self,path,*,raw=None,headers=None,method='POST',timeout=2):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=timeout)
        # Read-only probes must not send a webhook payload in a second write:
        # admission overload can reply and close before that write is possible.
        readonly=method.upper() in {'GET','HEAD'}
        body=None if readonly else self.payload() if raw is None else raw
        request_headers=({} if readonly else self.headers()) if headers is None else headers
        try:
            c.request(method,path,body=body,headers=request_headers)
            r=c.getresponse();return r.status,r.read(),dict(r.getheaders())
        finally:c.close()
    def wire(self,data):
        c=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2);c.sendall(data);result=b''
        try:
            while True:
                chunk=c.recv(4096)
                if not chunk:break
                result+=chunk
        except ConnectionResetError:pass
        finally:c.close()
        return result
    def await_handlers(self,count):
        deadline=time.monotonic()+1
        while self.server.active_handlers!=count and time.monotonic()<deadline:time.sleep(.005)
        self.assertEqual(self.server.active_handlers,count)
    def test_global_rejects_before_body_database_or_verifier_then_recovers(self):
        self.start(global_burst=1,global_per_second=1)
        self.assertEqual(self.request('/webhooks/not-registered/paypal')[0],404)
        with patch.object(self.server.monitor_store,'get_store',side_effect=AssertionError('DB must not run')),patch.object(self.server.RequestHandlerClass,'body',side_effect=AssertionError('body must not run')):
            raw=f'POST /webhooks/{self.a["id"]}/paypal HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\n'.encode()
            response=self.wire(raw);self.assertIn(b'503',response);self.assertIn(b'Retry-After:',response)
        self.assertEqual(self.factories,[]);self.now[0]=1
        self.assertEqual(self.request('/webhooks/'+self.a['id']+'/paypal')[0],401);self.assertEqual(len(self.calls),1)
    def test_store_budget_shared_across_routes_headers_and_providers(self):
        self.start(global_burst=100,global_per_second=1,store_burst=1,store_per_second=1,max_store_buckets=2)
        route='/webhooks/'+self.a['id']+'/paypal'
        self.assertEqual(self.request(route)[0],401)
        self.assertEqual(self.request(route+'/?delivery=changed',headers={**self.headers(),'X-Forwarded-For':'another-client'})[0],503)
        self.assertEqual(self.request('http://127.0.0.1:'+str(self.server.server_port)+route+'?changed=again')[0],503)
        self.assertEqual(self.request(route,method='GET')[0],503)
        self.assertEqual(self.request('/webhooks/'+self.a['id']+'/woocommerce')[0],503)
        self.assertEqual(self.request('/webhooks/'+self.b['id']+'/paypal')[0],401)
        for i in range(12):self.assertEqual(self.request('/webhooks/unknown-'+str(i)+'/paypal')[0],404)
        third=self.server.monitor_store.create_store('Store C','woocommerce','https://c.example.test',60)
        self.assertEqual(self.request('/webhooks/'+third['id']+'/paypal')[0],503)
        self.assertEqual(len(self.server.monitor_limiter.stores),2);self.assertEqual(len(self.calls),2)
        self.now[0]=1;self.assertEqual(self.request(route)[0],401)
    def test_concurrency_cap_slow_body_deadline_and_permit_recovery(self):
        self.start(max_handlers=1,request_timeout=.2)
        slow=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
        self.addCleanup(slow.close)
        slow.sendall(b'POST /api/login HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nx')
        self.await_handlers(1)
        status,_,headers=self.request('/healthz',method='GET');self.assertEqual(status,503);self.assertEqual(headers['Retry-After'],'1')
        started=time.monotonic();response=b''
        try:
            while True:
                data=slow.recv(4096)
                if not data:break
                response+=data
        except ConnectionResetError:pass
        finally:slow.close()
        self.assertLess(time.monotonic()-started,1);self.assertNotIn(b'200 OK',response)
        self.await_handlers(0);self.assertEqual(self.request('/healthz',method='GET')[0],200)
        self.assertLessEqual(self.server.peak_handlers,1)
    def test_close_shuts_partial_request_socket_and_releases_handler(self):
        self.start(max_handlers=1)
        slow=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=2)
        slow.sendall(b'POST /api/login HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nx');self.await_handlers(1)
        self.server.shutdown();self.thread.join(timeout=2);self.server.server_close()
        try:
            while slow.recv(4096):pass
        except ConnectionResetError:pass
        finally:slow.close()
        self.await_handlers(0)
    def test_duplicate_headers_bad_framing_deep_json_and_disconnect_release_permits(self):
        self.start(max_handlers=2,request_timeout=.3)
        base=f'POST /webhooks/{self.a["id"]}/paypal HTTP/1.1\r\nHost: localhost\r\n'.encode()
        for extra in [b'Content-Length: +1\r\n',b'Content-Length: 1_0\r\n',b'Content-Length: 1\r\nContent-Length: 1\r\n',b'Content-Length: 1\r\nTransfer-Encoding:\r\n',b'Content-Length: 1\r\nPaypal-Transmission-Sig: aa==\r\nPaypal-Transmission-Sig: aa==\r\n']:
            response=self.wire(base+extra+b'\r\nx');self.assertIn(b'400',response)
        deep=b'{"nested":'+b'['*1100+b'0'+b']'*1100+b'}'
        self.assertEqual(self.request('/api/login',raw=deep,headers={'X-CrashCart-Request':'1'})[0],400)
        c=socket.create_connection(('127.0.0.1',self.server.server_port));c.sendall(b'bad request\r\n\r\n');c.close()
        self.await_handlers(0);self.assertEqual(self.request('/healthz',method='GET')[0],200);self.assertEqual(self.factories,[])
    def test_missing_invalid_and_duplicate_signature_metadata_never_dispatch_provider(self):
        self.start();route='/webhooks/'+self.a['id']+'/paypal'
        for headers in [{'Content-Type':'application/json'},{**self.headers(),'Paypal-Cert-Url':'https://not-paypal.example.test/cert'},{**self.headers(),'Paypal-Transmission-Sig':'not-base64!'}]:
            self.assertEqual(self.request(route,headers=headers)[0],401)
        self.assertEqual(self.request(route,method='PUT')[0],405);self.assertEqual(self.factories,[])
    def test_intentional_receipt_capacity_is_retryable_not_acknowledged(self):
        self.start()
        class Success:
            def verify_webhook(self,*args,**kwargs):return True
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        env={'CRASHCART_MONITOR_TOKEN':TOKEN,**{_prefix(self.a['id'])+k:v for k,v in {'ALLOW_SANDBOX':'1','PAYPAL_CLIENT_ID':'local','PAYPAL_CLIENT_SECRET':'local','PAYPAL_WEBHOOK_ID':'local','PAYPAL_MERCHANT_ID':'LOCAL-MERCHANT'}.items()}}
        self.server=make_server(self.path,port=0,environ=env,paypal_factory=lambda _:Success(),start_scanner=False)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        body=json.dumps({'id':'local','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{'id':'CAP-1','status':'COMPLETED','payee':{'merchant_id':'LOCAL-MERCHANT'},'create_time':datetime.now(timezone.utc).isoformat(),'amount':{'currency_code':'USD','value':'29.00'}}}).encode()
        with patch.object(self.server.monitor_store,'record_payment',side_effect=ReceiptCapacityError('private diagnostic')):
            status,response,headers=self.request('/webhooks/'+self.a['id']+'/paypal',raw=body)
        self.assertEqual(status,503);self.assertIn('Retry-After',headers);self.assertNotIn(b'private diagnostic',response)
        self.assertEqual(self.server.monitor_store.orders(self.a['id']),[])
    def test_real_database_lock_returns_retryable_error_and_rolls_back(self):
        import sqlite3
        self.start(max_handlers=2)
        status,_,headers=self.request('/api/login',raw=json.dumps({'token':TOKEN}).encode(),headers={'X-CrashCart-Request':'1'})
        self.assertEqual(status,200);cookie=headers['Set-Cookie'].split(';')[0]
        locker=sqlite3.connect(self.path);locker.execute('BEGIN IMMEDIATE')
        payload=json.dumps({'name':'Must roll back','platform':'woocommerce','domain':'https://new.example.test','promise_seconds':60}).encode()
        try:
            # Actual writer contention using the production SQLite busy wait.
            started=time.monotonic()
            status,body,headers=self.request('/api/stores',raw=payload,headers={'X-CrashCart-Request':'1','Cookie':cookie},timeout=5)
            self.assertEqual(status,503);self.assertIn('Retry-After',headers);self.assertNotIn(b'locked',body)
            self.assertLess(time.monotonic()-started,5)
        finally:locker.rollback();locker.close()
        self.await_handlers(0);self.assertEqual(len(self.server.monitor_store.list_stores()),2)
        self.assertEqual(self.request('/api/stores',raw=payload,headers={'X-CrashCart-Request':'1','Cookie':cookie})[0],201)
        self.assertEqual(len(self.server.monitor_store.list_stores()),3)
    def test_actual_receipt_alias_capacity_returns_503_without_acknowledging_alias(self):
        import sqlite3
        self.start()
        class Success:
            def verify_webhook(self,*args,**kwargs):return True
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        env={'CRASHCART_MONITOR_TOKEN':TOKEN,**{_prefix(self.a['id'])+k:v for k,v in {'ALLOW_SANDBOX':'1','PAYPAL_CLIENT_ID':'local','PAYPAL_CLIENT_SECRET':'local','PAYPAL_WEBHOOK_ID':'local','PAYPAL_MERCHANT_ID':'LOCAL-MERCHANT'}.items()}}
        with patch('crashcart.monitor_server.MonitorStore',side_effect=lambda path:MonitorStore(path,receipt_alias_limit=1)):
            self.server=make_server(self.path,port=0,environ=env,paypal_factory=lambda _:Success(),start_scanner=False)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        event={'id':'canonical-local-event','event_type':'PAYMENT.CAPTURE.COMPLETED','resource':{'id':'CAP-CAPACITY','status':'COMPLETED','payee':{'merchant_id':'LOCAL-MERCHANT'},'create_time':datetime.now(timezone.utc).isoformat(),'amount':{'currency_code':'USD','value':'29.00'}}}
        route='/webhooks/'+self.a['id']+'/paypal'
        self.assertEqual(self.request(route,raw=json.dumps(event).encode())[0],200)
        with closing(sqlite3.connect(self.path)) as db:
            before=(db.execute('SELECT COUNT(*) FROM monitor_events').fetchone()[0],db.execute('SELECT COUNT(*) FROM monitor_payments').fetchone()[0])
        event['id']='refused-alias-local-event'
        status,_,headers=self.request(route,raw=json.dumps(event).encode());self.assertEqual(status,503);self.assertIn('Retry-After',headers)
        with closing(sqlite3.connect(self.path)) as db:
            after=(db.execute('SELECT COUNT(*) FROM monitor_events').fetchone()[0],db.execute('SELECT COUNT(*) FROM monitor_payments').fetchone()[0])
        self.assertEqual(before,after);self.assertEqual(before,(1,1))
        event['id']='canonical-local-event';self.assertEqual(self.request(route,raw=json.dumps(event).encode())[0],200)
    def test_total_socket_deadline_survives_header_and_body_drip(self):
        self.start(max_handlers=1,request_timeout=.2)
        for prefix in [b'POST /api/login HTTP/1.1\r\nHost: localhost\r\nX-Drip: ',b'POST /api/login HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\n']:
            c=socket.create_connection(('127.0.0.1',self.server.server_port),timeout=1)
            started=time.monotonic();c.sendall(prefix);self.await_handlers(1)
            closed=threading.Event();closed_at=[]
            def receive():
                try:
                    while c.recv(4096):pass
                except OSError:pass
                finally:closed_at.append(time.monotonic());closed.set()
            reader=threading.Thread(target=receive,daemon=True);reader.start()
            try:
                while not closed.is_set() and time.monotonic()-started<.6:
                    try:c.sendall(b'x')
                    except OSError:break
                    closed.wait(.04)
                self.assertTrue(closed.wait(1));self.assertLess(closed_at[0]-started,.5)
            finally:c.close();reader.join(timeout=1)
            self.await_handlers(0)
        self.assertEqual(self.request('/healthz',method='GET')[0],200)
    def test_all_consumed_critical_header_duplicates_are_rejected(self):
        self.start(global_burst=100)
        names=['Host','Origin','Cookie','X-CrashCart-Request','Paypal-Auth-Algo','Paypal-Cert-Url','Paypal-Transmission-Id','Paypal-Transmission-Sig','Paypal-Transmission-Time','X-Shopify-Hmac-Sha256','X-Shopify-Shop-Domain','X-Shopify-Topic','X-Shopify-Webhook-Id','X-WC-Webhook-Signature','X-WC-Webhook-Source','X-WC-Webhook-Topic','X-WC-Webhook-Delivery-ID']
        route=f'POST /webhooks/{self.a["id"]}/paypal HTTP/1.1\r\n'.encode()
        for name in names:
            for second in [name,name.lower()]:
                prefix=b'' if name=='Host' else b'Host: localhost\r\n'
                raw=route+prefix+f'{name}: x\r\n{second}: x\r\nContent-Length: 1\r\n\r\nx'.encode()
                self.assertIn(b'400',self.wire(raw))
        self.assertEqual(self.factories,[]);self.assertEqual(self.server.monitor_limiter.stores,{})
    def test_handler_setup_and_thread_spawn_failures_release_capacity(self):
        self.start(max_handlers=1)
        raw=b'GET /healthz HTTP/1.1\r\nHost: localhost\r\n\r\n'
        with patch.object(self.server,'handle_error') as handled:
            with patch.object(self.server.RequestHandlerClass,'setup',side_effect=OSError('controlled setup failure')):
                self.wire(raw)
            self.await_handlers(0);self.assertTrue(handled.called)
            handled.reset_mock()
            with patch('threading.Thread.start',side_effect=RuntimeError('controlled spawn failure')):
                self.wire(raw)
            self.await_handlers(0);self.assertTrue(handled.called)
        self.assertEqual(self.request('/healthz',method='GET')[0],200)
        self.assertLessEqual(self.server.peak_handlers,1)
