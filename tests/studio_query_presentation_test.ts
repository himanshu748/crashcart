/** LOCAL_TEST: synthetic receipts, rendered components and a fake fetch; no provider requests. */
import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { QueryContext, QueryWidget } from "../studio/src/query-widget";
import { QueryController, validateReceipt, type QueryReceipt, type QueryState } from "../studio/src/query-agent";
import { parseRunList } from "../studio/src/deadlines-model";

const RUN = "run_11111111111111111111111111111111";
const REQUEST = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee";
function receipt(unsupported: boolean, requestId = REQUEST): QueryReceipt {
  return {
    version: "studio-query-v1", request_id: requestId, run_id: RUN,
    attempt_id: "attempt_studio_" + requestId.replaceAll("-", ""),
    status: unsupported ? "UNSUPPORTED" : "COMPLETED", model_mode: "LOCAL_TEST",
    model: { configured: "synthetic", actual: "synthetic", response_id: "synthetic-response", usage: null },
    plan: { query: unsupported ? "unsupported" : "completed_missing_tickets", mode: "LOCAL_TEST" },
    dataset_sha256: "a".repeat(64), snapshot_at: "2026-11-09T10:00:00Z",
    rows: [], count: 0, cached: false,
    summary: { matching_runs: 0, scope_runs: 3, completed_payments: 0, ticket_count: 0,
      description: "Synthetic saved records.", scope_note: "LOCAL_TEST only." },
  };
}
function render(value: QueryReceipt): string {
  return renderToStaticMarkup(createElement(QueryContext.Provider,
    { value: { status: "complete", message: "", receipt: value } }, createElement(QueryWidget)));
}

test("unsupported questions show an explanation without zero-match totals", () => {
  const value = validateReceipt(receipt(true), RUN, REQUEST);
  const before = JSON.stringify(value);
  const html = render(value);
  assert.match(html, /This question cannot be answered from these records/);
  assert.doesNotMatch(html, /class="query-totals"/);
  assert.doesNotMatch(html, /No saved cases match/);
  assert.equal(JSON.stringify(value), before);
});

test("a supported empty result still shows zero totals and a no-matches message", () => {
  const value = validateReceipt(receipt(false), RUN, REQUEST);
  const html = render(value);
  assert.match(html, /class="query-totals"/);
  assert.match(html, /<strong>0<small>matching cases/);
  assert.match(html, /No saved cases match this question/);
  assert.doesNotMatch(html, /This question cannot be answered/);
});

test("supported results keep exact counts while ticket references stay in closed details", () => {
  const value = receipt(false);
  value.plan.query = "delivered";
  value.rows = [{ run_id: RUN, mode: "LOCAL_TEST", payment_state: "COMPLETED", payment_confirmed: 1,
    purchase_id: "purchase_22222222222222222222222222222222", amount: 2900, currency: "USD",
    order_id: "synthetic-order", capture_id: "synthetic-capture", ticket_count: 1, ticket_id: "synthetic-ticket",
    source_ids: { browser_event_id: null, provider_event_id: "synthetic-provider", merchant_event_id: "synthetic-merchant", invariant_event_id: null } }];
  value.count = value.summary.matching_runs = value.summary.completed_payments = value.summary.ticket_count = 1;
  const html = render(validateReceipt(value, RUN, REQUEST));
  assert.match(html, /<strong>1<small>matching case/);
  assert.match(html, /<details><summary>Ticket reference<\/summary><code>synthetic-ticket<\/code><\/details>/);
  assert.doesNotMatch(html, /<details open/);
});

for (const unsupported of [true, false]) {
  test(`chat distinguishes ${unsupported ? "unsupported" : "valid zero-match"} answers without changing internal counts`, async () => {
    const originalFetch = globalThis.fetch;
    let requests = 0;
    const states: QueryState[] = [];
    globalThis.fetch = (async (url, init) => {
      assert.equal(url, "/api/studio/query");
      assert.equal(init?.method, "POST");
      requests++;
      const body = JSON.parse(String(init?.body));
      assert.equal(body.run_id, RUN);
      return { ok: true, json: async () => receipt(unsupported, body.request_id) } as Response;
    }) as typeof fetch;
    try {
      const controller = new QueryController(() => ({ runId: RUN, ready: true }), state => states.push(state));
      const events: any[] = [];
      const input = { threadId: "synthetic-thread", runId: "synthetic-ai-run", messages: [{ role: "user", content: "Find missing tickets" }] };
      const context = { signal: new AbortController().signal };
      for await (const event of controller.runner.run(input as never, context as never)) events.push(event);
      const answer = events.filter(event => event.type === "TEXT_MESSAGE_CONTENT").map(event => event.delta).join("");
      assert.equal(requests, 1);
      assert.equal(states.at(-1)?.status, "complete");
      assert.equal(states.at(-1)?.receipt?.count, 0);
      assert.equal(events.find(event => event.type === "RUN_FINISHED")?.result.count, 0);
      if (unsupported) {
        assert.match(answer, /This question cannot be answered/);
        assert.match(answer, /Test data · simulated response/);
        assert.doesNotMatch(answer, /0 matching/);
      } else {
        assert.match(answer, /0 matching cases/);
        assert.match(answer, /Test data · simulated response/);
      }
    } finally { globalThis.fetch = originalFetch; }
  });
}

test("unsupported copy never bypasses receipt identity or count validation", () => {
  const wrongCase = receipt(true); wrongCase.run_id = "run_33333333333333333333333333333333";
  assert.throws(() => validateReceipt(wrongCase, RUN, REQUEST), /INVALID_QUERY_RECEIPT/);
  const wrongCount = receipt(true); wrongCount.count = 1;
  assert.throws(() => validateReceipt(wrongCount, RUN, REQUEST), /INVALID_QUERY_RECEIPT/);
});

test("only exact known generated case titles are translated", () => {
  const known = "Lost capture response: payment completed but the workshop ticket is missing.";
  const custom = known + " Customer asked us to check this order.";
  const row = (promise: string) => ({ id: RUN, purchase_id: "purchase_22222222222222222222222222222222", promise, mode: "LOCAL_TEST", state: "completed" });
  const source = { runs: [row(known)] };
  const before = JSON.stringify(source);
  assert.equal(parseRunList(source)[0].title, "Lost payment response: payment completed but the workshop ticket is missing.");
  assert.equal(JSON.stringify(source), before);
  assert.equal(parseRunList({ runs: [row(custom)] })[0].title, custom);
});
