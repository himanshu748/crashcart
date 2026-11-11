/* Presentation only. Saved observations, delivery rules and verdicts stay in app.js/site.js. */
(() => {
  'use strict';
  const gsap = window.gsap;
  if (!gsap || !window.ScrollTrigger) return;
  gsap.registerPlugin(window.ScrollTrigger);
  const root = document.documentElement;
  const select = (s) => Array.from(document.querySelectorAll(s));
  let media;
  let context;
  let hero;
  let mobileObserver;
  const replay = document.querySelector('[data-motion-replay]');
  const reduced = () => root.classList.contains('reduce-motion');
  const motionDisabled = () => reduced() || window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const clearCounts = () => {
    select('.motion-count-visual').forEach((node) => node.remove());
    select('.motion-count-source').forEach((node) => node.classList.remove('motion-count-source'));
  };
  const reset = () => {
    mobileObserver?.disconnect();
    media?.revert();
    context?.revert();
    document.querySelector('[data-scroll-story]')?.classList.remove('story-enhanced');
    select('[data-story-panel]').forEach((panel) => panel.removeAttribute('aria-hidden'));
    clearCounts();
  };
  function setupHero(noMotion) {
    const payment = document.querySelector('[data-hero-payment]');
    if (!payment) return;
    const gap = document.querySelector('[data-hero-gap]');
    const repair = document.querySelector('[data-hero-repair]');
    const clock = document.querySelector('[data-hero-clock] .clock-number') || document.querySelector('[data-hero-clock]');
    const line = select('.hero-flow-line');
    const figure = payment.closest('figure');
    if (noMotion) {
      gsap.set([payment, gap, repair], {opacity: 1, y: 0, scale: 1});
      gsap.set(line, {scaleX: 1});
      if (clock?.firstChild) clock.firstChild.nodeValue = '60';
      if (replay) replay.hidden = true;
      gap.classList.add('is-missing');
      figure.dataset.motionState = 'complete';
      return;
    }
    const timer = {seconds: 0};
    hero = gsap.timeline({defaults: {ease: 'power2.out'},
      onStart: () => {figure.dataset.motionState = 'playing'; gap.classList.remove('is-missing');},
      onComplete: () => {figure.dataset.motionState = 'complete';}})
      .fromTo(payment, {y: 10}, {y: 0, duration: 0.5}, 0)
      .fromTo(line, {scaleX: 0, transformOrigin: 'left center'}, {scaleX: 1, duration: 1.1}, 0.3)
      .to(timer, {seconds: 60, duration: 1.6, ease: 'none', onUpdate: () => {
        if (clock?.firstChild) clock.firstChild.nodeValue = String(Math.round(timer.seconds));
      }}, 0.5)
      .fromTo(gap, {y: 6}, {y: 0, duration: 0.45}, 1.8)
      .call(() => gap.classList.add('is-missing'), [], 2.1)
      .fromTo(repair, {y: 12, scale: 0.97}, {y: 0, scale: 1, duration: 0.6}, 2.8);
    if (replay) replay.hidden = false;
  }
  function setupStory(noMotion, desktop) {
    const story = document.querySelector('[data-scroll-story]');
    if (!story || noMotion) return;
    const visual = document.querySelector('[data-story-visual]');
    const panels = select('[data-story-panel]');
    const steps = select('[data-story-step]');
    if (!desktop || !visual || panels.length !== steps.length) {
      mobileObserver = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          if (!motionDisabled()) context?.add(() => gsap.from(entry.target, {y: 18, duration: 0.45}));
          mobileObserver.unobserve(entry.target);
        });
      }, {threshold: 0.1});
      steps.forEach((step) => mobileObserver.observe(step));
      return;
    }
    story.classList.add('story-enhanced');
    gsap.set(panels, {opacity: 0, y: 18});
    gsap.set(panels[0], {opacity: 1, y: 0});
    panels.forEach((panel, i) => panel.setAttribute('aria-hidden', String(i !== 0)));
    window.ScrollTrigger.create({trigger: visual, start: 'top 120px',
      endTrigger: story, end: 'bottom bottom', pin: true, pinSpacing: false, invalidateOnRefresh: true});
    steps.forEach((step, i) => {
      if (i === 0) return;
      gsap.timeline({scrollTrigger: {trigger: step, start: 'top 75%', end: 'top 35%', scrub: 0.35,
        onEnter: () => panels.forEach((p, n) => p.setAttribute('aria-hidden', String(n !== i))),
        onLeaveBack: () => panels.forEach((p, n) => p.setAttribute('aria-hidden', String(n !== i - 1)))}})
        .fromTo(panels[i - 1], {opacity: 1, y: 0},
          {opacity: 0, y: -14, duration: 0.45, immediateRender: false}, 0)
        .fromTo(panels[i], {opacity: 0, y: 18},
          {opacity: 1, y: 0, duration: 0.55, immediateRender: false}, 0.25);
    });
  }
  function animateNumbers() {
    const source = document.getElementById('healthy-time');
    if (source?.closest('[hidden]')) { clearCounts(); return; }
    if (!source || !source.textContent || source.dataset.motionValue === source.textContent) return;
    const label = source.textContent;
    const value = Number.parseFloat(label);
    if (!Number.isFinite(value)) return;
    source.dataset.motionValue = label;
    if (motionDisabled()) return;
    const visual = document.createElement('span');
    visual.className = 'motion-count-visual';
    visual.setAttribute('aria-hidden', 'true');
    source.classList.add('motion-count-source');
    source.after(visual);
    const n = {value: 0};
    gsap.to(n, {value, duration: 0.7, ease: 'power2.out', onUpdate: () => {
      visual.textContent = n.value.toFixed(2) + label.replace(/^[\d.]+/, '');
    }, onComplete: () => {visual.remove(); source.classList.remove('motion-count-source');}});
  }
  function renderMotion() {
    reset();
    media = gsap.matchMedia();
    media.add({osReduced: '(prefers-reduced-motion: reduce)', desktop: '(min-width: 1000px)',
      all: '(min-width: 0px)'}, (state) => {
      const noMotion = state.conditions.osReduced || reduced();
      context = gsap.context(() => {
        setupHero(noMotion);
        setupStory(noMotion, state.conditions.desktop);
        if (noMotion) return;
        select('.compare-card, .failure-ai, .product-copy + .glance, .sim-record').forEach((node) => {
          gsap.from(node, {y: 14, duration: 0.5,
            scrollTrigger: {trigger: node, start: 'top 95%', once: true}});
        });
        animateNumbers();
      });
      return () => {
        mobileObserver?.disconnect();
        context?.revert();
        clearCounts();
        document.querySelector('[data-scroll-story]')?.classList.remove('story-enhanced');
        select('[data-story-panel]').forEach((panel) => panel.removeAttribute('aria-hidden'));
      };
    });
  }
  renderMotion();
  replay?.addEventListener('click', () => {if (!reduced()) hero?.restart();});
  document.getElementById('reduce-motion')?.addEventListener('change', renderMotion);
  // app.js can render after this file has loaded. Animate nodes, never alter record text.
  const review = document.getElementById('review');
  if (review) {
    let queued = false;
    new MutationObserver((changes) => {
      if (motionDisabled() || queued || changes.every((change) => change.target.closest?.('.motion-count-visual'))) return;
      queued = true;
      requestAnimationFrame(() => {
        queued = false;
        if (motionDisabled()) return;
        context?.add(animateNumbers);
        const nodes = select('#timeline > li, #facts > .fact');
        const fresh = nodes.filter((node) => !node.dataset.motionSeen);
        fresh.forEach((node) => {node.dataset.motionSeen = '1';});
        if (fresh.length) context?.add(() => gsap.from(fresh, {y: 9, duration: 0.3,
          stagger: {each: 0.025, amount: Math.min(0.35, fresh.length * 0.025)}}));
      });
    }).observe(review, {childList: true, subtree: true, attributes: true, attributeFilter: ['hidden']});
  }
  // State feedback is separate from data rendering and does not delay input or navigation.
  document.addEventListener('click', (event) => {
    if (motionDisabled()) return;
    const trigger = event.target.closest('button[data-case], button[data-story], button[data-failure-step], [data-scenario]');
    if (trigger) context?.add(() => gsap.fromTo(trigger, {scale: 0.97}, {scale: 1, duration: 0.2, overwrite: true}));
  });
})();
