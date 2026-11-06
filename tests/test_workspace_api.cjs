const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../web/app.js'),'utf8');
const api=source.slice(source.indexOf('async function api('),source.indexOf('\nfunction text(',source.indexOf('async function api(')));
const messages=source.slice(source.indexOf('function errorMessage('),source.indexOf('\nfunction showError('));
function request(body,status=200,payload){
 const calls=[];const context=vm.createContext({readableText:x=>x,fetch:async(path,options)=>{calls.push({path,options});return new Response(body,{status});}});
 vm.runInContext(api+'\n'+messages,context);
 return {result:context.api('/api/runs/local-only/order',payload),calls,context};
}
test('valid response retains identity and structured API rejection retains code',async()=>{
 assert.equal((await request('{"id":"local-case"}').result).id,'local-case');
 await assert.rejects(request('{"error":"SCOPED_ACCESS_REQUIRED"}',401).result,{message:'SCOPED_ACCESS_REQUIRED'});
});
for(const [name,body,status] of [['HTML','<html>unavailable</html>',502],['empty','',503],['malformed','{',503],['null','null',200],['array','[]',200],['string','"ok"',200]]){
 test(name+' failed POST is dispatched once with unchanged payload and a readable error',async()=>{
  const payload={purchase:'LOCAL_TEST',request_id:'do-not-repeat'};
  const {result,calls,context}=request(body,status,payload);
  await assert.rejects(result,{message:'HTTP_RESPONSE_UNAVAILABLE'});
  assert.equal(calls.length,1);assert.equal(calls[0].options.method,'POST');
  assert.equal(calls[0].options.body,JSON.stringify(payload));
  assert.match(context.errorMessage('HTTP_RESPONSE_UNAVAILABLE'),/^Connection interrupted\./);
  assert.doesNotMatch(context.errorMessage('HTTP_RESPONSE_UNAVAILABLE'),/payment failed|SyntaxError|Unexpected token/i);
 });
}
test('connection rejection has one dispatch and no invented result',async()=>{
 let calls=0;const context=vm.createContext({fetch:async()=>{calls++;throw new TypeError('Failed to fetch');}});
 vm.runInContext(api,context);await assert.rejects(context.api('/local-only',{}),{message:'Failed to fetch'});assert.equal(calls,1);
});
test('startup rejection reaches the visible login message and connection details',async()=>{
 const nodes=new Map();const $=id=>{if(!nodes.has(id))nodes.set(id,{hidden:id==='workspace',textContent:''});return nodes.get(id);};
 const show=source.slice(source.indexOf('function showError('),source.indexOf('\nlet current'));
 const boot=source.slice(source.lastIndexOf("refresh().then(async"),source.lastIndexOf('\nsetInterval('));
 const context=vm.createContext({$,text:(id,value)=>$(id).textContent=value,readableText:x=>x,refresh:()=>Promise.reject(new Error('HTTP_RESPONSE_UNAVAILABLE'))});
 $('login-panel').hidden=true;vm.runInContext(messages+'\n'+show+'\n'+boot,context);await new Promise(resolve=>setImmediate(resolve));
 assert.equal($('login-panel').hidden,false);assert.match($('login-message').textContent,/Connection interrupted/);assert.equal($('login-error-details').hidden,false);assert.equal($('login-error-code').textContent,'HTTP_RESPONSE_UNAVAILABLE');
});
