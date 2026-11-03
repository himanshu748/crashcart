/** Read-only presentation of saved ticket-v1 records. This module never decides a verdict. */
export type RunMode = "LOCAL_TEST" | "LIVE_SANDBOX" | "RECORDED_REPLAY" | "FRESH_SANDBOX";
export type SavedVerdict = "PASS" | "FAIL" | "INCONCLUSIVE" | null;

export type RunSummary = {
  id: string;
  purchaseId: string;
  title: string;
  reference: string;
  mode: RunMode;
  modeLabel: string;
  state: string;
  stateLabel: string;
  sourceLabel: string;
};

export type TimingRow = RunSummary & {
  verdict: SavedVerdict;
  verdictLabel: string;
  verdictReason: string;
  paymentAt: string | null;
  paymentEpochMs: number | null;
  ticketOffsetsMs: number[];
  ticketTimes: string[];
  ticketCount: number | null;
  timingStatus: string;
  timingAvailable: boolean;
};

type RecordValue = Record<string, unknown>;
type Instant = { text: string; micros: bigint; epochMs: number };
const modes: Record<RunMode, string> = {
  LOCAL_TEST: "Local test",
  LIVE_SANDBOX: "Initial test checkout",
  RECORDED_REPLAY: "Recorded replay",
  FRESH_SANDBOX: "New checkout after a repair",
};
const states: Record<string, string> = {
  CREATED: "Ready to start", created: "Ready to start", queued: "Queued",
  running: "Running", awaiting_approval: "Awaiting buyer approval",
  completed: "Completed", failed: "Failed", cancelled: "Stopped",
  inconclusive: "More evidence needed",
};
const isRecord = (v: unknown): v is RecordValue => v !== null && typeof v === "object" && !Array.isArray(v);
const identity = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.length <= 256 && v === v.trim();
const runId = (v: unknown): v is string => typeof v === "string" && /^run_[a-f0-9]{32}$/.test(v);
const purchaseId = (v: unknown): v is string => typeof v === "string" && /^purchase_[a-f0-9]{32}$/.test(v);
const error = () => new Error("Saved investigation identity or records are invalid. Open the original investigation.");

/** Require an explicit timezone and an actual calendar date; preserve six-digit source precision. */
function instant(value: unknown): Instant | null {
  if (typeof value !== "string") return null;
  const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match) return null;
  const calendar = new Date(`${match[1]}T${match[2]}Z`);
  if (!Number.isFinite(calendar.getTime()) || calendar.toISOString().slice(0, 19) !== `${match[1]}T${match[2]}`) return null;
  const whole = Date.parse(`${match[1]}T${match[2]}${match[4]}`);
  if (!Number.isFinite(whole)) return null;
  const micros = BigInt(whole) * 1000n + BigInt((match[3] ?? "").padEnd(6, "0"));
  return { text: value, micros, epochMs: Number(micros) / 1000 };
}

function summary(value: unknown): RunSummary {
  if (!isRecord(value) || !runId(value.id) || !purchaseId(value.purchase_id) ||
      typeof value.promise !== "string" || !value.promise.trim() || value.promise.length > 4000 ||
      typeof value.mode !== "string" || !Object.hasOwn(modes, value.mode) ||
      typeof value.state !== "string" || !value.state || value.state.length > 80) throw error();
  const mode = value.mode as RunMode;
  return {
    id: value.id, purchaseId: value.purchase_id, title: value.promise,
    reference: value.id.slice(-8), mode, modeLabel: modes[mode], state: value.state,
    stateLabel: Object.hasOwn(states, value.state) ? states[value.state] : "Saved state unavailable",
    sourceLabel: mode === "RECORDED_REPLAY" ? "Saved replay records" : mode === "LOCAL_TEST" ? "Saved local test records" : "Saved test-payment records",
  };
}

export function parseRunList(value: unknown): RunSummary[] {
  if (!isRecord(value) || !Array.isArray(value.runs)) throw error();
  const result = value.runs.map(summary);
  if (new Set(result.map(v => v.id)).size !== result.length || new Set(result.map(v => v.purchaseId)).size !== result.length) throw error();
  return result;
}

type ResultRecord = { verdict: SavedVerdict; reason: string; deadline: unknown; issue: string | null };
function savedResult(events: unknown[], run: RunSummary, purchase: RecordValue): ResultRecord {
  const none: ResultRecord = { verdict: null, reason: "No saved delivery result.", deadline: undefined, issue: null };
  const candidates = events.filter(e => isRecord(e) && e.event_type === "invariant_result");
  if (!candidates.length) return none;
  let latest: RecordValue | null = null;
  let latestTime: bigint | null = null;
  const seen = new Set<string>();
  for (const candidate of candidates) {
    if (!isRecord(candidate)) continue;
    const observed = instant(candidate.observed_at);
    if (!identity(candidate.id) || seen.has(candidate.id) || !observed)
      return { ...none, issue: "The saved result's identity or time is unavailable." };
    seen.add(candidate.id);
    if (latestTime === null || observed.micros > latestTime ||
        (observed.micros === latestTime && candidate.id > String(latest?.id))) {
      latest = candidate;
      latestTime = observed.micros;
    }
  }
  if (!latest || latest.source !== "checker" || latest.run_id !== run.id ||
      latest.purchase_id !== run.purchaseId || latest.order_id !== purchase.order_id ||
      !isRecord(latest.payload)) return { ...none, issue: "The saved result does not match this investigation's records." };
  const payload = latest.payload;
  if (payload.invariant_version !== "ticket-v1" || !isRecord(payload.source_ids) ||
      typeof payload.verdict !== "string" || !["PASS", "FAIL", "INCONCLUSIVE"].includes(payload.verdict))
    return { ...none, issue: "The saved result does not use the supported delivery promise." };
  const ids = payload.source_ids;
  const expected: Record<string, unknown> = {
    run_id: run.id, purchase_id: run.purchaseId,
    order_id: purchase.order_id, capture_id: purchase.capture_id,
  };
  for (const [key, val] of Object.entries(expected)) {
    // Early inconclusive checks may not have established every source identity.
    if ((Object.hasOwn(ids, key) && ids[key] !== val) ||
        (payload.verdict !== "INCONCLUSIVE" && (!identity(val) || ids[key] !== val)))
      return { ...none, issue: "The saved result refers to different payment records." };
  }
  return {
    verdict: payload.verdict as Exclude<SavedVerdict, null>,
    reason: typeof payload.reason === "string" && payload.reason.length <= 4000 ? payload.reason : "Open the original saved result for details.",
    deadline: payload.deadline, issue: null,
  };
}

export function projectDetail(value: unknown, expectedRunId: string): TimingRow {
  if (!runId(expectedRunId) || !isRecord(value)) throw error();
  const run = summary(value.run);
  if (run.id !== expectedRunId || !isRecord(value.purchase) ||
      value.purchase.id !== run.purchaseId || value.purchase.run_id !== run.id) throw error();
  const purchase = value.purchase;
  const supported = isRecord(value.run) && value.run.invariant_version === "ticket-v1";
  const result: ResultRecord = supported ? savedResult(Array.isArray(value.events) ? value.events : [], run, purchase) :
    { verdict: null, reason: "No result for the supported delivery promise.", deadline: undefined, issue: null };
  const row: TimingRow = {
    ...run, verdict: result.verdict,
    verdictLabel: result.verdict === "PASS" ? "Promise kept" : result.verdict === "FAIL" ? "Promise broken" : result.verdict === "INCONCLUSIVE" ? "More evidence needed" : "Not checked",
    verdictReason: result.reason, paymentAt: null, paymentEpochMs: null,
    ticketOffsetsMs: [], ticketTimes: [], ticketCount: null,
    timingStatus: "Payment is not independently confirmed.", timingAvailable: false,
  };
  const unavailable = (reason: string): TimingRow => ({ ...row, timingStatus: reason });
  if (!supported)
    return unavailable("This investigation does not use the supported delivery promise.");
  if (purchase.payment_confirmed !== 1 && purchase.payment_confirmed !== true) return row;
  if (purchase.payment_state !== "COMPLETED" || !identity(purchase.order_id) || !identity(purchase.capture_id))
    return unavailable("A completed payment and its references are unavailable.");
  if (purchase.amount !== 2900 || purchase.currency !== "USD")
    return unavailable("This payment does not match the one-ticket USD 29 promise.");
  const payment = instant(purchase.capture_completed_at);
  if (!payment) return unavailable("Confirmed payment time is unavailable or has no timezone.");
  const merchant = value.merchant;
  if (!isRecord(merchant) || merchant.known !== true)
    return unavailable("The store's delivery records are unavailable.");
  if (merchant.purchase_id !== run.purchaseId || merchant.run_id !== run.id || merchant.order_id !== purchase.order_id)
    return unavailable("The payment and store records do not belong to the same purchase.");
  const observed = instant(merchant.observed_at);
  if (!observed || observed.micros < payment.micros)
    return unavailable("The store observation time is unavailable or precedes payment.");
  if (typeof merchant.ticket_count !== "number" || !Number.isInteger(merchant.ticket_count) || merchant.ticket_count < 0 ||
      !Array.isArray(merchant.tickets) || merchant.tickets.length !== merchant.ticket_count)
    return unavailable("The ticket count and delivery records disagree.");
  const tickets: Instant[] = [];
  const identities = new Set<string>();
  for (const ticket of merchant.tickets) {
    if (!isRecord(ticket) || !identity(ticket.id) || ticket.purchase_id !== run.purchaseId || identities.has(ticket.id))
      return unavailable("A ticket identity is repeated, unavailable or belongs to another purchase.");
    const time = instant(ticket.created_at);
    if (!time || time.micros < payment.micros || time.micros > observed.micros)
      return unavailable("A ticket time is unavailable or outside the recorded payment and store observation.");
    identities.add(ticket.id);
    tickets.push(time);
  }
  if (result.issue) return unavailable(result.issue);
  if (result.verdict !== null) {
    const deadline = instant(result.deadline);
    if (!deadline) return unavailable("The saved delivery deadline is unavailable.");
    if (deadline.micros !== payment.micros + 60_000_000n)
      return unavailable("The saved deadline conflicts with the fixed 60-second delivery promise.");
  }
  tickets.sort((a, b) => a.micros < b.micros ? -1 : a.micros > b.micros ? 1 : 0);
  return {
    ...row, paymentAt: payment.text, paymentEpochMs: payment.epochMs,
    ticketCount: merchant.ticket_count, ticketTimes: tickets.map(t => t.text),
    ticketOffsetsMs: tickets.map(t => Number(t.micros - payment.micros) / 1000),
    timingAvailable: true,
    timingStatus: result.verdict === null ? "Recorded timings shown. No delivery result has been saved." : "Recorded timings shown. The saved result is unchanged.",
  };
}
