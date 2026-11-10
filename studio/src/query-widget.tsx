import { createContext, useContext } from "react";
import { INITIAL_QUERY, queryLabel, type QueryState } from "./query-agent";

export const testTypeLabel = (mode: string): string => new Map([
  ["LIVE_SANDBOX", "Test checkout"],
  ["FRESH_SANDBOX", "New test checkout after a repair"],
  ["RECORDED_REPLAY", "Replayed checkout"],
  ["LOCAL_TEST", "Example data · no payment"],
]).get(mode) || "Checkout type unavailable";
const paymentLabel = (state:string) => new Map([
  ["COMPLETED","Payment confirmed"],["UNRESOLVED","Still being checked"],
  ["AWAITING_APPROVAL","Waiting for approval"],["APPROVED","Approved"],
  ["CREATED","Checkout started"],["UNPAID","Not paid"],["FAILED","Payment failed"],
  ["CANCELLED","Cancelled"],["CANCELED","Cancelled"],
]).get(state) || "Status not recorded";
export const QueryContext = createContext<QueryState>(INITIAL_QUERY);

export function QueryWidget() {
  const { status, message, receipt, errorCode }=useContext(QueryContext);
  const testData=receipt?.model_mode === "LOCAL_TEST";
  const recorded=receipt?.model_mode === "RECORDED_FILTER";
  return <section className="widget query-results" aria-label="Answers">
    {recorded&&<p className="query-source">Recorded example · browser filter, no AI call</p>}
    {testData&&<p className="query-source test-data">Test data · simulated response</p>}
    <p className="kicker"><span className="source-index" aria-hidden="true">↗</span> ASK ABOUT PAYMENTS & TICKETS</p>
    <h2>Answers</h2>
    <p role="status" className={`query-status ${status}${testData ? " test-data" : ""}`}>{testData ? "Test data · " : ""}{message}</p>
    <p className="meta">Find cases to follow up on. These answers use saved records; check each case’s delivery time before treating a missing ticket as late.</p>
    {!receipt&&<p className="query-empty">Use a suggested question in the panel to find payments and tickets in saved cases.</p>}
    {errorCode&&<details className="query-error-details"><summary>Technical details</summary><code>{errorCode}</code></details>}
    {receipt&&<>
      {receipt.status!=="UNSUPPORTED"&&<div className="query-totals"><strong>{receipt.count}<small>matching {receipt.count===1 ? "case" : "cases"}</small></strong><strong>{receipt.summary.completed_payments}<small>confirmed payment{receipt.summary.completed_payments === 1 ? "" : "s"}</small></strong><strong>{receipt.summary.ticket_count}<small>saved ticket{receipt.summary.ticket_count === 1 ? "" : "s"}</small></strong></div>}
      {receipt.rows.length===0 ? <p>{receipt.status === "UNSUPPORTED" ? "This question cannot be answered from these records. Try asking about paid orders, missing tickets or delivered tickets." : "No saved cases match this question."}</p> : <div className="query-table" tabIndex={0} role="region" aria-label="Matching cases"><table><thead><tr><th>Case</th><th>Payment</th><th>Tickets</th><th>Supporting records</th></tr></thead><tbody>{receipt.rows.map(row=><tr key={row.run_id}><td><strong>Case {row.run_id.slice(-8)}</strong><br/><small>{testTypeLabel(row.mode)}</small></td><td>{paymentLabel(row.payment_state)}<br/>{(row.amount/100).toFixed(2)} {row.currency}</td><td>{row.ticket_count}{" "}<small>{row.ticket_count===1 ? "ticket" : "tickets"}</small>{row.ticket_id&&<details><summary>Ticket reference</summary><code>{row.ticket_id}</code></details>}</td><td><details className="row-records"><summary>Technical details</summary><pre>{JSON.stringify(row,null,2)}</pre></details></td></tr>)}</tbody></table></div>}
      <details className="query-provenance"><summary>Technical details</summary><dl>
        <dt>Question filter</dt><dd>{queryLabel(receipt.plan.query)}</dd>
        <dt>Answer source</dt><dd>{testData ? "Test data · simulated response" : recorded ? "Recorded cases · browser filter, no AI call" : "Connected assistant"}</dd>
        <dt>Assistant</dt><dd>{receipt.model.actual}</dd>
        <dt>Records saved</dt><dd>{receipt.snapshot_at}</dd>
        <dt>Record fingerprint</dt><dd>{receipt.dataset_sha256}</dd>
        <dt>Request</dt><dd>{receipt.request_id} · {receipt.cached ? "Previously saved answer" : "New answer"}</dd>
        <dt>Records checked</dt><dd>{receipt.summary.scope_runs} saved cases</dd>
      </dl><p>Original answer and record references</p><pre>{JSON.stringify(receipt,null,2)}</pre></details>
    </>}
  </section>;
}
