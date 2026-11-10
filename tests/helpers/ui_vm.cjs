/* Delivered-script VM harness. Synthetic DOM/transport only; no browser proof. */
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ROOT=path.resolve(__dirname,'../..');
function environment(file,{fetch:fetcher,url='http://localhost/',mobile=false,storage}={}){
 const nodes=new Map(),all=[],queries=new Map(),calls=[],assigned=[];let document;
 class Element{
  constructor(tag='div'){this.tagName=tag;this.children=[];this.parentElement=null;this.dataset={};this.attributes={};this.handlers={};this.hidden=false;this.disabled=false;this.checked=false;this.open=false;this.value='';this._text='';const set=new Set();this.classList={add:(...x)=>x.forEach(v=>set.add(v)),remove:(...x)=>x.forEach(v=>set.delete(v)),contains:x=>set.has(x),toggle:(x,on)=>{on=on===undefined?!set.has(x):on;if(on)set.add(x);else set.delete(x);return on;}};all.push(this);}
  set id(value){this._id=value;nodes.set(value,this);}get id(){return this._id;}
  set className(value){this._className=value;for(const x of value.split(/\s+/))if(x)this.classList.add(x);}get className(){return this._className||'';}
  set textContent(value){this._text=String(value??'');this.children=[];}get textContent(){return this._text+this.children.map(x=>x.textContent).join('');}
  append(...items){for(const x of items){if(x.parentElement)x.remove();this.children.push(x);x.parentElement=this;}}
  replaceChildren(...items){for(const x of this.children)x.parentElement=null;this.children=[];this._text='';this.append(...items);}
  insertBefore(item,before){if(item.parentElement)item.remove();let i=this.children.indexOf(before);if(i<0)i=this.children.length;this.children.splice(i,0,item);item.parentElement=this;}
  before(item){if(this.parentElement)this.parentElement.insertBefore(item,this);}
  remove(){if(this.parentElement){const a=this.parentElement.children;a.splice(a.indexOf(this),1);this.parentElement=null;}}
  setAttribute(name,value){this.attributes[name]=String(value);if(name==='class')this.className=String(value);if(name==='href')this.href=String(value);if(name==='open')this.open=true;}
  getAttribute(name){return this.attributes[name]??null;}
  removeAttribute(name){delete this.attributes[name];if(name==='open')this.open=false;}
  toggleAttribute(name,on){if(on)this.setAttribute(name,'');else this.removeAttribute(name);}
  addEventListener(type,fn){(this.handlers[type]??=[]).push(fn);}
  async trigger(type,extra={}){for(const fn of this.handlers[type]||[])await fn({preventDefault(){},currentTarget:this,target:this,...extra});}
  focus(options){this.focusOptions=options;document.activeElement=this;}scrollIntoView(options){this.scrollOptions=options;}pause(){}load(){}
  showModal(){this.open=true;}close(){this.open=false;for(const fn of this.handlers.close||[])fn({target:this});}
  matches(selector){return selector.startsWith('.')&&this.classList.contains(selector.slice(1));}
  walk(){return this.children.flatMap(x=>[x,...x.walk()]);}
  querySelector(selector){if(selector==='time')return this.walk().find(x=>x.tagName==='time')||null;if(selector==='[data-case]')return this.caseButton||null;const key='local:'+this.id+':'+selector;if(!queries.has(key))queries.set(key,new Element());return queries.get(key);}
  querySelectorAll(selector){if(selector===':scope > .event')return this.children.filter(x=>x.classList.contains('event'));return [];}
 }
 const html=fs.readFileSync(path.join(ROOT,(file==='web/judge/app.js'?'web/judge/demo.html':file.replace(/app\.js$/,'index.html'))),'utf8');
 for(const match of html.matchAll(/<([\w-]+)\b([^>]*\bid="([^"]+)"[^>]*)>/g)){
  const e=new Element(match[1]);e.id=match[3];e.hidden=/\bhidden(?:\s|$|=)/.test(match[2]);e.disabled=/\bdisabled(?:\s|$|=)/.test(match[2]);e.value=/\bvalue="([^"]*)"/.exec(match[2])?.[1]||'';e.className=/\bclass="([^"]*)"/.exec(match[2])?.[1]||'';
 }
 const sources=['all','browser','provider','merchant'].map(source=>{const e=new Element('button');e.dataset.source=source;return e;});
 const stories=['payment','delivery','repair'].map(story=>{const e=new Element('button');e.dataset.story=story;return e;});
 const cases=['defective','healthy'].map(which=>{const e=new Element('button');e.dataset.case=which;return e;});
 const failureAi=[0,1,2].map(i=>{const e=new Element();e.dataset.failureStep=String(i);return e;});
 const ai=[0,1,2].map(i=>{const e=new Element('button');e.dataset.aiStep=String(i);return e;});const links=[new Element('a'),new Element('a')];links.forEach(x=>x.href='#investigation');
 const location=new URL(url);location.assign=value=>assigned.push(value);
 document={hidden:false,activeElement:null,body:new Element('body'),documentElement:new Element('html'),getElementById:id=>nodes.get(id)||null,
  createElement:tag=>new Element(tag),createTextNode:value=>{const e=new Element('#text');e.textContent=value;return e;},contains:el=>all.includes(el),addEventListener(){},
  querySelector(selector){if(selector==='input[name="mode"]:checked')return {value:'LIVE_SANDBOX'};if(selector.startsWith('#progress ')){if(!queries.has(selector))queries.set(selector,new Element());return queries.get(selector);}if(selector.startsWith('.')){const existing=all.find(e=>e.matches(selector));if(existing)return existing;}if(!queries.has(selector))queries.set(selector,new Element());return queries.get(selector);},
  querySelectorAll(selector){if(selector==='.run-row')return nodes.get('runs')?.walk().filter(e=>e.classList.contains('run-row'))||[];if(selector==='.trace-filters button')return sources;if(selector==='button[data-story]')return stories;if(selector==='[data-case]'||selector==='.case-switch [data-case]')return cases;if(selector==='[data-failure-step]')return failureAi;if(selector==='[data-ai-step]')return ai;if(selector==='a[href="#investigation"]')return links;if(selector==='.compare-card')return [];if(selector.includes('.brand'))return [document.querySelector('.brand'),document.querySelector('.nav-home')];return [];}};
 if(nodes.has('fault')){nodes.get('fault').options=['none','response_loss','event_delay','event_duplicate','process_interrupt'].map(value=>({value,hidden:false,disabled:false}));nodes.get('fault').value='none';}
 if(nodes.has('merchant'))nodes.get('merchant').value='healthy';if(nodes.has('fixture'))nodes.get('fixture').value='workshop-v1';if(nodes.has('source-filter'))nodes.get('source-filter').value='all';
 const context=vm.createContext({document,location,history:{replaceState:(_a,_b,next)=>{const x=new URL(next,location.href);location.href=x.href;}},window:{location,localStorage:storage,matchMedia:query=>({matches:query.includes('max-width')?mobile:false,addEventListener(){}}),addEventListener(){}},navigator:{clipboard:{writeText:async value=>{context.copied=value;}}},URL,URLSearchParams,Response,setInterval(){},clearInterval(){},fetch:async(...args)=>{calls.push(args);return fetcher?fetcher(...args):new Response('{}',{status:503});}});
 return {nodes,document,context,calls,assigned,sources,stories,cases,aiSteps:ai,failureSteps:failureAi,links,element:()=>new Element()};
}
function loadMain(options){const page=environment('web/app.js',options);const source=fs.readFileSync(path.join(ROOT,'web/app.js'),'utf8');const end=source.lastIndexOf('\n  updateLinks();');if(end<0)throw Error('Missing explicit startup boundary');const expose=`\n globalThis.ui={api,ApiError,errorMessage,showError,openWorkspace,refresh,safeRefresh,money,validDetails,latestVerdict,oneTicket,jobMessage,jobFinding,renderFlow,syncActionButtons,selectRun,startCheckout,openNewCase,closeNewCase,applyCapabilities,allowedFault,mutate,stillMine,poll, renderAssistant, state:()=>({selected,current,active,creating,cancelPending,unresolved,acknowledgedJobs,createUnresolved}), setState:value=>{if('selected'in value)selected=value.selected;if('current'in value)current=value.current;if('active'in value)active=value.active;if('pageMode'in value)pageMode=value.pageMode;}};\n})();`;
 vm.runInContext(source.slice(0,end)+expose,page.context,{filename:'web/app.js'});page.ui=page.context.ui;return page;}
async function loadJudge(fetcher,options={}){const page=environment('web/judge/app.js',{...options,fetch:fetcher});let source=fs.readFileSync(path.join(ROOT,'web/judge/app.js'),'utf8');source=source.replace(/\}\)\(\);\s*$/,'globalThis.ui={validReview,validCase,historicalAiStage};})();');vm.runInContext(source,page.context,{filename:'web/judge/app.js'});page.ui=page.context.ui;await flush();return page;}
async function flush(){await new Promise(setImmediate);await new Promise(setImmediate);}
function details(id='run-a',{paid=false,ticket=false,job=null}={}){const purchase='purchase-'+id,order=paid?'ORDER-'+id:null;const d={run:{id,purchase_id:purchase,promise:'Synthetic case',mode:'LOCAL_TEST',state:'created',fault:{kind:'none',merchant:'healthy'},budget:{max_attempts:8,max_seconds:180,max_model_calls:4},cancel_requested:0,execution:null,updated_at:'2026-11-09T00:00:00Z'},purchase:{id:purchase,run_id:id,order_id:order,amount:2900,currency:'USD',payment_confirmed:paid?1:0,payment_state:paid?'COMPLETED':'NOT_STARTED'},merchant:{known:true,run_id:id,purchase_id:purchase,order_id:order,ticket_count:ticket?1:0,tickets:ticket?[{id:'ticket-'+id,purchase_id:purchase,created_at:'2026-11-09T00:00:10Z'}]:[],status:ticket?'DELIVERED':'NOT_DELIVERED'},events:[],operations:[],investigation_job:job,recording:{availability:'disabled'}};return d;}
const response=(data,status=200)=>new Response(JSON.stringify(data),{status});
function backend(records,{failRead=()=>false,post=async()=>({})}={}){return async(url,init={})=>{if(init.method==='POST')return response(await post(url,JSON.parse(init.body)));if(url==='/healthz')return response({status:'ok',database:'ok',capabilities:{faults:['none','response_loss','event_delay','event_duplicate'],max_promise_chars:1000}});if(url==='/api/prerequisites')return response({paypal:{configured:true}});if(url==='/api/runs')return response({runs:[...records.values()].map(d=>d.run)});if(failRead(url))throw TypeError('Synthetic readback loss');const id=decodeURIComponent(url.split('/')[3]);return records.has(id)?response(records.get(id)):response({error:'Unknown run'},404);};}
module.exports={ROOT,loadMain,loadJudge,flush,details,response,backend};
