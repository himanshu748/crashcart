"""Explicitly approved activation, never a provider test or allowance reset."""
from pathlib import Path
import fcntl, hashlib, json, os, shutil, signal, stat, subprocess, time

ROOT=Path('__STAGING__')
SOURCE=Path('/opt/crashcart/live-e48cf18')
STATE=Path('/srv/crashcart-live')
HOST='workspace-crashcart.52.202.25.181.sslip.io'
IMAGE='sha256:eccdbb083c5a87227e8d0be9ff9a78fc975765426c68abfbe877f94ce0fe1608'
TAG='e48cf18'
CONFIG=Path('/opt/embodiweave/source/deploy/Caddyfile')
INSIDE='/etc/caddy/Caddyfile'
proof={'source_commit':'e48cf18f27aee961c16c103cddba55361eccdd5b','phase':'preflight','result':'FAIL','provider_calls':0}
old=None; candidate=None; candidate_at_path=None; before=None; written=False; activated=False; install_attempted=False

def run(args, data=None, timeout=40, label='command'):
    r=subprocess.run(args,input=data,capture_output=True,timeout=timeout)
    (ROOT/(label+'.out')).write_bytes(r.stdout)
    (ROOT/(label+'.err')).write_bytes(r.stderr)
    if r.returncode: raise RuntimeError(label+' failed with exit '+str(r.returncode))
    return r.stdout

def sha(data): return hashlib.sha256(data).hexdigest()
def inspect(name): return json.loads(run(['docker','inspect',name],label='inspect-'+name))[0]
def proxy():
    x=inspect('ew-proxy')
    return {'id':x['Id'],'image':x['Image'],'started':x['State']['StartedAt'],'restarts':x['RestartCount'],
            'networks':x['NetworkSettings']['Networks'],'mounts':x['Mounts']}
def container_config(): return run(['docker','exec','ew-proxy','cat',INSIDE],label='container-config')
def active_config():
    return json.loads(run(['docker','exec','ew-proxy','wget','-qO-','http://127.0.0.1:2019/config/'],label='active-caddy'))
def without_new_host(value):
    value=json.loads(json.dumps(value));removed=[]
    def visit(node):
        if isinstance(node,dict):
            for key,item in list(node.items()):
                if key=='routes' and isinstance(item,list):
                    kept=[]
                    for route in item:
                        matches=route.get('match',[]) if isinstance(route,dict) else []
                        hosts=[h for m in matches for h in m.get('host',[])]
                        if HOST in hosts:
                            assert hosts==[HOST],'New host unexpectedly shares an old matcher'
                            removed.append(route)
                        else:kept.append(route)
                    node[key]=kept
                visit(node[key])
        elif isinstance(node,list):
            for item in node:visit(item)
    visit(value);assert len(removed)==1,'Expected exactly one added hostname route'
    return value
def routes(adapted):
    hosts=set()
    def visit(value):
        if isinstance(value,dict):
            if isinstance(value.get('host'),list): hosts.update(value['host'])
            for v in value.values(): visit(v)
        elif isinstance(value,list):
            for v in value: visit(v)
    visit(adapted)
    return sorted(h for h in hosts if '*' not in h)
def route_check(host):
    r=subprocess.run(['curl','--silent','--show-error','--max-time','12','--resolve',host+':443:127.0.0.1',
                      '--write-out','\n%{http_code}', 'https://'+host+'/'],capture_output=True,timeout=15)
    if r.returncode: raise RuntimeError('Existing route TLS/read failed')
    body,code=r.stdout.rsplit(b'\n',1)
    return {'status':int(code),'body_sha256':sha(body)}
def compose(*args):
    return run(['docker','compose','-f',str(SOURCE/'deploy/live/compose.yaml'),*args],timeout=90,label='compose-'+args[0])
def write_new(path, data, uid=0):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:
        f.write(data);f.flush();os.fsync(f.fileno());os.fchown(f.fileno(),uid,uid)

def restore_original():
    # Hold the checked original inode through the entire rollback. Never open a
    # substituted pathname for writing or overwrite another operator's content.
    fd=os.open(CONFIG,os.O_RDWR|os.O_NOFOLLOW)
    with os.fdopen(fd,'r+b') as f:
        fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        actual=os.fstat(f.fileno())
        assert stat.S_ISREG(actual.st_mode) and actual.st_nlink==1
        assert (actual.st_dev,actual.st_ino)==config_inode
        current=CONFIG.lstat();assert (current.st_dev,current.st_ino)==config_inode
        assert f.read()==candidate,'Concurrent Caddy bytes; do not overwrite'
        current_active=active_config()
        assert current_active==old_active or (candidate_at_path is not None and current_active==candidate_at_path),'Another active configuration appeared; do not reload over it'
        run(['docker','exec','-i','ew-proxy','caddy','validate','--config','-','--adapter','caddyfile'],old,label='rollback-validate')
        current=CONFIG.lstat();assert (current.st_dev,current.st_ino)==config_inode
        f.seek(0);assert f.read()==candidate,'Concurrent Caddy bytes after validation'
        f.seek(0);f.write(old);f.truncate();f.flush();os.fsync(f.fileno())
        current=CONFIG.lstat()
        if (current.st_dev,current.st_ino)!=config_inode:
            # Restore this still-open old inode only; leave replacement alone.
            f.seek(0);f.write(candidate);f.truncate();f.flush();os.fsync(f.fileno())
            raise RuntimeError('Caddy pathname replaced during rollback')
        f.seek(0);assert f.read()==old
        assert container_config()==old
        run(['docker','exec','ew-proxy','caddy','validate','--config',INSIDE,'--adapter','caddyfile'],label='rollback-installed-validate')
        current=CONFIG.lstat();assert (current.st_dev,current.st_ino)==config_inode and CONFIG.read_bytes()==old
        assert container_config()==old
        current_active=active_config()
        assert current_active==old_active or (candidate_at_path is not None and current_active==candidate_at_path),'Active config changed during rollback; do not reload'
        run(['docker','exec','ew-proxy','caddy','reload','--config',INSIDE,'--adapter','caddyfile'],label='rollback-reload')
        assert active_config()==old_active

try:
    os.umask(0o077)
    write_new(ROOT/'activation.pid',str(os.getpid()).encode())
    def interrupted(*_):raise RuntimeError('Activation interrupted; guarded rollback follows')
    for sig in (signal.SIGTERM,signal.SIGHUP,signal.SIGINT):signal.signal(sig,interrupted)
    mem=int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))
    assert mem>=786432,'Less than 768MiB currently available'
    assert shutil.disk_usage('/').free>=2*1024**3,'Insufficient current disk'
    assert not STATE.exists() and not SOURCE.exists(),'Existing state/source: inspect, never overwrite'
    assert not run(['docker','ps','-aq','--filter','label=com.docker.compose.project=crashcart-live'],label='project-collision').strip(),'Existing Compose project: inspect, never modify'
    before=proxy()
    assert 'embodiweave-net' in before['networks']
    assert any(m['Source']==str(CONFIG) and m['Destination']==INSIDE for m in before['mounts'])
    info=CONFIG.lstat();assert stat.S_ISREG(info.st_mode) and info.st_nlink==1
    old=CONFIG.read_bytes();assert container_config()==old
    assert HOST.encode() not in old,'Hostname already configured'
    config_inode=(info.st_dev,info.st_ino)
    old_adapt=json.loads(run(['docker','exec','ew-proxy','caddy','adapt','--config',INSIDE,'--adapter','caddyfile'],label='adapt-before'))
    old_active=active_config();assert old_active==old_adapt,'Active configuration differs from mounted source; preserve pending edits and stop'
    old_stdin=json.loads(run(['docker','exec','-i','ew-proxy','caddy','adapt','--config','-','--adapter','caddyfile'],old,label='adapt-before-stdin'))
    hosts=routes(old_adapt);assert len(hosts)>=6
    prior={h:route_check(h) for h in hosts}
    stable={h:prior[h]==route_check(h) for h in hosts}
    proof.update(memory_available_before_kib=mem,original_config_sha256=sha(old),existing_routes_before=prior,
                 stable_route_bodies_before=stable,original_proxy_id=before['id'])
    fragment=(ROOT/'source/deploy/live/Caddyfile.fragment').read_bytes()
    candidate=old+b'\n'+fragment
    candidate_adapt=json.loads(run(['docker','exec','-i','ew-proxy','caddy','adapt','--config','-','--adapter','caddyfile'],candidate,label='adapt-combined'))
    assert without_new_host(candidate_adapt)==old_stdin,'Candidate changes original routes/settings in equal adaptation context'
    run(['docker','exec','-i','ew-proxy','caddy','validate','--config','-','--adapter','caddyfile'],candidate,label='validate-combined')
    assert CONFIG.read_bytes()==old and proxy()==before
    proof['combined_config_validated']=True
    image=inspect(IMAGE);assert image['Config']['User']=='10001:10001'
    assert not any(any(n in v.split('=',1)[0] for n in ('KEY','SECRET','TOKEN','CLIENT_ID')) for v in image['Config']['Env'])
    hashes=json.loads((ROOT/'image-files.json').read_text())
    image_script='import pathlib,hashlib,json; files='+repr(hashes)+'; assert all(hashlib.sha256((pathlib.Path("/app")/p).read_bytes()).hexdigest()==h for p,h in files.items()); print(json.dumps({"files":len(files),"match":True}))'
    match=json.loads(run(['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                         '--memory','96m','--pids-limit','32','--entrypoint','python',IMAGE,'-c',image_script],label='image-source-match'))
    assert match['match'];proof['image_source_match']=match
    proof['phase']='private-staging'
    SOURCE.mkdir(mode=0o755)
    shutil.copytree(ROOT/'source',SOURCE,dirs_exist_ok=True)
    for p in (STATE,STATE/'state',STATE/'state/model-allowance',STATE/'private'):
        p.mkdir(mode=0o700);os.chown(p,10001,10001)
    credential=(ROOT/'runtime.env').read_bytes()
    names={line.split(b'=',1)[0].decode() for line in credential.splitlines()}
    expected={'CRASHCART_OPERATOR_TOKEN','PAYPAL_CLIENT_ID','PAYPAL_CLIENT_SECRET','CRASHCART_PUBLIC_URL','CRASHCART_MODEL_PROVIDER',
              'MODAL_API_KEY','MODAL_MODEL','MODAL_BASE_URL','MODAL_ALLOWED_ORIGIN','CRASHCART_MODEL_ALLOWANCE_PATH',
              'CRASHCART_ALLOW_SANDBOX','CRASHCART_ALLOW_MODEL','CRASHCART_ALLOW_KERNEL','CRASHCART_ALLOW_PROCESS_INTERRUPT',
              'CRASHCART_EVALUATION_MODE','CRASHCART_LIVE_WINDOW_EXPIRES_AT'}
    assert names==expected
    ledger=json.loads((ROOT/'supplemental-allowance.json').read_text())
    assert ledger['calls']==[] and ledger['call_limit']==24 and ledger['ceiling_micro_usd']==1000000
    assert ledger['authorization']=='call_eaefd62313d04135beb2e31b35b867ae'
    write_new(STATE/'private/runtime.env',credential,10001)
    write_new(STATE/'state/model-allowance/allowance.json',(ROOT/'supplemental-allowance.json').read_bytes(),10001)
    write_new(STATE/'private/authorization.json',(ROOT/'authorization.json').read_bytes())
    os.environ.update(CRASHCART_LIVE_TAG=TAG,CRASHCART_PYTHON_IMAGE='python@sha256:e48f59cdba69a3cbd9ed2cf0f348d90d45a8d350d98134cf1070bc106ee9ed90',
        CRASHCART_PROXY_NETWORK='embodiweave-net',CRASHCART_LIVE_STATE_DIR=str(STATE/'state'),CRASHCART_LIVE_CREDENTIAL_FILE=str(STATE/'private/runtime.env'))
    # Explicit nonsecret compose settings make later stop/readback reproducible.
    write_new(SOURCE/'.env', ''.join(k+'='+os.environ[k]+'\n' for k in ('CRASHCART_LIVE_TAG','CRASHCART_PYTHON_IMAGE','CRASHCART_PROXY_NETWORK','CRASHCART_LIVE_STATE_DIR','CRASHCART_LIVE_CREDENTIAL_FILE')).encode())
    run(['docker','tag',IMAGE,'crashcart-live:'+TAG],label='tag-reviewed-image')
    compose('config','--quiet')
    compose('up','-d','--no-build','--pull','never')
    proof['phase']='private-health'
    containers=[inspect(n) for n in ('crashcart-live-api-1','crashcart-live-worker-1')]
    for c in containers:
        assert c['Image']==IMAGE and c['Config']['User']=='10001:10001'
        assert c['HostConfig']['ReadonlyRootfs'] and c['HostConfig']['Memory']==201326592
        assert c['HostConfig']['MemorySwap']==201326592 and c['HostConfig']['OomScoreAdj']==500
        assert c['HostConfig']['NanoCpus']==(150000000 if c['Name'].endswith('api-1') else 200000000)
        assert 'no-new-privileges:true' in c['HostConfig']['SecurityOpt']
        assert c['HostConfig']['PidsLimit']==64 and c['HostConfig']['CapDrop']==['ALL']
        assert not c['HostConfig']['PortBindings'] and not c['State']['OOMKilled']
        assert set(c['NetworkSettings']['Networks'])=={'embodiweave-net'}
    healthcode='import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8765/healthz",timeout=2).status)'
    # Only local health gets a short bounded startup retry; no provider call.
    health=False
    for _ in range(10):
        r=subprocess.run(['docker','exec','crashcart-live-api-1','python','-c',healthcode],capture_output=True,timeout=4)
        if r.returncode==0 and r.stdout.strip()==b'200':health=True;break
        time.sleep(1)
    assert health,'Private API failed startup health'
    processes=run(['docker','top','crashcart-live-worker-1','-eo','pid,args'],label='worker-processes')
    assert b'--role reconcile' in processes and b'--role investigate' in processes
    assert proxy()==before and CONFIG.read_bytes()==old and container_config()==old and active_config()==old_active
    # No provider dispatch has happened during activation.
    assert json.loads((STATE/'state/model-allowance/allowance.json').read_text())['calls']==[]
    proof['phase']='install-route'
    pending=ROOT/'combined.Caddyfile';write_new(pending,candidate)
    backup=CONFIG.with_name(CONFIG.name+'.before-crashcart-live-e48cf18')
    install_attempted=True
    run(['python3',str(SOURCE/'deploy/live/install_caddy.py'),str(CONFIG),str(pending),sha(old),sha(candidate),str(backup)],label='install-caddy')
    written=True
    assert CONFIG.read_bytes()==candidate and container_config()==candidate
    now=CONFIG.stat();assert (now.st_dev,now.st_ino)==config_inode
    assert proxy()==before
    run(['docker','exec','ew-proxy','caddy','validate','--config',INSIDE,'--adapter','caddyfile'],label='validate-installed')
    candidate_at_path=json.loads(run(['docker','exec','ew-proxy','caddy','adapt','--config',INSIDE,'--adapter','caddyfile'],label='adapt-installed'))
    assert without_new_host(candidate_at_path)==old_active,'Mounted candidate changes original active routes/settings'
    assert active_config()==old_active and CONFIG.read_bytes()==candidate and container_config()==candidate
    run(['docker','exec','ew-proxy','caddy','reload','--config',INSIDE,'--adapter','caddyfile'],label='reload-caddy')
    activated=True
    assert proxy()==before
    active_after=active_config();assert active_after==candidate_at_path and without_new_host(active_after)==old_active
    after={h:route_check(h) for h in hosts}
    for h in hosts:
        assert after[h]['status']==prior[h]['status'],'Existing route status changed'
        if stable[h]:assert after[h]['body_sha256']==prior[h]['body_sha256'],'Previously stable route body changed'
    proof.update(result='PASS',phase='activated',image_id=IMAGE,hostname=HOST,config_sha256=sha(candidate),same_config_inode=True,
                 proxy_identity_start_networks_mounts_unchanged=True,existing_routes_after=after,existing_routes_preserved=True,
                 private_credential_names=sorted(names),supplemental_ledger_calls=0,cases_created=0,public_live_route_activated=True,
                 old_active_config_sha256=sha(json.dumps(old_active,sort_keys=True).encode()),all_original_active_routes_settings_preserved=True,
                 trusted_public_https='NOT_YET_VERIFIED',provider_journey='NOT_YET_VERIFIED',backup=str(backup))
except BaseException as exc:
    proof.update(error=type(exc).__name__,message=str(exc),public_live_route_activated=activated)
    config_safe=not install_attempted
    if install_attempted and old is not None:
        try:
            current=CONFIG.lstat()
            assert (current.st_dev,current.st_ino)==config_inode,'Config pathname changed; require manual inspection'
            host_bytes=CONFIG.read_bytes();mounted_bytes=container_config()
            if host_bytes==old and mounted_bytes==old and active_config()==old_active:
                proof['config_confirmed_original_after_attempt']=True;activated=False;config_safe=True
            elif host_bytes==candidate and mounted_bytes==candidate:
                restore_original()
                proof['rollback_original_routes']=True;activated=False;config_safe=True
            else:
                raise RuntimeError('Partial or unknown config bytes; retain evidence for manual recovery')
        except BaseException as rollback:
            proof['rollback_error']=type(rollback).__name__
            proof['retain_staging_for_manual_recovery']=True
    if not activated and SOURCE.exists() and config_safe:
        try:compose('stop');proof['new_containers_stopped']=True
        except BaseException:proof['new_containers_stopped']=False
finally:
    (ROOT/'activation-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    write_new(ROOT/'activation-completed',b'proof written; no subsequent staging writes\n')
    print(json.dumps(proof),flush=True)
