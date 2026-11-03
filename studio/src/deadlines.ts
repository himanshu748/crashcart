import { Scheduler } from '@bryntum/scheduler-community';
import { StringHelper, LocaleHelper } from '@bryntum/core-community';
import { parseRunList, projectDetail } from './deadlines-model';
import type { RunSummary, TimingRow } from './deadlines-model';
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
const casePattern = /^run_[a-f0-9]{32}$/;
let rows: TimingRow[] = [];
let scheduler: Scheduler | null = null;
let active: AbortController | null = null;
let generation = 0;
let selected = new URLSearchParams(location.search).get('run');
let latestScope = '';

const seconds = (ms: number) => (ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 6 });
const moment = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' }) : 'Not recorded';
const path = (id: string, records = false) => (records ? '/studio/index.html?run=' : '/?run=') + encodeURIComponent(id);
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

class AccessRequired extends Error {}
async function savedJson(url: string, signal: AbortSignal): Promise<unknown> {
  const response = await fetch(url, { signal, credentials: 'same-origin', headers: { Accept: 'application/json' } });
  if (response.status === 401 || response.status === 403) throw new AccessRequired();
  if (!response.ok) throw new Error('Saved records unavailable');
  const body = await response.text();
  if (body.length > 4 * 1024 * 1024) throw new Error('Saved record is too large');
  return JSON.parse(body) as unknown;
}
function unavailable(run: RunSummary): TimingRow {
  return { ...run, verdict: null, verdictLabel: 'Result unavailable', verdictReason: 'This saved record could not be loaded.',
    paymentAt: null, paymentEpochMs: null, ticketOffsetsMs: [], ticketTimes: [], ticketCount: null,
    timingStatus: 'Timing unavailable. Open the investigation or refresh to try again.', timingAvailable: false };
}
function showDetail(row: TimingRow, focus = false) {
  selected = row.id;
  if (new URLSearchParams(location.search).get('run') !== row.id) history.replaceState(null, '', '/deadlines/index.html?run=' + encodeURIComponent(row.id));
  element('timing-detail-title').textContent = 'Case ' + row.reference;
  element('timing-detail-promise').textContent = row.title;
  element('timing-detail-source').textContent = row.sourceLabel + '. ' + row.modeLabel + '.';
  const facts = element('timing-detail-facts');
  facts.replaceChildren();
  const addFact = (label: string, value: string) => {
    const pair = document.createElement('div');
    pair.append(text('dt', label), text('dd', value));
    facts.append(pair);
  };
  addFact('Saved result', row.verdictLabel);
  addFact('Payment confirmed', moment(row.paymentAt));
  addFact('Recorded tickets', row.ticketCount === null ? 'Not available' : String(row.ticketCount));
  addFact('Ticket timing', row.ticketOffsetsMs.length ? row.ticketOffsetsMs.map(ms => seconds(ms) + ' seconds after payment').join('; ') : row.timingStatus);
  addFact('Recorded check', row.verdictReason || 'No delivery check is saved.');
  element<HTMLAnchorElement>('timing-open-case').href = path(row.id);
  element<HTMLAnchorElement>('timing-open-records').href = path(row.id, true);
  detail.hidden = false;
  if (focus) element('timing-detail-title').focus();
}
function createChart(visible: TimingRow[]) {
  scheduler?.destroy();
  scheduler = null;
  element('timing-chart').replaceChildren();
  const horizon = Number(range.value) * 1000;
  const events = visible.flatMap(row => row.timingAvailable ? [
    { id: row.id + '-window', resourceId: row.id, name: 'Promised delivery window', startDate: new Date(anchor), endDate: new Date(anchor + 60000), cls: 'delivery-window', readOnly: true },
    ...row.ticketOffsetsMs.flatMap((offset, index) => offset <= horizon ? [{ id: row.id + '-ticket-' + index, resourceId: row.id, name: 'Ticket at ' + seconds(offset) + ' seconds', startDate: new Date(anchor + offset), endDate: new Date(anchor + offset), cls: 'delivery-ticket', readOnly: true }] : []),
  ] : []);
  scheduler = new Scheduler({
    appendTo: element('timing-chart'),
    height: Math.min(520, 100 + Math.max(visible.length, 1) * 80),
    readOnly: true,
    startDate: new Date(anchor), endDate: new Date(anchor + horizon),
    viewPreset: { id: 'delivery-seconds', tickWidth: 80, timeResolution: { unit: 'second', increment: 1 },
      headers: [{ unit: 'second', increment: horizon === 120000 ? 15 : 30, renderer: (start: Date) => String((start.getTime() - anchor) / 1000) + 's' }] },
    rowHeight: 80,
    barMargin: 6,
    eventLayout: 'pack',
    columns: [{ text: 'Saved investigation', field: 'name', width: 260, sortable: false,
      renderer: ({ value }: { value: unknown }) => StringHelper.encodeHtml(String(value)) }],
    resources: visible.map(row => ({ id: row.id, name: 'Case ' + row.reference + ' / ' + row.verdictLabel })),
    events,
    features: { eventEdit: false, eventDrag: false, eventDragCreate: false, eventResize: false, eventMenu: false,
      scheduleMenu: false, cellEdit: false, eventTooltip: false, scheduleTooltip: false, timeAxisHeaderMenu: false, headerMenu: false, cellMenu: false },
    eventRenderer: ({ eventRecord, renderData }) => {
      renderData.ariaLabel = String(eventRecord.name) + '. Press Enter for case details.';
      return StringHelper.encodeHtml(String(eventRecord.name));
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
    const button = text('button', 'Case ' + row.reference, 'case-select') as HTMLButtonElement;
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
  status.textContent = visible.length + ' of ' + rows.length + ' saved investigations. ' + latestScope;
  const chosen = visible.find(row => row.id === selected);
  if (chosen) showDetail(chosen); else detail.hidden = true;
}
async function load() {
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
  status.textContent = 'Loading saved investigations…';
  resultPanel.setAttribute('aria-busy', 'true');
  try {
    const listed = parseRunList(await savedJson('/api/runs', controller.signal));
    const limited = listed.slice(0, 60);
    const requested = listed.find(run => run.id === selected);
    if (requested && !limited.some(run => run.id === requested.id)) limited[limited.length - 1] = requested;
    const loaded: TimingRow[] = [];
    let incomplete = 0;
    for (let i = 0; i < limited.length; i += 4) {
      const batch = await Promise.all(limited.slice(i, i + 4).map(async run => {
        try { return projectDetail(await savedJson('/api/runs/' + encodeURIComponent(run.id), controller.signal), run.id); }
        catch (error) { if (error instanceof AccessRequired || controller.signal.aborted) throw error; incomplete++; return unavailable(run); }
      }));
      loaded.push(...batch);
    }
    if (myGeneration !== generation) return;
    rows = loaded;
    latestScope = (listed.length > 60 ? 'Up to 60 records shown, including the selected case. ' : '') + (incomplete ? incomplete + (incomplete === 1 ? ' record could not be loaded. ' : ' records could not be loaded. ') : '') + 'Refresh reads saved records; it makes no new payment.';
    resultPanel.hidden = false;
    render();
  } catch (error) {
    if (myGeneration !== generation) return;
    const timedOut = controller.signal.aborted;
    controller.abort();
    scheduler?.destroy(); scheduler = null;
    rows = []; tableBody.replaceChildren(); detail.hidden = true; resultPanel.hidden = true;
    element('timing-error-copy').textContent = error instanceof AccessRequired ? 'Open your workspace with its private access key, then return to delivery timing.' : timedOut ? 'The records took too long to load. Try again or open the workspace.' : 'The saved records could not be read. Try again or inspect the original investigation.';
    errorPanel.hidden = false;
    status.textContent = error instanceof AccessRequired ? 'Workspace access required.' : 'Delivery timing is unavailable.';
  } finally {
    clearTimeout(timer);
    if (myGeneration === generation) { refresh.disabled = false; search.disabled = false; outcome.disabled = false; range.disabled = false; resultPanel.setAttribute('aria-busy', 'false'); }
  }
}
let filterTimer: ReturnType<typeof setTimeout>;
search.addEventListener('input', () => { clearTimeout(filterTimer); filterTimer = setTimeout(render, 160); });
outcome.addEventListener('change', render);
range.addEventListener('change', render);
refresh.addEventListener('click', load);
element('timing-retry').addEventListener('click', load);
window.addEventListener('pagehide', () => { ++generation; active?.abort(); scheduler?.destroy(); clearTimeout(filterTimer); });
window.addEventListener('pageshow', event => { if (event.persisted) void load(); });
if (selected && !casePattern.test(selected)) selected = null;
void load();
