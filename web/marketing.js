/* CrashCart product page. Everything here runs in the browser:
   no account, payment, case or AI request is ever made. */
(() => {
  'use strict';
  const root = document.documentElement;
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const reduced = () => motion.matches;
  // Motion-only styles (reveals, hero frames, panel entrances) apply only while this class is set.
  const syncMotionClass = () => root.classList.toggle('js-motion', !reduced());
  syncMotionClass();

  const landing = document.getElementById('landing');
  const landingShown = () => Boolean(landing) && !landing.hidden;

  /* ---------- Hero: paid, then the clock runs out, then nothing ---------- */
  const stage = document.getElementById('hero-stage');
  const replay = document.getElementById('hero-replay');
  let timers = [];
  function clearTimers() { timers.forEach(clearTimeout); timers = []; }
  function showFinal() {
    clearTimers();
    if (stage) stage.dataset.stage = 'final';
    if (replay) replay.hidden = true;
  }
  function play() {
    if (!stage) return;
    clearTimers();
    if (reduced()) { showFinal(); return; }
    stage.dataset.stage = 'start';
    // Force the start frame before moving on so transitions run.
    void stage.offsetWidth;
    timers.push(setTimeout(() => { stage.dataset.stage = 'paid'; }, 250));
    timers.push(setTimeout(() => { stage.dataset.stage = 'waiting'; }, 1300));
    timers.push(setTimeout(() => { stage.dataset.stage = 'final'; if (replay) replay.hidden = false; }, 4700));
  }
  // The replay button stays put while it plays, so keyboard focus is never dropped.
  if (replay) replay.addEventListener('click', play);

  let heroStarted = false;
  function startHero() {
    if (!stage || heroStarted || !landingShown()) return;
    heroStarted = true;
    if (reduced()) { showFinal(); return; }
    if (!('IntersectionObserver' in window)) { play(); return; }
    // Hold the opening frame from the moment the page is shown, so the
    // finished frame never flashes before the animation starts.
    stage.dataset.stage = 'start';
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) { io.disconnect(); play(); }
    }, {threshold: .35});
    io.observe(stage);
  }

  /* ---------- Gentle reveal on scroll ---------- */
  const reveals = Array.from(document.querySelectorAll('.reveal'));
  const revealAll = () => reveals.forEach((el) => el.classList.add('is-in'));
  if (reveals.length) {
    if ('IntersectionObserver' in window && !reduced()) {
      const io = new IntersectionObserver((entries) => {
        for (const entry of entries) if (entry.isIntersecting) { entry.target.classList.add('is-in'); io.unobserve(entry.target); }
      }, {threshold: .12, rootMargin: '0px 0px -40px 0px'});
      reveals.forEach((el) => io.observe(el));
    } else revealAll();
    // Anything focused by keyboard must be visible immediately.
    document.addEventListener('focusin', (e) => { e.target.closest?.('.reveal')?.classList.add('is-in'); });
  }

  motion.addEventListener?.('change', () => {
    syncMotionClass();
    if (reduced()) { showFinal(); revealAll(); }
  });

  /* ---------- Deep links: #faq-money opens that answer ---------- */
  function openFromHash(scroll) {
    let id = '';
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    if (!id || !landingShown()) return;
    const target = document.getElementById(id);
    if (!target || !landing.contains(target)) return;
    const item = target.closest('details.faq-item');
    if (item) item.open = true;
    target.closest('.reveal')?.classList.add('is-in');
    // The landing appears after load, so the browser's own jump can miss it.
    if (scroll) requestAnimationFrame(() => target.scrollIntoView({block: 'start'}));
  }
  window.addEventListener('hashchange', () => openFromHash(false));

  // app.js decides which view is visible; wait for it.
  let hashHandled = false;
  function onLandingShown() {
    if (!landingShown()) return;
    startHero();
    if (!hashHandled) { hashHandled = true; openFromHash(true); }
  }
  if (landing) new MutationObserver(onLandingShown).observe(landing, {attributes: true, attributeFilter: ['hidden']});
  onLandingShown();

  /* ---------- Walkthrough ---------- */
  const demo = document.querySelector('[data-marketing-demo]');
  if (!demo) return;
  const demoRoot = demo.querySelector('.demo');
  const sources = ['checkout', 'payment', 'delivery'];
  const sourceNames = {checkout: 'Checkout', payment: 'Payment', delivery: 'Delivery'};
  const scenarioOrder = ['missing', 'delivered', 'uncertain'];
  const scenarios = {
    missing: {
      name: 'Ticket missing',
      verdict: 'Promise broken',
      tone: 'bad',
      title: 'Paid in full.\nNo ticket in sight.',
      description: 'PayPal shows a completed payment, but the store still has no ticket after the 60-second promise. That points to a delivery problem, not a payment one.',
      checkout: {title: 'The checkout page says all is well.', observation: '“Payment successful. Your ticket is on its way.”', next: 'Ask PayPal whether the payment really completed, then look for the store’s ticket.', takeaway: 'A friendly success message is a clue, not proof that anything was delivered.'},
      payment: {title: 'PayPal confirms the payment.', observation: 'Completed · USD 29.00 · matched to this purchase', next: 'Find the ticket for this purchase and note when it was issued.', takeaway: 'Now you know the money arrived. Whether the ticket did is a separate question.'},
      delivery: {title: 'The store has no ticket for this order.', observation: '0 tickets · checked after the 60-second deadline', next: 'Have the assistant trace the store’s delivery step and reproduce the failure.', takeaway: 'Paid, past the deadline and still no ticket: the promise was broken.'},
    },
    delivered: {
      name: 'Ticket delivered',
      verdict: 'Promise kept',
      tone: 'ok',
      title: 'Paid in full.\nOne ticket, on time.',
      description: 'Every record agrees: one ticket arrived well inside the promised 60 seconds. The same rule is applied whatever the outcome.',
      checkout: {title: 'The customer can see their ticket.', observation: '“Payment confirmed. Your workshop ticket is ready.”', next: 'Match the ticket on screen with PayPal’s payment and the store’s record.', takeaway: 'The page looks right. The other records still have to agree.'},
      payment: {title: 'PayPal confirms the right amount.', observation: 'Completed · USD 29.00 · matched to this purchase', next: 'Check that exactly one ticket belongs to this purchase.', takeaway: 'A completed payment, tied to this purchase, is what the delivery check starts from.'},
      delivery: {title: 'Exactly one ticket, on time.', observation: '1 ticket · issued 45 seconds after payment', next: 'Keep the payment, ticket and timing records together in case anyone asks.', takeaway: 'One ticket inside 60 seconds: in this example the promise was kept.'},
    },
    uncertain: {
      name: 'Payment unclear',
      verdict: 'More evidence needed',
      tone: 'warn',
      title: 'Payment unclear.\nNo verdict yet.',
      description: 'Nothing confirms the payment yet, so a missing ticket isn’t a delivery failure. CrashCart says so plainly instead of guessing.',
      checkout: {title: 'The checkout couldn’t confirm the payment.', observation: '“We couldn’t confirm your payment. Please check its status.”', next: 'Check with PayPal before deciding anything about delivery.', takeaway: 'An interrupted reply doesn’t tell you whether the money moved.'},
      payment: {title: 'The payment still needs checking.', observation: 'No confirmation of a completed payment yet', next: 'Look the payment up with PayPal using the saved order reference.', takeaway: 'Keep the question open. Don’t assume the payment worked because the page said so.'},
      delivery: {title: 'No ticket has been issued yet.', observation: '0 tickets · payment not yet confirmed', next: 'Confirm the payment first, then judge delivery against the deadline.', takeaway: 'The honest answer here is “more evidence needed”, not “failed”.'},
    },
  };

  const tabs = sources.map((s) => demo.querySelector(`[data-demo-source="${s}"]`));
  const panels = sources.map((s) => demo.querySelector(`#demo-panel-${s}`));
  const scenarioButtons = Array.from(demo.querySelectorAll('[data-demo-scenario]'));
  const nextButton = demo.querySelector('#demo-next');
  const announcement = demo.querySelector('#demo-announcement');
  const stepCount = demo.querySelector('#demo-step-count');
  const verdict = demo.querySelector('#demo-verdict');
  if (!demoRoot || tabs.some((t) => !t) || panels.some((p) => !p) || !nextButton) return;
  let currentSource = 'checkout';
  let currentScenario = 'missing';
  const nextScenario = () => scenarioOrder[(scenarioOrder.indexOf(currentScenario) + 1) % scenarioOrder.length];

  function announce() {
    const s = scenarios[currentScenario];
    if (announcement) announcement.textContent = `${s.name}: ${s.verdict}. Seen from ${sourceNames[currentSource].toLowerCase()}.`;
  }

  function renderNext() {
    const index = sources.indexOf(currentSource);
    const arrow = document.createElement('span');
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '→';
    const label = index === sources.length - 1
      ? `Next outcome: ${scenarios[nextScenario()].name} `
      : `Next: ${sourceNames[sources[index + 1]]} `;
    nextButton.replaceChildren(document.createTextNode(label), arrow);
  }

  function selectSource(source, {focus = false, notify = true} = {}) {
    if (!sources.includes(source)) return;
    currentSource = source;
    sources.forEach((name, i) => {
      const on = name === source;
      tabs[i].setAttribute('aria-selected', String(on));
      tabs[i].tabIndex = on ? 0 : -1;
      panels[i].hidden = !on;
    });
    const index = sources.indexOf(source);
    demoRoot.dataset.source = source;
    if (stepCount) stepCount.textContent = `Perspective ${index + 1} of ${sources.length}`;
    renderNext();
    if (focus) tabs[index].focus();
    if (notify) announce();
  }

  function selectScenario(key, {notify = true} = {}) {
    if (!Object.prototype.hasOwnProperty.call(scenarios, key)) return;
    currentScenario = key;
    const s = scenarios[key];
    demoRoot.dataset.scenario = key;
    demo.querySelector('#demo-result-title').textContent = s.title;
    demo.querySelector('#demo-result-copy').textContent = s.description;
    if (verdict) { verdict.textContent = s.verdict; verdict.dataset.tone = s.tone; }
    scenarioButtons.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.demoScenario === key)));
    for (const source of sources) {
      demo.querySelector(`#demo-source-${source}`).textContent = s[source].title;
      for (const field of ['observation', 'next', 'takeaway']) {
        const el = demo.querySelector(`[data-demo-field="${source}.${field}"]`);
        if (el) el.textContent = s[source][field];
      }
    }
    renderNext();
    if (notify) announce();
  }

  tabs.forEach((tab, index) => {
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;
    tab.addEventListener('click', () => selectSource(sources[index]));
    tab.addEventListener('keydown', (event) => {
      const offsets = {ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1};
      let target;
      if (Object.prototype.hasOwnProperty.call(offsets, event.key)) target = (index + offsets[event.key] + sources.length) % sources.length;
      else if (event.key === 'Home') target = 0;
      else if (event.key === 'End') target = sources.length - 1;
      else return;
      event.preventDefault();
      selectSource(sources[target], {focus: true});
    });
  });

  scenarioButtons.forEach((b, index) => {
    b.addEventListener('click', () => selectScenario(b.dataset.demoScenario));
    // Arrow keys move between outcomes as well as Tab.
    b.addEventListener('keydown', (event) => {
      const step = {ArrowRight: 1, ArrowLeft: -1}[event.key];
      if (!step) return;
      event.preventDefault();
      const target = scenarioButtons[(index + step + scenarioButtons.length) % scenarioButtons.length];
      target.focus();
      selectScenario(target.dataset.demoScenario);
    });
  });

  // The meter doubles as a shortcut to each perspective for pointer users;
  // keyboard users have the tabs.
  demo.querySelectorAll('.meter-seg[data-seg]').forEach((seg) => {
    seg.addEventListener('click', () => selectSource(seg.dataset.seg));
  });

  nextButton.addEventListener('click', () => {
    const index = sources.indexOf(currentSource);
    if (index === sources.length - 1) {
      selectScenario(nextScenario(), {notify: false});
      selectSource(sources[0]);
    } else selectSource(sources[index + 1]);
  });

  selectScenario('missing', {notify: false});
  selectSource('checkout', {notify: false});
  demo.dataset.enhanced = 'true';
  demoRoot.dataset.enhanced = 'true';
  demo.querySelectorAll('[data-demo-controls]').forEach((control) => { control.hidden = false; });
})();
