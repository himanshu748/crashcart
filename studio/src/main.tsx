import React, {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createRoot } from "react-dom/client";
import { AgStudio, AgStudioProvider, createWidgets } from "ag-studio-react";
import type { AgWidgetDefinition } from "ag-studio-react";
import { AgStudioAiModule, createAiHarness, studioTheme } from "ag-studio";
import type {
  AgDefaultRegistry,
  AgReportState,
  AgWidgetData,
  AgWidgetDataFormat,
  AgWidgetParams,
  AgAiHarness,
  AgAiHarnessSetup,
  AgStudioApi,
} from "ag-studio";
import { INITIAL_QUERY, QueryController, queryDataSource } from "./query-agent";
import type { QueryState } from "./query-agent";
import { QueryContext, QueryWidget, testTypeLabel } from "./query-widget";
import { recordedApi, recordedQuery, recordedRecords } from "./recorded";
import type { RecordedRecords } from "./recorded";
import "./style.css";

// Explicit build values only; no server configuration is exported.
declare const __CRASHCART_AG_STUDIO_LICENSE_KEY__: string | undefined;
declare const __CRASHCART_RECORDED_STUDIO__: boolean;
const recorded = __CRASHCART_RECORDED_STUDIO__;

type Run = {
  id: string;
  promise: string;
  mode: string;
  state: string;
  fault: { kind: string; merchant: string };
};
type Event = {
  id: string;
  source: string;
  event_type: string;
  observed_at: string;
  event_time: string;
  caused_by: string | null;
  payload: Record<string, unknown>;
};
type Ticket = { id: string; created_at: string };
type Detail = {
  run: Run;
  purchase: {
    id: string;
    order_id: string | null;
    capture_id: string | null;
    payment_state: string;
    payment_confirmed: number;
  };
  merchant: {
    known: boolean;
    ticket_count: number | null;
    status: string;
    observed_at: string;
    tickets: Ticket[];
  };
  events: Event[];
};
const words = (x: unknown) => (typeof x === "string" ? x : "Not recorded");
const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value);
function validateRun(v: unknown): Run {
  if (!isRecord(v)) throw Error("Malformed run");
  const r = v;
  if (
    typeof r.id !== "string" ||
    !/^run_[a-f0-9]{32}$/.test(r.id) ||
    typeof r.promise !== "string" ||
    !r.promise.trim() ||
    r.promise.length > 4000 ||
    typeof r.mode !== "string" ||
    ![
      "LOCAL_TEST",
      "LIVE_SANDBOX",
      "RECORDED_REPLAY",
      "FRESH_SANDBOX",
    ].includes(r.mode) ||
    typeof r.state !== "string" ||
    !r.state ||
    !isRecord(r.fault) ||
    typeof r.fault.kind !== "string" ||
    !r.fault.kind ||
    typeof r.fault.merchant !== "string" ||
    !["healthy", "defective"].includes(r.fault.merchant)
  )
    throw Error("Malformed run identity");
  return r as Run;
}
function validateRuns(value: unknown): Run[] {
  if (!isRecord(value) || !Array.isArray(value.runs))
    throw Error("Malformed investigation list");
  const runs = value.runs.map(validateRun);
  if (new Set(runs.map((run) => run.id)).size !== runs.length)
    throw Error("Duplicate investigation identity");
  return runs;
}
function validateDetail(v: unknown, id: string): Detail {
  if (!v || typeof v !== "object") throw Error("Malformed evidence");
  const d = v as Detail;
  validateRun(d.run);
  if (
    d.run.id !== id ||
    typeof d.purchase?.id !== "string" ||
    typeof d.merchant?.known !== "boolean" ||
    !Array.isArray(d.merchant.tickets) ||
    !Array.isArray(d.events) ||
    !d.events.every(
      (e) =>
        typeof e.id === "string" &&
        typeof e.event_type === "string" &&
        typeof e.source === "string" &&
        typeof e.observed_at === "string" &&
        e.payload &&
        typeof e.payload === "object",
    )
  )
    throw Error("Evidence identity or shape mismatch");
  return d;
}
async function api(path: string, body?: object) {
  if (recorded) return recordedApi(path, body);
  const r = await fetch(
    path,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  const v = await r.json();
  if (!r.ok) throw Error(v.error || "Request failed");
  return v as unknown;
}
const Context = createContext<{
  primary: Detail | null;
  comparison: Detail | null;
  source: string;
  setSource: (s: string) => void;
}>({ primary: null, comparison: null, source: "all", setSource: () => {} });
const last = (d: Detail, type: string) =>
  [...d.events].reverse().find((e) => e.event_type === type);
const verdict = (d: Detail) => last(d, "invariant_result")?.payload;
const browserLabel = (value: unknown) => value === "LOCAL_BROWSER" ? "Recorded local browser" : value === "KERNEL" ? "Recorded remote browser" : value ? "Unrecognized browser source" : "Browser source not recorded";
const sourceLabel = (value: string) => ({browser:"Browser",provider:"PayPal",merchant:"Store",harness:"Test controls",checker:"Promise check",investigator:"Assistant",model:"Assistant"})[value] || "Other source";
const faultLabel = (value: string) => ({none:"No simulated problem",response_loss:"Payment reply lost",event_delay:"Ticket delivery delayed",event_duplicate:"Repeated delivery message",process_interrupt:"Store interrupted during checkout"})[value] || "Unrecognized test condition";
const versionLabel = (value: string) => value === "healthy" ? "Recovery enabled" : value === "defective" ? "Checkout with a known fault" : "Checkout version not recorded";
const generatedTitles = new Map([
  ['Fresh repair verification: recover a lost capture response and issue exactly one ticket.','Check the repair: recover a lost payment response and issue exactly one ticket.'],
  ['Lost capture response: payment completed but the workshop ticket is missing.','Lost payment response: payment completed but the workshop ticket is missing.'],
  ['Recover a real sandbox payment after the merchant process exits before ticket delivery, preserving exactly one ticket within 60 seconds.','Recover a test payment after the store stops before delivery, with exactly one ticket within 60 seconds.'],
  ['A completed USD 29 payment must produce exactly one workshop ticket within 60 seconds. Early independent read, then deadline verification.','A completed USD 29 payment must produce exactly one workshop ticket within 60 seconds. Check payment status, then check delivery at the deadline.'],
  ['LOCAL_TEST UI interaction: one workshop ticket within 60 seconds; unpaid fixture, no provider call.','Example case: one workshop ticket within 60 seconds; no payment made.'],
]);
const displayPromise = (value: string) => generatedTitles.get(value) ?? String(value ?? '');
const caseLabel = (run: Run) => recorded ? (run.fault.merchant === "defective" ? "Missed delivery — payment confirmed, no ticket" : "Repair replay — one ticket in 32.26 seconds") : `${testTypeLabel(run.mode)} · Case ${run.id.slice(-8)} — ${displayPromise(run.promise)}`;
const timeLabel = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value)) ? new Date(value).toLocaleString(undefined,{month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",second:"2-digit",timeZoneName:"short"}) : "Time not recorded";
const outcomeLabel = (value: unknown) => value === "PASS" ? "Promise kept" : value === "FAIL" ? "Promise broken" : "More information needed";
const eventLabel = (value: string) => ({customer_observation:"Page recorded",order_created:"Checkout started",pre_capture_read:"Payment checked before confirmation",fault_activated:"Test condition started",capture_transport_response:"Payment reply received",customer_message:"Store message saved",independent_order_read:"Payment checked with PayPal",ticket_fulfilled:"Ticket issued",entitlement_read:"Ticket checked with the store",invariant_result:"Delivery promise checked",fault_deactivated:"Test condition ended",attempt_started:"Case check started",attempt_completed:"Case check finished",run_cancelled:"Case stopped",webhook_received:"PayPal update received"})[value] || "Saved event";
const readableError = (value: string) => value === "Operator access required" ? "Enter your access code to open this workspace." : value === "Invalid operator token" || value.startsWith("Invalid") ? "That access code was not accepted. Try again." : "The records could not be loaded. Refresh and try again.";
function OriginalRecords({value,label="Technical details"}:{value:unknown;label?:string}) {return <details className="original-records"><summary>{label}</summary><pre>{JSON.stringify(value,null,2)}</pre></details>;}
function Identity({ data }: { data: Detail }) {
  return <p className="identity"><span>{testTypeLabel(data.run.mode)}</span><span className="case-reference">Case {data.run.id.slice(-8)}</span></p>;
}
function Result({ data }: { data: Detail }) {
  const v=verdict(data);
  return <div className={"result "+words(v?.verdict).toLowerCase()}><b>{outcomeLabel(v?.verdict)}</b><p>{v?.verdict === "PASS" ? "One ticket arrived within the promised time after payment." : v?.verdict === "FAIL" ? "The saved payment and delivery records do not meet the promise." : "More payment or delivery information is needed to check the promise."}</p><OriginalRecords value={v||null} label="Technical details" /></div>;
}
function EvidenceWidget({ widgetId }: AgWidgetParams) {
  const { primary:d,comparison,source,setSource }=useContext(Context);
  if(!d)return <section className="widget empty">Choose a case to see its payment and delivery records.</section>;
  if(widgetId === "customer") {
    const e=[...d.events].reverse().find(e=>e.source === "browser");
    const path=typeof e?.payload.url_path === "string" ? e.payload.url_path : "";
    const view=path === "/" ? "Case page" : path === "/shop" ? "Store page" : path === "/return" ? "Payment return page" : "Recorded page";
    return <section className="widget" aria-label="Browser record"><p className="kicker"><span className="source-index">01</span> BROWSER</p><h2>{e ? "What the page showed" : "No page saved yet"}</h2>
      {e&&<p className="browser-origin"><strong>{view}</strong><span>{browserLabel(e.payload.browser_kind)}</span></p>}
      <p>{e ? "See the page text saved with this case." : "No page has been saved for this case."}</p>
      <p className="meta">{e ? `Recorded ${timeLabel(e.observed_at)}` : "A payment record does not show what appeared in the browser."}</p>
      {e&&typeof e.payload.visible_text === "string"&&e.payload.visible_text.length>0&&<blockquote>{e.payload.visible_text.slice(0,180)}</blockquote>}
      {e&&<><details className="original-browser"><summary>Original page text</summary><blockquote>{words(e.payload.visible_text)}</blockquote></details><OriginalRecords value={e} /></>}
    </section>;
  }
  if(widgetId === "payment") {
    const e=last(d,"independent_order_read");
    return <section className="widget" aria-label="Payment record"><p className="kicker"><span className="source-index">02</span> PAYPAL</p><h2>{d.purchase.payment_confirmed===1 ? "Payment confirmed" : e ? "Payment still being checked" : "Payment not checked yet"}</h2>
      <div className="number">{d.purchase.payment_confirmed===1 ? "$29.00" : "—"}<span>USD · test ticket price</span></div>
      <p className="meta">{e ? `Checked ${timeLabel(e.observed_at)}` : "No payment check has been saved."}</p><p>Refreshing this page reads saved records. It does not contact PayPal.</p>
      <OriginalRecords value={{purchase:d.purchase,check:e||null}} />
    </section>;
  }
  if(widgetId === "merchant")return <section className="widget" aria-label="Ticket record"><p className="kicker"><span className="source-index">03</span> STORE</p><h2>{d.merchant.known ? "Ticket delivery" : "Purchase not found"}</h2><div className="number">{d.merchant.ticket_count??"—"}<span>{d.merchant.ticket_count===1 ? "workshop ticket" : "workshop tickets"}</span></div>
    {d.merchant.tickets.map(t=><div className="ticket" key={t.id}><strong><span aria-hidden="true">↳</span> Ticket issued</strong><details><summary>Ticket reference</summary><code>{t.id}</code></details><small>Issued {timeLabel(t.created_at)}</small></div>)}
    {d.merchant.ticket_count===0&&<p>No ticket is saved for this purchase.</p>}<p className="meta">{recorded ? "Replay loaded " : "Store checked "}{timeLabel(d.merchant.observed_at)}</p><OriginalRecords value={{purchase_id:d.purchase.id,...d.merchant}} />
  </section>;
  if(widgetId === "comparison")return <section className="widget" aria-label="Checkout comparison"><p className="kicker"><span className="source-index">04</span> COMPARE CHECKOUTS</p><h2>Compare checkout outcomes</h2><div className="compare"><div><h3>Selected case</h3><Identity data={d}/><Result data={d}/><p>{faultLabel(d.run.fault.kind)} · {versionLabel(d.run.fault.merchant)}</p></div><div><h3>Comparison case</h3>{comparison ? <><Identity data={comparison}/><Result data={comparison}/><p>{faultLabel(comparison.run.fault.kind)} · {versionLabel(comparison.run.fault.merchant)}</p></> : <p>Choose another case above to compare payment and delivery.</p>}</div></div><p className="meta">The promise is one $29 ticket within 60 seconds of confirmed payment. Two selected checkouts may have different test conditions.</p></section>;
  const visible=d.events.filter(e=>source === "all" || e.source === source);
  return <section className="widget trace" aria-label="Case timeline"><div className="trace-head"><div><p className="kicker"><span className="source-index">05</span> TIMELINE</p><h2>What happened, and when</h2></div><label>Show records from<select aria-label="Show records from" value={source} onChange={e=>setSource(e.target.value)}><option value="all">All sources</option>{[...new Set(d.events.map(e=>e.source))].map(value=><option key={value} value={value}>{sourceLabel(value)}</option>)}</select></label></div><p className="meta">{visible.length} of {d.events.length} saved activities. Open an activity for its details.</p><ol>{visible.map(e=><li key={e.id}><span className={"event-source "+e.source}>{sourceLabel(e.source)}</span><details><summary>{eventLabel(e.event_type)}<time>{timeLabel(e.observed_at)}</time></summary><p>Recorded {timeLabel(e.observed_at)}. {e.caused_by ? "An earlier event is linked in the original record." : "No earlier event is linked."}</p><OriginalRecords value={e}/></details></li>)}</ol></section>;
}

type Def = AgWidgetDefinition<
  "case-evidence",
  AgWidgetData<Record<string, never>, AgWidgetDataFormat<unknown>>
>;
type QueryDef = AgWidgetDefinition<
  "query-results",
  { type: "query-results" } & AgWidgetData<
    Record<string, never>,
    AgWidgetDataFormat<unknown>
  >
>;
interface Registry extends Omit<AgDefaultRegistry, "widgets"> {
  widgets: readonly [...AgDefaultRegistry["widgets"], Def, QueryDef];
}
const widgets = createWidgets<Registry>({
  additionalTypes: [
    {
      id: "case-evidence",
      label: "Payment and delivery records",
      form: (p) => p.createDefaults({}),
      comp: EvidenceWidget,
      defaultSize: { width: 400, height: 300 },
      minSize: { width: 220, height: 220 },
      toolbar: [],
    },
    {
      id: "query-results",
      label: "Answers",
      form: (p) => p.createDefaults({}),
      comp: QueryWidget,
      defaultSize: { width: 600, height: 650 },
      minSize: { width: 220, height: 300 },
      toolbar: [],
    },
  ],
});
const theme = studioTheme.withParams({
  accentColor: "#17191c",
  backgroundColor: "#f7f7f2",
  foregroundColor: "#17191c",
  borderColor: "#deded8",
  fontFamily: "system-ui, sans-serif",
  fontSize: 13,
  studioMinWidth: 280,
});
function pageState(mobile: boolean): AgReportState<Registry> {
  const items = ["customer", "payment", "merchant", "comparison", "timeline"];
  return {
    selectedPageId: "evidence",
    pages: [
      {
        id: "evidence",
        widgets: Object.fromEntries(
          items.map((id) => [id, { type: "case-evidence", dataMapping: {} }]),
        ),
        widgetLayout: mobile
          ? Object.fromEntries(
              items.map((id, i) => [
                id,
                {
                  xTrack: 0,
                  yTrack: i < 3 ? i * 18 : i === 3 ? 54 : 94,
                  xSpan: 24,
                  ySpan: i < 3 ? 18 : i === 3 ? 40 : 24,
                },
              ]),
            )
          : {
              customer: { xTrack: 0, yTrack: 0, xSpan: 8, ySpan: 19 },
              payment: { xTrack: 8, yTrack: 0, xSpan: 8, ySpan: 19 },
              merchant: { xTrack: 16, yTrack: 0, xSpan: 8, ySpan: 19 },
              comparison: { xTrack: 0, yTrack: 19, xSpan: 24, ySpan: 20 },
              timeline: { xTrack: 0, yTrack: 39, xSpan: 24, ySpan: 30 },
            },
        layout: {
          minWidth: 280,
          columns: 24,
          rowHeight: 20,
          pagePadding: 12,
          widgetPadding: 8,
          backgroundColor: "#f7f7f2",
          widgetBackgroundColor: "#ffffff",
          widgetBorderEnabled: true,
          widgetBorderColor: "#deded8",
          widgetBorderRadius: 10,
        },
      },
      {
        id: "queries",
        widgets: { query: { type: "query-results", dataMapping: {} } },
        widgetLayout: { query: { xTrack: 0, yTrack: 0, xSpan: 24, ySpan: 26 } },
        layout: {
          minWidth: 280,
          columns: 24,
          rowHeight: 20,
          pagePadding: 12,
          widgetPadding: 8,
          widgetBackgroundColor: "#ffffff",
          widgetBorderEnabled: true,
          widgetBorderColor: "#deded8",
          widgetBorderRadius: 10,
        },
      },
    ],
    panels: {
      data: { collapsed: true },
      filters: { collapsed: true },
      ai: { collapsed: true, width: mobile ? 320 : 360 },
    },
  };
}
function App() {
  const [runs, setRuns] = useState<Run[]>([]),
    [selected, setSelected] = useState(
      new URLSearchParams(location.search).get("run") || "",
    ),
    [compare, setCompare] = useState(""),
    [primary, setPrimary] = useState<Detail | null>(null),
    [comparison, setComparison] = useState<Detail | null>(null),
    [source, setSource] = useState("all"),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [ready, setReady] = useState(false),
    [login, setLogin] = useState(false),
    [token, setToken] = useState(""),
    [updated, setUpdated] = useState(""),
    [revision, setRevision] = useState(0),
    [mobile, setMobile] = useState(innerWidth < 850),
    [query, setQuery] = useState<QueryState>(INITIAL_QUERY),
    [queryOpen, setQueryOpen] = useState(false),
    [chatOpen, setChatOpen] = useState(false);
  const generation = useRef(0);
  const studioApi = useRef<AgStudioApi | null>(null);
  const harness = useRef<AgAiHarness | null>(null);
  const scope = useRef({ runId: selected, ready: false });
  scope.current = {
    runId: selected,
    ready: !!primary && !loading && primary.run.id === selected,
  };
  const [recording, setRecording] = useState<RecordedRecords | null>(null);
  useEffect(() => { if (recorded) recordedRecords().then(setRecording).catch(() => {}); }, []);
  const controller = useMemo(
    () => new QueryController(() => scope.current, setQuery, recorded ? recordedQuery : undefined),
    [],
  );
  const invalidateQuery = () => {
    for (const thread of harness.current?.threads || [])
      harness.current?.getSession?.(thread.threadId)?.cancel();
    controller.invalidate();
  };
  useEffect(() => {
    invalidateQuery();
  }, [primary, runs, mobile]);
  useEffect(() => () => controller.invalidate(), [controller]);
  const ai = useMemo<AgAiHarnessSetup>(
    () =>
      ({ api }) => {
        const next = createAiHarness(api, () => ({
          agents: [controller.runner],
          primary: controller.runner.id,
          promptStarters: [
            {
              label: "Paid, ticket missing",
              prompt: "Show completed payments with no stored tickets.",
            },
            {
              label: "Delivered tickets",
              prompt: "Show investigations with exactly one delivered ticket.",
            },
          ],
        }));
        harness.current = next;
        return next;
      },
    [controller],
  );
  const showWorkspace = (queries: boolean, openChat = queries) => {
    setQueryOpen(queries);
    setChatOpen(openChat);
    if (queries)
      requestAnimationFrame(() =>
        document
          .querySelector(".workspace-tabs")
          ?.scrollIntoView({ block: "start", behavior: "instant" }),
      );
    const api = studioApi.current;
    if (api) {
      const current = api.getState();
      api.setState({
        ...current,
        selectedPageId: queries ? "queries" : "evidence",
        panels: {
          ...current.panels,
          ai: { width: mobile ? 320 : 360, collapsed: !openChat },
        },
      });
    }
  };
  useEffect(() => {
    const api = studioApi.current;
    if (api && ready) {
      const current = api.getState();
      api.setState({
        ...current,
        selectedPageId: queryOpen ? "queries" : "evidence",
        panels: {
          ...current.panels,
          ai: { width: mobile ? 320 : 360, collapsed: !chatOpen },
        },
      });
    }
  }, [queryOpen, chatOpen, mobile, ready]);
  useEffect(() => {
    const m = matchMedia("(max-width:849px)");
    const f = () => setMobile(m.matches);
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  useEffect(() => {
    let disposed = false;
    api("/api/runs")
      .then((v) => {
        const r = validateRuns(v);
        if (!disposed) {
          setRuns(r);
          setLogin(false);
          if (!selected && r[0]) { setSelected(r[0].id); if (recorded && r[1]) setCompare(r[1].id); }
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!disposed) {
          setError(e.message);
          setLogin(e.message === "Operator access required");
          setLoading(false);
        }
      });
    return () => {
      disposed = true;
    };
  }, [revision]);
  useEffect(() => {
    const n = ++generation.current;
    setPrimary(null);
    setComparison(null);
    setSource("all");
    if (!selected) return;
    setLoading(true);
    setError("");
    history.replaceState(null, "", `?run=${selected}`);
    Promise.all([
      api(`/api/runs/${selected}`),
      compare ? api(`/api/runs/${compare}`) : Promise.resolve(null),
    ])
      .then(([a, b]) => {
        if (n !== generation.current) return;
        setPrimary(validateDetail(a, selected));
        setComparison(b ? validateDetail(b, compare) : null);
        setUpdated(new Date().toLocaleTimeString());
        setLoading(false);
      })
      .catch((e) => {
        if (n === generation.current) {
          setError(e.message);
          setLoading(false);
        }
      });
  }, [selected, compare, revision]);
  const data = useMemo(
    () => ({
      sources: [
        queryDataSource(query.receipt),
        {
          id: "investigations",
          fields: runs.length
            ? undefined
            : ["runId", "promise", "mode", "state", "fault", "merchant"].map(
                (id) => ({ id, format: "textFormat" as const }),
              ),
          data: runs.map((r) => ({
            runId: r.id,
            promise: r.promise,
            mode: r.mode,
            state: r.state,
            fault: r.fault.kind,
            merchant: r.fault.merchant,
          })),
        },
        {
          id: "events",
          fields: primary?.events.length
            ? undefined
            : [
                ...["eventId", "runId", "source", "type"].map((id) => ({
                  id,
                  format: "textFormat" as const,
                })),
                { id: "observedAt", format: "dateTimeFormat" as const },
              ],
          data: (primary?.events || []).map((e) => ({
            eventId: e.id,
            runId: primary!.run.id,
            source: e.source,
            type: e.event_type,
            observedAt: e.observed_at,
          })),
        },
      ],
      description:
        "Saved checkout investigations. Test checkouts and saved replays are separate. Event times alone do not explain causes.",
    }),
    [runs, primary, query.receipt],
  );
  const state = useMemo(() => {
    const s = pageState(mobile);
    return { ...s, selectedPageId: queryOpen ? "queries" : "evidence" };
  }, [mobile]);
  const canReplay =
    primary?.run.fault.merchant === "defective" &&
    ["response_loss", "process_interrupt"].includes(primary.run.fault.kind) &&
    primary.purchase.payment_confirmed === 1 &&
    !!primary.purchase.order_id &&
    !!primary.purchase.capture_id &&
    primary.merchant.known &&
    primary.merchant.ticket_count === 0 &&
    primary.merchant.tickets.length === 0 &&
    verdict(primary)?.verdict === "FAIL" &&
    verdict(primary)?.signature === "paid_without_ticket" &&
    !!last(primary, "independent_order_read") &&
    !!last(primary, "capture_transport_response");
  return (
    <>
      <a className="skip" href="#main">
        Skip to checkout records
      </a>
      <header>
        <a className="brand" href={recorded ? "/" : selected ? `/?view=home&run=${encodeURIComponent(selected)}` : "/?view=home"}>
          <span className="brand-mark" aria-hidden="true">↳</span> CrashCart <span className="brand-label">RECORDS</span>
        </a>
        <span className="header-scope"><span aria-hidden="true" />Test payments only · saved records</span>
        <a className="back" href={recorded ? "/example" : selected ? `/?run=${selected}` : "/"}>
          {recorded ? "Recorded example" : "Workspace"}
        </a>
      </header>
      <main id="main">
        <div className="heading">
          <div>
            <p className="kicker">PAYMENTS & DELIVERY</p>
            <h1>Follow the payment. Find the ticket.</h1>
            <p>
              See what happened at checkout, confirm the saved payment details and check ticket delivery.
            </p>
          </div>
          <div className="contract">
            <span>THE DELIVERY PROMISE</span>
            <strong><b>1</b> ticket <i aria-hidden="true">/</i> $29 <i aria-hidden="true">/</i> 60 seconds</strong>
            <p>From confirmed payment</p>
          </div>
        </div>
        {recorded && <aside className="recorded-notice" aria-label="About these records">
          <div><strong>Recorded checkout explorer</strong><p>Two versions of the same saved input. No new payment, AI call or store connection. AG Studio powers this workspace.</p></div>
          <a href="/demo.html#investigation">See the guided walkthrough ↗</a>
        </aside>}
        {recorded && recording && <details className="recorded-history"><summary>Where AI helped — a separate saved investigation</summary>
          <p>This earlier checkout was captured on 23 October; AI investigated it on 26 October. It is a different case from the missed order on 22 October and the live test on 8 November.</p>
          <p>{recording.historical_ai.provider} · {recording.historical_ai.model}. These are saved steps, not a conversation with a model now.</p>
          <ol>{recording.historical_ai.trace.map(step => <li key={step.step}><strong>{({read_provider:"Check the PayPal payment",read_merchant:"Check the ticket",finish:"Return to the promise check"})[step.action] || "Saved step"}</strong><p>{step.reasoning_summary || step.exact_model_excerpt}</p></li>)}</ol>
          <p>The model proposed what to inspect. Deterministic code checked payment and delivery. <a href="https://github.com/himanshu748/crashcart/blob/main/docs/LIVE_FLOW.md">Read about the separate 8 November live test.</a></p>
        </details>}
        {error && (
          <p role="alert" className="error">
            {readableError(error)}
          </p>
        )}
        {login ? (
          <form
            className="login"
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api("/api/login", { token });
                setToken("");
                setError("");
                setRevision((v) => v + 1);
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            <label>
              Workspace access key
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <button>Open saved records</button>
          </form>
        ) : (
          <>
            <div className="toolbar" aria-label="Choose records">
              <label>
                Case
                <select
                  aria-label="Case"
                  value={selected}
                  onChange={(e) => {
                    invalidateQuery();
                    const next = e.target.value;
                    if (recorded) setCompare(runs.find(run => run.id !== next)?.id || "");
                    else if (next === compare) setCompare("");
                    setSelected(next);
                  }}
                >
                  <option value="" disabled>
                    Choose a case
                  </option>
                  {runs.map((r) => (
                    <option value={r.id} key={r.id}>
                      {caseLabel(r)}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Compare with
                <select
                  aria-label="Compare with"
                  value={compare}
                  onChange={(e) => {
                    invalidateQuery();
                    setCompare(e.target.value);
                  }}
                >
                  <option value="">No comparison selected</option>
                  {runs
                    .filter((r) => r.id !== selected)
                    .map((r) => (
                      <option value={r.id} key={r.id}>
                        {caseLabel(r)}
                      </option>
                    ))}
                </select>
              </label>
              <button
                disabled={loading}
                onClick={() => {
                  invalidateQuery();
                  setRevision((v) => v + 1);
                }}
              >
                Refresh records
              </button>
            </div>
            <div className="status" role="status">
              {loading
                ? "Loading saved records…"
                : `${runs.length} saved cases · refreshed ${updated || "just now"} · ${ready ? "Ready" : "Loading workspace"}`}
            </div>
            {primary && (
              <div className="case-strip">
                <div className="selected-identity"><p className="selection-label">SELECTED CASE</p><Identity data={primary} /><OriginalRecords value={primary.run} /></div>
                <div>
                  <a download href={recorded ? `/downloads/${primary.run.fault.merchant}.json` : `/api/runs/${selected}/export`}>
                    Download records ↓
                  </a>
                  {canReplay && (
                    <a download href={recorded ? "/downloads/replay.zip" : `/api/runs/${selected}/regression.zip`}>
                      Download checkout replay ↓
                    </a>
                  )}
                </div>
              </div>
            )}
            <div className="workspace-tabs">
              <button
                aria-pressed={!queryOpen}
                onClick={() => showWorkspace(false)}
              >
                Compare records
              </button>
              <button
                aria-pressed={queryOpen}
                onClick={() => showWorkspace(true)}
              >
                {recorded ? "Explore saved cases" : "Ask a question"}
              </button>
              {queryOpen && chatOpen && (
                <button onClick={() => showWorkspace(true, false)}>
                  Show answers
                </button>
              )}
              {queryOpen && query.status === "running" && (
                <span className="meta">
                  Stopping an answer may still use part of your assistant allowance.
                </span>
              )}
            </div>
            {recorded && queryOpen && <div className="recorded-query-note"><strong>Local record filters, not live AI</strong><p>Use the suggested questions in the panel. The native Studio Agent Framework runs a browser filter over these two cases. Other questions are unavailable; no model or private API is called.</p></div>}
            <QueryContext.Provider value={query}>
              <Context.Provider
                value={{ primary, comparison, source, setSource }}
              >
                <div
                  className={
                    "studio-shell" + (queryOpen ? " query-workspace" : "")
                  }
                >
                  <AgStudioProvider modules={[AgStudioAiModule]} licenseKey={__CRASHCART_AG_STUDIO_LICENSE_KEY__}>
                    <AgStudio<Registry>
                      key={mobile ? "mobile" : "desktop"}
                      style={{ width: "100%", height: "100%" }}
                      theme={theme}
                      loadThemeGoogleFonts={false}
                      styleNonce={
                        document.querySelector<HTMLMetaElement>(
                          'meta[name="csp-nonce"]',
                        )?.content
                      }
                      mode={queryOpen ? "edit" : "view"}
                      panels={{
                        edit: { left: [], right: ["ai"] },
                        view: { left: [], right: [] },
                      }}
                      ai={ai}
                      widgets={widgets}
                      data={data}
                      initialState={state}
                      onApiReady={({ api }) => {
                        studioApi.current = api;
                      }}
                      onStudioReady={() => setReady(true)}
                    />
                  </AgStudioProvider>
                </div>
              </Context.Provider>
            </QueryContext.Provider>
          </>
        )}
      </main>
      <footer>
        <span>Test payments only · no real charges</span>
        <span>Showing saved payment and delivery records</span>
      </footer>
    </>
  );
}
function LicenseGate() {
  return <main className="license-gate"><a className="brand" href="/">↳ CrashCart</a><p className="kicker">RECORDED CHECKOUT EXPLORER</p><h1>Studio access is not configured.</h1><p>This optional workspace needs an AG Studio licence configured by its owner. The recorded walkthrough works without one.</p><a className="back" href="/example">Open the recorded example</a></main>;
}
createRoot(document.getElementById("root")!).render(recorded && !__CRASHCART_AG_STUDIO_LICENSE_KEY__ ? <LicenseGate /> : <App />);
