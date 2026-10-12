"""
FixMyNameOnline™ — Flask Web Server
Landing page, Free Search Snapshot intake, Stripe checkout, and fulfilment-safe onboarding.

Copyright (c) 2026 Madison Jade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of Madison Jade Pty Ltd.
"""
import html
import os
import json
import re
import hmac
import hashlib
import sys
import paid_actions
import site_shell
import site_pages
import plans
from site_shell import icon, esc
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

BASE_DIR = Path(__file__).resolve().parent
# Never expose the repository root through Flask's implicit static handler.
# Customer records, access tokens, source, deployment files and local state all
# live beside the application and must only be reachable through authenticated
# routes. Public files are served from the two explicit allowlists below.
app = Flask(__name__, static_folder=None)


PRIVATE_PATH_PREFIXES = ('/private-case-room/', '/diy-action/', '/admin/', '/onboarding', '/submit-onboarding', '/success', '/self-service/tracker', '/name-watch-alerts/waitlist', '/approval/')
PRIVATE_PATHS = {'/app', '/free-search-snapshot', '/submit-snapshot', '/snapshot-received', '/api/concierge/submit', '/billing', '/cancel.html', '/submit-question'}


def is_private_path(path):
    path = path or '/'
    return path in PRIVATE_PATHS or path.startswith(PRIVATE_PATH_PREFIXES)


def analytics_allowed(path, method='GET'):
    path = path or '/'
    if method != 'GET' or is_private_path(path):
        return False
    # No analytics anywhere a visitor types something: the free check, the
    # tracker and the NameWatch waitlist form (Meta's pixel can read form fields).
    if path == '/self-service' or path.startswith(('/self-service', '/name-watch-alerts', '/personal-search', '/static/', '/assets/', '/api/')):
        return False
    return True


@app.after_request
def private_workflow_headers(response):
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('Referrer-Policy', 'no-referrer')
    if is_private_path(request.path):
        response.headers['Cache-Control'] = 'no-store, private'
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response

stripe.api_key = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
DOMAIN = os.environ.get('DOMAIN', 'https://fixmynameonline.com').rstrip('/')
SEO_DESCRIPTION = 'Something about you shows up on Google? Get a free step-by-step plan, letters you can edit and the official forms. You send everything yourself.'
SEO_IMAGE = DOMAIN + '/assets/fmno-share-1080.jpg'
DATA_DIR = Path(os.environ.get('FMNO_DATA_DIR', str(BASE_DIR / 'data'))).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
try:
    DATA_DIR.chmod(0o700)
except OSError:
    pass
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
FROM_NAME = os.environ.get('FMNO_FROM_NAME', 'Fix My Name Online')
INTERNAL_EMAIL = os.environ.get('FMNO_INTERNAL_EMAIL') or os.environ.get('ADMIN_EMAIL') or 'Elli35111@gmail.com'

PLANS = {
    'diy-action': {'name': 'Legacy DIY Reputation Action Workspace™', 'price': 49, 'mode': 'payment', 'env': 'STRIPE_PRICE_DIY_ACTION'},
    'diy-single': {'name': 'Single Action', 'price': 19, 'mode': 'payment', 'env': 'STRIPE_PRICE_DIY_SINGLE'},
    'diy-pack': {'name': 'Action Pack', 'price': 49, 'mode': 'payment', 'env': 'STRIPE_PRICE_DIY_PACK'},
    'sentinel': {'name': 'NameWatch Alert™', 'price': 29, 'mode': 'subscription', 'env': 'STRIPE_PRICE_SENTINEL', 'payment_link': os.environ.get('FMNO_SENTINEL_PAYMENT_LINK', '')},
    'removal-review': {'name': 'Removal Review™', 'price': 297, 'mode': 'payment', 'env': 'STRIPE_PRICE_REMOVAL_REVIEW', 'payment_link': 'https://buy.stripe.com/bJe14mfBA3CN8ca6X3cZa04'},
    'review-defence': {'name': 'Review Defence™', 'price': 497, 'mode': 'payment', 'env': 'STRIPE_PRICE_REVIEW_DEFENCE', 'payment_link': 'https://buy.stripe.com/7sY9AS610b5f6426X3cZa05'},
    'starter': {'name': 'Starter™', 'price': 499, 'mode': 'subscription', 'env': 'STRIPE_PRICE_STARTER', 'payment_link': 'https://buy.stripe.com/28E9AS8987T3bom1CJcZa06'},
    'pro': {'name': 'Pro™', 'price': 997, 'mode': 'subscription', 'env': 'STRIPE_PRICE_PRO', 'payment_link': 'https://buy.stripe.com/6oUcN4dtsb5f786dlrcZa07'},
    'premium': {'name': 'Premium™', 'price': 2497, 'mode': 'subscription', 'env': 'STRIPE_PRICE_PREMIUM', 'payment_link': 'https://buy.stripe.com/6oUeVc2OOgpzfEC817cZa08'},
}

# Shown on old Free Search Snapshot private links (/private-case-room/<id>),
# picked by key from what people entered back then. Keys and priorities stay
# the same; the copy matches today's products (free check + US$19 letter pack).
TRIAGE_NEXT_STEPS = {
    'alerts': {
        'label': 'NameWatch alerts (paused)',
        'summary': 'New NameWatch sign-ups are paused. If you already subscribe, it carries on and you can manage it from billing. For anything you’ve already found, the free check gives you a plan.',
        'cta': 'About NameWatch',
        'url': '/name-watch-alerts',
        'priority': 'standard',
    },
    'removal-review': {
        'label': 'One old article or link',
        'summary': 'Start with the free check. It gives you a plan and a letter you can edit, for free. If you’d like your letters for that one link saved online, with a follow-up and a second letter, there’s an optional US$19 letter pack. Either way, you check the facts and send everything yourself.',
        'cta': 'See the US$19 letter pack',
        'url': '/diy-action',
        'priority': 'high',
    },
    'review-defence': {
        'label': 'A review',
        'summary': 'The platform decides reviews under its own rules. The free check shows you which rule might apply, the platform’s official report form and wording you can adapt. The letter pack isn’t for reviews.',
        'cta': 'Start the free check for a review',
        'url': '/self-service?problem=review',
        'priority': 'high',
    },
    'repair-plan': {
        'label': 'Start with the free check',
        'summary': 'Pick what you found and answer a few questions. You get a plan with the official forms and a letter you can edit. It’s free and runs in your browser.',
        'cta': 'Start the free check',
        'url': '/self-service',
        'priority': 'standard',
    },
    'high-risk': {
        'label': 'Get help from the right people first',
        'summary': 'If there are threats, a child is involved, or a court case is still running, start with emergency services, the police, eSafety or a lawyer, not a paid tool. The free check’s safety question puts those contacts at the top of your plan.',
        'cta': 'Start the free check',
        'url': '/self-service',
        'priority': 'urgent',
    },
}

BASE_STYLE = """
:root{--dark:#08090f;--card:#151824;--red:#d91f3d;--grey:#9aa2b6;--light:#e8ecf5;}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 20% 5%,rgba(217,31,61,.16),transparent 28%),var(--dark);color:white;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;line-height:1.5;padding:22px;}
a{color:#ff4d66}.wrap{max-width:980px;margin:0 auto}.card{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.11);border-radius:22px;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.28)}
.site-head{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:22px}.logo{font-weight:900;letter-spacing:.12em;color:var(--red);font-size:15px;text-decoration:none}.seo-nav{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:8px 14px;font-size:13px}.seo-nav a{color:var(--light);text-decoration:none}.seo-nav a:hover{text-decoration:underline}.sub{color:var(--grey)}h1{font-size:clamp(32px,6vw,58px);line-height:1.02;margin:0 0 14px}h2{margin-top:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.full{grid-column:1/-1}.snapshot-shell{display:grid;grid-template-columns:1.05fr .75fr;gap:22px;align-items:start}.trust-strip{display:flex;flex-wrap:wrap;gap:10px 18px;color:var(--grey);font-size:12px;margin:18px 0}.trust-strip span:before{content:'•';color:#d4af37;margin-right:8px}.side-card{position:sticky;top:18px}.steps{display:grid;gap:12px}.step{border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.04);border-radius:16px;padding:14px}.step b{color:#ffb0bd}.microcopy{font-size:12px;color:var(--grey);margin-top:6px}.submit-row{display:flex;flex-wrap:wrap;gap:12px;align-items:center}.progress{height:7px;background:#0d1019;border:1px solid rgba(255,255,255,.12);border-radius:999px;overflow:hidden;margin:10px 0 18px}.progress span{display:block;height:100%;width:18%;background:linear-gradient(90deg,var(--red),#ff6f85);transition:width .2s ease}
label{display:block;font-weight:700;margin:14px 0 7px}input,select,textarea{width:100%;background:#0d1019;color:white;border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:13px 14px;font:inherit}input:focus,select:focus,textarea:focus{outline:2px solid rgba(217,31,61,.35);border-color:rgba(217,31,61,.65)}textarea{min-height:105px}.btn{display:inline-block;background:linear-gradient(135deg,var(--red),#a81229);border:0;border-radius:13px;color:white;font-weight:800;padding:14px 20px;text-decoration:none;cursor:pointer;font-size:16px}.btn2{background:transparent;border:1px solid rgba(255,255,255,.22)}.note{font-size:13px;color:var(--grey)}.pill{display:inline-block;border:1px solid rgba(217,31,61,.35);background:rgba(217,31,61,.08);padding:7px 10px;border-radius:999px;color:#ffb0bd;font-size:13px;font-weight:700}.ok{color:#31d07a}.err{color:#ff6f85}.recommend{border:1px solid rgba(217,31,61,.35);background:rgba(217,31,61,.08);border-radius:18px;padding:20px;margin:22px 0}@media(max-width:820px){body{padding:14px}.site-head{align-items:flex-start;flex-direction:column}.seo-nav{justify-content:flex-start}.grid,.snapshot-shell{grid-template-columns:1fr}.card{padding:20px}.side-card{position:static}.submit-row .btn{width:100%;text-align:center} }
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
        # autoConfig off: Meta's automatic events would otherwise record clicks
        # (button text + link address), e.g. the problem tiles on the homepage.
        # Privacy section 4 promises those choices are not sent to Meta.
        pid = safe(meta_pixel_id)
        parts.append(f'''
<script>
!function(f,b,e,v,n,t,s){{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)}};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}}(window, document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('set', 'autoConfig', false, '{pid}');
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


def organization_schema():
    return {
        '@type': 'Organization', '@id': DOMAIN + '/#organization',
        'name': site_shell.BRAND,
        'alternateName': ['FixMyNameOnline', 'Fix My Name On Line', 'FMNO'],
        'url': DOMAIN + '/', 'legalName': site_shell.COMPANY,
        'taxID': site_shell.ABN_DIGITS,
        'email': site_shell.CONTACT_EMAIL,
        'address': {'@type': 'PostalAddress', 'addressRegion': 'SA', 'addressCountry': 'AU'},
        'areaServed': 'Worldwide',
        'sameAs': ['https://x.com/Fixmyname_com', 'https://www.instagram.com/fixmynameonlinecom/', 'https://www.tiktok.com/@fix.my.name.onlin', 'https://www.youtube.com/@FMNOReputationTV'],
    }


def page(title, body, description=None, canonical_path=None, schema_items=None, robots='index,follow,max-image-preview:large', analytics=True,
         current=None, desk=False, safety=None, crumbs=None, legacy=None, law_notice=True):
    """Render any page in the shared shell.

    Bodies written for the old template (cards, pills, .recommend) are wrapped
    in a `.legacy` container so they inherit the new design system.
    """
    desc = description or SEO_DESCRIPTION
    path = canonical_path or request.path or '/'
    canonical = DOMAIN + (path if path.startswith('/') else '/' + path)
    title = re.sub(r'\s*(?:—|\||-)\s*(?:FixMyNameOnline™|Fix My Name Online™|FMNO)\s*$', '', str(title)).replace('FixMyNameOnline™', site_shell.BRAND).replace('Fix My Name Online™', site_shell.BRAND)
    if site_shell.BRAND not in title:
        title = f'{title} | {site_shell.BRAND}'
    trail = crumbs if crumbs is not None else [(title.split(' | ')[0], canonical)]
    graph = [
        organization_schema(),
        {
            '@type': 'WebSite', '@id': DOMAIN + '/#website', 'url': DOMAIN + '/',
            'name': site_shell.BRAND, 'publisher': {'@id': DOMAIN + '/#organization'},
        },
        {
            '@type': 'WebPage', '@id': canonical + '#webpage', 'url': canonical,
            'name': title, 'description': desc,
            'isPartOf': {'@id': DOMAIN + '/#website'}, 'about': {'@id': DOMAIN + '/#organization'},
            'breadcrumb': {'@id': canonical + '#breadcrumb'},
        },
        {
            '@type': 'BreadcrumbList', '@id': canonical + '#breadcrumb',
            'itemListElement': [{'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': DOMAIN + '/'}] + [
                {'@type': 'ListItem', 'position': i + 2, 'name': name, 'item': (url if url.startswith('http') else DOMAIN + url)}
                for i, (name, url) in enumerate(trail)
            ],
        },
    ]
    if schema_items:
        graph.extend(schema_items)
    schema_json = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False).replace('</', '<\\/')
    if is_private_path(request.path) or request.method == 'POST':
        robots = 'noindex,nofollow'
    if not analytics_allowed(request.path, request.method):
        analytics = False
    if legacy is None:
        legacy = not body.lstrip().startswith(('<main', '<section', '<div class="page'))
    if legacy:
        body = f'<main id="main" class="wrap legacy">{body}</main>'
    return site_shell.document(
        title=title, description=desc, canonical=canonical, robots=robots, schema_json=schema_json,
        tracking=tracking_head() if analytics else '', body=body, current=current, desk=desk,
        safety=safety, og_image=SEO_IMAGE, law_notice=law_notice)


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
    ('names_to_check', 'What name, business or search phrase is your concern about? This is intake guidance, not a live search.'),
    ('country_state', 'What country, state, or city context should we consider for that search?'),
    ('authority', 'Who is this for? Reply self for your own name, business for a business you represent, or authorised if you have the other person’s permission.'),
    ('problem_links', 'If you already have a link, article title, review page, or search phrase, paste it here. If not, write “search first”.'),
    ('goal', 'What are you hoping to understand or fix from the Free Search Snapshot™?'),
    ('contact_name', 'What name should we use when we send the private snapshot?'),
    ('email', 'What email should be associated with this intake? Your first guidance appears on screen; email delivery is not confirmed here.'),
    ('consent', 'Do you agree to the Privacy Policy and Terms linked below, confirm your authority, and understand this is automated intake guidance with no external action? Reply yes to agree.'),
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
        value = str(collected.get(key, '')).strip().lower()
        if not value or (key == 'authority' and value not in {'self', 'business', 'authorised'}) or (key == 'consent' and value != 'yes'):
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
    system = '''You are Private Search Concierge™ for FixMyNameOnline™, operated by Madison Jade Pty Ltd.
Tone: premium, calm, private, human, concise.
Role: AI-assisted intake only. Keep replies short and move toward Free Search Snapshot™.
Never claim to have searched Google, verified a result, or promise human review. Guidance is based only on the visitor's answers. The free self-service desk is available at /self-service.
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
    if os.environ.get('ANTHROPIC_API_KEY'):
        return 'anthropic'
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
    if provider == 'anthropic':
        return 'claude-haiku-4-5-20251001'
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
    if provider == 'anthropic':
        api_key = (os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('CONCIERGE_API_KEY') or '').strip()
        default_base = 'https://api.anthropic.com/v1/messages'
    elif provider == 'openrouter':
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
    messages = build_concierge_messages(topic, collected, user_message, next_question, ready)
    if provider == 'anthropic':
        payload = {
            'model': model,
            'system': messages[0]['content'],
            'messages': [message for message in messages if message.get('role') != 'system'],
            'temperature': 0.25,
            'max_tokens': 1000,
        }
        headers = {'x-api-key': api_key, 'anthropic-version': '2023-06-01', 'Content-Type': 'application/json'}
    else:
        payload = {
            'model': model,
            'messages': messages,
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
        if provider == 'anthropic':
            content = ''.join(block.get('text', '') for block in data.get('content', []) if block.get('type') == 'text')
        else:
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
    recommended_pathway = clean_concierge_text(model_data.get('recommended_pathway') or 'Free Search Snapshot™')
    pathway_key = recommended_pathway.lower().replace('™', '').replace('-', '_').replace(' ', '_')
    recommended_pathway = {
        'free_search_snapshot': 'Free Search Snapshot™',
        'diy_action': 'DIY Reputation Action Workspace™',
        'diy_reputation_action_workspace': 'DIY Reputation Action Workspace™',
        'removal_review': 'DIY Reputation Action Workspace™',
        'namewatch': 'NameWatch Alert™',
        'namewatch_alert': 'NameWatch Alert™',
    }.get(pathway_key, recommended_pathway)
    return {
        'ok': True,
        'reply': reply,
        'next_question': question,
        'current_field': next_key,
        'collected': collected,
        'ready_to_submit': ready,
        'risk_level': risk_level,
        'recommended_pathway': recommended_pathway,
        'risk_score_preview': reputation_risk_score(preview_data, preview_triage),
        'cta': 'Submit Free Search Snapshot™' if ready else None,
        'model_used': bool(model_data),
    }

def triage_snapshot(data):
    text = ' '.join([data.get('case_type', ''), data.get('names_to_check', ''), data.get('problem_links', ''), data.get('goal', '')]).lower()
    case_type = data.get('case_type', '').lower()

    high_risk_words = ['emergency', 'criminal', 'police', 'lawsuit', 'defamation', 'doxxing', 'doxing', 'stalking', 'threat', 'threats', 'minor', 'minors', 'child', 'children', 'active legal', 'proceedings', 'high-risk', 'high risk']
    review_words = ['review', 'reviews', 'google review', '1 star', 'one star', 'fake review', 'malicious review']
    removal_words = ['article', 'old news', 'news article', 'bad link', 'bad links']
    alert_words = ['alert', 'monitor', 'tracking', 'mentions', 'watch']

    if 'high-risk' in case_type or any(re.search(r'\b' + re.escape(w) + r'\b', text) for w in high_risk_words):
        key = 'high-risk'
    elif 'private information' in case_type or 'wrong person' in case_type:
        key = 'repair-plan'
    elif 'monitoring' in case_type:
        key = 'alerts'
    elif 'review' in case_type or any(re.search(r'\b' + re.escape(w) + r'\b', text) for w in review_words):
        key = 'review-defence'
    elif 'article' in case_type or any(re.search(r'\b' + re.escape(w) + r'\b', text) for w in removal_words):
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
        'recommendation': triage.get('label') or (report or {}).get('recommended_package') or 'Free Search Snapshot™',
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
            'country_state': data.get('country_state', ''),
            'authority': data.get('authority', ''),
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


def send_onboarding_emails(data, queue_item):
    plan_label = PLANS.get(data.get('plan'), {}).get('name', data.get('plan', 'Private onboarding'))
    if data.get('plan') == 'sentinel':
        customer_html = f"""
        <div style=\"font-family:Arial,sans-serif;max-width:640px;margin:auto;color:#111;line-height:1.55\">
          <h1>NameWatch Alert™ is activated</h1>
          <p>Hi {safe(data.get('name'))},</p>
          <p>Thanks. We’ve got the names and phrases you want us to watch.</p>
          <h2>What happens next</h2>
          <ol><li>Our first search records what already shows up for those names. We don’t alert you about those.</li><li>After that, the search runs on a schedule.</li><li>When a search finds a result it hasn’t seen before, we email you the link.</li><li>If there’s nothing new, you get a short status note instead.</li></ol>
          <p>A new result isn’t necessarily bad, or newly published. It just means our search hadn’t seen it before. NameWatch doesn’t contact anyone or remove anything.</p>
          <p style=\"font-size:12px;color:#666\">Private reference: {safe(queue_item['id'])}<br>FixMyNameOnline™ · Madison Jade Pty Ltd</p>
        </div>
        """
        internal_html = f"""
        <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111\">
          <h1>New paid NameWatch onboarding</h1><p><strong>Queue ID:</strong> {safe(queue_item['id'])}</p>
          <pre style=\"background:#f5f5f5;padding:16px;border-radius:10px;white-space:pre-wrap\">{safe(json.dumps(data, indent=2, ensure_ascii=False))}</pre>
        </div>"""
        return {
            'customer_email_sent': send_brevo_email(data.get('email'), data.get('name'), 'NameWatch Alert™ activated — FixMyNameOnline™', customer_html),
            'internal_email_sent': send_internal_alert_email(f"FMNO NameWatch onboarding — {data.get('name', '')}", internal_html),
        }
    # Older managed packages are no longer offered and submit_onboarding() stops
    # before this point, so there is no customer email for them.
    return {}


@app.route('/data', defaults={'filename': ''}, methods=['GET', 'HEAD'])
@app.route('/data/<path:filename>', methods=['GET', 'HEAD'])
def deny_private_data(filename):
    """Fail closed if an old or future private-data URL is requested."""
    return Response(status=404)


@app.route('/assets/<path:filename>')
def public_asset(filename):
    # Versioned URLs (?v=hash) are immutable; unversioned ones revalidate hourly.
    max_age = 31536000 if request.args.get('v') else 3600
    return send_from_directory(str(BASE_DIR / 'assets'), filename, max_age=max_age)


@app.route('/static/<path:filename>')
def public_static(filename):
    return send_from_directory(str(BASE_DIR / 'static'), filename)


@app.route('/')
def landing():
    schema = [site_pages.faq_schema(site_pages.HOME_FAQ, DOMAIN + '/')]
    return page('Fix My Name Online | Deal with what shows up when people Google you', site_pages.home(),
                'Something about you shows up on Google? Get a free step-by-step plan, letters you can edit and the official forms. You send everything yourself.',
                canonical_path='/', schema_items=schema, crumbs=[])


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
    return send_from_directory(str(BASE_DIR / 'personal-search'), 'index.html')


@app.route('/personal-search/<path:filename>')
def personal_search_file(filename):
    if Path(filename).suffix.lower() != '.html':
        return not_found_page()
    return send_from_directory(str(BASE_DIR / 'personal-search'), filename)


# Only indexable, 200-status pages belong here. Intake/redirect URLs
# (/app, /free-search-snapshot, /questions) were removed in the 12 Oct 2026 audit fix.
HUB_PATHS = ['/help/' + p['hub'] for p in plans.PROBLEMS]
CORE_SITEMAP_URLS = [
    '/', '/self-service', *HUB_PATHS, '/how-it-works', '/pricing', '/faq',
    '/fix-my-name-online', '/fix-your-name-online', '/how-to-fix-your-reputation-online', '/learn', '/false-information-claims-online', '/bad-google-results-help',
    '/when-google-makes-your-past-look-like-your-present', '/google-your-name',
    '/contact', '/about', '/services', '/online-reputation-repair', '/worldwide-reputation-repair',
    '/reputation-repair-australia', '/private-reputation-repair', '/google-review-defence',
    '/google-review-defence-worldwide', '/google-review-defence-australia', '/remove-bad-google-results',
    '/remove-negative-google-results', '/name-watch-alerts', '/diy-action', '/privacy', '/terms',
]


def render_urlset(urls, high_priority=None):
    high_priority = set(high_priority or [])
    today = datetime.utcnow().strftime('%Y-%m-%d')
    unique_urls = list(dict.fromkeys(urls))
    urlset = ''.join(
        f"<url><loc>{DOMAIN}{path}</loc><lastmod>{today}</lastmod><changefreq>{'weekly' if path in high_priority else 'monthly'}</changefreq><priority>{'1.0' if path == '/' else ('0.9' if path in high_priority else '0.7')}</priority></url>"
        for path in unique_urls
    )
    return f"<?xml version='1.0' encoding='UTF-8'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>{urlset}</urlset>"


@app.route('/sitemap-core.xml')
def sitemap_core_xml():
    xml = render_urlset(CORE_SITEMAP_URLS, ['/', '/self-service', *HUB_PATHS, '/fix-my-name-online', '/fix-your-name-online', '/how-to-fix-your-reputation-online', '/learn', '/online-reputation-repair', '/bad-google-results-help'])
    return Response(xml, mimetype='application/xml')


@app.route('/sitemap-guides.xml')
def sitemap_guides_xml():
    urls = ['/' + slug for slug, _guide in active_seo_guides()]
    return Response(render_urlset(urls), mimetype='application/xml')


@app.route('/sitemap-personal-search.xml')
def sitemap_personal_search_xml():
    urls = ['/personal-search/']
    personal_search_dir = BASE_DIR / 'personal-search'
    if personal_search_dir.exists():
        urls += [f'/personal-search/{p.name}' for p in sorted(personal_search_dir.glob('*.html')) if p.name != 'index.html']
    return Response(render_urlset(urls), mimetype='application/xml')


@app.route('/sitemap.xml')
def sitemap_xml():
    today = datetime.utcnow().strftime('%Y-%m-%d')
    children = ['/sitemap-core.xml', '/sitemap-guides.xml', '/sitemap-personal-search.xml']
    entries = ''.join(f'<sitemap><loc>{DOMAIN}{path}</loc><lastmod>{today}</lastmod></sitemap>' for path in children)
    xml = f"<?xml version='1.0' encoding='UTF-8'?><sitemapindex xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>{entries}</sitemapindex>"
    return Response(xml, mimetype='application/xml')


@app.route('/about')
def about():
    return page('About and trust', site_pages.about(),
                f'Fix My Name Online is run by {site_shell.COMPANY} (ABN {site_shell.ABN}), South Australia. Self-service tools, not a law firm. What we do, what we don’t, and how to find a lawyer.',
                canonical_path='/about', current='about')


@app.route('/fix-my-name-on-line')
def fix_my_name_on_line_variant_redirect():
    return redirect('/fix-my-name-online', code=301)


@app.route('/fix-my-name-online')
def fix_my_name_online_exact_match():
    schema_items = [site_pages.faq_schema(site_pages.FIX_FAQ, DOMAIN + '/fix-my-name-online')]
    return page('Fix My Name Online: free self-service tools for what shows up when people search your name', site_pages.fix_my_name_online(),
                'Fix My Name Online is a set of free self-service tools for old articles, people-search listings, fake profiles, court records, reviews and photos. Not a legal name-change service.',
                canonical_path='/fix-my-name-online', schema_items=schema_items)


@app.route('/services')
def services():
    return page('Our tools: free check, tracker and letter pack', site_pages.services(),
                'Free self-service tools for what shows up when people search your name, plus one optional US$19 letter pack. No agency, no retainer.',
                canonical_path='/services')




def acquisition_page(slug):
    """The nine search-intent landing pages, rendered through the shared guide template."""
    data = site_pages.ACQUISITION[slug]
    related = [('/help/' + p['hub'], p['hub_title']) for p in plans.PROBLEMS][:4] + [('/learn', 'All guides')]
    body = site_pages.guide_page(slug=slug, h1=data['h1'], eyebrow=data['eyebrow'], intro=data['intro'], sections=data['sections'],
                                 faqs=data['faqs'], related=related, problem=data['problem'])
    return page(data['title'], body, data['description'], canonical_path='/' + slug, safety='au',
                schema_items=[site_pages.faq_schema(data['faqs'], DOMAIN + '/' + slug)],
                crumbs=[('Guides', '/learn'), (data['h1'], '/' + slug)])


@app.route('/online-reputation-repair')
def online_reputation_repair_page():
    return acquisition_page('online-reputation-repair')


@app.route('/worldwide-reputation-repair')
def worldwide_reputation_repair_page():
    return acquisition_page('worldwide-reputation-repair')


@app.route('/reputation-repair-australia')
def reputation_repair_australia_page():
    return acquisition_page('reputation-repair-australia')


@app.route('/remove-negative-google-results')
def remove_negative_google_results_page():
    return acquisition_page('remove-negative-google-results')


@app.route('/google-review-defence-worldwide')
def google_review_defence_worldwide_page():
    return acquisition_page('google-review-defence-worldwide')


@app.route('/google-review-defence-australia')
def google_review_defence_australia_page():
    return acquisition_page('google-review-defence-australia')


@app.route('/google-review-defence')
def google_review_defence_page():
    return acquisition_page('google-review-defence')


@app.route('/remove-bad-google-results')
def remove_bad_google_results_page():
    return acquisition_page('remove-bad-google-results')


@app.route('/private-reputation-repair')
def private_reputation_repair_page():
    return acquisition_page('private-reputation-repair')


SEO_GUIDES = {
    'online-reputation-management-australia': {
        'eyebrow': 'Australian reputation management',
        'title': 'Online Reputation Management Australia — Fix My Name Online',
        'h1': 'Online reputation management in Australia: what you can do yourself',
        'description': 'A practical, self-service guide for Australians dealing with what Google shows for their name or business: old articles, reviews, people-search listings and the official routes.',
        'intro': 'Fix My Name Online is run by Madison Jade Pty Ltd in Australia, and its free tools work for people anywhere. This guide explains a careful, practical way to manage your reputation online: see what shows up, keep evidence, ask the right people, publish accurate information and keep checking.',
        'sections': [
            ('Start with the search result page, not guesses', 'The first step is to see what Google actually shows for your full name, business name, old names, common misspellings, locations, and words like review or complaint. Look at what a stranger would see, not just your exact name on its own.'),
            ('Separate removable problems from reputation gaps', 'Some results can be corrected, updated or reported through the site, Google or a privacy form. Others can’t realistically be removed. Separate those early so you don’t spend months chasing takedowns that won’t happen.'),
            ('Make sure accurate information about you is easy to find', 'A current work profile, an up-to-date business listing or a short, true bio gives people something accurate to find. Keep it modest and true. Fake reviews and made-up pages break platform rules and can make things worse.'),
            ('Keep a simple record', 'Write down the searches you check, what shows up and the date. Check again every month or two, and after any page changes. If you have your own website, Google’s free Search Console tool can show whether Google has found your pages.'),
        ],
        'faqs': [
            ('Do Australian reputation cases only affect Australia?', 'No. Australians are often searched by people overseas: clients, employers, investors and journalists. You may live in Australia, but the people searching your name could be anywhere.'),
            ('Can anyone guarantee page one?', 'No. Google makes its own decisions, and anyone who promises a ranking is guessing. What you can do is ask for wrong or outdated pages to be fixed, and keep accurate information about you up to date.'),
        ],
    },
    'reputation-repair-for-individuals': {
        'eyebrow': 'Individual reputation repair',
        'title': 'Reputation Repair for Individuals — Fix My Name Online',
        'h1': 'Reputation repair for individuals when Google shows the wrong first impression',
        'description': 'Practical guide for individuals dealing with old Google results, associated names, outdated snippets, reviews, complaint pages or sensitive search terms.',
        'intro': 'People get searched before job interviews, dates, rentals, partnerships, media calls and client decisions. Individual reputation repair is about making the search result page more accurate, current and complete without making unsafe promises.',
        'sections': [
            ('Map the person behind the search', 'A real plan checks legal names, previous names, nicknames, professional names, locations, business links, images, news results, review sites and common risk phrases. One bad result may be less damaging than a pattern of associated searches.'),
            ('Put accurate information where people will find it', 'A short, true bio, a current work profile or a business page tells people who you are now. Share only what you’re comfortable having online; some things can stay private.'),
            ('Handle sensitive claims carefully', 'Where allegations, court mentions, old articles or disputes exist, keep anything you say in public factual, calm and short. If it’s a legal question, such as defamation, talk to a lawyer; we’re not a law firm.'),
            ('Check back over time', 'Search your name, old names, business name and suburb every month or two and note what has changed, so you can see whether a request worked.'),
        ],
        'faqs': [
            ('Is this public?', 'The free check runs in your browser, so your planning stays private. Only publish information that’s true and that you’re comfortable sharing.'),
            ('How long does it take?', 'A request usually takes about 30 minutes of your time. Replies often take two to six weeks, and changes in Google can take longer after the page itself changes.'),
        ],
    },
    'old-news-article-on-google': {
        'eyebrow': 'Old article search risk',
        'title': 'Old News Article Showing on Google — Options and Limits | Fix My Name Online',
        'h1': 'Old news article showing on Google? Start with options, limits and evidence',
        'description': 'What to do when an old news article, court mention or outdated story appears on Google: what to save, who decides, what to ask the publisher for, and Google’s refresh tool.',
        'intro': 'Old articles can keep following people long after the facts, context or life circumstances have changed. The right response depends on the source, accuracy, legal status, public interest, indexing and available evidence.',
        'sections': [
            ('Check whether the article is accurate and current', 'Correction and publisher requests are strongest when there is a clear factual error, missing outcome, outdated snippet, privacy issue or changed circumstance that can be evidenced.'),
            ('Understand what Google controls', 'Google usually indexes pages created by others. It may remove or update some results under specific policies, but it does not rewrite publisher content. That is why publisher, platform and search-engine paths need to be separated.'),
            ('Prepare evidence before asking', 'Screenshots, URLs, dates, cached snippets, legal outcomes, publisher contact details and proof of identity or authority can matter. A vague emotional request is weaker than a calm, documented request.'),
            ('If the article stays', 'Write down the publisher’s answer and check the complaint routes for your country. Make sure accurate, current information about you, like a work profile or business page, is easy to find.'),
        ],
        'faqs': [
            ('Can an old news article always be removed?', 'No. Some can be updated or taken down; many can’t. Start by checking the facts and what the publisher’s own policy allows.'),
            ('Can Google remove the snippet?', 'Sometimes outdated or policy-eligible snippets can be reviewed, but Google and the publisher make their own decisions.'),
        ],
    },
    'fake-google-reviews-help': {
        'eyebrow': 'Google review defence',
        'title': 'Fake Google Reviews Help — Evidence, Reporting and Response | Fix My Name Online',
        'h1': 'Fake Google reviews: evidence, a proper report and a calm reply',
        'description': 'What to do about a fake, malicious or unfair Google review: save the evidence, match it to Google’s rules, report it, and write a calm public reply.',
        'intro': 'A fake or malicious review can cost calls, bookings and trust. The strongest response isn’t panic or a public fight. It’s clear evidence, a report that names the policy, a calm public reply, and honest reviews over time.',
        'sections': [
            ('Document the pattern', 'Record review dates, reviewer names, wording, star rating, business relationship, screenshots and any signs of competitor, ex-employee, ex-partner or review-bombing activity.'),
            ('Match the issue to platform policy', 'Google decides whether a review is removed. A good report connects the facts to a specific policy, rather than simply saying the review is unfair.'),
            ('Respond for future customers', 'A calm owner response is often read by prospects. It should be short, factual, non-defamatory and focused on customer care, not a public argument.'),
            ('Keep the rest of your profile strong', 'Keep your business details current and ask every customer for an honest review, without offering anything in return. A steady stream of real reviews puts one bad one in context.'),
        ],
        'faqs': [
            ('Can anyone delete fake Google reviews for me?', 'No. Only Google can remove a review. The free plan walks you through saving the evidence, reporting it against the right rule, and replying. Google decides.'),
            ('Should I reply publicly?', 'Often yes, but carefully. The reply should reassure future customers, not escalate the dispute.'),
        ],
    },
    'how-to-check-your-online-reputation': {
        'eyebrow': 'Search self-audit',
        'title': 'How to Check Your Online Reputation Before People Search You | Fix My Name Online',
        'h1': 'How to check your online reputation before clients, employers or dates search you',
        'description': 'A practical online reputation self-audit checklist for names, business names, old names, Google results, reviews, images, snippets and associated search terms.',
        'intro': 'Most people find a problem result too late, after a client goes quiet or an employer hesitates. Checking your own name now shows you what’s fine, what’s wrong, and what you might want to ask someone to fix.',
        'sections': [
            ('Search like a stranger', 'Use your full name, quoted name, old names, nicknames, business names, suburb, city, job title, review terms and risk words. Check web results, images, videos, news and review profiles.'),
            ('Record what appears on page one and two', 'Titles, snippets and images can matter as much as the page itself. Screenshot the result, URL, date and search phrase so changes can be tracked.'),
            ('Sort what you find', 'Group results into fine, out of date, wrong, about someone else, reviews, and photos. Each kind has a different person who decides and a different thing to ask for.'),
            ('Deal with the ones that matter', 'If a result is wrong or out of date, ask the website to fix it. If it breaks a platform’s rules, report it. If there’s little accurate information about you, add a current profile you control.'),
        ],
        'faqs': [
            ('Should I search in private browsing?', 'It can help reduce personalization, but location and device still influence results. Track the exact search phrase and date.'),
            ('What should I do first if I find something bad?', 'Save the link and a dated screenshot before you react. Then start the free check to get the steps for that kind of result.'),
        ],
    },
    'bad-results-on-google-what-to-do': {
        'eyebrow': 'Bad Google results help',
        'title': 'I Have Bad Results on Google — What Do I Do? | Fix My Name Online',
        'h1': 'I have bad results on Google. What do I do first?',
        'description': 'What to do if you have bad results on Google: save evidence, work out who decides, ask for one specific change, and avoid the reactions that make it worse.',
        'intro': 'If you have bad results on Google, do not panic and do not start sending angry messages. The first move is to save evidence, understand what type of result it is, and pick the right next step before a rushed response makes it worse.',
        'sections': [
            ('Step 1: save the result before reacting', 'Take screenshots of the Google result, page title, snippet, URL, date, search phrase and any image or review that appears. If the result changes later, this evidence helps show what was visible and when.'),
            ('Step 2: identify what kind of bad result it is', 'A bad Google result can be an old news article, court mention, bad review, complaint page, image, outdated snippet, forum post, copied content or an associated-name result. Each one is handled a different way.'),
            ('Step 3: check whether removal or correction is realistic', 'Some results can be corrected by the publisher, reported to the platform, or refreshed in Google once the page changes. Others can’t. Working out which applies before you write saves time, and stops you asking for something that doesn’t fit.'),
            ('Step 4: build the stronger current story', 'If the bad result can’t be removed quickly, the next move is to publish accurate information about your name or business: profiles, pages, articles and FAQs that show the fuller current picture.'),
        ],
        'faqs': [
            ('Can bad results on Google be removed?', 'Sometimes. Often they can’t, or only once the website changes the page. Google, publishers and platforms make their own decisions. The free check shows which routes fit your situation.'),
            ('Should I contact the website immediately?', 'Not always. Save evidence first and work out what to ask for. A calm, specific message helps; a rushed or angry one can make things harder.'),
            ('Can Fix My Name Online look at this for me?', 'No. We don’t search for you or review your case. The free check runs in your browser: you tell it what kind of result you found and answer a few questions, and it gives you the steps, a letter you can edit and the official forms. Nothing you type is sent to us.'),
        ],
    },
    'what-to-do-if-google-results-are-bad': {
        'eyebrow': 'Bad search results action plan',
        'title': 'What To Do If Google Results Are Bad | Fix My Name Online',
        'h1': 'What to do if your Google results are bad',
        'description': 'A calm plan for bad Google results about your name or business: save the evidence, work out who decides, ask for the right thing, and keep a record.',
        'intro': 'Bad Google results can affect jobs, clients, money, relationships and trust. The safest response is calm: save the evidence, work out what kind of result it is, ask the person who decides for one specific change, and keep a record.',
        'sections': [
            ('Do not feed the result', 'Avoid public arguments, social posts about the issue and mass-reporting without evidence. These tend to draw more attention to the problem, not less.'),
            ('Check the searches people actually use', 'Try your full name, business name, old names, suburb, job and words like “review” or “complaint”. A problem often shows up for only one of these.'),
            ('Separate platform problems from search problems', 'Google shows results from other sites. A review platform, publisher, court database, social profile or complaint site may need a different response from Google itself.'),
            ('Create a private next-step plan', 'Decide whether this needs a request to the website, a platform report, a Google form, or simply watching for now. The right route depends on the evidence, who runs the source, how sensitive it is, and timing.'),
        ],
        'faqs': [
            ('How urgent is a bad Google result?', 'It depends on where it ranks, what the snippet says, whether it appears for your exact name and whether clients, employers or customers are likely to search it.'),
            ('Does adding my own information help?', 'Accurate, current information about you, such as a work profile, gives people a fuller picture. Search engines decide what shows and in what order.'),
        ],
    },
    'negative-google-results-help': {
        'eyebrow': 'Negative Google results',
        'title': 'Negative Google Results: What You Can Do | Fix My Name Online',
        'h1': 'Negative Google results need evidence, strategy and patience',
        'description': 'What you can do about negative Google results for your name or business: old links, reviews, complaint pages and snippets. Free plan, letters you send yourself.',
        'intro': 'Negative Google results can feel urgent, but the strongest plan starts with evidence and classification. Some problems need a request to the website, some need a platform report, some need accurate information of your own, and some need careful watching before any action.',
        'sections': [
            ('Work from the search page outward', 'Record the exact search phrase, ranking position, title, snippet and source. Then inspect the page itself. Search-page damage can come from the title or snippet even when the underlying article is more balanced.'),
            ('Look for policy or accuracy issues', 'Privacy, impersonation, outdated information, fake reviews, harassment, copyright, defamation concerns or incorrect facts may each have different reporting or correction options.'),
            ('Avoid reputation spam', 'Thin fake profiles, copied articles and aggressive mass posting can look low-quality and may not solve the problem. The better route is truthful, useful information you publish yourself.'),
            ('Keep a record as things change', 'Note the date you sent each request, what came back, and how the search result looks afterwards. Pages and snippets can take weeks to change in Google after the website updates.'),
        ],
        'faqs': [
            ('Is negative Google result help confidential?', 'Fix My Name Online’s free check runs in your browser, so you can plan without telling anyone. Only publish what’s true and what you’re comfortable sharing.'),
            ('What should I keep a record of?', 'The exact search phrase, the links, dated screenshots, and what you’d like changed. You’ll use them in your own requests. There’s nothing to send to us.'),
        ],
    },
    'how-to-fix-bad-google-search-results': {
        'eyebrow': 'Fix bad Google search results',
        'title': 'How To Fix Bad Google Search Results | Fix My Name Online',
        'h1': 'How to fix bad Google search results without making it worse',
        'description': 'How to deal with bad Google search results safely: save evidence, find who runs the page, ask for one specific change, and check back.',
        'intro': 'There’s no single button for bad Google results. It’s a sequence: save the evidence, find who runs the page, ask them for one specific change, then ask Google to catch up. The wrong shortcut can make it louder.',
        'sections': [
            ('Find the source of the problem', 'Google may be showing a publisher page, review profile, social result, image, court database, complaint page or copied snippet. The source controls many of the next options.'),
            ('Check removal, update or correction routes', 'Depending on the facts, there may be a publisher request, Google outdated-content request, review report, privacy request or legal route. Some matters need a lawyer first, for example defamation, which has short time limits.'),
            ('Keep your own information accurate', 'Profiles and pages you control should be truthful, specific and current. A few genuine ones do more than lots of thin ones.'),
            ('Review results over weeks, not minutes', 'Search engines crawl and rank over time. A sensible plan watches what Google shows over time, instead of expecting instant change.'),
        ],
        'faqs': [
            ('Can I fix bad Google results myself?', 'You can start by saving evidence and checking official platform policies. Legal or professional advice is worth getting when the issue is sensitive, confusing, or affects your income.'),
            ('What should I avoid?', 'Avoid fake content, threats, public arguments, spammy posting and anyone promising they control Google.'),
        ],
    },
    'bad-search-results-for-my-name': {
        'eyebrow': 'Personal name search problem',
        'title': 'Bad Search Results for My Name — What Can I Do? | Fix My Name Online',
        'h1': 'Bad search results for your name? What to do first',
        'description': 'What to do when bad search results appear for your personal name, old name, business name, location or associated search terms.',
        'intro': 'When bad search results appear for your name, it feels personal. People may search before hiring, dating, renting or trusting you. Start by seeing exactly what they see, privately, before you do anything public.',
        'sections': [
            ('Search all name variations', 'Check your full name, old names, middle name, nicknames, professional name, business name, city, suburb, occupation and terms people may add when they are suspicious.'),
            ('Look at images, news and suggestions', 'It isn’t only the ordinary links. Image results, news tabs, autocomplete, people-also-search boxes and review snippets can shape first impressions.'),
            ('Decide what should stay private', 'You don’t need to share your whole story online. Anything you do publish about yourself should be true and something you’re comfortable having out there.'),
            ('Add accurate information you control', 'A current work profile, a business page or a short bio gives people searching your name something true and up to date to find.'),
        ],
        'faqs': [
            ('Will anyone know I used this?', 'No. The free check runs in your browser and nothing you type is sent to us. Any request you send is a normal letter from you.'),
            ('Can this help with associated names?', 'Yes. Associated names, old names, nicknames, business names and locations should be mapped because people often search more than one phrase.'),
        ],
    },
    'personal-online-reputation-repair': {
        'eyebrow': 'Personal reputation repair',
        'title': 'Personal Online Reputation Repair — Private Name Search Help | Fix My Name Online',
        'h1': 'Personal online reputation repair for name searches that feel unfair',
        'description': 'A private, self-service way to deal with bad Google results, old articles, images and reviews about you. Free plan and letters; you send everything yourself.',
        'intro': 'People search names before they decide who to trust. If the first page shows old, incomplete or damaging material, start by saving what you see, then ask the people who run each page for one specific change.',
        'sections': [
            ('Start with what people actually type', 'Search your full name, old names, nicknames, suburb, business and image results. The damaging result may only appear for one combination, but that one can still affect work, relationships or money.'),
            ('Keep private things private', 'You don’t have to explain your history in public. Accurate, current information, such as a work profile or a short bio, often helps more.'),
            ('Check which routes fit before you write', 'Some pages can be corrected by the publisher, reported to a platform, or refreshed in Google once they change. Others can’t. Knowing which applies keeps your request specific and stops you making claims that don’t fit.'),
            ('Check back now and then', 'Search your name again every month or two, including images and news. Note what has changed. Changes in Google can take weeks after a page is updated.'),
        ],
        'faqs': [
            ('Is personal online reputation repair confidential?', 'The free check runs in your browser, so nothing you type is sent to us. Nothing is published or sent unless you do it yourself.'),
            ('Can this help if I am not a public figure?', 'Yes. Everyday people are searched by employers, clients, landlords, partners and communities. Reputation harm is not limited to celebrities.'),
        ],
    },
    'remove-outdated-google-search-results': {
        'eyebrow': 'Outdated Google results',
        'title': 'Remove Outdated Google Search Results? Options and Limits | Fix My Name Online',
        'h1': 'Remove outdated Google search results: what can be checked first',
        'description': 'Options for outdated Google search results, old snippets, changed pages, removed content, old articles and search results that no longer reflect the current facts.',
        'intro': 'Outdated Google search results can make old information look current. Sometimes the source page changed, the snippet is stale, an old page was copied, or a result no longer reflects the current facts. The first step is evidence, not panic.',
        'sections': [
            ('Check the live page and Google snippet separately', 'A result can be outdated because the publisher page changed but Google still shows the old snippet. It can also be outdated because another site copied or republished old information. Each needs a different fix.'),
            ('Collect proof of what changed', 'Save the search phrase, result title, snippet, URL, date, screenshots, original publication date and any current page showing the updated facts. Outdated-content requests are stronger when the difference is clear.'),
            ('Know the limits of Google tools', 'Google may update or remove certain stale results under its policies, but it does not control every publisher page and does not erase every old reference. Publisher contact or legal advice may be needed in some cases.'),
            ('Keep accurate information about you current', 'While you wait for a reply, make sure the pages you control, like a work profile or business listing, are up to date. They give people searching your name the current picture.'),
        ],
        'faqs': [
            ('Can Google remove outdated results?', 'Sometimes. It depends on the source page, policy, evidence and whether the information is truly outdated or still publicly available.'),
            ('What do I need before I ask?', 'The link, the Google result, a dated screenshot, the search phrase, and proof of what has changed. If the page itself has already changed, Google’s Refresh Outdated Content tool only needs the link.'),
        ],
    },
    'reputation-monitoring-alerts': {
        'eyebrow': 'Keeping an eye on your name',
        'title': 'How to Keep an Eye on What Shows Up for Your Name | Fix My Name Online',
        'h1': 'How to keep an eye on what shows up for your name',
        'description': 'Simple, free ways to notice new search results about your name or business: what to search, how often, and which free alert tools to use.',
        'intro': 'Most people only find a problem result when someone mentions it. A few minutes every month or two, plus a couple of free alert tools, means you’re more likely to see something new before it costs you.',
        'sections': [
            ('Search more than your exact name', 'Problems often show up for your name plus a suburb, a job title, a business name, an old name, or words like “review” or “complaint”. Keep a short list of the searches a stranger might try, and check images and news too.'),
            ('Write down what you see', 'Note the date, the search, and the first page of results. Next time, you can see at a glance what’s new or what has changed.'),
            ('Use free alert tools', 'Google Alerts can email you when new pages mention your name. Google’s “Results about you” tool can tell you about new results showing your phone number, email or home address, where it’s available.'),
            ('Decide what, if anything, to do', 'Most new results need nothing. If one is wrong, out of date or breaks a platform’s rules, the free check gives you the steps, a letter and the official forms for that kind of result.'),
        ],
        'faqs': [
            ('Does Fix My Name Online offer alerts?', 'We offer NameWatch alerts, but new sign-ups are paused while we rebuild it. If you already subscribe, your alerts carry on. You can join the waitlist for one email when it’s back. In the meantime, Google Alerts and “Results about you” are free.'),
            ('Does keeping an eye on things remove results?', 'No. It just helps you notice changes sooner. Removing or correcting anything is decided by the website, the platform or Google, and any request is one you send yourself.'),
        ],
    },
    'online-reputation-management-for-business': {
        'eyebrow': 'Business reputation management',
        'title': 'Online Reputation Management for Business | Fix My Name Online',
        'h1': 'Online reputation management for businesses that get searched before they get trusted',
        'description': 'Online reputation management for businesses dealing with Google reviews, bad search results, complaint pages, outdated listings, brand snippets and trust problems.',
        'intro': 'Customers search before they call, book or buy. Business reputation management is about making sure Google, reviews and public profiles show the most accurate and useful picture of the business — while handling bad results carefully.',
        'sections': [
            ('Audit the branded search page', 'Check the business name, owner names, suburb, service terms, reviews, images, map results, complaint pages, directories and old listings. A business can lose trust before the customer ever reaches the website.'),
            ('Handle reviews with evidence and calm replies', 'Fake, unfair or malicious reviews need screenshots, notes on any pattern, the specific policy they break, and a calm public reply. Fighting in public usually makes the business look less trustworthy.'),
            ('Keep your own listings accurate', 'Your website, Google Business Profile and directory listings are the pages you control. Keep the details current and the descriptions plain and true.'),
            ('Ask for genuine reviews, fairly', 'Ask every customer, not just happy ones, and never offer anything in return. A steady stream of real reviews puts one bad one in context.'),
        ],
        'faqs': [
            ('Can I do anything about fake Google reviews?', 'You can report a review that breaks one of Google’s rules, with a short factual note, and reply calmly in public. Google decides whether it comes down.'),
            ('Can a small business do this itself?', 'Yes. Most of it is checking what shows up, reporting reviews that break a rule, replying calmly, and keeping your own listings accurate. The free check covers reviews and other results.'),
        ],
    },
    'what-shows-up-when-someone-googles-my-name': {
        'eyebrow': 'Name search check',
        'title': 'What Shows Up When Someone Googles My Name? | Fix My Name Online',
        'h1': 'What shows up when someone Googles your name?',
        'description': 'A private name-search checklist for people worried about what employers, clients, dates, landlords or customers see when they Google a name.',
        'intro': 'Most people don’t know what appears when someone Googles their name until something goes wrong. Searching your own name the way a stranger would shows you the first impression people get before they meet you, hire you, date you or rent to you.',
        'sections': [
            ('Search the way another person would', 'Use your full name, quoted name, old names, nicknames, suburb, business names, job title and risk words. Check web results, images, videos, news, reviews and suggestions.'),
            ('Look at snippets, not only links', 'The headline and snippet can cause the damage even if the page itself is old or more balanced. Screenshots help record exactly what others may be seeing.'),
            ('Sort what you find', 'For each result, ask: is it about me, is it accurate, is it current? Most will be fine. Note the ones that are wrong, out of date, or about someone else with your name.'),
            ('Choose a calm next step', 'Some results need nothing. Some need a polite correction request to the website. A review may need reporting and a calm reply. The free check gives you the steps for each kind.'),
        ],
        'faqs': [
            ('Should I Google myself often?', 'Occasionally, yes, but track results calmly. Repeated panic searching does not solve the issue; evidence and a plan do.'),
            ('Can Fix My Name Online search my name for me?', 'No. We don’t search Google or run a scan. You search your name, using the steps above, then tell the free check what you found. It gives you a plan, a letter you can edit and the official forms for that kind of result.'),
        ],
    },
    'google-review-defence-for-small-business': {
        'eyebrow': 'Small business review defence',
        'title': 'Google Review Defence for Small Business | Fix My Name Online',
        'h1': 'Google review defence for small businesses hit by unfair reviews',
        'description': 'Google review defence for small businesses facing fake, unfair, malicious, competitor, ex-employee or review-bombing attacks on Google.',
        'intro': 'For a small business, one unfair Google review can affect phone calls, bookings and trust. A public fight rarely helps. What does help is keeping evidence, checking the platform’s rules, replying calmly and getting more genuine reviews from real customers.',
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
        'title': 'How Do I Clean Up My Google Results? | Fix My Name Online',
        'h1': 'How do I clean up my Google results?',
        'description': 'Plain-English help for people asking how to clean up Google results for their name, business, old articles, bad reviews or embarrassing search results.',
        'intro': 'When people say they want to clean up their Google results, they usually mean one thing: the search page is giving people the wrong first impression. The safe way starts with evidence, source checks and a plan for better current information.',
        'sections': [
            ('Check exactly what needs cleaning up', 'Write down the search phrase, result title, snippet, URL, image and date. A bad headline, old snippet, review box or copied page can each need a different response.'),
            ('Do not make it louder', 'Avoid public arguments, repeated angry comments, threats or spammy posts. Those reactions can create more search signals around the same problem.'),
            ('Look for realistic update or removal routes', 'Some results can be updated by the publisher, removed under a platform’s rules, or refreshed in Google once the page changes. Others will stay, and then accurate information of your own matters more.'),
            ('Add accurate information people can trust', 'Profiles and pages you control, kept true and current, help people see a fuller picture over time.'),
        ],
        'faqs': [
            ('Can Google results be cleaned up instantly?', 'No. Search engines, publishers and platforms make their own decisions, and changes in Google take time even after a page is fixed.'),
            ('What should I save first?', 'The exact search phrase, the links and dated screenshots, plus a note of what worries you most. Then start the free check for the steps that fit.'),
        ],
    },
    'old-stuff-showing-up-on-google': {
        'eyebrow': 'Old stuff on Google',
        'title': 'Why Is Old Stuff Showing Up on Google? | Fix My Name Online',
        'h1': 'Why is old stuff showing up when I Google myself?',
        'description': 'What to do when old stuff, outdated pages, old articles, records or embarrassing results keep showing up on Google for your name.',
        'intro': 'Old results can feel unfair because Google can make an old chapter look fresh. The page may be old, copied, re-indexed, newly linked or shown with a snippet that misses the full context.',
        'sections': [
            ('Work out whether the page or snippet is old', 'Sometimes the website still shows the old information. Sometimes the website changed but Google is showing an old title or snippet. That difference matters.'),
            ('Save proof of the age and context', 'Keep screenshots, original dates, current facts, changed outcomes and the exact Google result. Evidence makes any request stronger.'),
            ('Check the official routes first', 'There may be a publisher correction, Google’s refresh tool, a privacy request or a platform process. Not every old page qualifies, so check which fits before you ask.'),
            ('Add the current version of the story', 'If old material stays online, accurate current information you control, like a work profile or business page, helps people see who you are now.'),
        ],
        'faqs': [
            ('Can old information be removed from Google?', 'Sometimes a result or snippet can be updated or removed under specific policies, but there is no universal right to erase every old result.'),
            ('Is this only for court records?', 'No. It can involve old articles, reviews, images, copied pages, complaint sites, directories or outdated profiles.'),
        ],
    },
    'someone-googled-me-and-found-something-bad': {
        'eyebrow': 'Someone searched me',
        'title': 'Someone Googled Me and Found Something Bad | Fix My Name Online',
        'h1': 'Someone Googled me and found something bad. What now?',
        'description': 'Private next steps when an employer, client, date, landlord or customer Googled your name and found something bad or embarrassing.',
        'intro': 'The worst part is often the silence afterwards: the job goes cold, the client hesitates, the date changes tone or the customer stops replying. Before reacting, map exactly what they may have seen.',
        'sections': [
            ('Do the same search they likely did', 'Search your full name, business name, city, job title, old names and obvious risk words. Check web, images, news, reviews and suggestions.'),
            ('Record the first impression', 'Most people only look for seconds. Save the headline, snippet, image, ranking position and source so you know what shaped their view.'),
            ('Choose a private response', 'Depending on the issue, the next move may be watching for changes, a request to the website, a platform report, a correction request, or accurate information of your own.'),
            ('Do not over-explain publicly', 'Public crisis posts can draw more attention. Keep it calm and private, and only publish what’s true.'),
        ],
        'faqs': [
            ('Should I contact the person who searched me?', 'Sometimes, but not always. First work out what they saw and whether it can be fixed. A calm, short explanation can help; a long defence usually doesn’t.'),
            ('Can I deal with this quietly?', 'Yes. The free check runs in your browser and nothing you type is sent to us. Any request you send is a private letter from you to the website.'),
        ],
    },
    'bad-review-costing-me-customers': {
        'eyebrow': 'Bad review damage',
        'title': 'A Bad Review Is Costing Me Customers | Fix My Name Online',
        'h1': 'A bad review is costing me customers. What can I do?',
        'description': 'Plain-English Google review defence for business owners worried that a fake, unfair or damaging review is costing calls, bookings and customers.',
        'intro': 'One bad review can change how strangers see a business before they ever call. What helps most is keeping evidence, checking the platform’s rules, a calm public reply and more genuine reviews from real customers.',
        'sections': [
            ('Save the review and the pattern', 'Record the review text, star rating, reviewer name, date, screenshots, booking history and any signs of fake, competitor, ex-staff or coordinated behaviour.'),
            ('Check whether it may breach policy', 'Google decides review removals. A useful report connects facts to possible policy issues instead of simply saying the review is unfair.'),
            ('Reply for future customers', 'A calm owner response can reassure the next person reading. Avoid threats, private details or emotional back-and-forth.'),
            ('Strengthen the rest of the search page', 'Better business pages, FAQs, photos, accurate profiles and review hygiene can reduce the damage of one hostile result.'),
        ],
        'faqs': [
            ('Can you delete a bad Google review?', 'No agency can directly delete Google reviews. The free plan walks you through documenting it, reporting it where it breaks a rule, and replying.'),
            ('Should I ask happy customers for reviews?', 'Follow platform rules. Genuine steady feedback is safer than pressure, incentives or a sudden suspicious spike.'),
        ],
    },
    'old-court-record-showing-on-google': {
        'eyebrow': 'Old court record search risk',
        'title': 'Old Court Record Showing on Google | Fix My Name Online',
        'h1': 'Old court record showing on Google? Start with context and evidence',
        'description': 'Private guidance when an old court record, tribunal page, appeal transcript or legal mention appears in Google search results for your name.',
        'intro': 'Old court and tribunal pages can be complicated. Some are public records, some are copied by other sites, some miss context, and some show in Google in a way that feels newly damaging.',
        'sections': [
            ('Identify the source and copy sites', 'Check whether Google shows an official court page, publisher article, database, scraper site or copied version. The source affects the options.'),
            ('Collect the missing context', 'Save dates, outcomes, appeal results, corrections, expungement or spent-conviction information where relevant, and screenshots of the search result.'),
            ('Know when to get legal advice first', 'Some matters need a lawyer first, especially if a case is still running, or you want to know whether a spent-conviction scheme or a non-publication order covers you. Legal Aid and community legal centres can help. For copies on other sites, the free check gives you a letter and the official links, and you send them yourself.'),
            ('Keep accurate information about you current', 'If the record stays online, an accurate work profile or business page gives people more to go on. Nobody controls what Google shows.'),
        ],
        'faqs': [
            ('Can old court records always be removed?', 'No. It depends on the record, where you live, who published it and whether any special rules apply. The free check shows the routes that may fit. If you’re not sure whether a spent-conviction scheme or non-publication order covers you, ask Legal Aid or a lawyer first.'),
            ('Is Fix My Name Online a law firm?', 'No. Fix My Name Online is not a law firm and doesn’t give legal advice. It gives you free, self-service plans and letters you send yourself.'),
        ],
    },
    'my-name-brings-up-embarrassing-results': {
        'eyebrow': 'Embarrassing name results',
        'title': 'My Name Brings Up Embarrassing Results | Fix My Name Online',
        'h1': 'My name brings up embarrassing results. What are my options?',
        'description': 'Private help for embarrassing Google results tied to your name, old names, photos, articles, comments, reviews or associated search terms.',
        'intro': 'Embarrassing search results can affect work, dating, family, money and confidence. The first step isn’t shame or panic. It’s seeing exactly what shows up, and working out what can realistically be done.',
        'sections': [
            ('List every search that triggers it', 'Check full name, old names, nicknames, locations, business names and image searches. Embarrassing results often appear only for certain combinations.'),
            ('Classify the result', 'It may be outdated, inaccurate, sensitive, review-related, image-related, copied, defamatory, private or simply lacking context. Each type has different options.'),
            ('Keep your response in proportion', 'Avoid public arguments, fake content or posting lots of new pages. A quiet, specific request to the website is usually safer.'),
            ('Add accurate information you control', 'A current bio, work profile or business page helps people see you as you are now.'),
        ],
        'faqs': [
            ('Will this make the embarrassing result disappear?', 'No responsible service can promise that. The free check shows the routes that may apply, and you decide what to do.'),
            ('Do I have to explain everything publicly?', 'No. Only publish information you’re comfortable sharing. Sensitive details can stay private unless there is a clear reason to publish.'),
        ],
    },
    'can-i-remove-my-name-from-google': {
        'eyebrow': 'Remove name from Google',
        'title': 'Can I Remove My Name From Google? | Fix My Name Online',
        'h1': 'Can I remove my name from Google?',
        'description': 'Can you remove your name from Google? What Google controls, what only the website can change, and the forms you can use yourself.',
        'intro': 'Many people ask if they can remove their name from Google. The honest answer is that some specific results can be removed, but Google is an index of pages across the web, not a single profile you can simply delete.',
        'sections': [
            ('Google usually shows pages from other websites', 'The result may come from a publisher, review site, social profile, directory, court database, forum or copied page. The source often controls the content.'),
            ('Some personal information has its own removal forms', 'Certain privacy, outdated-content, explicit image, doxxing, impersonation or policy issues may be reviewable. Evidence and exact URLs matter.'),
            ('Removing a name is different from fixing a search page', 'If a result can’t be removed, you can still ask for it to be corrected or updated, and make sure accurate, current information about you is easy to find.'),
            ('Plan before you contact anyone', 'A rushed message to a publisher or platform can backfire. Save the result and work out what to ask for first. The free check helps with that.'),
        ],
        'faqs': [
            ('Can Google delete every result about me?', 'No. Google and source websites make their own decisions, and public-interest material may remain online.'),
            ('What is the first step?', 'Save the links, screenshots and search phrases, then start the free check to get a plan.'),
        ],
    },
    'hide-bad-google-results': {
        'eyebrow': 'Hide bad Google results',
        'title': 'Can You Hide Bad Google Results? Safer Options Explained | Fix My Name Online',
        'h1': 'Can you hide bad Google results? Here is the safer way to think about it',
        'description': 'Want to hide bad Google results? What’s realistic, what to avoid, and the honest options you can use yourself.',
        'intro': 'People often search for how to hide bad Google results because they feel exposed. No honest service can hide, bury or control Google results. The better question is what can be corrected, updated, reported or balanced with true, current information.',
        'sections': [
            ('Avoid anyone promising secret control over Google', 'Guaranteed hiding, burying or instant removal claims are red flags. Search engines decide what ranks.'),
            ('Check whether that particular result can be removed', 'Some problems may qualify for correction, privacy review, outdated-content review, review reporting or publisher contact. Others will not.'),
            ('Add accurate information honestly', 'A few genuine, current profiles and pages you control give people a fuller view over time.'),
            ('Keep an eye on new results', 'Search your name, old names and business name every month or two. Free tools like Google Alerts can also tell you about new mentions.'),
        ],
        'faqs': [
            ('Is hiding bad results the same as removal?', 'No. Removal means a specific page is taken down, updated or dropped from search by whoever controls it. Nobody can hide results by other means.'),
            ('Does adding my own information help?', 'True, current information you control can help people see a fuller picture over time. Search engines decide what shows and in what order.'),
        ],
    },
    'what-do-employers-see-when-they-google-me': {
        'eyebrow': 'Employer search check',
        'title': 'What Do Employers See When They Google Me? | Fix My Name Online',
        'h1': 'What do employers see when they Google me?',
        'description': 'A private checklist for job seekers and professionals worried about what employers see when they Google a name before an interview or offer.',
        'intro': 'Employers, recruiters and clients often search before making a decision. If the results show old issues, embarrassing pages, articles, images or thin profiles, the first impression may form before you speak.',
        'sections': [
            ('Search your name like a recruiter', 'Use your full name, city, profession, old names, LinkedIn name, business history and any likely risk words. Check web, images, news and videos.'),
            ('Look for gaps as well as bad results', 'Sometimes the problem is not only a bad link. It’s the lack of accurate, current information that explains who you are now.'),
            ('Keep your professional information current', 'A clear bio, an up-to-date work profile and a business page if you have one make the search page more useful and current.'),
            ('Handle sensitive results quietly', 'If an old article, record or complaint appears, save it and check your options before trying to explain it in public.'),
        ],
        'faqs': [
            ('Should I clean my results before applying for jobs?', 'It is wise to check early. Changes take time, so checking your name before a major application can prevent surprises.'),
            ('Can this help professionals and business owners?', 'Yes. The same search risk affects executives, trades, consultants, creators, founders and everyday job seekers.'),
        ],
    },
    'fix-my-online-reputation-fast': {
        'eyebrow': 'Fast reputation help',
        'title': 'How Can I Fix My Online Reputation Fast? | Fix My Name Online',
        'h1': 'How can I fix my online reputation fast without making it worse?',
        'description': 'Urgent but careful steps for people wanting to fix their online reputation fast after bad Google results, reviews, articles or search surprises.',
        'intro': 'When a search result is hurting jobs, customers or relationships, it feels urgent. Fast does not mean reckless. The first 24 hours should be about evidence, triage and choosing the safest next step.',
        'sections': [
            ('First: freeze the evidence', 'Screenshot the results, URLs, snippets, reviews, images and dates before anything changes. Good evidence prevents guesswork.'),
            ('Second: stop risky reactions', 'Do not threaten, spam, fake reviews, make public accusations or publish panic posts. Those actions can become new reputation problems.'),
            ('Third: work out the right route', 'Decide whether the issue needs a request to the website, a platform report, watching for changes, accurate information of your own, or legal advice. Different problems need different tools.'),
            ('Fourth: update what you control', 'While you wait for replies, update your own profiles and pages so the current picture is easy to find.'),
        ],
        'faqs': [
            ('What can be done quickly?', 'Saving evidence, working out who decides, writing your requests and updating your own profiles can all happen today. Changes in Google usually take longer.'),
            ('Is urgent reputation help private?', 'Yes. The first step can be a private free check before any public move is made.'),
        ],
    },

}


GENERATED_SEO_SLUGS = []
LOW_VALUE_SEO_GUIDES = set()


def load_generated_seo_guides():
    """Load Hermes SEO OS generated guides without hand-editing server.py.

    Expected file: generated_seo_guides.json in the app root.
    Shape matches SEO_GUIDES: {slug: {eyebrow,title,h1,description,intro,sections,faqs}}.
    Invalid records are skipped so a bad generated page cannot take down the app.
    """
    path = BASE_DIR / 'generated_seo_guides.json'
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
        clean_slug = str(slug)
        SEO_GUIDES[clean_slug] = guide
        GENERATED_SEO_SLUGS.append(clean_slug)


load_generated_seo_guides()


def flag_generated_guide_duplicates():
    """Keep near-clone query pages out of indexing until they are uniquely rewritten."""
    seen = {}
    for slug in GENERATED_SEO_SLUGS:
        guide = SEO_GUIDES.get(slug) or {}
        section_text = '\n'.join(str(section[1]).strip().lower() for section in guide.get('sections', []) if isinstance(section, (list, tuple)) and len(section) > 1)
        if not section_text:
            continue
        fingerprint = hashlib.sha256(section_text.encode('utf-8')).hexdigest()
        if fingerprint in seen:
            LOW_VALUE_SEO_GUIDES.add(slug)
        else:
            seen[fingerprint] = slug


flag_generated_guide_duplicates()
# This spelling is an intentional 301 brand alias, never a sitemap document.
LOW_VALUE_SEO_GUIDES.update({'fix-my-name-on-line'})


def active_seo_guides():
    return [(slug, guide) for slug, guide in SEO_GUIDES.items() if slug not in LOW_VALUE_SEO_GUIDES]


@app.route('/when-google-makes-your-past-look-like-your-present')
def google_past_present_article():
    description = "Old court records, appeal transcripts, scraped pages and outdated search results can make a person's past look current. Fix My Name Online explains the human cost, and what you can do next."
    body = """
    <section class="page-head"><div class="wrap"><nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li><a href="/learn">Guides</a></li></ol></nav><p class="eyebrow" style="margin-top:20px">Essay · Fix My Name Online</p><h1 style="margin-top:8px">When Google makes your past look like your present</h1></div></section>
    <div class="wrap"><article class="prose essay">
      <img class="article-hero" src="/assets/old-records-google-past-present-hero-1200.jpg" width="1200" height="800" alt="A person looking at search results on a laptop late at night">
      <p>Most people who’ve been through something hard want the same thing afterwards: to get on with their lives.</p>
      <p>They go back to work, apply for better jobs, start again after a divorce, a court case, a business that failed, a public mistake, an allegation or a family falling-out. It takes years, and it’s mostly quiet work that nobody sees.</p>
      <p>Then one night they search their own name and the old story is back on the first page.</p>
      <p>Sometimes it’s an old court page or an appeal decision. Sometimes it’s a copy of a public record on a site they’ve never heard of, with a new address and a recent-looking date, so it looks like news.</p>
      <blockquote>To everyone else it’s one search result. To the person named, it can feel like being sent back to the worst year of their life.</blockquote>

      <h2>The case ends. The search result doesn’t.</h2>
      <p>Plenty of people have already dealt with whatever happened. Some were cleared. Some won an appeal. Some made a mistake years ago and have worked hard since to put it right. Some were never fairly described in the first place.</p>
      <p>A search result can’t show any of that. It shows a headline, a couple of lines of text and a date. If the date looks recent, something from ten years ago can read like it happened last month.</p>
      <p>That’s the part that feels unfair. The record may be accurate about the day it describes, and still give a stranger the wrong picture of who you are now.</p>

      <h2>Most of the damage happens quietly</h2>
      <p>Employers, clients and landlords rarely tell you they searched your name and changed their mind. The interview just doesn’t go anywhere, or the deal goes cold, or a new friend gets a bit distant.</p>
      <p>When it does come up, you’re explaining yourself to someone who has already formed a view from a few lines on a screen.</p>
      <blockquote>A stranger looks at the result for a few seconds. The person named can live with it for years.</blockquote>

      <h2>Old information can be made to look new</h2>
      <p>Court decisions, tribunal pages and public records can lawfully be online. That’s a separate question.</p>
      <p>The problem is that some sites copy old material, put it on a new page with your full name in the title, and Google treats it as a fresh page. The outcome of the case might be missing. The details might be wrong. The page might be a copy of a copy.</p>
      <p>Google doesn’t read the whole story. It ranks pages, and sometimes the page that ranks best is the one that’s least fair to you.</p>

      <h2>A name isn’t clickbait</h2>
      <p>Someone’s worst day shouldn’t keep being recycled for clicks. Their family shouldn’t keep stumbling across it, and an employer shouldn’t meet the old version before the real person in front of them.</p>
      <p>That doesn’t mean every record can come down. Some records are meant to stay public, and Google can’t be made to forget everything. Anyone who promises otherwise isn’t being straight with you.</p>
      <p>But you shouldn’t have to work it out on your own, either.</p>

      <h2>What to check first</h2>
      <p>If an old record, court page, review, article or copied profile is showing for your name, start by writing down exactly what’s there. Keep a note of:</p>
      <ul>
        <li>what shows up when you search your name</li>
        <li>the exact link and page title</li>
        <li>the short description Google shows under it</li>
        <li>the date Google shows, if any</li>
        <li>when the events actually happened</li>
        <li>whether the page is a copy of something else, or leaves out the outcome</li>
        <li>whether the site has a way to ask for a correction or removal</li>
        <li>whether one of Google’s own forms might apply, for example for an outdated result</li>
      </ul>
      <p>With that in hand, you can work out what to ask for. It might be a correction from the site, an update to an old article, a request to Google to refresh an out-of-date result, a privacy complaint, or advice from a lawyer if it’s defamatory or a case is still running.</p>
      <p>Which one fits depends on the facts.</p>

      <h2>Why we built this</h2>
      <p>Fix My Name Online exists because people get judged by a search result before they get the chance to explain, and because most people don’t know where to start.</p>
      <p>We can’t erase the past, and we won’t pretend to. What we can do is show you the steps that are open to you, give you letters you can edit, and point you to the official forms. You stay in charge and send everything yourself.</p>
      <p>If old records, court pages, reviews, articles or copied profiles are coming up for your name, start with the free check. It runs in your browser, and nothing you type is sent to us.</p>

      <div class="card stack-sm">
        <h2 class="h-sans" style="margin-top:0">Start with the free check</h2>
        <p>Pick what’s showing up, answer a few questions, and get a step-by-step plan with letters you can edit and the official forms. You send everything yourself.</p>
        <p class="btn-row"><a class="btn btn-primary" href="/self-service?problem=court">Start free check</a><a class="btn btn-secondary" href="/learn">More guides</a></p>
        <p class="small">Fix My Name Online is a self-service tool, not a law firm, and this isn’t legal advice. No one can promise a removal or a ranking.</p>
      </div>
    </article></div>
    """
    return page('When Google Makes Your Past Look Like Your Present', '<main id="main">' + body + '</main>', description=description, canonical_path='/when-google-makes-your-past-look-like-your-present', safety='au', crumbs=[('Guides', '/learn'), ('When Google makes your past look like your present', '/when-google-makes-your-past-look-like-your-present')])



FALSE_CLAIMS_SLUGS = ['false-information-about-me-online', 'remove-false-google-results', 'someone-posted-false-claims-about-me', 'false-allegations-showing-on-google', 'false-review-damaging-my-name']
DIY_OLD_ARTICLE_SLUGS = ['how-to-get-an-old-news-article-removed-australia', 'how-to-ask-a-publisher-to-correct-an-old-article', 'how-to-request-anonymisation-from-a-news-website', 'can-google-remove-an-article-about-me', 'publisher-will-not-remove-old-article', 'how-to-request-noindex-for-an-old-webpage', 'how-to-update-an-outdated-google-search-result', 'wrong-information-about-me-appears-on-google', 'old-court-article-appearing-in-google', 'how-to-contact-a-publisher-about-inaccurate-information']
BAD_GOOGLE_SLUGS = ['bad-results-on-google-what-to-do', 'what-to-do-if-google-results-are-bad', 'negative-google-results-help', 'how-to-fix-bad-google-search-results', 'bad-search-results-for-my-name', 'old-news-article-on-google', 'old-stuff-showing-up-on-google', 'remove-outdated-google-search-results'] + DIY_OLD_ARTICLE_SLUGS
JOB_PANIC_SLUGS = ['someone-googled-me-and-found-something-bad', 'what-shows-up-when-someone-googles-my-name', 'employer-googled-me-found-old-article', 'background-check-found-old-article', 'recruiter-found-negative-google-results']


def guide_cards_for(slugs):
    cards = []
    used = set()
    for slug in slugs:
        if slug in LOW_VALUE_SEO_GUIDES or slug in used:
            continue
        used.add(slug)
        g = SEO_GUIDES.get(slug)
        if not g:
            continue
        cards.append(f'''<div class="card"><span class="pill">{safe(g['eyebrow'])}</span><h2><a href="/{safe(slug)}">{safe(g['h1'])}</a></h2><p class="sub">{safe(g['description'])}</p><p><a class="btn btn2" href="/{safe(slug)}">Read guide →</a></p></div>''')
    return ''.join(cards)


def guide_card(slug):
    g = SEO_GUIDES[slug]
    return ('/' + slug, g['h1'], g['description'])


@app.route('/false-information-claims-online')
def false_information_claims_hub():
    cards = [guide_card(g) for g in FALSE_CLAIMS_SLUGS if g in SEO_GUIDES and g not in LOW_VALUE_SEO_GUIDES]
    cards += [('/help/old-news-articles', 'Old news stories: the plan', 'Who decides, what to ask for, and the official forms.'), ('/help/reviews', 'Reviews: the plan', 'How to report a review that breaks the rules, and reply.')]
    body = site_pages.collection(eyebrow='False information', h1='False information about you online? Start with evidence, not panic.',
        lede='Guides for false claims, false Google results, false allegations and false reviews.',
        short='Save the link, a dated screenshot and the exact words that are wrong. Separate facts from opinion. Then ask whoever runs the site to correct it, using the platform’s own process for reviews and posts. If it’s false and seriously harming you, talk to a lawyer soon: defamation has short time limits.',
        cards=cards, problem='not-sure')
    schema = [{'@type': 'CollectionPage', 'name': 'False information and false claims online', 'url': DOMAIN + '/false-information-claims-online'}]
    return page('False Information About Me Online: What You Can Do', body, 'What to do when false information, false claims, false Google results or false reviews appear for your name or business.',
                canonical_path='/false-information-claims-online', schema_items=schema, safety='au', crumbs=[('Guides', '/learn'), ('False information', '/false-information-claims-online')])


@app.route('/bad-google-results-help')
def bad_google_results_hub():
    cards = [guide_card(g) for g in dict.fromkeys(BAD_GOOGLE_SLUGS + JOB_PANIC_SLUGS) if g in SEO_GUIDES and g not in LOW_VALUE_SEO_GUIDES]
    body = site_pages.collection(eyebrow='Bad Google results', h1='Bad Google results: what you can do before it costs you work or peace of mind',
        lede='Old articles, outdated snippets, court mentions, reviews and results about someone else with your name.',
        short='Don’t argue in public first. Save the result, work out who runs the source, and ask them for one specific change. Once the page changes, ask Google to refresh it. If it can’t be changed, make sure accurate, current information about you is easy to find.',
        cards=cards, problem='not-sure')
    schema = [{'@type': 'CollectionPage', 'name': 'Bad Google results help', 'url': DOMAIN + '/bad-google-results-help'}]
    return page('Bad Google Results: What You Can Do', body, 'What to do about bad Google results for your name: old articles, outdated snippets, court mentions and reviews. Free step-by-step plan.',
                canonical_path='/bad-google-results-help', schema_items=schema, safety='au', crumbs=[('Guides', '/learn'), ('Bad Google results', '/bad-google-results-help')])


@app.route('/learn')
def learn_hub():
    by_problem = {p['key']: [] for p in plans.PROBLEMS}
    general = []
    for slug, g in active_seo_guides():
        key = site_pages.guide_problem(slug, g['intro'])
        (by_problem.get(key, general)).append(('/' + slug, g['h1'], g['description']))
    groups = [(p['hub_title'], '/help/' + p['hub'], [('/help/' + p['hub'], p['hub_title'] + ': the full plan', p['card'])] + by_problem[p['key']]) for p in plans.PROBLEMS]
    general = [('/' + s, site_pages.ACQUISITION[s]['h1'], site_pages.ACQUISITION[s]['description']) for s in site_pages.ACQUISITION] + general
    groups.append(('Before you start, and everything else', None, general))
    featured = [
        ('/google-your-name', 'Google your name: what to look for, and what to do', 'Search like an employer would, then deal with what you find.'),
        ('/fix-your-name-online', 'Fix your name online when Google shows the wrong story', 'A step-by-step approach to correcting what appears for your name.'),
        ('/how-to-fix-your-reputation-online', 'How to fix your reputation online without making it worse', 'Audit, evidence, the right requests, and keeping track.'),
        ('/bad-google-results-help', 'Bad Google results help', 'Old articles, snippets, court mentions and reviews.'),
        ('/false-information-claims-online', 'False information about you online', 'False claims, allegations and reviews.'),
        ('/when-google-makes-your-past-look-like-your-present', 'When Google makes your past look like your present', 'An essay on old records that won’t stay in the past.'),
    ]
    return page('Guides: what shows up when people search your name', site_pages.learn(groups, featured),
                'Plain-English guides to old news stories, people-search sites, fake profiles, court records, reviews and photos. Who decides, what to ask for, and what to try next.',
                canonical_path='/learn', current='guides')


def authority_guide_page(slug, title, description, h1, intro, sections, checklist, faqs):
    related = [('/help/' + p['hub'], p['hub_title']) for p in plans.PROBLEMS] + [('/fix-my-name-online', 'What is Fix My Name Online?')]
    body = site_pages.guide_page(slug=slug, h1=h1, eyebrow='Practical guide', intro=intro, sections=sections, faqs=faqs,
                                 related=related, checklist=checklist, problem='not-sure')
    schema_items = [
        {'@type': 'Article', '@id': f'{DOMAIN}/{slug}#article', 'headline': h1, 'description': description,
         'dateModified': site_shell.LAST_REVIEWED_ISO, 'mainEntityOfPage': f'{DOMAIN}/{slug}',
         'author': {'@id': DOMAIN + '/#organization'}, 'publisher': {'@id': DOMAIN + '/#organization'}},
        site_pages.faq_schema(faqs, f'{DOMAIN}/{slug}'),
    ]
    return page(title, body, description, canonical_path='/' + slug, schema_items=schema_items, safety='au',
                crumbs=[('Guides', '/learn'), (h1, '/' + slug)])


@app.route('/fix-your-name-online')
def fix_your_name_online_guide():
    return authority_guide_page(
        'fix-your-name-online',
        'Fix Your Name Online: Repair What Google Shows | Fix My Name Online™',
        'How to fix your name online when Google shows old, false, damaging or incomplete information: checking what shows up, keeping evidence, asking for corrections and practical next steps.',
        'Fix your name online: what to do when Google shows the wrong story',
        'If “fix your name” means changing a passport, licence or legal identity record, use the relevant government authority. If it means fixing what employers, clients, dates or customers see when they search your name online, begin with the search result page itself.',
        [
            ('1. Search the name the way another person would', 'Use the full name, common spelling, previous name, location, profession and business. Check normal web results, images, news, video and obvious combinations such as the name plus review, complaint, court or company. Record results rather than relying on memory.'),
            ('2. Separate factual errors from unwanted but accurate material', 'A wrong name, wrong date, copied page, misleading snippet or impersonation problem is handled differently from an accurate article or lawful public record. Label each item as false, outdated, incomplete, private, review-related, copied, or simply unflattering before deciding what to do.'),
            ('3. Check the source before asking Google', 'Google usually displays information from another page. A correction from the publisher, profile owner or platform can be more effective than starting with a general request to Google. Preserve the original page and the Google result because the wording may differ.'),
            ('4. Use the official route that matches the evidence', 'Possible routes include publisher correction, platform reporting, review policy, privacy tools, outdated-content refresh, account recovery or legal advice. Do not send every complaint to every channel. A focused request with exact URLs and evidence is easier to assess.'),
            ('5. Strengthen the current, accurate identity', 'When the search page is dominated by old or incomplete information, add useful current proof: an official profile, company page, clear biography, professional work, contact details and accurate articles. The goal is not fake praise; it is a fuller and verifiable current picture.'),
        ],
        [
            'Capture the exact Google query and a dated screenshot',
            'Save the result URL and the source-page URL separately',
            'Write the exact sentence, date, image or claim that is wrong or outdated',
            'Collect documents or source links that support a correction',
            'Avoid threats, fake reviews, duplicate pages and public arguments',
            'Search the same phrase again after any change or request',
        ],
        [
            ('Can I legally change my name through Fix My Name Online?', 'No. Legal identity changes belong with government authorities. FMNO focuses on what appears when a person or business name is searched online.'),
            ('Can Google correct my name in a search result?', 'Sometimes Google can refresh or review a result, but many corrections must first happen on the source website. The right route depends on where the wrong information originates.'),
            ('What if the bad page cannot be removed?', 'Write down the answer, try the complaint routes for your country, and make sure accurate, current information about you is easy to find, such as a work profile or business listing.'),
            ('How quickly can name-search results change?', 'A source page may update quickly, while Google recrawling and broader ranking movement can take longer. Timing depends on the source, crawl frequency and competition around the name.'),
        ],
    )


@app.route('/how-to-fix-your-reputation-online')
def how_to_fix_your_reputation_online_guide():
    return authority_guide_page(
        'how-to-fix-your-reputation-online',
        'How to Fix Your Reputation Online: A Practical Search Plan | FMNO',
        'A practical guide to fixing your reputation online: see what shows up, save evidence, ask the right people for the right thing, keep your own profiles accurate, and check back.',
        'How to fix your reputation online without making the problem worse',
        'Online reputation repair starts with diagnosis, not a burst of generic content. The useful question is not “How do I hide everything?” It is “Which results are wrong, outdated, removable, reviewable or missing important current context?”',
        [
            ('Audit what is actually visible', 'Search the exact personal or business name in a clean browser and record the first two pages, image results, review profiles and autocomplete phrases. Note which results are controlled by you, controlled by a platform, or published by an independent source.'),
            ('Prioritise by real-world harm', 'A page that appears first for the exact name usually deserves more attention than a result found only through an obscure phrase. Rank each issue by visibility, accuracy, source authority, urgency and the decision it may affect, such as employment, customers or finance.'),
            ('Choose correction before confrontation', 'If information is factually wrong, prepare a short request showing the exact error and reliable supporting evidence. If it is a review, use the platform policy and a calm owner response. Public threats and emotional arguments can create additional searchable material.'),
            ('Keep your own profiles accurate', 'Complete the profiles that are genuinely yours, such as a work profile or business listing, and keep your name and details consistent. When there’s little accurate, current information about you, one bad result stands out more.'),
            ('Check back over time', 'Search the same phrases every month or two and note what has changed. Record what you sent, when, and what came back, so you know what to do next.'),
        ],
        [
            'List the first 20 results for the exact name or business',
            'Mark each result accurate, inaccurate, outdated, private, review-related or unrelated',
            'Preserve URLs, screenshots, dates and source evidence',
            'Identify the correct publisher, platform or Google tool for each issue',
            'Complete official profiles and current business information consistently',
            'Search your name again each month or two and note what has changed',
        ],
        [
            ('What is the first step in online reputation repair?', 'Audit the exact search result page and preserve the evidence. Without that map, it is easy to work on content or requests that do not address the visible problem.'),
            ('Should I respond publicly to a negative result?', 'Only when a calm, factual reply serves a clear purpose, such as replying to a review. Most issues are better handled with a private request to the website or a report to the platform.'),
            ('Can my own profiles help?', 'Accurate, current profiles give people something true to find. Keep them genuine and complete rather than making lots of thin ones.'),
            ('Is this a one-time job?', 'Usually not. Pages change, and new ones appear. Checking back every month or two lets you see whether a request worked and catch anything new.'),
        ],
    )


@app.route('/i-have-bad-results-on-google')
@app.route('/i-have-bad-google-results')
@app.route('/my-google-results-are-bad')
@app.route('/what-can-i-do-about-bad-google-results')
@app.route('/bad-google-results-what-do-i-do')
def bad_google_results_variant_redirects():
    return redirect('/bad-results-on-google-what-to-do', code=301)


def not_found_page():
    response = Response(page('Page not found', site_pages.not_found(), 'That page isn’t here.', robots='noindex,nofollow', analytics=False), status=404, mimetype='text/html')
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@app.errorhandler(404)
def handle_not_found(_error):
    return not_found_page()


@app.route('/<slug>')
def seo_guide(slug):
    guide = SEO_GUIDES.get(slug)
    if not guide:
        return not_found_page()
    problem = site_pages.guide_problem(slug, guide['intro'])
    if slug in FALSE_CLAIMS_SLUGS:
        pool = FALSE_CLAIMS_SLUGS + ['old-news-article-on-google']
    elif slug in BAD_GOOGLE_SLUGS or slug in JOB_PANIC_SLUGS:
        pool = BAD_GOOGLE_SLUGS + JOB_PANIC_SLUGS
    else:
        pool = [g for g, _ in active_seo_guides()]
    related = [('/' + other, SEO_GUIDES[other]['h1']) for other in pool
               if other != slug and other in SEO_GUIDES and other not in LOW_VALUE_SEO_GUIDES][:5]
    hub = site_pages.PROBLEM_BY_KEY.get(problem)
    if hub:
        related.insert(0, ('/help/' + hub['hub'], hub['hub_title'] + ': the full plan'))
    body = site_pages.guide_page(slug=slug, h1=guide['h1'], eyebrow=guide['eyebrow'], intro=guide['intro'],
                                 sections=guide['sections'], faqs=guide['faqs'], related=related, problem=problem)
    robots = 'noindex,follow' if slug in LOW_VALUE_SEO_GUIDES else 'index,follow,max-image-preview:large'
    schema_items = [
        {'@type': 'Article', '@id': f'{DOMAIN}/{slug}#article', 'headline': guide['h1'], 'description': guide['description'],
         'dateModified': site_shell.LAST_REVIEWED_ISO, 'author': {'@id': DOMAIN + '/#organization'},
         'publisher': {'@id': DOMAIN + '/#organization'}, 'mainEntityOfPage': f'{DOMAIN}/{slug}'},
        site_pages.faq_schema(guide['faqs'], f'{DOMAIN}/{slug}'),
    ]
    crumbs = [('Guides', '/learn')] + ([(hub['hub_title'], '/help/' + hub['hub'])] if hub else []) + [(guide['h1'], '/' + slug)]
    return page(guide['title'], body, description=guide['description'], canonical_path='/' + slug, robots=robots,
                schema_items=schema_items, safety='au', crumbs=crumbs)


@app.route('/delete-me')
def delete_me_style_redirect():
    # "Delete me" searches are about people-search listings, not alerts.
    return redirect('/help/people-search-sites', code=301)


@app.route('/google-alerts-for-my-name')
def google_alerts_for_my_name_redirect():
    return redirect('/name-watch-alerts', code=301)


@app.route('/name-watch-alerts')
def name_watch_alerts_page():
    return page('NameWatch is coming back', site_pages.namewatch(),
                'NameWatch alerts are being rebuilt. New sign-ups are paused. Join the waitlist for one email when it’s back, or use the free check now.',
                canonical_path='/name-watch-alerts', analytics=False)


WAITLIST_DB = DATA_DIR / 'namewatch_waitlist.sqlite3'
EMAIL_RE = re.compile(r'^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,24}$')


@app.route('/name-watch-alerts/waitlist', methods=['GET', 'POST'])
def name_watch_waitlist():
    """Store one email for a single relaunch notice. Nothing is emailed now."""
    if request.method == 'GET':
        return redirect('/name-watch-alerts#waitlist', code=303)
    if request.content_length and request.content_length > 4096:
        return page('NameWatch waitlist', site_pages.namewatch(error='That was too much data. Please try again.'), canonical_path='/name-watch-alerts'), 413
    if (request.form.get('website') or '').strip():
        # Honeypot filled: answer as if it worked, store nothing.
        return page('You’re on the list', site_pages.namewatch_thanks(), canonical_path='/name-watch-alerts')
    email = (request.form.get('email') or '').strip().lower()[:254]
    if not EMAIL_RE.match(email):
        return page('NameWatch waitlist', site_pages.namewatch(error='Please enter a valid email address.'), canonical_path='/name-watch-alerts'), 400
    if request.form.get('consent') != 'yes':
        return page('NameWatch waitlist', site_pages.namewatch(error='Please tick the box so we know you’d like the email.'), canonical_path='/name-watch-alerts'), 400
    import sqlite3
    con = sqlite3.connect(str(WAITLIST_DB), timeout=10)
    try:
        WAITLIST_DB.chmod(0o600)
        con.execute('CREATE TABLE IF NOT EXISTS waitlist (email TEXT PRIMARY KEY, joined TEXT NOT NULL, consent TEXT NOT NULL)')
        con.execute('INSERT OR IGNORE INTO waitlist(email, joined, consent) VALUES(?,?,?)', (email, utc_now(), 'one relaunch email'))
        con.commit()
    finally:
        con.close()
    return page('You’re on the list', site_pages.namewatch_thanks(), canonical_path='/name-watch-alerts')


@app.route('/google-your-name')
def google_your_name_landing():
    return page('Google your name: what to look for, and what to do', site_pages.google_your_name(),
                'Google your name the way an employer would. What to look for, and a free step-by-step plan for anything that worries you.',
                canonical_path='/google-your-name', safety='au')


@app.route('/free-search-snapshot')
def ad_free_snapshot_form():
    # The Free Search Snapshot is now the free check. Old links and ads land there.
    return redirect('/self-service?from=snapshot', code=301)


@app.route('/free-snapshot')
@app.route('/snapshot')
def free_snapshot_short_redirect():
    return redirect('/self-service?from=snapshot', code=301)


@app.route('/namewatch')
def namewatch_short_redirect():
    return redirect('/name-watch-alerts', code=301)


@app.route('/name-watch')
def name_watch_short_redirect():
    return redirect('/name-watch-alerts', code=301)


def paid_next_steps_html(source='post_snapshot'):
    return f'''
    <div class="recommend"><h2>Keep the next step yours.</h2><p>Use the <a href="/self-service">free self-service desk</a> first. If an old article or bad link fits the stated scope, Single Action is US$19 once for one URL.</p><p><a class="btn" href="/diy-action?source={safe(source)}">See the US$19 DIY action →</a></p><p class="note">No subscription or human review. You verify facts and submit requests yourself.</p></div>'''


@app.route('/pricing')
def pricing():
    return page('Pricing: free to use, one optional extra', site_pages.pricing(),
                'The free check, plans, letters and tracker are free. One optional extra: a US$19 letter pack for one link, with a 7-day refund if unused.',
                canonical_path='/pricing', current='pricing')


@app.route('/how-it-works')
def how_it_works():
    return page('How it works', site_pages.how_it_works(),
                'Tell us what you found, get a step-by-step plan, send it yourself and keep track. What we do, what we don’t, and who decides what.',
                canonical_path='/how-it-works', current='how')


@app.route('/faq')
def faq():
    return page('Questions and answers', site_pages.faq_page(),
                'Plain answers about the free check, letters, results, privacy, refunds and legal help.',
                canonical_path='/faq', schema_items=[site_pages.faq_schema(site_pages.faq_items_flat(), DOMAIN + '/faq')])


@app.route('/help/<slug>')
def problem_hub(slug):
    hub = site_pages.HUB_BY_SLUG.get(slug)
    if not hub:
        return not_found_page()
    guide_titles = [(g, SEO_GUIDES[g]['h1']) for g in site_pages.HUB_GUIDES.get(slug, []) if g in SEO_GUIDES and g not in LOW_VALUE_SEO_GUIDES]
    title, _intro = site_pages.HUB_INTRO[slug]
    return page(f'{title}: what you can do', site_pages.hub(slug, guide_titles),
                f'{title}: who decides, what to ask for, the order to do it in, and the official forms. Free step-by-step plan with letters you can edit.',
                canonical_path='/help/' + slug, safety='au',
                crumbs=[('Guides', '/learn'), (hub['hub_title'], '/help/' + slug)])


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
    """Retired with the Free Search Snapshot (October 2026). Nothing is stored or emailed."""
    return jsonify({'ok': False, 'retired': True,
                    'error': 'This form has been replaced by the free check, which runs in your browser. Nothing you typed was saved.',
                    'redirect': '/self-service?from=snapshot'}), 410


@app.route('/snapshot-received')
def snapshot_received_light():
    ref = request.args.get('ref', '')
    ref_line = f'<p class="note">Reference: {safe(ref)}</p>' if ref else ''
    body = f'''<div class="card"><span class="pill">Earlier tool</span><h1>The Free Search Snapshot is now the free check.</h1><p class="sub">If you used the Snapshot before October 2026, your private link still opens what you entered then. For anything new, the free check gives you a plan, a letter you can edit and the official forms. It runs in your browser and nothing you type is sent to us.</p>{ref_line}<p><a class="btn" href="/self-service">Start the free check →</a></p></div>'''
    return page('The Snapshot is now the free check', body, robots='noindex,nofollow')


@app.route('/private-case-room/<queue_id>')
def private_case_room(queue_id):
    record = find_case_room(queue_id)
    supplied = (request.args.get('access_token') or '').strip()
    if not record or not supplied or not hmac.compare_digest(supplied, record.get('access_token', '')):
        body = '''<div class="card"><span class="pill err">Private link needed</span><h1>This page needs your private link.</h1><p class="sub">For privacy, it only opens from the link you were given when you used the earlier Free Search Snapshot. For anything new, use the free check.</p><p><a class="btn" href="/self-service">Start the free check</a></p></div>'''
        return page('Private link needed', body), 403

    previous_triage = record.get('triage') or {}
    triage = TRIAGE_NEXT_STEPS.get(previous_triage.get('key') or '', TRIAGE_NEXT_STEPS['repair-plan'])
    preview = record.get('intake_preview') or {}
    timeline = [
        ('1', 'What you told us', 'What you entered at the time is shown below. Nobody here has reviewed it or searched for you.'),
        ('2', 'A suggested route', 'The route above was picked from your answers by a simple matching rule, not from a search of Google.'),
        ('3', 'Your decision', 'Check the facts, read the official requirements, and decide whether to act.'),
        ('4', 'Your plan and tracker', 'The free check gives you a step-by-step plan, a letter you can edit and a tracker for anything you send.'),
    ]
    timeline_html = ''.join(f'<div class="card"><span class="pill">Step {n}</span><h2>{safe(title)}</h2><p class="sub">{safe(text)}</p></div>' for n, title, text in timeline)
    body = f'''
    <div class="card"><span class="pill ok">Earlier tool · Free Search Snapshot</span><h1>Your Snapshot answers</h1>
      <p class="sub">Hi {safe(record.get('name'))}. This is what you entered in the Free Search Snapshot, which has since been replaced by the free check. The suggestion below came from your answers, not a live Google search. Nothing has been sent to anyone.</p>
      <div class="grid"><div class="card"><h2>A route to consider</h2><p class="sub">{safe(triage.get('label'))}</p><p>{safe(triage.get('summary'))}</p><p><a class="btn" href="{safe(triage.get('url', '/self-service'))}">{safe(triage.get('cta', 'View next step'))} →</a></p><p class="note">The free check is enough for most people. Only buy the letter pack if it fits what you need.</p></div>
      <div class="card"><h2>Private reference</h2><p class="note">Reference: {safe(record.get('queue_id'))}<br>Case: {safe(record.get('case_id'))}<br>Status: {safe(record.get('status'))}</p></div></div>
      <h2 style="margin-top:22px">What you gave us</h2>
      <div class="card"><p><strong>Names/search:</strong><br>{safe(preview.get('names_to_check'))}</p><p><strong>Links/search clues:</strong><br>{safe(preview.get('problem_links'))}</p><p><strong>Goal:</strong><br>{safe(preview.get('goal'))}</p></div>
      <h2 style="margin-top:22px">Your next-step checklist</h2><div class="grid">{timeline_html}</div>
      <p><a class="btn btn2" href="/self-service">Start the free check →</a></p>
      <p class="note">Keep this link private: anyone with it can open this page. The free check doesn’t copy these details across. To have this record deleted, email admin@fixmynameonline.com. Fix My Name Online is run by Madison Jade Pty Ltd. Publishers, platforms and search engines make their own decisions.</p>
    </div>'''
    return page('Your Snapshot answers', body, 'Your answers from the earlier Free Search Snapshot.', canonical_path='/private-case-room')


@app.route('/app')
def free_snapshot_form():
    return redirect('/self-service?from=snapshot', code=301)


def desk_page(canonical_path):
    body = (BASE_DIR / 'self_service.html').read_text(encoding='utf-8')
    body = body.replace('{{DESK}}', site_pages.desk(plans.client_json())).replace('{{SCRIPT}}', site_shell.asset('self-service.js'))
    return page('Free check: what’s showing up for your name?', body,
                'Pick what’s showing up for your name and get a free step-by-step plan, letters you can edit and the official forms. Runs in your browser; nothing is sent to us.',
                canonical_path=canonical_path, analytics=False, desk=True, legacy=False, safety='au')


@app.route('/self-service')
def self_service():
    return desk_page('/self-service')


@app.route('/self-service/tracker')
def self_service_tracker():
    return desk_page('/self-service/tracker')


@app.route('/self-serve')
def self_serve_alias():
    return redirect('/self-service', code=301)


@app.route('/submit-snapshot', methods=['GET', 'POST'])
def submit_snapshot():
    """Retired with the Free Search Snapshot (October 2026).

    Old cached forms may still POST here. Nothing is read, stored or emailed:
    the visitor goes straight to the free check, which runs in their browser.
    """
    if request.method == 'GET':
        return redirect('/self-service', code=303)
    return redirect('/self-service?from=snapshot', code=303)


LEGACY_PACKAGE_NOTICE = (
    '<div class="card"><span class="pill">Older package</span><h1>This package is no longer offered.</h1>'
    '<p class="sub">Fix My Name Online is now a self-service tool. Nobody here works on cases, reviews links or contacts anyone for you, '
    'so we can’t provide this older package.</p>'
    '<p>If you paid for it, please email <a href="mailto:admin@fixmynameonline.com">admin@fixmynameonline.com</a> with the email you paid with. '
    'If we can’t provide what you paid for, you’re entitled to a refund under the Australian Consumer Law.</p>'
    '<p>In the meantime, the free check gives you a step-by-step plan, a letter you can edit and the official forms.</p>'
    '<p><a class="btn" href="/self-service">Start the free check</a></p></div>')


@app.route('/onboarding')
def onboarding_form():
    plan = request.args.get('plan', 'starter')
    plan_label = PLANS.get(plan, {}).get('name', plan.replace('-', ' ').title())
    session_id = (request.args.get('session_id') or '').strip()
    if plan in paid_actions.CATALOG:
        return redirect('/diy-action/start?session_id=' + session_id, code=303)
    if plan != 'sentinel' and not verify_paid_checkout(session_id, expected_tier=plan):
        return redirect('/self-service', code=302)
    if plan == 'sentinel':
        paid_session = verify_paid_checkout(session_id, expected_tier='sentinel')
        if not paid_session:
            return page('Payment verification required — FixMyNameOnline™', '<div class="card"><h1>Paid NameWatch checkout required.</h1><p class="sub">Private monitoring onboarding opens only after a verified NameWatch Alert™ payment.</p><p><a class="btn" href="/name-watch-alerts">View NameWatch Alert™</a></p></div>'), 402
        details = checkout_value(paid_session, 'customer_details', {}) or {}
        paid_email = checkout_value(details, 'email', '') or checkout_value(paid_session, 'customer_email', '') or ''
        body = f"""
        <div class="card"><span class="pill ok">Payment confirmed</span><h1>Activate NameWatch monitoring</h1><p class="sub">Tell us the names and phrases to search for. Our first search records what already shows up, and later searches tell you what’s new. We use what you enter here for NameWatch and nothing else.</p>
        <form method="post" action="/submit-onboarding" class="grid"><input type="hidden" name="plan" value="sentinel"><input type="hidden" name="session_id" value="{safe(session_id)}">
          <div><label>Your name</label><input name="name" required autocomplete="name"></div><div><label>Alert email</label><input type="email" name="email" required autocomplete="email" value="{safe(paid_email)}"></div>
          <div><label>Country / location context</label><input name="business" placeholder="Example: Australia, Sydney, New York"></div><div><label>Phone optional</label><input name="phone" autocomplete="tel"></div>
          <div class="full"><label>Exact names and associated names to monitor</label><textarea name="names" required placeholder="One per line: full name, old name, business name, nickname or distinctive search phrase"></textarea><div class="microcopy">Use the spelling people are most likely to search. Add only names you are authorised to monitor.</div></div>
          <div class="full"><label>Known links or search clues optional</label><textarea name="links" placeholder="Articles, profiles or reviews you already know about"></textarea></div>
          <div class="full"><label>Anything else that helps optional</label><textarea name="context" placeholder="Anything that helps distinguish you from people with a similar name"></textarea></div>
          <input type="hidden" name="avoid" value="">
          <div class="full"><button class="btn" type="submit">Activate NameWatch monitoring →</button><p class="note">We email you when a search finds something new. A new result isn’t necessarily bad, or newly published. See the <a href="/privacy#collect">privacy policy</a> for where this is kept.</p></div>
        </form></div>"""
        return page('Activate NameWatch Alert™ — FixMyNameOnline™', body, robots='noindex,nofollow')
    return page('This package is no longer offered', LEGACY_PACKAGE_NOTICE, robots='noindex,nofollow')


@app.route('/submit-onboarding', methods=['POST'])
def submit_onboarding():
    fields = ['plan', 'session_id', 'name', 'email', 'phone', 'business', 'names', 'links', 'context', 'avoid']
    data = {k: request.form.get(k, '').strip() for k in fields}
    if data.get('plan') in paid_actions.CATALOG:
        return redirect('/diy-action/start?session_id=' + data.get('session_id', ''), code=303)
    if data.get('plan') != 'sentinel' and not verify_paid_checkout(data.get('session_id'), expected_tier=data.get('plan')):
        return jsonify({'ok': False, 'error': 'A verified existing purchase is required.'}), 402
    if not data['name'] or not data['email']:
        return jsonify({'ok': False, 'error': 'Missing name/email'}), 400
    if data.get('plan') != 'sentinel':
        # Older managed packages are no longer offered: store nothing, email nothing.
        return page('This package is no longer offered', LEGACY_PACKAGE_NOTICE, robots='noindex,nofollow')
    if data.get('plan') == 'sentinel':
        paid_session = verify_paid_checkout(data.get('session_id'), expected_tier='sentinel')
        if not paid_session:
            return page('Payment verification required — FixMyNameOnline™', '<div class="card"><h1>Paid NameWatch checkout required.</h1><p class="sub">No monitoring file was activated because the Stripe payment could not be verified.</p></div>'), 402
        details = checkout_value(paid_session, 'customer_details', {}) or {}
        paid_email = (checkout_value(details, 'email', '') or checkout_value(paid_session, 'customer_email', '') or '').strip().lower()
        if paid_email and paid_email != data.get('email', '').strip().lower():
            return page('Checkout email mismatch — FixMyNameOnline™', '<div class="card"><h1>Use the email from the paid checkout.</h1><p class="sub">The monitoring email must match the verified Stripe checkout. Contact admin@fixmynameonline.com if it needs to be changed.</p></div>'), 400
        if not data.get('names'):
            return jsonify({'ok': False, 'error': 'Add at least one exact name or search phrase to monitor.'}), 400

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

    body = f"""<div class="card"><span class="pill ok">NameWatch started</span><h1>Thanks. NameWatch has your names.</h1><p class="sub">Our first search records what already shows up for them. After that, we email you when a search finds something new, and send a short status note when there’s nothing.</p><p class="note">Your reference: {safe(queue_item['id'])}<br>A new result isn’t necessarily bad, or newly published. It just means our search hadn’t seen it before.</p><a class="btn" href="/">Back to Fix My Name Online</a></div>"""
    return page('Onboarding received — FixMyNameOnline™', body)


def checkout_value(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    try:
        return obj.get(key, default)
    except Exception:
        return getattr(obj, key, default)


def verify_paid_checkout(session_id, expected_tier=None):
    """Return only a completed, paid Stripe Checkout Session for the expected FMNO tier."""
    session_id = (session_id or '').strip()
    if not session_id or not stripe.api_key:
        return None
    try:
        session = paid_actions.stripe_data(stripe.checkout.Session.retrieve(session_id))
    except Exception as exc:
        app.logger.warning('Paid checkout verification failed: %s', exc)
        return None
    payment_status = checkout_value(session, 'payment_status', '')
    status = checkout_value(session, 'status', '')
    metadata = checkout_value(session, 'metadata', {}) or {}
    tier = checkout_value(metadata, 'tier', '')
    if status != 'complete' or payment_status not in {'paid', 'no_payment_required'}:
        return None
    if expected_tier and tier != expected_tier:
        return None
    return session


def verify_diy_checkout(session_id, checkout_token=''):
    """No static-token or synthetic-payment bypass in application code."""
    return paid_actions.paid(sys.modules[__name__], session_id)


def diy_access_token(session_id):
    return hmac.new(approval_secret().encode('utf-8'), f'diy-action:{session_id}'.encode('utf-8'), hashlib.sha256).hexdigest()


@app.route('/diy-action')
def diy_action_sales():
    return paid_actions.sales(sys.modules[__name__])


@app.route('/diy-action/start')
def diy_action_start():
    return paid_actions.start(sys.modules[__name__])


@app.route('/diy-action/generate', methods=['POST'])
def diy_action_generate():
    return paid_actions.generate(sys.modules[__name__])


@app.route('/checkout/<tier>')
def checkout(tier):
    tier = {'name-watch': 'sentinel', 'namewatch': 'sentinel', 'name-watch-alerts': 'sentinel'}.get(tier, tier)
    if tier in paid_actions.CATALOG:
        return paid_actions.checkout(sys.modules[__name__], tier)
    if tier == 'sentinel':
        return redirect('/name-watch-alerts', code=302)
    if tier == 'free':
        return redirect('/app')
    if tier == 'concierge':
        return redirect('/self-service')
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
        success_url = (
            f'{DOMAIN}/diy-action/start?session_id={{CHECKOUT_SESSION_ID}}'
            if tier == 'diy-action'
            else f'{DOMAIN}/success.html?tier={tier}&session_id={{CHECKOUT_SESSION_ID}}'
        )
        session = stripe.checkout.Session.create(
            mode=plan['mode'],
            line_items=[{'price': price_id, 'quantity': 1}],
            success_url=success_url,
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
    session_id = (request.args.get('session_id') or '').strip()
    if tier in paid_actions.CATALOG:
        return redirect('/diy-action/start?session_id=' + session_id, code=303)
    if not verify_paid_checkout(session_id, expected_tier=tier):
        return paid_actions.error(sys.modules[__name__], 'We couldn’t match this page to a finished payment, and nothing new has been charged. If you bought the letter pack, get a new access link by email. For anything else, email admin@fixmynameonline.com from the address you paid with and we’ll look into it.', 402, heading='We couldn’t confirm that payment yet.')
    if tier == 'sentinel':
        onboarding_url = f'/onboarding?plan=sentinel&amp;session_id={safe(session_id)}'
        body = f"""<div class="card"><span class="pill ok">Payment received</span><h1>One step left: tell us which names to watch</h1><p class="sub">Your NameWatch payment went through. Next, add the names and phrases you want us to search for.</p><ol><li>Open the sign-up form.</li><li>Add each name or phrase people might search for.</li><li>Our first search records what already shows up.</li><li>After that, we email you when a search finds something new.</li></ol><p><a class="btn" href="{onboarding_url}">Activate NameWatch monitoring →</a></p><p class="note">A new result isn’t necessarily bad, or newly published. Search engines decide what appears.</p></div>"""
        return page('Activate NameWatch Alert™ — FixMyNameOnline™', body, robots='noindex,nofollow')
    return page('This package is no longer offered', LEGACY_PACKAGE_NOTICE, robots='noindex,nofollow')


@app.route('/cancel.html')
def cancel():
    return page('Checkout cancelled', '<div class="card"><h1>Checkout cancelled</h1><p class="sub">No payment was taken. The free check, plan and letters are still yours to use.</p><p><a class="btn" href="/self-service">Start free check</a> <a class="btn btn2" href="/diy-action">Back to the letter pack</a></p></div>')


@app.route('/contact')
def contact():
    return page('Contact', site_pages.contact(),
                'Email Fix My Name Online about the site, letter pack purchases, refunds, billing or privacy requests. We can’t review cases or give legal advice.',
                canonical_path='/contact')


@app.route('/billing')
def billing():
    portal = paid_actions.PUBLIC_BILLING['portal_login_url']
    return page('Billing and cancellation', f'<div class="card"><h1>Billing and cancellation</h1><p>Use Stripe’s secure email sign-in to view invoices, update a payment method or cancel an existing NameWatch subscription at the end of its paid period. New NameWatch sign-ups are paused.</p><p><a class="btn" href="{safe(portal)}" rel="noreferrer">Open secure Stripe billing →</a></p><p>The letter pack is a one-time purchase, not a subscription. For the seven-day unused-purchase refund, open your private workspace. <a href="/diy-action/recover">Get back into your workspace</a>.</p><p class="note">For a faulty product, statutory rights or an unresolved billing issue: admin@fixmynameonline.com.</p></div>', analytics=False, robots='noindex,nofollow')


@app.route('/questions')
def question_form():
    return redirect('/contact', code=301)


def legacy_question_form():
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
      <p style=\"font-size:12px;color:#666\">FixMyNameOnline™ · Madison Jade Pty Ltd<br>No ranking, removal, review-removal, de-indexing or platform outcome is guaranteed. We do not provide legal advice.</p>
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
    return page('Self-service guidance — FixMyNameOnline™', '<div class="card"><h1>Use the self-service desk.</h1><p>We no longer accept requests for personal case review through this form. No question or manual work item was created.</p><a class="btn" href="/self-service">Open free guidance</a></div>', analytics=False), 410


def legacy_submit_question():
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
    ga_id = (os.environ.get('FMNO_GA_MEASUREMENT_ID') or os.environ.get('GA_MEASUREMENT_ID') or '').strip()
    return page('Privacy policy', site_pages.privacy(ga_id),
                'What Fix My Name Online collects, tool by tool. The free check and tracker run in your browser; the letter pack and waitlist keep only what they need.',
                canonical_path='/privacy')


@app.route('/terms')
def terms():
    return page('Terms of use', site_pages.terms(),
                'Terms for Fix My Name Online’s self-service tools and the US$19 letter pack, including refunds and your Australian Consumer Law rights.',
                canonical_path='/terms')


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
        event = paid_actions.stripe_data(stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET))
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    if event['type'] in {'checkout.session.completed', 'checkout.session.async_payment_succeeded'}:
        session = event['data']['object']
        if (session.get('metadata') or {}).get('tier') in paid_actions.CATALOG:
            if session.get('payment_status') != 'paid':
                return '', 200
            return ('', 200) if paid_actions.webhook(sys.modules[__name__], session) else ('Payment verification unavailable', 503)
        if session.get('payment_status') != 'paid':
            return '', 200
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
        'private_case_rooms': read_jsonl_records(CASE_ROOMS_FILE),
        'concierge_transcripts': read_jsonl_records(CONCIERGE_TRANSCRIPTS_FILE),
        'diy_actions': read_jsonl_records(DIY_ACTIONS_FILE),
        'paid_action_workspaces': paid_actions.backup(sys.modules[__name__]),
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
    configured = bool(os.environ.get('CONCIERGE_API_KEY') or os.environ.get('LLM_API_KEY') or (os.environ.get('OPENROUTER_API_KEY') if provider == 'openrouter' else os.environ.get('ANTHROPIC_API_KEY') if provider == 'anthropic' else os.environ.get('MINIMAX_API_KEY')))
    return jsonify({'status': 'ok', 'service': 'fixmynameonline', 'version': 'launch-v54-self-serve-redesign', 'domain': DOMAIN, 'stripe_configured': bool(stripe.api_key), 'stripe_webhook_configured': bool(STRIPE_WEBHOOK_SECRET), 'diy_checkout_configured': bool(stripe.api_key and paid_actions.price_id(paid_actions.CATALOG['diy-single'])), 'namewatch_checkout_configured': False, 'namewatch_new_sales': 'paused', 'self_service_prices_usd': {'single': 19}, 'admin_token_configured': bool(os.environ.get('FMNO_ADMIN_TOKEN')), 'tracking_configured': bool(os.environ.get('FMNO_GA_MEASUREMENT_ID') or os.environ.get('GA_MEASUREMENT_ID') or os.environ.get('FMNO_META_PIXEL_ID') or os.environ.get('META_PIXEL_ID')), 'brevo_email_configured': bool(os.environ.get('BREVO_API_KEY') or os.environ.get('SENDINBLUE_API_KEY')), 'concierge_model_configured': configured, 'concierge_provider': provider, 'concierge_model': concierge_model_name(), 'concierge_voice_configured': concierge_voice_configured(), 'ava_avatar_configured': Path('assets/ava_concierge.mp4').exists(), 'click_tracking_configured': True})


paid_actions.register(sys.modules[__name__])


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
