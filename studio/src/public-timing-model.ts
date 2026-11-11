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
