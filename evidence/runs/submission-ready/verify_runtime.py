import hashlib,json,subprocess,sys,tempfile,urllib.request,zipfile,io
from pathlib import Path
root=Path.cwd()
out=root.parent/"results"
r={"source_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),"initial_git_status":(out/"initial-status.txt").read_text(),"python":sys.version,"node":subprocess.check_output(["node","--version"],text=True).strip(),"mode":"RECORDED_REPLAY","network_to_providers":False,"cases":[]}
for name,variant,wanted in [("early-response-loss-input.json","defective",1),("early-response-loss-input.json","healthy",0),("response-loss-input.json","healthy",1)]:
    command=[sys.executable,"-m","crashcart.replay","run","evidence/runs/paypal-live/"+name,"--merchant",variant]
    p=subprocess.run(command,text=True,capture_output=True)
    assert p.returncode==wanted,(command,p.stderr)
    data=json.loads(p.stdout)
    r["cases"].append({"command":command[1:],"exit_code":p.returncode,"result":data})
response=urllib.request.urlopen("http://127.0.0.1:8911/data.json")
data=json.load(response)
assert data["computed_when"]=="app launch" and data["network_calls"]==0
assert data["cases"]["defective"]["receipt"]["signature"]=="paid_without_ticket"
assert data["cases"]["healthy"]["receipt"]["signature"]=="ticket_delivered_once_on_time"
r["http"]={"status":response.status,"computed_when":data["computed_when"],"mode":data["mode"],"network_calls":data["network_calls"],"fresh_execution":data["fresh_execution"]}
raw=urllib.request.urlopen("http://127.0.0.1:8911/downloads/replay.zip").read()
with tempfile.TemporaryDirectory(prefix="submission61-export-") as temp:
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        z.extractall(temp)
    r["downloaded_zip"]={"sha256":hashlib.sha256(raw).hexdigest(),"executions":[]}
    for variant,expected in [("defective",1),("healthy",0)]:
        p=subprocess.run([sys.executable,"-m","crashcart.replay","run","input.json","--merchant",variant],cwd=temp,text=True,capture_output=True)
        assert p.returncode==expected,p.stderr
        result=json.loads(p.stdout)
        r["downloaded_zip"]["executions"].append({"variant":variant,"exit_code":p.returncode,"verdict":result["verdict"],"signature":result["signature"]})
r["result"]="PASS"
(out/"runtime-result.json").write_text(json.dumps(r,indent=2)+"\n")
print(json.dumps({"result":r["result"],"http":r["http"],"downloaded_zip":r["downloaded_zip"]},indent=2))
