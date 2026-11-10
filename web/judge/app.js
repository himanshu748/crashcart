/* CrashCart recorded example. Reads one relative data.json and nothing else:
   no account, payment, PayPal or AI request is made from this page. */
(() => {
  'use strict';

  const byId = (id) => document.getElementById(id);
  const el = (tag, content, className) => { const n = document.createElement(tag); if (content !== undefined && content !== null) n.textContent = content; if (className) n.className = className; return n; };
  const validTime = (v) => typeof v === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(v) && !Number.isNaN(new Date(v).getTime());
  const instant = (v) => validTime(v) ? new Date(v).toLocaleString(undefined, {dateStyle: 'medium', timeStyle: 'medium', timeZone: 'UTC'}) + ' UTC' : 'Not recorded';
  const day = (v) => validTime(v) ? new Date(v).toLocaleDateString(undefined, {dateStyle: 'long', timeZone: 'UTC'}) : 'an unrecorded date';
  const seconds = (later, earlier) => (new Date(later) - new Date(earlier)) / 1000;
  const duration = (v) => Number.isFinite(v) ? `${v.toFixed(2)} seconds` : 'an unrecorded time';
  const shortDuration = (v) => Number.isFinite(v) ? `${v.toFixed(2)}s` : 'n/a';

  const sourceNames = {provider: 'PayPal', browser: 'Checkout page', merchant: 'Ticket store', harness: 'Connection interruption'};
  const eventNames = {
    customer_observation: 'What the customer saw', order_created: 'Checkout created', pre_capture_read: 'Buyer approval checked',
    fault_activated: 'PayPal’s reply to the store was cut off', fault_deactivated: 'Connection restored', capture_transport_response: 'PayPal’s reply recorded',
    independent_order_read: 'Payment looked up directly with PayPal', entitlement_read: 'Ticket store checked', process_exit_boundary: 'Store stopped mid-delivery',
    capture_completed: 'Payment completed', ticket_created: 'Ticket issued', ticket_issued: 'Ticket issued',
  };

  /* ---------- Motion ---------- */
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  const motionControl = byId('reduce-motion');
  const motionKey = 'crashcart-reduce-motion';
  const rememberedMotion = () => { try { return window.localStorage.getItem(motionKey) === '1'; } catch { return false; } };
  const reduced = () => document.documentElement.classList.contains('reduce-motion');
  function applyMotionPreference() { document.documentElement.classList.toggle('reduce-motion', motionPreference.matches || motionControl.checked); }
  motionControl.checked = motionPreference.matches || rememberedMotion();
  motionControl.addEventListener('change', () => {
    try { window.localStorage.setItem(motionKey, motionControl.checked ? '1' : '0'); } catch { /* The control still works when storage is blocked. */ }
    applyMotionPreference();
  });
  motionPreference.addEventListener?.('change', () => { if (motionPreference.matches) motionControl.checked = true; applyMotionPreference(); });
  applyMotionPreference();

  /* ---------- Validation: refuse partial or mismatched data ---------- */
  const identity = (value) => typeof value === 'string' && value.length > 0 && value === value.trim();
  const digest = (value) => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
  function fixedInvariant(value) {
    const fixed = {version: 'ticket-v1', amount: 2900, currency: 'USD', ticket_count: 1, recovery_seconds: 60};
    return !!value && typeof value === 'object' && Object.keys(value).length === Object.keys(fixed).length
      && Object.entries(fixed).every(([key, expected]) => value[key] === expected);
  }
  function sameMap(left, right) {
    return !!left && !!right && Object.keys(left).length === Object.keys(right).length
      && Object.keys(left).every((key) => Object.prototype.hasOwnProperty.call(right, key) && left[key] === right[key]);
  }
  function validCase(item, source, variant) {
    if (!item || typeof item !== 'object' || item.variant !== variant) return false;
    const {receipt: r, execution: x, purchase: p, merchant: m, events} = item;
    if (!r || !x || !p || !m || !Array.isArray(events)) return false;
    if (r.mode !== 'RECORDED_REPLAY' || r.fresh_execution !== false || r.network_calls !== 0
      || x.mode !== 'RECORDED_REPLAY' || x.network_calls !== 0 || r.merchant_variant !== variant || x.merchant_variant !== variant) return false;
    if (!digest(r.input_sha256) || x.input_sha256 !== r.input_sha256 || !fixedInvariant(x.invariant) || x.invariant_version !== 'ticket-v1') return false;
    const expected = variant === 'healthy' ? ['PASS', 'ticket_delivered_once_on_time', 1] : ['FAIL', 'paid_without_ticket', 0];
    if (r.verdict !== expected[0] || r.signature !== expected[1] || r.ticket_count !== expected[2]
      || x.verdict !== r.verdict || x.signature !== r.signature || x.ticket_count !== r.ticket_count) return false;
    if (!identity(p.id) || !identity(p.run_id) || !identity(p.order_id) || !identity(p.capture_id)
      || r.run_id !== p.run_id || r.purchase_id !== p.id || p.payment_confirmed !== 1 || p.payment_state !== 'COMPLETED'
      || p.amount !== 2900 || p.currency !== 'USD' || !validTime(p.capture_completed_at) || !validTime(x.deadline)
      || new Date(x.deadline).getTime() - new Date(p.capture_completed_at).getTime() !== 60000) return false;
    const mapping = r.identity_mapping, ids = x.source_ids;
    if (!mapping || typeof mapping !== 'object' || Array.isArray(mapping) || Object.keys(mapping).length !== 4
      || !Object.entries(mapping).every(([key, value]) => identity(key) && identity(value))
      || new Set(Object.values(mapping)).size !== 4 || !ids || r.source_run_id !== source.run_id
      || mapping[source.run_id] !== p.run_id || mapping[source.purchase_id] !== p.id || mapping[source.order_id] !== p.order_id) return false;
    const mapped = (value) => Object.prototype.hasOwnProperty.call(mapping, value) ? mapping[value] : value;
    if (mapped(ids.run_id) !== p.run_id || mapped(ids.purchase_id) !== p.id || mapped(ids.order_id) !== p.order_id || mapped(ids.capture_id) !== p.capture_id) return false;
    if (m.known !== true || m.run_id !== p.run_id || m.purchase_id !== p.id || m.order_id !== p.order_id
      || m.ticket_count !== r.ticket_count || !Array.isArray(m.tickets) || m.tickets.length !== r.ticket_count
      || !m.tickets.every((ticket) => identity(ticket?.id) && ticket.purchase_id === p.id && validTime(ticket.created_at)
        && seconds(ticket.created_at, p.capture_completed_at) >= 0 && seconds(ticket.created_at, p.capture_completed_at) <= 60)) return false;
    const tickets = m.tickets.map((ticket) => ticket.id);
    if (!Array.isArray(ids.ticket_ids) || ids.ticket_ids.length !== tickets.length || ids.ticket_ids.some((id, index) => id !== tickets[index])) return false;
    if (!events.every((event) => event && typeof event.source === 'string' && event.run_id === p.run_id
      && (event.purchase_id == null || event.purchase_id === p.id) && (event.order_id == null || event.order_id === p.order_id))) return false;
    const check = [...events].reverse().find((event) => event.source === 'checker' && event.event_type === 'invariant_result');
    const finding = check?.payload, found = finding?.source_ids, provenance = finding?.replay_provenance;
    return !!check && check.purchase_id === p.id && check.order_id === p.order_id && !!finding && !!found
      && finding.verdict === r.verdict && finding.signature === r.signature && finding.invariant_version === 'ticket-v1'
      && finding.deadline === x.deadline && found.run_id === p.run_id && found.purchase_id === p.id
      && found.order_id === p.order_id && found.capture_id === p.capture_id
      && Array.isArray(found.ticket_ids) && found.ticket_ids.length === tickets.length && found.ticket_ids.every((id, index) => id === tickets[index])
      && !!provenance && provenance.mode === 'RECORDED_REPLAY' && provenance.fresh_execution === false && provenance.network_calls === 0
      && provenance.input_sha256 === r.input_sha256 && sameMap(provenance.identity_mapping, mapping);
  }
  function validReview(data) {
    if (!data || typeof data !== 'object' || Array.isArray(data) || data.mode !== 'RECORDED_REPLAY' || data.fresh_execution !== false || data.network_calls !== 0
      || !fixedInvariant(data.invariant) || !digest(data.input_file_sha256)) return false;
    const source = data.recorded_source;
    if (!source || !['run_id', 'purchase_id', 'order_id'].every((key) => identity(source[key]))) return false;
    const d = data.cases?.defective, h = data.cases?.healthy;
    if (!validCase(d, source, 'defective') || !validCase(h, source, 'healthy')) return false;
    // Generated run/order/capture identities differ by import. Bind canonical
    // input and source mapping, never literal runtime identities across cases.
    if (d.receipt.input_sha256 !== h.receipt.input_sha256 || Object.keys(d.receipt.identity_mapping).sort().join('\n') !== Object.keys(h.receipt.identity_mapping).sort().join('\n')) return false;
    return new Date(d.purchase.capture_completed_at).getTime() === new Date(h.purchase.capture_completed_at).getTime()
      && new Date(d.execution.deadline).getTime() === new Date(h.execution.deadline).getTime();
  }

  /* ---------- State ---------- */
  let review = null;
  let selected = 'defective';

  /* ---------- Case view ---------- */
  function fact(label, main, note, tone) {
    const box = el('div', null, 'fact' + (tone ? ` fact-${tone}` : ''));
    box.append(el('span', label, 'small-label'), el('h3', main, 'fact-main'), el('p', note));
    return box;
  }

  function renderCase() {
    if (!review) return;
    const item = review.cases[selected], receipt = item.receipt;
    const paid = item.purchase.capture_completed_at;
    const ticket = item.merchant.tickets[0];
    byId('selected-name').textContent = selected === 'defective' ? 'Missed order' : 'Recovered order (replay)';
    document.querySelectorAll('.case-switch [data-case]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.case === selected)));
    document.querySelectorAll('.compare-card').forEach((card) => card.classList.toggle('is-selected', card.querySelector('[data-case]')?.dataset.case === selected));
    byId('download-case').href = `downloads/${selected}.json`;
    byId('download-case').textContent = selected === 'defective' ? 'Download missed-order summary (JSON)' : 'Download recovered-order summary (JSON)';
    const kept = receipt.verdict === 'PASS';
    const amount = Number(item.purchase.amount), currency = item.purchase.currency;
    const paidLabel = Number.isFinite(amount) && typeof currency === 'string' && /^[A-Z]{3}$/.test(currency) ? `${currency} ${(amount / 100).toFixed(2)} confirmed` : 'Payment confirmed';
    byId('facts').replaceChildren(
      fact('1 · Payment', paidLabel, `PayPal recorded the completed payment at ${instant(paid)}.`),
      fact('2 · Delivery', `${receipt.ticket_count} ${receipt.ticket_count === 1 ? 'ticket' : 'tickets'}`,
        ticket ? `Issued in this replay at ${instant(ticket.created_at)}, ${duration(seconds(ticket.created_at, paid))} after payment.`
          : 'The customer was still waiting when the 60-second promise ran out.', kept ? 'good' : 'bad'),
      fact('3 · Promise', kept ? 'Kept' : 'Broken', `Deadline: ${instant(item.execution.deadline)}. One ticket within 60 seconds of payment.`, kept ? 'good' : 'bad'),
    );
    byId('technical-result').textContent = JSON.stringify({
      mode: review.mode, new_payment: false, computed_when: review.computed_when, computed_at: review.computed_at,
      input_file_sha256: review.input_file_sha256, canonical_input_sha256: receipt.input_sha256, merchant_variant: selected,
      verdict: receipt.verdict, signature: receipt.signature, invariant: review.invariant, source_authenticity: receipt.source_authenticity,
    }, null, 2);
    renderTimeline();
  }

  function renderTimeline() {
    if (!review) return;
    const item = review.cases[selected], source = byId('source-filter').value;
    // Page and payment observations are preserved as recorded. Store results come
    // from this variant's replay; the original store observation stays nested.
    const records = item.events.filter((e) => sourceNames[e.source]);
    const visible = records.filter((e) => source === 'all' || e.source === source);
    byId('timeline-count').textContent = `${visible.length} of ${records.length} steps · times measured from the payment`;
    if (!visible.length) { byId('timeline').replaceChildren(el('li', 'Nothing recorded from this source.', 'empty')); return; }
    const entries = visible.map((e) => {
      const li = el('li', null, `step step-${e.source}`), details = el('details'), summary = el('summary');
      const rel = validTime(e.event_time) ? seconds(e.event_time, item.purchase.capture_completed_at) : NaN;
      summary.append(el('span', sourceNames[e.source], 'source-badge'), el('span', eventNames[e.event_type] || 'Saved observation', 'event-name'),
        el('span', Number.isFinite(rel) ? `${rel >= 0 ? '+' : '−'}${shortDuration(Math.abs(rel))}` : 'time n/a', 'event-time'));
      const body = el('div', null, 'record-body');
      body.append(el('p', `${instant(e.event_time)} · ${e.source === 'merchant'
        ? 'Store response from this recorded comparison. The original observation is available in technical details.'
        : 'Recorded during the original checkout. No new request was made.'}`));
      const payload = {...(e.payload || {})}; delete payload.replay_provenance;
      const pre = el('pre', JSON.stringify(payload, null, 2));
      pre.tabIndex = 0;
      pre.setAttribute('aria-label', `Original details: ${eventNames[e.event_type] || 'saved observation'}`);
      const original = el('details', null, 'original-details');
      original.append(el('summary', 'Technical details'), pre);
      body.append(original);
      details.append(summary, body); li.append(details);
      return li;
    });
    byId('timeline').replaceChildren(...entries);
  }

  /* ---------- Story ---------- */
  function showStory(stage) {
    const latency = review ? seconds(review.cases.healthy.merchant.tickets[0].created_at, review.cases.healthy.purchase.capture_completed_at) : NaN;
    const descriptions = {
      payment: ['1 of 3', 'Payment confirmed', 'The payment went through.', 'PayPal’s saved record confirms the $29 payment. That tells us the money arrived. It doesn’t tell us whether the customer got their ticket.'],
      delivery: ['2 of 3', 'Promise broken', 'But the ticket never arrived.', 'PayPal’s reply to the store was lost on the way. The original store never issued a ticket, even after its 60-second promise ran out.'],
      repair: ['3 of 3', 'Repaired store · replay', 'The repaired store closes the gap.', `The recovered store checks PayPal directly instead of waiting for a lost reply. Replayed against the same saved payment, it issues exactly one ticket after ${duration(latency)}. The customer’s one-minute promise stays the same.`],
    };
    const values = descriptions[stage];
    if (!values) return;
    selected = stage === 'repair' ? 'healthy' : 'defective';
    renderCase();
    document.querySelector('.promise').dataset.story = stage;
    document.querySelectorAll('button[data-story]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.story === stage)));
    ['story-counter', 'story-status', 'story-title', 'story-description'].forEach((id, i) => { byId(id).textContent = values[i]; });
    restartEnter(byId('story-copy'));
  }

  function restartEnter(node) {
    node.classList.remove('enter');
    if (reduced()) return;
    // Restart only this small, user-triggered animation; nothing loops.
    void node.offsetWidth;
    node.classList.add('enter');
  }
  byId('story-copy').addEventListener('animationend', () => byId('story-copy').classList.remove('enter'));
  document.querySelectorAll('button[data-story]').forEach((b) => b.addEventListener('click', () => { if (review) showStory(b.dataset.story); }));

  /* The actual 8 November missed-delivery investigation, separately recorded. */
  let failureHistory = null;
  function validFailureAi(history) {
    const actions = ['read_provider', 'read_merchant', 'finish'];
    const result = history?.deterministic_result;
    return !!history && history.kind === 'recorded-failure-investigation-v1' && history.fresh_execution === false && history.same_case_as_public_faulty_replay === false && history.recorded_date === '2026-11-08' && history.provider === 'Modal' && history.model === 'deepseek-ai/DeepSeek-V4.1-Flash' && result?.verdict === 'FAIL' && result.signature === 'paid_without_ticket' && Array.isArray(result.source_ids?.ticket_ids) && result.source_ids.ticket_ids.length === 0 && Array.isArray(history.trace) && history.trace.length === 3 && history.trace.every((step, i) => step?.step === i + 1 && step.action === actions[i] && typeof step.hypothesis === 'string' && Array.isArray(step.findings) && step.findings.length === i && step.findings.every(f => f.kind === 'observed' && typeof f.claim === 'string' && Array.isArray(f.evidence_ids) && f.evidence_ids.length > 0 && f.evidence_ids.every(id => [result.source_ids.provider_observation_id,result.source_ids.merchant_observation_id].includes(id))));
  }
  function showFailureStep(index) {
    if (!failureHistory || !Number.isInteger(index) || index < 0 || index > 2) return;
    const step = failureHistory.trace[index];
    document.querySelectorAll('[data-failure-step]').forEach(b => b.setAttribute('aria-pressed', String(Number(b.dataset.failureStep) === index)));
    byId('failure-question').textContent = ['Did the payment complete?', 'Was a ticket delivered?', 'What does the evidence support?'][index];
    byId('failure-answer').textContent = ['The assistant started without payment or delivery observations and requested the PayPal record.', 'PayPal confirmed the $29 capture. The assistant then requested the matching ticket records.', 'The store had no ticket after the one-minute deadline. The assistant finished with citations to both records.'][index];
    byId('failure-reasoning').textContent = step.hypothesis;
    byId('failure-citations').textContent = step.findings.length ? JSON.stringify(step.findings, null, 2) : 'No observations had been collected at this step.';
    byId('failure-verdict').textContent = index === 2 ? 'Paid, but no ticket. Fixed code checked the unchanged promise: FAIL / paid_without_ticket.' : 'The assistant chooses where to look; it does not decide the payment outcome.';
  }
  document.querySelectorAll('[data-failure-step]').forEach(b => b.addEventListener('click', () => showFailureStep(Number(b.dataset.failureStep))));
  function initialiseFailureAi(history) {
    if (!validFailureAi(history)) return;
    failureHistory = history;
    byId('failure-ai-panel').hidden = false;
    byId('failure-ai-unavailable').hidden = true;
    showFailureStep(0);
  }

  /* ---------- Saved AI investigation (separate, earlier case) ---------- */
  let aiHistory = null;
  function historicalAiStage(history, index) {
    const actions = ['read_provider', 'read_merchant', 'finish'];
    if (!history || history.mode !== 'RECORDED_AI_INVESTIGATION' || history.fresh_execution !== false || history.same_case_as_public_faulty_replay !== false || history.provider !== 'Modal' || history.model !== 'deepseek-ai/DeepSeek-V4.1-Flash' || !Number.isInteger(index) || index < 0 || index > 2) return null;
    if (typeof history.investigation_started_at !== 'string' || !history.investigation_started_at.startsWith('2026-10-26T') || history.historical_capture_date !== '2026-10-23') return null;
    const counts = history.actual_operations, result = history.deterministic_result;
    if (!counts || counts.model_calls !== 3 || counts.paypal_existing_order_gets !== 1 || counts.new_payments !== 0 || !result || result.verdict !== 'PASS' || result.signature !== 'ticket_delivered_once_on_time' || !Number.isFinite(result.delivery_latency_seconds) || result.delivery_latency_seconds < 0 || result.delivery_latency_seconds > 60) return null;
    if (!Array.isArray(history.trace) || history.trace.length !== 3 || !history.trace.every((step, i) => step && step.step === i + 1 && step.action === actions[i] && Array.isArray(step.evidence_categories_before_response) && step.evidence_categories_before_response.every((v) => typeof v === 'string' && v.length < 300) && typeof (step.exact_model_excerpt || step.reasoning_summary) === 'string' && (step.exact_model_excerpt || step.reasoning_summary).length <= 1000)) return null;
    const step = history.trace[index];
    const known = step.evidence_categories_before_response;
    const observations = new Map([['completed PayPal Sandbox capture', 'PayPal had confirmed the test payment.'], ['matching single delivered ticket', 'The store had one ticket linked to that payment.']]);
    if (known.some((v) => !observations.has(v))) return null;
    return {
      count: `Step ${index + 1} of 3`,
      question: ['Did the payment go through?', 'Did the customer get their ticket?', 'Was the promise kept?'][index],
      known: known.length ? known.map((v) => observations.get(v)).join(' ') : 'Nothing yet. No payment or ticket records had been read.',
      reasoningLabel: step.exact_model_excerpt ? 'What the assistant considered' : 'Why it checked this',
      reasoning: step.exact_model_excerpt || step.reasoning_summary,
      next: ['Look the payment up directly with PayPal.', 'Find the ticket linked to that payment.', 'Compare the ticket’s time with the 60-second promise.'][index],
      takeaway: index === 0 ? 'Start with the payment service, not the page the customer saw.'
        : index === 1 ? 'A completed payment alone can’t tell you whether the order was fulfilled.'
        : `One matching ticket, ${result.delivery_latency_seconds.toFixed(2)} seconds after payment. The payment and ticket timings confirm the promise was kept.`,
    };
  }

  function showAiStep(index) {
    const stage = historicalAiStage(aiHistory, index);
    if (!stage) return;
    document.querySelectorAll('[data-ai-step]').forEach((b) => b.setAttribute('aria-pressed', String(Number(b.dataset.aiStep) === index)));
    byId('ai-step-count').textContent = stage.count;
    byId('ai-question').textContent = stage.question;
    byId('ai-known').textContent = stage.known;
    byId('ai-reasoning-label').textContent = stage.reasoningLabel;
    byId('ai-reasoning').textContent = stage.reasoning;
    byId('ai-next').textContent = stage.next;
    byId('ai-takeaway').textContent = stage.takeaway;
    restartEnter(byId('ai-answer-copy'));
  }

  function initialiseAiHistory(history) {
    if (![0, 1, 2].every((i) => historicalAiStage(history, i))) return;
    aiHistory = history;
    const c = history.actual_operations;
    byId('ai-scope').textContent = `This is a different, earlier test checkout, captured on ${day(history.historical_capture_date + 'T00:00:00Z')}, where the ticket did arrive. It isn’t the missed order above. It shows how the assistant works through a case, one question at a time.`;
    byId('ai-identity').textContent = `Recorded investigation · started ${instant(history.investigation_started_at)} · DeepSeek on ${history.provider} · ${c.model_calls} saved assistant steps · no new payment or AI call on this page.`;
    byId('ai-unavailable').hidden = true;
    byId('ai-story-panel').hidden = false;
    showAiStep(0);
  }
  byId('ai-answer-copy').addEventListener('animationend', () => byId('ai-answer-copy').classList.remove('enter'));
  document.querySelectorAll('[data-ai-step]').forEach((b) => b.addEventListener('click', () => showAiStep(Number(b.dataset.aiStep))));

  /* ---------- Case switching ---------- */
  document.querySelectorAll('[data-case]').forEach((button) => button.addEventListener('click', () => {
    if (!review || !Object.prototype.hasOwnProperty.call(review.cases, button.dataset.case)) return;
    selected = button.dataset.case;
    renderCase();
    if (button.classList.contains('select-case')) {
      document.querySelector('.order-records').open = true;
      // Move focus without scrolling first, then make one deliberate scroll.
      byId('evidence-title').focus({preventScroll: true});
      byId('evidence').scrollIntoView({block: 'start', behavior: reduced() ? 'auto' : 'smooth'});
    }
  }));
  byId('source-filter').addEventListener('change', () => { if (review) renderTimeline(); });

  /* ---------- Load ---------- */
  function fail() {
    // Discard anything partial so no control can act on half-loaded records.
    review = null;
    aiHistory = null;
    byId('review').hidden = true;
    const notice = byId('load-state');
    notice.hidden = false;
    notice.classList.add('error');
    notice.replaceChildren(
      el('strong', 'We couldn’t open the saved records.'),
      document.createTextNode(' Reload the page to try again. No payment or AI request was made, and nothing will be retried automatically. The downloads below are still available.'),
    );
    document.querySelectorAll('a[href="#investigation"]').forEach((link) => link.setAttribute('href', '#load-state'));
  }

  fetch('data.json', {cache: 'no-store'})
    .then((response) => { if (!response.ok) throw new Error('unavailable'); return response.json(); })
    .then((data) => {
      if (!validReview(data)) throw new Error('mismatch');
      review = data;
      const d = data.cases.defective, h = data.cases.healthy;
      const when = data.computed_when === 'site build' ? 'when this site was built' : data.computed_when === 'app launch' ? 'when this app started' : 'when this page was prepared';
      const recorded = d.events.map((e) => e.event_time).filter(validTime).sort()[0] || d.purchase.capture_completed_at;
      byId('execution-note').textContent = `Both results were recalculated ${when} (${instant(data.computed_at)}) from the same saved input. The checkout itself was recorded on ${day(recorded)}.`;
      byId('defective-count').textContent = String(d.receipt.ticket_count);
      byId('healthy-count').textContent = String(h.receipt.ticket_count);
      byId('healthy-time').textContent = duration(seconds(h.merchant.tickets[0].created_at, h.purchase.capture_completed_at));
      byId('defective-finding').textContent = 'PayPal confirmed the payment, but no ticket was issued before the deadline. The promise was broken.';
      renderCase();
      showStory('payment');
      byId('story-copy').classList.remove('enter');
      if (data.failure_ai !== undefined) initialiseFailureAi(data.failure_ai);
      if (data.historical_ai !== undefined) initialiseAiHistory(data.historical_ai);
      byId('load-state').hidden = true;
      byId('review').hidden = false;
      // A launch URL may point at a section before the records arrive.
      const hash = window.location.hash.slice(1);
      const anchor = hash ? byId(hash) : null;
      if (anchor) anchor.scrollIntoView({block: 'start', behavior: 'auto'});
    })
    .catch(fail);
})();
