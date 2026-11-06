"use strict";
const sourceNames = {provider:"PayPal",browser:"Checkout page",merchant:"Ticket store",harness:"Test interruption"};
const eventNames = {customer_observation:"Customer page observed",order_created:"Checkout created",pre_capture_read:"Buyer approval checked",fault_activated:"Payment response interruption started",capture_transport_response:"Payment reply recorded",independent_order_read:"Payment independently checked",entitlement_read:"Ticket store checked",process_exit_boundary:"Merchant process interrupted"};
let review, selected = "defective";
const byId = id => document.getElementById(id);
const text = (tag, content, className) => {const element=document.createElement(tag);element.textContent=content;if(className)element.className=className;return element;};
const instant = value => value ? new Date(value).toLocaleString(undefined,{dateStyle:"medium",timeStyle:"medium",timeZone:"UTC"})+" UTC" : "Not recorded";
const seconds = (later, earlier) => (new Date(later)-new Date(earlier))/1000;
const duration = value => Number.isFinite(value) ? `${value.toFixed(2)}s` : "Not recorded";
const motionPreference=window.matchMedia("(prefers-reduced-motion: reduce)");
const motionControl=byId("reduce-motion");
function applyMotionPreference(){
  document.documentElement.classList.toggle("reduce-motion",motionPreference.matches||motionControl.checked);
}
motionControl.checked=motionPreference.matches;
motionControl.addEventListener("change",applyMotionPreference);
motionPreference.addEventListener("change",()=>{if(motionPreference.matches)motionControl.checked=true;applyMotionPreference();});
applyMotionPreference();
function fact(label, main, note){const element=document.createElement("div");element.append(text("span",label,"small-label"),text("h3",main,"fact-main"),text("p",note));return element;}
function renderCase(){
  const item=review.cases[selected], receipt=item.receipt;
  const paymentTime=item.purchase.capture_completed_at;
  const ticket=item.merchant.tickets[0];
  byId("selected-name").textContent=selected==="defective"?"Failed checkout · saved payment response lost":"Repaired replay · same saved payment response lost";
  document.querySelectorAll("[data-case]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.case===selected)));
  byId("download-case").href=`downloads/${selected}.json`;
  byId("facts").replaceChildren(
    fact("01 / PAYMENT","$29.00 confirmed",`Historical completion: ${instant(paymentTime)}.`),
    fact("02 / DELIVERY",`${receipt.ticket_count} ${receipt.ticket_count===1?"ticket":"tickets"}`,ticket?`Replay creation: ${instant(ticket.created_at)} · ${duration(seconds(ticket.created_at,paymentTime))} after payment.`:"No ticket remained after the 60-second deadline in the faulty replay."),
    fact("03 / DEADLINE","60 seconds",`Unchanged deadline: ${instant(item.execution.deadline)}. Outcome: ${receipt.verdict==="PASS"?"promise kept":"promise broken"}.`));
  byId("technical-result").textContent=JSON.stringify({mode:review.mode,new_payment:false,computed_when:review.computed_when,computed_at:review.computed_at,input_file_sha256:review.input_file_sha256,canonical_input_sha256:receipt.input_sha256,merchant_variant:selected,verdict:receipt.verdict,signature:receipt.signature,invariant:review.invariant,source_authenticity:receipt.source_authenticity},null,2);
  renderTimeline();
}
function renderTimeline(){
  const item=review.cases[selected], source=byId("source-filter").value;
  // The projection preserves original page/payment observations. Merchant state
  // comes from this variant's replay; its historical source remains nested.
  const records=item.events.filter(event=>sourceNames[event.source]);
  const visible=records.filter(event=>source==="all"||event.source===source);
  byId("timeline-count").textContent=`${visible.length} of ${records.length} saved observations. Times are relative to confirmed payment; order alone does not establish cause.`;
  const entries=visible.map(event=>{
    const li=document.createElement("li"), details=document.createElement("details"), summary=document.createElement("summary");
    const relative=seconds(event.event_time,item.purchase.capture_completed_at);
    summary.append(text("span",sourceNames[event.source],"source-badge"),text("span",eventNames[event.event_type]||"Saved observation","event-name"),text("span",`${relative>=0?"+":""}${duration(relative)}`,"event-time"));
    const body=document.createElement("div");body.className="record-body";
    body.append(text("p",`${instant(event.event_time)} · ${event.source==="merchant"?"Store result produced by this replay variant. The nested recorded_payload preserves the original store observation.":"Preserved historical observation; no new service request."}`));
    const payload={...event.payload};delete payload.replay_provenance;
    const pre=text("pre",JSON.stringify(payload,null,2));pre.tabIndex=0;pre.setAttribute("aria-label",`Original details: ${eventNames[event.event_type]||"saved observation"}`);
    body.append(pre);details.append(summary,body);li.append(details);return li;
  });
  byId("timeline").replaceChildren(...entries);
}
function showStory(stage){
  const descriptions={
    payment:["01 / 03","Payment confirmed","The payment went through.","PayPal’s saved record confirms the $29 payment. That tells us the money arrived—not whether the customer got their ticket."],
    delivery:["02 / 03","Customer promise broken","But the ticket never arrived.","The response was lost. The faulty store recorded no ticket even after its 60-second delivery promise expired."],
    repair:["03 / 03","Repaired checkout replay","A second check closes the gap.",review?`The repaired store checks the same saved payment record and creates exactly one ticket after ${duration(seconds(review.cases.healthy.merchant.tickets[0].created_at,review.cases.healthy.purchase.capture_completed_at))}. Same input. Same deadline.`:"The repaired store rechecks the saved payment record and delivers one ticket within the unchanged 60-second promise."]
  };
  const values=descriptions[stage];
  document.querySelector(".promise").dataset.story=stage;
  document.querySelectorAll("button[data-story]").forEach(button=>button.setAttribute("aria-pressed",String(button.dataset.story===stage)));
  ["story-counter","story-status","story-title","story-description"].forEach((id,index)=>byId(id).textContent=values[index]);
  const copy=byId("story-copy");copy.classList.remove("enter");
  // Restart only this small, user-triggered feedback animation; no loops.
  void copy.offsetWidth;copy.classList.add("enter");
}
byId("story-copy").addEventListener("animationend",()=>byId("story-copy").classList.remove("enter"));
document.querySelectorAll("button[data-story]").forEach(button=>button.addEventListener("click",()=>showStory(button.dataset.story)));
document.querySelectorAll("[data-case]").forEach(button=>button.addEventListener("click",()=>{
  if(!review)return;selected=button.dataset.case;renderCase();
  if(button.classList.contains("select-case")){byId("evidence-title").focus();byId("evidence").scrollIntoView({block:"start",behavior:"instant"});}
}));
byId("source-filter").addEventListener("change",()=>{if(review)renderTimeline();});
fetch("data.json",{cache:"no-store"}).then(response=>{if(!response.ok)throw new Error("Saved results could not be loaded");return response.json();}).then(data=>{
  if(data.mode!=="RECORDED_REPLAY"||data.fresh_execution!==false||data.cases?.defective?.receipt?.signature!=="paid_without_ticket"||data.cases?.healthy?.receipt?.signature!=="ticket_delivered_once_on_time")throw new Error("The saved comparison does not match this review");
  review=data;
  byId("execution-note").textContent=`Both outcomes were recomputed during ${data.computed_when} (${instant(data.computed_at)}). The checkout observations were recorded in October 2026.`;
  byId("defective-count").textContent=data.cases.defective.receipt.ticket_count;
  byId("healthy-count").textContent=data.cases.healthy.receipt.ticket_count;
  const healthy=data.cases.healthy;
  byId("healthy-time").textContent=duration(seconds(healthy.merchant.tickets[0].created_at,healthy.purchase.capture_completed_at));
  byId("defective-finding").textContent="Confirmed payment, zero tickets beyond the deadline. CrashCart marks the customer promise as broken.";
  renderCase();byId("load-state").hidden=true;byId("review").hidden=false;
  // The launch URL may target the finished case before its records arrive.
  const anchor=byId(window.location.hash.slice(1));
  if(anchor)anchor.scrollIntoView({block:"start",behavior:"auto"});
}).catch(()=>{
  // A structurally incomplete response may fail after parsing. Discard it so
  // the walkthrough and case controls cannot reuse a partial investigation.
  review=null;
  byId("review").hidden=true;
  const notice=byId("load-state");notice.hidden=false;notice.classList.add("error");
  notice.textContent="The saved investigation could not be opened. Reload this page to try again. No new payment or AI request was made.";
});
