/* Fix My Name Online: free check, plan and tracker.
   Runs entirely in this browser. Nothing you type is sent to the server:
   no fetch, no forms, no analytics. Storage: this tab only (sessionStorage)
   unless you switch on "Save on this browser" (localStorage). */
(() => {
  'use strict';
  const root = document.getElementById('desk-app');
  const dataNode = document.getElementById('plan-data');
  if (!root || !dataNode) return;
  const DATA = JSON.parse(dataNode.textContent);
  const KEY = 'fmno_self_service_v2';
  const OLD_KEY = 'fmno_self_service_v1';
  const STATUS = Object.fromEntries(DATA.statuses);
  const STATUS_CLASS = {'not-started': 'st-not-started', preparing: 'st-preparing', submitted: 'st-sent', waiting: 'st-waiting', answered: 'st-answered', closed: 'st-closed'};
  const PROBLEMS = Object.fromEntries(DATA.problems.map(p => [p.key, p]));
  const COUNTRY = Object.fromEntries(DATA.countries);
  const SAFETY = {threat: 'Someone is threatening or harassing me', child: 'A child is involved', intimate: 'There are intimate images of me'};
  const LIMITS = {link: 2000, label: 160, notes: 8000, reference: 300, sentTo: 200};
  const MAX_ITEMS = 50;

  // ---------- small helpers ----------
  const $ = sel => root.querySelector(sel);
  function el(tag, attrs, ...kids) {
    const node = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === 'class') node.className = v;
      else if (k === 'text') node.textContent = v;
      else if (k.startsWith('on')) node.addEventListener(k.slice(2), v);
      else node.setAttribute(k, v === true ? '' : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false) node.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return node;
  }
  function svg(name, cls = 'icon icon-sm') {
    const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    s.setAttribute('class', cls); s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttribute('href', '#i-' + name); s.appendChild(use); return s;
  }
  const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
  const pad = n => String(n).padStart(2, '0');
  const iso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const today = () => iso(new Date());
  const addDays = (days, from) => { const d = from ? new Date(from + 'T12:00:00') : new Date(); d.setDate(d.getDate() + days); return iso(d); };
  const nice = s => { if (!s) return ''; const d = new Date(s + 'T12:00:00'); return isNaN(d) ? s : d.toLocaleDateString('en-AU', {day: 'numeric', month: 'short', year: 'numeric'}); };
  const daysUntil = s => Math.round((new Date(s + 'T12:00:00') - new Date(today() + 'T12:00:00')) / 86400000);
  const matches = (when, a) => !when || Object.entries(when).every(([k, allowed]) => allowed.includes(a[k]));
  const pick = (variants, a) => (variants.find(v => matches(v.when, a)) || {}).text || '';
  const host = url => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch (_) { return ''; } };

  function guessCountry() {
    return typeof window.fmnoGuessCountry === 'function' ? window.fmnoGuessCountry() : 'au';
  }

  // ---------- state + storage ----------
  let state = {version: 2, items: [], draft: null};
  let persistence = false; // true = localStorage (opted in); false = this tab only
  let dirty = false;
  let flash = '';

  function cleanItem(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('bad item');
    const str = (v, max) => { if (v === undefined || v === null) return ''; if (typeof v !== 'string' || v.length > max) throw new Error('bad field'); return v; };
    const date = v => { v = str(v, 10); if (v && !/^\d{4}-\d{2}-\d{2}$/.test(v)) throw new Error('bad date'); return v; };
    const problem = str(raw.problem, 20);
    if (!PROBLEMS[problem] && problem !== 'not-sure') throw new Error('bad problem');
    const item = {
      id: /^[a-z0-9]{6,24}$/.test(raw.id || '') ? raw.id : uid(), problem,
      link: str(raw.link, LIMITS.link), label: str(raw.label, LIMITS.label), notes: str(raw.notes, LIMITS.notes),
      reference: str(raw.reference, LIMITS.reference), sentTo: str(raw.sentTo, LIMITS.sentTo),
      sentOn: date(raw.sentOn), checkBack: date(raw.checkBack), created: date(raw.created) || today(), updated: date(raw.updated) || today(),
      status: Object.hasOwn(STATUS, raw.status || 'not-started') ? (raw.status || 'not-started') : 'not-started',
      answers: {}, asks: [], done: {}, ticks: {}, letters: {},
    };
    const answers = raw.answers || {};
    if (typeof answers !== 'object' || Array.isArray(answers)) throw new Error('bad answers');
    for (const [k, v] of Object.entries(answers).slice(0, 12)) {
      if (k === 'safety') { if (!Array.isArray(v)) throw new Error('bad safety'); item.answers.safety = v.filter(x => Object.hasOwn(SAFETY, x)); }
      else if (/^[a-z]{2,12}$/.test(k) && typeof v === 'string' && v.length <= 20) item.answers[k] = v;
    }
    if (!Object.hasOwn(COUNTRY, item.answers.country || '')) item.answers.country = 'au';
    if (Array.isArray(raw.asks)) item.asks = raw.asks.filter(a => Object.hasOwn(DATA.asks, a)).slice(0, 5);
    for (const key of ['done', 'ticks']) {
      const src = raw[key] || {};
      if (typeof src !== 'object' || Array.isArray(src)) throw new Error('bad ' + key);
      for (const [k, v] of Object.entries(src).slice(0, 40)) if (/^[a-z]{2,12}(:\d{1,2})?$/.test(k) && typeof v === 'boolean') item[key][k] = v;
    }
    const letters = raw.letters || {};
    for (const [k, v] of Object.entries(letters)) if (Object.hasOwn(DATA.letters, k) && typeof v === 'string' && v.length <= 16000) item.letters[k] = v;
    return item;
  }

  function fromV1(v1) {
    // v1 desk: one concern. Becomes one tracker item, nothing lost.
    if (!v1 || v1.version !== 1 || typeof v1 !== 'object') throw new Error('not v1');
    const map = {article: ['old-news', {now: 'left-out'}], outdated: ['old-news', {now: 'left-out'}], review: ['review', {}], personal: ['people-search', {}], 'wrong-person': ['old-news', {who: 'same-name'}], safety: ['not-sure', {}]};
    const [problem, extra] = map[v1.issue] || ['not-sure', {}];
    const status = {'not-started': 'not-started', preparing: 'preparing', submitted: 'submitted', waiting: 'waiting', closed: 'closed'}[v1.status] || 'not-started';
    const notes = [v1.concern && 'What needs attention: ' + v1.concern, v1.evidence && 'Evidence notes: ' + v1.evidence, v1.region && 'Region: ' + v1.region, v1.notes].filter(Boolean).join('\n\n');
    return cleanItem({problem, answers: Object.assign({country: 'au', who: 'me', status: 'finished'}, extra, v1.issue === 'safety' ? {safety: ['threat']} : {}),
      link: String(v1.url || '').slice(0, LIMITS.link), label: String(v1.title || '').slice(0, LIMITS.label), status,
      notes: notes.slice(0, LIMITS.notes), reference: String(v1.reference || '').slice(0, LIMITS.reference), checkBack: /^\d{4}-\d{2}-\d{2}$/.test(v1.followup || '') ? v1.followup : ''});
  }

  function validated(input) {
    if (input && input.version === 1) return {version: 2, items: [fromV1(input)], draft: null};
    if (!input || typeof input !== 'object' || input.version !== 2 || !Array.isArray(input.items) || input.items.length > MAX_ITEMS) throw new Error('This isn’t a Fix My Name Online tracker file.');
    return {version: 2, items: input.items.map(cleanItem), draft: input.draft ? cleanItem(input.draft) : null};
  }

  function store() {
    const text = JSON.stringify(state);
    try {
      if (persistence) localStorage.setItem(KEY, text);
      else sessionStorage.setItem(KEY, text);
    } catch (_) {
      if (persistence) { persistence = false; flash = 'Saving on this browser didn’t work. Download a copy instead.'; renderStorage(); }
    }
  }
  function changed() { dirty = true; store(); }

  function load() {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved) { if (saved.length > 400000) throw new Error('too big'); state = validated(JSON.parse(saved)); persistence = true; return; }
      const old = localStorage.getItem(OLD_KEY);
      if (old) {
        state = validated(JSON.parse(old)); persistence = true;
        localStorage.setItem(KEY, JSON.stringify(state)); localStorage.removeItem(OLD_KEY);
        flash = 'We’ve moved your saved notes into the new tracker.';
        return;
      }
    } catch (_) { flash = 'Your saved tracker couldn’t be read, so nothing was changed. You can restore a downloaded copy instead.'; }
    try { const tab = sessionStorage.getItem(KEY); if (tab) state = validated(JSON.parse(tab)); } catch (_) { /* start fresh */ }
  }

  // ---------- plan building ----------
  function planKey(item) {
    if (item.problem !== 'not-sure') return item.problem;
    return (DATA.notSure.find(r => matches(r.when, item.answers)) || {plan: 'general'}).plan;
  }
  function stepLetter(step, a) {
    let letter = step.letter || null;
    for (const alt of step.letter_when || []) if (matches(alt.when, a)) { letter = alt.letter; break; }
    return letter;
  }
  function stepLinks(step, a) {
    let links = step.links && matches(step.links_when, a) ? [...step.links] : [];
    for (const [qid, byValue] of Object.entries(step.links_by || {})) links = links.concat(byValue[a[qid]] || []);
    return links;
  }
  function buildPlan(item) {
    const key = planKey(item);
    const plan = DATA.plans[key];
    const a = item.answers;
    const safety = a.safety || [];
    const ongoing = a.status === 'ongoing';
    const help = [...safety];
    if (ongoing) help.push('ongoing');
    const steps = (ongoing && plan.ongoing_steps ? plan.ongoing_steps : plan.steps).filter(s => matches(s.when, a));
    return {
      key, plan, steps, help, ongoing,
      title: pick(plan.title, a), lede: pick(plan.lede, a),
      ifNo: ongoing ? [] : plan.if_no.filter(i => matches(i.when, a)),
      pack: plan.pack && !safety.length && !ongoing,
    };
  }
  function defaultAsks(item) {
    const plan = DATA.plans[planKey(item)];
    const step = plan.steps.find(s => s.asks);
    if (!step) return [];
    const d = step.default_asks || {};
    return (d[item.answers.now] || d._ || [step.asks[0]]).slice();
  }
  function askSentence(asks) {
    const phrases = asks.map(k => DATA.asks[k] && DATA.asks[k].phrase).filter(Boolean);
    if (!phrases.length) return 'I’m writing to ask you to update the page.';
    return 'I’m writing to ask you to ' + phrases[0] + '.' + phrases.slice(1).map(p => ' If that isn’t possible, could you ' + p + '?').join('');
  }

  // Letter as DOM (fill-in fields highlighted) and as plain text.
  function letterParas(key, item) {
    return DATA.letters[key].paras.filter(p => matches(p.when, item.answers)).map(p => p.text.replace('{{ask}}', askSentence(item.asks.length ? item.asks : defaultAsks(item))));
  }
  function fillValue(field, item) {
    if (field === 'link' && item.link) return item.link;
    if (field === 'sent' && item.sentOn) return nice(item.sentOn);
    return '';
  }
  function letterPlain(key, item) {
    if (item.letters[key]) return item.letters[key];
    return letterParas(key, item).map(t => t.replace(/\{\{(\w+)\|([^}]+)\}\}/g, (_, f, label) => fillValue(f, item) || '[' + label + ']')).join('\n\n');
  }
  function letterNode(key, item) {
    const body = el('div', {class: 'letter-body', contenteditable: 'true', spellcheck: 'true', role: 'textbox', 'aria-multiline': 'true', 'aria-label': DATA.letters[key].name + ' (you can edit this)', id: 'letter-' + key});
    if (item.letters[key]) {
      item.letters[key].split(/\n{2,}/).forEach(p => body.append(el('p', {}, p)));
    } else {
      for (const text of letterParas(key, item)) {
        const p = el('p');
        let last = 0;
        text.replace(/\{\{(\w+)\|([^}]+)\}\}/g, (m, field, label, offset) => {
          p.append(text.slice(last, offset));
          const value = fillValue(field, item);
          p.append(value ? el('span', {class: 'filled'}, value) : el('span', {class: 'fill'}, label));
          last = offset + m.length; return m;
        });
        p.append(text.slice(last));
        body.append(p);
      }
    }
    body.addEventListener('input', () => {
      item.letters[key] = body.innerText.replace(/\n{3,}/g, '\n\n').trim().slice(0, 16000);
      changed();
      const reset = body.parentNode && body.parentNode.querySelector('[data-reset]');
      if (reset) reset.hidden = false;
    });
    return body;
  }
  function letterCard(key, item, label) {
    const name = label || ('Free letter · ' + DATA.letters[key].name);
    const reset = el('button', {type: 'button', class: 'btn btn-secondary btn-sm', 'data-reset': '1', hidden: !item.letters[key], onclick: () => { delete item.letters[key]; changed(); render(); }}, 'Reset');
    const copy = el('button', {type: 'button', class: 'btn btn-secondary btn-sm', onclick: async e => {
      try { await navigator.clipboard.writeText(letterPlain(key, item)); e.currentTarget.lastChild.textContent = 'Copied'; } catch (_) { say('Copy didn’t work here. Select the letter text and copy it instead.'); }
    }}, svg('copy'), el('span', {}, 'Copy'));
    const dl = el('button', {type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => download(letterPlain(key, item), 'text/plain;charset=utf-8', `FMNO-${DATA.letters[key].name.replace(/[^A-Za-z]+/g, '-')}.txt`)}, svg('download'), el('span', {}, 'Download'));
    return el('div', {class: 'letter'},
      el('div', {class: 'letter-bar'}, el('strong', {}, name), el('span', {class: 'btn-row'}, reset, copy, dl)),
      letterNode(key, item),
      el('p', {class: 'letter-hint small'}, 'Click into the letter to edit it. The highlighted parts are for you to fill in. You send it yourself.'));
  }
  function linkButton(id, primary) {
    const link = DATA.links[id];
    if (!link) return null;
    return el('a', {class: primary ? 'btn btn-secondary btn-sm' : 'btn-quiet btn-sm', href: link.url, target: '_blank', rel: 'noopener noreferrer'}, link.label, ' ', svg('ext'), el('span', {class: 'sr'}, ' (opens in a new tab)'));
  }
  function checkedNote(ids) {
    const dates = ids.map(id => DATA.links[id] && DATA.links[id].checked).filter(Boolean);
    return dates.length ? el('p', {class: 'small'}, 'Official links last checked ' + nice(dates.sort()[0]) + '.') : null;
  }

  // ---------- shared view parts ----------
  const LABELS = ['What’s showing up', 'A few questions', 'Your plan', 'Track it'];
  function head(step, eyebrow, title, lede) {
    return el('section', {class: 'page-head'}, el('div', {class: 'wrap'},
      el('ol', {class: 'stepper', 'aria-label': 'Progress'}, LABELS.map((l, i) => el('li', {class: i + 1 < step ? 'done' : (i + 1 === step ? 'now' : ''), 'aria-current': i + 1 === step ? 'step' : null}, el('span', {}, l)))),
      el('p', {class: 'step-count'}, `Step ${step} of 4 · ${LABELS[step - 1]}`),
      el('p', {class: 'eyebrow', style: 'margin-top:28px'}, eyebrow),
      el('h1', {style: 'margin-top:8px', tabindex: '-1', id: 'view-title'}, title),
      lede ? el('p', {class: 'lede'}, lede) : null,
      el('p', {class: 'desk-message', role: 'status', 'aria-live': 'polite', id: 'desk-message'}, flash)));
  }
  function say(text) { const m = document.getElementById('desk-message'); if (m) m.textContent = text; }

  function privacyCard() {
    return el('div', {class: 'card stack'},
      el('h3', {class: 'h-icon'}, svg('lock', 'icon'), 'Private by design'),
      el('ul', {class: 'ticks'}, el('li', {}, 'Nothing you type here is sent to us'), el('li', {}, 'No analytics on this page'), el('li', {}, 'No name or email needed'), el('li', {}, 'Close the tab and it’s gone, unless you choose to save it')));
  }
  function storageCard() {
    const box = el('input', {type: 'checkbox', id: 'desk-save', checked: persistence ? true : null});
    box.addEventListener('change', () => {
      if (box.checked) {
        persistence = true;
        try { localStorage.setItem(KEY, JSON.stringify(state)); sessionStorage.removeItem(KEY); say('Saved on this browser. Only use this on your own device.'); }
        catch (_) { persistence = false; box.checked = false; say('Saving on this browser didn’t work. Download a copy instead.'); }
      } else {
        try { localStorage.removeItem(KEY); localStorage.removeItem(OLD_KEY); } catch (_) { /* ignore */ }
        persistence = false; store(); say('Removed from this browser. It stays in this tab until you close it.');
      }
      renderStorage();
    });
    const file = el('input', {type: 'file', id: 'import-file', accept: '.json,application/json', hidden: true, onchange: restore});
    return el('div', {class: 'card stack-sm', id: 'storage-card'},
      el('h3', {class: 'h-icon'}, svg('lock', 'icon'), 'Where this is kept'),
      el('p', {class: 'meta', id: 'storage-mode'}, ''),
      el('label', {class: 'check-row', for: 'desk-save'}, box, el('span', {}, 'Save on this browser so I can come back')),
      el('p', {class: 'small'}, 'Anyone using this browser could see it, so don’t save it on a shared or work computer.'),
      el('div', {class: 'btn-row', style: 'margin-top:8px'},
        el('button', {type: 'button', class: 'btn btn-secondary btn-sm', id: 'export-json', onclick: () => download(JSON.stringify({version: 2, exported: today(), items: state.items, draft: state.draft}, null, 2), 'application/json', 'FMNO-Tracker-Backup.json')}, svg('download'), 'Download a copy'),
        el('button', {type: 'button', class: 'btn btn-secondary btn-sm', id: 'import-json', onclick: () => file.click()}, svg('upload'), 'Restore a copy'), file),
      el('p', {}, el('button', {type: 'button', class: 'btn-quiet btn-sm danger', id: 'clear-desk', onclick: clearAll}, 'Clear everything from this browser')));
  }
  function renderStorage() {
    const mode = document.getElementById('storage-mode');
    if (mode) mode.textContent = persistence ? 'Saved on this browser, on this device only. We never see it.' : 'Kept in this tab only. Close the tab and it’s gone, unless you save it or download a copy.';
    const box = document.getElementById('desk-save');
    if (box) box.checked = persistence;
  }

  function download(content, type, filename) {
    const url = URL.createObjectURL(new Blob([content], {type}));
    const a = el('a', {href: url, download: filename});
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    say('Downloaded. Check your downloads folder.');
  }
  async function restore(e) {
    const input = e.target; const f = input.files[0];
    if (!f) return;
    try {
      if (f.size > 400000) throw new Error('That file is too big to be a tracker copy.');
      const next = validated(JSON.parse(await f.text()));
      if ((state.items.length || state.draft) && !confirm('Replace what’s here with this copy? Download your current tracker first if you need it.')) return;
      state = next; changed(); flash = 'Restored. Nothing was uploaded.'; go(state.items.length ? '#tracker' : '');
    } catch (err) { say(err instanceof SyntaxError ? 'That file isn’t a valid tracker copy. Nothing was changed.' : err.message); }
    finally { input.value = ''; }
  }
  function clearAll() {
    if (!confirm('Clear your plan and tracker from this browser? Files you’ve downloaded won’t be touched.')) return;
    try { localStorage.removeItem(KEY); localStorage.removeItem(OLD_KEY); sessionStorage.removeItem(KEY); } catch (_) { say('Your browser blocked this. Clear this site’s data in your browser settings.'); return; }
    state = {version: 2, items: [], draft: null}; persistence = false; dirty = false; flash = 'Cleared. Downloaded files are still yours.'; go('');
  }

  function tiles(selected, onPick) {
    const wrap = el('div', {class: 'tiles tiles-3 compact-phone', role: 'group', 'aria-label': 'What did you find?'});
    for (const p of DATA.problems) {
      wrap.append(el('button', {type: 'button', class: 'tile' + (p.key === selected ? ' is-selected' : ''), 'aria-pressed': p.key === selected ? 'true' : 'false', 'data-problem': p.key, onclick: () => onPick(p.key)},
        svg(p.icon, 'icon'), el('strong', {}, p.label), el('span', {}, p.hint)));
    }
    wrap.append(el('button', {type: 'button', class: 'tile tile-wide' + (selected === 'not-sure' ? ' is-selected' : ''), 'aria-pressed': selected === 'not-sure' ? 'true' : 'false', 'data-problem': 'not-sure', onclick: () => onPick('not-sure')},
      el('strong', {}, 'Something else, or I’m not sure'), svg('arrow')));
    return wrap;
  }

  // ---------- view: the free check ----------
  function newDraft(problem) {
    const prev = state.draft && state.draft.answers ? state.draft.answers.country : null;
    return cleanItem({problem, answers: {country: prev || guessCountry()}});
  }
  function renderCheck() {
    const params = new URLSearchParams(location.search);
    const wanted = params.get('problem');
    if (wanted && (PROBLEMS[wanted] || wanted === 'not-sure') && (!state.draft || state.draft.problem !== wanted) && !root.dataset.prefilled) {
      state.draft = newDraft(wanted); root.dataset.prefilled = '1';
    }
    const d = state.draft;
    const view = el('div');
    const fromSnapshot = params.get('from') === 'snapshot';
    view.append(head(d ? 2 : 1, 'Free check', 'What’s showing up for your name?', 'Pick the closest one, then answer a few quick questions. Your plan comes straight after. It takes about two minutes.'));
    const main = el('div', {class: 'stack-lg'});
    if (fromSnapshot) main.append(el('div', {class: 'callout callout-info'}, svg('info', 'icon icon-sm'), el('p', {}, el('strong', {}, 'The Free Search Snapshot is now this free check.'), 'There’s no email or sign-up any more. Your plan appears on this page.')));
    main.append(el('section', {class: 'card'}, el('h2', {class: 'h-sans'}, '1. What did you find?'), el('div', {class: 'mt-2'}, tiles(d && d.problem, key => { state.draft = newDraft(key); changed(); renderCheckInto(); const q = document.getElementById('questions'); if (q) q.scrollIntoView({behavior: 'smooth', block: 'start'}); }))));
    if (d) main.append(questionsCard(d), safetyCard(d), el('p', {class: 'form-msg', id: 'check-error', role: 'alert'}),
      el('div', {class: 'btn-row stack-phone'},
        el('button', {type: 'button', class: 'btn btn-primary', id: 'show-plan', onclick: showPlan}, 'Show my plan ', svg('arrow')),
        state.items.length ? el('a', {class: 'btn btn-secondary', href: '/self-service/tracker'}, 'Go to my tracker') : null));
    const aside = el('aside', {class: 'aside stack'}, privacyCard(),
      el('div', {class: 'callout callout-brand'}, svg('nosearch', 'icon'), el('p', {}, el('strong', {}, 'We don’t search Google.'), 'You tell us what you found, and we match it to the steps that fit. No scores, no guesses.')));
    view.append(el('div', {class: 'wrap split'}, main, aside));
    return view;
  }
  function renderCheckInto() { render(); }

  function radioGroup(q, item) {
    const name = 'q-' + q.id;
    return el('fieldset', {class: 'field', 'data-q': q.id},
      el('legend', {class: 'label'}, q.label),
      el('div', {class: 'choices' + (q.stack ? '' : ' inline')}, q.options.map(o => el('label', {class: 'choice'},
        el('input', {type: 'radio', name, value: o.value, checked: item.answers[q.id] === o.value ? true : null, onchange: () => { item.answers[q.id] = o.value; changed(); }}),
        el('span', {class: 'dot', 'aria-hidden': 'true'}),
        el('span', {}, o.label, o.small ? el('small', {}, o.small) : null)))));
  }
  function questionsCard(d) {
    const qs = DATA.questions[d.problem] || [];
    const country = el('select', {class: 'select', id: 'q-country', onchange: e => { d.answers.country = e.target.value; changed(); if (window.fmnoSetSafety) window.fmnoSetSafety(e.target.value); }},
      DATA.countries.map(([v, l]) => el('option', {value: v, selected: d.answers.country === v ? true : null}, l)));
    const link = el('input', {class: 'input', id: 'q-link', type: 'url', inputmode: 'url', autocomplete: 'off', maxlength: String(LIMITS.link), placeholder: 'https://', value: d.link || null, oninput: e => { d.link = e.target.value.slice(0, LIMITS.link); changed(); }});
    const name = d.problem === 'not-sure' ? 'what you found' : PROBLEMS[d.problem].label.replace(/^(An|A) /, '').toLowerCase();
    return el('section', {class: 'card', id: 'questions'},
      el('h2', {class: 'h-sans'}, `2. A few questions about ${name}`),
      el('p', {class: 'meta mt-1'}, 'They decide which steps, letters and official forms fit.'),
      el('div', {class: 'mt-3'},
        qs.map(q => radioGroup(q, d)),
        el('div', {class: 'field'}, el('label', {class: 'label', for: 'q-country'}, 'Where do you live?'), el('span', {class: 'hint'}, 'This decides which laws and official routes apply.'), country),
        el('div', {class: 'field'}, el('label', {class: 'label', for: 'q-link'}, 'Paste the link ', el('span', {class: 'meta', style: 'font-weight:400'}, '(optional)')), el('span', {class: 'hint'}, 'It stays in this browser. We use it to fill in your letter.'), link)));
  }
  function safetyCard(d) {
    const set = new Set(d.answers.safety || []);
    const none = el('input', {type: 'checkbox', id: 'safety-none', checked: d.answers.safety && !set.size ? true : null});
    const boxes = Object.entries(SAFETY).map(([k, label]) => {
      const box = el('input', {type: 'checkbox', id: 'safety-' + k, value: k, checked: set.has(k) ? true : null});
      box.addEventListener('change', () => { if (box.checked) { set.add(k); none.checked = false; } else set.delete(k); d.answers.safety = [...set]; changed(); });
      return el('label', {class: 'choice', for: 'safety-' + k}, box, el('span', {class: 'box', 'aria-hidden': 'true'}), el('span', {}, label));
    });
    none.addEventListener('change', () => { if (none.checked) { set.clear(); boxes.forEach(b => { b.querySelector('input').checked = false; }); } d.answers.safety = [...set]; changed(); });
    return el('section', {class: 'card', 'data-q': 'safety'},
      el('h2', {class: 'h-sans'}, '3. One safety check'),
      el('p', {class: 'meta mt-1'}, 'Is any of this true right now?'),
      el('div', {class: 'choices mt-2'}, boxes, el('label', {class: 'choice', for: 'safety-none'}, none, el('span', {class: 'box', 'aria-hidden': 'true'}), el('span', {}, 'None of these'))),
      el('div', {class: 'callout callout-info mt-2'}, svg('info', 'icon icon-sm'), el('p', {}, 'If any of these are true, your plan starts with the people who can act quickly, like eSafety or the police, then shows the rest of the steps.')));
  }
  function showPlan() {
    const d = state.draft;
    const missing = (DATA.questions[d.problem] || []).find(q => !d.answers[q.id]);
    const err = document.getElementById('check-error');
    if (missing) { err.textContent = 'Please answer: ' + missing.label; const f = root.querySelector(`[data-q="${missing.id}"] input`); if (f) f.focus(); return; }
    if (!Array.isArray(d.answers.safety)) { err.textContent = 'Please answer the safety check (tick “None of these” if none apply).'; const f = document.getElementById('safety-threat'); if (f) f.focus(); return; }
    if (d.link && !/^https?:\/\/[^\s]+\.[^\s]+/i.test(d.link)) { err.textContent = 'That link doesn’t look right. It should start with https:// (or leave it empty).'; document.getElementById('q-link').focus(); return; }
    d.asks = defaultAsks(d);
    d.checkBack = '';
    changed(); go('#plan');
  }

  // ---------- view: the plan (draft or tracker item) ----------
  function helpCards(built, item) {
    const c = item.answers.country;
    return built.help.map(type => {
      const h = DATA.help[type];
      const links = (h[c] || []).map(id => linkButton(id, true)).filter(Boolean);
      return el('div', {class: 'callout callout-safe help-first', 'data-help': type}, svg('alert', 'icon'),
        el('div', {class: 'stack-sm'}, el('strong', {}, h.title), el('p', {}, h.text),
          h.numbers && h.numbers[c] ? el('p', {}, el('strong', {}, h.numbers[c])) : null,
          links.length ? el('p', {class: 'btn-row'}, links) : null,
          type !== 'ongoing' ? el('p', {class: 'small'}, 'The rest of your plan is below. You can come back to it any time.') : null));
    });
  }
  function stepNode(step, item, built) {
    const done = !!item.done[step.id];
    const li = el('li', {class: done ? 'done' : '', id: 'step-' + step.id});
    const meta = el('p', {class: 'step-meta'});
    if (step.time) meta.append(el('span', {}, svg('clock'), step.time));
    if (step.you_send) meta.append(el('span', {}, svg('mail'), 'You send it'));
    if (step.check_back) meta.append(el('span', {}, svg('calendar'), 'Check back on ' + nice(item.checkBack || addDays(built.plan.check_back_days))));
    li.append(el('h3', {}, step.title), meta);
    if (step.body) li.append(el('p', {class: 'muted mt-1'}, step.body));
    if (step.checklist) {
      li.append(el('ul', {class: 'checklist mt-1'}, step.checklist.map((text, i) => {
        const k = step.id + ':' + i;
        const box = el('input', {type: 'checkbox', id: 'tick-' + step.id + '-' + i, checked: item.ticks[k] ? true : null});
        box.addEventListener('change', () => {
          item.ticks[k] = box.checked;
          item.done[step.id] = step.checklist.every((_, j) => item.ticks[step.id + ':' + j]);
          changed(); refreshProgress(item, built);
          li.classList.toggle('done', !!item.done[step.id]);
          const doneBox = document.getElementById('done-' + step.id); if (doneBox) doneBox.checked = !!item.done[step.id];
        });
        return el('li', {}, el('label', {class: 'check-row', for: box.id}, box, el('span', {}, text)));
      })));
    }
    if (step.asks) {
      li.append(el('div', {class: 'choices mt-2'}, step.asks.map(k => {
        const ask = DATA.asks[k];
        const box = el('input', {type: 'checkbox', value: k, checked: item.asks.includes(k) ? true : null});
        box.addEventListener('change', () => {
          item.asks = step.asks.filter(x => x === k ? box.checked : item.asks.includes(x));
          changed(); refreshLetters(item);
        });
        return el('label', {class: 'choice'}, box, el('span', {class: 'box', 'aria-hidden': 'true'}), el('span', {}, ask.label, ask.small ? el('small', {}, ask.small) : null));
      })));
    }
    const letter = stepLetter(step, item.answers);
    if (letter) {
      const card = letterCard(letter, item, step.letter_label ? step.letter_label : null);
      card.dataset.letter = letter;
      if (step.letter_collapsed) li.append(el('details', {class: 'mt-2 letter-more'}, el('summary', {}, 'Show the follow-up letter'), card));
      else li.append(el('div', {class: 'mt-2'}, card));
    }
    if (step.where) li.append(el('p', {class: 'meta mt-2'}, el('strong', {}, 'Where to send it: '), step.where));
    const links = stepLinks(step, item.answers);
    if (links.length) li.append(el('p', {class: 'btn-row mt-2'}, links.map((id, i) => linkButton(id, i === 0))), checkedNote(links));
    const doneBox = el('input', {type: 'checkbox', id: 'done-' + step.id, checked: done ? true : null});
    doneBox.addEventListener('change', () => { item.done[step.id] = doneBox.checked; li.classList.toggle('done', doneBox.checked); changed(); refreshProgress(item, built); });
    li.append(el('label', {class: 'check-row done-row', for: doneBox.id}, doneBox, el('span', {}, 'I’ve done this step')));
    return li;
  }
  function refreshLetters(item) {
    root.querySelectorAll('[data-letter]').forEach(card => {
      const key = card.dataset.letter;
      if (item.letters[key]) return;
      card.querySelector('.letter-body').replaceWith(letterNode(key, item));
    });
  }
  function progressCard(item, built) {
    const n = built.steps.filter(s => item.done[s.id]).length;
    return el('div', {class: 'card stack-sm hide-below-desk', id: 'glance'},
      el('p', {class: 'eyebrow'}, 'At a glance'),
      el('p', {}, el('strong', {}, `${n} of ${built.steps.length} steps done`)),
      el('div', {class: 'bar'}, el('span', {style: `width:${Math.round(100 * n / Math.max(1, built.steps.length))}%`})),
      el('ul', {class: 'checklist mt-1'}, built.steps.map(s => el('li', {}, el('span', {class: 'box' + (item.done[s.id] ? ' on' : ''), 'aria-hidden': 'true'}), el('a', {href: '#step-' + s.id, onclick: e => { e.preventDefault(); const t = document.getElementById('step-' + s.id); if (t) t.scrollIntoView({behavior: 'smooth'}); }}, s.title)))));
  }
  function refreshProgress(item, built) { const g = document.getElementById('glance'); if (g) g.replaceWith(progressCard(item, built)); }

  function trackingCard(item) {
    const field = (label, input, hint) => el('div', {class: 'field-sm'}, el('label', {class: 'label-sm', for: input.id}, label), hint ? el('span', {class: 'hint'}, hint) : null, input);
    const bind = (input, key, max) => { input.addEventListener('input', () => { item[key] = input.value.slice(0, max || 10); item.updated = today(); changed(); }); return input; };
    const status = el('select', {class: 'select', id: 'item-status'}, DATA.statuses.map(([v, l]) => el('option', {value: v, selected: item.status === v ? true : null}, l)));
    status.addEventListener('change', () => { item.status = status.value; if (status.value === 'submitted' && !item.sentOn) { item.sentOn = today(); document.getElementById('item-sent').value = item.sentOn; } item.updated = today(); changed(); });
    const ics = el('button', {type: 'button', class: 'btn btn-secondary btn-sm', id: 'item-ics', onclick: () => {
      if (!item.checkBack) { say('Set a check-back date first.'); return; }
      download(icsFor(item), 'text/calendar', 'FMNO-Check-back.ics');
    }}, svg('calendar'), 'Add to my calendar');
    return el('section', {class: 'card stack', id: 'tracking'},
      el('div', {class: 'kicker-row', style: 'justify-content:space-between'}, el('h2', {class: 'h-sans'}, 'Your record'), el('span', {class: 'chip ' + STATUS_CLASS[item.status]}, STATUS[item.status])),
      el('div', {class: 'form-grid'},
        field('Status', status),
        field('Name for this item', bind(el('input', {class: 'input', id: 'item-label', maxlength: '160', value: item.label || null}), 'label', LIMITS.label)),
        field('Sent to', bind(el('input', {class: 'input', id: 'item-sent-to', maxlength: '200', placeholder: 'e.g. the editor', value: item.sentTo || null}), 'sentTo', LIMITS.sentTo)),
        field('Sent on', bind(el('input', {class: 'input', id: 'item-sent', type: 'date', value: item.sentOn || null}), 'sentOn')),
        field('Check back on', bind(el('input', {class: 'input', id: 'item-check', type: 'date', value: item.checkBack || null}), 'checkBack')),
        field('Reference number', bind(el('input', {class: 'input', id: 'item-ref', maxlength: '300', value: item.reference || null}), 'reference', LIMITS.reference))),
      field('Notes', bind(el('textarea', {class: 'textarea', id: 'item-notes', maxlength: '8000', placeholder: 'What you sent, what they said, what you’ll do next.'}, item.notes || ''), 'notes', LIMITS.notes)),
      el('div', {class: 'btn-row'}, ics,
        el('button', {type: 'button', class: 'btn-quiet btn-sm danger', onclick: () => { if (!confirm('Delete this item from your tracker?')) return; state.items = state.items.filter(x => x.id !== item.id); changed(); go('#tracker'); }}, 'Delete this item')),
      el('p', {class: 'small'}, 'You set every status yourself. Nothing is sent to anyone from here.'));
  }

  function renderPlan(item, isDraft) {
    const built = buildPlan(item);
    const problemLabel = item.problem === 'not-sure' ? 'Your answers' : PROBLEMS[item.problem].label.replace(/^(An|A) /, '');
    const eyebrow = `Your plan · ${problemLabel[0].toUpperCase() + problemLabel.slice(1)} · ${COUNTRY[item.answers.country]}`;
    const view = el('div');
    view.append(head(isDraft ? 3 : 4, eyebrow, built.title, built.lede));
    const main = el('div', {class: 'stack-lg'});
    if (!isDraft) main.append(trackingCard(item));
    main.append(...helpCards(built, item));
    if (item.problem === 'not-sure') main.append(el('div', {class: 'callout callout-brand'}, svg('info', 'icon icon-sm'), el('p', {}, el('strong', {}, 'From your answers, this looks like: ' + (PROBLEMS[built.key] ? PROBLEMS[built.key].label.toLowerCase() : 'a page on someone else’s site') + '.'), 'If that’s not right, ', el('a', {href: '/self-service', onclick: e => { e.preventDefault(); go(''); }}, 'pick a different problem'), '.')));
    main.append(el('div', {class: 'grid grid-2'},
      el('div', {class: 'card'}, el('p', {class: 'eyebrow'}, 'Who decides'), el('p', {class: 'mt-1'}, built.plan.who_decides)),
      el('div', {class: 'card'}, el('p', {class: 'eyebrow'}, 'Time'), el('p', {class: 'mt-1'}, built.plan.time))));
    if (built.plan.order && !built.ongoing) main.append(el('div', {class: 'callout callout-warn'}, svg('alert', 'icon icon-sm'), el('p', {}, built.plan.order)));
    const ol = el('ol', {class: 'steps'}, built.steps.map(s => stepNode(s, item, built)));
    if (built.ifNo.length) {
      const ids = built.ifNo.map(i => i.link).filter(Boolean);
      ol.append(el('li', {class: 'if-no'}, el('h3', {}, 'If the answer is no'),
        el('ul', {class: 'ticks mt-1'}, built.ifNo.map(i => el('li', {}, i.text, i.link ? [' ', linkButton(i.link, false)] : null))), checkedNote(ids)));
    }
    main.append(el('section', {class: 'card card-lg steps-card'}, ol));
    if (built.pack) main.append(el('section', {class: 'card stack-sm pack-offer no-print'},
      el('div', {class: 'kicker-row', style: 'justify-content:space-between'}, el('h3', {}, 'Want more help with this one link?'), el('span', {class: 'tag'}, 'Optional · US$19 once')),
      el('p', {class: 'muted'}, 'The letter pack saves your letter, a follow-up and a second letter online for this one link, with calendar reminders and a download. You still check and send everything yourself. Refund within 7 days if you haven’t used it.'),
      el('p', {}, el('a', {href: '/diy-action'}, 'See what’s in the letter pack →'))));
    const actions = el('div', {class: 'btn-row stack-phone no-print'});
    if (isDraft) actions.append(el('button', {type: 'button', class: 'btn btn-primary', id: 'add-to-tracker', onclick: () => addToTracker(item, built)}, svg('plus'), 'Add this plan to my tracker'));
    else actions.append(el('a', {class: 'btn btn-primary', href: '/self-service/tracker', onclick: e => { e.preventDefault(); go('#tracker'); }}, 'Back to my tracker'));
    actions.append(el('button', {type: 'button', class: 'btn btn-secondary', id: 'print-plan', onclick: () => window.print()}, svg('print'), 'Print or save as PDF'),
      el('button', {type: 'button', class: 'btn btn-secondary', id: 'export-text', onclick: () => download(planText(item, built), 'text/plain;charset=utf-8', 'FMNO-My-Plan.txt')}, svg('download'), 'Download as text'));
    if (isDraft) actions.append(el('button', {type: 'button', class: 'btn-quiet', onclick: () => go('')}, 'Change my answers'));
    main.append(actions);
    const aside = el('aside', {class: 'aside stack'}, progressCard(item, built), privacyCard(), storageCard());
    view.append(el('div', {class: 'wrap split'}, main, aside));
    return view;
  }

  function addToTracker(item, built) {
    if (state.items.length >= MAX_ITEMS) { say('Your tracker is full (50 items). Close or delete some first.'); return; }
    const copy = cleanItem(JSON.parse(JSON.stringify(item)));
    copy.id = uid();
    copy.checkBack = copy.checkBack || addDays(built.plan.check_back_days);
    copy.status = Object.values(copy.done).some(Boolean) ? 'preparing' : 'not-started';
    copy.label = copy.label || ((copy.problem === 'not-sure' ? 'Something I found' : PROBLEMS[copy.problem].label.replace(/^(An|A) /, '').replace(/^./, c => c.toUpperCase())) + (host(copy.link) ? ' · ' + host(copy.link) : ''));
    copy.created = today(); copy.updated = today();
    state.items.unshift(copy); state.draft = null;
    flash = 'Added to your tracker.'; changed(); go('#tracker');
  }

  function planText(item, built) {
    const lines = ['FIX MY NAME ONLINE · MY PLAN', built.title, '', 'Your plan for: ' + (item.label || (PROBLEMS[item.problem] || {label: 'something I found'}).label) + ' · ' + COUNTRY[item.answers.country]];
    if (item.link) lines.push('Link: ' + item.link);
    lines.push('', 'WHO DECIDES', built.plan.who_decides, '', 'TIME', built.plan.time);
    built.help.forEach(t => lines.push('', 'FIRST: ' + DATA.help[t].title.toUpperCase(), DATA.help[t].text, ...(DATA.help[t][item.answers.country] || []).map(id => DATA.links[id].label + ': ' + DATA.links[id].url)));
    if (built.plan.order && !built.ongoing) lines.push('', built.plan.order);
    built.steps.forEach((s, i) => {
      lines.push('', `${item.done[s.id] ? '[x]' : '[ ]'} STEP ${i + 1}: ${s.title}`);
      if (s.body) lines.push(s.body);
      (s.checklist || []).forEach((c, j) => lines.push(`   ${item.ticks[s.id + ':' + j] ? '[x]' : '[ ]'} ${c}`));
      if (s.asks) lines.push('   Asking for: ' + (item.asks.map(a => DATA.asks[a].label).join('; ') || 'not chosen yet'));
      const letter = stepLetter(s, item.answers);
      if (letter) lines.push('', '--- ' + DATA.letters[letter].name.toUpperCase() + ' ---', letterPlain(letter, item), '--- end ---');
      if (s.where) lines.push('Where to send it: ' + s.where);
      stepLinks(s, item.answers).forEach(id => lines.push(DATA.links[id].label + ': ' + DATA.links[id].url));
    });
    if (built.ifNo.length) { lines.push('', 'IF THE ANSWER IS NO'); built.ifNo.forEach(i => lines.push('- ' + i.text + (i.link ? ' ' + DATA.links[i.link].url : ''))); }
    if (!state.items.includes(item)) lines.push('');
    else lines.push('', 'MY RECORD', 'Status: ' + STATUS[item.status], 'Sent to: ' + (item.sentTo || '-'), 'Sent on: ' + (item.sentOn || '-'), 'Check back on: ' + (item.checkBack || '-'), 'Reference: ' + (item.reference || '-'), 'Notes: ' + (item.notes || '-'));
    lines.push('', 'You check the facts and send everything yourself. Nothing was sent from Fix My Name Online. No one can promise a result.', 'Official links last checked ' + nice(DATA.lastChecked) + '.');
    return lines.join('\n');
  }
  function icsFor(item) {
    const d = item.checkBack.replace(/-/g, '');
    const next = addDays(1, item.checkBack).replace(/-/g, '');
    const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
    const summary = ('Check back: ' + (item.label || 'my request')).replace(/[\\;,\n]/g, ' ').slice(0, 120);
    return ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Fix My Name Online//Tracker//EN', 'BEGIN:VEVENT', `UID:${item.id}-${d}@fixmynameonline.com`, 'DTSTAMP:' + stamp,
      'DTSTART;VALUE=DATE:' + d, 'DTEND;VALUE=DATE:' + next, 'SUMMARY:' + summary, 'DESCRIPTION:Open your tracker and check for a reply. Nothing is sent automatically.',
      'BEGIN:VALARM', 'TRIGGER:-PT9H', 'ACTION:DISPLAY', 'DESCRIPTION:Check back on your request', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR', ''].join('\r\n');
  }

  // ---------- view: tracker ----------
  function nextStep(item) {
    const built = buildPlan(item);
    if (item.status === 'closed') return {text: 'You closed this' + (item.updated ? ' on ' + nice(item.updated) : ''), due: false};
    if (item.checkBack && ['submitted', 'waiting'].includes(item.status)) {
      const n = daysUntil(item.checkBack);
      if (n <= 0) return {text: 'Due now: check for a reply, or send the follow-up', due: true};
      if (n <= 7) return {text: `Due in ${n} day${n === 1 ? '' : 's'}: check for a reply`, due: true};
    }
    const step = built.steps.find(s => !item.done[s.id]);
    return {text: step ? 'Next: ' + step.title.replace(/^./, c => c.toLowerCase()) : 'All steps done. Update the status when you hear back.', due: false};
  }
  function trackCard(item) {
    const p = PROBLEMS[planKey(item)] || {icon: 'help'};
    const nx = nextStep(item);
    const asked = item.asks.map(a => DATA.asks[a].label).join('; ');
    return el('article', {class: 'track-item', 'data-item': item.id},
      el('div', {class: 'track-top'},
        el('div', {class: 'track-title'}, el('span', {class: 'ico'}, svg(p.icon, 'icon')), el('div', {}, el('h3', {class: 'track-h'}, item.label || 'Untitled'), item.link ? el('p', {class: 'track-url'}, item.link) : null)),
        el('span', {class: 'chip ' + STATUS_CLASS[item.status]}, STATUS[item.status])),
      el('dl', {class: 'track-facts'},
        el('div', {}, el('dt', {}, 'Sent to'), el('dd', {}, item.sentTo || 'Not yet')),
        el('div', {}, el('dt', {}, 'Sent'), el('dd', {}, item.sentOn ? nice(item.sentOn) : 'Not yet')),
        el('div', {}, el('dt', {}, 'Check back'), el('dd', {}, item.checkBack ? nice(item.checkBack) : 'Not set')),
        el('div', {}, el('dt', {}, item.reference ? 'Reference' : 'Asked for'), el('dd', {}, item.reference || asked || '—'))),
      el('div', {class: 'track-next'}, el('span', {class: nx.due ? 'due' : 'muted'}, nx.text),
        el('a', {class: nx.due ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm', href: '#item-' + item.id, onclick: e => { e.preventDefault(); go('#item-' + item.id); }}, 'Open')));
  }
  function renderTracker() {
    const view = el('div');
    view.append(head(4, 'My tracker', 'Everything you’re working on, in one place.', 'Update each one as things happen. You set every status yourself. We never see this list.'));
    const main = el('div', {class: 'stack'});
    const dueSoon = state.items.filter(i => i.checkBack && ['submitted', 'waiting'].includes(i.status) && daysUntil(i.checkBack) <= 7).length;
    if (state.items.length) {
      main.append(el('div', {class: 'kicker-row', style: 'justify-content:space-between'},
        el('p', {}, el('strong', {}, `${state.items.length} item${state.items.length === 1 ? '' : 's'}`), dueSoon ? [' · ', el('span', {class: 'due'}, `${dueSoon} due this week`)] : null),
        el('a', {class: 'btn btn-secondary btn-sm', href: '/self-service', id: 'add-another', onclick: e => { e.preventDefault(); state.draft = null; go(''); }}, svg('plus'), 'Add something else')),
      el('div', {class: 'track'}, state.items.map(trackCard)));
    } else {
      main.append(el('div', {class: 'card stack'}, el('h2', {class: 'h-sans'}, 'Nothing here yet.'), el('p', {class: 'muted'}, 'Start with what’s showing up for your name. Your plan can go straight into this tracker.'),
        tiles(null, key => { state.draft = newDraft(key); changed(); go(''); })));
    }
    main.append(el('details', {class: 'card statuses'}, el('summary', {}, 'What the statuses mean'),
      el('p', {class: 'btn-row mt-2', style: 'gap:8px'}, DATA.statuses.map(([v, l]) => el('span', {class: 'chip ' + STATUS_CLASS[v]}, l))),
      el('p', {class: 'meta mt-1'}, '“Answered” means you heard back, whatever the answer was. Write what they said in your notes so you can decide the next step. A “no” is a normal outcome, and it’s worth recording.')));
    const aside = el('aside', {class: 'aside stack'}, storageCard(),
      el('div', {class: 'card stack-sm muted-card'}, el('p', {class: 'eyebrow muted-eyebrow'}, 'Coming back'), el('h3', {class: 'h-icon'}, svg('bell', 'icon'), 'NameWatch'),
        el('p', {class: 'meta'}, 'Alerts when something new shows up for your name. New sign-ups are paused while we rebuild it.'),
        el('a', {class: 'btn btn-secondary btn-block btn-sm', href: '/name-watch-alerts#waitlist'}, 'Join the waitlist'),
        el('p', {class: 'small'}, 'The waitlist is a separate page. Your email isn’t linked to this tracker.')));
    view.append(el('div', {class: 'wrap split'}, main, aside));
    return view;
  }

  // ---------- routing ----------
  function currentView() {
    const h = location.hash;
    if (h.startsWith('#item-')) { const item = state.items.find(i => i.id === h.slice(6)); if (item) return ['item', item]; }
    if (h === '#plan' && state.draft && state.draft.answers.safety) return ['plan', state.draft];
    if (h === '#tracker' || location.pathname.replace(/\/$/, '') === '/self-service/tracker') return ['tracker'];
    return ['check'];
  }
  function render() {
    const [view, item] = currentView();
    const node = view === 'plan' ? renderPlan(item, true) : view === 'item' ? renderPlan(item, false) : view === 'tracker' ? renderTracker() : renderCheck();
    root.replaceChildren(node);
    root.dataset.view = view;
    document.title = {check: 'Free check', plan: 'Your plan', item: 'Your plan', tracker: 'My tracker'}[view] + ' | Fix My Name Online';
    renderStorage();
    if (window.fmnoSetSafety && (item || state.draft)) window.fmnoSetSafety((item || state.draft).answers.country);
    flash = '';
  }
  function go(hash) {
    let url;
    if (hash === '#tracker') url = '/self-service/tracker';
    else if (hash.startsWith('#item-')) url = '/self-service/tracker' + hash;
    else if (hash === '#plan') url = '/self-service#plan';
    else url = '/self-service';
    history.pushState(null, '', url);
    render();
    const t = document.getElementById('view-title');
    window.scrollTo(0, 0);
    if (t) t.focus({preventScroll: true});
  }
  window.addEventListener('popstate', render);
  window.addEventListener('hashchange', render);
  window.addEventListener('beforeunload', e => { if (dirty && !persistence && state.items.length) { e.preventDefault(); e.returnValue = ''; } });

  load();
  render();
  root.removeAttribute('aria-busy');
})();
