(() => {
  'use strict';
  const KEY = 'fmno_self_service_v1';
  const desk = document.getElementById('self-service-desk');
  if (!desk) return;
  const $ = id => document.getElementById(id);
  const LIMITS = {url:2000,region:160,title:160,concern:3000,evidence:5000,reference:300,notes:8000,followup:10};
  const STATUS = {'not-started':'Not started',preparing:'Preparing',submitted:'Submitted by me',waiting:'Waiting for a response',closed:'Closed / no further action'};
  const common = ['Confirm the result and my authority to act.', 'Save the public URL, visible date and a screenshot reference.', 'Record accurate facts and evidence for any correction.'];
  const routes = {
    article: {title:"Start with the publisher's official process", description:"Confirm the result relates to you and identify what is wrong or outdated. Find the publisher's corrections or privacy process and check its requirements.", links:[['Google removal overview','https://support.google.com/websearch/answer/11080680']], steps:[...common,"Find and read the publisher's official corrections or privacy process.",'Decide whether to submit; keep the reference and response.'], paid:true},
    outdated: {title:'Check whether the source page has actually changed',description:"Google's Refresh Outdated Content tool is for content that is no longer available, or is significantly different on the source page. It is not a way to remove unchanged content simply because it is old.",links:[['Refresh Outdated Content help','https://support.google.com/websearch/answer/6349986'],['Open the official tool','https://search.google.com/search-console/remove-outdated-content']],steps:[...common,'Check that the source is removed or significantly changed.','Read eligibility, submit if appropriate, and keep the reference.'],paid:false},
    review: {title:'Match the review to an actual platform policy',description:'Disagreeing with a review or receiving a low rating alone does not make it removable. Document the specific policy issue. Avoid false reports, incentives or coordinated reporting.',links:[['Google: report inappropriate reviews','https://support.google.com/business/answer/4596773'],['Google Maps prohibited content policy','https://support.google.com/contributionpolicy/answer/7400114']],steps:[...common,'Identify the exact platform policy and supporting facts.','Use the official report or appeal process; retain confirmation.'],paid:false},
    personal: {title:'Check the official personal-content criteria',description:'Google has specific pathways for personal information. Check which category applies and what evidence is required. A search removal does not remove the source page.',links:[['Google personal-content removal guidance','https://support.google.com/websearch/answer/9673730']],steps:[...common,'Read the relevant personal-content criteria and safety guidance.','Submit through the official secure channel only if appropriate.'],paid:false},
    'wrong-person': {title:'Establish the identity mismatch before acting',description:'A matching name is not proof a result is about you. Record the distinguishing context and any specific false attribution. Do not claim control over someone else’s accurate information.',links:[['Google removal overview','https://support.google.com/websearch/answer/11080680']],steps:[...common,'Distinguish a shared name from an actual false attribution.','Find the source’s official correction route if facts are wrong.'],paid:false},
    safety: {title:'Pause the DIY route and prioritise appropriate help',description:'If there is immediate danger, contact your local emergency service. Threats, minors or active proceedings need appropriate safety or independent professional support. Do not buy an article pack for this situation.',links:[['Google personal-content guidance','https://support.google.com/websearch/answer/9673730'],['Australia: eSafety reporting','https://www.esafety.gov.au/report']],steps:['Prioritise immediate safety and local emergency help if needed.','Identify the appropriate official safety or professional channel.','Avoid putting sensitive documents into this desk.','Preserve evidence safely when appropriate.','Record only non-sensitive next steps and references.'],paid:false}
  };
  const blank = () => ({version:1,issue:'article',status:'not-started',url:'',region:'',title:'',concern:'',evidence:'',reference:'',notes:'',followup:'',checks:{}});
  let state = blank();
  let dirty = false;
  let persistence = false;
  const message = text => { $('desk-message').textContent = text; };
  function validated(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input) || input.version !== 1 || !Object.hasOwn(routes,input.issue) || !Object.hasOwn(STATUS,input.status)) throw new Error('This is not a compatible FMNO desk backup.');
    const clean = blank();
    clean.issue = input.issue; clean.status = input.status;
    for (const [key,max] of Object.entries(LIMITS)) {
      if (typeof input[key] !== 'string' || input[key].length > max) throw new Error('A backup field is missing, invalid or too long.');
      clean[key] = input[key];
    }
    if (clean.followup && !/^\d{4}-\d{2}-\d{2}$/.test(clean.followup)) throw new Error('Invalid check-in date.');
    if (!input.checks || typeof input.checks !== 'object' || Array.isArray(input.checks)) throw new Error('Invalid checklist data.');
    for (const issue of Object.keys(routes)) {
      const checks = input.checks[issue];
      if (checks !== undefined) {
        if (!Array.isArray(checks) || checks.length !== 5 || checks.some(value => typeof value !== 'boolean')) throw new Error('Invalid checklist data.');
        clean.checks[issue] = [...checks];
      }
    }
    return clean;
  }
  function displayStorage() {
    $('desk-save').checked = persistence;
    $('storage-mode').textContent = persistence ? 'Saved on this browser' : 'This open page only';
    $('storage-detail').textContent = persistence ? 'Same browser, same device. Export a backup too.' : 'Export a backup before closing.';
  }
  function store() {
    if (!persistence) return;
    try { localStorage.setItem(KEY,JSON.stringify(state)); }
    catch (_) { persistence = false; displayStorage(); message('Browser saving failed. Export a backup now; an older saved copy may remain.'); }
  }
  function progress() {
    const checks = state.checks[state.issue] || [];
    const count = checks.filter(Boolean).length;
    $('progress-label').textContent = `${count} of 5 steps`;
    $('desk-progress').value = count;
    $('status-summary').textContent = STATUS[state.status];
  }
  function pathway() {
    const route = routes[state.issue];
    $('pathway-title').textContent = route.title;
    $('pathway-description').textContent = route.description;
    $('desk-upsell').hidden = !route.paid;
    const links = $('pathway-links'); links.replaceChildren();
    route.links.forEach(([text,url]) => { const a = document.createElement('a'); a.textContent = text + ' ↗'; a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; links.appendChild(a); });
    const list = $('desk-checklist'); list.replaceChildren();
    route.steps.forEach((text,index) => {
      const label = document.createElement('label'); label.className = 'desk-check';
      const input = document.createElement('input'); input.type = 'checkbox'; input.checked = !!(state.checks[state.issue] || [])[index]; input.id = `desk-step-${index}`;
      const span = document.createElement('span'); span.textContent = text;
      input.addEventListener('change', () => { if (!state.checks[state.issue]) state.checks[state.issue] = Array(5).fill(false); state.checks[state.issue][index] = input.checked; dirty = true; store(); progress(); });
      label.append(input,span); list.appendChild(label);
    });
    progress();
  }
  function render() { desk.querySelectorAll('[data-field]').forEach(el => { el.value = state[el.dataset.field]; }); pathway(); displayStorage(); }
  try {
    const saved = localStorage.getItem(KEY);
    if (saved) { if (saved.length > 60000) throw new Error('Saved data is too large.'); state = validated(JSON.parse(saved)); persistence = true; message('Your saved desk has been restored on this browser.'); }
  } catch (_) { message('Browser storage is unavailable or the saved copy could not be read. No saved data was overwritten. You can use exports instead.'); }
  render();
  desk.querySelectorAll('[data-field]').forEach(el => el.addEventListener('input', () => {
    state[el.dataset.field] = el.value; dirty = true;
    if (el.dataset.field === 'issue') pathway(); else progress();
    store();
  }));
  $('desk-save').addEventListener('change', () => {
    if ($('desk-save').checked) { persistence = true; store(); displayStorage(); if (persistence) message('Saved on this browser. Use only on a private device.'); }
    else { try { localStorage.removeItem(KEY); persistence = false; displayStorage(); message('Saved browser copy removed. Your open notes remain until you leave.'); } catch (_) { $('desk-save').checked = persistence; message('Could not remove the saved browser copy. Clear this site’s data in browser settings.'); } }
  });
  function download(content,type,filename) {
    const url = URL.createObjectURL(new Blob([content],{type})); const a = document.createElement('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),1000); message('Download requested. Check your downloads before closing this desk.');
  }
  function readable() {
    return ['FMNO — MY SELF-SERVICE NOTES','Private personal record; not verified findings.','',...Object.entries(LIMITS).map(([key]) => `${key.toUpperCase()}: ${state[key]}`),'','STATUS: '+STATUS[state.status],'PATHWAY: '+routes[state.issue].title,'',...routes[state.issue].steps.map((step,i) => `${(state.checks[state.issue] || [])[i] ? '[x]' : '[ ]'} ${step}`),'',...routes[state.issue].links.map(([text,url]) => text+': '+url),'','You confirm the facts and submit any external request. No requests have been sent from this desk.'].join('\n');
  }
  $('export-text').addEventListener('click', () => download(readable(),'text/plain;charset=utf-8','FMNO-My-Action-Notes.txt'));
  $('export-json').addEventListener('click', () => download(JSON.stringify(state,null,2),'application/json','FMNO-Desk-Backup.json'));
  $('import-json').addEventListener('click', () => $('import-file').click());
  $('import-file').addEventListener('change', async () => {
    const file = $('import-file').files[0]; if (!file) return;
    try {
      if (file.size > 60000) throw new Error('The backup is too large (maximum 60 KB).');
      const imported = validated(JSON.parse(await file.text()));
      if (!confirm('Replace the current desk with this backup? Export your current notes first if you need them.')) return;
      state = imported; dirty = true; render(); store(); message('Backup restored. Nothing was uploaded.');
    } catch (error) { message(error instanceof SyntaxError ? 'The file is not valid JSON. Your current notes are unchanged.' : error.message); }
    finally { $('import-file').value = ''; }
  });
  $('clear-desk').addEventListener('click', () => {
    if (!confirm('Clear all notes and this desk’s saved browser copy? Downloaded files will not be deleted.')) return;
    try { localStorage.removeItem(KEY); }
    catch (_) { message('Cannot clear browser storage. Use your browser’s site-data settings; current notes have not been cleared.'); return; }
    state = blank(); persistence = false; dirty = false; render(); message('Desk and saved browser copy cleared. Downloaded files remain yours to manage.');
  });
  $('print-desk').addEventListener('click', () => {
    const win = window.open('','_blank');
    if (!win) { message('Allow the print window, or download readable notes instead.'); return; }
    win.opener = null; win.document.title = 'FMNO — My self-service notes';
    const pre = win.document.createElement('pre'); pre.textContent = readable(); pre.style.cssText = 'white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6 sans-serif;padding:20px'; win.document.body.appendChild(pre); win.print();
  });
  window.addEventListener('beforeunload', event => { if (dirty && !persistence) { event.preventDefault(); event.returnValue = ''; } });
})();
