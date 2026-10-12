/* Fix My Name Online: small shared behaviour. No data leaves the page from this file. */
(() => {
  'use strict';

  // Law-directory notice: shown only when the visitor arrived from a law-firm directory.
  // Client-side check of document.referrer; nothing is stored or sent.
  try {
    const notice = document.getElementById('law-notice');
    const ref = document.referrer ? new URL(document.referrer) : null;
    const known = ['lawfirms1.com', 'lawfirms1.com.au'];
    if (notice && ref && ref.hostname !== location.hostname) {
      const host = ref.hostname.replace(/^www\./, '');
      if (known.includes(host) || /(law-?firm|lawyers?|solicitors?|attorneys?|legal-?directory)/i.test(host)) {
        notice.hidden = false;
      }
    }
  } catch (_) { /* bad referrer: ignore */ }

  // Menu sheet (a <details> element, so it also works without JavaScript).
  const menu = document.querySelector('.menu');
  if (menu) {
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && menu.open) { menu.open = false; menu.querySelector('summary').focus(); }
    });
    document.addEventListener('click', e => { if (menu.open && !menu.contains(e.target)) menu.open = false; });
  }

  // Safety strip: match the visitor's region when the browser says it isn't Australia.
  const strip = document.querySelector('[data-safety]');
  const SETS = {
    nz: [['In danger now?', 'Call 111.'], ['Online harm or threats?', '', 'Netsafe', 'https://netsafe.org.nz/'], ['Need to talk?', '', 'Call or text 1737', 'https://1737.org.nz/']],
    uk: [['In danger now?', 'Call 999.'], ['Intimate images shared?', '', 'Revenge Porn Helpline', 'https://revengepornhelpline.org.uk/'], ['Need to talk?', '', 'Samaritans 116 123', 'tel:116123']],
    us: [['In danger now?', 'Call 911.'], ['Intimate images shared?', '', 'StopNCII', 'https://stopncii.org/'], ['Need to talk?', '', 'Call or text 988', 'https://988lifeline.org/']],
    other: [['In danger now?', 'Call your local emergency number.'], ['Intimate images shared?', '', 'StopNCII', 'https://stopncii.org/'], ['Need to talk?', 'Contact a local crisis line.']]
  };
  function setSafety(code) {
    if (!strip || !SETS[code] || strip.dataset.safety === code) return;
    const wrap = strip.querySelector('.wrap');
    const phone = wrap.querySelector('svg');
    wrap.replaceChildren();
    SETS[code].forEach(([lead, text, linkText, href], i) => {
      const span = document.createElement('span');
      if (i === 0 && phone) span.appendChild(phone);
      const strong = document.createElement('strong'); strong.textContent = lead; span.append(strong, ' ');
      if (text) span.append(text + ' ');
      if (linkText) {
        const a = document.createElement('a'); a.textContent = linkText; a.href = href;
        if (!href.startsWith('tel:')) { a.rel = 'noopener'; a.target = '_blank'; }
        span.appendChild(a);
      }
      wrap.appendChild(span);
    });
    strip.dataset.safety = code;
  }
  window.fmnoSetSafety = code => setSafety({au: 'au', nz: 'nz', uk: 'uk', us: 'us'}[code] || (code === 'au' ? 'au' : 'other'));
  // Time zone is a better guide than browser language (many Australian devices say en-US).
  window.fmnoGuessCountry = () => {
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
      if (/^Australia\//.test(tz)) return 'au';
      if (/^(Pacific\/Auckland|Pacific\/Chatham)$/.test(tz)) return 'nz';
      if (/^(Europe\/London|Europe\/Belfast)$/.test(tz)) return 'uk';
      if (/^America\/(Toronto|Vancouver|Edmonton|Winnipeg|Halifax|St_Johns|Regina|Montreal)/.test(tz)) return 'ca';
      if (/^(America\/|US\/|Pacific\/Honolulu)/.test(tz)) return 'us';
      if (/^Europe\//.test(tz)) return 'eu';
      return tz ? 'other' : 'au';
    } catch (_) { return 'au'; }
  };
  const guessed = window.fmnoGuessCountry();
  if (guessed !== 'au') setSafety(guessed === 'eu' || guessed === 'ca' ? 'other' : guessed);

  // Copy buttons: <button data-copy="#element-id">
  document.addEventListener('click', async e => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const target = document.querySelector(btn.dataset.copy);
    if (!target) return;
    try { await navigator.clipboard.writeText(target.innerText.trim()); btn.dataset.done = '1'; const old = btn.lastChild.textContent; btn.lastChild.textContent = ' Copied'; setTimeout(() => { btn.lastChild.textContent = old; }, 1600); }
    catch (_) { /* clipboard blocked: the text is still selectable */ }
  });

  // Guide search on /learn (filters the visible list; nothing is sent anywhere).
  const search = document.getElementById('guide-search');
  if (search) {
    const links = [...document.querySelectorAll('[data-guide]')];
    const empty = document.getElementById('guide-empty');
    search.addEventListener('input', () => {
      const q = search.value.trim().toLowerCase();
      let shown = 0;
      links.forEach(a => { const hit = !q || a.dataset.guide.includes(q); a.hidden = !hit; if (hit) shown++; });
      document.querySelectorAll('.guide-group').forEach(g => { g.hidden = !g.querySelector('[data-guide]:not([hidden])'); });
      if (empty) empty.hidden = shown > 0;
    });
  }

  // Problem tiles on marketing pages: optional analytics event carrying the problem code only.
  document.addEventListener('click', e => {
    const tile = e.target.closest('a[data-problem]');
    if (tile && typeof window.gtag === 'function') {
      try { window.gtag('event', 'choose_problem', {problem: tile.dataset.problem}); } catch (_) { /* ignore */ }
    }
  });
})();
