/* CrashCart public pages: Home, Product and Integrations. Purely local:
   no fetch, no payment, no PayPal or AI request. demo.html uses app.js instead. */
(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);
  const root = document.documentElement;

  /* ---------- Motion: OS setting or the page toggle, remembered on these pages ---------- */
  const MOTION_KEY = 'crashcart-reduce-motion';
  const media = window.matchMedia('(prefers-reduced-motion: reduce)');
  const toggle = byId('reduce-motion');
  const remembered = () => { try { return window.localStorage.getItem(MOTION_KEY) === '1'; } catch { return false; } };
  const remember = (on) => { try { window.localStorage.setItem(MOTION_KEY, on ? '1' : '0'); } catch { /* storage blocked: still works for this page */ } };
  const reduced = () => root.classList.contains('reduce-motion');
  function applyMotion() { root.classList.toggle('reduce-motion', media.matches || (toggle ? toggle.checked : false)); }
  if (toggle) {
    toggle.checked = media.matches || remembered();
    toggle.addEventListener('change', () => { remember(toggle.checked); applyMotion(); if (reduced()) stopPlay(); });
  }
  media.addEventListener?.('change', () => { if (media.matches && toggle) toggle.checked = true; applyMotion(); if (reduced()) stopPlay(); });
  applyMotion();

  /* ---------- Product: the 60-second rule, as an illustration ---------- */
  // Times are illustrative. The rule is the real one: exactly one ticket
  // within 60 seconds of the completed payment.
  const DEADLINE = 60, END = 90;
  const scenarios = {
    lost: {
      tickets: [],
      store: 'Never heard back from PayPal',
      hint: 'PayPal says the money arrived, but the store never acted on it. Look the payment up directly with PayPal, then find the step where the store stopped waiting for a reply.',
    },
    lookup: {
      tickets: [8],
      store: 'Looked the payment up itself',
      hint: 'Nothing to chase. The store checked the payment directly and issued one ticket in time.',
    },
    late: {
      tickets: [75],
      store: 'Delivery was held up',
      hint: 'The ticket exists, so the store did hear about the payment. Look at what held it up between payment and issue.',
    },
    twice: {
      tickets: [8, 11],
      store: 'Handled the payment notice twice',
      hint: 'Two tickets for one payment. Check whether the store processed the same payment notice more than once.',
    },
  };

  const sim = byId('sim');
  let scenario = 'lost', t = END, frame = 0, lastStamp = 0, announced = '';

  function stateAt(s, time) {
    const issued = s.tickets.filter((x) => x <= time);
    if (issued.length > 1) return 'broken';
    if (issued.length === 1) return issued[0] <= DEADLINE ? 'kept' : 'late';
    return time <= DEADLINE ? 'waiting' : 'broken';
  }

  function copyFor(s, state, time) {
    const issued = s.tickets.filter((x) => x <= time).length;
    const store = issued === 0 ? (time <= DEADLINE ? 'No ticket yet' : 'No ticket')
      : issued === 1 ? `1 ticket at ${s.tickets[0]}s` : `${issued} tickets`;
    const promise = {
      waiting: [time === DEADLINE ? 'Check again' : `${DEADLINE - Math.floor(time)}s left`, 'Waiting for one ticket.'],
      kept: ['Kept', 'Exactly one ticket, inside 60 seconds.'],
      broken: ['Broken', issued > 1 ? 'More than one ticket for one payment.' : 'No ticket inside 60 seconds.'],
      late: ['Broken', 'A ticket came, but after the deadline.'],
    }[state];
    const verdict = {
      waiting: ['Waiting for delivery', 'No ticket is recorded yet. Check the store again before deciding whether delivery is late.'],
      kept: ['Promise kept', 'Payment complete, one ticket, on time. No delivery issue in these records.'],
      broken: ['Paid, but not delivered as promised', issued > 1 ? 'The customer was sent more than one ticket for a single payment.' : 'The customer paid and is still waiting. This is the case CrashCart exists to catch.'],
      late: ['Delivered late', 'The customer did get a ticket, but after the 60 seconds you promised. That still counts as broken.'],
    }[state];
    return {store, promise, verdict};
  }

  const pct = (v) => `${(Math.min(Math.max(v, 0), END) / END) * 100}%`;

  function renderSim() {
    if (!sim) return;
    const s = scenarios[scenario];
    const state = stateAt(s, t);
    const copy = copyFor(s, state, t);
    sim.dataset.state = state;
    byId('sim-fill').style.transform = `scaleX(${Math.min(Math.max(t, 0), END) / END})`;
    byId('sim-now').style.transform = `translateX(${pct(t)})`;
    const mark = byId('sim-ticket');
    mark.style.left = s.tickets.length ? pct(s.tickets[0]) : '100%';
    mark.textContent = s.tickets.length > 1 ? `Ticket ×${s.tickets.length}` : s.tickets.length ? 'Ticket' : 'No ticket';
    mark.classList.toggle('is-issued', s.tickets.length > 0 && t >= s.tickets[0]);
    const range = byId('sim-time');
    range.value = String(Math.round(t));
    range.setAttribute('aria-valuetext', `${Math.round(t)} seconds after payment`);
    byId('sim-clock').textContent = `${Math.round(t)}s`;
    byId('sim-store').textContent = copy.store;
    byId('sim-store-note').textContent = s.store;
    byId('sim-promise').textContent = copy.promise[0];
    byId('sim-promise-note').textContent = copy.promise[1];
    const showHint = state === 'broken' || state === 'late';
    // Announce only when the verdict changes, not on every slider step.
    const key = `${scenario}:${state}`;
    if (key !== announced) {
      announced = key;
      byId('sim-verdict-title').textContent = copy.verdict[0];
      byId('sim-verdict-body').textContent = copy.verdict[1];
      byId('sim-hint').hidden = !showHint;
      byId('sim-hint-text').textContent = s.hint;
    }
  }

  function setPlayLabel(playing) {
    const button = byId('sim-play');
    button.textContent = playing ? 'Pause' : 'Play from payment';
    button.setAttribute('aria-pressed', String(playing));
  }
  function stopPlay() {
    if (!frame) return;
    cancelAnimationFrame(frame);
    frame = 0;
    if (sim) setPlayLabel(false);
  }
  function step(stamp) {
    const dt = lastStamp ? (stamp - lastStamp) / 1000 : 0;
    lastStamp = stamp;
    t = Math.min(END, t + dt * 15); // 90 illustrated seconds in six real ones
    renderSim();
    if (t >= END) { frame = 0; setPlayLabel(false); return; }
    frame = requestAnimationFrame(step);
  }
  function play() {
    if (frame) { stopPlay(); return; }
    if (t >= END) t = 0;
    if (reduced()) { t = END; renderSim(); return; }
    lastStamp = 0;
    setPlayLabel(true);
    frame = requestAnimationFrame(step);
  }

  if (sim) {
    byId('sim-controls').hidden = false;
    document.querySelectorAll('[data-scenario]').forEach((button) => button.addEventListener('click', () => {
      if (!Object.prototype.hasOwnProperty.call(scenarios, button.dataset.scenario)) return;
      scenario = button.dataset.scenario;
      document.querySelectorAll('[data-scenario]').forEach((b) => b.setAttribute('aria-pressed', String(b === button)));
      renderSim();
    }));
    byId('sim-time').addEventListener('input', (event) => { stopPlay(); t = Number(event.target.value) || 0; renderSim(); });
    byId('sim-play').addEventListener('click', play);
    renderSim();
  }

  /* ---------- Integrations: filter by where each piece runs ---------- */
  const filters = document.querySelectorAll('[data-int-filter]');
  const cards = document.querySelectorAll('.int-card[data-where]');
  function applyFilter(value) {
    let shown = 0;
    cards.forEach((card) => {
      const match = value === 'all' || card.dataset.where.split(' ').includes(value);
      card.hidden = !match;
      if (match) shown += 1;
    });
    filters.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.intFilter === value)));
    const count = byId('int-count');
    if (count) count.textContent = `Showing ${shown} of ${cards.length}`;
  }
  if (filters.length && cards.length) {
    byId('int-tools').hidden = false;
    filters.forEach((b) => b.addEventListener('click', () => applyFilter(b.dataset.intFilter)));
    applyFilter('all');
  }
})();
