import type {
  AgAiAgentRunner,
  AgAiRunInput,
  AgAiAgentRunContext,
  AgAiEvent,
} from "ag-studio";

const MODES = [
  "LOCAL_TEST",
  "LIVE_SANDBOX",
  "RECORDED_REPLAY",
  "FRESH_SANDBOX",
];
const QUERIES = [
  "all",
  "completed",
  "completed_missing_tickets",
  "unresolved",
  "delivered",
  "unsupported",
];
const record = (v: unknown): v is Record<string, any> =>
  !!v && typeof v === "object" && !Array.isArray(v);
const text = (v: unknown): v is string =>
  typeof v === "string" && v.length > 0 && v.length <= 4000;
const count = (v: unknown): v is number =>
  Number.isSafeInteger(v) && Number(v) >= 0;
const optionalId = (v: unknown) => v === null || text(v);
export type QueryRow = {
  run_id: string;
  mode: string;
  payment_state: string;
  payment_confirmed: number;
  purchase_id: string;
  amount: number;
  currency: string;
  order_id: string | null;
  capture_id: string | null;
  ticket_count: number;
  ticket_id: string | null;
  source_ids: {
    browser_event_id: string | null;
    provider_event_id: string | null;
    merchant_event_id: string | null;
    invariant_event_id: string | null;
  };
};
export type QueryReceipt = {
  version: string;
  request_id: string;
  run_id: string;
  attempt_id: string;
  status: "COMPLETED" | "UNSUPPORTED";
  model_mode: "LOCAL_TEST" | "LIVE_MODEL";
  model: {
    configured: string;
    actual: string;
    response_id: string;
    usage: Record<string, number> | null;
  };
  plan: { query: string; mode: string };
  dataset_sha256: string;
  snapshot_at: string;
  rows: QueryRow[];
  count: number;
  cached: boolean;
  summary: {
    matching_runs: number;
    scope_runs: number;
    completed_payments: number;
    ticket_count: number;
    description: string;
    scope_note: string;
  };
};
export type QueryState = {
  status: "idle" | "running" | "complete" | "blocked" | "error" | "cancelled";
  message: string;
  receipt: QueryReceipt | null;
  errorCode?: string;
};
export const INITIAL_QUERY: QueryState = {
  status: "idle",
  message: "Ask the assistant about your saved investigations.",
  receipt: null,
};

export const queryLabel = (query: string) =>
  ({
    all: "All saved investigations",
    completed: "Completed payments",
    completed_missing_tickets: "Completed payments without tickets",
    unresolved: "Payments still being checked",
    delivered: "Delivered tickets",
    unsupported: "Unsupported question",
  })[query] || "Unsupported question";

/** Accept a correlated terminal receipt, never model-authored counts or a payment verdict. */
export function validateReceipt(
  value: unknown,
  runId: string,
  requestId: string,
): QueryReceipt {
  const fail = () => {
    throw new Error("INVALID_QUERY_RECEIPT");
  };
  if (!record(value)) return fail();
  const r = value;
  if (
    r.version !== "studio-query-v1" ||
    r.run_id !== runId ||
    r.request_id !== requestId ||
    r.attempt_id !== "attempt_studio_" + requestId.replaceAll("-", "") ||
    !["COMPLETED", "UNSUPPORTED"].includes(r.status) ||
    !["LOCAL_TEST", "LIVE_MODEL"].includes(r.model_mode) ||
    !record(r.model) ||
    ![r.model.configured, r.model.actual, r.model.response_id].every(text) ||
    !(
      r.model.usage === null ||
      (record(r.model.usage) &&
        Object.entries(r.model.usage).every(
          ([k, v]) =>
            ["input_tokens", "output_tokens", "total_tokens"].includes(k) &&
            count(v),
        ))
    ) ||
    !record(r.plan) ||
    !QUERIES.includes(r.plan.query) ||
    !["ANY", ...MODES].includes(r.plan.mode) ||
    (r.status === "UNSUPPORTED") !== (r.plan.query === "unsupported") ||
    typeof r.dataset_sha256 !== "string" ||
    !/^[a-f0-9]{64}$/.test(r.dataset_sha256) ||
    !text(r.snapshot_at) ||
    !Number.isFinite(Date.parse(r.snapshot_at)) ||
    !/(Z|[+-]\d\d:\d\d)$/.test(r.snapshot_at) ||
    !Array.isArray(r.rows) ||
    r.rows.length > 200 ||
    r.count !== r.rows.length ||
    typeof r.cached !== "boolean" ||
    !record(r.summary)
  )
    return fail();
  const seen = new Set();
  for (const row of r.rows) {
    if (
      !record(row) ||
      typeof row.run_id !== "string" ||
      !/^run_[a-f0-9]{32}$/.test(row.run_id) ||
      seen.has(row.run_id) ||
      !MODES.includes(row.mode) ||
      (r.plan.mode !== "ANY" && row.mode !== r.plan.mode) ||
      (r.model_mode === "LOCAL_TEST" && row.mode !== "LOCAL_TEST") ||
      !text(row.purchase_id) ||
      !count(row.amount) ||
      !text(row.currency) ||
      !text(row.payment_state) ||
      ![0, 1].includes(row.payment_confirmed) ||
      !count(row.ticket_count) ||
      ![row.order_id, row.capture_id, row.ticket_id].every(optionalId) ||
      !record(row.source_ids) ||
      ![
        "browser_event_id",
        "provider_event_id",
        "merchant_event_id",
        "invariant_event_id",
      ].every((k) => optionalId(row.source_ids[k]))
    )
      return fail();
    const complete =
      row.payment_confirmed === 1 && row.payment_state === "COMPLETED";
    if (
      (r.plan.query === "completed" && !complete) ||
      (r.plan.query === "completed_missing_tickets" &&
        (!complete || row.ticket_count !== 0)) ||
      (r.plan.query === "unresolved" &&
        (row.payment_confirmed !== 0 || row.payment_state !== "UNRESOLVED")) ||
      (r.plan.query === "delivered" && row.ticket_count !== 1) ||
      r.plan.query === "unsupported"
    )
      return fail();
    seen.add(row.run_id);
  }
  const s = r.summary;
  if (
    s.matching_runs !== r.count ||
    !count(s.scope_runs) ||
    s.scope_runs < r.count ||
    s.scope_runs > 200 ||
    s.completed_payments !==
      r.rows.filter(
        (row: QueryRow) =>
          row.payment_confirmed === 1 && row.payment_state === "COMPLETED",
      ).length ||
    s.ticket_count !==
      r.rows.reduce(
        (sum: number, row: QueryRow) => sum + row.ticket_count,
        0,
      ) ||
    !text(s.description) ||
    !text(s.scope_note)
  )
    return fail();
  return r as QueryReceipt;
}

const errorMessage = (code: string) => {
  if (code === "MISSING_OR_INVALID_STUDIO_CALL_ALLOWANCE")
    return "The assistant is unavailable because no usage allowance has been set.";
  if (code.startsWith("MISSING_CONFIGURATION:"))
    return "The assistant is not connected yet. Ask the workspace owner to finish setup.";
  if (code === "MODEL_USAGE_NOT_AUTHORIZED")
    return "The workspace owner has not enabled the assistant yet.";
  if (code === "STUDIO_CALL_BUDGET_EXHAUSTED")
    return "The assistant has reached this workspace’s usage limit.";
  if (code.startsWith("DATASET_"))
    return "Saved records changed. Refresh records and ask again.";
  if (code === "QUESTION_TOO_LONG")
    return "Use a question of 1–2,000 characters.";
  if (code === "NO_READY_INVESTIGATION")
    return "Choose an investigation and wait for its records to load.";
  if (code === "INVALID_QUERY_RECEIPT")
    return "The answer could not be checked, so no results were shown. Try again.";
  return "The assistant could not answer. No results were shown. Try again.";
};
const modeDescription = (mode: string) => ({
  ANY: "all saved test types", LIVE_SANDBOX: "initial test checkouts",
  FRESH_SANDBOX: "new test checkouts after a repair", RECORDED_REPLAY: "saved replays",
  LOCAL_TEST: "simulated test data",
})[mode] || "an unknown test type";

/** One native Studio runner; one bounded server request per message, with no automatic retries. */
export class QueryController {
  private epoch = 0;
  private active: AbortController | null = null;
  constructor(
    private scope: () => { runId: string; ready: boolean },
    private update: (state: QueryState) => void,
  ) {}
  invalidate() {
    ++this.epoch;
    this.active?.abort();
    this.active = null;
    this.update({
      ...INITIAL_QUERY,
      message:
        "The selected records changed. Ask again to use the current records.",
    });
  }
  readonly runner: AgAiAgentRunner = {
    id: "crashcart-saved-records",
    name: "CrashCart records",
    description:
      "Find answers in saved records. Counts come from those records.",
    run: async function* (
      this: QueryController,
      input: AgAiRunInput,
      ctx: AgAiAgentRunContext,
    ): AsyncGenerator<AgAiEvent> {
      const epoch = ++this.epoch;
      this.active?.abort();
      const controller = new AbortController();
      this.active = controller;
      const abort = () => controller.abort();
      ctx.signal?.addEventListener("abort", abort, { once: true });
      if (ctx.signal?.aborted) controller.abort();
      const current = () => epoch === this.epoch && !controller.signal.aborted;
      const { runId, ready } = this.scope();
      const question = [...input.messages]
        .reverse()
        .find((m) => m.role === "user")?.content;
      const requestId = crypto.randomUUID();
      try {
        if (!current()) return;
        yield {
          type: "RUN_STARTED",
          threadId: input.threadId,
          runId: input.runId,
        };
        if (!current()) return;
        if (!ready || !/^run_[a-f0-9]{32}$/.test(runId))
          throw Error("NO_READY_INVESTIGATION");
        if (
          typeof question !== "string" ||
          !question.trim() ||
          question.length > 2000
        )
          throw Error("QUESTION_TOO_LONG");
        this.update({
          status: "running",
          message: "Checking saved records…",
          receipt: null,
        });
        const response = await fetch("/api/studio/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            run_id: runId,
            request_id: requestId,
            question,
          }),
        });
        const value: unknown = await response.json();
        if (!current()) return;
        if (!response.ok)
          throw Error(
            record(value) &&
              typeof value.code === "string" &&
              /^[A-Z0-9_:,]+$/.test(value.code)
              ? value.code
              : "QUERY_REQUEST_FAILED",
          );
        const receipt = validateReceipt(value, runId, requestId);
        this.update({
          status: "complete",
          message:
            receipt.status === "UNSUPPORTED"
              ? "This question is outside the questions these saved records can answer."
              : `${receipt.count} matching investigation${receipt.count === 1 ? "" : "s"}.`,
          receipt,
        });
        const messageId = crypto.randomUUID();
        yield { type: "TEXT_MESSAGE_START", messageId, role: "assistant" };
        if (!current()) return;
        yield {
          type: "TEXT_MESSAGE_CONTENT",
          messageId,
          delta: `${receipt.model_mode === "LOCAL_TEST" ? "Test data · simulated response.\n\n" : ""}${queryLabel(receipt.plan.query)}: ${receipt.count} matching investigation${receipt.count === 1 ? "" : "s"} from ${modeDescription(receipt.plan.mode)}.\n\nThese results describe saved records. A missing ticket alone does not show that its delivery deadline was missed.\n\nResults are ready in the Answers panel. ${receipt.model_mode === "LOCAL_TEST" ? "This is a simulated answer." : "The assistant used the saved records."} Open Technical details there to inspect the original answer and record references.`,
        };
        if (!current()) return;
        yield { type: "TEXT_MESSAGE_END", messageId };
        if (!current()) return;
        yield {
          type: "RUN_FINISHED",
          threadId: input.threadId,
          runId: input.runId,
          result: { request_id: requestId, count: receipt.count },
        };
      } catch (error) {
        if (!current()) return;
        const code =
          error instanceof Error && /^[A-Z0-9_:,]+$/.test(error.message)
            ? error.message
            : "QUERY_TRANSPORT_ERROR";
        const message = errorMessage(code);
        this.update({
          status: /ALLOWANCE|CONFIGURATION|AUTHORIZED|BUDGET_EXHAUSTED/.test(
            code,
          )
            ? "blocked"
            : "error",
          message,
          errorCode: code,
          receipt: null,
        });
        yield { type: "RUN_ERROR", code, message };
      } finally {
        ctx.signal?.removeEventListener("abort", abort);
        if (epoch === this.epoch) {
          this.active = null;
          if (controller.signal.aborted)
            this.update({
              status: "cancelled",
              message:
                "Answer stopped. A request already sent to the assistant may still use part of your allowance.",
              receipt: null,
            });
        }
      }
    }.bind(this),
  };
}

export function queryDataSource(receipt: QueryReceipt | null) {
  return {
    id: "query_results",
    name: "Answers",
    description:
      "Answers from saved records. These counts do not decide whether a delivery promise was kept.",
    fields: [
      ...[
        "run_id",
        "mode",
        "purchase_id",
        "payment_state",
        "order_id",
        "capture_id",
        "ticket_id",
        "request_id",
        "dataset_sha256",
        "model_mode",
        "provider_event_id",
        "merchant_event_id",
        "browser_event_id",
        "invariant_event_id",
      ].map((id) => ({ id, format: "textFormat" as const, editable: false })),
      { id: "ticket_count", format: "integerFormat" as const, editable: false },
      { id: "amount", format: "integerFormat" as const, editable: false },
    ],
    data: receipt
      ? receipt.rows.map((row) => ({
          run_id: row.run_id,
          mode: row.mode,
          purchase_id: row.purchase_id,
          payment_state: row.payment_state,
          order_id: row.order_id,
          capture_id: row.capture_id,
          ticket_id: row.ticket_id,
          ticket_count: row.ticket_count,
          amount: row.amount,
          request_id: receipt.request_id,
          dataset_sha256: receipt.dataset_sha256,
          model_mode: receipt.model_mode,
          ...row.source_ids,
        }))
      : [],
  };
}
