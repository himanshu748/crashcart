"""Scoped loopback public-namespace checks. Synthetic and actual replay are separate."""
from concurrent.futures import ThreadPoolExecutor
import http.client
from http.server import ThreadingHTTPServer
import io,json,os,socket,threading,unittest,zipfile
from unittest.mock import patch
from crashcart.server import Handler,RECORDED_FILES,RECORDED_MAX_FILE

class PrivateState:
    def __getattr__(self,name):raise AssertionError('Recorded route touched private workspace: '+name)

def synthetic_bundle():
    files={}
    for name in RECORDED_FILES:
        kind=('text/html' if name.endswith('.html') else 'text/javascript' if name.endswith('.js') else 'text/css' if name.endswith('.css') else 'application/zip' if name.endswith('.zip') else 'application/json' if name.endswith('.json') else 'text/plain')
        files[name]=(kind,('LOCAL_TEST namespace fixture: '+name).encode())
    return files

class HTTPFixture(unittest.TestCase):
    def setUp(self):
        self.server=self.thread=None
        env=patch.dict(os.environ,{'CRASHCART_OPERATOR_TOKEN':'synthetic-namespace-test'});env.start();self.addCleanup(env.stop)
        original=socket.socket.connect;resolve=socket.getaddrinfo
        def loopback(sock,address):
            if not isinstance(address,tuple) or address[0]!='127.0.0.1':raise AssertionError('Outbound connections forbidden')
            return original(sock,address)
        def loopback_resolution(host,*args,**kwargs):
            if host!='127.0.0.1':raise AssertionError('External DNS forbidden')
            return resolve(host,*args,**kwargs)
        guard=patch.object(socket.socket,'connect',loopback);guard.start();self.addCleanup(guard.stop)
        dns=patch.object(socket,'getaddrinfo',loopback_resolution);dns.start();self.addCleanup(dns.stop)
        fqdn=patch.object(socket,'getfqdn',return_value='localhost');fqdn.start();self.addCleanup(fqdn.stop)
        # Keep all network guards installed until every server handler finishes.
        self.addCleanup(self.stop)
    def start(self,builder=None,handler=Handler):
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler);self.server.store=PrivateState()
        if builder is not None:self.server._recorded_bundle_builder=builder
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def stop(self):
        if self.server:self.server.shutdown();self.server.server_close()
        if self.thread:self.thread.join(5)
        self.server=self.thread=None
    def request(self,path,method='GET',body=None):
        client=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=15)
        try:
            client.request(method,path,body=body,headers={'Content-Type':'application/json'} if method=='POST' else {})
            response=client.getresponse();return response.status,response.read(),dict(response.getheaders())
        finally:client.close()

class RecordedNamespaceUnitTests(HTTPFixture):
    """Injected, labelled bundle only; no claim of actual replay execution."""
    def test_lazy_single_cache_thirteen_exact_members_and_private_auth(self):
        calls=[];files=synthetic_bundle()
        self.start(lambda:calls.append(True) or files)
        self.assertEqual(len(RECORDED_FILES),13);self.assertEqual(self.request('/api/runs')[0],401);self.assertEqual(calls,[])
        for name in sorted(RECORDED_FILES):
            status,body,headers=self.request('/recorded/'+name)
            self.assertEqual(status,200);self.assertEqual(body,files[name][1]);self.assertIn("script-src 'self'",headers['Content-Security-Policy']);self.assertNotIn('Set-Cookie',headers)
        self.assertEqual(len(calls),1);original=self.request('/recorded/')[1]
        files['index.html']=('text/html',b'changed builder dictionary')
        self.assertEqual(self.request('/recorded/')[1],original);self.assertEqual(self.request('/api/runs')[0],401);self.assertEqual(len(calls),1)
    def test_concurrent_build_is_once_and_contenders_do_not_queue(self):
        calls=[];entered=threading.Event();release=threading.Event();self.addCleanup(release.set)
        def build():
            calls.append(True);entered.set()
            if not release.wait(5):raise AssertionError('Test did not release builder')
            return synthetic_bundle()
        self.start(build)
        with ThreadPoolExecutor(max_workers=5) as pool:
            first=pool.submit(self.request,'/recorded/');self.assertTrue(entered.wait(5))
            others=[pool.submit(self.request,'/recorded/data.json') for _ in range(4)]
            for future in others:
                status,_,headers=future.result(timeout=5);self.assertEqual(status,503);self.assertEqual(headers['Retry-After'],'1')
            self.assertEqual(len(calls),1);release.set();self.assertEqual(first.result(timeout=5)[0],200)
        self.assertEqual(self.request('/recorded/data.json')[0],200);self.assertEqual(len(calls),1)
    def test_unknown_and_traversal_paths_do_not_build_or_read_files(self):
        calls=[];self.start(lambda:calls.append(True) or synthetic_bundle())
        for suffix in ('../api/runs','../../.env','%2e%2e/.env','%64ata.json','/data.json','downloads/../../.env','api/runs','demo.html/../data.json','unknown.js'):
            self.assertEqual(self.request('/recorded/'+suffix)[0],404)
        status,_,headers=self.request('/recorded');self.assertEqual(status,308);self.assertEqual(headers['Location'],'/recorded/');self.assertEqual(calls,[])
    def test_post_rejected_before_body_auth_or_api_dispatch(self):
        calls=[];self.start(lambda:calls.append(True) or synthetic_bundle())
        with patch.object(Handler,'api_post',side_effect=AssertionError('Must not dispatch')):
            for route in ('/recorded','/recorded/','/recorded/data.json','/recorded/api/runs'):
                status,body,headers=self.request(route,'POST',b'{not valid json');self.assertEqual(status,405);self.assertEqual(headers['Allow'],'GET');self.assertIn(b'read-only',body)
        self.assertEqual(calls,[]);self.assertEqual(self.request('/api/runs','POST',b'{}')[0],401)
    def test_hosted_handler_inherits_public_get_and_rejects_post_without_runtime_or_keys(self):
        from crashcart.hosted_live import HostedHandler
        calls=[];self.start(lambda:calls.append(True) or synthetic_bundle(),handler=HostedHandler)
        self.assertEqual(self.request('/recorded/site.js')[0],200)
        self.assertEqual(self.request('/recorded/data.json','POST',b'{invalid')[0],405)
        self.assertEqual(len(calls),1)
    def test_failed_builder_does_not_repeat_on_refresh(self):
        calls=[]
        def build():calls.append(True);raise ValueError('Synthetic failure details')
        self.start(build)
        for route in ('/recorded/','/recorded/data.json','/recorded/demo.html'):
            status,body,_=self.request(route);self.assertEqual(status,503);self.assertNotIn(b'Synthetic failure details',body)
        self.assertEqual(len(calls),1)
    def test_extra_member_and_memory_bounds_fail_closed(self):
        for problem in ('extra','missing','oversized'):
            with self.subTest(problem=problem):
                calls=[]
                def build():
                    calls.append(True);files=synthetic_bundle()
                    if problem=='extra':files['../../.env']=('text/plain',b'not a private file')
                    elif problem=='missing':files.pop('site.js')
                    else:files['data.json']=('application/json',bytes(RECORDED_MAX_FILE+1))
                    return files
                self.start(build)
                try:self.assertEqual(self.request('/recorded/data.json')[0],503);self.assertEqual(self.request('/recorded/')[0],503);self.assertEqual(len(calls),1)
                finally:self.stop()

class RecordedNamespaceActualReplayTests(HTTPFixture):
    """Run only after new pages and judge.ASSETS land; actual offline replay."""
    def test_actual_public_pages_data_downloads_and_read_only_auth_boundaries(self):
        from crashcart import judge
        self.assertTrue({'index.html','product.html','integrations.html','demo.html','site.js'}<=set(judge.ASSETS),'New canonical public assets must land before this check')
        self.start()
        for name in ('','product.html','integrations.html','demo.html','app.js','site.js','style.css','LICENSE'):
            status,body,_=self.request('/recorded/'+name);self.assertEqual(status,200);self.assertTrue(body)
        status,raw,_=self.request('/recorded/data.json');self.assertEqual(status,200);data=json.loads(raw)
        self.assertEqual(data['mode'],'RECORDED_REPLAY');self.assertFalse(data['fresh_execution']);self.assertEqual(data['network_calls'],0)
        self.assertEqual(data['cases']['defective']['receipt']['signature'],'paid_without_ticket')
        self.assertEqual(data['cases']['healthy']['receipt']['signature'],'ticket_delivered_once_on_time');self.assertEqual(data['cases']['healthy']['receipt']['verdict'],'PASS')
        for name in ('input.json','defective.json','healthy.json'):self.assertEqual(self.request('/recorded/downloads/'+name)[0],200)
        status,archive,headers=self.request('/recorded/downloads/replay.zip');self.assertEqual(status,200);self.assertEqual(headers['Content-Type'],'application/zip')
        with zipfile.ZipFile(io.BytesIO(archive)) as package:self.assertIn('input.json',package.namelist());self.assertIn('README.md',package.namelist())
        self.assertEqual(self.request('/api/runs')[0],401);self.assertEqual(self.request('/recorded/data.json','POST',b'{}')[0],405);self.assertEqual(self.request('/recorded/../api/runs')[0],404)

if __name__=='__main__':unittest.main(verbosity=2)
