import { Scheduler } from '@bryntum/scheduler-community';
import { StringHelper, LocaleHelper } from '@bryntum/core-community';
import type { TimingRow } from './deadlines-model';
import { publicTimingRows, liveTimingRows } from './public-timing-model';
import type { LiveTimingRow } from './public-timing-model';
type ChartRow = TimingRow | LiveTimingRow;
document.documentElement.classList.add('public-timing');
import '@bryntum/scheduler-community/scheduler.css';
import '@bryntum/scheduler-community/stockholm.css';
import '@bryntum/core-community/fontawesome/css/fontawesome.css';
import '@bryntum/core-community/fontawesome/css/solid.css';
import './deadlines.css';

const element = <T extends HTMLElement>(id: string) => {
  const value = document.getElementById(id);
  if (!value) throw new Error('Delivery view is incomplete. Reload the workspace.');
  return value as T;
};
const status = element('timing-status');
const errorPanel = element('timing-error');
const resultPanel = element('timing-results');
const tableBody = element<HTMLTableSectionElement>('timing-rows');
const search = element<HTMLInputElement>('timing-search');
const outcome = element<HTMLSelectElement>('timing-outcome');
const range = element<HTMLSelectElement>('timing-range');
const refresh = element<HTMLButtonElement>('timing-refresh');
const detail = element('timing-detail');
const anchor = Date.UTC(2000, 0, 1); // Projection coordinate only; never a recorded timestamp.
const compactChart = window.matchMedia('(max-width: 720px)');
let rows: ChartRow[] = [];
let liveMode = false;
let pollUntil = 0;
let pollTimer: ReturnType<typeof setTimeout>;
const liveButton = element<HTMLButtonElement>('timing-load-live');
const savedButton = element<HTMLButtonElement>('timing-load-saved');
const isLive = (row: ChartRow): row is LiveTimingRow => row.mode === 'LIVE_SANDBOX';
function stopPolling() { clearTimeout(pollTimer); pollUntil = 0; }
let scheduler: Scheduler | null = null;
let active: AbortController | null = null;
let generation = 0;
let selected: string | null = null;
let latestScope = '';

const seconds = (ms: number) => (ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 6 });
const moment = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' }) : 'Not recorded';
const path = (row: ChartRow, records = false) => isLive(row) ? 'live.html?run=' + encodeURIComponent(row.id) : records ? 'downloads/replay.zip' : 'demo.html#investigation';
const label = (row: ChartRow) => row.reference;
const text = (tag: string, value: string, className?: string) => {
  const node = document.createElement(tag);
  node.textContent = value;
  if (className) node.className = className;
  return node;
};

// The chart has a relative axis. Do not expose its artificial coordinate date to assistive technology.
LocaleHelper.publishLocale({ localeName: 'En', localeDesc: 'English', localeCode: 'en-US',
  TimeAxisColumn: { ariaLabel: () => 'Delivery timing in seconds after confirmed payment' },
});

async function savedJson(url: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error('Saved records unavailable');
  const body = await response.text();
  if (body.length > 4 * 1024 * 1024) throw new Error('Saved record is too large');
  return JSON.parse(body) as unknown;
}
function showDetail(row: ChartRow, focus = false) {
  selected = row.id;
  element('timing-detail-title').textContent = label(row);
  element('timing-detail-promise').textContent = row.title;
  element('timing-detail-source').textContent = row.sourceLabel + '. ' + row.modeLabel + '.';
  const facts = element('timing-detail-facts');
  facts.replaceChildren();
  const addFact = (label: string, value: string) => {
    const pair = document.createElement('div');
    pair.append(text('dt', label), text('dd', value));
    facts.append(pair);
  };
  addFact(isLive(row) ? 'Delivery result' : 'Saved result', row.verdictLabel);
  if (isLive(row)) {
    addFact('Checkout status', row.stateLabel);
    addFact('Payment notification', row.webhookVerified ? 'Signature verified' : 'Not verified yet');
    addFact('Delivery deadline', moment(row.deadlineAt));
  }
  addFact('Payment confirmed', moment(row.paymentAt));
  addFact('Tickets', row.ticketCount === null ? 'Not available' : String(row.ticketCount));
  addFact('Delivery time', row.ticketOffsetsMs.length ? row.ticketOffsetsMs.map(ms => seconds(ms) + ' seconds after payment').join('; ') : row.timingStatus);
  const check = document.createElement('div');
  const explanation = document.createElement('dd');
  const technical = document.createElement('details');
  technical.append(text('summary', 'Technical details'), text('p', row.verdictReason || 'No delivery check is saved.'));
  explanation.append(technical);
  check.append(text('dt', 'Delivery check'), explanation);
  facts.append(check);
  element<HTMLAnchorElement>('timing-open-case').href = path(row);
  element('timing-open-case').textContent = isLive(row) ? 'Open this Sandbox checkout' : 'Inspect both outcomes';
  element<HTMLAnchorElement>('timing-open-records').href = path(row, true);
  element('timing-open-records').hidden = isLive(row);
  detail.hidden = false;
  if (focus) element('timing-detail-title').focus();
}
function createChart(visible: ChartRow[]) {
  scheduler?.destroy();
  scheduler = null;
  element('timing-chart').replaceChildren();
  const horizon = Number(range.value) * 1000;
  const compact = compactChart.matches;
  const events = visible.flatMap(row => row.timingAvailable ? [
    { id: row.id + '-window', resourceId: row.id, name: 'Promised delivery window', startDate: new Date(anchor), endDate: new Date(anchor + 60000), cls: 'delivery-window', readOnly: true },
    ...(isLive(row) && row.missingPaidCase && row.gapOffsetMs > 0 ? [{ id: row.id + '-gap', resourceId: row.id, name: 'Paid; no ticket recorded · ' + seconds(row.gapOffsetMs) + 's observed', startDate: new Date(anchor), endDate: new Date(anchor + row.gapOffsetMs), cls: 'delivery-gap', readOnly: true }] : []),
    ...row.ticketOffsetsMs.flatMap((offset, index) => offset <= horizon ? [{ id: row.id + '-ticket-' + index, resourceId: row.id, name: 'Ticket at ' + seconds(offset) + ' seconds', startDate: new Date(anchor + offset), endDate: new Date(anchor + offset), cls: 'delivery-ticket', readOnly: true }] : []),
  ] : []);
  scheduler = new Scheduler({
    appendTo: element('timing-chart'),
    height: Math.min(520, 100 + Math.max(visible.length, 1) * 80),
    readOnly: true,
    forceFit: compact,
    startDate: new Date(anchor), endDate: new Date(anchor + horizon),
    viewPreset: { id: 'delivery-seconds', tickWidth: 80, timeResolution: { unit: 'second', increment: 1 },
      headers: [{ unit: 'second', increment: horizon === 120000 ? (compact ? 30 : 15) : (compact ? 60 : 30), renderer: (start: Date) => String((start.getTime() - anchor) / 1000) + 's' }] },
    rowHeight: 80,
    barMargin: 6,
    eventLayout: 'pack',
    columns: [{ text: 'Case', field: 'name', width: compact ? 104 : 260, sortable: false,
      renderer: ({ value }: { value: unknown }) => StringHelper.encodeHtml(String(value)) }],
    resources: visible.map(row => ({ id: row.id, name: compact ? label(row) : label(row) + ' / ' + row.verdictLabel })),
    events,
    features: { eventEdit: false, eventDrag: false, eventDragCreate: false, eventResize: false, eventMenu: false,
      scheduleMenu: false, cellEdit: false, eventTooltip: false, scheduleTooltip: false, timeAxisHeaderMenu: false, headerMenu: false, cellMenu: false },
    eventRenderer: ({ eventRecord, renderData }) => {
      renderData.ariaLabel = String(eventRecord.name) + '. Press Enter for case details.';
      const ticket = compact && String(eventRecord.id).includes('-ticket-');
      const gap = String(eventRecord.id).includes('-gap');
      const name = ticket ? 'Ticket · ' + ((eventRecord.startDate.getTime() - anchor) / 1000).toFixed(2) + 's' : gap && compact ? 'No ticket yet' : compact ? '60s' : String(eventRecord.name);
      return StringHelper.encodeHtml(name);
    },
    listeners: { eventClick: ({ eventRecord }) => {
      const row = visible.find(item => item.id === String(eventRecord.resourceId));
      if (row) showDetail(row, true);
    }, eventKeyDown: ({ eventRecords, event }) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      const record = eventRecords[0];
      const row = record && visible.find(item => item.id === String(record.resourceId));
      if (row) { event.preventDefault(); showDetail(row, true); }
    } },
  });
}
function render() {
  const term = search.value.trim().toLocaleLowerCase();
  const visible = rows.filter(row => (!term || (row.title + ' ' + row.reference + ' ' + row.modeLabel).toLocaleLowerCase().includes(term)) &&
    (outcome.value === 'all' || (outcome.value === 'unknown' ? row.verdict === null || row.verdict === 'INCONCLUSIVE' : row.verdict === outcome.value)));
  tableBody.replaceChildren();
  element('timing-empty').hidden = visible.length > 0;
  element('timing-chart-shell').hidden = visible.length === 0;
  element('timing-table-wrap').hidden = visible.length === 0;
  if (visible.length) createChart(visible); else { scheduler?.destroy(); scheduler = null; }
  for (const row of visible) {
    const tr = document.createElement('tr');
    const identity = document.createElement('td');
    const button = text('button', label(row), 'case-select') as HTMLButtonElement;
    button.type = 'button'; button.addEventListener('click', () => showDetail(row, true));
    identity.append(button, text('span', row.title, 'timing-promise'), text('span', row.modeLabel, 'timing-meta'), text('span', row.verdictLabel, 'mobile-result saved-result ' + (row.verdict || 'unknown').toLowerCase()));
    const result = document.createElement('td');
    result.append(text('span', row.verdictLabel, 'saved-result ' + (row.verdict || 'unknown').toLowerCase()));
    const ticket = document.createElement('td');
    ticket.append(text('span', row.ticketOffsetsMs.length ? row.ticketOffsetsMs.map(ms => seconds(ms) + 's').join(', ') : row.ticketCount === 0 ? 'No ticket recorded' : 'Timing unavailable'));
    ticket.append(text('span', row.timingAvailable ? String(row.ticketCount) + (row.ticketCount === 1 ? ' ticket recorded' : ' tickets recorded') : row.timingStatus, 'timing-meta'));
    tr.append(identity, result, ticket);
    tableBody.append(tr);
  }
  status.textContent = visible.length + ' of ' + rows.length + (liveMode ? ' Sandbox cases. ' : ' saved cases. ') + latestScope;
  element('timing-empty').textContent = liveMode ? 'No Sandbox cases match. Open the Sandbox workspace to start a test checkout, or switch to the saved comparison.' : 'No cases match. Try another search or result filter.';
  const chosen = visible.find(row => row.id === selected);
  if (chosen) showDetail(chosen); else detail.hidden = true;
}
function describeMode(live: boolean) {
  liveMode = live;
  element('timing-gap-legend').hidden = !live;
  element('timing-mode').textContent = live ? 'LIVE SANDBOX · your browser’s cases' : 'SAVED REPLAY · 22 October 2026 comparison';
  element('timing-disclosure').textContent = live ? 'This view reads your checkout records. It does not start a payment or ask the AI. Automatic status refresh stops after eight minutes.' : 'The 22 October repair comparison is separate from the 8 November AI investigation. Saved records only; no new payment or AI call.';
  refresh.textContent = live ? 'Refresh my Sandbox cases' : 'Reload recorded comparison';
  element('timing-result-label').textContent = live ? 'Delivery result' : 'Saved result';
  element('timing-table-result').textContent = live ? 'Delivery result' : 'Saved result';
  element('timing-intro-copy').textContent = live ? 'Your own Sandbox checkouts, from confirmed payment to recorded ticket delivery. Each order keeps the original 60-second promise.' : 'One saved payment, two merchant rules. Compare the missing ticket with one delivered in 32.26 seconds, inside the same 60-second promise.';
  search.placeholder = live ? 'Sandbox checkout reference' : 'Missed or recovered order';
  liveButton.setAttribute('aria-pressed', String(live));
  savedButton.setAttribute('aria-pressed', String(!live));
}
async function load() {
  stopPolling();
  describeMode(false);
  clearTimeout(filterTimer);
  const myGeneration = ++generation;
  active?.abort();
  active = new AbortController();
  const controller = active;
  const timer = setTimeout(() => controller.abort(), 30000);
  refresh.disabled = true;
  search.disabled = true;
  outcome.disabled = true;
  range.disabled = true;
  errorPanel.hidden = true;
  status.textContent = 'Loading saved cases…';
  resultPanel.setAttribute('aria-busy', 'true');
  try {
    rows = publicTimingRows(await savedJson('data.json', controller.signal));
    latestScope = 'Recorded payment and delivery times.';
    resultPanel.hidden = false;
    render();
  } catch (error) {
    if (myGeneration !== generation) return;
    const timedOut = controller.signal.aborted;
    controller.abort();
    scheduler?.destroy(); scheduler = null;
    rows = []; tableBody.replaceChildren(); detail.hidden = true; resultPanel.hidden = true;
    element('timing-error-copy').textContent = timedOut ? 'The records took too long to load. Try again or open the workspace.' : 'The saved records could not be loaded. Try again or open the case.';
    errorPanel.hidden = false;
    status.textContent = 'Delivery timing is unavailable.';
  } finally {
    clearTimeout(timer);
    if (myGeneration === generation) { refresh.disabled = false; search.disabled = false; outcome.disabled = false; range.disabled = false; resultPanel.setAttribute('aria-busy', 'false'); }
  }
}
function scheduleLivePoll() {
  clearTimeout(pollTimer);
  if (!pollUntil || !liveMode) return;
  if (Date.now() >= pollUntil) { stopPolling(); latestScope = 'Automatic refresh stopped. Refresh manually to check again.'; render(); return; }
  const terminal = new Set(['COMPLETED', 'FAILED', 'CANCELLED', 'EXPIRED']);
  if (!rows.length || rows.every(row => terminal.has(row.state))) { stopPolling(); return; }
  pollTimer = setTimeout(() => {
    if (document.hidden || document.activeElement?.closest('#timing-chart')) scheduleLivePoll();
    else void loadLive(true);
  }, 5000);
}
async function loadLive(poll = false) {
  if (!poll) { stopPolling(); pollUntil = Date.now() + 8 * 60 * 1000; }
  if (poll && (!liveMode || !pollUntil || Date.now() >= pollUntil)) { scheduleLivePoll(); return; }
  const myGeneration = ++generation;
  active?.abort();
  const controller = new AbortController(); active = controller;
  const timer = setTimeout(() => controller.abort(), 10000);
  liveButton.disabled = true;
  resultPanel.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch('/api/live/timing', {signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'application/json'}});
    if (!response.ok) throw new Error([401, 403].includes(response.status) ? 'Open the Sandbox workspace in this browser first.' : 'Sandbox timing is unavailable or paused.');
    const raw = await response.text();
    if (raw.length > 512 * 1024) throw new Error('Sandbox timing response is too large.');
    const projected = liveTimingRows(JSON.parse(raw));
    if (myGeneration !== generation) return;
    rows = projected; describeMode(true); errorPanel.hidden = true; resultPanel.hidden = false;
    latestScope = 'Payment and delivery records from this browser session.';
    render(); scheduleLivePoll();
  } catch (error) {
    if (myGeneration !== generation) return;
    const message = error instanceof Error ? error.message : 'Sandbox timing could not be read.';
    // Static mirrors and paused live workspaces retain the complete saved comparison.
    await load();
    status.textContent += ' ' + message + ' Showing the saved comparison.';
  } finally {
    clearTimeout(timer);
    if (myGeneration === generation || !liveMode) {
      liveButton.disabled = false; resultPanel.setAttribute('aria-busy', 'false');
    }
  }
}
let filterTimer: ReturnType<typeof setTimeout>;
search.addEventListener('input', () => { clearTimeout(filterTimer); filterTimer = setTimeout(render, 160); });
outcome.addEventListener('change', render);
range.addEventListener('change', render);
compactChart.addEventListener('change', () => { if (rows.length) render(); });
refresh.addEventListener('click', () => liveMode ? void loadLive() : void load());
liveButton.addEventListener('click', () => void loadLive());
savedButton.addEventListener('click', () => void load());
element('timing-retry').addEventListener('click', load);
window.addEventListener('pagehide', () => { stopPolling(); ++generation; active?.abort(); scheduler?.destroy(); clearTimeout(filterTimer); });
window.addEventListener('pageshow', event => { if (event.persisted) void load(); });
void load();
