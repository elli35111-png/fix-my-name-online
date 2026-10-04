(() => {
  'use strict';
  const form = document.getElementById('snapshot-form');
  if (!form) return;
  let started = false;
  function track(event) {
    const data = {event, label: 'snapshot_intake_v2', location: location.pathname, source: 'snapshot_form'};
    if (typeof gtag === 'function') gtag('event', event, {form_name: 'snapshot_intake_v2'});
    if (navigator.sendBeacon) navigator.sendBeacon('/api/track-click', new Blob([JSON.stringify(data)], {type: 'application/json'}));
  }
  form.addEventListener('input', () => {
    if (!started) { started = true; track('snapshot_start'); }
  });
  form.addEventListener('submit', () => {
    if (!form.checkValidity()) return;
    const button = document.getElementById('snapshot-submit');
    button.disabled = true;
    button.textContent = 'Preparing your next step…';
    // Submission conversion is emitted by the server only after a record is saved.
  });
  window.addEventListener('pageshow', () => {
    const button = document.getElementById('snapshot-submit');
    button.disabled = false;
    button.textContent = 'Get my Free Snapshot →';
  });
  const errors = document.getElementById('form-errors');
  if (errors) errors.focus();
})();
