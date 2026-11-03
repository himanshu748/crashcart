import { createContext, useContext } from "react";
import { INITIAL_QUERY, queryLabel, type QueryState } from "./query-agent";

export const testTypeLabel = (mode: string): string => new Map([
  ["LIVE_SANDBOX", "Initial test checkout"],
  ["FRESH_SANDBOX", "New checkout after a repair"],
  ["RECORDED_REPLAY", "Saved checkout replay"],
  ["LOCAL_TEST", "Simulated test data"],
]).get(mode) || "Test type not recorded";
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
  return <section className="widget query-results" aria-label="Answers">
    {testData&&<p className="query-source test-data">Test data · simulated response</p>}
    <p className="kicker"><span className="source-index" aria-hidden="true">↗</span> ASK YOUR SAVED RECORDS</p>
    <h2>Answers</h2>
    <p role="status" className={`query-status ${status}${testData ? " test-data" : ""}`}>{testData ? "Test data · " : ""}{message}</p>
    <p className="meta">The assistant chooses which records to show. Counts come from those records. A missing ticket alone does not show that the delivery deadline was missed.</p>
    {!receipt&&<p className="query-empty">Open “Ask a question” to find completed payments, missing tickets, payments still being checked, or delivered tickets.</p>}
    {errorCode&&<details className="query-error-details"><summary>Technical details</summary><code>{errorCode}</code></details>}
    {receipt&&<>
      <div className="query-totals"><strong>{receipt.count}<small>matching {receipt.count===1 ? "investigation" : "investigations"}</small></strong><strong>{receipt.summary.completed_payments}<small>confirmed payments</small></strong><strong>{receipt.summary.ticket_count}<small>saved tickets</small></strong></div>
      {receipt.rows.length===0 ? <p>{receipt.status === "UNSUPPORTED" ? "This question cannot be answered from these records. No filter was applied." : "No saved investigations match this question."}</p> : <div className="query-table" tabIndex={0} role="region" aria-label="Matching saved investigations"><table><thead><tr><th>Investigation</th><th>Payment</th><th>Tickets</th><th>Supporting records</th></tr></thead><tbody>{receipt.rows.map(row=><tr key={row.run_id}><td><strong>Case {row.run_id.slice(-8)}</strong><br/><small>{testTypeLabel(row.mode)}</small></td><td>{paymentLabel(row.payment_state)}<br/>{(row.amount/100).toFixed(2)} {row.currency}</td><td>{row.ticket_count}<code>{row.ticket_id||"No ticket"}</code></td><td><details className="row-records"><summary>Original records</summary><pre>{JSON.stringify(row,null,2)}</pre></details></td></tr>)}</tbody></table></div>}
      <details className="query-provenance"><summary>Technical details</summary><dl>
        <dt>Question filter</dt><dd>{queryLabel(receipt.plan.query)}</dd>
        <dt>Answer source</dt><dd>{testData ? "Test data · simulated response" : "Connected assistant"}</dd>
        <dt>Assistant</dt><dd>{receipt.model.actual}</dd>
        <dt>Records saved</dt><dd>{receipt.snapshot_at}</dd>
        <dt>Record fingerprint</dt><dd>{receipt.dataset_sha256}</dd>
        <dt>Request</dt><dd>{receipt.request_id} · {receipt.cached ? "Previously saved answer" : "New answer"}</dd>
        <dt>Records checked</dt><dd>{receipt.summary.scope_runs} saved investigations</dd>
      </dl><p>Original answer and record references</p><pre>{JSON.stringify(receipt,null,2)}</pre></details>
    </>}
  </section>;
}
