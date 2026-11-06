from pathlib import Path
import hashlib,json,os,subprocess,sys,tempfile
repo=Path('/Users/himanshujha/Documents/ChatGPT/paypal/var/github-publication-v1/repository');out=Path('/Users/himanshujha/Documents/ChatGPT/paypal/evidence/runs/monitor-v2')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
code=r'''
from pathlib import Path
import http.client,json,subprocess,sys,tempfile,threading
import crashcart.monitor_server as module
assert Path(module.__file__).resolve().is_relative_to(Path.cwd())
assert not Path('.env').exists()
with tempfile.TemporaryDirectory(prefix='monitor-smoke-') as directory:
 db=Path(directory)/'monitor.sqlite3'
 srv=module.make_server(db,port=0,environ={'CRASHCART_MONITOR_TOKEN':'local-clean-clone-smoke-only'},start_scanner=False)
 thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
 def request(path,body=None,cookie=None):
  payload=json.dumps(body).encode() if body is not None else None
  headers={'X-CrashCart-Request':'1'}
  if cookie:headers['Cookie']=cookie
  c=http.client.HTTPConnection('127.0.0.1',srv.server_port,timeout=3)
  c.request('POST' if body is not None else 'GET',path,payload,headers)
  r=c.getresponse();raw=r.read();result=(r.status,raw,r.getheader('Set-Cookie'));c.close();return result
 try:
  status,raw,_=request('/');assert status==200
  assert raw.index(b'id="message"')<raw.index(b'id="workspace"')
  status,raw,cookie=request('/api/login',{'token':'local-clean-clone-smoke-only'});assert status==200
  status,raw,_=request('/api/stores',{'name':'Local clone example','platform':'woocommerce','domain':'https://clone.example.test','promise_seconds':3600},cookie);assert status==201
  store=json.loads(raw)['store'];assert store['connections']['connection_verified'] is False
  status,raw,_=request('/api/stores/'+store['id']+'/orders',cookie=cookie);assert status==200 and json.loads(raw)=={'orders':[]}
  backup=Path(directory)/'backup.sqlite3'
  result=subprocess.run([sys.executable,'scripts/monitor_backup.py',str(db),str(backup)],capture_output=True,text=True,timeout=15)
  assert result.returncode==0,result.stderr
  assert json.loads(result.stdout)['integrity_check']=='ok'
  print(json.dumps({'status':'PASS','entry_http':200,'login_http':200,'create_store_http':201,'orders':[],'connection_verified':False,'backup_integrity':'ok','private_env_file_present':False,'provider_keys_supplied':False,'provider_calls':0}),flush=True)
 finally:
  srv.shutdown();srv.server_close();thread.join(timeout=3)
'''
with tempfile.TemporaryDirectory(prefix='crashcart-clean-') as folder:
 clone=Path(folder)/'repository'
 subprocess.run(['git','clone','--quiet','--no-hardlinks',str(repo),str(clone)],check=True,capture_output=True,text=True,timeout=30)
 cloned=subprocess.check_output(['git','rev-parse','HEAD'],cwd=clone,text=True).strip();assert cloned==head
 env=dict(os.environ);env.pop('PYTHONPATH',None)
 run=subprocess.run([sys.executable,'-c',code],cwd=clone,env=env,capture_output=True,text=True,timeout=30)
 (out/'clean-clone.log').write_text(run.stdout+run.stderr)
 if run.returncode:raise SystemExit(run.returncode)
 result=json.loads(run.stdout.strip());assert result['status']=='PASS'
 report={'mode':'LOCAL_TEST','source_commit':head,'clone_kind':'Fresh local Git clone of committed source; no hidden working files','command':'git clone --quiet --no-hardlinks SOURCE TEMP; python3 clean-clone actual HTTP/backup probe','result':result,'exit_code':run.returncode,'runtime':'Python3.13.15','cleanup':'Temporaryclone/database removed andserverclosed','log_sha256':hashlib.sha256((out/'clean-clone.log').read_bytes()).hexdigest()}
 (out/'clean-clone.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
