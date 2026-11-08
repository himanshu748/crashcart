"""Private disposable LOCAL_TEST fixture; no real provider calls."""
from pathlib import Path
import json,os,socket,sys,tempfile,threading,time
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from crashcart.server import Handler
from crashcart.store import Store
from crashcart.worker import work,investigation_job
from crashcart.investigator import Investigation as RealInvestigation
from tests.test_investigator import LocalModel,LocalProvider,LocalService,plan
control=Path(sys.argv[1]).resolve();control.mkdir(parents=True,exist_ok=True)
os.environ.clear();os.environ.update(PATH=os.defpath,CRASHCART_OPERATOR_TOKEN='local-test-only-background-preview',CRASHCART_ALLOW_MODEL='0',CRASHCART_ALLOW_SANDBOX='0',CRASHCART_ALLOW_KERNEL='0')
original=socket.socket.connect
external=[]
def loopback(sock,address):
 if not isinstance(address,tuple) or address[0]!='127.0.0.1':external.append('blocked');raise AssertionError('No external network permitted')
 return original(sock,address)
with tempfile.TemporaryDirectory(prefix='crashcart-background-preview-') as folder,patch.object(socket.socket,'connect',loopback):
 db=Path(folder)/'state.db';store=Store(db);run=store.create_run('Example: a paid workshop ticket is missing',mode='LOCAL_TEST')
 store.update_purchase(run['purchase_id'],order_id='LOCALORDER')
 provider=LocalProvider(run['purchase_id'])
 model=None
 def strategy(context):return plan(context,['read_provider','read_merchant','finish'][min(model.calls-1,2)])
 model=LocalModel(strategy)
 def investigation(current_store,_service):return RealInvestigation(current_store,LocalService(provider),model_factory=lambda:model)
 server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.store=store
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 (control/'ready.json').write_text(json.dumps({'url':f'http://127.0.0.1:{server.server_port}/?run='+run['id'],'run':run['id'],'mode':'LOCAL_TEST'}))
 print((control/'ready.json').read_text(),flush=True)
 started=time.monotonic()
 try:
  while not (control/'stop').exists() and time.monotonic()-started<900:
   if (control/'run-once').exists():
    (control/'run-once').unlink()
    with patch('crashcart.investigator.Investigation',side_effect=investigation):work(db,once=True)
    (control/'worker-result.json').write_text(json.dumps({'job':investigation_job(store,run['id']),'model_calls':model.calls,'provider_calls':provider.calls,'external_attempts':external,'purchase':store.purchase_for_run(run['id'])},indent=2))
   time.sleep(.1)
 finally:server.shutdown();server.server_close();thread.join(5)
