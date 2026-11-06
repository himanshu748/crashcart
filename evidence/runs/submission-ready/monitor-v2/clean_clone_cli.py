from pathlib import Path
import http.client,json,os,select,signal,subprocess,sys,tempfile,hashlib
repo=Path('/Users/himanshujha/Documents/ChatGPT/paypal/var/github-publication-v1/repository');out=Path('/Users/himanshujha/Documents/ChatGPT/paypal/evidence/runs/monitor-v2')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
with tempfile.TemporaryDirectory(prefix='crashcart-cli-clone-') as folder:
 clone=Path(folder)/'repository';subprocess.run(['git','clone','--quiet','--no-hardlinks',str(repo),str(clone)],check=True,capture_output=True,timeout=30)
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=clone,text=True).strip()==head
 assert not (clone/'.env').exists()
 env={'PATH':os.environ.get('PATH','/usr/bin:/bin'),'CRASHCART_MONITOR_TOKEN':'local-clean-clone-cli-fixture-only'}
 process=subprocess.Popen([sys.executable,'-m','crashcart.monitor_server','--db',str(Path(folder)/'monitor.sqlite3'),'--port','0'],cwd=clone,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 try:
  ready,_,_=select.select([process.stdout],[],[],5);assert ready,'CLI did not announce startup'
  line=process.stdout.readline().strip();assert line.startswith('CrashCart monitoring: http://127.0.0.1:')
  port=int(line.rsplit(':',1)[1].rstrip('/'));c=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
  c.request('GET','/');response=c.getresponse();html=response.read();assert response.status==200;c.close()
  assert html.index(b'id="message"')<html.index(b'id="workspace"')
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=3);payload=json.dumps({'token':env['CRASHCART_MONITOR_TOKEN']}).encode()
  c.request('POST','/api/login',payload,{'X-CrashCart-Request':'1'});response=c.getresponse();body=json.loads(response.read());assert response.status==200 and body=={'authenticated':True};cookie=response.getheader('Set-Cookie').split(';')[0];c.close()
  c=http.client.HTTPConnection('127.0.0.1',port,timeout=3);c.request('GET','/api/stores',headers={'Cookie':cookie});response=c.getresponse();assert response.status==200 and json.loads(response.read())=={'stores':[]};c.close()
 finally:
  process.send_signal(signal.SIGINT)
  try:stdout,stderr=process.communicate(timeout=5)
  except subprocess.TimeoutExpired:
   process.kill();process.communicate(timeout=5);raise
 assert process.returncode==0,(process.returncode,stderr)
 report={'mode':'LOCAL_TEST','source_commit':head,'command':'Fresh local git clone; python3 -m crashcart.monitor_server --db TEMP/monitor.sqlite3 --port 0','status':'PASS','entry_http':200,'login_http':200,'empty_stores_http':200,'private_env_file':False,'provider_credentials_supplied':False,'provider_calls':0,'process_exit_after_SIGINT':0,'cleanup':'Ownedprocessclosed;temporaryclone/database removed'}
 (out/'clean-clone-cli.log').write_text(json.dumps(report)+'\n'+stderr);report['log_sha256']=hashlib.sha256((out/'clean-clone-cli.log').read_bytes()).hexdigest();(out/'clean-clone-cli.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
