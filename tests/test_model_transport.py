"""No-network shared-provider and real caller regression tests; synthetic replies only."""
from copy import deepcopy
import io
import json
import os
import select
import socket
import threading
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request
import uuid

from crashcart import model_transport as wire
from crashcart.investigator import OpenAIModel, Investigation
from crashcart.studio_agent import StudioQuery, StudioQueryError
from crashcart.store import Store
from tests.test_promise import requested_values

ENV = {"CRASHCART_MODEL_PROVIDER":"modal", "MODAL_API_KEY":"test-only-modal-key",
       "MODAL_MODEL":wire.MODAL_MODEL, "MODAL_BASE_URL":"https://crashcart-model-test.modal.run",
       "MODAL_ALLOWED_ORIGIN":"https://crashcart-model-test.modal.run",
       "CRASHCART_ALLOW_MODEL":"1", "CRASHCART_STUDIO_MODEL_MAX_CALLS":"16"}
SCHEMA = {"type":"object", "properties":{"ok":{"type":"boolean"}}, "required":["ok"], "additionalProperties":False}

def chat(content='{"ok":true}', **changes):
    value={"id":"chatcmpl_synthetic", "model":wire.MODAL_MODEL,
           "usage":{"prompt_tokens":11,"completion_tokens":7,"total_tokens":18},
           "choices":[{"index":0,"message":{"role":"assistant","content":content},"finish_reason":"stop"}]}
    value.update(changes)
    return value

class Transport:
    def __init__(self, response=None, callback=None):
        self.response=chat() if response is None else response
        self.requests=[]; self.callback=callback
    def __call__(self, request, timeout):
        self.requests.append((request,timeout))
        if self.callback:
            self.callback(request)
        return deepcopy(self.response)


class LoopbackHTTP:
    """One owned loopback connection; never accepts an external destination."""
    def __init__(self, kind):
        self.kind=kind;self.stop=threading.Event();self.done=threading.Event()
        self.accepted=threading.Event();self.streaming=threading.Event()
        self.disconnected=False;self.request=b"";self.error=None
        self.socket=socket.socket();self.socket.bind(("127.0.0.1",0));self.socket.listen(1)
        self.url="http://127.0.0.1:"+str(self.socket.getsockname()[1])+"/test"
        self.thread=threading.Thread(target=self.serve,daemon=True);self.thread.start()
    def serve(self):
        try:
            self.socket.settimeout(3)
            with self.socket.accept()[0] as conn:
                self.accepted.set()
                conn.settimeout(3)
                while b"\r\n\r\n" not in self.request:
                    chunk=conn.recv(4096)
                    if not chunk:self.disconnected=True;return
                    self.request+=chunk
                headers,body=self.request.split(b"\r\n\r\n",1)
                length=next((int(line.split(b":",1)[1]) for line in headers.split(b"\r\n") if line.lower().startswith(b"content-length:")),0)
                while len(body)<length:
                    chunk=conn.recv(4096)
                    if not chunk:self.disconnected=True;return
                    body+=chunk
                response=json.dumps(chat(),separators=(",",":")).encode()
                if self.kind=="redirect":
                    conn.sendall(b"HTTP/1.1 302 Found\r\nLocation: https://must-never-contact.invalid/\r\nContent-Length: 0\r\n\r\n");return
                if self.kind=="complete":
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: "+str(len(response)).encode()+b"\r\n\r\n"+response);return
                if self.kind=="headers":
                    conn.sendall(b"HTTP/1.1 200 OK\r\nX-Drip: ")
                    drip=b"x"*100
                else:
                    conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: "+str(len(response)).encode()+b"\r\n\r\n")
                    drip=response[:100]
                for index,byte in enumerate(drip):
                    if self.stop.wait(.04):return
                    if select.select([conn],[],[],0)[0] and conn.recv(1,socket.MSG_PEEK)==b"":
                        self.disconnected=True;return
                    conn.sendall(bytes([byte]))
                    if index==0:self.streaming.set()
                if self.kind=="headers":
                    conn.sendall(b"\r\nContent-Length: "+str(len(response)).encode()+b"\r\n\r\n"+response)
                else:conn.sendall(response[len(drip):])
        except (BrokenPipeError,ConnectionResetError):self.disconnected=True
        except Exception as exc:self.error=type(exc).__name__
        finally:self.done.set()
    def close(self):
        self.stop.set();self.socket.close();self.thread.join(3)

class WallClockTransportTests(unittest.TestCase):
    def server(self,kind):
        server=LoopbackHTTP(kind);self.addCleanup(server.close);return server
    def assert_timeout_reaps_worker(self,server,timeout,elapsed_limit):
        processes=[];original=wire.subprocess.Popen
        def spawn(*args,**kwargs):
            proc=original(*args,**kwargs);processes.append(proc);return proc
        start=time.monotonic()
        with patch.object(wire.subprocess,"Popen",side_effect=spawn):
            with self.assertRaisesRegex(wire.ModelTransportError,"MODEL_TIMEOUT"):
                wire.http(Request(server.url,data=b"{}",method="POST"),timeout)
        self.assertLess(time.monotonic()-start,elapsed_limit)
        self.assertEqual(len(processes),1);self.assertIsNotNone(processes[0].returncode)
        with self.assertRaises(ChildProcessError):os.waitpid(processes[0].pid,os.WNOHANG)

    def test_short_total_deadline_kills_and_reaps_worker_even_during_startup(self):
        for kind in ("headers","body"):
            with self.subTest(kind=kind):
                server=self.server(kind)
                self.assert_timeout_reaps_worker(server,.3,.8)
                # Cold startup can consume the whole deadline before connecting.
                # A peer-disconnect assertion has no meaning without a peer.
                if server.accepted.is_set():
                    self.assertTrue(server.done.wait(.6));self.assertTrue(server.disconnected);self.assertIsNone(server.error)
                else:self.assertFalse(server.streaming.is_set())

    def test_active_dripping_headers_and_body_are_disconnected_at_total_deadline(self):
        for kind in ("headers","body"):
            with self.subTest(kind=kind):
                server=self.server(kind)
                self.assert_timeout_reaps_worker(server,2,2.6)
                # Mandatory precondition, never a skip: the four-second stream
                # must actually begin before the two-second request deadline.
                self.assertTrue(server.accepted.is_set())
                self.assertTrue(server.request)
                self.assertTrue(server.streaming.is_set())
                self.assertTrue(server.done.wait(.6));self.assertTrue(server.disconnected);self.assertIsNone(server.error)
    def test_worker_success_private_stdin_and_no_redirect(self):
        server=self.server("complete");original=wire.subprocess.Popen;calls=[]
        def spawn(*args,**kwargs):calls.append((args,kwargs));return original(*args,**kwargs)
        with patch.object(wire.subprocess,"Popen",side_effect=spawn):
            response=wire.http(Request(server.url,data=b"{}",method="POST",headers={"Authorization":"Bearer test-only-wire-secret"}),2)
        self.assertEqual(response,chat());self.assertIn(b"test-only-wire-secret",server.request)
        self.assertNotIn("test-only-wire-secret",repr(calls));self.assertEqual(calls[0][1]["env"],{"PATH":os.defpath})
        redirect=self.server("redirect")
        with self.assertRaisesRegex(wire.ModelTransportError,"MODEL_HTTP_302"):
            wire.http(Request(redirect.url,data=b"{}",method="POST"),2)
    def test_timeout_with_already_observed_response_retains_identity_and_usage(self):
        def late(_request,_timeout):raise wire.ModelTransportError("MODEL_TIMEOUT",response=chat())
        with self.assertRaises(wire.ModelTransportError) as error:
            wire.complete(wire.configuration(ENV),system="JSON",context={},schema=SCHEMA,schema_name="test",environ=ENV,timeout=1,transport=late)
        self.assertEqual(error.exception.code,"MODEL_TIMEOUT")
        self.assertEqual(error.exception.metadata["response_id"],"chatcmpl_synthetic")
        self.assertEqual(error.exception.metadata["usage"]["total_tokens"],18)

class ModalOriginConfigurationTests(unittest.TestCase):
    def setUp(self):
        blocker = patch("socket.create_connection", side_effect=AssertionError("Synthetic tests forbid network"))
        blocker.start(); self.addCleanup(blocker.stop)

    def test_owned_origin_pin_selects_exact_wire_endpoint_and_preserves_guards(self):
        env = {**ENV, "MODAL_ALLOWED_ORIGIN": "https://other-owned-test.modal.run",
               "MODAL_BASE_URL": "https://other-owned-test.modal.run"}
        transport = Transport()
        result = wire.complete(wire.configuration(env), system="JSON", context={}, schema=SCHEMA,
            schema_name="test", environ=env, timeout=5, transport=transport)
        self.assertEqual(len(transport.requests), 1)
        request = transport.requests[0][0]
        self.assertEqual(request.full_url, env["MODAL_ALLOWED_ORIGIN"] + "/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer " + env["MODAL_API_KEY"])
        self.assertEqual(result["endpoint_origin"], env["MODAL_ALLOWED_ORIGIN"])
        self.assertEqual(result["model"], wire.MODAL_MODEL)
        self.assertNotIn(env["MODAL_API_KEY"], repr(wire.configuration(env)))

    def test_malformed_or_unpinned_origin_never_dispatches_a_request(self):
        invalid = [wire.MODAL_ORIGIN, "https://modal.run", "http://owned.modal.run",
            "https://owned.modal.run/", "https://owned.modal.run/v1", "https://owned.modal.run:443",
            "https://owned.modal.run:8443", "https://user@owned.modal.run", "https://owned.modal.run?x=1",
            "https://owned.modal.run#x", "https://owned.modal.run.", "https://owned.modal.run.attacker.test",
            "https://owned.modal.run.modal.run", "https://ownéd.modal.run", "https://owned%2emodal.run",
            "https://owned-modal.run", "https://owned.example", "https://127.0.0.1",
            "https://Owned.modal.run", "https://-owned.modal.run", "https://owned-.modal.run",
            "https://" + "x" * 64 + ".modal.run", "https://owned.modal.run\n", None, 1]
        for origin in invalid:
            with self.subTest(origin=origin):
                transport = Transport()
                env = {**ENV, "MODAL_BASE_URL": origin, "MODAL_ALLOWED_ORIGIN": origin}
                with self.assertRaises(wire.ModelTransportError):
                    wire.complete(wire.configuration(env), system="JSON", context={}, schema=SCHEMA,
                        schema_name="test", environ=env, timeout=5, transport=transport)
                self.assertEqual(transport.requests, [])
        transport = Transport()
        with self.assertRaisesRegex(wire.ModelTransportError, "INVALID_MODAL_ENDPOINT_OR_MODEL"):
            wire.complete(wire.configuration({**ENV, "MODAL_BASE_URL":"https://different.modal.run"}),
                system="JSON", context={}, schema=SCHEMA, schema_name="test", environ=ENV,
                timeout=5, transport=transport)
        self.assertEqual(transport.requests, [])
        env = dict(ENV); del env["MODAL_ALLOWED_ORIGIN"]
        with self.assertRaisesRegex(wire.ModelTransportError, "MISSING_CONFIGURATION:MODAL_ALLOWED_ORIGIN"):
            wire.configuration(env)

    def test_placeholder_is_only_available_to_credential_free_injected_transports(self):
        config = wire.configuration({"CRASHCART_MODEL_PROVIDER":"modal"}, injected=True)
        self.assertEqual(config.origin, wire.MODAL_ORIGIN)
        self.assertEqual(config.key, "")
        env = {**ENV, "MODAL_BASE_URL":wire.MODAL_ORIGIN, "MODAL_ALLOWED_ORIGIN":wire.MODAL_ORIGIN}
        with self.assertRaisesRegex(wire.ModelTransportError, "INVALID_MODAL_ENDPOINT_OR_MODEL"):
            wire.configuration(env)
        injected = wire.configuration(ENV, injected=True)
        self.assertEqual(injected.origin, ENV["MODAL_ALLOWED_ORIGIN"])
        self.assertEqual(injected.key, "")

class SharedTransportTests(unittest.TestCase):
    def setUp(self):
        blocker=patch('socket.create_connection',side_effect=AssertionError('No network in synthetic transport tests'))
        blocker.start();self.addCleanup(blocker.stop)
    def complete(self, transport, **kwargs):
        return wire.complete(wire.configuration(ENV),system='Return exactly one JSON object.',context={},
            schema=SCHEMA,schema_name='test_schema',environ=ENV,timeout=5,transport=transport,**kwargs)
    def test_modal_exact_chat_request_and_actual_metadata(self):
        t=Transport();r=self.complete(t);request,timeout=t.requests[0];body=json.loads(request.data)
        self.assertEqual(len(t.requests),1)
        self.assertEqual(request.full_url,ENV["MODAL_ALLOWED_ORIGIN"]+'/v1/chat/completions')
        self.assertEqual(request.get_header('Authorization'),'Bearer '+ENV['MODAL_API_KEY'])
        self.assertGreater(timeout,0);self.assertLessEqual(timeout,5);self.assertEqual(body['max_tokens'],1024)
        self.assertEqual((body['stream'],body['n'],body['reasoning_effort']),(False,1,'none'))
        self.assertEqual(body['response_format'],{'type':'json_schema','json_schema':{'name':'test_schema','strict':True,'schema':SCHEMA}})
        self.assertEqual([m['role'] for m in body['messages']],['system','user'])
        self.assertFalse({'input','text','store','max_output_tokens','tools'}&body.keys())
        self.assertEqual(r['model'],wire.MODAL_MODEL);self.assertEqual(r['response_id'],'chatcmpl_synthetic')
        self.assertEqual(r['usage'],{'input_tokens':11,'output_tokens':7,'total_tokens':18})
        self.assertEqual((r['provider'],r['protocol'],r['endpoint_origin']),('modal','chat_completions',ENV["MODAL_ALLOWED_ORIGIN"]))
        self.assertEqual(r['request_bytes'],len(request.data));self.assertNotIn(ENV['MODAL_API_KEY'],json.dumps(r))
    def test_configuration_never_accepts_other_destinations_models_or_credentials(self):
        for origin in [ENV["MODAL_ALLOWED_ORIGIN"]+'/',ENV["MODAL_ALLOWED_ORIGIN"]+'?token=x',ENV["MODAL_ALLOWED_ORIGIN"]+'#x',ENV["MODAL_ALLOWED_ORIGIN"].replace('https:','http:'),'https://foreign.invalid',ENV["MODAL_ALLOWED_ORIGIN"].replace('https://','https://user@')]:
            with self.subTest(origin=origin),self.assertRaises(wire.ModelTransportError):wire.configuration({**ENV,'MODAL_BASE_URL':origin})
        for change in [{'CRASHCART_MODEL_PROVIDER':'unknown'},{'MODAL_MODEL':'another-model'},{'MODAL_API_KEY':''},{'MODAL_API_KEY':'x\r\nInjected: y'},{'CRASHCART_ALLOW_MODEL':'0'}]:
            with self.subTest(fields=list(change)),self.assertRaises(wire.ModelTransportError):wire.configuration({**ENV,**change})
        self.assertNotIn(ENV['MODAL_API_KEY'],repr(wire.configuration(ENV)))
    def test_openai_default_retains_responses_shape(self):
        env={'OPENAI_API_KEY':'test-only-openai','OPENAI_MODEL':'configured-model','CRASHCART_ALLOW_MODEL':'1'}
        t=Transport({'id':'resp_test','model':'actual-reported-model','status':'completed','usage':None,'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'{}'}]}]})
        r=wire.complete(wire.configuration(env),system='JSON',context={},schema=SCHEMA,schema_name='test',environ=env,timeout=5,transport=t)
        body=json.loads(t.requests[0][0].data)
        self.assertEqual(t.requests[0][0].full_url,'https://api.openai.com/v1/responses')
        self.assertFalse(body['store']);self.assertEqual(body['max_output_tokens'],1024);self.assertTrue(body['text']['format']['strict'])
        self.assertEqual(r['model'],'actual-reported-model');self.assertEqual(r['provider'],'openai');self.assertIsNone(r['usage'])
    def test_request_utf8_exact_byte_boundary_before_any_send(self):
        config=wire.configuration(ENV)
        def call(text,t):return wire.complete(config,system='JSON',context={'text':text},schema=SCHEMA,schema_name='test',environ=ENV,timeout=5,transport=t)
        initial=Transport();call('',initial);room=wire.MAX_REQUEST_BYTES-len(initial.requests[0][0].data)
        exact=Transport();self.assertEqual(call('x'*room,exact)['request_bytes'],65536)
        too_big=Transport()
        with self.assertRaises(wire.ModelTransportError) as e:call('x'*(room-1)+'é',too_big)
        self.assertEqual(e.exception.code,'MODEL_REQUEST_TOO_LARGE');self.assertEqual(e.exception.metadata['request_bytes'],65537);self.assertEqual(too_big.requests,[])
    def test_invalid_output_and_time_budgets_never_send(self):
        for field,value in [('max_output_tokens',0),('max_output_tokens',1025),('max_output_tokens',True),('timeout',31),('timeout',float('nan')),('timeout',True)]:
            t=Transport();args={'timeout':5,'max_output_tokens':1024,field:value}
            with self.subTest(field=field,value=value),self.assertRaisesRegex(wire.ModelTransportError,'INVALID_MODEL_BUDGET'):
                wire.complete(wire.configuration(ENV),system='JSON',context={},schema=SCHEMA,schema_name='test',environ=ENV,transport=t,**args)
            self.assertEqual(t.requests,[])
    def test_invalid_chat_envelopes_preserve_usage_and_never_retry(self):
        variants=[]
        def variant(change):
            r=chat();change(r);variants.append(r)
        variant(lambda r:r.update(choices=[]))
        variant(lambda r:r['choices'].append(deepcopy(r['choices'][0])))
        variant(lambda r:r['choices'][0].update(finish_reason='length'))
        variant(lambda r:r['choices'][0].update(finish_reason='tool_calls'))
        variant(lambda r:r['choices'][0]['message'].update(tool_calls=[{'name':'capture'}]))
        variant(lambda r:r['choices'][0]['message'].update(function_call={'name':'capture'}))
        variant(lambda r:r['choices'][0]['message'].update(refusal='Cannot answer'))
        variant(lambda r:r['choices'][0]['message'].update(role='user'))
        variant(lambda r:r['choices'][0]['message'].update(content=None,reasoning_content='{"ok":true}'))
        variant(lambda r:r.update(id=None))
        variant(lambda r:r.update(model=None))
        for value in variants:
            t=Transport(value)
            with self.subTest(value=value),self.assertRaises(wire.ModelTransportError) as e:self.complete(t)
            self.assertEqual(len(t.requests),1);self.assertEqual(e.exception.metadata['usage']['total_tokens'],18)
            self.assertEqual(e.exception.metadata['provider'],'modal');self.assertEqual(e.exception.metadata['endpoint_origin'],ENV["MODAL_ALLOWED_ORIGIN"])
    def test_no_json_repair_or_reasoning_extraction(self):
        for content in ['', '```json\n{"ok":true}\n```','<think>reason</think>{"ok":true}','{"ok":true,"ok":false}','{"value":NaN}','[]','{"ok":true} trailing','x'*16001]:
            t=Transport(chat(content))
            with self.subTest(content=content[:30]),self.assertRaises(wire.ModelTransportError):self.complete(t)
            self.assertEqual(len(t.requests),1)
    def test_invalid_reported_usage_is_not_silently_accepted(self):
        for usage in [{'prompt_tokens':True},{'completion_tokens':-1},{'total_tokens':1.5},'usage unavailable']:
            with self.subTest(usage=usage),self.assertRaisesRegex(wire.ModelTransportError,'MALFORMED_MODEL_USAGE'):self.complete(Transport(chat(usage=usage)))
        r=self.complete(Transport(chat(usage={'prompt_tokens':11})))
        self.assertEqual(r['usage'],{'input_tokens':11});self.assertNotIn('total_tokens',r['usage'])
    def test_preparation_time_deducted_and_late_response_retains_actual_usage(self):
        t=Transport()
        with patch.object(wire.time,'monotonic',side_effect=[0.0,1.0,6.0]):
            with self.assertRaises(wire.ModelTransportError) as error:self.complete(t)
        self.assertEqual(error.exception.code,'MODEL_TIMEOUT')
        self.assertEqual(t.requests[0][1],4.0)
        self.assertEqual(error.exception.metadata['usage']['total_tokens'],18)
        self.assertEqual(error.exception.metadata['response_id'],'chatcmpl_synthetic')

    def test_errors_have_destination_provenance_and_no_retry(self):
        for code in [302,401,429,500]:
            def fail(_request,code=code):raise HTTPError('private',code,'do not persist body',{},io.BytesIO(b'private'))
            t=Transport(callback=fail)
            with self.subTest(code=code),self.assertRaises(wire.ModelTransportError) as e:self.complete(t)
            self.assertEqual(e.exception.code,'MODEL_HTTP_'+str(code));self.assertEqual(len(t.requests),1);self.assertEqual(e.exception.metadata['provider'],'modal')
        t=Transport(callback=lambda _:(_ for _ in ()).throw(TimeoutError('private')))
        with self.assertRaisesRegex(wire.ModelTransportError,'MODEL_TIMEOUT'):self.complete(t)
        self.assertEqual(len(t.requests),1)
    def test_http_enforces_response_byte_limit_and_installs_no_redirect_handler(self):
        class Opener:
            def open(self,*args,**kwargs):return io.BytesIO(b'x'*(wire.MAX_RESPONSE_BYTES+1))
        with patch.object(wire,'build_opener',return_value=Opener()) as build:
            with self.assertRaisesRegex(wire.ModelTransportError,'MODEL_RESPONSE_TOO_LARGE'):
                wire._direct_http(None,5)
            handler=build.call_args.args[0]
            self.assertIsInstance(handler,wire._NoRedirects)
            for code in (301,302,303,307,308):self.assertIsNone(handler.redirect_request(None,None,code,None,None,'https://foreign.invalid'))
    def test_secrets_and_emails_removed_from_context_and_returned_metadata(self):
        t=Transport(chat(json.dumps({'note':ENV['MODAL_API_KEY']}),id=ENV['MODAL_API_KEY']))
        r=wire.complete(wire.configuration(ENV),system='JSON',context={'note':ENV['MODAL_API_KEY']+' buyer@example.test','api_key':'do not send'},schema=SCHEMA,schema_name='test',environ=ENV,timeout=5,transport=t)
        self.assertNotIn(ENV['MODAL_API_KEY'],t.requests[0][0].data.decode()+json.dumps(r));self.assertNotIn('buyer@example.test',t.requests[0][0].data.decode());self.assertIn('[REDACTED]',r['plan_text'])

class CallerChatTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.store=Store(Path(tmp.name)/'local.sqlite3');self.run=self.store.create_run('Synthetic local promise',mode='LOCAL_TEST')
        self.env=dict(ENV)
        blocker=patch('socket.create_connection',side_effect=AssertionError('No network in caller tests'));blocker.start();self.addCleanup(blocker.stop)
    def payload(self):return {'run_id':self.run['id'],'request_id':str(uuid.uuid4()),'question':'Completed payments with no tickets'}
    def test_studio_changed_saved_dataset_uses_same_filters_with_chat_transport(self):
        order,capture='TEST_ORDER','TEST_CAPTURE'
        self.store.update_purchase(self.run['purchase_id'],order_id=order)
        self.store.confirm_payment(self.run['purchase_id'],order_id=order,capture_id=capture,amount=2900,currency='USD',completed_at='2026-10-22T10:00:00Z',provider_response={'synthetic':True})
        t=Transport(chat('{"query":"completed_missing_tickets","mode":"LOCAL_TEST"}'))
        query=StudioQuery(self.store,environ=self.env,transport=t)
        before=query.query(self.payload());self.store.fulfill(self.run['purchase_id']);after=query.query(self.payload())
        self.assertEqual((before['count'],after['count']),(1,0));self.assertNotEqual(before['dataset_sha256'],after['dataset_sha256'])
        self.assertEqual(self.store.get_attempts(self.run['id'])[0]['input']['model_configuration']['provider'],'modal')
        self.assertEqual(after['model_mode'],'LOCAL_TEST');self.assertEqual(after['model']['provider'],'modal');self.assertEqual(after['model']['actual'],wire.MODAL_MODEL)
        self.assertEqual(len(t.requests),2);self.assertNotIn('Authorization',dict(t.requests[0][0].header_items()))
    def test_studio_rejected_response_persists_actual_usage_and_source(self):
        value=chat();value['choices'][0]['finish_reason']='length';t=Transport(value)
        with self.assertRaises(StudioQueryError) as e:StudioQuery(self.store,environ=self.env,transport=t).query(self.payload())
        receipt=e.exception.receipt;self.assertEqual(receipt['status'],'FAILED');self.assertEqual(receipt['rows'],[])
        self.assertEqual(receipt['model']['usage']['total_tokens'],18);self.assertEqual(receipt['model']['protocol'],'chat_completions')
        self.assertEqual(self.store.get_attempts(self.run['id'])[0]['result'],receipt)
    def test_studio_cancel_after_chat_response_keeps_usage_without_applying_rows(self):
        t=Transport(chat('{"query":"all","mode":"ANY"}'),callback=lambda _:self.store.update_run(self.run['id'],cancel_requested=1,state='cancelled'))
        with self.assertRaises(StudioQueryError) as e:StudioQuery(self.store,environ=self.env,transport=t).query(self.payload())
        self.assertEqual(e.exception.code,'CANCELLED');self.assertEqual(e.exception.receipt['model']['usage']['total_tokens'],18);self.assertEqual(e.exception.receipt['rows'],[]);self.assertEqual(len(t.requests),1)
    def test_investigator_chat_metadata_persists_on_success_and_rejection(self):
        # The transport is synthetic and the test model explicitly stays LOCAL_TEST.
        plan={'hypothesis':'Insufficient payment evidence.','requested_values':requested_values(),'tool':'finish','arguments':{'run_id':self.run['id'],'fault':None},'findings':[]}
        t=Transport(chat(json.dumps(plan)));model=OpenAIModel(environ=self.env,transport=t)
        result=Investigation(self.store,None,model_factory=lambda:model).run(self.run['id'])
        self.assertEqual(result['model_mode'],'LOCAL_TEST');self.assertEqual(result['final_verdict']['verdict'],'INCONCLUSIVE')
        attempts=[a for a in self.store.get_attempts(self.run['id']) if a['kind']=='investigator.model']
        self.assertEqual(len(attempts),1)
        self.assertEqual(attempts[0]['input']['model_configuration']['provider'],'modal')
        saved=attempts[0]['result'];self.assertEqual(saved['provider'],'modal');self.assertEqual(saved['usage']['total_tokens'],18)
        other=self.store.create_run('Synthetic rejected response',mode='LOCAL_TEST');bad=chat();bad['choices'][0]['finish_reason']='length'
        model=OpenAIModel(environ=self.env,transport=Transport(bad));result=Investigation(self.store,None,model_factory=lambda:model).run(other['id'])
        attempts=[a for a in self.store.get_attempts(other['id']) if a['kind']=='investigator.model']
        self.assertEqual(len(attempts),1)
        self.assertEqual(result['status'],'FAILED');saved=attempts[0]['result'];self.assertEqual(saved['response_id'],'chatcmpl_synthetic');self.assertEqual(saved['endpoint_origin'],ENV["MODAL_ALLOWED_ORIGIN"]);self.assertEqual(saved['usage']['total_tokens'],18)
    def test_plain_injected_investigator_cannot_claim_live_mode_or_receive_credentials(self):
        # Same candidate-1 reproduction: plain OpenAIModel, synthetic finish,
        # LIVE_SANDBOX run and configured synthetic credential.
        for mode in ("LIVE_SANDBOX", "FRESH_SANDBOX", "RECORDED_REPLAY"):
            with self.subTest(mode=mode):
                run=self.store.create_run("Synthetic mode-boundary regression only",mode=mode)
                t=Transport();model=OpenAIModel(environ=self.env,transport=t)
                result=Investigation(self.store,None,model_factory=lambda:model).run(run["id"])
                self.assertEqual(result["status"],"BLOCKED" if mode=="RECORDED_REPLAY" else "FAILED")
                self.assertEqual(result["reason"],"REPLAY_MODEL_NETWORK_FORBIDDEN" if mode=="RECORDED_REPLAY" else "MODEL_PROOF_MODE_MISMATCH")
                self.assertEqual(t.requests,[]);self.assertEqual(self.store.get_attempts(run["id"]),[])
                self.assertEqual(model.evidence_mode,"LOCAL_TEST");self.assertEqual(model.config.key,"")
        t=Transport(chat('{"ok":true}'));model=OpenAIModel(environ=self.env,transport=t)
        response=model.complete({"run_id":self.run["id"]})
        self.assertEqual(response["model_mode"],"LOCAL_TEST")
        self.assertIsNone(t.requests[0][0].get_header("Authorization"))
        # Isolated tests require no authorization flag or credentials at all.
        model=OpenAIModel(environ={},transport=Transport({"id":"synthetic_response","model":"synthetic_model","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"{}"}]}]}))
        self.assertEqual(model.complete({})["model_mode"],"LOCAL_TEST")
    def test_modal_credentials_are_redacted_from_studio_saved_question(self):
        payload=self.payload();payload['question']='Do not repeat '+ENV['MODAL_API_KEY']
        t=Transport(chat('{"query":"unsupported","mode":"ANY"}'));StudioQuery(self.store,environ=self.env,transport=t).query(payload)
        attempt=self.store.get_attempts(self.run['id'])[0]
        self.assertNotIn(ENV['MODAL_API_KEY'],json.dumps(attempt)+t.requests[0][0].data.decode())

if __name__=='__main__':unittest.main(verbosity=2)
