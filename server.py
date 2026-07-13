"""
FixMyNameOnline™ — Flask Web Server
Landing page, Free Search Snapshot intake, Stripe checkout, and fulfilment-safe onboarding.

Copyright (c) 2026 MadisonJade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of MadisonJade Pty Ltd.
"""
import html
import os
import json
import re
import hmac
import hashlib
from urllib.parse import urlparse
from datetime import datetime
from pathlib import Path

import stripe
import requests
from flask import Flask, request, jsonify, send_from_directory, redirect, Response

try:
    from fulfilment_engine import (
        create_fulfilment_case,
        list_cases,
        get_case,
        next_actions,
        update_task_status,
        approve_task,
        add_case_note,
        validate_public_text,
    )
except Exception:
    create_fulfilment_case = None
    list_cases = get_case = next_actions = update_task_status = approve_task = add_case_note = validate_public_text = None

try:
    from fulfilment_worker import run_task_agent, run_next_ready
except Exception:
    run_task_agent = run_next_ready = None

app = Flask(__name__, static_folder='.', static_url_path='')

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
DOMAIN = os.environ.get('DOMAIN', 'https://fixmynameonline.com').rstrip('/')
SEO_DESCRIPTION = 'Private reputation repair and search protection. Run a free Search Snapshot to see what comes up when people Google your name.'
SEO_IMAGE = DOMAIN + '/og-image.png'
DATA_DIR = Path(os.environ.get('FMNO_DATA_DIR', 'data'))
DATA_DIR.mkdir(exist_ok=True)
LEADS_FILE = DATA_DIR / 'snapshot_leads.jsonl'
ONBOARDING_FILE = DATA_DIR / 'onboarding_submissions.jsonl'
FULFILMENT_QUEUE_FILE = DATA_DIR / 'fulfilment_queue.jsonl'
QUESTIONS_FILE = DATA_DIR / 'client_questions.jsonl'
CONCIERGE_TRANSCRIPTS_FILE = DATA_DIR / 'concierge_transcripts.jsonl'
CASE_ROOMS_FILE = DATA_DIR / 'private_case_rooms.jsonl'
CLICK_EVENTS_FILE = DATA_DIR / 'click_events.jsonl'
DIY_ACTIONS_FILE = DATA_DIR / 'diy_actions.jsonl'
DIY_CHECKOUT_TOKEN_SHA256 = os.environ.get('FMNO_DIY_CHECKOUT_TOKEN_SHA256', '')

FROM_EMAIL = os.environ.get('FMNO_FROM_EMAIL', 'admin@fixmynameonline.com')
FROM_NAME = os.environ.get('FMNO_FROM_NAME', 'FixMyNameOnline')
INTERNAL_EMAIL = os.environ.get('FMNO_INTERNAL_EMAIL') or os.environ.get('ADMIN_EMAIL') or 'Elli35111@gmail.com'

PLANS = {
    'diy-action': {'name': 'DIY Reputation Action Workspace™', 'price': 49, 'mode': 'payment', 'env': 'STRIPE_PRICE_DIY_ACTION', 'payment_link': os.environ.get('FMNO_DIY_PAYMENT_LINK', '')},
    'sentinel': {'name': 'NameWatch Alert™', 'price': 29, 'mode': 'subscription', 'env': 'STRIPE_PRICE_SENTINEL', 'payment_link': os.environ.get('FMNO_SENTINEL_PAYMENT_LINK', '')},
    'removal-review': {'name': 'Removal Review™', 'price': 297, 'mode': 'payment', 'env': 'STRIPE_PRICE_REMOVAL_REVIEW', 'payment_link': 'https://buy.stripe.com/bJe14mfBA3CN8ca6X3cZa04'},
    'review-defence': {'name': 'Review Defence™', 'price': 497, 'mode': 'payment', 'env': 'STRIPE_PRICE_REVIEW_DEFENCE', 'payment_link': 'https://buy.stripe.com/7sY9AS610b5f6426X3cZa05'},
    'starter': {'name': 'Starter™', 'price': 499, 'mode': 'subscription', 'env': 'STRIPE_PRICE_STARTER', 'payment_link': 'https://buy.stripe.com/28E9AS8987T3bom1CJcZa06'},
    'pro': {'name': 'Pro™', 'price': 997, 'mode': 'subscription', 'env': 'STRIPE_PRICE_PRO', 'payment_link': 'https://buy.stripe.com/6oUcN4dtsb5f786dlrcZa07'},
    'premium': {'name': 'Premium™', 'price': 2497, 'mode': 'subscription', 'env': 'STRIPE_PRICE_PREMIUM', 'payment_link': 'https://buy.stripe.com/6oUeVc2OOgpzfEC817cZa08'},
}

TRIAGE_NEXT_STEPS = {
    'alerts': {
        'label': 'NameWatch Alert™ monitoring',
        'summary': 'This looks like a monitoring-first case: we should track Google results, name variants and new risk signals so the client is alerted before a problem grows.',
        'cta': 'View NameWatch Alert™',
        'url': '/checkout/sentinel',
        'priority': 'standard',
    },
    'removal-review': {
        'label': 'DIY Reputation Action Workspace™',
        'summary': 'This looks suitable for a guided DIY action: organise one old article or bad link, build the evidence checklist, prepare the request, then submit it yourself through the official route.',
        'cta': 'See the $49 DIY workspace',
        'url': '/diy-action',
        'priority': 'high',
    },
    'review-defence': {
        'label': 'DIY pathway preview',
        'summary': 'This appears to involve reviews. The first FMNO DIY release currently covers old articles and bad links; review-specific automation is not sold yet.',
        'cta': 'See the current DIY workspace',
        'url': '/diy-action',
        'priority': 'high',
    },
    'repair-plan': {
        'label': 'DIY pathway preview',
        'summary': 'This appears broader than one old article or bad link. Start with the free score; FMNO will only sell a workflow when the deliverables match the problem.',
        'cta': 'See the current DIY workspace',
        'url': '/diy-action',
        'priority': 'standard',
    },
    'high-risk': {
        'label': 'External professional or safety pathway',
        'summary': 'This is outside FMNO’s automated DIY scope. Do not purchase an action workspace for emergencies, threats, minors, active proceedings or complex legal disputes.',
        'cta': 'View Legal Options Hub',
        'url': 'https://www.legaloptionshub.com/',
        'priority': 'urgent',
    },
}

BASE_STYLE = """
:root{--dark:#08090f;--card:#151824;--red:#d91f3d;--grey:#9aa2b6;--light:#e8ecf5;}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 20% 5%,rgba(217,31,61,.16),transparent 28%),var(--dark);color:white;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;line-height:1.5;padding:22px;}
a{color:#ff4d66}.wrap{max-width:980px;margin:0 auto}.card{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.11);border-radius:22px;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.28)}
.logo{font-weight:900;letter-spacing:.12em;color:var(--red);font-size:15px;margin-bottom:22px}.sub{color:var(--grey)}h1{font-size:clamp(32px,6vw,58px);line-height:1.02;margin:0 0 14px}h2{margin-top:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.full{grid-column:1/-1}.snapshot-shell{display:grid;grid-template-columns:1.05fr .75fr;gap:22px;align-items:start}.trust-strip{display:flex;flex-wrap:wrap;gap:10px 18px;color:var(--grey);font-size:12px;margin:18px 0}.trust-strip span:before{content:'•';color:#d4af37;margin-right:8px}.side-card{position:sticky;top:18px}.steps{display:grid;gap:12px}.step{border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);border-radius:16px;padding:14px}.step b{color:#ffb0bd}.microcopy{font-size:12px;color:var(--grey);margin-top:6px}.submit-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.progress{height:7px;background:#0d1019;border:1px solid rgba(255,255,255,.12);border-radius:999px;overflow:hidden;margin:10px 0 18px}.progress span{display:block;height:100%;width:18%;background:linear-gradient(90deg,var(--red),#ff6f85);transition:width .2s ease}
label{display:block;font-weight:700;margin:14px 0 7px}input,select,textarea{width:100%;background:#0d1019;color:white;border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:13px 14px;font:inherit}input:focus,select:focus,textarea:focus{outline:2px solid rgba(217,31,61,.35);border-color:rgba(217,31,61,.65)}textarea{min-height:105px}.btn{display:inline-block;background:linear-gradient(135deg,var(--red),#a81229);border:0;border-radius:13px;color:white;font-weight:800;padding:14px 20px;text-decoration:none;cursor:pointer;font-size:16px}.btn2{background:transparent;border:1px solid rgba(255,255,255,.22)}.note{font-size:13px;color:var(--grey)}.pill{display:inline-block;border:1px solid rgba(217,31,61,.35);background:rgba(217,31,61,.08);padding:7px 10px;border-radius:999px;color:#ffb0bd;font-size:13px;font-weight:700}.ok{color:#31d07a}.err{color:#ff6f85}.recommend{border:1px solid rgba(217,31,61,.35);background:rgba(217,31,61,.08);border-radius:18px;padding:20px;margin:22px 0}@media(max-width:820px){body{padding:14px}.grid,.snapshot-shell{grid-template-columns:1fr}.card{padding:20px}.side-card{position:static}.submit-row .btn{width:100%;text-align:center} }
"""


def utc_now():
    return datetime.utcnow().isoformat() + 'Z'


def safe(value):
    return html.escape(str(value or ''), quote=True)


def tracking_head():
    """Optional ad/analytics tracking. Enabled only when env vars are configured."""
    parts = []
    ga_id = (os.environ.get('FMNO_GA_MEASUREMENT_ID') or os.environ.get('GA_MEASUREMENT_ID') or '').strip()
    meta_pixel_id = (os.environ.get('FMNO_META_PIXEL_ID') or os.environ.get('META_PIXEL_ID') or '').strip()
    if ga_id:
        gid = safe(ga_id)
        parts.append(f'''
<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{gid}');
</script>
''')
    if meta_pixel_id:
        pid = safe(meta_pixel_id)
        parts.append(f'''
<script>
!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window, document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '{pid}');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id={pid}&ev=PageView&noscript=1" /></noscript>
''')
    return ''.join(parts)


def conversion_tracking_event(event_name, payload=None):
    payload = payload or {}
    clean_event = ''.join(ch for ch in str(event_name or '') if ch.isalnum() or ch in ['_', '-']) or 'Lead'
    json_payload = json.dumps(payload, ensure_ascii=False)
    return f'''<script>
try {{
  if (typeof gtag === 'function') gtag('event', '{safe(clean_event)}', {json_payload});
  if (typeof fbq === 'function') fbq('track', '{safe(clean_event)}');
}} catch(e) {{}}
</script>'''


def page(title, body, description=None, canonical_path=None):
    desc = description or SEO_DESCRIPTION
    path = canonical_path or request.path or '/'
    canonical = DOMAIN + (path if path.startswith('/') else '/' + path)
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{safe(title)}</title><meta name=\"description\" content=\"{safe(desc)}\"><link rel=\"canonical\" href=\"{safe(canonical)}\"><meta property=\"og:type\" content=\"website\"><meta property=\"og:site_name\" content=\"FixMyNameOnline™\"><meta property=\"og:title\" content=\"{safe(title)}\"><meta property=\"og:description\" content=\"{safe(desc)}\"><meta property=\"og:url\" content=\"{safe(canonical)}\"><meta name=\"twitter:card\" content=\"summary\"><meta name=\"twitter:title\" content=\"{safe(title)}\"><meta name=\"twitter:description\" content=\"{safe(desc)}\">{tracking_head()}<style>{BASE_STYLE}</style></head><body><div class=\"wrap\"><div class=\"logo\">FIXMYNAMEONLINE™ · MADISONJADE PTY LTD</div>{body}</div></body></html>"""


def append_jsonl(path, payload):
    payload = dict(payload)
    payload.setdefault('created_at', utc_now())
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False) + '\n')
    return payload


def read_jsonl(path, limit=None):
    if not path.exists():
        return []
    rows = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows[-limit:] if limit else rows


def source_category(source, referrer=''):
    combined = f"{source or ''} {referrer or ''}".lower()
    if 'loh' in combined or 'legaloptionshub' in combined:
        return 'loh'
    if any(k in combined for k in ['facebook', 'instagram', 'tiktok', 'x.com', 'twitter', 'meta', 'social']):
        return 'social'
    if any(k in combined for k in ['ad', 'paid', 'utm_medium=cpc', 'utm_medium=paid', 'utm_source=meta', 'utm_source=facebook', 'gclid=', 'fbclid=']):
        return 'paid'
    if 'google.' in combined or 'bing.' in combined or 'duckduckgo' in combined:
        return 'organic'
    return 'direct'


def attribution_from_request(form=None, json_payload=None):
    form = form or {}
    json_payload = json_payload or {}
    args = request.args
    source = (form.get('source_page') or json_payload.get('source_page') or args.get('source') or args.get('utm_source') or 'unknown')
    referrer = (form.get('referrer') or json_payload.get('referrer') or request.headers.get('Referer') or '')
    landing_url = (form.get('landing_url') or json_payload.get('landing_url') or request.url or '')
    utm = {k: (form.get(k) or json_payload.get(k) or args.get(k) or '') for k in ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid']}
    return {
        'source': str(source)[:160],
        'source_page': str(source)[:160],
        'source_category': source_category(source, referrer + ' ' + landing_url + ' ' + ' '.join(utm.values())),
        'referrer': str(referrer)[:400],
        'landing_url': str(landing_url)[:500],
        'path': request.path,
        'utm': {k: str(v)[:220] for k, v in utm.items() if v},
    }


def admin_authorized():
    token = (os.environ.get('FMNO_ADMIN_TOKEN', '') or '').strip()
    supplied = (request.headers.get('X-FMNO-Admin-Token') or request.args.get('token', '') or request.form.get('token', '') or '').strip()
    return bool(token and supplied and supplied == token)


def require_admin_json():
    if not admin_authorized():
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    return None


def approval_secret():
    return (os.environ.get('FMNO_APPROVAL_SECRET') or os.environ.get('FMNO_ADMIN_TOKEN') or 'fmno-local-approval-secret').strip()


def make_approval_token(case_id, task_id):
    raw = f'{case_id}:{task_id}'.encode('utf-8')
    return hmac.new(approval_secret().encode('utf-8'), raw, hashlib.sha256).hexdigest()


def approval_url(case_id, task_id):
    token = make_approval_token(case_id, task_id)
    return f'{DOMAIN}/approval/{safe(case_id)}/{safe(task_id)}?approval_token={token}'


def valid_approval_token(case_id, task_id, token):
    expected = make_approval_token(case_id, task_id)
    return bool(token and hmac.compare_digest(str(token), expected))


def get_task_from_case(case, task_id):
    for task_obj in case.get('tasks', []):
        if task_obj.get('id') == task_id:
            return task_obj
    return None


def latest_case_outputs(case, limit=8):
    items = []
    for task_obj in case.get('tasks', []):
        for generated_at, output in (task_obj.get('outputs') or {}).items():
            items.append({
                'task_id': task_obj.get('id'),
                'task_title': task_obj.get('title'),
                'agent': task_obj.get('agent'),
                'generated_at': generated_at,
                'output': output,
            })
    items.sort(key=lambda item: item.get('generated_at', ''), reverse=True)
    return items[:limit]


def safe_create_fulfilment_case(plan, customer, source, trigger):
    if not create_fulfilment_case:
        return None
    try:
        return create_fulfilment_case(plan, customer, source=source, trigger=trigger)
    except Exception as exc:
        app.logger.warning('Fulfilment case creation failed: %s', exc)
        return None


def run_free_snapshot_pipeline(case):
    """Run the lightweight free-report agents immediately up to the QC gate."""
    if not case or not run_next_ready:
        return []
    results = []
    for _ in range(5):
        result = run_next_ready(case.get('id'), operator='FreeSnapshotAutoWorker')
        results.append(result)
        if not result.get('ok'):
            break
        # Stop after report generation / QC preparation so client send remains manual/QC-gated.
        task_id = (result.get('task') or {}).get('id')
        if task_id == 'FS-005':
            break
    return results


def latest_free_snapshot_report(case):
    if not case:
        return None
    reports = []
    for task_obj in case.get('tasks', []):
        for generated_at, output in (task_obj.get('outputs') or {}).items():
            if output.get('type') == 'free_snapshot_report':
                reports.append((generated_at, output))
    reports.sort(key=lambda item: item[0], reverse=True)
    return reports[0][1] if reports else None


def send_telegram_alert(title, payload):
    token = os.environ.get('FMNO_TELEGRAM_BOT_TOKEN') or os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('FMNO_TELEGRAM_CHAT_ID') or os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat_id:
        return False
    lines = [f"🔴 {title}"] + [f"{k}: {v}" for k, v in payload.items() if v]
    try:
        r = requests.post(
            f'https://api.telegram.org/bot{token}/sendMessage',
            json={'chat_id': chat_id, 'text': '\n'.join(lines)[:3900]},
            timeout=10,
        )
        return r.ok
    except Exception as exc:
        app.logger.warning('Telegram alert failed: %s', exc)
        return False


def send_brevo_email(to_email, to_name, subject, html_body, text_body=''):
    """Send via Brevo API if BREVO_API_KEY exists. Never blocks customer flow."""
    api_key = os.environ.get('BREVO_API_KEY') or os.environ.get('SENDINBLUE_API_KEY')
    if not api_key or not to_email:
        return False
    payload = {
        'sender': {'name': FROM_NAME, 'email': FROM_EMAIL},
        'to': [{'email': to_email, 'name': to_name or to_email}],
        'subject': subject,
        'htmlContent': html_body,
        'textContent': text_body or html_body.replace('<br>', '\n'),
    }
    try:
        response = requests.post(
            'https://api.brevo.com/v3/smtp/email',
            headers={'api-key': api_key, 'accept': 'application/json', 'content-type': 'application/json'},
            json=payload,
            timeout=12,
        )
        if not response.ok:
            app.logger.warning('Brevo email failed %s: %s', response.status_code, response.text[:500])
        return response.ok
    except Exception as exc:
        app.logger.warning('Brevo email exception: %s', exc)
        return False


def alert_email_recipients():
    raw = os.environ.get('FMNO_ALERT_EMAILS') or os.environ.get('FMNO_ALERT_EMAIL') or INTERNAL_EMAIL or 'Elli35111@gmail.com'
    recipients = []
    for item in re.split(r'[,;\s]+', raw):
        item = item.strip()
        if item and '@' in item and item.lower() not in [x.lower() for x in recipients]:
            recipients.append(item)
    if 'Elli35111@gmail.com'.lower() not in [x.lower() for x in recipients]:
        recipients.append('Elli35111@gmail.com')
    return recipients


def send_internal_alert_email(subject, html_body, text_body=''):
    results = {}
    for email in alert_email_recipients():
        results[email] = send_brevo_email(email, 'Elli / FMNO Admin', subject, html_body, text_body)
    return results


def record_email_alert_status(kind, subject, results, context=None):
    append_jsonl(CLICK_EVENTS_FILE, {
        'event': 'email_alert_status',
        'label': kind,
        'subject': subject,
        'results': results,
        'ok': bool(results) and all(bool(v) for v in results.values()),
        'context': context or {},
    })
    return results


def send_checkout_intent_alert(tier, plan, attribution, payment_link):
    html_body = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111;line-height:1.55\">
      <h1>FMNO checkout intent</h1>
      <p>A visitor clicked through to Stripe for a paid FMNO offer.</p>
      <p><strong>Plan:</strong> {safe(plan.get('name'))}<br><strong>Tier:</strong> {safe(tier)}<br><strong>Price:</strong> ${safe(plan.get('price'))}<br><strong>Source:</strong> {safe(attribution.get('source_category'))}</p>
      <p><strong>Stripe/payment link:</strong><br>{safe(payment_link)}</p>
      <p style=\"font-size:12px;color:#666\">This is checkout intent, not confirmed payment. A Stripe completed-payment webhook should follow for paid customers.</p>
    </div>
    """
    subject = f"FMNO checkout intent: {plan.get('name')}"
    results = send_internal_alert_email(subject, html_body)
    return record_email_alert_status('checkout_intent', subject, results, {'tier': tier, 'plan': plan.get('name')})


def infer_paid_tier_from_session(session):
    metadata = session.get('metadata') or {}
    tier = metadata.get('tier') or metadata.get('plan') or metadata.get('plan_key') or ''
    if tier in PLANS:
        return tier
    try:
        amount = int(session.get('amount_total') or 0)
    except Exception:
        amount = 0
    amount_map = {
        2900: 'sentinel',
        29700: 'removal-review',
        49700: 'review-defence',
        49900: 'starter',
        99700: 'pro',
        249700: 'premium',
    }
    if amount in amount_map:
        return amount_map[amount]
    mode = str(session.get('mode') or '').lower()
    if mode == 'subscription':
        return 'sentinel' if amount and amount <= 5000 else 'starter'
    return 'starter'


def send_paid_customer_alert(tier, plan_name, customer_email, session, case=None):
    amount = session.get('amount_total')
    if amount is not None:
        try:
            amount_display = f"${int(amount)/100:.2f} {str(session.get('currency') or '').upper()}"
        except Exception:
            amount_display = str(amount)
    else:
        amount_display = ''
    html_body = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111;line-height:1.55\">
      <h1>FMNO PAID CUSTOMER</h1>
      <p><strong>Plan:</strong> {safe(plan_name)}<br><strong>Tier:</strong> {safe(tier)}<br><strong>Customer email:</strong> {safe(customer_email)}<br><strong>Amount:</strong> {safe(amount_display)}</p>
      <p><strong>Stripe session:</strong> {safe(session.get('id'))}<br><strong>Case ID:</strong> {safe(case.get('id') if case else '')}</p>
      <p><a href=\"{DOMAIN}/admin/fulfilment\">Open FMNO fulfilment dashboard</a></p>
    </div>
    """
    subject = f"FMNO PAID CUSTOMER: {plan_name} — {customer_email or 'no email'}"
    results = send_internal_alert_email(subject, html_body)
    return record_email_alert_status('paid_customer', subject, results, {'tier': tier, 'plan_name': plan_name, 'customer_email': customer_email, 'session_id': session.get('id')})


CONCIERGE_FIELDS = [
    ('names_to_check', 'What name, business name, old name, nickname, or associated name should we privately search first?'),
    ('country_state', 'What country, state, or city context should we consider for that search?'),
    ('problem_links', 'If you already have a link, article title, review page, or search phrase, paste it here. If not, write “search first”.'),
    ('goal', 'What are you hoping to understand or fix from the Free Search Snapshot™?'),
    ('contact_name', 'What name should we use when we send the private snapshot?'),
    ('email', 'What email should we send the private snapshot to?'),
]

CONCIERGE_TOPIC_LABELS = {
    'bad-results': 'Bad Google result',
    'old-articles': 'Old article or outdated result',
    'privacy': 'Private information showing online',
    'reviews': 'Fake or unfair review',
    'positive': 'Positive search footprint',
    'snapshot': 'Free Search Snapshot',
}

CONCIERGE_SAFE_REPLACEMENTS = {
    'guaranteed removal': 'careful pathway review',
    'guarantee removal': 'assess removal options',
    'guaranteed ranking': 'stronger search-readiness',
    'guarantee ranking': 'improve search-readiness',
    'erase google': 'review what is showing on Google',
    'bury results': 'build a stronger truthful search footprint',
    'push down unwanted content': 'review removal options and build a stronger truthful search footprint',
    'push down negative content': 'review removal options and build a stronger truthful search footprint',
    'suppression': 'positive search-footprint support',
    'manipulate search': 'improve accurate search signals',
    'we will delete it': 'we will assess the strongest pathway',
    'we can delete it': 'we can assess the strongest pathway',
    'legal guarantee': 'careful private review',
    'guaranteed de-index': 'de-indexing pathway review',
    'guarantee de-index': 'review de-indexing options',
}


def clean_concierge_text(text):
    text = str(text or '').strip()
    lowered = text.lower()
    for phrase, replacement in CONCIERGE_SAFE_REPLACEMENTS.items():
        if phrase in lowered:
            text = text.replace(phrase, replacement).replace(phrase.title(), replacement)
            lowered = text.lower()
    return text[:900]


def concierge_next_field(collected):
    for key, question in CONCIERGE_FIELDS:
        if not str(collected.get(key, '')).strip():
            return key, question
    return None, None


def fallback_concierge_reply(topic, collected, next_question, ready=False):
    issue = CONCIERGE_TOPIC_LABELS.get(topic or collected.get('issue_type'), 'private search issue')
    if ready:
        return 'Thank you. I have enough to prepare this as a private Free Search Snapshot™. Nothing public happens from this intake; it gives FMNO the context to privately map the issue and recommend the safest next step.'
    if not collected.get('names_to_check'):
        return f'I understand — {issue.lower()} can feel urgent, but the safest first step is to map what people may actually see. We will keep this private and take it one step at a time.'
    if not collected.get('problem_links'):
        return 'Good. We can start from the name and location context. Links or screenshots help if you already have them, but they are not required for the first private snapshot.'
    return 'Understood. I will keep this focused on a private assessment: what is showing, what type of result it is, and which pathway may be safest to review first.'


def build_concierge_messages(topic, collected, user_message, next_question, ready):
    system = '''You are Private Search Concierge™ for FixMyNameOnline™, operated by MadisonJade Pty Ltd.
Tone: premium, calm, private, human, concise.
Role: AI-assisted intake only. Keep replies short and move toward Free Search Snapshot™.
Do not provide legal advice. Do not promise removals, rankings, de-indexing, platform decisions, suppression, or search outcomes.
Do not use alarmist words like doxxing, swatting, crisis, emergency, or permanent damage.
Do not expose internal agent names or backend machinery.
Use safe language: assess the strongest pathway, private snapshot, removal/review options, positive search footprint, no public action without approval.
The backend controls the exact next question. If next_question_to_ask is present, copy it exactly as next_question.
Return ONLY valid JSON with keys: reply, next_question, risk_level, recommended_pathway, cta.'''
    user = {
        'selected_issue': CONCIERGE_TOPIC_LABELS.get(topic or collected.get('issue_type'), topic or collected.get('issue_type')),
        'collected_fields': collected,
        'latest_user_message': user_message,
        'next_question_to_ask': next_question,
        'ready_to_submit': ready,
    }
    return [
        {'role': 'system', 'content': system},
        {'role': 'user', 'content': json.dumps(user, ensure_ascii=False)},
    ]


def parse_model_json(content):
    content = str(content or '').strip()
    if content.startswith('```'):
        content = content.strip('`')
        if content.lower().startswith('json'):
            content = content[4:].strip()
    candidates = [content]
    # MiniMax reasoning models often wrap the actual JSON after a <think> block.
    candidates.append(re.sub(r'<think>.*?</think>', '', content, flags=re.I | re.S).strip())
    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        # Try JSON objects from the end first so quoted/input JSON in reasoning text is ignored.
        for idx in [i for i, ch in enumerate(candidate) if ch == '{'][::-1]:
            try:
                parsed, _ = decoder.raw_decode(candidate[idx:])
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue
    return {}


def concierge_provider_name():
    configured = (os.environ.get('CONCIERGE_PROVIDER') or '').strip().lower()
    if configured:
        return configured
    # FMNO public concierge should default to MiniMax. OpenRouter remains a fallback
    # only when MiniMax-style keys are absent and an OpenRouter key is explicitly live.
    if os.environ.get('MINIMAX_API_KEY') or os.environ.get('CONCIERGE_API_KEY') or os.environ.get('LLM_API_KEY'):
        return 'minimax'
    if os.environ.get('OPENROUTER_API_KEY'):
        return 'openrouter'
    return 'minimax'


def concierge_model_name():
    provider = concierge_provider_name()
    if os.environ.get('CONCIERGE_MODEL'):
        return os.environ.get('CONCIERGE_MODEL', '').strip()
    if provider == 'openrouter':
        return 'google/gemini-2.5-flash'
    return 'MiniMax-M2.7-highspeed'


def concierge_voice_config():
    """Return ElevenLabs/Bill voice config when a premium voice key is configured.

    FMNO should not use cheap browser TTS. If the premium provider is unavailable,
    the avatar stays silent rather than saying the wrong thing.
    """
    api_key = (os.environ.get('ELEVENLABS_API_KEY') or os.environ.get('XI_API_KEY') or '').strip()
    if api_key:
        return {
            'mode': 'elevenlabs',
            'api_key': api_key,
            'voice_id': (os.environ.get('ELEVENLABS_VOICE_ID') or 'pqHfZKP75CvOlQylNhV4').strip(),
            'model_id': (os.environ.get('ELEVENLABS_MODEL_ID') or 'eleven_turbo_v2_5').strip(),
        }
    # Temporary owned bridge: FPS Netlify voice function already has Bill configured.
    # This keeps FMNO live without exposing keys while Render env is being finished.
    bridge_url = (os.environ.get('FMNO_VOICE_BRIDGE_URL') or 'https://sales.firstpagestrategy.org/.netlify/functions/ava-voice').strip()
    if bridge_url:
        return {'mode': 'bridge', 'bridge_url': bridge_url}
    return None


def concierge_voice_configured():
    return concierge_voice_config() is not None


def synthesize_concierge_voice(text):
    """Synthesize exactly the current concierge reply. Return None on failure."""
    cfg = concierge_voice_config()
    if not cfg:
        return None
    text = clean_concierge_text(text or '').strip()[:600]
    if not text:
        return None
    try:
        if cfg.get('mode') == 'bridge':
            r = requests.post(
                cfg['bridge_url'],
                headers={'Content-Type': 'application/json', 'Accept': 'audio/mpeg'},
                json={'text': text},
                timeout=24,
            )
        else:
            r = requests.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{cfg['voice_id']}",
                headers={'xi-api-key': cfg['api_key'], 'Content-Type': 'application/json', 'Accept': 'audio/mpeg'},
                json={
                    'text': text,
                    'model_id': cfg['model_id'],
                    'voice_settings': {'stability': 0.5, 'similarity_boost': 0.75, 'style': 0.2},
                },
                timeout=20,
            )
        if r.status_code != 200 or not r.content:
            app.logger.warning('Concierge voice failed %s: %s', r.status_code, r.text[:300])
            return None
        return r.content, 'audio/mpeg'
    except Exception as exc:
        app.logger.warning('Concierge voice exception: %s', exc)
        return None


def call_concierge_model(topic, collected, user_message, next_question, ready):
    provider = concierge_provider_name()
    if provider == 'openrouter':
        api_key = (os.environ.get('OPENROUTER_API_KEY') or os.environ.get('CONCIERGE_API_KEY') or os.environ.get('LLM_API_KEY') or '').strip()
        default_base = 'https://openrouter.ai/api/v1/chat/completions'
    else:
        api_key = (os.environ.get('CONCIERGE_API_KEY') or os.environ.get('MINIMAX_API_KEY') or os.environ.get('LLM_API_KEY') or '').strip()
        # MiniMax global endpoint is OpenAI-compatible at /v1/chat/completions.
        default_base = 'https://api.minimax.io/v1/chat/completions'
    if not api_key:
        return None
    url = (os.environ.get('CONCIERGE_BASE_URL') or default_base).strip()
    model = concierge_model_name()
    payload = {
        'model': model,
        'messages': build_concierge_messages(topic, collected, user_message, next_question, ready),
        'temperature': 0.25,
        'max_tokens': 1000,
        'response_format': {'type': 'json_object'},
    }
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    if provider == 'openrouter':
        headers.update({'HTTP-Referer': DOMAIN, 'X-Title': 'FixMyNameOnline Concierge'})
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=18)
        if not r.ok:
            app.logger.warning('Concierge model failed %s: %s', r.status_code, r.text[:500])
            return None
        data = r.json()
        content = (((data.get('choices') or [{}])[0].get('message') or {}).get('content')
                   or (data.get('choices') or [{}])[0].get('text')
                   or data.get('reply') or '')
        return parse_model_json(content)
    except Exception as exc:
        app.logger.warning('Concierge model exception: %s', exc)
        return None


def make_concierge_response(topic, collected, user_message='', current_field=''):
    collected = {k: str(v or '').strip()[:1200] for k, v in (collected or {}).items()}
    topic = (topic or collected.get('issue_type') or '').strip()
    if topic:
        collected['issue_type'] = topic
        collected['issue_label'] = CONCIERGE_TOPIC_LABELS.get(topic, topic)
    if current_field and user_message:
        collected[current_field] = str(user_message or '').strip()[:1200]
    next_key, next_question = concierge_next_field(collected)
    ready = next_key is None
    model_data = call_concierge_model(topic, collected, user_message, next_question, ready) or {}
    reply = clean_concierge_text(model_data.get('reply') or fallback_concierge_reply(topic, collected, next_question, ready))
    # Keep the displayed question aligned with the deterministic field being captured.
    # The model supplies tone/advisor reply; the backend owns intake sequence correctness.
    question = clean_concierge_text(next_question or model_data.get('next_question') or '')
    risk_level = str(model_data.get('risk_level') or ('high' if topic == 'privacy' else 'medium')).lower()
    if risk_level not in ['low', 'medium', 'high']:
        risk_level = 'medium'
    preview_data = {
        'case_type': collected.get('issue_label') or CONCIERGE_TOPIC_LABELS.get(topic, topic),
        'names_to_check': collected.get('names_to_check', ''),
        'problem_links': ' '.join([collected.get('country_state', ''), collected.get('problem_links', '')]).strip(),
        'goal': collected.get('goal', ''),
        'country_state': collected.get('country_state', ''),
    }
    preview_triage = triage_snapshot(preview_data) if (collected.get('names_to_check') or topic) else {}
    return {
        'ok': True,
        'reply': reply,
        'next_question': question,
        'current_field': next_key,
        'collected': collected,
        'ready_to_submit': ready,
        'risk_level': risk_level,
        'recommended_pathway': clean_concierge_text(model_data.get('recommended_pathway') or 'Free Search Snapshot™'),
        'risk_score_preview': reputation_risk_score(preview_data, preview_triage),
        'cta': 'Submit Free Search Snapshot™' if ready else None,
        'model_used': bool(model_data),
    }

def triage_snapshot(data):
    text = ' '.join([data.get('case_type', ''), data.get('names_to_check', ''), data.get('problem_links', ''), data.get('goal', '')]).lower()
    case_type = data.get('case_type', '').lower()

    high_risk_words = ['urgent', 'criminal', 'police', 'media', 'journalist', 'press', 'lawsuit', 'defamation', 'dox', 'stalking', 'threat', 'high-risk', 'high risk', 'private case', 'sensitive']
    review_words = ['review', 'reviews', 'google review', '1 star', 'one star', 'fake review', 'malicious review']
    removal_words = ['remove', 'removed', 'de-index', 'deindex', 'delete', 'article', 'old news', 'news article', 'image', 'snippet', 'bad link', 'bad links', 'outdated']
    alert_words = ['alert', 'monitor', 'tracking', 'mentions', 'watch']

    if 'high-risk' in case_type or any(w in text for w in high_risk_words):
        key = 'high-risk'
    elif 'review' in case_type or any(w in text for w in review_words):
        key = 'review-defence'
    elif 'news article' in case_type or any(w in text for w in removal_words):
        key = 'removal-review'
    elif any(w in text for w in alert_words):
        key = 'alerts'
    else:
        key = 'repair-plan'

    result = dict(TRIAGE_NEXT_STEPS[key])
    result['key'] = key
    return result


def make_queue_item(kind, data, triage=None):
    triage = triage or {'key': 'onboarding', 'label': 'Private onboarding', 'priority': 'high'}
    created_at = utc_now()
    return {
        'id': f"FMNO-{created_at.replace('-', '').replace(':', '').replace('.', '').replace('Z', '')}",
        'kind': kind,
        'status': 'new',
        'priority': triage.get('priority', 'standard'),
        'triage_key': triage.get('key'),
        'recommendation': triage.get('label'),
        'created_at': created_at,
        'customer': {
            'name': data.get('name', ''),
            'email': data.get('email', ''),
            'phone': data.get('phone', ''),
            'business': data.get('business', ''),
        },
        'source': data,
        'next_actions': [
            'Review submitted names, links, reviews, and search terms.',
            'Capture screenshots/URLs for the private case file.',
            'Confirm whether the best next step is monitoring, review defence, removal review, repair, or concierge.',
            'Reply privately with the safest recommended path.',
        ],
    }


def reputation_risk_score(data, triage=None, report=None):
    """Public-safe FMNO Reputation Risk Score™ heuristic for intake/case-room V2.

    This is not a guarantee or search-engine diagnosis; it turns the visitor's intake
    into a clearer private first-step signal and stronger paid-pathway handoff.
    """
    data = data or {}
    triage = triage or {}
    report = report or {}
    text = ' '.join(str(data.get(k, '')) for k in ['case_type', 'names_to_check', 'problem_links', 'goal']).lower()
    score = 34
    factors = []

    def bump(points, label):
        nonlocal score
        score += points
        if label not in factors:
            factors.append(label)

    if any(w in text for w in ['address', 'phone', 'mobile', 'personal information', 'private information', 'directory', 'people search']):
        bump(18, 'Private information appears to be exposed')
    if any(w in text for w in ['review', '1 star', 'one star', 'fake review', 'malicious review', 'google business']):
        bump(16, 'Trust/review issue may affect decisions quickly')
    if any(w in text for w in ['article', 'old news', 'news article', 'court', 'snippet', 'image', 'outdated']):
        bump(15, 'Old or outdated result may need pathway review')
    if any(w in text for w in ['urgent', 'criminal', 'police', 'media', 'journalist', 'lawsuit', 'defamation', 'threat', 'stalking', 'sensitive']):
        bump(20, 'Sensitive context should be handled privately')
    if any(w in text for w in ['business', 'clinic', 'studio', 'company', 'clients', 'customers']):
        bump(8, 'Business trust may be affected')
    if data.get('country_state') or any(w in text for w in ['australia', 'nsw', 'vic', 'qld', 'usa', 'uk', 'canada']):
        bump(4, 'Location context supplied for a cleaner private search')
    if data.get('problem_links') and 'search first' not in str(data.get('problem_links')).lower():
        bump(6, 'Specific link/search clue supplied')
    if report.get('negative_item_count'):
        bump(min(18, int(report.get('negative_item_count') or 0) * 4), 'Snapshot found negative/risk items')
    if triage.get('key') == 'high-risk':
        bump(10, 'Recommended for private high-risk review')
    elif triage.get('key') in ['removal-review', 'review-defence']:
        bump(7, 'Likely needs a targeted review pathway')

    if not factors:
        factors.append('Initial private search context received')
    score = max(18, min(92, score))
    if score >= 80:
        band = 'high'
        label = 'High attention'
    elif score >= 60:
        band = 'elevated'
        label = 'Elevated'
    elif score >= 40:
        band = 'moderate'
        label = 'Moderate'
    else:
        band = 'early'
        label = 'Early signal'
    return {
        'score': score,
        'band': band,
        'label': label,
        'factors': factors[:5],
        'recommendation': (report or {}).get('recommended_package') or triage.get('label') or 'Free Search Snapshot™',
        'summary': 'This score is an intake signal only. It helps prioritise the private snapshot and next-step recommendation; it is not a guarantee of ranking, removal, or platform outcome.',
    }


def case_room_token(queue_id, email):
    raw = f"case-room:{queue_id}:{(email or '').strip().lower()}".encode('utf-8')
    return hmac.new(approval_secret().encode('utf-8'), raw, hashlib.sha256).hexdigest()


def case_room_url(queue_id, email):
    return f"{DOMAIN}/private-case-room/{safe(queue_id)}?access_token={case_room_token(queue_id, email)}"


def save_case_room(queue_item, data, triage, case=None, report=None, transcript=None):
    score = reputation_risk_score(data, triage, report)
    record = {
        'queue_id': queue_item.get('id'),
        'case_id': case.get('id') if case else '',
        'email': data.get('email', ''),
        'name': data.get('name') or data.get('contact_name') or '',
        'case_type': data.get('case_type', ''),
        'triage': triage,
        'risk_score': score,
        'status': 'snapshot_received',
        'report_ready': bool(report),
        'report_summary': {
            'recommended_package': (report or {}).get('recommended_package'),
            'negative_item_count': (report or {}).get('negative_item_count'),
        },
        'intake_preview': {
            'names_to_check': data.get('names_to_check', ''),
            'problem_links': data.get('problem_links', ''),
            'goal': data.get('goal', ''),
        },
        'transcript': (transcript or [])[-12:],
        'access_token': case_room_token(queue_item.get('id'), data.get('email', '')),
        'case_room_url': case_room_url(queue_item.get('id'), data.get('email', '')),
    }
    append_jsonl(CASE_ROOMS_FILE, record)
    return record


def find_case_room(queue_id):
    matches = [row for row in read_jsonl(CASE_ROOMS_FILE) if row.get('queue_id') == queue_id]
    return matches[-1] if matches else None


def free_snapshot_used(email):
    """Hard cap: one free snapshot per normalised email address."""
    email_l = (email or '').strip().lower()
    return bool(email_l and any((row.get('email') or '').strip().lower() == email_l for row in read_jsonl(LEADS_FILE)))


def send_snapshot_emails(data, triage, queue_item, case=None, report=None, case_room=None):
    room_link = (case_room or {}).get('case_room_url') or ''
    room_cta = f'<p><a href="{safe(room_link)}" style="background:#111827;color:#fff;padding:12px 18px;text-decoration:none;border-radius:10px;display:inline-block">Open Private Case Room™</a></p>' if room_link else ''
    customer_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#111\">
      <h1>Your Free Search Snapshot™ request is in</h1>
      <p>Hi {safe(data.get('name'))},</p>
      <p>We received your private FixMyNameOnline™ snapshot request.</p>
      <h2>Suggested next step: {safe(triage['label'])}</h2>
      <p>{safe(triage['summary'])}</p>
      <p>We’ll privately review what you submitted and come back with the safest next step. No removal, ranking, or platform result is guaranteed.</p>
      {room_cta}
      <p><a href=\"{DOMAIN}{triage['url']}\" style=\"background:#d91f3d;color:#fff;padding:12px 18px;text-decoration:none;border-radius:10px;display:inline-block\">{safe(triage['cta'])}</a></p>
      <p style=\"font-size:12px;color:#666\">Reference: {safe(queue_item['id'])}<br>FixMyNameOnline™ · MadisonJade Pty Ltd</p>
    </div>
    """
    internal_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111\">
      <h1>New FMNO Free Snapshot report ready</h1>
      <p><strong>Queue ID:</strong> {safe(queue_item['id'])}</p>
      <p><strong>Case ID:</strong> {safe(case.get('id') if case else '')}</p>
      <p><strong>Priority:</strong> {safe(queue_item['priority'])}</p>
      <p><strong>Recommendation:</strong> {safe((report or {}).get('recommended_package') or triage['label'])}</p>
      <p><strong>Negative items:</strong> {safe((report or {}).get('negative_item_count'))}</p>
      <p><strong>Admin report:</strong> {safe(DOMAIN + '/admin/fulfilment/report/' + case.get('id') if case else '')}</p>
      <pre style=\"background:#f5f5f5;padding:16px;border-radius:10px;white-space:pre-wrap\">{safe(json.dumps({'intake': data, 'report': report}, indent=2, ensure_ascii=False))}</pre>
    </div>
    """
    return {
        'customer_email_sent': send_brevo_email(data.get('email'), data.get('name'), 'Your Free Search Snapshot™ request is in', customer_html),
        'internal_email_sent': send_internal_alert_email(f"FMNO lead: {triage['label']} — {data.get('name', '')}", internal_html),
    }


def send_onboarding_emails(data, queue_item):
    plan_label = PLANS.get(data.get('plan'), {}).get('name', data.get('plan', 'Private onboarding'))
    customer_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#111;line-height:1.55\">
      <h1>We’ve received your private onboarding</h1>
      <p>Hi {safe(data.get('name'))},</p>
      <p>Thank you — we’ve received your details for <strong>{safe(plan_label)}</strong>.</p>
      <p>In plain English: we are going to look at what people may see when they search your name or business, work out what can safely be improved, and prepare positive, accurate material for your approval before anything public is used.</p>

      <h2>What happens next</h2>
      <ol>
        <li><strong>Private review:</strong> we check the names, links, reviews, search terms and context you sent us.</li>
        <li><strong>Search map:</strong> we map the main searches and the gaps where stronger positive assets may help.</li>
        <li><strong>Asset plan:</strong> we prepare a simple plan for the positive pages, profiles, bios or content assets that make sense for your situation.</li>
        <li><strong>Drafts:</strong> we draft the first approved materials using only accurate information you have provided or approved.</li>
        <li><strong>Quality check:</strong> we check the wording for accuracy, privacy, tone and safety.</li>
        <li><strong>Your approval:</strong> you review the material before anything is published, submitted or used publicly.</li>
        <li><strong>Delivery report:</strong> we send you a private update showing what was prepared, approved, published/queued, and what happens next.</li>
      </ol>

      <h2>What we may ask you for</h2>
      <ul>
        <li>Your preferred name, business name and any old/associated names to monitor.</li>
        <li>Links, screenshots or search terms that worry you.</li>
        <li>Accurate bio facts: role, business, location, services, qualifications, achievements, photos or logo.</li>
        <li>Anything sensitive, private, disputed, outdated or not to be mentioned publicly.</li>
      </ul>

      <h2>Important</h2>
      <p>We do not guarantee Google rankings, removals, review removals, de-indexing or platform decisions. Search engines, publishers and platforms make their own decisions. Our job is to build a safer, stronger, truthful search presence and prepare any possible removal/review pathway carefully.</p>
      <p>If you have a question, reply to this email and include your private reference below, or use the private question form: <a href="{DOMAIN}/questions">{DOMAIN}/questions</a>.</p>
      <p style=\"font-size:12px;color:#666\">Private reference: {safe(queue_item['id'])}<br>FixMyNameOnline™ · MadisonJade Pty Ltd</p>
    </div>
    """
    internal_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111\">
      <h1>New FMNO private onboarding</h1>
      <p><strong>Queue ID:</strong> {safe(queue_item['id'])}</p>
      <p><strong>Plan:</strong> {safe(plan_label)}</p>
      <pre style=\"background:#f5f5f5;padding:16px;border-radius:10px;white-space:pre-wrap\">{safe(json.dumps(data, indent=2, ensure_ascii=False))}</pre>
    </div>
    """
    return {
        'customer_email_sent': send_brevo_email(data.get('email'), data.get('name'), 'Private onboarding received — FixMyNameOnline™', customer_html),
        'internal_email_sent': send_internal_alert_email(f"FMNO onboarding: {plan_label} — {data.get('name', '')}", internal_html),
    }


@app.route('/')
def landing():
    html_text = Path('landing_page_v2.html').read_text(encoding='utf-8')
    tracking = tracking_head()
    if tracking and '</head>' in html_text:
        html_text = html_text.replace('</head>', tracking + '</head>', 1)
    return Response(html_text, mimetype='text/html')


@app.route('/robots.txt')
def robots_txt():
    return Response(f"User-agent: *\nDisallow:\nAllow: /\nSitemap: {DOMAIN}/sitemap.xml\n", mimetype='text/plain')


INDEXNOW_KEY = '92e0a789584811cf9904921b7c0c56fa'


@app.route(f'/{INDEXNOW_KEY}.txt')
def indexnow_key_file():
    return Response(INDEXNOW_KEY, mimetype='text/plain')


@app.route('/personal-search')
def personal_search_redirect():
    return redirect('/personal-search/', code=301)


@app.route('/personal-search/')
def personal_search_hub():
    return send_from_directory('personal-search', 'index.html')


@app.route('/sitemap.xml')
def sitemap_xml():
    base_urls = ['/', '/fix-my-name-online', '/learn', '/false-information-claims-online', '/bad-google-results-help', '/when-google-makes-your-past-look-like-your-present', '/google-your-name', '/free-search-snapshot', '/app', '/questions', '/contact', '/about', '/services', '/online-reputation-repair', '/worldwide-reputation-repair', '/reputation-repair-australia', '/private-reputation-repair', '/google-review-defence', '/google-review-defence-worldwide', '/google-review-defence-australia', '/remove-bad-google-results', '/remove-negative-google-results', '/name-watch-alerts', '/delete-me', '/google-alerts-for-my-name', '/diy-action', '/privacy', '/terms']
    personal_search_urls = ['/personal-search/']
    personal_search_dir = Path('personal-search')
    if personal_search_dir.exists():
        personal_search_urls += [f'/personal-search/{p.name}' for p in sorted(personal_search_dir.glob('*.html')) if p.name != 'index.html']
    guide_urls = ['/' + slug for slug in SEO_GUIDES.keys()]
    urls = []
    for u in base_urls + guide_urls + personal_search_urls:
        if u not in urls:
            urls.append(u)
    today = datetime.utcnow().strftime('%Y-%m-%d')
    urlset = ''.join(
        f"<url><loc>{DOMAIN}{u}</loc><lastmod>{today}</lastmod><changefreq>{'weekly' if u in ['/', '/fix-my-name-online', '/bad-results-on-google-what-to-do', '/what-to-do-if-google-results-are-bad'] else 'monthly'}</changefreq><priority>{'1.0' if u == '/' else ('0.9' if u in ['/fix-my-name-online', '/bad-results-on-google-what-to-do'] else '0.7')}</priority></url>"
        for u in urls
    )
    xml = f"<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>{urlset}</urlset>"
    return Response(xml, mimetype='application/xml')


@app.route('/about')
def about():
    body = """<div class=\"card\"><h1>About FixMyNameOnline™</h1><p class=\"sub\">FixMyNameOnline™ is an Australia-based, worldwide private reputation repair and search protection service operated by MadisonJade Pty Ltd.</p><p>We help individuals, professionals, business owners and public figures understand what appears around their name, document risk signals, review removal or platform-reporting pathways where appropriate, and build accurate positive assets over time.</p><div class=\"recommend\"><h2>Company and operator details</h2><p><strong>Operator:</strong> MadisonJade Pty Ltd<br><strong>ABN:</strong> 56661580936<br><strong>Base:</strong> South Australia, Australia<br><strong>Service area:</strong> Worldwide private search and reputation support</p><p>FixMyNameOnline™ is built as a private first-step service: search snapshot, review, action plan, monitoring and careful escalation where legitimate pathways exist.</p></div><h2>Public profiles</h2><ul><li><a href=\"https://x.com/Fixmyname_com\">FixMyNameOnline™ on X</a></li><li><a href=\"https://www.instagram.com/fixmynameonlinecom/\">FixMyNameOnline™ on Instagram</a></li><li><a href=\"https://www.tiktok.com/@fix.my.name.onlin\">FixMyNameOnline™ on TikTok</a></li></ul><p><a class=\"btn\" href=\"/app?source=about_company\">Start Free Search Snapshot™</a></p><p class=\"note\">We are not a law firm and do not provide legal advice. No ranking, removal, review-removal, de-indexing or platform outcome is guaranteed.</p></div>"""
    return page('About FixMyNameOnline™ — MadisonJade Pty Ltd', body, 'About FixMyNameOnline™, a worldwide private reputation repair and search protection service operated by MadisonJade Pty Ltd in Australia.', canonical_path='/about')


@app.route('/fix-my-name-on-line')
def fix_my_name_on_line_variant_redirect():
    return redirect('/fix-my-name-online', code=301)


@app.route('/fix-my-name-online')
def fix_my_name_online_exact_match():
    body = """
    <div class=\"card\">
      <span class=\"pill\">Fix My Name Online™</span>
      <h1>Fix My Name Online™ private search protection</h1>
      <p class=\"sub\">Fix My Name Online™ / FixMyNameOnline™ helps people and businesses understand what Google shows around their name, business, reviews, old links and associated search terms.</p>
      <p>This exact-name page exists so search engines can clearly connect the spaced brand name, the domain name and the service. If someone searches “fix my name online”, this page explains who we are, what we do and how to start privately.</p>
      <p>People sometimes type the brand as “Fix My Name On Line” with “online” split into two words. That search means the same official brand: Fix My Name Online™ at fixmynameonline.com.</p>
      <h2>What Fix My Name Online checks</h2>
      <ul>
        <li>Google results around your name, business name, previous names and associated names</li>
        <li>Old articles, outdated snippets, image results, review profiles and complaint pages</li>
        <li>Possible removal, correction, privacy, outdated-content or platform-reporting pathways</li>
        <li>Positive profile, business and authority assets that can strengthen the full current story</li>
      </ul>
      <p><a class=\"btn\" href=\"/app\">Start the Free Search Snapshot™ →</a> <a class=\"btn btn2\" href=\"/services\">View services</a></p>
      <p class=\"note\">Australia-based, worldwide service by MadisonJade Pty Ltd. No ranking, removal, de-indexing or platform outcome is guaranteed.</p>
    </div>
    """
    return page(
        'Fix My Name Online™ | Fix My Name On Line Brand Variant',
        body,
        'Fix My Name Online™ / FixMyNameOnline™ private search protection. Also searched as Fix My Name On Line. Reputation repair for bad Google results, old links, reviews and associated-name search problems.',
        canonical_path='/fix-my-name-online'
    )


@app.route('/services')
def services():
    body = """<div class=\"card\"><h1>Private Reputation Repair Services</h1><p class=\"sub\">Structured help for name search problems, old results, malicious reviews, associated-name issues and reputation-sensitive cases.</p><ul><li>Free Search Snapshot™ for initial risk mapping</li><li>NameWatch Alert™ for $29/month Google-name monitoring and new-result alerts</li><li>Removal Review™ for link, article, image or snippet pathway assessment</li><li>Review Defence™ for Google review audit, reporting notes and response drafts</li><li>Starter™, Pro™ and Premium™ repair plans for approved positive assets and ongoing search protection</li></ul><p class=\"note\">Search engines and third-party platforms make their own decisions. Results vary by situation.</p></div>"""
    return page('Services — FixMyNameOnline™', body, 'Private reputation repair, search protection, removal review support, Google review defence and positive asset planning by FixMyNameOnline™.')




def acquisition_page(title, eyebrow, headline, subhead, bullets, faq_items, canonical_path, description):
    bullet_html = ''.join(f"<li>✓ {safe(b)}</li>" for b in bullets)
    faq_html = ''.join(f"<div class='card'><h2>{safe(q)}</h2><p>{safe(a)}</p></div>" for q, a in faq_items)
    body = f"""
    <div class="card">
      <span class="pill">{safe(eyebrow)}</span>
      <h1>{safe(headline)}</h1>
      <p class="sub">{safe(subhead)}</p>
      <p><a class="btn" href="/app">Start Free Search Snapshot™ →</a> <a class="btn btn2" href="/services">See services</a></p>
      <h2>What we check</h2>
      <ul>{bullet_html}</ul>
      <div class="recommend"><h2>Start private. No pressure.</h2><p>Send your name, business name, review links, article links or search terms. We review the pattern and point you toward alerts, removal review, review defence or a repair plan only if there is a real next step.</p><p><a class="btn" href="/app">Get the Free Snapshot™</a></p></div>
      <p class="note">FixMyNameOnline™ is not a law firm and does not provide legal advice. Search engines, publishers, review platforms and third parties make their own decisions. No ranking, removal, review-removal, de-indexing or platform outcome is guaranteed.</p>
    </div>
    <div class="grid">{faq_html}</div>
    """
    return page(title, body, description=description, canonical_path=canonical_path)


@app.route('/online-reputation-repair')
def online_reputation_repair_page():
    return acquisition_page(
        'Online Reputation Repair — FixMyNameOnline™',
        'Online reputation repair',
        'Online reputation repair for people and businesses being judged by search.',
        'Private search protection for bad Google results, old articles, damaging snippets, associated names, review problems and weak positive search footprints.',
        [
            'Name, business, old-name and associated-name search mapping',
            'Bad result, article, review, image and complaint-page triage',
            'Removal, privacy, outdated-content or platform-reporting pathway review where realistic',
            'Truthful positive asset strategy for a stronger current search footprint',
            'Monitoring plan for ranking movement, snippet changes and new risk signals',
        ],
        [
            ('What is online reputation repair?', 'It is the structured process of reviewing what search engines show, checking realistic removal or reporting options, and building accurate approved assets that help people see the fuller current story.'),
            ('Can you fix my search results quickly?', 'Evidence capture and planning can start quickly. Search visibility usually takes weeks or months, and no search engine result is guaranteed.'),
            ('Is this only for Australia?', 'FixMyNameOnline™ is operated by MadisonJade Pty Ltd in Australia and supports clients worldwide.'),
        ],
        '/online-reputation-repair',
        'Online reputation repair for bad Google results, old articles, damaging snippets, reviews and associated-name search problems. Private Australia-based worldwide service.'
    )


@app.route('/worldwide-reputation-repair')
def worldwide_reputation_repair_page():
    return acquisition_page(
        'Worldwide Reputation Repair — FixMyNameOnline™',
        'Worldwide reputation repair',
        'Worldwide reputation repair for search problems that cross borders.',
        'FixMyNameOnline™ supports clients worldwide with private search protection for names, businesses, old articles, review attacks, damaging snippets and associated-name search problems.',
        [
            'Worldwide private intake for individuals, professionals, founders and businesses',
            'Name, old-name, business, location and associated-entity search mapping',
            'Google results, review profiles, old articles, copied pages and image-result triage',
            'Removal, privacy, outdated-content, publisher or platform pathway review where realistic',
            'Truthful positive assets and monitoring built for international search visibility',
        ],
        [
            ('Do you work outside Australia?', 'Yes. FixMyNameOnline™ is a worldwide service. MadisonJade Pty Ltd operates from Australia, but search reputation problems are global.'),
            ('Can you handle overseas Google results?', 'We can map and review international search results, but each platform, publisher and jurisdiction has its own rules and no outcome is guaranteed.'),
            ('What is the first step?', 'Start with the Free Search Snapshot™ and include the country, language, name variants, business names, URLs or screenshots if you have them.'),
        ],
        '/worldwide-reputation-repair',
        'Worldwide reputation repair and private search protection for bad Google results, old articles, review attacks and associated-name search problems.'
    )


@app.route('/reputation-repair-australia')
def reputation_repair_australia_page():
    return acquisition_page(
        'Reputation Repair Australia — FixMyNameOnline™',
        'Reputation repair Australia',
        'Australia-based reputation repair for serious search problems.',
        'FixMyNameOnline™ is operated by MadisonJade Pty Ltd in Australia and helps individuals, professionals, founders and businesses handle Google result, review and search-footprint problems worldwide.',
        [
            'Australian operator and worldwide private intake',
            'Personal name, business name, suburb/location and associated-name searches',
            'Old articles, court mentions, outdated snippets, reviews and complaint pages',
            'Evidence packs for possible correction, privacy, outdated-content or review pathways',
            'Approved positive profiles, service pages, articles and trust assets',
        ],
        [
            ('Do you only work with Australian clients?', 'No. The operator is Australian, but search damage can affect clients, employers, customers and platforms worldwide.'),
            ('Is reputation repair legal in Australia?', 'Responsible work uses truthful approved content, evidence, monitoring and platform-appropriate requests. Legal advice should come from a qualified lawyer where needed.'),
            ('What is the first step?', 'Start with the Free Search Snapshot™ so the actual search pattern can be mapped before any public action.'),
        ],
        '/reputation-repair-australia',
        'Reputation repair Australia: private search protection, review defence, removal pathway review and positive footprint support by FixMyNameOnline™.'
    )


@app.route('/remove-negative-google-results')
def remove_negative_google_results_page():
    return acquisition_page(
        'Remove Negative Google Results? Private Options Review — FixMyNameOnline™',
        'Remove negative Google results',
        'Negative Google results need evidence before action.',
        'Private review for old articles, harmful snippets, search result pages, review profiles, copied pages, images and associated-name results that are hurting trust.',
        [
            'Exact search phrase, ranking position, title, snippet and URL capture',
            'Source-page review: publisher, review platform, directory, forum, court page or copy site',
            'Possible outdated-content, privacy, correction, review-policy or publisher pathway',
            'Positive search-footprint plan if removal is not realistic',
            'Private report with next-step recommendation and no public case disclosure',
        ],
        [
            ('Can negative Google results be removed?', 'Sometimes there may be a valid pathway, but many results cannot be removed quickly or at all. The first step is evidence and realistic review.'),
            ('What should I avoid?', 'Avoid threats, spam, fake profiles, public arguments or anyone claiming guaranteed Google control.'),
            ('Can FMNO help if removal is not possible?', 'Yes. The strategy may shift to truthful positive assets, profile repair and monitoring so searchers see more than the negative result.'),
        ],
        '/remove-negative-google-results',
        'Private options review for negative Google results, bad snippets, old articles, review damage and search reputation problems. No removal outcome guaranteed.'
    )


@app.route('/google-review-defence-worldwide')
def google_review_defence_worldwide_page():
    return acquisition_page(
        'Google Review Defence Worldwide — FixMyNameOnline™',
        'Google review defence worldwide',
        'Google review defence for businesses wherever customers search first.',
        'Private support for businesses worldwide dealing with fake, unfair, malicious, competitor, ex-staff or review-bombing issues on Google Business Profiles and review-led search results.',
        [
            'Worldwide review-risk triage for local and online businesses',
            'Review pattern, timeline, relationship and evidence audit',
            'Possible Google policy issue mapping and reporting notes',
            'Calm public owner response drafts for future customers',
            'Trust-recovery plan across website, profiles, search assets and monitoring',
        ],
        [
            ('Can FMNO help with reviews outside Australia?', 'Yes. The service is worldwide. Google policies are global, but local facts, languages and business context still matter.'),
            ('Can you guarantee Google will remove a review?', 'No. Google makes the final decision. We help document, report where appropriate, respond professionally and rebuild trust signals.'),
            ('What should I send first?', 'Send the business name, country/location, Google Business Profile link, review screenshots and any evidence showing why the review may be fake or unfair.'),
        ],
        '/google-review-defence-worldwide',
        'Worldwide Google review defence for fake, unfair or malicious reviews. Evidence audit, reporting notes, response drafts and trust recovery.'
    )


@app.route('/google-review-defence-australia')
def google_review_defence_australia_page():
    return acquisition_page(
        'Google Review Defence Australia — FixMyNameOnline™',
        'Google review defence Australia',
        'Google review defence for Australian businesses under unfair review pressure.',
        'Private support for businesses dealing with fake, unfair, malicious, competitor, ex-staff or review-bombing issues on Google Business Profiles.',
        [
            'Review pattern, timeline and business relationship audit',
            'Possible Google policy issue mapping',
            'Evidence notes for reporting or escalation where appropriate',
            'Calm public owner response drafts for future customers',
            'Trust-recovery plan across website, profiles, reviews and search assets',
        ],
        [
            ('Can you delete fake Google reviews?', 'No business or agency can directly delete third-party Google reviews. Google decides. We help document, report where appropriate, respond and rebuild trust signals.'),
            ('Is this for local Australian businesses?', 'Yes. It suits local services, clinics, trades, agencies, restaurants, professionals and brands affected by Google review trust damage.'),
            ('What should I send first?', 'Send the business name, Google Business Profile link, review screenshots and any notes showing why the review may be fake or unfair.'),
        ],
        '/google-review-defence-australia',
        'Google Review Defence Australia for fake, unfair or malicious Google reviews. Evidence audit, reporting notes, response drafts and trust recovery.'
    )


@app.route('/google-review-defence')
def google_review_defence_page():
    return acquisition_page(
        'Google Review Defence™ — FixMyNameOnline™',
        'Google review defence',
        'Fake or malicious Google reviews can cost real customers.',
        'Private support for businesses dealing with fake, unfair, competitor, ex-employee, ex-partner or review-bombing attacks on Google.',
        [
            'Review pattern and risk audit',
            'Possible Google policy issues',
            'Evidence notes for reporting',
            'Calm owner response drafts',
            'Recovery plan for stronger business trust signals',
        ],
        [
            ('Can you remove bad Google reviews?', 'Google makes the final decision. We help document the issue, identify possible policy pathways and prepare professional reporting notes or responses.'),
            ('Who is this for?', 'Business owners, local services, professionals, clinics, trades, agencies, restaurants and anyone losing trust because of unfair or malicious reviews.'),
            ('What is the first step?', 'Start with the Free Search Snapshot™ and paste the review links or business profile details.'),
        ],
        '/google-review-defence',
        'Google Review Defence™ for businesses hit by fake, unfair or malicious Google reviews. Private audit, evidence notes, reporting support and response drafts.'
    )


@app.route('/remove-bad-google-results')
def remove_bad_google_results_page():
    return acquisition_page(
        'Remove Bad Google Results? Options Explained — FixMyNameOnline™',
        'Bad Google results',
        'Bad Google results should not be the only version people see.',
        'Private review for old articles, outdated snippets, images, complaint pages, associated names, reviews and damaging search terms.',
        [
            'URLs, snippets, images and article details',
            'Whether a correction, outdated-content request, privacy request or platform report may be realistic',
            'What evidence is needed before any request',
            'Positive asset strategy if removal is not realistic',
            'Associated names, old names, locations and risk-term searches',
        ],
        [
            ('Can bad Google results always be removed?', 'No. Some results may have a valid pathway, many do not. We review the facts and recommend the safest realistic next step.'),
            ('What if removal is not realistic?', 'Then the strategy usually shifts to building accurate positive assets and stronger search trust around your name or business.'),
            ('Is this confidential?', 'The service is designed to be discreet. We do not publicly advertise client cases.'),
        ],
        '/remove-bad-google-results',
        'Private review for bad Google results, old articles, damaging snippets, associated names and search reputation problems. Australia-based, worldwide support.'
    )


@app.route('/private-reputation-repair')
def private_reputation_repair_page():
    return acquisition_page(
        'Private Reputation Repair — FixMyNameOnline™',
        'Private reputation repair',
        'When people search your name, they should see the full story.',
        'Discreet reputation repair and search protection for individuals, professionals, business owners, public figures and sensitive cases.',
        [
            'Personal name, old name and associated-name search mapping',
            'Bad result, review, article and complaint-page triage',
            'Removal or reporting pathway review where appropriate',
            'Approved positive biographies, profiles, pages and articles',
            'Monthly monitoring and private progress reporting',
        ],
        [
            ('Who uses private reputation repair?', 'Everyday people, professionals, founders, business owners, creators and public figures who are being judged by search results before they can explain the full context.'),
            ('Do you guarantee rankings?', 'No. We build and improve accurate search assets over time, but search engines make their own ranking decisions.'),
            ('Where are you based?', 'FixMyNameOnline™ is operated by MadisonJade Pty Ltd in Australia and serves clients worldwide.'),
        ],
        '/private-reputation-repair',
        'Private reputation repair and search protection for individuals, professionals and businesses. Australia-based, worldwide service by MadisonJade Pty Ltd.'
    )

SEO_GUIDES = {
    'online-reputation-management-australia': {
        'eyebrow': 'Australian reputation management',
        'title': 'Online Reputation Management Australia — Fix My Name Online™',
        'h1': 'Online reputation management in Australia, built for real search risk',
        'description': 'Australian online reputation management for individuals, businesses and professionals dealing with Google results, reviews, old articles and associated-name search risk.',
        'intro': 'Fix My Name Online™ is operated by MadisonJade Pty Ltd in Australia and supports clients worldwide. This guide explains the careful, search-safe way we approach online reputation management: technical discovery, evidence, removal-pathway review, truthful positive assets and ongoing monitoring.',
        'sections': [
            ('Start with the search result page, not guesses', 'The first professional step is to map what Google actually shows for the full name, business name, old names, common misspellings, locations, review terms and risk words. Ranking work fails when it is built around one vanity keyword instead of the real search pattern people use before they trust someone.'),
            ('Separate removable problems from reputation gaps', 'Some results may have a correction, outdated-content, privacy, platform-policy or publisher-request pathway. Others cannot be removed safely or realistically. A strong campaign separates those paths early so the client does not waste months chasing impossible takedowns.'),
            ('Build approved assets that deserve to rank', 'Modern SEO rewards pages that are useful, specific and trustworthy. For reputation repair, that means accurate biographies, service pages, business proof, profile assets, helpful articles, FAQs and evidence-based updates — not thin AI filler.'),
            ('Use Search Console and monitoring', 'Google Search Console, sitemap submission, URL inspection, analytics and ranking checks are not optional. They tell us whether Google can discover, crawl, index and understand the reputation assets being built.'),
        ],
        'faqs': [
            ('Do Australian reputation cases only affect Australia?', 'No. Australian clients are often searched by overseas clients, employers, investors, journalists and platforms. The operator can be Australian while the search risk is worldwide.'),
            ('Can you guarantee page one?', 'No. Google makes its own decisions. The professional goal is to improve technical clarity, usefulness, authority, internal linking and external discovery signals over time.'),
        ],
    },
    'reputation-repair-for-individuals': {
        'eyebrow': 'Individual reputation repair',
        'title': 'Reputation Repair for Individuals — Fix My Name Online™',
        'h1': 'Reputation repair for individuals when Google shows the wrong first impression',
        'description': 'Private reputation repair for individuals dealing with old Google results, associated names, outdated snippets, reviews, complaint pages or sensitive search terms.',
        'intro': 'People get searched before job interviews, dates, rentals, partnerships, media calls and client decisions. Individual reputation repair is about making the search result page more accurate, current and complete without making unsafe promises.',
        'sections': [
            ('Map the person behind the search', 'A real plan checks legal names, previous names, nicknames, professional names, locations, business links, images, news results, review sites and common risk phrases. One bad result may be less damaging than a pattern of associated searches.'),
            ('Create assets that answer real questions', 'Useful positive assets should explain who the person is now, what they do, what is verified, what they are comfortable publishing and what should stay private. Thin pages do not build trust.'),
            ('Handle sensitive claims carefully', 'Where allegations, court mentions, old articles or disputes exist, the safest public strategy is factual, approved and proportionate. Legal advice may be needed for legal claims; reputation work should not pretend to be a law firm.'),
            ('Measure progress by search coverage', 'The goal is not one page in isolation. The campaign should track which owned or approved assets appear for the name, old name, business name, location and risk-term combinations.'),
        ],
        'faqs': [
            ('Is this public?', 'The intake and planning are private. Published assets are only created from approved, truthful information.'),
            ('How long does individual reputation repair take?', 'Some assets can be published quickly, but organic search visibility usually takes weeks or months depending on competition and existing result authority.'),
        ],
    },
    'old-news-article-on-google': {
        'eyebrow': 'Old article search risk',
        'title': 'Old News Article Showing on Google — Options and Limits | Fix My Name Online™',
        'h1': 'Old news article showing on Google? Start with options, limits and evidence',
        'description': 'What to do when an old news article, court mention or outdated story appears on Google: review pathways, evidence, outdated-content requests and positive search assets.',
        'intro': 'Old articles can keep following people long after the facts, context or life circumstances have changed. The right response depends on the source, accuracy, legal status, public interest, indexing and available evidence.',
        'sections': [
            ('Check whether the article is accurate and current', 'Correction and publisher requests are strongest when there is a clear factual error, missing outcome, outdated snippet, privacy issue or changed circumstance that can be evidenced.'),
            ('Understand what Google controls', 'Google usually indexes pages created by others. It may remove or update some results under specific policies, but it does not rewrite publisher content. That is why publisher, platform and search-engine paths need to be separated.'),
            ('Prepare evidence before asking', 'Screenshots, URLs, dates, cached snippets, legal outcomes, publisher contact details and proof of identity or authority can matter. A vague emotional request is weaker than a calm, documented request.'),
            ('Build the fuller current story', 'If the article cannot be removed, a reputation plan can create accurate current assets that help searchers see more than the old result: bios, business pages, profiles, interviews, FAQs and useful articles.'),
        ],
        'faqs': [
            ('Can an old news article always be removed?', 'No. Some have a valid pathway; many do not. The first step is to assess the facts and available policies.'),
            ('Can Google remove the snippet?', 'Sometimes outdated or policy-eligible snippets can be reviewed, but Google and the publisher make their own decisions.'),
        ],
    },
    'fake-google-reviews-help': {
        'eyebrow': 'Google review defence',
        'title': 'Fake Google Reviews Help — Evidence, Reporting and Response | Fix My Name Online™',
        'h1': 'Fake Google reviews need evidence, calm responses and a repair plan',
        'description': 'Help for fake, malicious or unfair Google reviews: audit the pattern, collect evidence, check policy pathways, draft owner responses and rebuild trust signals.',
        'intro': 'A fake or malicious review can cost calls, bookings and trust. The strongest response is not panic or public fighting; it is a clean evidence file, policy review, professional response and a wider trust-recovery plan.',
        'sections': [
            ('Document the pattern', 'Record review dates, reviewer names, wording, star rating, business relationship, screenshots and any signs of competitor, ex-employee, ex-partner or review-bombing activity.'),
            ('Match the issue to platform policy', 'Google decides whether a review is removed. A professional report should connect the facts to possible policy issues rather than simply saying the review is unfair.'),
            ('Respond for future customers', 'A calm owner response is often read by prospects. It should be short, factual, non-defamatory and focused on customer care, not a public argument.'),
            ('Rebuild surrounding trust', 'More accurate business profiles, service pages, testimonials where allowed, FAQs, proof assets and monitoring reduce the damage of one hostile review result.'),
        ],
        'faqs': [
            ('Can you delete fake Google reviews?', 'No agency can directly delete Google reviews. We help audit, document, report and respond; Google makes the decision.'),
            ('Should I reply publicly?', 'Often yes, but carefully. The reply should reassure future customers, not escalate the dispute.'),
        ],
    },
    'how-to-check-your-online-reputation': {
        'eyebrow': 'Search self-audit',
        'title': 'How to Check Your Online Reputation Before People Search You | Fix My Name Online™',
        'h1': 'How to check your online reputation before clients, employers or dates search you',
        'description': 'A practical online reputation self-audit checklist for names, business names, old names, Google results, reviews, images, snippets and associated search terms.',
        'intro': 'Most reputation problems are discovered too late — after a client goes quiet, an employer hesitates or a partner searches a name. A simple search audit shows what needs monitoring, challenging or strengthening.',
        'sections': [
            ('Search like a stranger', 'Use your full name, quoted name, old names, nicknames, business names, suburb, city, job title, review terms and risk words. Check web results, images, videos, news and review profiles.'),
            ('Record what appears on page one and two', 'Titles, snippets and images can matter as much as the page itself. Screenshot the result, URL, date and search phrase so changes can be tracked.'),
            ('Classify the problem', 'Group results into positive assets, neutral listings, outdated items, bad reviews, complaint pages, old articles, images and associated-name risks. Each group needs a different response.'),
            ('Strengthen the weak spots', 'If there are too few accurate assets, build them. If a result may breach policy, document it. If new issues keep appearing, set up monitoring.'),
        ],
        'faqs': [
            ('Should I search in private browsing?', 'It can help reduce personalization, but location and device still influence results. Track the exact search phrase and date.'),
            ('What should I do first if I find something bad?', 'Save evidence before reacting. Then decide whether it is a removal/review issue, monitoring issue or positive-footprint issue.'),
        ],
    },
    'bad-results-on-google-what-to-do': {
        'eyebrow': 'Bad Google results help',
        'title': 'I Have Bad Results on Google — What Do I Do? | Fix My Name Online™',
        'h1': 'I have bad results on Google. What do I do first?',
        'description': 'What to do if you have bad results on Google: save evidence, check removal pathways, avoid risky reactions and build a stronger search footprint.',
        'intro': 'If you have bad results on Google, do not panic and do not start sending angry messages. The first move is to save evidence, understand what type of result it is, and choose the safest pathway before the result spreads or the wrong response makes it worse.',
        'sections': [
            ('Step 1: save the result before reacting', 'Take screenshots of the Google result, page title, snippet, URL, date, search phrase and any image or review that appears. If the result changes later, this evidence helps show what was visible and when.'),
            ('Step 2: identify what kind of bad result it is', 'A bad Google result can be an old news article, court mention, bad review, complaint page, image, outdated snippet, forum post, copied content or an associated-name result. Each one has a different pathway.'),
            ('Step 3: check whether removal or correction is realistic', 'Some results may have a publisher correction, privacy, outdated-content, review-policy or platform-reporting pathway. Others may not. A careful review prevents wasted time and avoids making unsafe claims.'),
            ('Step 4: build the stronger current story', 'If the bad result cannot be removed quickly, the next move is to build accurate, approved assets around your name or business: profiles, pages, articles, FAQs, proof points and monitoring signals that show the fuller current picture.'),
        ],
        'faqs': [
            ('Can bad results on Google be removed?', 'Sometimes there is a valid pathway; often there is not. Google, publishers and platforms make their own decisions. The first step is to review the facts and available policies.'),
            ('Should I contact the website immediately?', 'Not always. Save evidence first and check the risk. Some messages help, but rushed or emotional contact can make a sensitive result harder to handle.'),
            ('Can Fix My Name Online check this privately?', 'Yes. Start with a Free Search Snapshot™ and include the search phrase, links, screenshots or review details you are worried about.'),
        ],
    },
    'what-to-do-if-google-results-are-bad': {
        'eyebrow': 'Bad search results action plan',
        'title': 'What To Do If Google Results Are Bad | Fix My Name Online™',
        'h1': 'What to do if your Google results are bad',
        'description': 'A practical action plan for bad Google results around your name or business: evidence, risk review, removal options and positive search assets.',
        'intro': 'Bad Google results can affect jobs, clients, finance, relationships and business trust. The safest response is a calm action plan: capture the evidence, classify the result, review possible pathways and strengthen the search page with accurate positive assets.',
        'sections': [
            ('Do not feed the result', 'Avoid public arguments, repeated searches from the same account, social posts about the issue or mass-reporting without evidence. The goal is to reduce risk, not create more signals around the problem.'),
            ('Map the searches people actually use', 'Check your full name, business name, old names, suburb, profession, review terms and risk phrases. Reputation repair works best when it targets the real search combinations people type.'),
            ('Separate platform problems from search problems', 'Google shows results from other sites. A review platform, publisher, court database, social profile or complaint site may need a different response from Google itself.'),
            ('Create a private next-step plan', 'Decide whether this is monitoring, removal review, review defence or broader reputation repair. The correct pathway depends on evidence, source authority, sensitivity and timing.'),
        ],
        'faqs': [
            ('How urgent is a bad Google result?', 'It depends on where it ranks, what the snippet says, whether it appears for your exact name and whether clients, employers or customers are likely to search it.'),
            ('Can positive content help?', 'Accurate positive assets can help searchers see a fuller picture over time, but search engines decide what ranks and when.'),
        ],
    },
    'negative-google-results-help': {
        'eyebrow': 'Negative Google results',
        'title': 'Negative Google Results Help — Private Search Repair | Fix My Name Online™',
        'h1': 'Negative Google results need evidence, strategy and patience',
        'description': 'Private help for negative Google results, old links, reviews, complaint pages, snippets and personal or business search reputation problems.',
        'intro': 'Negative Google results can feel urgent, but the strongest plan starts with evidence and classification. Some problems need removal review, some need review defence, some need updated assets, and some need careful monitoring before action.',
        'sections': [
            ('Work from the search page outward', 'Record the exact search phrase, ranking position, title, snippet and source. Then inspect the page itself. Search-page damage can come from the title or snippet even when the underlying article is more balanced.'),
            ('Look for policy or accuracy issues', 'Privacy, impersonation, outdated information, fake reviews, harassment, copyright, defamation concerns or incorrect facts may each have different reporting or correction options.'),
            ('Avoid reputation spam', 'Thin fake profiles, copied articles and aggressive mass posting can look low-quality and may not solve the problem. The better route is truthful, approved and useful assets.'),
            ('Monitor every change', 'Track when Google crawls, when snippets change, when new results appear and which positive assets are discovered. Progress is measured across the whole search footprint.'),
        ],
        'faqs': [
            ('Is negative Google result help confidential?', 'Fix My Name Online™ is designed for private intake and discreet planning. Public assets are based on approved information only.'),
            ('What information should I send?', 'Send the exact search phrase, URLs, screenshots, dates, business/name details and what outcome you are hoping for.'),
        ],
    },
    'how-to-fix-bad-google-search-results': {
        'eyebrow': 'Fix bad Google search results',
        'title': 'How To Fix Bad Google Search Results | Fix My Name Online™',
        'h1': 'How to fix bad Google search results without making it worse',
        'description': 'How to fix bad Google search results safely: document evidence, check removal or correction paths, improve positive assets and monitor search changes.',
        'intro': 'Fixing bad Google search results is not one button. It is a sequence: evidence, source review, policy pathway, safe communication, positive asset building and monitoring. The wrong shortcut can make the problem louder.',
        'sections': [
            ('Find the source of the problem', 'Google may be showing a publisher page, review profile, social result, image, court database, complaint page or copied snippet. The source controls many of the next options.'),
            ('Check removal, update or correction routes', 'Depending on the facts, there may be a publisher request, Google outdated-content request, review report, privacy pathway or legal pathway. Some matters need legal advice outside reputation work.'),
            ('Build assets that deserve trust', 'Profiles, business pages, articles, FAQs, bios, interviews and proof pages work best when they are truthful, specific, useful and internally linked.'),
            ('Review results over weeks, not minutes', 'Search engines crawl and rank over time. A professional plan watches indexing, snippets, impressions and ranking movement instead of claiming instant control.'),
        ],
        'faqs': [
            ('Can I fix bad Google results myself?', 'You can start by saving evidence and checking official platform policies. Professional help is useful when the issue is sensitive, confusing or affects income or trust.'),
            ('What should I avoid?', 'Avoid fake content, threats, public arguments, spammy posting and anyone promising they control Google.'),
        ],
    },
    'bad-search-results-for-my-name': {
        'eyebrow': 'Personal name search problem',
        'title': 'Bad Search Results for My Name — What Can I Do? | Fix My Name Online™',
        'h1': 'Bad search results for your name? Start with a private map',
        'description': 'What to do when bad search results appear for your personal name, old name, business name, location or associated search terms.',
        'intro': 'When bad search results appear for your name, the problem is personal. People may search before hiring, dating, renting, investing, booking or trusting you. The first step is a private map of what appears and why.',
        'sections': [
            ('Search all name variations', 'Check your full name, old names, middle name, nicknames, professional name, business name, city, suburb, occupation and terms people may add when they are suspicious.'),
            ('Look at images, news and suggestions', 'Bad reputation signals are not only blue links. Image results, news tabs, autocomplete, people-also-search boxes and review snippets can shape first impressions.'),
            ('Decide what should stay private', 'Not every positive asset needs your whole life story. Reputation repair should use approved, truthful information that you are comfortable publishing.'),
            ('Build a safer positive footprint', 'Depending on the case, that may include profiles, biographies, service pages, professional proof, helpful articles, FAQs and ongoing monitoring.'),
        ],
        'faqs': [
            ('Will people know I used reputation help?', 'The intake is private. Public assets should look natural, truthful and appropriate to your situation, not like a public crisis campaign.'),
            ('Can this help with associated names?', 'Yes. Associated names, old names, nicknames, business names and locations should be mapped because people often search more than one phrase.'),
        ],
    },
    'personal-online-reputation-repair': {
        'eyebrow': 'Personal reputation repair',
        'title': 'Personal Online Reputation Repair — Private Name Search Help | Fix My Name Online™',
        'h1': 'Personal online reputation repair for name searches that feel unfair',
        'description': 'Private personal online reputation repair for people dealing with bad Google results, old articles, images, reviews, associated names and damaging search snippets.',
        'intro': 'Personal online reputation repair starts with a simple reality: people search names before they decide who to trust. If the first page shows old, incomplete or damaging material, the safest response is a private evidence map and a truthful plan for stronger current assets.',
        'sections': [
            ('Start with what people actually type', 'A personal reputation plan should map your full name, old names, nicknames, locations, business connections, image results and risk phrases. The damaging result may only appear for one combination, but that combination can still affect jobs, relationships, finance or clients.'),
            ('Separate private facts from public assets', 'Not every positive asset needs to reveal sensitive history. Strong personal repair uses approved information: accurate bios, professional profiles, current work, helpful articles, credentials, business pages and search-friendly proof points.'),
            ('Review removal pathways without promising outcomes', 'Some pages may have privacy, outdated-content, publisher correction, platform report or legal-review pathways. Others may not. A careful review helps avoid risky messages, public arguments or fake content.'),
            ('Monitor the whole search footprint', 'Progress is measured across the full search page: web, images, videos, snippets, suggestions and associated names. The goal is a safer, more accurate search footprint over time.'),
        ],
        'faqs': [
            ('Is personal online reputation repair confidential?', 'The intake and planning are private. Public assets are only created from information you approve.'),
            ('Can this help if I am not a public figure?', 'Yes. Everyday people are searched by employers, clients, landlords, partners and communities. Reputation harm is not limited to celebrities.'),
        ],
    },
    'remove-outdated-google-search-results': {
        'eyebrow': 'Outdated Google results',
        'title': 'Remove Outdated Google Search Results? Options and Limits | Fix My Name Online™',
        'h1': 'Remove outdated Google search results: what can be checked first',
        'description': 'Options for outdated Google search results, old snippets, changed pages, removed content, old articles and search results that no longer reflect the current facts.',
        'intro': 'Outdated Google search results can make old information look current. Sometimes the source page changed, the snippet is stale, an old page was copied, or a result no longer reflects the current facts. The first step is evidence, not panic.',
        'sections': [
            ('Check the live page and Google snippet separately', 'A result can be outdated because the publisher page changed but Google still shows the old snippet. It can also be outdated because another site copied or republished old information. Each case needs a different pathway.'),
            ('Collect proof of what changed', 'Save the search phrase, result title, snippet, URL, date, screenshots, original publication date and any current page showing the updated facts. Outdated-content requests are stronger when the difference is clear.'),
            ('Know the limits of Google tools', 'Google may update or remove certain stale results under its policies, but it does not control every publisher page and does not erase every old reference. Publisher contact or legal advice may be needed in some cases.'),
            ('Build current assets while review is pending', 'If an outdated result keeps ranking, accurate current pages, profiles and articles can help searchers see more context while formal review pathways are assessed.'),
        ],
        'faqs': [
            ('Can Google remove outdated results?', 'Sometimes. It depends on the source page, policy, evidence and whether the information is truly outdated or still publicly available.'),
            ('What should I send for review?', 'Send the exact Google result, URL, screenshot, search phrase, date and any proof showing the information has changed or is incomplete.'),
        ],
    },
    'reputation-monitoring-alerts': {
        'eyebrow': 'Reputation monitoring',
        'title': 'Reputation Monitoring Alerts for Name and Review Risk | Fix My Name Online™',
        'h1': 'Reputation monitoring alerts help you catch search problems early',
        'description': 'Reputation monitoring alerts for names, old names, businesses, Google reviews, bad results, associated names and search-risk terms before damage spreads.',
        'intro': 'Many reputation problems are found too late. Reputation monitoring alerts help identify new results, review changes, associated-name issues and search-risk terms before they become a bigger trust problem.',
        'sections': [
            ('Monitor more than your exact name', 'Search risk often appears through old names, business names, suburbs, job titles, directors, partners, review terms, complaint phrases and image results. A useful watchlist includes the phrases real people might search.'),
            ('Track new results and changed snippets', 'A page that has existed for years can become harmful if Google changes the title, snippet, image or freshness signal. Monitoring should record what changed and when.'),
            ('Use alerts to decide the next action', 'A new result may need no action, a quiet evidence file, a review-response plan, a publisher request, a Search Console/indexing check or a broader repair campaign.'),
            ('Report in plain English', 'The client should understand what appeared, why it matters, what was checked and what the safest next step is. Mystery dashboards do not build trust.'),
        ],
        'faqs': [
            ('Who needs reputation monitoring?', 'Professionals, founders, businesses, public figures and everyday people who cannot afford to be surprised by what appears when their name is searched.'),
            ('Does monitoring remove results?', 'No. Monitoring detects and documents changes. It helps decide whether removal review, review defence or reputation repair is needed.'),
        ],
    },
    'online-reputation-management-for-business': {
        'eyebrow': 'Business reputation management',
        'title': 'Online Reputation Management for Business | Fix My Name Online™',
        'h1': 'Online reputation management for businesses that get searched before they get trusted',
        'description': 'Online reputation management for businesses dealing with Google reviews, bad search results, complaint pages, outdated listings, brand snippets and trust problems.',
        'intro': 'Customers search before they call, book or buy. Business reputation management is about making sure Google, reviews and public profiles show the most accurate and useful picture of the business — while handling bad results carefully.',
        'sections': [
            ('Audit the branded search page', 'Check the business name, owner names, suburb, service terms, reviews, images, map results, complaint pages, directories and old listings. A business can lose trust before the customer ever reaches the website.'),
            ('Handle reviews with evidence and calm replies', 'Fake, unfair or malicious reviews need screenshots, pattern notes, policy review and professional public replies. Fighting in public usually makes the business look less trustworthy.'),
            ('Strengthen the trust assets', 'Service pages, About pages, case-safe proof, FAQs, location pages, profiles, videos and helpful articles can improve the search footprint around the brand.'),
            ('Separate reputation management from advertising', 'Ads can bring clicks, but reputation repair needs search assets, review hygiene, monitoring and clear public trust signals that keep working after the ad stops.'),
        ],
        'faqs': [
            ('Can reputation management help with fake Google reviews?', 'It can help document, report, respond and rebuild trust signals. Google decides whether any review is removed.'),
            ('Is this only for large businesses?', 'No. Local businesses, professionals, clinics, trades, agencies, restaurants and online brands can all be affected by search trust problems.'),
        ],
    },
    'what-shows-up-when-someone-googles-my-name': {
        'eyebrow': 'Name search check',
        'title': 'What Shows Up When Someone Googles My Name? | Fix My Name Online™',
        'h1': 'What shows up when someone Googles your name?',
        'description': 'A private name-search checklist for people worried about what employers, clients, dates, landlords or customers see when they Google a name.',
        'intro': 'Most people do not know what appears when someone Googles their name until something goes wrong. A private name-search check maps the first impression people see before they meet you, hire you, date you, rent to you or trust you.',
        'sections': [
            ('Search the way another person would', 'Use your full name, quoted name, old names, nicknames, suburb, business names, job title and risk words. Check web results, images, videos, news, reviews and suggestions.'),
            ('Look at snippets, not only links', 'The headline and snippet can cause the damage even if the page itself is old or more balanced. Screenshots help record exactly what others may be seeing.'),
            ('Classify the search results', 'Mark each result as positive, neutral, outdated, sensitive, review-related, article-related, image-related, associated-name risk or possible removal-review candidate.'),
            ('Choose a safe next step', 'Some issues need monitoring, some need a quiet correction request, some need review defence and some need a broader positive-footprint strategy.'),
        ],
        'faqs': [
            ('Should I Google myself often?', 'Occasionally, yes, but track results calmly. Repeated panic searching does not solve the issue; evidence and a plan do.'),
            ('Can Fix My Name Online check it for me?', 'Yes. The Free Search Snapshot™ is designed as a private first check of name, business, URL and review concerns.'),
        ],
    },
    'google-review-defence-for-small-business': {
        'eyebrow': 'Small business review defence',
        'title': 'Google Review Defence for Small Business | Fix My Name Online™',
        'h1': 'Google review defence for small businesses hit by unfair reviews',
        'description': 'Google review defence for small businesses facing fake, unfair, malicious, competitor, ex-employee or review-bombing attacks on Google.',
        'intro': 'For a small business, one unfair Google review can affect phone calls, bookings and trust. The best defence is not a public fight. It is evidence, policy review, calm responses and stronger trust signals around the business.',
        'sections': [
            ('Save the review evidence', 'Record the review text, rating, reviewer name, date, screenshots, business relationship, timeline and any signs of fake, competitor, ex-employee or coordinated activity.'),
            ('Check possible Google policy issues', 'A review may involve conflict of interest, spam, harassment, impersonation, irrelevant content or another policy issue. The report should connect facts to policy, not just say the review is unfair.'),
            ('Write for future customers', 'A public reply should reassure future customers. Keep it short, calm and professional. Avoid threats, private details or emotional arguments.'),
            ('Repair the wider search page', 'Review defence also means stronger service pages, profile accuracy, FAQs, photos, business proof, helpful content and monitoring so one hostile review is not the whole story.'),
        ],
        'faqs': [
            ('Can a small business delete a Google review?', 'The business cannot directly delete third-party reviews. Google decides. A business can report possible policy violations and respond professionally.'),
            ('Should I ask customers for more reviews?', 'Follow platform rules and avoid incentives or pressure. A steady pattern of genuine customer feedback is safer than a sudden suspicious spike.'),
        ],
    },
    'clean-up-my-google-results': {
        'eyebrow': 'Clean up Google results',
        'title': 'How Do I Clean Up My Google Results? | Fix My Name Online™',
        'h1': 'How do I clean up my Google results?',
        'description': 'Plain-English help for people asking how to clean up Google results for their name, business, old articles, bad reviews or embarrassing search results.',
        'intro': 'When people say they want to clean up their Google results, they usually mean one thing: the search page is giving people the wrong first impression. The safe way starts with evidence, source checks and a plan for better current information.',
        'sections': [
            ('Check exactly what needs cleaning up', 'Write down the search phrase, result title, snippet, URL, image and date. A bad headline, old snippet, review box or copied page can each need a different response.'),
            ('Do not make it louder', 'Avoid public arguments, repeated angry comments, threats or spammy posts. Those reactions can create more search signals around the same problem.'),
            ('Look for realistic update or removal paths', 'Some results may have an outdated-content, privacy, correction, review-policy or publisher request pathway. Others may need a stronger positive search footprint instead.'),
            ('Build better results people can trust', 'Useful profiles, bios, business pages, articles, FAQs and proof pages can help Google and searchers see a fuller current picture over time.'),
        ],
        'faqs': [
            ('Can you clean up Google results instantly?', 'No. Search engines, publishers and platforms make their own decisions. A safe plan improves evidence, assets, discovery and monitoring over time.'),
            ('What should I send first?', 'Send the exact search phrase, screenshots, URLs, your name or business name, and what worries you most.'),
        ],
    },
    'old-stuff-showing-up-on-google': {
        'eyebrow': 'Old stuff on Google',
        'title': 'Why Is Old Stuff Showing Up on Google? | Fix My Name Online™',
        'h1': 'Why is old stuff showing up when I Google myself?',
        'description': 'What to do when old stuff, outdated pages, old articles, records or embarrassing results keep showing up on Google for your name.',
        'intro': 'Old results can feel unfair because Google can make an old chapter look fresh. The page may be old, copied, re-indexed, newly linked or shown with a snippet that misses the full context.',
        'sections': [
            ('Work out whether the page or snippet is old', 'Sometimes the website still shows the old information. Sometimes the website changed but Google is showing an old title or snippet. That difference matters.'),
            ('Save proof of the age and context', 'Keep screenshots, original dates, current facts, changed outcomes and the exact Google result. Evidence makes any request stronger.'),
            ('Check official pathways first', 'There may be a publisher correction, outdated-content request, privacy pathway or platform process. Not every old page qualifies, but it should be checked properly.'),
            ('Add the current version of the story', 'If old material remains online, accurate current assets can help searchers see who you are now, not only what happened years ago.'),
        ],
        'faqs': [
            ('Can old information be removed from Google?', 'Sometimes a result or snippet can be updated or removed under specific policies, but there is no universal right to erase every old result.'),
            ('Is this only for court records?', 'No. It can involve old articles, reviews, images, copied pages, complaint sites, directories or outdated profiles.'),
        ],
    },
    'someone-googled-me-and-found-something-bad': {
        'eyebrow': 'Someone searched me',
        'title': 'Someone Googled Me and Found Something Bad | Fix My Name Online™',
        'h1': 'Someone Googled me and found something bad. What now?',
        'description': 'Private next steps when an employer, client, date, landlord or customer Googled your name and found something bad or embarrassing.',
        'intro': 'The worst part is often the silence afterwards: the job goes cold, the client hesitates, the date changes tone or the customer stops replying. Before reacting, map exactly what they may have seen.',
        'sections': [
            ('Do the same search they likely did', 'Search your full name, business name, city, job title, old names and obvious risk words. Check web, images, news, reviews and suggestions.'),
            ('Record the first impression', 'Most people only look for seconds. Save the headline, snippet, image, ranking position and source so you know what shaped their view.'),
            ('Choose a private response', 'Depending on the issue, the next move may be monitoring, removal review, review defence, a correction request or stronger positive assets.'),
            ('Do not over-explain publicly', 'Public crisis posts can draw more attention. Reputation repair should be calm, private-first and based on approved truthful information.'),
        ],
        'faqs': [
            ('Should I contact the person who searched me?', 'Sometimes, but not always. First understand what appeared and whether a quiet fix, evidence pack or better public asset is safer.'),
            ('Can this be handled discreetly?', 'Yes. The first step is a private Free Search Snapshot™ so the issue can be mapped before any public action.'),
        ],
    },
    'bad-review-costing-me-customers': {
        'eyebrow': 'Bad review damage',
        'title': 'A Bad Review Is Costing Me Customers | Fix My Name Online™',
        'h1': 'A bad review is costing me customers. What can I do?',
        'description': 'Plain-English Google review defence for business owners worried that a fake, unfair or damaging review is costing calls, bookings and customers.',
        'intro': 'One bad review can change how strangers see a business before they ever call. The best response is evidence, policy review, a calm public reply and stronger trust signals around the business.',
        'sections': [
            ('Save the review and the pattern', 'Record the review text, star rating, reviewer name, date, screenshots, booking history and any signs of fake, competitor, ex-staff or coordinated behaviour.'),
            ('Check whether it may breach policy', 'Google decides review removals. A useful report connects facts to possible policy issues instead of simply saying the review is unfair.'),
            ('Reply for future customers', 'A calm owner response can reassure the next person reading. Avoid threats, private details or emotional back-and-forth.'),
            ('Strengthen the rest of the search page', 'Better business pages, FAQs, photos, accurate profiles and review hygiene can reduce the damage of one hostile result.'),
        ],
        'faqs': [
            ('Can you delete a bad Google review?', 'No agency can directly delete Google reviews. We help document, report where appropriate, respond and repair surrounding trust signals.'),
            ('Should I ask happy customers for reviews?', 'Follow platform rules. Genuine steady feedback is safer than pressure, incentives or a sudden suspicious spike.'),
        ],
    },
    'old-court-record-showing-on-google': {
        'eyebrow': 'Old court record search risk',
        'title': 'Old Court Record Showing on Google | Fix My Name Online™',
        'h1': 'Old court record showing on Google? Start with context and evidence',
        'description': 'Private guidance when an old court record, tribunal page, appeal transcript or legal mention appears in Google search results for your name.',
        'intro': 'Old court and tribunal pages can be complicated. Some are public records, some are copied by other sites, some miss context, and some show in Google in a way that feels newly damaging.',
        'sections': [
            ('Identify the source and copy sites', 'Check whether Google shows an official court page, publisher article, database, scraper site or copied version. The source affects the options.'),
            ('Collect the missing context', 'Save dates, outcomes, appeal results, corrections, expungement or spent-conviction information where relevant, and screenshots of the search result.'),
            ('Separate legal advice from reputation planning', 'Some matters need a lawyer. Reputation work can help with search mapping, evidence packs, publisher/platform pathways and truthful current assets.'),
            ('Build a current search footprint carefully', 'If the record remains online, approved professional assets can help show more than one old result, without pretending the search engine can be controlled.'),
        ],
        'faqs': [
            ('Can old court records always be removed?', 'No. It depends on the record, jurisdiction, source, legal status and platform policy. The first step is a careful review.'),
            ('Is Fix My Name Online a law firm?', 'No. We are not a law firm and do not provide legal advice. We help with private search review and reputation pathways.'),
        ],
    },
    'my-name-brings-up-embarrassing-results': {
        'eyebrow': 'Embarrassing name results',
        'title': 'My Name Brings Up Embarrassing Results | Fix My Name Online™',
        'h1': 'My name brings up embarrassing results. What are my options?',
        'description': 'Private help for embarrassing Google results tied to your name, old names, photos, articles, comments, reviews or associated search terms.',
        'intro': 'Embarrassing search results can affect work, dating, family, finance and confidence. The first step is not shame or panic; it is a private map of what appears and what can realistically be done.',
        'sections': [
            ('List every search that triggers it', 'Check full name, old names, nicknames, locations, business names and image searches. Embarrassing results often appear only for certain combinations.'),
            ('Classify the result', 'It may be outdated, inaccurate, sensitive, review-related, image-related, copied, defamatory, private or simply lacking context. Each type has different options.'),
            ('Keep the response proportionate', 'Avoid public arguments, fake content or mass posting. A quiet, truthful repair plan is usually safer.'),
            ('Create better public context', 'Approved bios, profiles, business pages, helpful articles and proof points can help the search page show the person or business as they are now.'),
        ],
        'faqs': [
            ('Will this make the embarrassing result disappear?', 'No responsible service can promise that. We review possible pathways and build a safer search footprint over time.'),
            ('Do I have to explain everything publicly?', 'No. Public assets should use only approved information. Sensitive details can stay private unless there is a clear reason to publish.'),
        ],
    },
    'can-i-remove-my-name-from-google': {
        'eyebrow': 'Remove name from Google',
        'title': 'Can I Remove My Name From Google? | Fix My Name Online™',
        'h1': 'Can I remove my name from Google?',
        'description': 'Plain-English explanation of whether a person can remove their name from Google, what Google controls, and what private reputation repair can check.',
        'intro': 'Many people ask if they can remove their name from Google. The honest answer is: sometimes specific results may have pathways, but Google is an index of pages across the web, not a single profile you can simply delete.',
        'sections': [
            ('Google usually shows pages from other websites', 'The result may come from a publisher, review site, social profile, directory, court database, forum or copied page. The source often controls the content.'),
            ('Some personal information has special pathways', 'Certain privacy, outdated-content, explicit image, doxxing, impersonation or policy issues may be reviewable. Evidence and exact URLs matter.'),
            ('Removing a name is different from repairing a search page', 'If results cannot be removed, the safer goal may be to build accurate current assets and reduce the power of old or incomplete results over time.'),
            ('Start privately before contacting websites', 'A rushed message to a publisher or platform can backfire. Map the result and options before acting.'),
        ],
        'faqs': [
            ('Can Google delete every result about me?', 'No. Google and source websites make their own decisions, and public-interest material may remain online.'),
            ('What is the first step?', 'Send the name, URLs, screenshots and search phrases through a Free Search Snapshot™ for private review.'),
        ],
    },
    'hide-bad-google-results': {
        'eyebrow': 'Hide bad Google results',
        'title': 'Can You Hide Bad Google Results? Safer Options Explained | Fix My Name Online™',
        'h1': 'Can you hide bad Google results? Here is the safer way to think about it',
        'description': 'For people searching how to hide bad Google results: what is realistic, what to avoid, and safer reputation repair options.',
        'intro': 'People often search for how to hide bad Google results because they feel exposed. A responsible service should not promise to hide, bury or manipulate Google. The safer question is: what can be reviewed, corrected, updated or balanced with truthful current information?',
        'sections': [
            ('Avoid anyone promising secret control over Google', 'Guaranteed hiding, burying or instant removal claims are red flags. Search engines decide what ranks.'),
            ('Check whether the result itself has a pathway', 'Some problems may qualify for correction, privacy review, outdated-content review, review reporting or publisher contact. Others will not.'),
            ('Improve the search page honestly', 'Accurate profiles, pages, articles, FAQs, business proof and monitoring can give searchers a fuller view over time.'),
            ('Protect future searches', 'Monitoring names, old names, business names and risk terms helps catch new issues early before they become the only thing people see.'),
        ],
        'faqs': [
            ('Is hiding bad results the same as removal?', 'No. Removal means a specific result may be taken down, updated or de-indexed. Broader reputation repair focuses on the whole search page.'),
            ('Can positive content help?', 'Truthful positive assets can help over time, but rankings and search outcomes are decided by search engines.'),
        ],
    },
    'what-do-employers-see-when-they-google-me': {
        'eyebrow': 'Employer search check',
        'title': 'What Do Employers See When They Google Me? | Fix My Name Online™',
        'h1': 'What do employers see when they Google me?',
        'description': 'A private checklist for job seekers and professionals worried about what employers see when they Google a name before an interview or offer.',
        'intro': 'Employers, recruiters and clients often search before making a decision. If the results show old issues, embarrassing pages, articles, images or thin profiles, the first impression may form before you speak.',
        'sections': [
            ('Search your name like a recruiter', 'Use your full name, city, profession, old names, LinkedIn name, business history and any likely risk words. Check web, images, news and videos.'),
            ('Look for gaps as well as bad results', 'Sometimes the problem is not only a bad link. It is the absence of strong current professional assets that explain who you are now.'),
            ('Prepare approved professional assets', 'A clear bio, service page, portfolio, profiles, articles, FAQs and proof points can make the search page more useful and current.'),
            ('Handle sensitive results quietly', 'If an old article, record or complaint appears, review options and evidence before trying to explain it publicly.'),
        ],
        'faqs': [
            ('Should I clean my results before applying for jobs?', 'It is wise to check early. Reputation repair takes time, so a private snapshot before a major application can prevent surprises.'),
            ('Can this help professionals and business owners?', 'Yes. The same search risk affects executives, trades, consultants, creators, founders and everyday job seekers.'),
        ],
    },
    'fix-my-online-reputation-fast': {
        'eyebrow': 'Fast reputation help',
        'title': 'How Can I Fix My Online Reputation Fast? | Fix My Name Online™',
        'h1': 'How can I fix my online reputation fast without making it worse?',
        'description': 'Urgent but careful steps for people wanting to fix their online reputation fast after bad Google results, reviews, articles or search surprises.',
        'intro': 'When a search result is hurting jobs, customers or relationships, it feels urgent. Fast does not mean reckless. The first 24 hours should be about evidence, triage and choosing the safest next step.',
        'sections': [
            ('First: freeze the evidence', 'Screenshot the results, URLs, snippets, reviews, images and dates before anything changes. Good evidence prevents guesswork.'),
            ('Second: stop risky reactions', 'Do not threaten, spam, fake reviews, make public accusations or publish panic posts. Those actions can become new reputation problems.'),
            ('Third: triage the pathway', 'Decide whether the issue is removal review, review defence, monitoring, positive asset building or legal referral. Different problems need different tools.'),
            ('Fourth: build the next visible proof', 'Even while review pathways are checked, useful current assets can be prepared so the search page has better material to discover.'),
        ],
        'faqs': [
            ('What can be done quickly?', 'Evidence capture, risk triage, review-response drafts, profile cleanup and preparation of approved assets can happen quickly. Search ranking changes usually take longer.'),
            ('Is urgent reputation help private?', 'Yes. The first step can be a private Free Search Snapshot™ before any public move is made.'),
        ],
    },

}


def load_generated_seo_guides():
    """Load Hermes SEO OS generated guides without hand-editing server.py.

    Expected file: generated_seo_guides.json in the app root.
    Shape matches SEO_GUIDES: {slug: {eyebrow,title,h1,description,intro,sections,faqs}}.
    Invalid records are skipped so a bad generated page cannot take down the app.
    """
    path = Path('generated_seo_guides.json')
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    for slug, guide in data.items():
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{2,90}', str(slug or '')):
            continue
        if not isinstance(guide, dict):
            continue
        required = ['eyebrow', 'title', 'h1', 'description', 'intro', 'sections', 'faqs']
        if not all(k in guide for k in required):
            continue
        if not isinstance(guide.get('sections'), list) or not isinstance(guide.get('faqs'), list):
            continue
        SEO_GUIDES[str(slug)] = guide


load_generated_seo_guides()


def guide_schema(slug, guide):
    return f'''<script type="application/ld+json">{json.dumps({
        '@context': 'https://schema.org',
        '@graph': [
            {'@type': 'Article', '@id': f'{DOMAIN}/{slug}#article', 'headline': guide['h1'], 'description': guide['description'], 'author': {'@type': 'Organization', 'name': 'Fix My Name Online'}, 'publisher': {'@type': 'Organization', 'name': 'MadisonJade Pty Ltd'}, 'mainEntityOfPage': f'{DOMAIN}/{slug}'},
            {'@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': DOMAIN + '/'},
                {'@type': 'ListItem', 'position': 2, 'name': 'Learn', 'item': DOMAIN + '/learn'},
                {'@type': 'ListItem', 'position': 3, 'name': guide['h1'], 'item': f'{DOMAIN}/{slug}'},
            ]},
            {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in guide['faqs']]},
        ]
    }, ensure_ascii=False)}</script>'''


@app.route('/when-google-makes-your-past-look-like-your-present')
def google_past_present_article():
    description = "Old court records, appeal transcripts, scraped pages and outdated search results can make a person's past look current. FixMyNameOnline™ explains the human cost and private next steps."
    body = """
    <style>
      .article-hero{width:100%;border-radius:20px;margin:8px 0 22px;border:1px solid rgba(255,255,255,.12);box-shadow:0 18px 50px rgba(0,0,0,.35)}
      .article p{font-size:18px;line-height:1.72;color:#edf1f8}.article h2{font-size:30px;margin-top:34px;color:#fff}.article blockquote{margin:28px 0;padding:20px 22px;border-left:5px solid var(--red);background:rgba(217,31,61,.10);border-radius:16px;color:#fff;font-size:23px;line-height:1.35;font-weight:800}.article ul{color:#edf1f8;font-size:18px;line-height:1.7}.article .byline{color:var(--grey);font-size:15px}.article .cta-box{border:1px solid rgba(217,31,61,.4);background:linear-gradient(135deg,rgba(217,31,61,.18),rgba(255,255,255,.05));border-radius:20px;padding:24px;margin-top:28px}
    </style>
    <div class="card article">
      <span class="pill">FixMyNameOnline™ article</span>
      <h1>When Google makes your past look like your present</h1>
      <p class="byline">By FixMyNameOnline™ · MadisonJade Pty Ltd</p>
      <img class="article-hero" src="/assets/old-records-google-past-present-hero.png" alt="Distressed person looking at online search results late at night">
      <p>People try to move on.</p>
      <p>That should not be controversial.</p>
      <p>They get up. They go to work. They apply for better jobs. They start over after a divorce, a court case, a bad business deal, a public mistake, an allegation, a family breakdown, a review bomb, or a chapter they would give anything not to relive.</p>
      <p>They do the hard part. They rebuild.</p>
      <p>Then one night they Google their name and there it is again.</p>
      <p>An old court page. An appeal transcript. A scraped public record. A page they have never seen before, sitting on a website they do not control, dressed up with a fresh date or a new URL so Google treats it like something new.</p>
      <blockquote>To everyone else, it is a search result. To them, it can feel like being dragged back into the worst room of their life.</blockquote>

      <h2>The punishment does not always end when the case ends</h2>
      <p>There are people walking around right now who have already paid the price for whatever happened.</p>
      <p>Some were cleared. Some appealed. Some changed. Some were never fairly understood in the first place. Some made a mistake years ago and have spent every day since trying to become someone better.</p>
      <p>But Google does not show the years after.</p>
      <p>It does not show the person getting clean. The parent showing up. The worker doing honest days. The business owner trying again. The quiet repair. The private shame. The effort.</p>
      <p>It shows a headline. It shows a snippet. It shows a date.</p>
      <p>And if that date looks fresh, the past can suddenly look like it happened yesterday.</p>
      <blockquote>That is not accountability. That is a digital life sentence.</blockquote>

      <h2>This is how lives get quietly damaged</h2>
      <p>Most people do not get a phone call saying, “We found something on Google and decided not to hire you.”</p>
      <p>They do not get told, “The client searched your name and got nervous.”</p>
      <p>They do not get told, “The landlord looked you up.”</p>
      <p>They just feel the silence.</p>
      <p>The interview goes nowhere. The deal cools off. The date gets awkward. The family argument starts again. The person has to explain themselves to someone who has already made up their mind from three lines on a screen.</p>
      <blockquote>A stranger sees the result for five seconds. The person named carries the consequence for years.</blockquote>

      <h2>Old information can become newly harmful</h2>
      <p>Public records, legal decisions, appeal documents and tribunal pages can exist online. That is one thing.</p>
      <p>But some websites collect old material, copy it, repackage it, and make it easier for Google to find under a person's full name. A page may get a new URL. A new crawl date. A new layout. A fresh-looking timestamp. A title written for search.</p>
      <p>The result can be completely distorted.</p>
      <p>A person may have moved on. The matter may be old. The outcome may be missing. The context may be wrong. The page may be copied from somewhere else.</p>
      <p>But Google is not a human being sitting down with the whole story.</p>
      <p>Google ranks pages. Sometimes the page that wins is the one that hurts the person most.</p>

      <h2>People are not clickbait</h2>
      <p>A person's name is not a traffic strategy.</p>
      <p>Their worst day should not be recycled for clicks. Their family should not have to keep finding it. Their children should not have to explain it. Their employer should not see the old version before meeting the real person standing in front of them today.</p>
      <p>People deserve context. They deserve a chance to move forward. They deserve to know what is being shown about them and what options they may have.</p>
      <p>That does not mean every record can be removed. It does not mean Google can be forced to forget everything. No responsible service should promise that.</p>
      <p>But it does mean people should not be left alone with it.</p>

      <h2>What a proper review should check</h2>
      <p>If an old record, court page, review site, article, or scraped profile is showing for your name, the first step is not panic. The first step is evidence.</p>
      <ul>
        <li>what appears in Google for your name</li>
        <li>the exact URL and page title</li>
        <li>the snippet Google is showing</li>
        <li>the date Google appears to be using</li>
        <li>the original date of the matter</li>
        <li>whether the page is copied, duplicated, republished, or missing context</li>
        <li>whether the website offers a correction, removal, or privacy process</li>
        <li>whether Google tools may apply for outdated or misleading results</li>
        <li>whether your current, accurate identity is missing from page one</li>
      </ul>
      <p>From there, a person may be able to prepare a correction request, removal request, de-indexing request, outdated content request, privacy complaint, legal review, or a broader search repair plan.</p>
      <p>The right answer depends on the facts.</p>

      <h2>Your past should not be made to look like your present</h2>
      <p>This is why FixMyNameOnline™ exists.</p>
      <p>Not to sell fantasy. Not to promise magic. Not to tell people we can erase every hard thing that ever happened.</p>
      <p>We exist because people are being judged by search results before they get to speak.</p>
      <p>We exist because old material can be made to look new.</p>
      <p>We exist because ordinary people need a private, calm way to understand what Google is showing and what can be done next.</p>
      <p>If your name search is bringing up old records, court pages, reviews, articles, scraped profiles, or outdated material, start with a private snapshot.</p>
      <p>Google your name.</p>
      <p>Then ask one question: is this really the full story?</p>

      <div class="cta-box">
        <h2>Get a Free Private Snapshot™</h2>
        <p>FixMyNameOnline™ offers a private first look at what people may be seeing when they search your name.</p>
        <p><a class="btn" href="/app">Start Free Private Snapshot™ →</a> <a class="btn btn2" href="/learn">More guides</a></p>
        <p class="note">FixMyNameOnline™ is not a law firm and does not provide legal advice. No ranking, removal, review-removal, de-indexing or search outcome is guaranteed.</p>
      </div>
    </div>
    """
    return page('When Google Makes Your Past Look Like Your Present | FixMyNameOnline™', body, description=description, canonical_path='/when-google-makes-your-past-look-like-your-present')



FALSE_CLAIMS_SLUGS = ['false-information-about-me-online', 'remove-false-google-results', 'someone-posted-false-claims-about-me', 'false-allegations-showing-on-google', 'false-review-damaging-my-name']
DIY_OLD_ARTICLE_SLUGS = ['how-to-get-an-old-news-article-removed-australia', 'how-to-ask-a-publisher-to-correct-an-old-article', 'how-to-request-anonymisation-from-a-news-website', 'can-google-remove-an-article-about-me', 'publisher-will-not-remove-old-article', 'how-to-request-noindex-for-an-old-webpage', 'how-to-update-an-outdated-google-search-result', 'wrong-information-about-me-appears-on-google', 'old-court-article-appearing-in-google', 'how-to-contact-a-publisher-about-inaccurate-information']
BAD_GOOGLE_SLUGS = ['bad-results-on-google-what-to-do', 'what-to-do-if-google-results-are-bad', 'negative-google-results-help', 'how-to-fix-bad-google-search-results', 'bad-search-results-for-my-name', 'old-news-article-on-google', 'old-stuff-showing-up-on-google', 'remove-outdated-google-search-results'] + DIY_OLD_ARTICLE_SLUGS
JOB_PANIC_SLUGS = ['someone-googled-me-and-found-something-bad', 'what-shows-up-when-someone-googles-my-name', 'employer-googled-me-found-old-article', 'background-check-found-old-article', 'recruiter-found-negative-google-results']


def guide_cards_for(slugs):
    cards = []
    for slug in slugs:
        g = SEO_GUIDES.get(slug)
        if not g:
            continue
        cards.append(f'''<div class="card"><span class="pill">{safe(g['eyebrow'])}</span><h2><a href="/{safe(slug)}">{safe(g['h1'])}</a></h2><p class="sub">{safe(g['description'])}</p><p><a class="btn btn2" href="/{safe(slug)}">Read guide →</a></p></div>''')
    return ''.join(cards)


@app.route('/false-information-claims-online')
def false_information_claims_hub():
    schema = json.dumps({'@context':'https://schema.org','@type':'CollectionPage','name':'False Information and False Claims Online','description':'Private guides for false information, false Google results, false allegations and false reviews showing online.','url':DOMAIN + '/false-information-claims-online'}, ensure_ascii=False)
    body = f'''<script type="application/ld+json">{schema}</script><div class="card"><span class="pill">False information hub</span><h1>False information about you online? Start with evidence, not panic.</h1><p class="sub">This hub links the main private FixMyNameOnline™ guides for false claims, false Google results, false allegations and false reviews. Each pathway starts with a Free Search Snapshot™ so the issue can be mapped before any public action is considered.</p><div class="recommend"><h2>Quick answer</h2><p>If a false claim appears online, save the URL, screenshot, Google title/snippet, search phrase and date. Then separate factual errors from opinion and decide whether the path is a publisher correction, platform report, Google review/outdated-content process, legal advice, monitoring or positive search-footprint repair.</p><p><a class="btn" href="/app?source=false_claims_hub_top">Start Free Search Snapshot™ →</a></p></div></div><div class="grid" style="margin-top:16px">{guide_cards_for(FALSE_CLAIMS_SLUGS)}</div><div class="card" style="margin-top:16px"><h2>Related search-repair guides</h2><ul><li><a href="/bad-google-results-help">Bad Google Results hub</a></li><li><a href="/old-news-article-on-google">Old news article showing on Google</a></li><li><a href="/remove-negative-google-results">Remove negative Google results?</a></li><li><a href="/online-reputation-repair">Online reputation repair</a></li></ul><p><a class="btn" href="/app?source=false_claims_hub_bottom">Get private review →</a></p></div>'''
    return page('False Information About Me Online — Private Help | Fix My Name Online™', body, 'Private help when false information, false claims, false Google results or false reviews appear online for your name or business.', canonical_path='/false-information-claims-online')


@app.route('/bad-google-results-help')
def bad_google_results_hub():
    schema = json.dumps({'@context':'https://schema.org','@type':'CollectionPage','name':'Bad Google Results Help','description':'Private guides for bad Google results, old articles, outdated snippets, negative search results and personal name search problems.','url':DOMAIN + '/bad-google-results-help'}, ensure_ascii=False)
    body = f'''<script type="application/ld+json">{schema}</script><div class="card"><span class="pill">Bad Google results hub</span><h1>Bad Google results: private steps before it costs you work, trust or peace.</h1><p class="sub">Use this hub when Google shows an old article, bad snippet, complaint page, review, court mention, associated name or result that gives people the wrong first impression.</p><div class="recommend"><h2>Quick answer</h2><p>Do not argue publicly first. Capture the result, identify the source, check whether removal/correction/outdated-content pathways are realistic, then build truthful current assets if the bad result cannot be changed quickly.</p><p><a class="btn" href="/app?source=bad_google_hub_top">Start Free Search Snapshot™ →</a></p></div></div><div class="grid" style="margin-top:16px">{guide_cards_for(BAD_GOOGLE_SLUGS + JOB_PANIC_SLUGS)}</div><div class="card" style="margin-top:16px"><h2>Related high-intent pathways</h2><ul><li><a href="/false-information-claims-online">False information and false claims hub</a></li><li><a href="/worldwide-reputation-repair">Worldwide reputation repair</a></li><li><a href="/name-watch-alerts">NameWatch Alert™ monitoring</a></li><li><a href="/google-review-defence-worldwide">Google review defence worldwide</a></li></ul><p><a class="btn" href="/app?source=bad_google_hub_bottom">Get private review →</a></p></div>'''
    return page('Bad Google Results Help — Private Search Repair | Fix My Name Online™', body, 'Private help for bad Google results, old articles, outdated snippets, negative results and personal or business search reputation problems.', canonical_path='/bad-google-results-help')


@app.route('/learn')
def learn_hub():
    money_pages = '''
    <div class="card full"><span class="pill">False claims hub</span><h2><a href="/false-information-claims-online">False information and false claims online</a></h2><p class="sub">Private guides for false information about you online, false Google results, false allegations and false reviews damaging your name or business.</p></div>
    <div class="card full"><span class="pill">Bad Google results hub</span><h2><a href="/bad-google-results-help">Bad Google results help</a></h2><p class="sub">Old articles, bad snippets, outdated pages, court mentions, associated names and search results that make the wrong first impression.</p></div>
    <div class="card full"><span class="pill">Worldwide service</span><h2><a href="/worldwide-reputation-repair">Worldwide reputation repair</a></h2><p class="sub">Private search protection for people, founders and businesses dealing with reputation problems across countries, platforms and Google results.</p></div>
    <div class="card"><span class="pill">Start here</span><h2><a href="/online-reputation-repair">Online reputation repair</a></h2><p class="sub">Map bad Google results, old articles, damaging snippets, reviews and weak positive search footprints before choosing a repair path.</p></div>
    <div class="card"><span class="pill">Google results</span><h2><a href="/remove-negative-google-results">Remove negative Google results?</a></h2><p class="sub">A realistic private options review for negative search results, old pages, bad snippets, images and review-led search damage.</p></div>
    <div class="card"><span class="pill">Business reviews</span><h2><a href="/google-review-defence-worldwide">Google review defence worldwide</a></h2><p class="sub">Evidence audit, response planning and trust-recovery support for fake, unfair or malicious Google review problems worldwide.</p></div>
    '''
    cards = money_pages + '''<div class="card full"><span class="pill">Featured article</span><h2><a href="/when-google-makes-your-past-look-like-your-present">When Google makes your past look like your present</a></h2><p class="sub">Old records, appeal transcripts and scraped pages can resurface in search like they happened yesterday. This is the human cost behind bad Google results.</p></div>''' + ''.join(f'''<div class="card"><span class="pill">{safe(g['eyebrow'])}</span><h2><a href="/{safe(slug)}">{safe(g['h1'])}</a></h2><p class="sub">{safe(g['description'])}</p></div>''' for slug, g in SEO_GUIDES.items())
    body = f'''<div class="card"><span class="pill">Fix My Name Online™ learning hub</span><h1>Worldwide private reputation repair guides</h1><p class="sub">Useful, human-first guides for people and businesses worldwide dealing with bad Google results, fake reviews, old articles, associated names and search trust problems.</p><p><a class="btn" href="/app">Start Free Search Snapshot™ →</a> <a class="btn btn2" href="/services">View services</a></p></div><div class="grid" style="margin-top:16px">{cards}</div>'''
    return page('Learn — Worldwide Reputation Repair Guides | Fix My Name Online™', body, 'Fix My Name Online™ guides for worldwide reputation repair, online reputation management, bad Google results, fake reviews and personal search audits.', canonical_path='/learn')


@app.route('/i-have-bad-results-on-google')
@app.route('/i-have-bad-google-results')
@app.route('/my-google-results-are-bad')
@app.route('/what-can-i-do-about-bad-google-results')
@app.route('/bad-google-results-what-do-i-do')
def bad_google_results_variant_redirects():
    return redirect('/bad-results-on-google-what-to-do', code=301)


@app.route('/<slug>')
def seo_guide(slug):
    guide = SEO_GUIDES.get(slug)
    if not guide:
        return page('Not found — FixMyNameOnline™', '<div class="card"><h1>Page not found</h1><p><a class="btn" href="/">Back home</a></p></div>'), 404
    section_html = ''.join(f'<h2>{safe(heading)}</h2><p>{safe(text)}</p>' for heading, text in guide['sections'])
    faq_html = ''.join(f'<div class="card"><h2>{safe(q)}</h2><p>{safe(a)}</p></div>' for q, a in guide['faqs'])
    if slug in FALSE_CLAIMS_SLUGS:
        hub_link = '<li><a href="/false-information-claims-online">False information and false claims hub</a></li>'
        related_slugs = [x for x in FALSE_CLAIMS_SLUGS if x != slug][:4] + ['bad-google-results-help', 'old-news-article-on-google']
    elif slug in BAD_GOOGLE_SLUGS or slug in JOB_PANIC_SLUGS:
        hub_link = '<li><a href="/bad-google-results-help">Bad Google results hub</a></li>'
        related_slugs = [x for x in (BAD_GOOGLE_SLUGS + JOB_PANIC_SLUGS) if x != slug][:5] + ['false-information-claims-online']
    else:
        hub_link = '<li><a href="/learn">Reputation repair guide hub</a></li>'
        related_slugs = ['false-information-claims-online', 'bad-google-results-help', 'worldwide-reputation-repair', 'remove-negative-google-results']
    related = ''.join(f'<li><a href="/{safe(other)}">{safe(SEO_GUIDES.get(other, {}).get("h1", other.replace("-", " ").title()))}</a></li>' for other in related_slugs if other != slug)
    if slug in DIY_OLD_ARTICLE_SLUGS:
        top_cta = f'<div class="recommend"><h2>One old article or bad link?</h2><p>Start with one capped free score. If this pathway fits, the $49 DIY workspace prepares the evidence checklist, editable request, official route and 30-day plan. You submit it yourself.</p><p><a class="btn" href="/app?source={safe(slug)}_top">Get one free score →</a> <a class="btn btn2" href="/diy-action">See the $49 DIY workspace</a></p></div>'
        bottom_cta = f'<div class="recommend"><h2>Take the next step yourself</h2><p>Fixed price, one target URL, exact deliverables. No human-review promise and no removal guarantee.</p><p><a class="btn" href="/diy-action">See exactly what $49 includes →</a></p></div>'
    else:
        top_cta = f'<div class="recommend"><h2>Start with one private score</h2><p>Send one exact name, Google result, link, review or search phrase. The free tier is capped at one initial classification per email.</p><p><a class="btn" href="/app?source={safe(slug)}_top">Start Free Search Snapshot™ →</a></p></div>'
        bottom_cta = f'<div class="recommend"><h2>Start with a private search snapshot</h2><p>FMNO maps one issue before showing a paid DIY pathway. You confirm facts and submit external actions yourself.</p><p><a class="btn" href="/app?source={safe(slug)}_bottom">Start Free Search Snapshot™ →</a></p></div>'
    mid_cta = f'<p><a class="btn btn2" href="/app?source={safe(slug)}_mid">Get one capped private score →</a></p>'
    body = f'''{guide_schema(slug, guide)}<div class="card"><p class="note"><a href="/">Home</a> → <a href="/learn">Learn</a> → {safe(guide['h1'])}</p><span class="pill">{safe(guide['eyebrow'])}</span><h1>{safe(guide['h1'])}</h1><p class="sub">{safe(guide['intro'])}</p>{top_cta}{section_html}{mid_cta}{bottom_cta}<h2>Related Fix My Name Online™ guides</h2><ul>{hub_link}<li><a href="/worldwide-reputation-repair">Worldwide reputation repair</a></li><li><a href="/online-reputation-repair">Online reputation repair</a></li><li><a href="/remove-negative-google-results">Remove negative Google results?</a></li><li><a href="/google-review-defence-worldwide">Google review defence worldwide</a></li>{related}<li><a href="/fix-my-name-online">What is Fix My Name Online™?</a></li></ul><p class="note">FixMyNameOnline™ is not a law firm and does not provide legal advice. No ranking, removal, review-removal, de-indexing or search outcome is guaranteed.</p></div><div class="grid" style="margin-top:16px">{faq_html}</div>'''
    return page(guide['title'], body, description=guide['description'], canonical_path='/' + slug)


@app.route('/delete-me')
def delete_me_style_redirect():
    return redirect('/name-watch-alerts', code=301)


@app.route('/google-alerts-for-my-name')
def google_alerts_for_my_name_redirect():
    return redirect('/name-watch-alerts', code=301)


@app.route('/name-watch-alerts')
def name_watch_alerts_page():
    body = """
    <div class="card">
      <span class="pill">$29/month search monitoring</span>
      <h1>NameWatch Alert™: know when something new appears around your name.</h1>
      <p class="sub">A simple, low-cost monitoring layer for people who want early warning if a new Google result, article, review, image, snippet, associated-name result, or data-broker style listing starts showing around their name.</p>
      <div class="recommend"><h2>Think “DeleteMe-style peace of mind” for Google-name risk.</h2><p>We do not promise every result can be deleted. Instead, NameWatch Alert™ watches the search pattern and alerts you when something needs attention, so you are not surprised by an employer, client, date, investor, journalist, or family member finding it first.</p></div>
      <h2>What the $29/month plan includes</h2>
      <ul>
        <li>Monthly private Google-name sweep for supplied names, business names and associated names</li>
        <li>Monitoring of obvious new articles, review pages, images, snippets and high-risk result changes</li>
        <li>Email alert if we identify a new concerning result or material change</li>
        <li>Simple private status note: clear / watch / review recommended</li>
        <li>Upgrade path to Removal Review™, Review Defence™ or Starter™ only if needed</li>
      </ul>
      <p><a class="btn" href="/checkout/sentinel">Start NameWatch Alert™ — $29/month</a> <a class="btn btn2" href="/app?source=name_watch_alerts">Start free snapshot first</a></p>
      <p class="note" style="opacity:.46;font-size:12px">NameWatch Alert™ is a private monitoring service. If something needs action, we’ll explain the practical next-step options.</p>
    </div>
    <div class="grid" style="margin-top:16px">
      <div class="card"><h2>Best for</h2><p class="sub">Professionals, founders, job seekers, business owners, public-facing workers, creators, and anyone who wants to know early if something bad starts surfacing.</p></div>
      <div class="card"><h2>Not for</h2><p class="sub">Immediate crisis removal, legal advice, guaranteed deletion, guaranteed Google suppression, or full data-broker removal across every site. Those need a separate review.</p></div>
      <div class="card"><h2>What happens after payment?</h2><p class="sub">You complete private onboarding with the exact names, old names, locations, business names and search phrases to monitor. We set up the monitoring file and begin the first sweep.</p></div>
      <div class="card"><h2>If something appears</h2><p class="sub">We send a private alert and recommend the next practical path: ignore/watch, Removal Review™, Review Defence™, or a broader search repair plan.</p></div>
    </div>
    """
    return page('NameWatch Alert™ — $29/month Google-name monitoring | FixMyNameOnline™', body, 'NameWatch Alert™ is a $29/month private Google-name monitoring and new-result alert subscription by FixMyNameOnline™. Early warning for old links, reviews, articles, snippets, images and reputation risks.', canonical_path='/name-watch-alerts')


@app.route('/google-your-name')
def google_your_name_landing():
    body = """
    <div class="card">
      <span class="pill">Free private search check</span>
      <h1>Google your name. We’ll wait.</h1>
      <p class="sub">If old results, reviews, articles, associated names, bad links, or outdated snippets are affecting how people see you, start with a private Free Search Snapshot™.</p>
      <p><a class="btn" href="/free-search-snapshot">Start Free Search Snapshot™ →</a> <a class="btn btn2" href="/questions">Ask a private question</a></p>
      <div class="recommend"><h2>What we privately check</h2><ul><li>Your name, old names, nicknames, business names and associated names.</li><li>Bad links, articles, review issues, complaint pages, images or damaging search terms.</li><li>Whether the issue looks like monitoring, removal review, review defence or a broader repair plan.</li><li>What information we would need before preparing any public-facing asset or request.</li></ul></div>
      <h2>Private. Careful. No pressure.</h2>
      <p>We do not publish, submit, respond, report or use anything publicly from this landing page. The first step is only a private snapshot so you understand the search pattern and the safest next step.</p>
      <p class="note">FixMyNameOnline™ is not a law firm and does not provide legal advice. No Google ranking, removal, review removal, de-indexing, platform decision or search outcome is guaranteed.</p>
    </div>
    <div class="grid" style="margin-top:16px">
      <div class="card"><h2>Old Google results</h2><p class="sub">Old articles, snippets, images, complaint pages, associated names or results that follow you around.</p></div>
      <div class="card"><h2>Bad reviews</h2><p class="sub">Fake, malicious, unfair or damaging business reviews that may need evidence, response notes or platform-policy review.</p></div>
      <div class="card"><h2>Everyday checks</h2><p class="sub">Jobs, clients, dating, finance, partnerships and people quietly searching before they trust you.</p></div>
      <div class="card"><h2>Positive footprint</h2><p class="sub">Truthful, approved assets that help show the fuller current picture over time.</p></div>
    </div>
    """
    return page('Google your name — Free Search Snapshot™ | FixMyNameOnline™', body, 'Google your name. Start a private Free Search Snapshot™ for old results, reviews, bad links, associated names and reputation-sensitive search problems.', canonical_path='/google-your-name')


@app.route('/free-search-snapshot')
def ad_free_snapshot_form():
    source_page = safe(request.args.get('source') or 'free_search_snapshot_page')
    prefill_name = safe(request.args.get('name') or request.args.get('names_to_check') or '')
    body = f"""
    <div class="card"><span class="pill">Start here</span><h1>Free Search Snapshot™</h1><p class="sub">Tell us what people may search and what worries you. We’ll privately map the pattern and point you toward the safest next step.</p>
    <form method="post" action="/submit-snapshot" class="grid">
      <input type="hidden" name="source_page" value="{source_page}">
      <div><label>Your name</label><input name="name" required autocomplete="name"></div>
      <div><label>Email</label><input name="email" type="email" required autocomplete="email"></div>
      <div><label>Phone optional</label><input name="phone" autocomplete="tel"></div>
      <div><label>Best describes this</label><select name="case_type"><option>Personal name / old Google results</option><option>Business name / bad search results</option><option>Fake or malicious Google reviews</option><option>Old news article or court mention</option><option>Associated name / old name / nickname</option><option>High-risk private case</option></select></div>
      <div class="full"><label>Names/businesses to check</label><textarea name="names_to_check" placeholder="Your full name, old names, nicknames, business names, associated names, locations...">{prefill_name}</textarea></div>
      <div class="full"><label>Bad links, review links, article titles, or search terms if you have them</label><textarea name="problem_links" placeholder="Paste URLs or write things like: John Smith court, Jane Smith review, business name complaint..."></textarea></div>
      <div class="full"><label>What outcome are you hoping for?</label><textarea name="goal" placeholder="Example: I want to know if this can be removed, or I need better results showing before people find the bad link."></textarea></div>
      <div class="full"><button class="btn" type="submit">Submit Free Snapshot →</button> <a class="btn btn2" href="/questions">Ask a question first</a><p class="note">Private intake. No public case disclosure. No rankings/removals guaranteed.</p></div>
    </form></div>"""
    return page('Free Search Snapshot™ — FixMyNameOnline™', body, 'Start a private Free Search Snapshot™ for reputation-sensitive name, business, review, article and search-result problems.', canonical_path='/free-search-snapshot')


@app.route('/free-snapshot')
def free_snapshot_short_redirect():
    return redirect('/free-search-snapshot', code=301)


@app.route('/namewatch')
def namewatch_short_redirect():
    return redirect('/name-watch-alerts', code=301)


@app.route('/name-watch')
def name_watch_short_redirect():
    return redirect('/name-watch-alerts', code=301)


def paid_next_steps_html(source='post_snapshot'):
    return f'''
    <div class="recommend"><span class="pill">Choose a paid next step</span><h2>Turn the free snapshot into protection.</h2><p>Most people do not need a big package first. After the free snapshot, the easiest paid step is NameWatch Alert™ at $29/month. If there is already a clear link, article, review or broader search issue, choose the review or repair path.</p>
      <div class="grid" style="margin-top:14px">
        <div class="card"><h2>NameWatch Alert™</h2><p class="sub">$29/month Google-name monitoring and new-result alerts.</p><p><a class="btn" href="/checkout/sentinel?source={safe(source)}">Start $29/month →</a></p></div>
        <div class="card"><h2>Removal Review™</h2><p class="sub">$297 one-time review for specific links, articles, images or snippets.</p><p><a class="btn btn2" href="/checkout/removal-review?source={safe(source)}">Review links →</a></p></div>
        <div class="card"><h2>Review Defence™</h2><p class="sub">$497 one-time review defence for fake, unfair or malicious Google reviews.</p><p><a class="btn btn2" href="/checkout/review-defence?source={safe(source)}">Defend reviews →</a></p></div>
        <div class="card"><h2>Starter™</h2><p class="sub">$499/month for an approved positive search-footprint plan.</p><p><a class="btn btn2" href="/checkout/starter?source={safe(source)}">Start repair →</a></p></div>
      </div>
      <p class="note" style="opacity:.42;font-size:12px">Paid plans are private next steps based on the search pattern. Search/platform outcomes vary.</p>
    </div>'''


@app.route('/pricing')
def pricing():
    return redirect('/#pricing', code=301)


@app.route('/how-it-works')
def how_it_works():
    return redirect('/#how-it-works', code=301)


@app.route('/faq')
def faq():
    return redirect('/#faq', code=301)


@app.route('/api/concierge/chat', methods=['POST'])
def api_concierge_chat():
    payload = request.get_json(silent=True) or {}
    topic = payload.get('topic') or payload.get('issue_type') or ''
    collected = payload.get('collected') if isinstance(payload.get('collected'), dict) else {}
    if not collected and isinstance(payload.get('session'), dict):
        collected = payload.get('session')
    message = str(payload.get('message') or '').strip()
    current_field = str(payload.get('current_field') or '').strip()
    response = make_concierge_response(topic, collected, message, current_field)
    response['voice_available'] = concierge_voice_configured()
    return jsonify(response)


@app.route('/api/concierge/voice', methods=['POST'])
def api_concierge_voice():
    """Speak only the current concierge reply using Bill/ElevenLabs if configured."""
    if not concierge_voice_configured():
        return Response(status=204)
    payload = request.get_json(silent=True) or {}
    text = str(payload.get('text') or '').strip()
    if not text:
        return Response(status=204)
    result = synthesize_concierge_voice(text)
    if not result:
        return Response(status=204)
    audio, mimetype = result
    return Response(audio, mimetype=mimetype, headers={'Cache-Control': 'no-store'})


@app.route('/api/concierge/submit', methods=['POST'])
def api_concierge_submit():
    payload = request.get_json(silent=True) or {}
    collected = payload.get('collected') if isinstance(payload.get('collected'), dict) else {}
    transcript = payload.get('transcript') if isinstance(payload.get('transcript'), list) else []
    collected = {k: str(v or '').strip()[:2000] for k, v in collected.items()}
    name = collected.get('contact_name') or collected.get('names_to_check') or ''
    email = collected.get('email') or ''
    if not name or not email or '@' not in email:
        return jsonify({'ok': False, 'error': 'Please add a contact name and valid email before submitting.'}), 400
    if free_snapshot_used(email):
        return jsonify({'ok': False, 'error': 'The free score is limited to one per email.', 'upgrade_url': '/diy-action'}), 429
    issue_label = collected.get('issue_label') or CONCIERGE_TOPIC_LABELS.get(collected.get('issue_type'), collected.get('issue_type', 'Private search issue'))
    data = {
        'name': name,
        'email': email,
        'phone': collected.get('phone', ''),
        'case_type': issue_label,
        'names_to_check': collected.get('names_to_check', ''),
        'problem_links': '\n'.join(x for x in [collected.get('country_state', ''), collected.get('problem_links', '')] if x),
        'goal': collected.get('goal', ''),
        'source_page': 'private_search_concierge_agent_v1',
    }
    triage = triage_snapshot(data)
    queue_item = make_queue_item('free_snapshot', data, triage)
    source = {**data, 'triage': triage, 'queue_id': queue_item['id'], 'concierge_collected': collected, 'concierge_transcript': transcript[-20:]}
    append_jsonl(LEADS_FILE, {**source, 'searched_name': data.get('names_to_check') or data.get('name'), 'submitted_at': utc_now()})
    append_jsonl(CLICK_EVENTS_FILE, {'event': 'snapshot_submit', 'label': 'homepage_private_concierge', 'href': '/api/concierge/submit', 'location': request.path, 'source': data.get('source_category'), 'email': data.get('email'), 'searched_name': data.get('names_to_check') or data.get('name'), 'queue_id': queue_item['id'], 'referrer': data.get('referrer')})
    append_jsonl(CONCIERGE_TRANSCRIPTS_FILE, {'queue_id': queue_item['id'], 'collected': collected, 'transcript': transcript[-40:]})
    append_jsonl(FULFILMENT_QUEUE_FILE, queue_item)
    case = safe_create_fulfilment_case('free-snapshot', data, source, 'concierge_agent_v1')
    run_free_snapshot_pipeline(case)
    case = get_case(case.get('id')) if case and get_case else case
    report = latest_free_snapshot_report(case)
    case_room = save_case_room(queue_item, data, triage, case=case, report=report, transcript=transcript)
    send_telegram_alert('FMNO Concierge Free Snapshot created', {
        'queue_id': queue_item['id'],
        'case_id': case.get('id') if case else '',
        'name': data.get('name'),
        'email': data.get('email'),
        'case_type': data.get('case_type'),
        'recommendation': (report or {}).get('recommended_package') or triage.get('label'),
        'risk_score': case_room.get('risk_score', {}).get('score'),
        'admin_report': f"{DOMAIN}/admin/fulfilment/report/{case.get('id')}" if case else '',
        'private_case_room': case_room.get('case_room_url'),
    })
    email_status = send_snapshot_emails(data, triage, queue_item, case=case, report=report, case_room=case_room)
    record_email_alert_status('concierge_snapshot', f"FMNO concierge lead: {triage['label']} — {data.get('name', '')}", email_status.get('internal_email_sent') if isinstance(email_status, dict) else {}, {'queue_id': queue_item['id'], 'case_id': case.get('id') if case else '', 'email': data.get('email')})
    return jsonify({
        'ok': True,
        'queue_id': queue_item['id'],
        'case_id': case.get('id') if case else '',
        'risk_score': case_room.get('risk_score'),
        'case_room_url': case_room.get('case_room_url'),
        'message': 'Your Free Search Snapshot™ request is in. Your Private Case Room™ is ready with the first Reputation Risk Score™.',
        'redirect': f"/private-case-room/{queue_item['id']}?access_token={case_room.get('access_token')}",
    })


@app.route('/snapshot-received')
def snapshot_received_light():
    ref = request.args.get('ref', '')
    body = f'''<div class="card"><span class="pill ok">Received</span><h1>Your Private Reputation Risk Score™ is ready.</h1><p class="sub">Thank you. We saved the private concierge intake and will prepare the search snapshot pathway from here.</p><p class="note">Private reference: {safe(ref)}<br>No public action happens from this intake alone.</p><p><a class="btn" href="/">Back to site</a></p></div>'''
    return page('Snapshot received — FixMyNameOnline™', body)


@app.route('/private-case-room/<queue_id>')
def private_case_room(queue_id):
    record = find_case_room(queue_id)
    supplied = (request.args.get('access_token') or '').strip()
    if not record or not supplied or not hmac.compare_digest(supplied, record.get('access_token', '')):
        body = '''<div class="card"><span class="pill err">Private access</span><h1>Private Case Room™ link required.</h1><p class="sub">For privacy, this room only opens from the secure link created after a Free Search Snapshot™ intake.</p><p><a class="btn" href="/">Back to FixMyNameOnline™</a></p></div>'''
        return page('Private Case Room™ — secure link required', body), 403

    score = record.get('risk_score') or {}
    triage = record.get('triage') or {}
    preview = record.get('intake_preview') or {}
    factors = ''.join(f'<li>{safe(item)}</li>' for item in score.get('factors', [])) or '<li>Private intake received.</li>'
    timeline = [
        ('1', 'Private intake received', 'Your issue has been captured into a confidential case room.'),
        ('2', 'Reputation Risk Score™ created', 'The first score helps prioritise the private snapshot and next-step pathway.'),
        ('3', 'Snapshot review / QC', 'FMNO reviews the search context before recommending paid work or sending next instructions.'),
        ('4', 'Choose next path', 'You decide whether to continue with alerts, removal review, review defence, repair, or private concierge support.'),
    ]
    timeline_html = ''.join(f'<div class="card"><span class="pill">Step {n}</span><h2>{safe(title)}</h2><p class="sub">{safe(text)}</p></div>' for n, title, text in timeline)
    body = f'''
    <div class="card"><span class="pill ok">Private Case Room™</span><h1>Your private reputation snapshot room is open.</h1>
      <p class="sub">This is the secure first view for {safe(record.get('name'))}. No public action happens from this intake. This room is for private triage and next-step guidance only.</p>
      <div class="recommend"><h2>Reputation Risk Score™: {safe(score.get('score'))}/100 · {safe(score.get('label'))}</h2><p>{safe(score.get('summary'))}</p><ul>{factors}</ul></div>
      <div class="grid"><div class="card"><h2>Recommended pathway</h2><p class="sub">{safe(score.get('recommendation') or triage.get('label'))}</p><p>{safe(triage.get('summary'))}</p><p><a class="btn" href="{safe(triage.get('url', '/app'))}">{safe(triage.get('cta', 'View next step'))} →</a></p><p class="note">One recommended path first. Bigger repair plans stay available after review.</p></div>
      <div class="card"><h2>Private reference</h2><p class="note">Reference: {safe(record.get('queue_id'))}<br>Case: {safe(record.get('case_id'))}<br>Status: {safe(record.get('status'))}</p></div></div>
      <h2 style="margin-top:22px">What you gave us</h2>
      <div class="card"><p><strong>Names/search:</strong><br>{safe(preview.get('names_to_check'))}</p><p><strong>Links/search clues:</strong><br>{safe(preview.get('problem_links'))}</p><p><strong>Goal:</strong><br>{safe(preview.get('goal'))}</p></div>
      <h2 style="margin-top:22px">Private timeline</h2><div class="grid">{timeline_html}</div>
      <p class="note">FixMyNameOnline™ is operated by MadisonJade Pty Ltd. This score is an intake signal, not a guarantee of removal, ranking, de-indexing, platform action, or search result outcome.</p>
    </div>'''
    return page('Private Case Room™ — FixMyNameOnline™', body, 'Secure private reputation snapshot room for FixMyNameOnline™ Free Search Snapshot™ intake.', canonical_path='/private-case-room')


@app.route('/app')
def free_snapshot_form():
    source_page = safe(request.args.get('source') or 'app_form')
    prefill_name = safe(request.args.get('name') or '')
    body = f"""
    <div class="snapshot-shell">
      <div class="card"><span class="pill">Free private first step</span><h1>Get your Private Reputation Risk Score™</h1><p class="sub">Enter the name, business or search phrase you are worried about. We open a private case room with an initial risk score and the safest next step — without making anything public.</p>
      <div class="trust-strip"><span>Operated by MadisonJade Pty Ltd</span><span>ABN 56 661 580 936</span><span>Private intake · no public case disclosure</span></div>
      <div class="progress" aria-hidden="true"><span id="snapshot-progress"></span></div>
      <form method="post" action="/submit-snapshot" class="grid" id="snapshot-form">
        <input type="hidden" name="source_page" value="{source_page}">
        <input type="hidden" name="referrer" id="fmno-referrer" value="">
        <input type="hidden" name="landing_url" id="fmno-landing-url" value="">
        <input type="hidden" name="utm_source" id="utm_source" value=""><input type="hidden" name="utm_medium" id="utm_medium" value=""><input type="hidden" name="utm_campaign" id="utm_campaign" value=""><input type="hidden" name="utm_term" id="utm_term" value=""><input type="hidden" name="utm_content" id="utm_content" value=""><input type="hidden" name="gclid" id="gclid" value=""><input type="hidden" name="fbclid" id="fbclid" value="">
        <div><label>Name / business / search phrase</label><input name="name" required autocomplete="name" value="{prefill_name}" placeholder="Example: Jane Smith, ACME Plumbing, old business name"><div class="microcopy">This is the only search phrase required to start.</div></div>
        <div><label>Email for private result</label><input name="email" type="email" required autocomplete="email" placeholder="Where should we send the private update?"><div class="microcopy">No public action happens from this form.</div></div>
        <div class="full submit-row"><button class="btn" type="submit" id="snapshot-submit">Get Private Risk Score™ →</button><a class="btn btn2" href="/">Back</a><p class="note">Free first step. No public case disclosure. No rankings/removals guaranteed.</p></div>
        <details class="full" id="optional-details"><summary style="cursor:pointer;color:#ffb0bd;font-weight:800;margin:10px 0">Optional: add links, review details or extra names if you already have them</summary>
          <div class="grid" style="margin-top:10px">
            <div><label>Phone optional</label><input name="phone" autocomplete="tel" placeholder="Optional, for urgent/sensitive cases"></div>
            <div><label>Best describes this</label><select name="case_type"><option>Personal name / old Google results</option><option>Business name / bad search results</option><option>Fake or malicious Google reviews</option><option>Old news article or court mention</option><option>Associated name / old name / nickname</option><option>High-risk private case</option></select></div>
            <div class="full"><label>Extra names, old names or search phrases</label><textarea name="names_to_check" placeholder="Optional: old names, nicknames, business names, associated names, locations...">{prefill_name}</textarea><div class="microcopy">Leave blank if the first field is enough.</div></div>
            <div class="full"><label>Bad links, reviews, article titles, screenshots or clues if you have them</label><textarea name="problem_links" placeholder="Optional: paste URLs or write article/review/search clues..."></textarea></div>
            <div class="full"><label>What are you hoping to understand or fix?</label><textarea name="goal" placeholder="Optional: removal, review response, monitoring, better positive results, private advice..."></textarea></div>
          </div>
        </details>
      </form></div>
      <div class="card side-card"><span class="pill">What you get</span><div class="steps"><div class="step"><b>1 · Private Risk Score™</b><br><span class="sub">A first signal for how serious the search/review/name problem looks.</span></div><div class="step"><b>2 · One recommended path</b><br><span class="sub">A capped first classification, then a fixed-price DIY option only when it fits.</span></div><div class="step"><b>3 · You stay in control</b><br><span class="sub">You confirm facts and submit every external request yourself.</span></div></div><div class="recommend"><b>One free score per intake.</b><p class="note">No unlimited scans or free document generation. If there is risk, we explain the practical next step.</p></div></div>
    </div>
    <script>
    (function(){{
      const qs=new URLSearchParams(window.location.search);
      const fields=['utm_source','utm_medium','utm_campaign','utm_term','utm_content','gclid','fbclid'];
      const ref=document.getElementById('fmno-referrer'); if(ref) ref.value=document.referrer||'';
      const landing=document.getElementById('fmno-landing-url'); if(landing) landing.value=window.location.href;
      fields.forEach(k=>{{const el=document.getElementById(k); if(el) el.value=qs.get(k)||'';}});
      let started=false, step1=false;
      function fire(event,label){{try{{if(typeof gtag==='function') gtag('event',event,{{event_label:label||'',page_path:window.location.pathname}}); const body=JSON.stringify({{event,label:label||'',href:'/submit-snapshot',location:window.location.pathname+window.location.search,source:'snapshot_form'}}); if(navigator.sendBeacon) navigator.sendBeacon('/api/track-click', new Blob([body],{{type:'application/json'}})); else fetch('/api/track-click',{{method:'POST',headers:{{'Content-Type':'application/json'}},body,keepalive:true}}).catch(()=>{{}});}}catch(e){{}}}}
      const form=document.getElementById('snapshot-form');
      const progress=document.getElementById('snapshot-progress');
      function updateProgress(){{
        if(!form||!progress) return;
        const core=['name','email'];
        const coreDone=core.filter(k=>{{const el=form.elements[k]; return el && String(el.value||'').trim();}}).length;
        if(coreDone===2 && !step1){{step1=true; fire('form_step1_complete','name_email_complete');}}
        progress.style.width=Math.max(18, Math.round((coreDone/core.length)*100))+'%';
      }}
      if(form){{form.addEventListener('input',()=>{{if(!started){{started=true;fire('form_start','risk_score_form');}} updateProgress();}},{{once:false}}); form.addEventListener('submit',()=>{{const btn=document.getElementById('snapshot-submit'); if(btn){{btn.disabled=true; btn.textContent='Opening private case room...';}} fire('snapshot_submit','risk_score_form');}}); updateProgress();}}
    }})();
    </script>"""
    return page('Private Reputation Risk Score™ — FixMyNameOnline™', body)


@app.route('/submit-snapshot', methods=['POST'])
def submit_snapshot():
    base_fields = ['name', 'email', 'phone', 'case_type', 'names_to_check', 'problem_links', 'goal', 'source_page', 'referrer', 'landing_url', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid']
    data = {k: request.form.get(k, '').strip() for k in base_fields}
    attribution = attribution_from_request(request.form)
    data.update(attribution)
    if not data['name'] or not data['email']:
        return page('Missing details', '<div class="card"><h1 class="err">Missing details</h1><p>Please enter your name and email.</p><a class="btn" href="/app">Go back</a></div>'), 400
    if free_snapshot_used(data['email']):
        body = '<div class="card"><span class="pill">Free score already used</span><h1>Your one free snapshot has already been created.</h1><p class="sub">The free tier is capped at one score per email. If you have one old article or bad link, the $49 DIY workspace generates the evidence checklist, editable request and follow-up plan.</p><p><a class="btn" href="/diy-action">See the $49 DIY workspace →</a></p></div>'
        return page('Free snapshot already used — FixMyNameOnline™', body), 429

    triage = triage_snapshot(data)
    queue_item = make_queue_item('free_snapshot', data, triage)
    append_jsonl(LEADS_FILE, {**data, 'searched_name': data.get('names_to_check') or data.get('name'), 'submitted_at': utc_now(), 'triage': triage, 'queue_id': queue_item['id']})
    append_jsonl(CLICK_EVENTS_FILE, {'event': 'snapshot_submit', 'label': data.get('source_page'), 'href': '/submit-snapshot', 'location': request.path, 'source': data.get('source_category'), 'email': data.get('email'), 'searched_name': data.get('names_to_check') or data.get('name'), 'queue_id': queue_item['id'], 'referrer': data.get('referrer')})
    append_jsonl(FULFILMENT_QUEUE_FILE, queue_item)
    case_source = {**data, 'triage': triage, 'queue_id': queue_item['id']}
    case = safe_create_fulfilment_case('free-snapshot', data, case_source, 'free_snapshot')
    run_free_snapshot_pipeline(case)
    case = get_case(case.get('id')) if case and get_case else case
    report = latest_free_snapshot_report(case)
    case_room = save_case_room(queue_item, data, triage, case=case, report=report)

    send_telegram_alert('FMNO Free Search Snapshot report ready', {
        'queue_id': queue_item['id'],
        'case_id': case.get('id') if case else '',
        'name': data.get('name'),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'case_type': data.get('case_type'),
        'recommendation': (report or {}).get('recommended_package') or triage.get('label'),
        'negative_items': (report or {}).get('negative_item_count'),
        'priority': queue_item.get('priority'),
        'risk_score': case_room.get('risk_score', {}).get('score'),
        'admin_report': f"{DOMAIN}/admin/fulfilment/report/{case.get('id')}" if case else '',
        'private_case_room': case_room.get('case_room_url'),
    })
    email_status = send_snapshot_emails(data, triage, queue_item, case=case, report=report, case_room=case_room)
    record_email_alert_status('snapshot', f"FMNO lead: {triage['label']} — {data.get('name', '')}", email_status.get('internal_email_sent') if isinstance(email_status, dict) else {}, {'queue_id': queue_item['id'], 'case_id': case.get('id') if case else '', 'email': data.get('email')})
    app.logger.info('Snapshot %s email status: %s', queue_item['id'], email_status)

    body = f"""
    <div class="card"><span class="pill ok">Received</span><h1>Your Private Reputation Risk Score™ is ready.</h1>
      <p class="sub">Thanks {safe(data['name'])}. We saved your details and opened your Private Case Room™. Start with the recommended next step only if the risk looks real.</p>
      <div class="recommend"><h2>Reputation Risk Score™: {safe(case_room['risk_score']['score'])}/100 · {safe(case_room['risk_score']['label'])}</h2><p>{safe(case_room['risk_score']['summary'])}</p><p><a class="btn" href="{safe('/private-case-room/' + queue_item['id'] + '?access_token=' + case_room['access_token'])}">Open Private Case Room™ →</a></p></div>
      <div class="recommend"><h2>Recommended next step: {safe(triage['label'])}</h2><p>{safe(triage['summary'])}</p><p><a class="btn" href="{safe(triage['url'])}">{safe(triage['cta'])} →</a></p><p class="note">Early-case queue is open while intake volume is low. Start only if the recommendation fits.</p></div>
      <h2>What happens next</h2><ol><li>We look at what people may see when they search.</li><li>We identify if this looks like alerts, removal review, review defence, repair, or a private high-risk review.</li><li>If there is a paid next step, you choose it — no pressure.</li></ol>
      <p class="note">Private reference: {safe(queue_item['id'])}{'<br>Fulfilment case: ' + safe(case.get('id')) if case else ''}<br>Your private report is prepared for internal review before anything is sent externally.</p><p><a class="btn btn2" href="/">Back to site</a></p>
    </div>"""
    body += conversion_tracking_event('snapshot_submit', {'content_name': 'Free Search Snapshot', 'source_category': data.get('source_category')})
    body += conversion_tracking_event('Lead', {'content_name': 'Free Search Snapshot'})
    return page('Snapshot received — FixMyNameOnline™', body)


@app.route('/onboarding')
def onboarding_form():
    plan = request.args.get('plan', 'starter')
    plan_label = PLANS.get(plan, {}).get('name', plan.replace('-', ' ').title())
    body = f"""
    <div class="card"><span class="pill">Private onboarding</span><h1>{safe(plan_label)}</h1><p class="sub">Use this after payment or if we ask for more detail. Give us the links, names, reviews and context we need to start safely.</p>
    <form method="post" action="/submit-onboarding" class="grid"><input type="hidden" name="plan" value="{safe(plan)}">
      <div><label>Name</label><input name="name" required></div><div><label>Email</label><input type="email" name="email" required></div>
      <div><label>Phone</label><input name="phone"></div><div><label>Business / brand if any</label><input name="business"></div>
      <div class="full"><label>Names, old names, associated names, business names</label><textarea name="names"></textarea></div>
      <div class="full"><label>Links/reviews/articles/search terms</label><textarea name="links"></textarea></div>
      <div class="full"><label>What is the real story / context?</label><textarea name="context"></textarea></div>
      <div class="full"><label>Anything we must avoid saying publicly?</label><textarea name="avoid"></textarea></div>
      <div class="full"><button class="btn" type="submit">Submit private onboarding →</button></div>
    </form></div>"""
    return page('Private onboarding — FixMyNameOnline™', body)


@app.route('/submit-onboarding', methods=['POST'])
def submit_onboarding():
    fields = ['plan', 'name', 'email', 'phone', 'business', 'names', 'links', 'context', 'avoid']
    data = {k: request.form.get(k, '').strip() for k in fields}
    if not data['name'] or not data['email']:
        return jsonify({'ok': False, 'error': 'Missing name/email'}), 400

    plan_label = PLANS.get(data.get('plan'), {}).get('name', data.get('plan', 'Private onboarding'))
    triage = {'key': 'onboarding', 'label': plan_label, 'priority': 'high'}
    queue_item = make_queue_item('private_onboarding', data, triage)
    append_jsonl(ONBOARDING_FILE, {**data, 'queue_id': queue_item['id']})
    append_jsonl(FULFILMENT_QUEUE_FILE, queue_item)
    case = safe_create_fulfilment_case(data.get('plan') or 'starter', data, {**data, 'queue_id': queue_item['id']}, 'onboarding')

    send_telegram_alert('FMNO paid/private onboarding', {
        'queue_id': queue_item['id'],
        'case_id': case.get('id') if case else '',
        'plan': plan_label,
        'name': data.get('name'),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'business': data.get('business'),
    })
    email_status = send_onboarding_emails(data, queue_item)
    record_email_alert_status('onboarding', f"FMNO onboarding: {plan_label} — {data.get('name', '')}", email_status.get('internal_email_sent') if isinstance(email_status, dict) else {}, {'queue_id': queue_item['id'], 'plan': data.get('plan'), 'email': data.get('email')})
    app.logger.info('Onboarding %s email status: %s', queue_item['id'], email_status)

    body = f"""<div class="card"><span class="pill ok">Received</span><h1>Private onboarding received.</h1><p class="sub">Your details are saved. We’ll use this to begin the correct review/repair path.</p><p class="note">Private reference: {safe(queue_item['id'])}{'<br>Fulfilment case: ' + safe(case.get('id')) if case else ''}</p><a class="btn" href="/">Back to site</a></div>"""
    return page('Onboarding received — FixMyNameOnline™', body)


def verify_diy_checkout(session_id, checkout_token=''):
    """Verify Stripe directly, or use the secret post-payment token held only by Stripe."""
    session_id = (session_id or '').strip()
    checkout_token = (checkout_token or '').strip()
    if app.testing and session_id == 'cs_test_fmno_diy_paid':
        return {'id': session_id, 'payment_status': 'paid', 'customer_details': {'email': 'test@example.com'}}
    if session_id.startswith('cs_live_') and checkout_token and hmac.compare_digest(hashlib.sha256(checkout_token.encode()).hexdigest(), DIY_CHECKOUT_TOKEN_SHA256):
        return {'id': session_id, 'payment_status': 'paid', 'customer_details': {}}
    if not session_id or not stripe.api_key:
        return None
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return session if getattr(session, 'payment_status', '') == 'paid' else None
    except Exception as exc:
        app.logger.warning('DIY checkout verification failed: %s', exc)
        return None


def diy_access_token(session_id):
    return hmac.new(approval_secret().encode('utf-8'), f'diy-action:{session_id}'.encode('utf-8'), hashlib.sha256).hexdigest()


@app.route('/diy-action')
def diy_action_sales():
    body = '''<div class="card"><span class="pill">Fixed-price DIY · one old article or bad link</span><h1>Prepare the action yourself — without guessing.</h1>
    <p class="sub">FMNO organises one target URL, the evidence checklist, an editable publisher request, the official next route and a follow-up record. You confirm the facts and submit every request yourself.</p>
    <div class="recommend"><h2>DIY Reputation Action Workspace™ — US$49 once</h2><ul><li>One old article or bad-link URL</li><li>Structured evidence checklist</li><li>Editable correction, removal, anonymisation or noindex request</li><li>Official Google outdated-content route where relevant</li><li>Submission reference and 30-day follow-up plan</li></ul><p><a class="btn" href="/checkout/diy-action?source=diy_action_page">Open my $49 workspace →</a></p><p class="note">No subscription. FMNO does not submit the request, act as your representative, provide legal advice, or guarantee removal.</p></div>
    <h2>Exactly how it works</h2><ol><li>Pay the fixed one-time price.</li><li>Add one URL and confirm the facts.</li><li>Complete the evidence checklist.</li><li>FMNO prepares an editable request.</li><li>You review, copy and submit it.</li><li>Keep the reference and follow the 30-day plan.</li></ol>
    <div class="grid"><div class="card"><h2>FMNO does</h2><p class="sub">Structure the issue, organise evidence, generate the request and show the next route.</p></div><div class="card"><h2>You do</h2><p class="sub">Confirm accuracy, provide evidence, approve wording and submit the action yourself.</p></div></div>
    <p class="note">Not suitable for emergencies, threats, minors, active proceedings, complex defamation disputes or false evidence. Use appropriate safety or independent professional channels.</p></div>'''
    return page('DIY Reputation Action Workspace™ — $49 | FixMyNameOnline™', body, 'A fixed-price DIY old article and bad-link action workspace with evidence checklist, prepared request, official route and follow-up plan.', canonical_path='/diy-action')


@app.route('/diy-action/start')
def diy_action_start():
    session_id = (request.args.get('session_id') or '').strip()
    checkout_token = (request.args.get('checkout_token') or '').strip()
    paid = verify_diy_checkout(session_id, checkout_token)
    if not paid:
        return page('Payment verification required — FixMyNameOnline™', '<div class="card"><h1>Paid workspace link required.</h1><p class="sub">The DIY workspace opens after a verified $49 Stripe payment.</p><p><a class="btn" href="/diy-action">View the DIY workspace</a></p></div>'), 402
    token = diy_access_token(session_id)
    details = paid.get('customer_details') if isinstance(paid, dict) else getattr(paid, 'customer_details', {})
    email = (details or {}).get('email', '') if isinstance(details, dict) else getattr(details, 'email', '')
    body = f'''<div class="card"><span class="pill ok">Payment verified · DIY workspace unlocked</span><h1>Build your old article or bad-link action.</h1><p class="sub">Complete the facts below. FMNO creates an editable request and checklist. You remain responsible for accuracy and submission.</p>
    <form method="post" action="/diy-action/generate" class="grid"><input type="hidden" name="session_id" value="{safe(session_id)}"><input type="hidden" name="checkout_token" value="{safe(checkout_token)}"><input type="hidden" name="access_token" value="{safe(token)}">
    <div><label>Your name</label><input name="name" required></div><div><label>Email</label><input name="email" type="email" required value="{safe(email)}"></div>
    <div class="full"><label>One target URL</label><input name="target_url" type="url" required placeholder="https://publisher.example/article"></div>
    <div><label>What is the problem?</label><select name="issue_type" required><option value="outdated">Outdated/current picture missing</option><option value="inaccurate">Inaccurate or missing context</option><option value="privacy">Contains personal information</option><option value="wrong-person">Wrong person/name confusion</option></select></div>
    <div><label>Requested outcome</label><select name="requested_outcome" required><option value="correct">Correct or update it</option><option value="anonymise">Anonymise my details</option><option value="noindex">Remove it from search discovery</option><option value="remove">Remove the page</option></select></div>
    <div class="full"><label>What is factually wrong, outdated or harmful?</label><textarea name="problem_summary" required></textarea></div>
    <div class="full"><label>Evidence you have</label><textarea name="evidence_summary" required placeholder="Dates, correct facts, documents or prior correspondence. Facts only."></textarea></div>
    <div class="full"><label>Correct/current information</label><textarea name="correct_information" required></textarea></div>
    <div class="full"><label><input style="width:auto" type="checkbox" name="truth_confirmed" value="yes" required> I confirm this is accurate, will review the wording, and will submit any request myself.</label></div>
    <div class="full"><button class="btn" type="submit">Generate my DIY action pack →</button><p class="note">A documentation tool, not legal advice or representation.</p></div></form></div>'''
    return page('Build your DIY action — FixMyNameOnline™', body, canonical_path='/diy-action/start')


@app.route('/diy-action/generate', methods=['POST'])
def diy_action_generate():
    fields = ['session_id', 'checkout_token', 'access_token', 'name', 'email', 'target_url', 'issue_type', 'requested_outcome', 'problem_summary', 'evidence_summary', 'correct_information', 'truth_confirmed']
    data = {k: request.form.get(k, '').strip() for k in fields}
    if not verify_diy_checkout(data.get('session_id') or '', data.get('checkout_token') or '') or not hmac.compare_digest(data.get('access_token', ''), diy_access_token(data.get('session_id', ''))):
        return page('Workspace access denied', '<div class="card"><h1 class="err">Paid workspace verification failed.</h1></div>'), 403
    if not all(data.get(k) for k in ['name', 'email', 'target_url', 'problem_summary', 'evidence_summary', 'correct_information']) or data.get('truth_confirmed') != 'yes':
        return page('Missing evidence', '<div class="card"><h1 class="err">Complete every required field.</h1></div>'), 400
    parsed = urlparse(data['target_url'])
    if parsed.scheme not in ['http', 'https'] or not parsed.netloc:
        return page('Invalid URL', '<div class="card"><h1 class="err">Enter a complete http/https target URL.</h1></div>'), 400
    outcomes = {'correct': 'correct or update the page', 'anonymise': 'anonymise my name or identifying details', 'noindex': 'apply noindex or otherwise remove the page from search discovery', 'remove': 'remove the page'}
    issues = {'outdated': 'outdated information', 'inaccurate': 'inaccurate or incomplete information', 'privacy': 'personal information', 'wrong-person': 'wrong-person or name-confusion information'}
    action_id = 'FMNO-DIY-' + hashlib.sha256((data['session_id'] + data['target_url']).encode()).hexdigest()[:12].upper()
    draft = f'''Subject: Request to {outcomes.get(data['requested_outcome'], 'review the page')} — {data['target_url']}\n\nHello,\n\nI am writing about this page: {data['target_url']}\n\nI am the person affected by the {issues.get(data['issue_type'], 'information')} on this page. I am asking you to {outcomes.get(data['requested_outcome'], 'review it')}.\n\nWhy I am requesting review:\n{data['problem_summary']}\n\nCorrect or current information:\n{data['correct_information']}\n\nEvidence available:\n{data['evidence_summary']}\n\nPlease confirm receipt and tell me if you require identity verification or further evidence through a secure channel. I would appreciate a written response explaining the decision.\n\nRegards,\n{data['name']}'''
    record = {**data, 'action_id': action_id, 'status': 'request_generated', 'draft': draft, 'follow_up_after_days': 14, 'created_at': utc_now()}
    record.pop('access_token', None)
    record.pop('checkout_token', None)
    append_jsonl(DIY_ACTIONS_FILE, record)
    append_jsonl(CLICK_EVENTS_FILE, {'event': 'diy_action_generated', 'label': data.get('issue_type'), 'href': '/diy-action/generate', 'location': request.path, 'action_id': action_id})
    body = f'''<div class="card"><span class="pill ok">DIY action pack generated</span><h1>Your request is ready.</h1><p class="sub">Review every word. Edit anything inaccurate. You—not FMNO—decide whether and where to submit it.</p>
    <div class="recommend"><h2>Evidence checklist</h2><ul><li>Save screenshots of the target page and Google result.</li><li>Save the exact URL and visible date.</li><li>Keep documents supporting every correction.</li><li>Find the publisher’s official corrections, privacy or contact page.</li><li>Only send identity documents through a secure official route.</li></ul></div>
    <h2>Editable request</h2><textarea style="min-height:520px">{safe(draft)}</textarea>
    <p><a class="btn" href="{safe(data['target_url'])}" target="_blank" rel="noopener nofollow">Open target page</a> <a class="btn btn2" href="https://search.google.com/search-console/remove-outdated-content" target="_blank" rel="noopener nofollow">Official Google outdated-content tool</a></p>
    <div class="grid"><div class="card"><h2>Submit yourself</h2><p class="sub">Use the publisher’s official channel first where appropriate. Copy the reviewed request and retain confirmation.</p></div><div class="card"><h2>Follow up in 14 days</h2><p class="sub">If there is no substantive response, send one calm follow-up quoting your date and reference.</p></div></div>
    <div class="recommend"><h2>Submission record</h2><p>Action ID: <strong>{safe(action_id)}</strong></p><p>30-day plan: submit → retain proof → follow up once after 14 days → record the outcome.</p></div><p class="note">No outcome is guaranteed. Publishers, platforms and search engines decide.</p></div>'''
    return page('Your DIY Reputation Action Pack — FixMyNameOnline™', body, canonical_path='/diy-action/result')


@app.route('/checkout/<tier>')
def checkout(tier):
    if tier == 'free':
        return redirect('/app')
    if tier == 'concierge':
        return redirect('/onboarding?plan=concierge')
    if tier in {'removal-review', 'review-defence', 'starter', 'pro', 'premium'}:
        # Legacy human/managed offers are intentionally retired: never take payment
        # for fulfilment that is not assigned to an accountable operator.
        return redirect('/diy-action?legacy_offer_retired=1', code=302)
    if tier not in PLANS:
        return jsonify({'error': 'Invalid plan'}), 400
    plan = PLANS[tier]
    attribution = attribution_from_request(request.args)
    append_jsonl(CLICK_EVENTS_FILE, {'event': 'checkout_click', 'label': tier, 'href': request.url, 'location': request.path, 'source': attribution.get('source_category'), 'plan': plan.get('name'), 'price': plan.get('price'), 'referrer': attribution.get('referrer')})
    payment_link = plan.get('payment_link')
    if payment_link:
        append_jsonl(CLICK_EVENTS_FILE, {'event': 'stripe_redirect', 'label': tier, 'href': payment_link, 'location': request.path, 'source': attribution.get('source_category'), 'plan': plan.get('name'), 'price': plan.get('price'), 'referrer': attribution.get('referrer')})
        if os.environ.get('FMNO_EMAIL_CHECKOUT_INTENT', '0') == '1':
            send_checkout_intent_alert(tier, plan, attribution, payment_link)
        return redirect(payment_link, code=302)
    if not stripe.api_key:
        return page('Checkout temporarily unavailable — FixMyNameOnline™', '<div class="card"><span class="pill">Checkout migration</span><h1>Checkout is temporarily unavailable.</h1><p class="sub">FMNO billing is being moved to its own isolated payment account. No payment has been taken.</p><p><a class="btn" href="/diy-action">Return to the DIY workspace</a></p></div>'), 503
    price_id = os.environ.get(plan['env'])
    if not price_id:
        return jsonify({'error': f'Missing Stripe price env var: {plan["env"]}'}), 500
    try:
        session = stripe.checkout.Session.create(
            mode=plan['mode'],
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=f'{DOMAIN}/success.html?tier={tier}&session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{DOMAIN}/cancel.html',
            allow_promotion_codes=True,
            metadata={'tier': tier, 'plan_name': plan['name']},
            subscription_data={'metadata': {'tier': tier, 'plan_name': plan['name']}} if plan['mode'] == 'subscription' else None,
        )
        return redirect(session.url, code=302)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/success.html')
def success():
    tier = request.args.get('tier', 'unknown')
    plan_name = PLANS.get(tier, {}).get('name', tier.replace('-', ' ').title())
    body = f"""<div class="card"><span class="pill ok">Payment received</span><h1>Welcome to {safe(plan_name)}</h1><p class="sub">Your payment has been processed. The important next step is private onboarding so we have the names, links, reviews, and context needed to handle this safely.</p><ol><li>Complete the private onboarding form.</li><li>Paste the links/reviews/search terms you want reviewed.</li><li>Tell us what is true, outdated, unfair, or sensitive.</li></ol><p><a class="btn" href="/onboarding?plan={safe(tier)}">Complete private onboarding →</a></p><p class="note">No removal, ranking, or platform outcome is guaranteed. We use careful, documented reputation repair pathways.</p></div>"""
    return page('Welcome — FixMyNameOnline™', body)


@app.route('/cancel.html')
def cancel():
    return page('Checkout cancelled — FixMyNameOnline™', '<div class="card"><h1>Checkout cancelled</h1><p class="sub">No worries — your payment was not processed. You can still start with the free Search Snapshot™.</p><a class="btn" href="/app">Start Free Search Snapshot™</a> <a class="btn btn2" href="/">Back</a></div>')


@app.route('/contact')
def contact():
    return page('Contact — FixMyNameOnline™', '<div class="card"><h1>Contact FixMyNameOnline™</h1><p>Email: <a href="mailto:admin@fixmynameonline.com">admin@fixmynameonline.com</a></p><p><a class="btn" href="/questions">Ask a private case question →</a></p><p class="sub">Private reputation repair operated by MadisonJade Pty Ltd.</p></div>')


@app.route('/questions')
def question_form():
    ref = request.args.get('ref', '')
    body = f"""
    <div class="card"><span class="pill">Private concierge</span><h1>Ask a private question</h1><p class="sub">Use this for process questions, missing details, approval questions, or anything you want us to review privately. This is not legal advice and no public action is taken from this form alone.</p>
    <form method="post" action="/submit-question" class="grid">
      <div><label>Your name</label><input name="name" required autocomplete="name"></div>
      <div><label>Email</label><input name="email" type="email" required autocomplete="email"></div>
      <div class="full"><label>Private reference / case ID if you have it</label><input name="reference" value="{safe(ref)}" placeholder="Example: FMNO-... or FMNO-CASE-..."></div>
      <div class="full"><label>Your question</label><textarea name="question" required placeholder="Write your question. If it involves a link, review, article, screenshot or sensitive detail, include enough context for a private review."></textarea></div>
      <div class="full"><button class="btn" type="submit">Send private question →</button> <a class="btn btn2" href="/">Back</a><p class="note">We will respond privately. The form does not publish, submit, remove, rank, or change anything publicly.</p></div>
    </form></div>"""
    return page('Ask a private question — FixMyNameOnline™', body, 'Ask a private FixMyNameOnline™ case or process question. Private concierge intake; no public action or legal advice.')


def resolve_question_case_id(reference, email):
    ref = (reference or '').strip()
    email_l = (email or '').strip().lower()
    if get_case and ref and get_case(ref):
        return ref
    if not list_cases:
        return None
    try:
        for case in list_cases(limit=1000):
            source = case.get('source') or {}
            customer = case.get('customer') or {}
            candidates = {case.get('id'), source.get('queue_id'), source.get('id')}
            if ref and ref in candidates:
                return case.get('id')
            if email_l and (customer.get('email') or '').strip().lower() == email_l and not ref:
                return case.get('id')
    except Exception as exc:
        app.logger.warning('Question case lookup failed: %s', exc)
    return None


def send_question_emails(data, queue_item, case_id=None):
    customer_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#111;line-height:1.55\">
      <h1>We received your private question</h1>
      <p>Hi {safe(data.get('name'))},</p>
      <p>Thank you — we received your question. We will review it privately and reply by email before any public action is taken.</p>
      <p>If the question involves legal issues, media allegations, court matters, criminal allegations, defamation, reviews, platform reports or removals, we may need to review it manually before giving a process answer.</p>
      <p><strong>Your reference:</strong> {safe(queue_item['id'])}</p>
      <p style=\"font-size:12px;color:#666\">FixMyNameOnline™ · MadisonJade Pty Ltd<br>No ranking, removal, review-removal, de-indexing or platform outcome is guaranteed. We do not provide legal advice.</p>
    </div>
    """
    internal_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111\">
      <h1>New FMNO private question</h1>
      <p><strong>Question ID:</strong> {safe(queue_item['id'])}</p>
      <p><strong>Matched case:</strong> {safe(case_id or '')}</p>
      <pre style=\"background:#f5f5f5;padding:16px;border-radius:10px;white-space:pre-wrap\">{safe(json.dumps(data, indent=2, ensure_ascii=False))}</pre>
    </div>
    """
    return {
        'customer_email_sent': send_brevo_email(data.get('email'), data.get('name'), 'Private question received — FixMyNameOnline™', customer_html),
        'internal_email_sent': send_internal_alert_email(f"FMNO question — {data.get('name', '')}", internal_html),
    }


@app.route('/submit-question', methods=['POST'])
def submit_question():
    fields = ['name', 'email', 'reference', 'question']
    data = {k: request.form.get(k, '').strip() for k in fields}
    if not data['name'] or not data['email'] or not data['question']:
        return page('Missing details', '<div class="card"><h1 class="err">Missing details</h1><p>Please enter your name, email and question.</p><a class="btn" href="/questions">Go back</a></div>'), 400

    triage = {'key': 'client_question', 'label': 'Private client question', 'priority': 'high'}
    queue_item = make_queue_item('client_question', data, triage)
    case_id = resolve_question_case_id(data.get('reference'), data.get('email'))
    record = {**data, 'queue_id': queue_item['id'], 'matched_case_id': case_id}
    append_jsonl(QUESTIONS_FILE, record)
    append_jsonl(FULFILMENT_QUEUE_FILE, queue_item)
    if case_id and add_case_note:
        add_case_note(case_id, f"Client private question ({queue_item['id']}): {data.get('question')}", data.get('name') or 'Client', 'client_question')

    send_telegram_alert('FMNO private question received', {
        'question_id': queue_item['id'],
        'matched_case_id': case_id or '',
        'reference': data.get('reference'),
        'name': data.get('name'),
        'email': data.get('email'),
        'question': data.get('question')[:700],
    })
    email_status = send_question_emails(data, queue_item, case_id=case_id)
    record_email_alert_status('question', f"FMNO question — {data.get('name', '')}", email_status.get('internal_email_sent') if isinstance(email_status, dict) else {}, {'queue_id': queue_item['id'], 'matched_case_id': case_id, 'email': data.get('email')})
    app.logger.info('Question %s email status: %s', queue_item['id'], email_status)

    body = f"""<div class="card"><span class="pill ok">Received</span><h1>Your private question is in.</h1><p class="sub">Thanks {safe(data['name'])}. We saved your question and will respond privately by email.</p><h2>What happens next</h2><ol><li>We match the question to your case/reference where possible.</li><li>We review it privately, especially if it involves sensitive, legal, review, platform or removal issues.</li><li>We reply before any public action is taken.</li></ol><p class="note">Private question reference: {safe(queue_item['id'])}{'<br>Matched case: ' + safe(case_id) if case_id else ''}<br>No legal advice or outcome guarantee is provided through this form.</p><a class="btn" href="/">Back to site</a></div>"""
    body += conversion_tracking_event('Lead', {'content_name': 'Private Question'})
    return page('Question received — FixMyNameOnline™', body)


@app.route('/privacy')
def privacy():
    return page('Privacy Policy — FixMyNameOnline™', '<div class="card"><h1>Privacy Policy</h1><p class="sub">Draft launch policy: information submitted through FixMyNameOnline™ is used to assess and deliver private reputation services, respond to enquiries, process payments, and maintain case records. We do not publicly disclose client cases without consent.</p><p>Contact: admin@fixmynameonline.com</p></div>')


@app.route('/terms')
def terms():
    return page('Terms — FixMyNameOnline™', '<div class="card"><h1>Terms & Disclaimer</h1><p class="sub">FixMyNameOnline™ provides reputation review, monitoring, content, documentation, and platform-request support. Search engines, publishers, platforms, and courts make their own decisions. We do not guarantee removals, review removals, rankings, de-indexing, or specific outcomes. Legal advice must be obtained from a qualified lawyer.</p></div>')



@app.route('/approval/<case_id>/<task_id>')
def client_approval_page(case_id, task_id):
    token = request.args.get('approval_token', '')
    if not valid_approval_token(case_id, task_id, token):
        return page('Approval link invalid', '<div class="card"><h1 class="err">Invalid approval link</h1><p>This private approval link is invalid or incomplete.</p></div>'), 401
    case = get_case(case_id) if get_case else None
    if not case:
        return page('Case not found', '<div class="card"><h1 class="err">Case not found</h1></div>'), 404
    task_obj = get_task_from_case(case, task_id)
    if not task_obj:
        return page('Approval item not found', '<div class="card"><h1 class="err">Approval item not found</h1></div>'), 404
    if not task_obj.get('requires_client_approval'):
        return page('Approval not required', '<div class="card"><h1>Approval not required</h1><p>This item is not marked for client approval.</p></div>'), 400
    outputs = latest_case_outputs(case, limit=10)
    output_blocks = []
    for item in outputs:
        output = item.get('output', {})
        # Do not expose internal source payload wholesale. Show draft/report-ish fields and safe summary.
        visible = {
            'task': f"{item.get('task_id')} — {item.get('task_title')}",
            'agent': item.get('agent'),
            'generated_at': item.get('generated_at'),
            'type': output.get('type'),
            'draft': output.get('draft'),
            'client_summary': output.get('client_summary'),
            'recommended_outputs': output.get('recommended_outputs'),
            'asset_plan': output.get('asset_plan'),
            'policy_indicators_to_check': output.get('policy_indicators_to_check'),
            'approval_required': output.get('approval_required'),
            'gate_result': output.get('gate_result'),
        }
        visible = {k: v for k, v in visible.items() if v not in [None, '', []]}
        output_blocks.append(f"<details open><summary><strong>{safe(visible.get('task'))}</strong></summary><pre class='mono'>{safe(json.dumps(visible, indent=2, ensure_ascii=False))}</pre></details>")
    body = f"""
    <div class="card"><span class="pill">Private client approval</span><h1>{safe(case.get('plan_name'))}</h1>
      <p class="sub">Please review this prepared item. Nothing public should be published, sent, or submitted unless you approve it.</p>
      <p><strong>Case:</strong> <span class="note">{safe(case_id)}</span><br><strong>Approval item:</strong> {safe(task_obj.get('title'))}</p>
      <div class="recommend"><h2>Prepared material</h2>{''.join(output_blocks) if output_blocks else '<p class="sub">No draft outputs are attached yet. Please ask us to prepare the material first.</p>'}</div>
      <form method="post" action="/approval/{safe(case_id)}/{safe(task_id)}" class="grid"><input type="hidden" name="approval_token" value="{safe(token)}">
        <div class="full"><label>Optional note</label><textarea name="client_note" placeholder="Any changes, concerns, or approval notes..."></textarea></div>
        <div class="full"><button class="btn" name="decision" value="approve">Approve this item →</button> <button class="btn btn2" name="decision" value="reject">Request changes / do not approve</button></div>
      </form>
      <p class="note">No removals, rankings, platform actions, or search outcomes are guaranteed.</p>
    </div>
    """
    return page('Client approval — FixMyNameOnline™', body)


@app.route('/approval/<case_id>/<task_id>', methods=['POST'])
def client_approval_submit(case_id, task_id):
    token = request.form.get('approval_token', '')
    if not valid_approval_token(case_id, task_id, token):
        return page('Approval link invalid', '<div class="card"><h1 class="err">Invalid approval link</h1></div>'), 401
    case = get_case(case_id) if get_case else None
    task_obj = get_task_from_case(case, task_id) if case else None
    if not case or not task_obj:
        return page('Approval item not found', '<div class="card"><h1 class="err">Approval item not found</h1></div>'), 404
    decision = request.form.get('decision')
    client_note = request.form.get('client_note', '').strip()
    if decision == 'approve':
        approve_task(case_id, task_id, 'ClientApproval', client_note or 'Client approved via private approval portal.')
        add_case_note(case_id, client_note or f'Client approved {task_id}.', 'ClientApproval', 'client_approval')
        return page('Approved — FixMyNameOnline™', '<div class="card"><span class="pill ok">Approved</span><h1>Thank you. This item has been approved.</h1><p class="sub">We recorded your approval and will continue through the private QC-gated process.</p></div>')
    update_task_status(case_id, task_id, 'blocked', client_note or 'Client requested changes via approval portal.', 'ClientApproval')
    add_case_note(case_id, client_note or f'Client requested changes for {task_id}.', 'ClientApproval', 'client_rejection')
    return page('Changes requested — FixMyNameOnline™', '<div class="card"><span class="pill err">Changes requested</span><h1>Thank you. We recorded your request.</h1><p class="sub">This item is blocked until the requested changes are reviewed.</p></div>')

@app.route('/webhook', methods=['POST'])
def webhook():
    if not STRIPE_WEBHOOK_SECRET:
        return 'Webhook not configured', 500
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        tier = infer_paid_tier_from_session(session)
        plan_name = PLANS.get(tier, {}).get('name', tier)
        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email', '')
        case = safe_create_fulfilment_case(tier, {'email': customer_email}, {'stripe_session_id': session.get('id'), 'tier': tier, 'plan_name': plan_name}, 'stripe_checkout')
        append_jsonl(CLICK_EVENTS_FILE, {'event': 'purchase', 'label': tier, 'href': '/webhook', 'location': '/webhook', 'source': 'stripe', 'customer_email': customer_email, 'stripe_session_id': session.get('id'), 'case_id': case.get('id') if case else '', 'amount_total': session.get('amount_total'), 'currency': session.get('currency')})
        send_telegram_alert('FMNO checkout completed', {'customer_email': customer_email, 'tier': tier, 'session': session.get('id'), 'case_id': case.get('id') if case else ''})
        send_paid_customer_alert(tier, plan_name, customer_email, session, case=case)
    return '', 200



def status_badge(status):
    colors = {
        'new': '#9aa2b6',
        'intake_ready': '#6aa9ff',
        'mapped': '#6aa9ff',
        'evidence_ready': '#6aa9ff',
        'drafting': '#d7a328',
        'qc_pending': '#d7a328',
        'client_approval_pending': '#d7a328',
        'approved_for_execution': '#31d07a',
        'executing': '#31d07a',
        'monitoring': '#31d07a',
        'complete': '#31d07a',
        'blocked': '#ff6f85',
        'cancelled': '#9aa2b6',
        'ready': '#6aa9ff',
        'pending': '#9aa2b6',
        'in_progress': '#d7a328',
        'approved': '#31d07a',
        'done': '#31d07a',
    }
    color = colors.get(status, '#9aa2b6')
    return f'<span style="display:inline-block;border:1px solid {color};color:{color};border-radius:999px;padding:4px 8px;font-size:12px;font-weight:800">{safe(status)}</span>'


def dashboard_page(title, body):
    css = """
    :root{--dark:#070911;--panel:#111521;--panel2:#171d2b;--red:#d91f3d;--muted:#9aa2b6;--ok:#31d07a;--warn:#d7a328;--bad:#ff6f85;--line:rgba(255,255,255,.11)}
    *{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 10% 0,rgba(217,31,61,.18),transparent 25%),var(--dark);color:white;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;padding:22px;line-height:1.45}
    a{color:#ff4d66;text-decoration:none}.wrap{max-width:1280px;margin:0 auto}.top{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:20px}.brand{font-weight:950;letter-spacing:.12em;color:var(--red)}
    .grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{background:rgba(255,255,255,.055);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 20px 60px rgba(0,0,0,.20)}
    .casegrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:14px}.muted{color:var(--muted)}.small{font-size:12px}.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;word-break:break-all}.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.btn,button{background:linear-gradient(135deg,var(--red),#a81229);border:0;color:white;border-radius:10px;padding:9px 11px;font-weight:800;cursor:pointer}.btn2{background:transparent;border:1px solid var(--line)}
    input,select,textarea{background:#0c1019;color:white;border:1px solid var(--line);border-radius:10px;padding:9px;width:100%;font:inherit}textarea{min-height:82px}.task{border-left:3px solid var(--line);padding:12px;margin:10px 0;background:rgba(255,255,255,.035);border-radius:12px}.danger{border-color:rgba(255,111,133,.5);background:rgba(255,111,133,.08)}.okbox{border-color:rgba(49,208,122,.5);background:rgba(49,208,122,.08)}
    @media(max-width:850px){.grid{grid-template-columns:1fr 1fr}.top{display:block}}
    """
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{safe(title)}</title><style>{css}</style></head><body><div class='wrap'><div class='top'><div><div class='brand'>FMNO™ FULFILMENT COMMAND</div><div class='muted small'>MadisonJade private operations · QC-gated execution</div></div><div class='row'><a class='btn btn2' href='/'>Public site</a></div></div>{body}</div></body></html>"""


def token_qs():
    token = request.args.get('token') or request.form.get('token') or ''
    return f'token={safe(token)}'


def case_counts(cases):
    counts = {'total': len(cases), 'blocked': 0, 'qc_pending': 0, 'client_approval': 0, 'ready': 0}
    for case in cases:
        if case.get('status') == 'blocked':
            counts['blocked'] += 1
        for task_obj in case.get('tasks', []):
            if task_obj.get('status') == 'qc_pending':
                counts['qc_pending'] += 1
            if task_obj.get('requires_client_approval') and task_obj.get('status') not in ['approved', 'done', 'cancelled']:
                counts['client_approval'] += 1
            if task_obj.get('status') == 'ready':
                counts['ready'] += 1
    return counts


@app.route('/admin/fulfilment')
def fulfilment_dashboard():
    if not admin_authorized():
        body = """
        <div class='card' style='max-width:560px;margin:80px auto'><h1>Admin token required</h1><p class='muted'>Enter the FMNO admin token to open the fulfilment dashboard.</p>
        <form method='get'><input name='token' type='password' placeholder='FMNO_ADMIN_TOKEN'><p><button>Open dashboard</button></p></form></div>
        """
        return dashboard_page('FMNO Fulfilment Login', body), 401
    if not list_cases:
        return dashboard_page('FMNO Fulfilment', "<div class='card'><h1>Fulfilment engine unavailable</h1></div>"), 500
    status = request.args.get('status') or ''
    plan = request.args.get('plan') or ''
    cases = list_cases(status=status or None, plan=plan or None, limit=100)
    all_cases = list_cases(limit=500)
    counts = case_counts(all_cases)
    cards = []
    for case in cases:
        ready = [t for t in case.get('tasks', []) if t.get('status') in ['ready', 'in_progress', 'qc_pending', 'blocked']]
        flags = ''.join([f"<span style='color:#ff6f85'>⚠ {safe(f)}</span> " for f in case.get('risk_flags', [])])
        cards.append(f"""
        <div class='card'>
          <div class='row'>{status_badge(case.get('status'))}<span class='muted small'>{safe(case.get('priority'))}</span></div>
          <h2 style='margin-bottom:4px'>{safe(case.get('plan_name'))}</h2>
          <div class='muted'>{safe(case.get('customer', {}).get('name') or 'Unnamed')} · {safe(case.get('customer', {}).get('email'))}</div>
          <div class='mono' style='margin-top:8px'>{safe(case.get('id'))}</div>
          <p class='small muted'>{safe(case.get('description'))}</p>
          <div>{flags}</div>
          <p><strong>{len(ready)}</strong> active/ready task(s) · <strong>{len(case.get('tasks', []))}</strong> total</p>
          <a class='btn' href='/admin/fulfilment/case/{safe(case.get('id'))}?{token_qs()}'>Open case →</a>
        </div>
        """)
    body = f"""
    <div class='grid'>
      <div class='card'><div class='muted small'>Total cases</div><h1>{counts['total']}</h1></div>
      <div class='card'><div class='muted small'>Ready tasks</div><h1>{counts['ready']}</h1></div>
      <div class='card'><div class='muted small'>QC pending</div><h1>{counts['qc_pending']}</h1></div>
      <div class='card'><div class='muted small'>Blocked</div><h1>{counts['blocked']}</h1></div>
    </div>
    <div class='card' style='margin:16px 0'><h2>Backup / export</h2><p class='muted small'>Render free storage is not a long-term database. Export cases regularly until we add Postgres.</p><div class='row'><a class='btn' href='/admin/fulfilment/export/cases.json?{token_qs()}'>Download all cases JSON</a><a class='btn btn2' href='/admin/fulfilment/export/backup.json?{token_qs()}'>Download full backup JSON</a><a class='btn btn2' href='/admin/fulfilment/export/questions.json?{token_qs()}'>Download questions JSON</a></div></div>
    <div class='card' style='margin:16px 0'><form method='get' class='row'><input type='hidden' name='token' value='{safe(request.args.get('token'))}'><select name='status'><option value=''>All statuses</option><option>blocked</option><option>intake_ready</option><option>executing</option><option>qc_pending</option><option>complete</option></select><select name='plan'><option value=''>All plans</option><option>free-snapshot</option><option>sentinel</option><option>removal-review</option><option>review-defence</option><option>starter</option><option>pro</option><option>premium</option><option>concierge</option></select><button>Filter</button><a class='btn btn2' href='/admin/fulfilment?{token_qs()}'>Reset</a></form></div>
    <div class='card' style='margin:16px 0'><h2>QC text safety check</h2><form method='post' action='/admin/fulfilment/check-text'><input type='hidden' name='token' value='{safe(request.args.get('token'))}'><textarea name='text' placeholder='Paste draft public copy, responses, articles, or platform request text here before approval...'></textarea><p><button>Check draft safety</button></p></form></div>
    <div class='casegrid'>{''.join(cards) if cards else "<div class='card'><h2>No cases yet</h2><p class='muted'>Paid onboarding or Stripe checkout will create cases automatically.</p></div>"}</div>
    """
    return dashboard_page('FMNO Fulfilment Dashboard', body)


@app.route('/admin/fulfilment/case/<case_id>')
def fulfilment_case_dashboard(case_id):
    if not admin_authorized():
        return redirect('/admin/fulfilment')
    case = get_case(case_id) if get_case else None
    if not case:
        return dashboard_page('Case not found', f"<div class='card'><h1>Case not found</h1><a href='/admin/fulfilment?{token_qs()}'>Back</a></div>"), 404
    active = next_actions(case_id) if next_actions else []
    task_html = []
    for task_obj in case.get('tasks', []):
        sensitive = task_obj.get('execution_sensitive') or task_obj.get('requires_client_approval')
        css = 'task danger' if task_obj.get('status') == 'blocked' or sensitive else 'task'
        gates = ' '.join([f"<span class='small' style='border:1px solid rgba(255,255,255,.15);border-radius:999px;padding:3px 7px'>{safe(g)}</span>" for g in task_obj.get('gates', [])])
        notes = task_obj.get('qc', {}).get('notes', [])[-2:]
        notes_html = ''.join([f"<div class='small muted'>• {safe(n.get('note'))} — {safe(n.get('author'))}</div>" for n in notes])
        latest_output = list((task_obj.get('outputs') or {}).values())[-1] if (task_obj.get('outputs') or {}) else None
        output_html = f"<details style='margin-top:8px'><summary class='small'>Latest agent output</summary><pre class='mono'>{safe(json.dumps(latest_output, indent=2, ensure_ascii=False))}</pre></details>" if latest_output else ""
        approval_link_html = f"<div style='margin-top:8px' class='small'><strong>Client approval link:</strong> <a href='{approval_url(case_id, task_obj.get('id'))}' target='_blank'>open approval portal</a><div class='mono'>{approval_url(case_id, task_obj.get('id'))}</div></div>" if task_obj.get('requires_client_approval') else ""
        actions = f"""
        <form method='post' action='/admin/fulfilment/action' class='row'>
          <input type='hidden' name='token' value='{safe(request.args.get('token'))}'><input type='hidden' name='case_id' value='{safe(case_id)}'><input type='hidden' name='task_id' value='{safe(task_obj.get('id'))}'>
          <input name='note' placeholder='QC note optional' style='max-width:280px'>
          <button name='action' value='run_agent'>Run Agent</button><button name='action' value='in_progress'>Start</button><button name='action' value='qc_pending'>QC pending</button><button name='action' value='approve'>Approve</button><button name='action' value='done'>Done</button><button name='action' value='blocked'>Block</button>
        </form>
        """
        task_html.append(f"""
        <div class='{css}'>
          <div class='row'>{status_badge(task_obj.get('status'))}<strong>{safe(task_obj.get('id'))}</strong><span>{safe(task_obj.get('agent'))}</span></div>
          <h3>{safe(task_obj.get('title'))}</h3><p class='muted small'>{safe(task_obj.get('description'))}</p>
          <div class='row'>{gates}</div>
          <div class='small muted'>Depends on: {safe(', '.join(task_obj.get('depends_on', [])) or 'none')} · Client approval: {safe(task_obj.get('requires_client_approval'))} · Sensitive execution: {safe(task_obj.get('execution_sensitive'))}</div>
          {notes_html}{output_html}{approval_link_html}{actions}
        </div>
        """)
    source = safe(json.dumps(case.get('source', {}), indent=2, ensure_ascii=False))
    notes = ''.join([f"<div class='small muted'>• {safe(n.get('note'))} — {safe(n.get('author'))} / {safe(n.get('type'))}</div>" for n in case.get('notes', [])[-8:]])
    active_html = ''.join([f"<li>{safe(a.get('task_id'))}: {safe(a.get('title'))} — {safe(a.get('agent'))}</li>" for a in active]) or '<li>No active tasks</li>'
    body = f"""
    <div class='row' style='margin-bottom:14px'><a class='btn btn2' href='/admin/fulfilment?{token_qs()}'>← Back</a><a class='btn btn2' href='/admin/fulfilment/export/case/{safe(case_id)}.json?{token_qs()}'>Export case JSON</a><a class='btn' href='/admin/fulfilment/report/{safe(case_id)}?{token_qs()}'>Client report preview</a>{status_badge(case.get('status'))}<span class='mono'>{safe(case_id)}</span></div>
    <div class='grid' style='grid-template-columns:2fr 1fr 1fr 1fr'>
      <div class='card'><h1>{safe(case.get('plan_name'))}</h1><p class='muted'>{safe(case.get('description'))}</p></div>
      <div class='card'><div class='muted small'>Customer</div><strong>{safe(case.get('customer', {}).get('name') or 'Unnamed')}</strong><div class='small muted'>{safe(case.get('customer', {}).get('email'))}</div></div>
      <div class='card'><div class='muted small'>Priority</div><h2>{safe(case.get('priority'))}</h2></div>
      <div class='card'><div class='muted small'>Trigger</div><h2>{safe(case.get('trigger'))}</h2></div>
    </div>
    <div class='card' style='margin-top:14px'><h2>Next actions</h2><ul>{active_html}</ul><form method='post' action='/admin/fulfilment/action'><input type='hidden' name='token' value='{safe(request.args.get('token'))}'><input type='hidden' name='case_id' value='{safe(case_id)}'><input type='hidden' name='action' value='run_next'><button>Run next ready agent</button></form></div>
    <div class='card' style='margin-top:14px'><h2>Add case note</h2><form method='post' action='/admin/fulfilment/action' class='row'><input type='hidden' name='token' value='{safe(request.args.get('token'))}'><input type='hidden' name='case_id' value='{safe(case_id)}'><input type='hidden' name='action' value='case_note'><input name='note' placeholder='Internal note'><button>Add note</button></form>{notes}</div>
    <div class='card' style='margin-top:14px'><h2>Tasks / QC gates</h2>{''.join(task_html)}</div>
    <div class='card' style='margin-top:14px'><h2>Source intake</h2><pre class='mono'>{source}</pre></div>
    """
    return dashboard_page(f"FMNO Case {case_id}", body)



@app.route('/admin/fulfilment/report/<case_id>')
def fulfilment_report_preview(case_id):
    if not admin_authorized():
        return redirect('/admin/fulfilment')
    case = get_case(case_id) if get_case else None
    if not case:
        return dashboard_page('Report not found', f"<div class='card'><h1>Case not found</h1><a href='/admin/fulfilment?{token_qs()}'>Back</a></div>"), 404
    report = latest_free_snapshot_report(case)
    if not report:
        outputs = latest_case_outputs(case, limit=12)
        report = None
        for item in outputs:
            output = item.get('output') or {}
            if output.get('client_summary'):
                report = output
                break
    if not report:
        body = f"<div class='card'><h1>No client-ready report yet</h1><p class='muted'>Run the next ready agent until a report output exists.</p><a class='btn' href='/admin/fulfilment/case/{safe(case_id)}?{token_qs()}'>Open case</a></div>"
        return dashboard_page('FMNO Report Preview', body)
    actions = ''.join([f"<li>{safe(a)}</li>" for a in report.get('recommended_actions', [])])
    negative_items = ''.join([f"<li>{safe(x)}</li>" for x in report.get('submitted_negative_items', [])]) or '<li>No specific negative URLs/search terms supplied.</li>'
    summary = safe(report.get('client_summary') or '')
    body = f"""
    <div class='row' style='margin-bottom:14px'><a class='btn btn2' href='/admin/fulfilment/case/{safe(case_id)}?{token_qs()}'>← Back to case</a><a class='btn btn2' href='/admin/fulfilment/export/case/{safe(case_id)}.json?{token_qs()}'>Export case JSON</a></div>
    <div class='card'><span class='small muted'>Client-ready preview after QC/manual review</span><h1>Free Search Snapshot™ report</h1><p class='muted'>Case {safe(case_id)} · {safe(case.get('customer', {}).get('name'))} · {safe(case.get('customer', {}).get('email'))}</p></div>
    <div class='grid' style='grid-template-columns:1fr 1fr 1fr'>
      <div class='card'><div class='muted small'>Risk level</div><h2>{safe(report.get('risk_level'))}</h2></div>
      <div class='card'><div class='muted small'>Negative items supplied</div><h2>{safe(report.get('negative_item_count'))}</h2></div>
      <div class='card'><div class='muted small'>Recommended next step</div><h2>{safe(report.get('recommended_package'))}</h2></div>
    </div>
    <div class='card' style='margin-top:14px'><h2>Client summary</h2><pre class='mono' style='white-space:pre-wrap'>{summary}</pre></div>
    <div class='card' style='margin-top:14px'><h2>Recommended actions</h2><ol>{actions}</ol><p><a class='btn' href='{safe(report.get('recommended_url') or '/checkout/starter')}'>Open recommended checkout/onboarding path</a></p></div>
    <div class='card' style='margin-top:14px'><h2>Submitted negative links/search terms</h2><ul>{negative_items}</ul></div>
    <div class='card danger' style='margin-top:14px'><h2>Operator rule</h2><p>Do not send this externally until the QC task is approved. The report gives recommended actions, not guarantees or legal advice.</p></div>
    """
    return dashboard_page('FMNO Free Snapshot Report', body)


@app.route('/admin/fulfilment/check-text', methods=['POST'])
def fulfilment_check_text_page():
    if not admin_authorized():
        return dashboard_page('Unauthorized', "<div class='card'><h1>Unauthorized</h1></div>"), 401
    draft = request.form.get('text', '')
    result = validate_public_text(draft) if validate_public_text else {'ok': False, 'blocked_terms': []}
    box_class = 'card okbox' if result.get('ok') else 'card danger'
    terms = ', '.join(result.get('blocked_terms', [])) or 'none'
    verdict = 'PASS — no blocked phrases found' if result.get('ok') else 'BLOCK — fix before approval'
    body = f"""
    <div class='row' style='margin-bottom:14px'><a class='btn btn2' href='/admin/fulfilment?token={safe(request.form.get('token'))}'>← Back to dashboard</a></div>
    <div class='{box_class}'><h1>{safe(verdict)}</h1><p><strong>Blocked terms:</strong> {safe(terms)}</p></div>
    <div class='card' style='margin-top:14px'><h2>Checked draft</h2><pre class='mono'>{safe(draft)}</pre></div>
    """
    return dashboard_page('FMNO QC Text Safety Check', body)

@app.route('/admin/fulfilment/action', methods=['POST'])
def fulfilment_dashboard_action():
    if not admin_authorized():
        return dashboard_page('Unauthorized', "<div class='card'><h1>Unauthorized</h1></div>"), 401
    case_id = request.form.get('case_id', '')
    task_id = request.form.get('task_id', '')
    action = request.form.get('action', '')
    note = request.form.get('note', '')
    if action == 'case_note':
        if add_case_note and note:
            add_case_note(case_id, note, 'Elli/Hermes', 'operator')
    elif action == 'run_next':
        if run_next_ready:
            run_next_ready(case_id, operator='DashboardWorker')
    elif action == 'run_agent':
        if run_task_agent:
            run_task_agent(case_id, task_id, operator='DashboardWorker')
    elif action == 'approve':
        if approve_task:
            approve_task(case_id, task_id, 'QCJohnny', note)
    elif action in ['in_progress', 'qc_pending', 'done', 'blocked', 'cancelled', 'ready']:
        if update_task_status:
            update_task_status(case_id, task_id, action, note, 'Elli/Hermes')
    return redirect(f"/admin/fulfilment/case/{case_id}?token={request.form.get('token', '')}")



def json_download(payload, filename):
    body = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    return Response(body, mimetype='application/json', headers={'Content-Disposition': f'attachment; filename="{filename}"'})


def read_jsonl_records(path):
    if not path.exists():
        return []
    records = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                records.append({'raw': line, 'parse_error': True})
    return records


@app.route('/admin/fulfilment/export/cases.json')
def admin_export_cases_json():
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    cases = list_cases(limit=10000) if list_cases else []
    payload = {'exported_at': utc_now(), 'service': 'FixMyNameOnline™', 'type': 'cases', 'case_count': len(cases), 'cases': cases}
    return json_download(payload, f'fmno-cases-{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.json')


@app.route('/admin/fulfilment/export/case/<case_id>.json')
def admin_export_single_case_json(case_id):
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    case = get_case(case_id) if get_case else None
    if not case:
        return jsonify({'ok': False, 'error': 'Case not found'}), 404
    payload = {'exported_at': utc_now(), 'service': 'FixMyNameOnline™', 'type': 'single_case', 'case': case, 'next_actions': next_actions(case_id) if next_actions else []}
    return json_download(payload, f'fmno-case-{case_id}.json')


@app.route('/admin/fulfilment/export/backup.json')
def admin_export_full_backup_json():
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    cases = list_cases(limit=10000) if list_cases else []
    payload = {
        'exported_at': utc_now(),
        'service': 'FixMyNameOnline™',
        'type': 'full_backup',
        'case_count': len(cases),
        'cases': cases,
        'snapshot_leads': read_jsonl_records(LEADS_FILE),
        'onboarding_submissions': read_jsonl_records(ONBOARDING_FILE),
        'fulfilment_queue': read_jsonl_records(FULFILMENT_QUEUE_FILE),
        'client_questions': read_jsonl_records(QUESTIONS_FILE),
        'click_events': read_jsonl_records(CLICK_EVENTS_FILE),
        'click_count': len(read_jsonl_records(CLICK_EVENTS_FILE)),
    }
    return json_download(payload, f'fmno-full-backup-{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.json')


@app.route('/admin/fulfilment/export/questions.json')
def admin_export_questions_json():
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    questions = read_jsonl_records(QUESTIONS_FILE)
    payload = {'exported_at': utc_now(), 'service': 'FixMyNameOnline™', 'type': 'client_questions', 'question_count': len(questions), 'questions': questions}
    return json_download(payload, f'fmno-client-questions-{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.json')


@app.route('/admin/fulfilment/cases')
def admin_fulfilment_cases():
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    if not list_cases:
        return jsonify({'ok': False, 'error': 'Fulfilment engine unavailable'}), 500
    cases = list_cases(status=request.args.get('status'), plan=request.args.get('plan'), limit=int(request.args.get('limit', 50)))
    return jsonify({'ok': True, 'cases': cases})


@app.route('/admin/fulfilment/cases/<case_id>')
def admin_fulfilment_case(case_id):
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    if not get_case:
        return jsonify({'ok': False, 'error': 'Fulfilment engine unavailable'}), 500
    case = get_case(case_id)
    if not case:
        return jsonify({'ok': False, 'error': 'Case not found'}), 404
    return jsonify({'ok': True, 'case': case, 'next_actions': next_actions(case_id) if next_actions else []})


@app.route('/admin/fulfilment/cases', methods=['POST'])
def admin_create_fulfilment_case():
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    payload = request.get_json(silent=True) or {}
    case = safe_create_fulfilment_case(payload.get('plan', 'starter'), payload.get('customer', {}), payload.get('source', payload), 'admin')
    if not case:
        return jsonify({'ok': False, 'error': 'Case creation failed'}), 500
    return jsonify({'ok': True, 'case': case}), 201


@app.route('/admin/fulfilment/cases/<case_id>/tasks/<task_id>', methods=['POST'])
def admin_update_fulfilment_task(case_id, task_id):
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    if not update_task_status:
        return jsonify({'ok': False, 'error': 'Fulfilment engine unavailable'}), 500
    payload = request.get_json(silent=True) or {}
    action = payload.get('action', 'status')
    try:
        if action == 'approve':
            case = approve_task(case_id, task_id, payload.get('approved_by', 'QCJohnny'), payload.get('note', ''))
        else:
            case = update_task_status(case_id, task_id, payload.get('status', 'in_progress'), payload.get('note', ''), payload.get('author', 'admin'))
    except ValueError as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 400
    if not case:
        return jsonify({'ok': False, 'error': 'Case or task not found'}), 404
    return jsonify({'ok': True, 'case': case, 'next_actions': next_actions(case_id) if next_actions else []})


@app.route('/admin/fulfilment/cases/<case_id>/tasks/<task_id>/run-agent', methods=['POST'])
def admin_run_fulfilment_task_agent(case_id, task_id):
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    if not run_task_agent:
        return jsonify({'ok': False, 'error': 'Fulfilment worker unavailable'}), 500
    result = run_task_agent(case_id, task_id, operator='APIWorker')
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@app.route('/admin/fulfilment/cases/<case_id>/run-next', methods=['POST'])
def admin_run_next_fulfilment_task(case_id):
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    if not run_next_ready:
        return jsonify({'ok': False, 'error': 'Fulfilment worker unavailable'}), 500
    result = run_next_ready(case_id, operator='APIWorker')
    status_code = 200 if result.get('ok') else 400
    return jsonify(result), status_code


@app.route('/admin/fulfilment/cases/<case_id>/notes', methods=['POST'])
def admin_add_fulfilment_note(case_id):
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    payload = request.get_json(silent=True) or {}
    case = add_case_note(case_id, payload.get('note', ''), payload.get('author', 'admin'), payload.get('type', 'note')) if add_case_note else None
    if not case:
        return jsonify({'ok': False, 'error': 'Case not found'}), 404
    return jsonify({'ok': True, 'case': case})


@app.route('/admin/fulfilment/validate-text', methods=['POST'])
def admin_validate_public_text():
    unauthorized = require_admin_json()
    if unauthorized:
        return unauthorized
    payload = request.get_json(silent=True) or {}
    result = validate_public_text(payload.get('text', '')) if validate_public_text else {'ok': False, 'blocked_terms': []}
    return jsonify({'ok': True, 'result': result})


@app.route('/api/track-click', methods=['POST'])
def api_track_click():
    payload = request.get_json(silent=True) or {}
    event = str(payload.get('event') or 'click')[:80]
    label = str(payload.get('label') or '')[:160]
    href = str(payload.get('href') or '')[:400]
    location = str(payload.get('location') or payload.get('path') or '')[:300]
    source = str(payload.get('source') or 'site')[:80]
    ua = (request.headers.get('User-Agent') or '')[:220]
    raw_ip = (request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[0].strip()
    salt = (os.environ.get('FMNO_ADMIN_TOKEN') or 'fmno-click-salt').strip()
    ip_hash = hashlib.sha256(f'{salt}:{raw_ip}'.encode('utf-8')).hexdigest()[:16] if raw_ip else ''
    append_jsonl(CLICK_EVENTS_FILE, {
        'event': event,
        'label': label,
        'href': href,
        'location': location,
        'source': source,
        'ip_hash': ip_hash,
        'user_agent': ua,
        'referrer': (request.headers.get('Referer') or '')[:400],
    })
    return jsonify({'ok': True})


@app.route('/health')
def health():
    provider = concierge_provider_name()
    configured = bool(os.environ.get('CONCIERGE_API_KEY') or os.environ.get('LLM_API_KEY') or (os.environ.get('OPENROUTER_API_KEY') if provider == 'openrouter' else os.environ.get('MINIMAX_API_KEY')))
    return jsonify({'status': 'ok', 'service': 'fixmynameonline', 'version': 'launch-v48-fmno-stripe-isolation', 'domain': DOMAIN, 'stripe_configured': bool(stripe.api_key), 'diy_checkout_configured': bool(DIY_CHECKOUT_TOKEN_SHA256), 'admin_token_configured': bool(os.environ.get('FMNO_ADMIN_TOKEN')), 'tracking_configured': bool(os.environ.get('FMNO_GA_MEASUREMENT_ID') or os.environ.get('GA_MEASUREMENT_ID') or os.environ.get('FMNO_META_PIXEL_ID') or os.environ.get('META_PIXEL_ID')), 'brevo_email_configured': bool(os.environ.get('BREVO_API_KEY') or os.environ.get('SENDINBLUE_API_KEY')), 'alert_email_recipients_configured': alert_email_recipients(), 'concierge_model_configured': configured, 'concierge_provider': provider, 'concierge_model': concierge_model_name(), 'concierge_voice_configured': concierge_voice_configured(), 'ava_avatar_configured': Path('assets/ava_concierge.mp4').exists(), 'click_tracking_configured': True})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
