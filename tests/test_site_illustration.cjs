/* The marketing illustration must agree with the actual fixed delivery rule. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {spawnSync}=require('node:child_process');
const root=path.resolve(__dirname,'..');
const source=fs.readFileSync(path.join(root,'web/judge/site.js'),'utf8');
const start=source.indexOf('  function stateAt('),end=source.indexOf('  function copyFor(',start);
assert.ok(start>=0&&end>start,'The delivered illustration must expose its actual pure rule function to this test');
const stateAt=vm.runInNewContext('const DEADLINE=60;'+source.slice(start,end)+';stateAt');
const cases=[
 {name:'missing at59',tickets:[],time:59}, {name:'missing at60',tickets:[],time:60},
 {name:'missing at61',tickets:[],time:61}, {name:'delivered at8 observed at8',tickets:[8],time:8},
 {name:'delivered at8 observed at20',tickets:[8],time:20}, {name:'delivered at60',tickets:[60],time:60},
 {name:'late ticket still pending at60',tickets:[61],time:60}, {name:'late ticket at61',tickets:[61],time:61},
 {name:'late at75',tickets:[75],time:90}, {name:'duplicate not issued yet',tickets:[8,11],time:8},
 {name:'duplicate at11',tickets:[8,11],time:11}, {name:'duplicate at90',tickets:[8,11],time:90},
];
const program=`import json,sys\nfrom datetime import datetime,timedelta,timezone\nfrom crashcart.invariant import evaluate\nbase=datetime(2026,11,1,tzinfo=timezone.utc)\ndef stamp(s):return (base+timedelta(seconds=s)).isoformat()\nout=[]\nfor case in json.load(sys.stdin):\n issued=[t for t in case['tickets'] if t<=case['time']]\n provider={'confirmed':True,'status':'COMPLETED','amount':2900,'currency':'USD','run_id':'illustration-run','purchase_id':'illustration-purchase','order_id':'illustration-order','capture_id':'illustration-capture','capture_completed_at':stamp(0),'observed_at':stamp(case['time'])}\n merchant={'known':True,'run_id':'illustration-run','purchase_id':'illustration-purchase','order_id':'illustration-order','ticket_count':len(issued),'tickets':[{'id':'ticket-'+str(i),'purchase_id':'illustration-purchase','created_at':stamp(t)} for i,t in enumerate(issued)],'observed_at':stamp(case['time'])}\n result=evaluate(provider,merchant,stamp(case['time']))\n state='kept' if result['verdict']=='PASS' else 'waiting' if result['verdict']=='INCONCLUSIVE' else 'late' if len(issued)==1 and issued[0]>60 else 'broken'\n out.append({'state':state,'verdict':result['verdict'],'signature':result['signature']})\nprint(json.dumps(out))`;
const run=spawnSync(process.env.CRASHCART_TEST_PYTHON||'python3',['-c',program],{cwd:root,input:JSON.stringify(cases),encoding:'utf8',timeout:15000,env:{PATH:process.env.PATH,PYTHONPATH:root,PYTHONDONTWRITEBYTECODE:'1'}});
assert.equal(run.status,0,run.error?.message||run.stderr);
const expected=JSON.parse(run.stdout);
for(const [i,example] of cases.entries())test('illustration agrees with checker: '+example.name,()=>{
 const before=JSON.stringify(example);
 assert.equal(stateAt(example,example.time),expected[i].state,expected[i].signature);
 assert.equal(JSON.stringify(example),before,'Illustration must not mutate the supplied ticket record');
});
