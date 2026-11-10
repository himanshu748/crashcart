/* Delivered motion controller under a synthetic DOM/GSAP boundary.
   These regressions prove control/cleanup semantics, not browser frame rate. */
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const motionSource = fs.readFileSync(path.join(root, 'web/judge/motion.js'), 'utf8');

function dom() {
  const all = [], ids = new Map();
  class Element {
    constructor() {
      this.children = []; this.parentElement = null; this.dataset = {}; this.style = {};
      this.attributes = {}; this.handlers = {}; this.textContent = ''; this.hidden = false;
      const classes = new Set();
      this.classList = {add: (...names) => names.forEach(n => classes.add(n)),
        remove: (...names) => names.forEach(n => classes.delete(n)), contains: n => classes.has(n),
        toggle: (name, on) => { if (on) classes.add(name); else classes.delete(name); return !!on; }};
      all.push(this);
    }
    set className(value) { value.split(/\s+/).filter(Boolean).forEach(n => this.classList.add(n)); }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    removeAttribute(name) { delete this.attributes[name]; }
    getAttribute(name) { return this.attributes[name] ?? null; }
    addEventListener(name, callback) { (this.handlers[name] ??= []).push(callback); }
    dispatch(name) { for (const cb of this.handlers[name] || []) cb({target: this}); }
    append(child) { this.children.push(child); child.parentElement = this; }
    after(child) { const p = this.parentElement; p.children.splice(p.children.indexOf(this) + 1, 0, child); child.parentElement = p; }
    remove() { if (this.parentElement) { const p = this.parentElement; p.children.splice(p.children.indexOf(this), 1); this.parentElement = null; } }
    closest(selector) { return selector.startsWith('.') ? (this.classList.contains(selector.slice(1)) ? this : this.parentElement?.closest(selector)) : null; }
  }
  function node(id) { const e = new Element(); if (id) ids.set(id, e); return e; }
  return {all, ids, node, Element};
}

function motionHarness({osReduced = false, userReduced = false, number = true, story = false} = {}) {
  const d = dom(), html = d.node(), review = d.node('review'), toggle = d.node('reduce-motion');
  if (userReduced) html.classList.add('reduce-motion');
  const numberSource = d.node('healthy-time'); numberSource.textContent = number ? '32.26 seconds' : ''; review.append(numberSource);
  const panels = story ? [d.node(), d.node()] : [], steps = story ? [d.node(), d.node()] : [];
  const storyNode = story ? d.node() : null, visual = story ? d.node() : null;
  const fresh = [], frames = [], observers = [], tweens = [], contexts = [], medias = [];
  let activeContext = null;
  const attached = e => e === numberSource || e.parentElement !== null;
  const document = {documentElement: html, getElementById: id => d.ids.get(id) || null,
    createElement: () => d.node(), addEventListener() {},
    querySelector(selector) {
      if (selector === '[data-scroll-story]') return storyNode;
      if (selector === '[data-story-visual]') return visual;
      return null;
    },
    querySelectorAll(selector) {
      if (selector === '[data-story-panel]') return panels;
      if (selector === '[data-story-step]') return steps;
      if (selector === '#timeline > li, #facts > .fact') return fresh;
      if (selector.startsWith('.motion-count-')) return d.all.filter(e => attached(e) && e.classList.contains(selector.slice(1)));
      return [];
    }};
  function record(method, target, vars) {
    const tween = {method, target, vars, owner: activeContext, killed: false};
    tweens.push(tween); activeContext?.tweens.push(tween); return tween;
  }
  const gsap = {registerPlugin() {}, set() {},
    from: (target, vars) => record('from', target, vars),
    to: (target, vars) => record('to', target, vars),
    fromTo: (target, _from, vars) => record('fromTo', target, vars),
    timeline(vars) { const timeline = record('timeline', null, vars); timeline.to = timeline.fromTo = () => timeline; return timeline; },
    context(callback) {
      const context = {tweens: [], reverted: false,
        add(fn) { const before = activeContext; activeContext = context; try { return fn(); } finally { activeContext = before; } },
        revert() { context.reverted = true; context.tweens.forEach(t => {t.killed = true;}); }};
      contexts.push(context); context.add(callback); return context;
    },
    matchMedia() {
      const media = {reverted: false, callback: null, cleanup: null,
        run() { media.cleanup = media.callback({conditions: {osReduced, desktop: true, all: true}}); },
        add(_queries, cb) { media.callback = cb; media.run(); },
        revert() { if (!media.reverted) { media.cleanup?.(); media.reverted = true; } }};
      medias.push(media); return media;
    }};
  class MutationObserver { constructor(callback) { this.callback = callback; observers.push(this); } observe() {} }
  class IntersectionObserver { observe() {} disconnect() {} }
  vm.runInNewContext(motionSource, {document, window: {gsap, ScrollTrigger: {create() {}},
    matchMedia: () => ({matches: osReduced})}, MutationObserver, IntersectionObserver,
    requestAnimationFrame: cb => { frames.push(cb); return frames.length; }}, {filename: 'motion.js'});
  return {html, review, toggle, numberSource, panels, storyNode, tweens, contexts, frames,
    visuals: () => document.querySelectorAll('.motion-count-visual'),
    newRecord() { const e = d.node(); fresh.push(e); return e; },
    mutate() { observers[0].callback([{target: review}]); },
    flush() { while (frames.length) frames.shift()(); },
    setOSReduced(value) { osReduced = value; for (const media of medias.filter(m => !m.reverted)) {media.cleanup?.(); media.run();} },
    setUserReduced(value) { html.classList.toggle('reduce-motion', value); toggle.dispatch('change'); }};
}

test('OS reduced motion prevents record-render entrances and count-up overlays', () => {
  const h = motionHarness({osReduced: true}); h.newRecord(); h.mutate(); h.flush();
  assert.equal(h.tweens.length, 0);
  assert.equal(h.visuals().length, 0);
  assert.equal(h.numberSource.textContent, '32.26 seconds');
  assert.equal(h.numberSource.classList.contains('motion-count-source'), false);
});

test('a reduced-motion change cancels an already queued record animation', () => {
  const h = motionHarness({number: false}), record = h.newRecord(); h.mutate();
  assert.equal(h.frames.length, 1, 'The control case must actually queue an animation');
  h.setOSReduced(true); h.flush();
  assert.equal(h.tweens.filter(t => t.method === 'from').length, 0);
  assert.equal(record.dataset.motionSeen, undefined, 'A blocked entrance must not be recorded as played');
});

test('OS preference cleanup restores the original timing during an unfinished count-up', () => {
  const h = motionHarness(), counter = h.tweens.find(t => t.method === 'to');
  assert.ok(counter); counter.target.value = 8; counter.vars.onUpdate();
  assert.match(h.visuals()[0].textContent, /^8\.00/);
  assert.equal(h.numberSource.classList.contains('motion-count-source'), true);
  h.setOSReduced(true);
  assert.equal(counter.killed, true);
  assert.equal(h.visuals().length, 0);
  assert.equal(h.numberSource.classList.contains('motion-count-source'), false);
  assert.equal(h.numberSource.textContent, '32.26 seconds');
});

test('async entrances belong to a cleanup context and the page toggle stops them', () => {
  const h = motionHarness({number: false}); h.numberSource.textContent = '32.26 seconds';
  h.newRecord(); h.mutate(); h.flush();
  const asyncTweens = h.tweens.filter(t => t.method === 'from' || t.method === 'to');
  assert.equal(asyncTweens.length, 2);
  assert.ok(asyncTweens.every(t => t.owner), 'Async tweens need the same reversible context as setup tweens');
  h.setUserReduced(true);
  assert.ok(asyncTweens.every(t => t.killed));
  assert.equal(h.visuals().length, 0);
  assert.equal(h.numberSource.classList.contains('motion-count-source'), false);
});

test('reduced motion exposes every story panel instead of retaining hidden panels', () => {
  const h = motionHarness({story: true, number: false});
  assert.equal(h.panels[1].getAttribute('aria-hidden'), 'true');
  assert.equal(h.storyNode.classList.contains('story-enhanced'), true);
  h.setOSReduced(true);
  assert.ok(h.panels.every(panel => panel.getAttribute('aria-hidden') === null));
  assert.equal(h.storyNode.classList.contains('story-enhanced'), false);
});

function simulatorHarness() {
  const d = dom(), html = d.node();
  for (const id of ['reduce-motion', 'sim', 'sim-fill', 'sim-now', 'sim-ticket', 'sim-time', 'sim-clock', 'sim-store',
    'sim-store-note', 'sim-promise', 'sim-promise-note', 'sim-hint', 'sim-verdict-title', 'sim-verdict-body', 'sim-hint-text', 'sim-controls', 'sim-play']) d.node(id);
  const scenarios = ['lost', 'lookup', 'late', 'twice'].map(name => { const b = d.node(); b.dataset.scenario = name; return b; });
  const document = {documentElement: html, getElementById: id => d.ids.get(id) || null,
    querySelectorAll: selector => selector === '[data-scenario]' ? scenarios : []};
  const source = fs.readFileSync(path.join(root, 'web/judge/site.js'), 'utf8');
  vm.runInNewContext(source, {document, window: {matchMedia: () => ({matches: false, addEventListener() {}}),
    localStorage: {getItem: () => null, setItem() {}}}, requestAnimationFrame() {}, cancelAnimationFrame() {}}, {filename: 'site.js'});
  return {node: id => d.ids.get(id), set(name, time) {
    scenarios.find(b => b.dataset.scenario === name).dispatch('click');
    const input = d.ids.get('sim-time'); input.value = String(time); input.dispatch('input'); }};
}

test('transform-only simulator rendering preserves timing, ticket and verdict outcomes', () => {
  const h = simulatorHarness();
  for (const [scenario, time, state, ticketText] of [
    ['lost', 60, 'waiting', 'No ticket yet'], ['lost', 90, 'broken', 'No ticket'],
    ['lookup', 8, 'kept', '1 ticket at 8s'], ['late', 75, 'late', '1 ticket at 75s'],
    ['twice', 11, 'broken', '2 tickets'],
  ]) {
    h.set(scenario, time);
    assert.equal(h.node('sim').dataset.state, state);
    assert.equal(h.node('sim-store').textContent, ticketText);
    assert.equal(h.node('sim-time').getAttribute('aria-valuetext'), `${time} seconds after payment`);
    assert.equal(h.node('sim-fill').style.transform, `scaleX(${time / 90})`);
    assert.equal(h.node('sim-now').style.transform, `translateX(${time / 90 * 100}%)`);
    assert.equal(h.node('sim-fill').style.width, undefined);
    assert.equal(h.node('sim-now').style.left, undefined);
  }
});
