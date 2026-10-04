(() => {
  'use strict';
  const button = document.getElementById('menu-toggle');
  const nav = document.getElementById('main-nav');
  button.hidden = false;
  document.querySelector('.header').classList.add('js-nav');
  function closeMenu() { nav.classList.remove('open'); button.setAttribute('aria-expanded', 'false'); }
  button.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    button.setAttribute('aria-expanded', String(open));
  });
  nav.addEventListener('click', e => { if (e.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && nav.classList.contains('open')) { closeMenu(); button.focus(); } });
  document.querySelectorAll('[data-track]').forEach(link => link.addEventListener('click', () => {
    const event = {event: 'cta_click', label: link.dataset.track, href: link.getAttribute('href'), location: '/', source: 'homepage_v52'};
    if (navigator.sendBeacon) navigator.sendBeacon('/api/track-click', new Blob([JSON.stringify(event)], {type: 'application/json'}));
  }));
})();
