/** Strict presentation adapter over the keyless judge export. Never evaluates a new verdict. */
import { projectDetail } from './deadlines-model';
import type { TimingRow } from './deadlines-model';
type RecordValue = Record<string, unknown>;
const record = (v: unknown): v is RecordValue => v !== null && typeof v === 'object' && !Array.isArray(v);
const fail = () => new Error('The recorded timing comparison is incomplete or inconsistent. Open the recorded workspace.');
export function publicTimingRows(value: unknown): TimingRow[] {
  if (!record(value) || value.mode !== 'RECORDED_REPLAY' || value.fresh_execution !== false || value.network_calls !== 0 ||
      !record(value.invariant) || value.invariant.version !== 'ticket-v1' || value.invariant.recovery_seconds !== 60 ||
      !record(value.cases)) throw fail();
  const invariant = value.invariant;
  return ['defective', 'healthy'].map(variant => {
    const c = (value.cases as RecordValue)[variant];
    if (!record(c) || c.variant !== variant || !record(c.receipt) || !record(c.execution) || !record(c.purchase) || !record(c.merchant)) throw fail();
    const receipt = c.receipt, execution = c.execution;
    if (receipt.mode !== 'RECORDED_REPLAY' || receipt.merchant_variant !== variant || execution.merchant_variant !== variant ||
        receipt.network_calls !== 0 || execution.network_calls !== 0 || receipt.fresh_execution !== false ||
        !['PASS', 'FAIL', 'INCONCLUSIVE'].includes(String(receipt.verdict)) ||
        receipt.verdict !== execution.verdict || receipt.signature !== execution.signature ||
        receipt.ticket_count !== execution.ticket_count || receipt.ticket_count !== c.merchant.ticket_count ||
        receipt.run_id !== c.purchase.run_id || receipt.purchase_id !== c.purchase.id) throw fail();
    const row = projectDetail({run: {id: receipt.run_id, purchase_id: receipt.purchase_id,
      promise: 'Recorded USD 29 workshop ticket promise', mode: receipt.mode,
      state: receipt.verdict === 'PASS' ? 'VERIFIED' : 'FAILED', invariant_version: invariant.version},
      purchase: c.purchase, merchant: c.merchant, events: c.events}, String(receipt.run_id));
    if (!row.timingAvailable || row.verdict !== receipt.verdict) throw fail();
    if (row.verdict === 'PASS' && (row.ticketCount !== 1 || row.ticketOffsetsMs.length !== 1 ||
        row.ticketOffsetsMs[0] < 0 || row.ticketOffsetsMs[0] > 60_000)) throw fail();
    return {...row, reference: variant === 'healthy' ? 'Recovered order' : 'Missed order',
      title: '22 October 2026 · same saved payment', sourceLabel: variant === 'healthy' ? 'Repaired merchant rule applied to recorded input' : 'Original merchant rule applied to recorded input'};
  });
}

/** Projects actual owner-scoped Sandbox records; never decides a delivery verdict. */
export type LiveTimingRow = Omit<TimingRow, 'purchaseId'> & {
  mode: 'LIVE_SANDBOX'; deadlineAt: string | null; gapOffsetMs: number;
  missingPaidCase: boolean; webhookVerified: boolean;
};
const liveStateLabels: Record<string, string> = {
  CREATING: 'Starting checkout', AWAITING_APPROVAL: 'Waiting for buyer approval',
  CONFIRMING: 'Confirming payment', WAITING_FOR_WEBHOOK: 'Waiting for a verified payment notification',
  WAITING_FOR_PROMISE: 'Watching for ticket delivery', INVESTIGATING: 'Investigating missing delivery',
  COMPLETED: 'Complete', FAILED: 'Checkout stopped', CANCELLED: 'Cancelled', EXPIRED: 'Session expired',
};
const liveFail = () => new Error('The Sandbox timing records are incomplete. Open your checkout for details.');
const safeText = (v: unknown, max: number): v is string => typeof v === 'string' &&
  v.length > 0 && v.length <= max && v === v.trim() && !/[\x00-\x1f\x7f]/.test(v);
function utcTime(value: unknown): {text: string; micros: bigint; epochMs: number} | null {
  if (typeof value !== 'string') return null;
  const m = /^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(value);
  if (!m) return null;
  const base = Date.parse(m[1] + 'Z');
  if (!Number.isFinite(base) || new Date(base).toISOString().slice(0, 19) !== m[1]) return null;
  const micros = BigInt(base) * 1000n + BigInt((m[2] ?? '').padEnd(6, '0'));
  return {text: value, micros, epochMs: Number(micros) / 1000};
}
export function liveTimingRows(value: unknown, now = Date.now()): LiveTimingRow[] {
  if (!Number.isFinite(now) || now < 0 || !record(value) || value.mode !== 'LIVE_SANDBOX' ||
      !Array.isArray(value.cases) || value.cases.length > 100) throw liveFail();
  const seen = new Set<string>();
  return value.cases.map(item => {
    if (!record(item) || typeof item.run_id !== 'string' || !/^run_[a-f0-9]{32}$/.test(item.run_id) ||
        seen.has(item.run_id) || !safeText(item.reference, 160) || typeof item.state !== 'string' ||
        !Object.hasOwn(liveStateLabels, item.state) || typeof item.webhook_verified !== 'boolean' ||
        !Number.isInteger(item.ticket_count) || Number(item.ticket_count) < 0 || Number(item.ticket_count) > 10000) throw liveFail();
    seen.add(item.run_id);
    for (const field of ['model_cost_usd', 'cost_usd']) if (Object.hasOwn(item, field) && item[field] !== null &&
      (typeof item[field] !== 'number' || !Number.isFinite(item[field]) || item[field] < 0)) throw liveFail();
    const payment = utcTime(item.payment_completed_at), deadline = utcTime(item.deadline), ticket = utcTime(item.ticket_created_at);
    if ((item.payment_completed_at !== null && !payment) || (item.deadline !== null && !deadline) ||
        (item.ticket_created_at !== null && !ticket) || Boolean(payment) !== Boolean(deadline) ||
        (payment && deadline && deadline.micros !== payment.micros + 60_000_000n) ||
        (Number(item.ticket_count) === 0 ? ticket !== null : !ticket) ||
        (ticket && (!payment || ticket.micros < payment.micros))) throw liveFail();
    let verdict: TimingRow['verdict'] = null, reason = '';
    if (item.verdict !== null) {
      if (!record(item.verdict) || !['PASS', 'FAIL', 'INCONCLUSIVE'].includes(String(item.verdict.verdict)) ||
          !safeText(item.verdict.signature, 160) || !safeText(item.verdict.reason, 4000)) throw liveFail();
      verdict = item.verdict.verdict as Exclude<TimingRow['verdict'], null>; reason = item.verdict.reason;
    }
    const missing = payment !== null && item.ticket_count === 0;
    const elapsed = payment && deadline ? Math.max(0, Math.min(now, deadline.epochMs) - payment.epochMs) : 0;
    return {
      id: item.run_id, reference: item.reference, title: 'Your USD 29 Sandbox checkout', mode: 'LIVE_SANDBOX',
      modeLabel: 'LIVE SANDBOX', state: item.state, stateLabel: liveStateLabels[item.state],
      sourceLabel: 'Your session’s payment and delivery records', verdict,
      verdictLabel: verdict === 'PASS' ? 'Promise kept' : verdict === 'FAIL' ? 'Promise broken' : verdict === 'INCONCLUSIVE' ? 'Needs more information' : 'Not checked yet',
      verdictReason: reason, paymentAt: payment?.text ?? null, paymentEpochMs: payment?.epochMs ?? null,
      deadlineAt: deadline?.text ?? null, ticketOffsetsMs: ticket && payment ? [Number(ticket.micros - payment.micros) / 1000] : [],
      ticketTimes: ticket ? [ticket.text] : [], ticketCount: Number(item.ticket_count), timingAvailable: payment !== null,
      timingStatus: !payment ? 'Waiting for payment confirmation.' : missing ? 'Payment confirmed; no ticket recorded.' : 'Showing the recorded ticket time.',
      gapOffsetMs: elapsed, missingPaidCase: missing, webhookVerified: item.webhook_verified,
    };
  });
}
