import { Scheduler } from '@bryntum/scheduler-community';
import { StringHelper, LocaleHelper } from '@bryntum/core-community';
import type { TimingRow } from './deadlines-model';
import { publicTimingRows } from './public-timing-model';
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
let rows: TimingRow[] = [];
let scheduler: Scheduler | null = null;
let active: AbortController | null = null;
let generation = 0;
let selected: string | null = null;
let latestScope = '';

const seconds = (ms: number) => (ms / 1000).toLocaleString(undefined, { maximumFractionDigits: 6 });
const moment = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit', timeZoneName: 'short' }) : 'Not recorded';
const path = (_id: string, records = false) => records ? 'downloads/replay.zip' : 'demo.html#investigation';
const label = (row: TimingRow) => row.reference;
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
function showDetail(row: TimingRow, focus = false) {
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
  addFact('Saved result', row.verdictLabel);
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
    columns: [{ text: 'Case', field: 'name', width: 260, sortable: false,
      renderer: ({ value }: { value: unknown }) => StringHelper.encodeHtml(String(value)) }],
    resources: visible.map(row => ({ id: row.id, name: label(row) + ' / ' + row.verdictLabel })),
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
  status.textContent = visible.length + ' of ' + rows.length + ' saved cases. ' + latestScope;
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
  status.textContent = 'Loading saved cases…';
  resultPanel.setAttribute('aria-busy', 'true');
  try {
    rows = publicTimingRows(await savedJson('data.json', controller.signal));
    latestScope = 'Recorded 22 October comparison. No payment, AI request or private workspace access.';
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
let filterTimer: ReturnType<typeof setTimeout>;
search.addEventListener('input', () => { clearTimeout(filterTimer); filterTimer = setTimeout(render, 160); });
outcome.addEventListener('change', render);
range.addEventListener('change', render);
refresh.addEventListener('click', load);
element('timing-retry').addEventListener('click', load);
window.addEventListener('pagehide', () => { ++generation; active?.abort(); scheduler?.destroy(); clearTimeout(filterTimer); });
window.addEventListener('pageshow', event => { if (event.persisted) void load(); });
void load();
