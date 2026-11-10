import type { QueryReceipt, QueryRow } from "./query-agent";

/** Read-only browser adapter. No private API, model, storage or write transport. */
export type RecordedRecords = {
  version: "recorded-studio-v1";
  runs: { id: string }[];
  details: Record<string, unknown>;
  rows: QueryRow[];
  dataset_sha256: string;
  snapshot_at: string;
  historical_ai: {
    investigation_started_at: string;
    historical_capture_date: string;
    provider: string;
    model: string;
    trace: { step: number; action: string; reasoning_summary?: string; exact_model_excerpt?: string }[];
  };
};
let pending: Promise<RecordedRecords> | undefined;
export function recordedRecords(): Promise<RecordedRecords> {
  if (!pending) pending = fetch("./records.json", { credentials: "omit" })
    .then(async response => {
      if (!response.ok) throw Error("RECORDED_DATA_UNAVAILABLE");
      const value = await response.json() as RecordedRecords;
      if (value.version !== "recorded-studio-v1" || !Array.isArray(value.runs) ||
          !Array.isArray(value.rows) || !value.details ||
          !/^[a-f0-9]{64}$/.test(value.dataset_sha256) ||
          value.rows.some(row => row.mode !== "RECORDED_REPLAY"))
        throw Error("INVALID_RECORDED_DATA");
      return value;
    }).catch(error => { pending = undefined; throw error; });
  return pending;
}

export async function recordedApi(path: string, body?: object): Promise<unknown> {
  if (body) throw Error("RECORDED_VIEW_IS_READ_ONLY");
  const data = await recordedRecords();
  if (path === "/api/runs") return { runs: data.runs };
  const id = path.match(/^\/api\/runs\/(run_[a-f0-9]{32})$/)?.[1];
  if (!id || !Object.hasOwn(data.details, id)) throw Error("RECORDED_CASE_NOT_FOUND");
  return data.details[id];
}

// These explicit browser filters are not a model investigating a new checkout.
export function filterRecorded(data: RecordedRecords, question: string, runId: string, requestId: string): QueryReceipt {
  if (!data.runs.some(run => run.id === runId)) throw Error("RECORDED_CASE_NOT_FOUND");
  const known = new Map([
    ["show completed payments with no stored tickets.", "completed_missing_tickets"],
    ["show investigations with exactly one delivered ticket.", "delivered"],
    ["show all saved cases.", "all"],
  ]);
  const query = known.get(question.trim().toLowerCase()) ?? "unsupported";
  const rows = data.rows.filter(row => query === "all" ||
    (query === "completed_missing_tickets" && row.payment_confirmed === 1 && row.payment_state === "COMPLETED" && row.ticket_count === 0) ||
    (query === "delivered" && row.ticket_count === 1));
  return {
    version: "studio-query-v1", request_id: requestId, run_id: runId,
    attempt_id: "attempt_studio_" + requestId.replaceAll("-", ""),
    status: query === "unsupported" ? "UNSUPPORTED" : "COMPLETED",
    model_mode: "RECORDED_FILTER",
    model: { configured: "none", actual: "Browser filter — no model call", response_id: requestId, usage: null },
    plan: { query, mode: "RECORDED_REPLAY" },
    dataset_sha256: data.dataset_sha256, snapshot_at: data.snapshot_at,
    rows, count: rows.length, cached: false,
    summary: {
      matching_runs: rows.length, scope_runs: data.rows.length,
      completed_payments: rows.filter(row => row.payment_confirmed === 1 && row.payment_state === "COMPLETED").length,
      ticket_count: rows.reduce((sum, row) => sum + row.ticket_count, 0),
      description: "Filtered locally from the two recorded checkout variants.",
      scope_note: "Recorded input only. No PayPal, AI or private workspace request.",
    },
  };
}

export async function recordedQuery(runId: string, requestId: string, question: string, signal: AbortSignal): Promise<unknown> {
  const data = await recordedRecords();
  signal.throwIfAborted();
  return filterRecorded(data, question, runId, requestId);
}
