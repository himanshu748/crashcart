from pathlib import Path
import base64,hashlib,hmac,http.client,json,socket,sys,threading,time
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
repo=Path('/Users/himanshujha/Documents/ChatGPT/paypal/var/github-publication-v1/repository');sys.path.insert(0,str(repo))
from crashcart.monitor_store import MonitorStore
from crashcart.monitor_server import make_server,_prefix
from crashcart.monitor_connectors import parse_woocommerce
out=Path('/Users/himanshujha/Documents/ChatGPT/paypal/evidence/runs/monitor-v2/browser');out.mkdir(parents=True,exist_ok=True)
db=out/'synthetic.sqlite3'
if db.exists():raise SystemExit('Preserving existing proof database; refusing overwrite')
domain=MonitorStore(db);a=domain.create_store('Example shop · local verification','woocommerce','https://safeguard.example.test',60);b=domain.create_store('Example Shopify · local verification','shopify','https://safeguard.myshopify.com',60)
now=datetime.now(timezone.utc).replace(microsecond=0);paid=(now-timedelta(minutes=2)).isoformat()
raw=json.dumps({'id':101,'number':'EXAMPLE-101','currency':'USD','total':'29.00','status':'processing','date_modified_gmt':now.strftime('%Y-%m-%dT%H:%M:%S'),'date_completed_gmt':None,'transaction_id':'LOCAL_CAPTURE'}).encode()
fixture_key='local-webhook-safeguard-fixture-only';headers={'X-WC-Webhook-Source':'https://safeguard.example.test','X-WC-Webhook-Topic':'order.updated','X-WC-Webhook-Delivery-ID':'local-0','X-WC-Webhook-Signature':base64.b64encode(hmac.new(fixture_key.encode(),raw,hashlib.sha256).digest()).decode()}
u=asdict(parse_woocommerce(raw,headers,fixture_key,'https://safeguard.example.test'));u['payment_references']=list(u['payment_references']);keys=['display_number','currency','total_minor','payment_references','fulfillment_status','fulfilled_at','updated_at','event_id']
for i in range(32):
 u['event_id']='local-'+str(i);domain.upsert_order(a['id'],u['platform_order_id'],**{k:u[k] for k in keys})
domain.record_payment(a['id'],capture_id='LOCAL_CAPTURE',reference='LOCAL_CAPTURE',currency='USD',amount_minor=2900,completed_at=paid,event_id='local-payment');domain.scan(now.isoformat())
server=make_server(db,port=0,environ={'CRASHCART_MONITOR_TOKEN':'local-safeguards-browser-access-only',_prefix(a['id'])+'WOOCOMMERCE_SECRET':fixture_key})
t=threading.Thread(target=server.serve_forever,daemon=True);t.start();port=server.server_port
headers['X-WC-Webhook-Delivery-ID']='local-32'
c=http.client.HTTPConnection('127.0.0.1',port,timeout=3);c.request('POST','/webhooks/'+a['id']+'/woocommerce',raw,headers);r=c.getresponse();response={'status':r.status,'body':json.loads(r.read()),'retry_after':r.getheader('Retry-After')};c.close()
(out/'receipt-capacity.json').write_text(json.dumps({'mode':'LOCAL_TEST; locally signed fixture, direct synthetic PayPal facts, zero provider calls','response':response,'orders':len(domain.orders(a['id'])),'alerts':len(domain.alerts(a['id']))},indent=2))
files=['crashcart/monitor_store.py','crashcart/monitor_server.py','crashcart/monitor_ingress.py','crashcart/monitor_connectors.py','scripts/monitor_backup.py','web/monitor/app.js','web/monitor/index.html','web/monitor/style.css']
(out/'server.json').write_text(json.dumps({'url':f'http://127.0.0.1:{port}','mode':'LOCAL_TEST','source_sha256':{f:hashlib.sha256((repo/f).read_bytes()).hexdigest() for f in files}},indent=2));print(f'http://127.0.0.1:{port}',flush=True)
sockets=[];triggered=False
try:
 while not (out/'stop').exists():
  if (out/'saturate').exists() and not triggered:
   triggered=True
   for i in range(server.ingress_limits.max_handlers):
    s=socket.create_connection(('127.0.0.1',port),timeout=1);s.sendall(f'POST /api/login HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nContent-Length: 10000\r\n\r\n'.encode());sockets.append(s)
   end=time.monotonic()+1
   while server.active_handlers<server.ingress_limits.max_handlers and time.monotonic()<end:time.sleep(.005)
   (out/'saturated.json').write_text(json.dumps({'active':server.active_handlers,'peak':server.peak_handlers,'limit':server.ingress_limits.max_handlers}))
  if (out/'release').exists():
   for s in sockets:s.close()
   sockets=[]
  time.sleep(.02)
finally:
 for s in sockets:s.close()
 server.shutdown();server.server_close();t.join(timeout=3)
 (out/'cleanup.json').write_text(json.dumps({'server_closed':True,'peak_handlers':server.peak_handlers,'handler_limit':server.ingress_limits.max_handlers,'provider_calls':0}))
