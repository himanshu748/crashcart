/** LOCAL_TEST: synthetic records only. These tests do not establish any provider or browser execution. */
import assert from "node:assert/strict";
import test from "node:test";
import { parseRunList, projectDetail } from "../studio/src/deadlines-model.ts";

const RUN = "run_11111111111111111111111111111111";
const PURCHASE = "purchase_22222222222222222222222222222222";
const OTHER_RUN = "run_33333333333333333333333333333333";
const OTHER_PURCHASE = "purchase_44444444444444444444444444444444";
const fixed = () => ({
  run: { id: RUN, purchase_id: PURCHASE, invariant_version: "ticket-v1", promise: "Synthetic local test: one USD 29 ticket within 60 seconds.", mode: "LIVE_SANDBOX", state: "completed" },
  purchase: { id: PURCHASE, run_id: RUN, order_id: "synthetic-order", capture_id: "synthetic-capture", payment_confirmed: 1 as unknown, payment_state: "COMPLETED", amount: 2900, currency: "USD", capture_completed_at: "2026-10-28T07:47:43Z" },
  merchant: { known: true, run_id: RUN, purchase_id: PURCHASE, order_id: "synthetic-order", ticket_count: 1, observed_at: "2026-10-28T07:50:00Z", tickets: [{ id: "synthetic-ticket", purchase_id: PURCHASE, created_at: "2026-10-28T07:47:46.898776Z" }] },
  events: [{ id: "synthetic-event-1", source: "checker", event_type: "invariant_result", run_id: RUN, purchase_id: PURCHASE, order_id: "synthetic-order", observed_at: "2026-10-28T07:47:47Z", payload: { verdict: "PASS", invariant_version: "ticket-v1", reason: "Synthetic saved checker result.", deadline: "2026-10-28T07:48:43Z" as unknown, source_ids: { run_id: RUN, purchase_id: PURCHASE, order_id: "synthetic-order", capture_id: "synthetic-capture" } as Record<string, unknown> } }],
});
type Fixture = ReturnType<typeof fixed>;
const project = (v: unknown = fixed()) => projectDetail(v, RUN);
function unplotted(v: unknown) {
  const row = project(v);
  assert.equal(row.timingAvailable, false);
  assert.equal(row.paymentAt, null);
  assert.equal(row.paymentEpochMs, null);
  assert.deepEqual(row.ticketOffsetsMs, []);
  assert.deepEqual(row.ticketTimes, []);
  assert.equal(row.ticketCount, null);
  assert.ok(row.timingStatus.length > 0);
  return row;
}
function freeze(value: unknown): void {
  if (value && typeof value === "object") { Object.freeze(value); Object.values(value).forEach(freeze); }
}

test("valid correlated saved records preserve microsecond relative ticket time and the server result", () => {
  const row = project();
  assert.equal(row.timingAvailable, true);
  assert.equal(row.paymentAt, "2026-10-28T07:47:43Z");
  assert.deepEqual(row.ticketOffsetsMs, [3898.776]);
  assert.deepEqual(row.ticketTimes, ["2026-10-28T07:47:46.898776Z"]);
  assert.equal(row.verdict, "PASS");
  assert.equal(row.verdictReason, "Synthetic saved checker result.");
  assert.equal(row.sourceLabel, "Saved test-payment records");
});

test("projection accepts frozen input and changes no source records", () => {
  const data = fixed(); const before = JSON.stringify(data); freeze(data);
  project(data); assert.equal(JSON.stringify(data), before);
});

test("a completed run or customer page message cannot establish payment", () => {
  const data = fixed(); data.purchase.payment_confirmed = 0;
  data.events = []; Object.assign(data, { browser: { visible_text: "Payment confirmed" } });
  const row = unplotted(data); assert.equal(row.verdict, null);
});

for (const paid of ["1", "true", 2, null]) test(`untrusted confirmation flag ${JSON.stringify(paid)} stays unplotted`, () => {
  const data = fixed(); data.purchase.payment_confirmed = paid; unplotted(data);
});

test("boolean true is an explicit confirmation flag, not a truthy coercion", () => {
  const data = fixed(); data.purchase.payment_confirmed = true; assert.equal(project(data).timingAvailable, true);
});

for (const field of ["order_id", "capture_id", "payment_state"] as const) test(`missing completed-payment ${field} stays unplotted`, () => {
  const data = fixed(); data.purchase[field] = ""; unplotted(data);
});

test("wrong amount or currency does not enter the fixed-ticket timeline", () => {
  const amount = fixed(); amount.purchase.amount = 2901; unplotted(amount);
  const currency = fixed(); currency.purchase.currency = "EUR"; unplotted(currency);
});

for (const time of ["2026-10-28T07:47:43", "2026-02-30T07:47:43Z", "2026-10-28T24:00:00Z", "2026-10-28T07:47:43+24:00", "not-a-date"])
  test(`ambiguous or invalid payment time ${time} stays unplotted`, () => {
    const data = fixed(); data.purchase.capture_completed_at = time; unplotted(data);
  });

test("equivalent explicit offsets preserve actual relative timing", () => {
  const data = fixed(); data.purchase.capture_completed_at = "2026-10-28T13:17:43+05:30";
  assert.deepEqual(project(data).ticketOffsetsMs, [3898.776]);
});

test("unknown store records stay unavailable rather than becoming zero tickets", () => {
  const data = fixed(); data.merchant.known = false; unplotted(data);
});

for (const field of ["run_id", "purchase_id", "order_id"] as const) test(`cross-purchase merchant ${field} stays unplotted`, () => {
  const data = fixed(); data.merchant[field] = "different-record"; unplotted(data);
});

test("missing or pre-payment store observation is not plotted", () => {
  for (const time of ["", "2026-10-28T07:50:00", "2026-10-28T07:47:42Z"]) {
    const data = fixed(); data.merchant.observed_at = time; unplotted(data);
  }
});

test("disagreeing ticket count, negative count or repeated ticket is not repaired by the client", () => {
  for (const count of [0, 2, -1, 0.5]) { const data = fixed(); data.merchant.ticket_count = count; unplotted(data); }
  const duplicate = fixed(); duplicate.merchant.ticket_count = 2;
  duplicate.merchant.tickets.push({ ...duplicate.merchant.tickets[0] }); unplotted(duplicate);
});

test("a ticket from another purchase cannot create a timeline marker", () => {
  const data = fixed(); data.merchant.tickets[0].purchase_id = OTHER_PURCHASE; unplotted(data);
});

test("invalid, timezone-free, pre-payment or after-observation ticket times are not clamped", () => {
  for (const time of ["bad", "2026-10-28T07:47:46", "2026-10-28T07:47:42Z", "2026-10-28T07:50:01Z"]) {
    const data = fixed(); data.merchant.tickets[0].created_at = time; unplotted(data);
  }
});

test("a late ticket keeps its actual offset and never changes the recorded verdict", () => {
  const data = fixed(); data.merchant.tickets[0].created_at = "2026-10-28T07:48:44.000001Z";
  const row = project(data);
  assert.deepEqual(row.ticketOffsetsMs, [61000.001]);
  assert.equal(row.verdict, "PASS", "the presentation must not replace a saved result with its own verdict");
});

test("multiple distinct tickets retain all actual offsets and the recorded result", () => {
  const data = fixed(); data.merchant.ticket_count = 2;
  data.merchant.tickets.push({ id: "second-synthetic-ticket", purchase_id: PURCHASE, created_at: "2026-10-28T07:47:44Z" });
  data.events[0].payload.verdict = "FAIL";
  const row = project(data);
  assert.deepEqual(row.ticketOffsetsMs, [1000, 3898.776]); assert.equal(row.ticketCount, 2); assert.equal(row.verdict, "FAIL");
});

test("zero tickets beyond the promise without a saved result does not become a client failure", () => {
  const data = fixed(); data.events = []; data.merchant.tickets = []; data.merchant.ticket_count = 0;
  const row = project(data);
  assert.equal(row.timingAvailable, true); assert.equal(row.ticketCount, 0); assert.equal(row.verdict, null);
  assert.equal(row.verdictLabel, "Not checked"); assert.match(row.timingStatus, /No delivery result/);
});

test("newest observed checker result wins independently of array order", () => {
  const data = fixed(); const latest = structuredClone(data.events[0]);
  latest.id = "synthetic-event-2"; latest.observed_at = "2026-10-28T07:47:48Z"; latest.payload.verdict = "FAIL";
  data.events.unshift(latest); assert.equal(project(data).verdict, "FAIL");
});

test("equal observed times use the API's deterministic event-id ordering", () => {
  const data = fixed(); const latest = structuredClone(data.events[0]);
  latest.id = "synthetic-event-2"; latest.payload.verdict = "FAIL"; data.events.unshift(latest);
  assert.equal(project(data).verdict, "FAIL");
});

test("bad latest result identity never silently falls back to an earlier favorable result", () => {
  const data = fixed(); const bad = structuredClone(data.events[0]);
  bad.id = "synthetic-event-2"; bad.observed_at = "2026-10-28T07:47:48Z"; bad.payload.source_ids.capture_id = "wrong-capture";
  data.events.push(bad); assert.equal(unplotted(data).verdict, null);
});

for (const field of ["run_id", "purchase_id", "order_id", "source"] as const) test(`saved result header ${field} must belong to this checker observation`, () => {
  const data = fixed(); data.events[0][field] = "wrong-record"; assert.equal(unplotted(data).verdict, null);
});

test("unsupported payload invariant or verdict is not presented as an accepted server result", () => {
  const invariant = fixed(); invariant.events[0].payload.invariant_version = "ticket-v2"; assert.equal(unplotted(invariant).verdict, null);
  const verdict = fixed(); verdict.events[0].payload.verdict = "HTTP_200"; assert.equal(unplotted(verdict).verdict, null);
});

test("duplicate checker identity or an unavailable result time does not choose an outcome", () => {
  const duplicate = fixed(); duplicate.events.push(structuredClone(duplicate.events[0])); assert.equal(unplotted(duplicate).verdict, null);
  const time = fixed(); time.events[0].observed_at = "2026-10-28T07:47:47"; assert.equal(unplotted(time).verdict, null);
});

test("missing saved deadline hides timing while preserving the recorded result", () => {
  const data = fixed(); data.events[0].payload.deadline = null;
  assert.equal(unplotted(data).verdict, "PASS");
});

test("even a one-microsecond deadline conflict is exposed without rewriting the saved result", () => {
  const data = fixed(); data.events[0].payload.deadline = "2026-10-28T07:48:43.000001Z";
  const row = unplotted(data); assert.equal(row.verdict, "PASS"); assert.match(row.timingStatus, /conflicts/);
});

test("an inconclusive saved checker result may have only the source identities it established", () => {
  const data = fixed(); data.events[0].payload.verdict = "INCONCLUSIVE"; data.events[0].payload.source_ids = {};
  const row = project(data); assert.equal(row.timingAvailable, true); assert.equal(row.verdict, "INCONCLUSIVE");
});

test("unsupported run invariant is unavailable even when a payload says ticket-v1", () => {
  const data = fixed(); data.run.invariant_version = "ticket-v2";
  assert.equal(unplotted(data).verdict, null);
});

test("top-level run and purchase identity errors throw a fixed user-safe error", () => {
  const cases: unknown[] = [null, {}, { ...fixed(), run: { ...fixed().run, id: OTHER_RUN } },
    { ...fixed(), purchase: { ...fixed().purchase, id: OTHER_PURCHASE } },
    { ...fixed(), purchase: { ...fixed().purchase, run_id: OTHER_RUN } },
    { ...fixed(), run: { ...fixed().run, mode: "LIVE_MONEY" } }];
  for (const value of cases) assert.throws(() => project(value), { message: "Saved investigation identity or records are invalid. Open the original investigation." });
});

test("run list rejects duplicate identities and maps modes without internal enum labels", () => {
  for (const [mode, label] of [["LOCAL_TEST", "Example data · no payment"], ["LIVE_SANDBOX", "Test checkout"], ["RECORDED_REPLAY", "Replayed checkout"], ["FRESH_SANDBOX", "New test checkout after a repair"]]) {
    const run = { ...fixed().run, mode }; const row = parseRunList({ runs: [run] })[0]; assert.equal(row.modeLabel, label);
    assert.ok(!row.sourceLabel.includes("LIVE_SANDBOX"));
  }
  assert.throws(() => parseRunList({ runs: [fixed().run, fixed().run] }));
  assert.throws(() => parseRunList({ runs: [fixed().run, { ...fixed().run, id: OTHER_RUN }] }));
  assert.throws(() => parseRunList({ runs: "invalid" }));
});

test("unknown state names cannot select prototype properties or become executable content", () => {
  const data = fixed(); data.run.state = "constructor"; data.run.promise = "<script>synthetic text only</script>";
  const row = project(data); assert.equal(row.stateLabel, "Status unavailable"); assert.equal(row.title, data.run.promise);
});
