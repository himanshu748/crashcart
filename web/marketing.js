/* An illustrative, entirely local product walkthrough. No account or payment work. */
(() => {
  'use strict';
  const demo = document.querySelector('[data-marketing-demo]');
  if (!demo) return;
  const sources = ['checkout', 'payment', 'delivery'];
  const sourceNames = {checkout: 'Checkout', payment: 'Payment', delivery: 'Delivery'};
  const scenarios = {
    missing: {
      name: 'Ticket missing', title: 'Payment confirmed.\nTicket still missing.',
      description: 'The payment completed, but the store has no ticket after the 60-second promise. The records point to a delivery issue.',
      checkout: {title: 'The checkout says the payment went through.', observation: 'Payment successful. Your ticket is on its way.', next: "Confirm the payment with PayPal and find the store's ticket record.", takeaway: 'A successful page message is a clue. It does not prove that a ticket was delivered.'},
      payment: {title: 'PayPal confirms the payment.', observation: 'Completed payment of USD 29.00, matched to the purchase.', next: 'Find the ticket for this purchase and check when it was delivered.', takeaway: 'Confirming payment answers one question. Delivery is a separate record.'},
      delivery: {title: 'The store has no ticket for this purchase.', observation: '0 tickets · checked after the 60-second delivery deadline.', next: "Investigate the store's delivery path and reproduce the supported failure.", takeaway: 'Together, the payment and store records establish the missing-ticket problem in this example.'}
    },
    delivered: {
      name: 'Ticket delivered', title: 'Payment confirmed.\nOne ticket delivered.',
      description: 'The records agree: one ticket arrived within the promised time. The same delivery promise is checked in every example.',
      checkout: {title: 'The customer can see the ticket.', observation: 'Payment confirmed. Your workshop ticket is ready.', next: 'Match the visible ticket with the payment and store records.', takeaway: 'The page looks right. The other records still need to agree.'},
      payment: {title: 'PayPal confirms the expected amount.', observation: 'Completed payment of USD 29.00, matched to the purchase.', next: 'Check that exactly one ticket belongs to this purchase.', takeaway: 'A completed payment and its purchase reference anchor the delivery check.'},
      delivery: {title: 'Exactly one ticket arrived in time.', observation: '1 ticket · issued 45 seconds after payment confirmation.', next: 'Keep the linked payment, ticket and timing records together.', takeaway: 'This illustrated checkout meets the one-ticket, 60-second delivery promise.'}
    },
    uncertain: {
      name: 'Payment uncertain', title: 'Payment unclear.\nKeep the question open.',
      description: 'The available records do not confirm payment. A missing ticket alone cannot establish a delivery failure.',
      checkout: {title: 'The checkout could not confirm payment.', observation: 'We could not confirm your payment. Please check its status.', next: 'Check the payment service before making a delivery judgment.', takeaway: 'An interrupted response does not tell you whether money was captured.'},
      payment: {title: 'Payment status still needs checking.', observation: 'No separate confirmation of a completed payment is available.', next: 'Retrieve the payment using its saved purchase and order references.', takeaway: 'Keep uncertainty visible. Do not infer a successful payment from the page.'},
      delivery: {title: 'No ticket is recorded yet.', observation: '0 tickets · payment confirmation is still missing.', next: 'Confirm payment before evaluating the delivery deadline.', takeaway: 'This example needs more evidence, rather than a confident failure label.'}
    }
  };
  const tabs = sources.map(source => demo.querySelector(`[data-demo-source="${source}"]`));
  const panels = sources.map(source => demo.querySelector(`#demo-panel-${source}`));
  const scenarioButtons = Array.from(demo.querySelectorAll('[data-demo-scenario]'));
  const nextButton = demo.querySelector('#demo-next');
  const announcement = demo.querySelector('#demo-announcement');
  let currentSource = 'checkout';
  let currentScenario = 'missing';

  function announce() {
    announcement.textContent = `Example: ${scenarios[currentScenario].name}. ${sourceNames[currentSource]} perspective.`;
  }
  function selectSource(source, {focus = false, notify = true} = {}) {
    if (!sources.includes(source)) return;
    currentSource = source;
    sources.forEach((name, index) => {
      const selected = name === source;
      tabs[index].setAttribute('aria-selected', String(selected));
      tabs[index].tabIndex = selected ? 0 : -1;
      panels[index].hidden = !selected;
    });
    const index = sources.indexOf(source);
    demo.querySelector('#demo-step-count').textContent = `Perspective ${index + 1} of 3`;
    const arrow = document.createElement('span');
    arrow.setAttribute('aria-hidden', 'true');
    arrow.textContent = '→';
    nextButton.replaceChildren(document.createTextNode(index === 2 ? 'Start again ' : `Next: ${sourceNames[sources[index + 1]]} `), arrow);
    if (focus) tabs[index].focus();
    if (notify) announce();
  }
  function selectScenario(key, {notify = true} = {}) {
    if (!Object.prototype.hasOwnProperty.call(scenarios, key)) return;
    currentScenario = key;
    const scenario = scenarios[key];
    demo.dataset.scenario = key;
    demo.querySelector('#demo-result-title').textContent = scenario.title;
    demo.querySelector('#demo-result-copy').textContent = scenario.description;
    scenarioButtons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.demoScenario === key)));
    sources.forEach(source => {
      demo.querySelector(`#demo-source-${source}`).textContent = scenario[source].title;
      ['observation', 'next', 'takeaway'].forEach(field => {
        demo.querySelector(`[data-demo-field="${source}.${field}"]`).textContent = scenario[source][field];
      });
    });
    if (notify) announce();
  }

  tabs.forEach((tab, index) => {
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', tab.id);
    panels[index].tabIndex = 0;
    tab.addEventListener('click', () => selectSource(sources[index]));
    tab.addEventListener('keydown', event => {
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
  scenarioButtons.forEach(button => button.addEventListener('click', () => selectScenario(button.dataset.demoScenario)));
  nextButton.addEventListener('click', () => selectSource(sources[(sources.indexOf(currentSource) + 1) % sources.length]));
  selectScenario('missing', {notify: false});
  selectSource('checkout', {notify: false});
  demo.dataset.enhanced = 'true';
  demo.querySelectorAll('[data-demo-controls]').forEach(control => { control.hidden = false; });
})();
