"""Local HTTP/signature fixtures; no provider execution."""
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from crashcart.monitor_server import make_server, _prefix
from crashcart.monitor_store import MonitorStore
TOKEN = 'local-http-test-operator-token-32chars'
SECRET = 'local-commerce-fixture-secret'

class MonitorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.path = Path(self.tmp.name) / 'monitor.sqlite3'
        domain = MonitorStore(self.path)
        self.store = domain.create_store('Owned test store','woocommerce','https://owned.example.test',60)
        self.other = domain.create_store('Other test store','shopify','owned.myshopify.com',60)
        prefix = _prefix(self.store['id'])
        env = {'CRASHCART_MONITOR_TOKEN':TOKEN,prefix+'WOOCOMMERCE_SECRET':SECRET,
               prefix+'ALLOW_SANDBOX':'1',prefix+'PAYPAL_CLIENT_ID':'local-client',
               prefix+'PAYPAL_CLIENT_SECRET':'local-secret',prefix+'PAYPAL_WEBHOOK_ID':'local-webhook',
               prefix+'PAYPAL_MERCHANT_ID':'OWNED-MERCHANT'}
        self.verifications = []
        def factory(config):
            owner = self
            class FixtureVerifier:
                def verify_webhook(self,headers,event,*,raw_body):
                    owner.verifications.append((event,raw_body))
                    return headers.get('X-Test-Signature') == 'valid-local-fixture'
            return FixtureVerifier()
        self.server = make_server(self.path,port=0,environ=env,paypal_factory=factory,start_scanner=False)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.cookie=None
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3);self.tmp.cleanup()
    def request(self,path,data=None,headers=None,*,raw=None,method=None):
        method = method or ('POST' if data is not None or raw is not None else 'GET')
        payload = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
        hdr = {'X-CrashCart-Request':'1',**({'Cookie':self.cookie} if self.cookie else {}),**(headers or {})}
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=3)
        conn.request(method,path,body=payload,headers=hdr);res=conn.getresponse();body=res.read()
        result=(res.status,json.loads(body),dict(res.getheaders()));conn.close();return result
    def login(self):
        status,body,headers=self.request('/api/login',{'token':TOKEN});self.assertEqual(status,200)
        self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.cookie=headers['Set-Cookie'].split(';')[0]
    def woo(self):
        now=datetime.now(timezone.utc).replace(microsecond=0)
        data={'id':123,'number':'Order 123','currency':'USD','total':'29.00','status':'processing',
              'date_modified_gmt':now.strftime('%Y-%m-%dT%H:%M:%S'),'date_completed_gmt':None,'transaction_id':'CAPTURE-123'}
        raw=json.dumps(data).encode()
        headers={'X-WC-Webhook-Source':'https://owned.example.test','X-WC-Webhook-Topic':'order.updated',
                 'X-WC-Webhook-Delivery-ID':'woo-delivery-1',
                 'X-WC-Webhook-Signature':base64.b64encode(hmac.new(SECRET.encode(),raw,hashlib.sha256).digest()).decode()}
        return raw,headers
    def paypal(self,merchant='OWNED-MERCHANT'):
        at=(datetime.now(timezone.utc)-timedelta(seconds=65)).isoformat()
        return {'id':'paypal-local-event-1','event_type':'PAYMENT.CAPTURE.COMPLETED',
                'resource':{'id':'CAPTURE-123','status':'COMPLETED','create_time':at,
                            'payee':{'merchant_id':merchant},'amount':{'currency_code':'USD','value':'29.00'}}}
    def test_shopify_setup_rejects_unusable_address_with_safe_hint(self):
        self.login();before=self.request('/api/stores')[1]['stores']
        status,data,_=self.request('/api/stores',{'name':'Local setup','platform':'shopify','domain':'https://wrong.example.test','promise_seconds':3600})
        self.assertEqual(status,400);self.assertIn('myshopify.com',data['error'])
        self.assertNotIn('wrong.example.test',data['error'])
        self.assertEqual(self.request('/api/stores')[1]['stores'],before)

    def test_auth_csrf_and_secret_minimization(self):
        self.assertEqual(self.request('/api/stores')[0],401)
        self.assertEqual(self.request('/api/login',{'token':TOKEN},{'Origin':'https://other.example.test'})[0],403)
        self.assertEqual(self.request('/api/login',{'token':'wrong'})[0],401);self.login()
        status,data,_=self.request('/api/stores');self.assertEqual(status,200)
        self.assertNotIn(SECRET,json.dumps(data));self.assertNotIn('local-secret',json.dumps(data))
        item=next(x for x in data['stores'] if x['id']==self.store['id'])
        self.assertTrue(item['connections']['commerce_configured']);self.assertFalse(item['connections']['connection_verified'])
        self.request('/api/logout',{});self.assertEqual(self.request('/api/stores')[0],401)
    def test_signed_order_payment_and_persistent_inbox(self):
        raw,headers=self.woo();route='/webhooks/'+self.store['id']+'/woocommerce'
        self.assertEqual(self.request(route,raw=raw,headers=headers)[0],200)
        self.assertEqual(self.request(route,raw=raw,headers=headers)[0],200)
        self.assertEqual(self.server.monitor_store.orders(self.store['id'])[0]['payment_state'],'unmatched')
        paypal='/webhooks/'+self.store['id']+'/paypal'
        event=self.paypal();self.assertEqual(self.request(paypal,event,{'X-Test-Signature':'valid-local-fixture'})[0],200)
        self.assertEqual(self.request(paypal,event,{'X-Test-Signature':'bad'})[0],401)
        self.assertEqual(len(self.server.monitor_store.alerts(self.store['id'])),1)
        self.login();_,inbox,_=self.request('/api/stores/'+self.store['id']+'/alerts');alert=inbox['alerts'][0]
        self.assertEqual(self.request('/api/stores/'+self.other['id']+'/alerts/'+alert['id']+'/ack',{})[0],404)
        self.assertEqual(self.request('/api/stores/'+self.store['id']+'/alerts/'+alert['id']+'/ack',{})[0],200)
        self.assertTrue(MonitorStore(self.path).alerts(self.store['id'])[0]['acknowledged_at'])
    def test_invalid_deliveries_never_mutate(self):
        raw,headers=self.woo();route='/webhooks/'+self.store['id']+'/woocommerce'
        self.assertEqual(self.request(route,raw=raw+b' ',headers=headers)[0],401)
        self.assertEqual(self.server.monitor_store.orders(self.store['id']),[])
        self.assertEqual(self.request('/webhooks/'+self.other['id']+'/woocommerce',raw=raw,headers=headers)[0],400)
        self.assertEqual(self.request('/webhooks/'+self.other['id']+'/paypal',self.paypal())[0],503)
        self.assertEqual(self.request('/webhooks/'+self.store['id']+'/paypal',self.paypal('OTHER-MERCHANT'),{'X-Test-Signature':'valid-local-fixture'})[0],400)
        self.assertEqual(self.server.monitor_store.orders(self.store['id']),[])
    def test_body_limits_duplicate_json_and_no_payment_routes(self):
        self.assertEqual(self.request('/api/login',raw=b'{"token":"a","token":"b"}')[0],400)
        self.assertEqual(self.request('/api/login',raw=b'x'*131073)[0],400);self.login()
        self.assertEqual(self.request('/api/stores',{'name':'Another','platform':'woocommerce','domain':'https://next.example.test','promise_seconds':120})[0],201)
        self.assertEqual(self.request('/api/stores/'+self.store['id']+'/capture',{})[0],404)
        self.assertEqual(self.request('/api/stores/missing/alerts')[0],404)
    def test_missing_operator_token(self):
        with self.assertRaises(ValueError):make_server(self.path,port=0,environ={})

    def test_failed_login_is_bounded(self):
        for _ in range(5):self.assertEqual(self.request('/api/login',{'token':'wrong'})[0],401)
        self.assertEqual(self.request('/api/login',{'token':'wrong'})[0],429)

    def test_https_proxy_origin_sets_secure_cookie_and_rejects_other_origin(self):
        server=make_server(self.path,port=0,environ={'CRASHCART_MONITOR_TOKEN':TOKEN,'CRASHCART_MONITOR_PUBLIC_ORIGIN':'https://monitor.example.test'},start_scanner=False)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();original=self.server
        try:
            self.server=server;headers={'Host':'monitor.example.test','Origin':'https://monitor.example.test'}
            status,_,response=self.request('/api/login',{'token':TOKEN},headers)
            self.assertEqual(status,200);self.assertIn('; Secure',response['Set-Cookie'])
            headers['Origin']='https://wrong.example.test'
            self.assertEqual(self.request('/api/login',{'token':TOKEN},headers)[0],403)
        finally:
            self.server=original;server.shutdown();server.server_close();thread.join(timeout=3)

    def test_scanner_failure_is_visible_in_health(self):
        from unittest.mock import patch
        called=threading.Event()
        def fail(*args):
            called.set();raise ValueError('controlled local scanner failure')
        with patch.object(MonitorStore,'scan',fail):
            server=make_server(self.path,port=0,environ={'CRASHCART_MONITOR_TOKEN':TOKEN},start_scanner=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();original=self.server
            try:
                self.server=server;self.assertTrue(called.wait(1));status,health,_=self.request('/healthz')
                self.assertEqual(status,200);self.assertEqual(health['status'],'degraded')
                self.assertEqual(health['scanner']['status'],'error');self.assertIsNone(health['scanner']['last_scan_at'])
            finally:
                self.server=original;server.shutdown();server.server_close();thread.join(timeout=3)

    def test_background_scanner_creates_alert_without_inbox_request(self):
        from unittest.mock import patch
        domain=self.server.monitor_store;now=datetime.now(timezone.utc)
        paid=(now-timedelta(seconds=70)).isoformat();updated=now.isoformat()
        domain.upsert_order(self.store['id'],'background-order',display_number='Background order',currency='USD',total_minor=2900,payment_references=['CAPTURE-BG'],fulfillment_status='unfulfilled',fulfilled_at=None,updated_at=updated,event_id='background-commerce')
        domain.record_payment(self.store['id'],capture_id='CAPTURE-BG',reference='CAPTURE-BG',currency='USD',amount_minor=2900,completed_at=paid,event_id='background-payment')
        self.assertEqual(domain.alerts(self.store['id']),[])
        completed=threading.Event();original_scan=MonitorStore.scan
        def observed_scan(instance,at):
            result=original_scan(instance,at);completed.set();return result
        with patch.object(MonitorStore,'scan',observed_scan):
            server=make_server(self.path,port=0,environ={'CRASHCART_MONITOR_TOKEN':TOKEN},start_scanner=True)
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();original=self.server
            try:
                self.assertTrue(completed.wait(2));self.assertEqual(len(domain.alerts(self.store['id'])),1)
                self.server=server;_,health,_=self.request('/healthz')
                self.assertEqual(health['scanner']['status'],'running');self.assertTrue(health['scanner']['last_scan_at'])
            finally:
                self.server=original;server.shutdown();server.server_close();thread.join(timeout=3)

    def test_shared_commerce_secret_refuses_relabelled_delivery_for_both_platforms(self):
        domain=self.server.monitor_store
        for platform in ['shopify','woocommerce']:
            with self.subTest(platform=platform):
                first=self.other if platform=='shopify' else self.store
                second=domain.create_store('Separate '+platform,platform,'second.myshopify.com' if platform=='shopify' else 'https://second.example.test',60)
                secret_key='SHOPIFY_SECRET' if platform=='shopify' else 'WOOCOMMERCE_SECRET'
                if platform=='shopify':
                    raw=json.dumps({'id':123,'name':'#123','currency':'USD','total_price':'29.00','updated_at':'2026-11-06T10:00:00Z','fulfillment_status':None,'fulfillments':[]}).encode()
                    def headers(secret,store_item):
                        return {'X-Shopify-Shop-Domain':store_item['domain'],'X-Shopify-Topic':'orders/updated','X-Shopify-Webhook-Id':'local-shared-key-check','X-Shopify-Hmac-Sha256':base64.b64encode(hmac.new(secret.encode(),raw,hashlib.sha256).digest()).decode()}
                else:
                    raw,_=self.woo()
                    def headers(secret,store_item):
                        return {'X-WC-Webhook-Source':'https://'+store_item['domain'],'X-WC-Webhook-Topic':'order.updated','X-WC-Webhook-Delivery-ID':'local-shared-key-check','X-WC-Webhook-Signature':base64.b64encode(hmac.new(secret.encode(),raw,hashlib.sha256).digest()).decode()}
                for reused in [True,False]:
                    with self.subTest(reused=reused):
                        second_secret=SECRET if reused else SECRET+'-second-store'
                        env={'CRASHCART_MONITOR_TOKEN':TOKEN,_prefix(first['id'])+secret_key:SECRET,_prefix(second['id'])+secret_key:second_secret}
                        server=make_server(self.path,port=0,environ=env,start_scanner=False)
                        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();original=self.server
                        try:
                            self.server=server;self.cookie=None
                            # Raw body and signature are unchanged; source/delivery headers now name B.
                            status,body,_=self.request('/webhooks/'+second['id']+'/'+platform,raw=raw,headers=headers(SECRET,second))
                            self.assertEqual(status,503 if reused else 401)
                            self.assertEqual(domain.orders(second['id']),[])
                            self.login();_,data,_=self.request('/api/stores')
                            configured={s['id']:s['connections']['commerce_configured'] for s in data['stores']}
                            self.assertEqual(configured[first['id']],not reused);self.assertEqual(configured[second['id']],not reused)
                            self.assertNotIn(SECRET,json.dumps(data))
                            if reused:
                                self.assertIn('separate signing secret',body['error'])
                                self.assertEqual(self.request('/webhooks/'+first['id']+'/'+platform,raw=raw,headers=headers(SECRET,first))[0],503)
                            else:
                                self.assertEqual(self.request('/webhooks/'+first['id']+'/'+platform,raw=raw,headers=headers(SECRET,first))[0],200)
                                self.assertEqual(self.request('/webhooks/'+second['id']+'/'+platform,raw=raw,headers=headers(second_secret,second))[0],200)
                        finally:
                            self.server=original;server.shutdown();server.server_close();thread.join(timeout=3)

    def test_authenticated_store_readback_and_ack_isolation_survive_restart(self):
        """LOCAL_TEST seeds collide externally; actual HTTP reads remain store-scoped."""
        domain=self.server.monitor_store;now=datetime.now(timezone.utc)
        paid=(now-timedelta(seconds=120)).isoformat()
        fulfilled=(now-timedelta(seconds=100)).isoformat()
        for item,number,status,completed in [
            (self.store,'A overdue order','unfulfilled',None),
            (self.other,'B fulfilled order','fulfilled',fulfilled),
        ]:
            domain.upsert_order(item['id'],'identical-external-order',display_number=number,
                currency='USD',total_minor=2900,payment_references=['identical-payment-reference'],
                fulfillment_status=status,fulfilled_at=completed,updated_at=now.isoformat(),
                event_id='identical-commerce-event')
            domain.record_payment(item['id'],capture_id='identical-capture-id',
                reference='identical-payment-reference',currency='USD',amount_minor=2900,
                completed_at=paid,event_id='identical-payment-event')
        domain.scan(now.isoformat())
        self.assertEqual(len(domain.alerts(self.store['id'])),1)
        self.assertEqual(domain.alerts(self.other['id']),[])
        self.login();old_cookie=self.cookie
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
        self.assertFalse(self.thread.is_alive())
        self.server=make_server(self.path,port=0,environ={'CRASHCART_MONITOR_TOKEN':TOKEN},start_scanner=False)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.cookie=old_cookie
        self.assertEqual(self.request('/api/stores')[0],401)
        self.login()
        status,stores,_=self.request('/api/stores');self.assertEqual(status,200)
        self.assertEqual({s['id'] for s in stores['stores']},{self.store['id'],self.other['id']})
        readback={}
        for item,number,state in [(self.store,'A overdue order','unfulfilled'),(self.other,'B fulfilled order','fulfilled')]:
            status,data,_=self.request('/api/stores/'+item['id']+'/orders');self.assertEqual(status,200)
            self.assertEqual(len(data['orders']),1);order=data['orders'][0]
            self.assertEqual(order['store_id'],item['id'])
            self.assertEqual(order['platform_order_id'],'identical-external-order')
            self.assertEqual(order['display_number'],number);self.assertEqual(order['fulfillment_status'],state)
            self.assertEqual(order['capture_id'],'identical-capture-id')
            self.assertEqual(order['payment_references'],['identical-payment-reference'])
            self.assertEqual(order['payment_state'],'confirmed')
            status,inbox,_=self.request('/api/stores/'+item['id']+'/alerts');self.assertEqual(status,200)
            readback[item['id']]=inbox['alerts']
        self.assertEqual(readback[self.other['id']],[])
        self.assertEqual(len(readback[self.store['id']]),1)
        alert=readback[self.store['id']][0]
        self.assertEqual(alert['store_id'],self.store['id'])
        self.assertIsNone(alert['acknowledged_at'])
        self.assertEqual(self.request('/api/stores/'+self.other['id']+'/alerts/'+alert['id']+'/ack',{})[0],404)
        _,unchanged,_=self.request('/api/stores/'+self.store['id']+'/alerts')
        self.assertEqual(unchanged['alerts'],[alert])
        self.assertEqual(self.request('/api/stores/'+self.store['id']+'/alerts/'+alert['id']+'/ack',{})[0],200)
        _,acknowledged,_=self.request('/api/stores/'+self.store['id']+'/alerts')
        self.assertTrue(acknowledged['alerts'][0]['acknowledged_at'])
        _,other_inbox,_=self.request('/api/stores/'+self.other['id']+'/alerts')
        self.assertEqual(other_inbox['alerts'],[])
