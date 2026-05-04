"""
FixMyNameOnline™ — Flask Web Server
Landing page, Free Search Snapshot intake, Stripe checkout, and fulfilment-safe onboarding.

Copyright (c) 2026 MadisonJade Pty Ltd. All rights reserved.
FixMyNameOnline™ is a trademark of MadisonJade Pty Ltd.
"""
import html
import os
import json
from datetime import datetime
from pathlib import Path

import stripe
import requests
from flask import Flask, request, jsonify, send_from_directory, redirect

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
DATA_DIR = Path(os.environ.get('FMNO_DATA_DIR', 'data'))
DATA_DIR.mkdir(exist_ok=True)
LEADS_FILE = DATA_DIR / 'snapshot_leads.jsonl'
ONBOARDING_FILE = DATA_DIR / 'onboarding_submissions.jsonl'
FULFILMENT_QUEUE_FILE = DATA_DIR / 'fulfilment_queue.jsonl'

FROM_EMAIL = os.environ.get('FMNO_FROM_EMAIL', 'admin@fixmynameonline.com')
FROM_NAME = os.environ.get('FMNO_FROM_NAME', 'FixMyNameOnline')
INTERNAL_EMAIL = os.environ.get('FMNO_INTERNAL_EMAIL') or os.environ.get('ADMIN_EMAIL') or 'Elli35111@gmail.com'

PLANS = {
    'sentinel': {'name': 'Sentinel Alert™', 'price': 29, 'mode': 'subscription', 'env': 'STRIPE_PRICE_SENTINEL'},
    'removal-review': {'name': 'Removal Review™', 'price': 297, 'mode': 'payment', 'env': 'STRIPE_PRICE_REMOVAL_REVIEW'},
    'review-defence': {'name': 'Review Defence™', 'price': 497, 'mode': 'payment', 'env': 'STRIPE_PRICE_REVIEW_DEFENCE'},
    'starter': {'name': 'Starter™', 'price': 499, 'mode': 'subscription', 'env': 'STRIPE_PRICE_STARTER'},
    'pro': {'name': 'Pro™', 'price': 997, 'mode': 'subscription', 'env': 'STRIPE_PRICE_PRO'},
    'premium': {'name': 'Premium™', 'price': 2497, 'mode': 'subscription', 'env': 'STRIPE_PRICE_PREMIUM'},
}

TRIAGE_NEXT_STEPS = {
    'alerts': {
        'label': 'Sentinel Alert™ monitoring',
        'summary': 'This looks like a monitoring-first case: we should track mentions, searches, and new risk signals before deciding whether heavier work is needed.',
        'cta': 'View Sentinel Alert™',
        'url': '/checkout/sentinel',
        'priority': 'standard',
    },
    'removal-review': {
        'label': 'Removal Review™',
        'summary': 'This looks like it may need a private review of links, articles, images, snippets, or search results to check whether there is a valid action pathway.',
        'cta': 'View Removal Review™',
        'url': '/checkout/removal-review',
        'priority': 'high',
    },
    'review-defence': {
        'label': 'Review Defence™',
        'summary': 'This looks like a reviews/reputation trust case. The next step is to audit the review pattern and prepare a careful platform-appropriate response/reporting path.',
        'cta': 'View Review Defence™',
        'url': '/checkout/review-defence',
        'priority': 'high',
    },
    'repair-plan': {
        'label': 'Search repair plan',
        'summary': 'This looks like a broader search trust case. The next step is mapping what people see and building better truthful assets around the name or brand.',
        'cta': 'View Starter™',
        'url': '/checkout/starter',
        'priority': 'standard',
    },
    'high-risk': {
        'label': 'Private high-risk review',
        'summary': 'This looks sensitive or urgent. It should be handled privately before recommending a fixed package.',
        'cta': 'Start private onboarding',
        'url': '/onboarding?plan=concierge',
        'priority': 'urgent',
    },
}

BASE_STYLE = """
:root{--dark:#08090f;--card:#151824;--red:#d91f3d;--grey:#9aa2b6;--light:#e8ecf5;}
*{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at 20% 5%,rgba(217,31,61,.16),transparent 28%),var(--dark);color:white;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,sans-serif;line-height:1.5;padding:22px;}
a{color:#ff4d66}.wrap{max-width:880px;margin:0 auto}.card{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.11);border-radius:22px;padding:28px;box-shadow:0 20px 60px rgba(0,0,0,.28)}
.logo{font-weight:900;letter-spacing:.12em;color:var(--red);font-size:15px;margin-bottom:22px}.sub{color:var(--grey)}h1{font-size:clamp(32px,6vw,58px);line-height:1.02;margin:0 0 14px}h2{margin-top:0}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}.full{grid-column:1/-1}
label{display:block;font-weight:700;margin:14px 0 7px}input,select,textarea{width:100%;background:#0d1019;color:white;border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:13px 14px;font:inherit}textarea{min-height:105px}.btn{display:inline-block;background:linear-gradient(135deg,var(--red),#a81229);border:0;border-radius:13px;color:white;font-weight:800;padding:14px 20px;text-decoration:none;cursor:pointer;font-size:16px}.btn2{background:transparent;border:1px solid rgba(255,255,255,.22)}.note{font-size:13px;color:var(--grey)}.pill{display:inline-block;border:1px solid rgba(217,31,61,.35);background:rgba(217,31,61,.08);padding:7px 10px;border-radius:999px;color:#ffb0bd;font-size:13px;font-weight:700}.ok{color:#31d07a}.err{color:#ff6f85}.recommend{border:1px solid rgba(217,31,61,.35);background:rgba(217,31,61,.08);border-radius:18px;padding:20px;margin:22px 0}@media(max-width:720px){body{padding:14px}.grid{grid-template-columns:1fr}.card{padding:20px} }
"""


def utc_now():
    return datetime.utcnow().isoformat() + 'Z'


def safe(value):
    return html.escape(str(value or ''), quote=True)


def page(title, body):
    return f"""<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>{safe(title)}</title><style>{BASE_STYLE}</style></head><body><div class=\"wrap\"><div class=\"logo\">FIXMYNAMEONLINE™ · MADISONJADE PTY LTD</div>{body}</div></body></html>"""


def append_jsonl(path, payload):
    payload = dict(payload)
    payload.setdefault('created_at', utc_now())
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False) + '\n')
    return payload


def admin_authorized():
    token = os.environ.get('FMNO_ADMIN_TOKEN', '')
    supplied = request.headers.get('X-FMNO-Admin-Token') or request.args.get('token', '') or request.form.get('token', '')
    return bool(token and supplied and supplied == token)


def require_admin_json():
    if not admin_authorized():
        return jsonify({'ok': False, 'error': 'Unauthorized'}), 401
    return None


def safe_create_fulfilment_case(plan, customer, source, trigger):
    if not create_fulfilment_case:
        return None
    try:
        return create_fulfilment_case(plan, customer, source=source, trigger=trigger)
    except Exception as exc:
        app.logger.warning('Fulfilment case creation failed: %s', exc)
        return None


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


def send_snapshot_emails(data, triage, queue_item):
    customer_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#111\">
      <h1>Your Free Search Snapshot™ request is in</h1>
      <p>Hi {safe(data.get('name'))},</p>
      <p>We received your private FixMyNameOnline™ snapshot request.</p>
      <h2>Suggested next step: {safe(triage['label'])}</h2>
      <p>{safe(triage['summary'])}</p>
      <p>We’ll privately review what you submitted and come back with the safest next step. No removal, ranking, or platform result is guaranteed.</p>
      <p><a href=\"{DOMAIN}{triage['url']}\" style=\"background:#d91f3d;color:#fff;padding:12px 18px;text-decoration:none;border-radius:10px;display:inline-block\">{safe(triage['cta'])}</a></p>
      <p style=\"font-size:12px;color:#666\">Reference: {safe(queue_item['id'])}<br>FixMyNameOnline™ · MadisonJade Pty Ltd</p>
    </div>
    """
    internal_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:760px;margin:auto;color:#111\">
      <h1>New FMNO Free Snapshot lead</h1>
      <p><strong>Queue ID:</strong> {safe(queue_item['id'])}</p>
      <p><strong>Priority:</strong> {safe(queue_item['priority'])}</p>
      <p><strong>Recommendation:</strong> {safe(triage['label'])}</p>
      <pre style=\"background:#f5f5f5;padding:16px;border-radius:10px;white-space:pre-wrap\">{safe(json.dumps(data, indent=2, ensure_ascii=False))}</pre>
    </div>
    """
    return {
        'customer_email_sent': send_brevo_email(data.get('email'), data.get('name'), 'Your Free Search Snapshot™ request is in', customer_html),
        'internal_email_sent': send_brevo_email(INTERNAL_EMAIL, 'FMNO Admin', f"FMNO lead: {triage['label']} — {data.get('name', '')}", internal_html),
    }


def send_onboarding_emails(data, queue_item):
    plan_label = PLANS.get(data.get('plan'), {}).get('name', data.get('plan', 'Private onboarding'))
    customer_html = f"""
    <div style=\"font-family:Arial,sans-serif;max-width:620px;margin:auto;color:#111\">
      <h1>Private onboarding received</h1>
      <p>Hi {safe(data.get('name'))},</p>
      <p>We received your private onboarding details for {safe(plan_label)}.</p>
      <p>We’ll use this to review the names, links, reviews, search terms, context, and anything that must be handled carefully.</p>
      <p style=\"font-size:12px;color:#666\">Reference: {safe(queue_item['id'])}<br>FixMyNameOnline™ · MadisonJade Pty Ltd</p>
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
        'internal_email_sent': send_brevo_email(INTERNAL_EMAIL, 'FMNO Admin', f"FMNO onboarding: {plan_label} — {data.get('name', '')}", internal_html),
    }


@app.route('/')
def landing():
    return send_from_directory('.', 'landing_page_v2.html')


@app.route('/pricing')
def pricing():
    return redirect('/#pricing')


@app.route('/how-it-works')
def how_it_works():
    return redirect('/#how-it-works')


@app.route('/faq')
def faq():
    return redirect('/#faq')


@app.route('/app')
def free_snapshot_form():
    body = """
    <div class="card"><span class="pill">Free first step</span><h1>Start your Free Search Snapshot™</h1><p class="sub">Tell us what people may search and what worries you. We’ll use this to point you toward the right next step: alerts, removal review, review defence, or repair.</p>
    <form method="post" action="/submit-snapshot" class="grid">
      <div><label>Your name</label><input name="name" required autocomplete="name"></div>
      <div><label>Email</label><input name="email" type="email" required autocomplete="email"></div>
      <div><label>Phone optional</label><input name="phone" autocomplete="tel"></div>
      <div><label>Best describes this</label><select name="case_type"><option>Personal name / old Google results</option><option>Business name / bad search results</option><option>Fake or malicious Google reviews</option><option>Old news article or court mention</option><option>Associated name / old name / nickname</option><option>High-risk private case</option></select></div>
      <div class="full"><label>Names/businesses to check</label><textarea name="names_to_check" placeholder="Your full name, old names, nicknames, business names, associated names, locations..."></textarea></div>
      <div class="full"><label>Bad links, review links, article titles, or search terms if you have them</label><textarea name="problem_links" placeholder="Paste URLs or write things like: John Smith court, Jane Smith review, business name complaint..."></textarea></div>
      <div class="full"><label>What outcome are you hoping for?</label><textarea name="goal" placeholder="Example: I want to know if this can be removed, or I need better results showing before people find the bad link."></textarea></div>
      <div class="full"><button class="btn" type="submit">Submit Free Snapshot →</button> <a class="btn btn2" href="/">Back</a><p class="note">Private intake. No public case disclosure. No rankings/removals guaranteed.</p></div>
    </form></div>"""
    return page('Free Search Snapshot™ — FixMyNameOnline™', body)


@app.route('/submit-snapshot', methods=['POST'])
def submit_snapshot():
    data = {k: request.form.get(k, '').strip() for k in ['name', 'email', 'phone', 'case_type', 'names_to_check', 'problem_links', 'goal']}
    if not data['name'] or not data['email']:
        return page('Missing details', '<div class="card"><h1 class="err">Missing details</h1><p>Please enter your name and email.</p><a class="btn" href="/app">Go back</a></div>'), 400

    triage = triage_snapshot(data)
    queue_item = make_queue_item('free_snapshot', data, triage)
    append_jsonl(LEADS_FILE, {**data, 'triage': triage, 'queue_id': queue_item['id']})
    append_jsonl(FULFILMENT_QUEUE_FILE, queue_item)

    send_telegram_alert('FMNO Free Search Snapshot lead', {
        'queue_id': queue_item['id'],
        'name': data.get('name'),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'case_type': data.get('case_type'),
        'recommendation': triage.get('label'),
        'priority': queue_item.get('priority'),
    })
    email_status = send_snapshot_emails(data, triage, queue_item)
    app.logger.info('Snapshot %s email status: %s', queue_item['id'], email_status)

    body = f"""
    <div class="card"><span class="pill ok">Received</span><h1>Your Free Search Snapshot™ request is in.</h1>
      <p class="sub">Thanks {safe(data['name'])}. We saved your details. The next step is a private review of the names, links, reviews, or search terms you gave us.</p>
      <div class="recommend"><h2>Suggested next step: {safe(triage['label'])}</h2><p>{safe(triage['summary'])}</p><p><a class="btn" href="{safe(triage['url'])}">{safe(triage['cta'])} →</a></p></div>
      <h2>What happens next</h2><ol><li>We look at what people may see when they search.</li><li>We identify if this looks like alerts, removal review, review defence, repair, or a private high-risk review.</li><li>If there is a paid next step, you choose it — no pressure.</li></ol>
      <p class="note">Private reference: {safe(queue_item['id'])}</p><p><a class="btn btn2" href="/">Back to site</a></p>
    </div>"""
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
    app.logger.info('Onboarding %s email status: %s', queue_item['id'], email_status)

    body = f"""<div class="card"><span class="pill ok">Received</span><h1>Private onboarding received.</h1><p class="sub">Your details are saved. We’ll use this to begin the correct review/repair path.</p><p class="note">Private reference: {safe(queue_item['id'])}{'<br>Fulfilment case: ' + safe(case.get('id')) if case else ''}</p><a class="btn" href="/">Back to site</a></div>"""
    return page('Onboarding received — FixMyNameOnline™', body)


@app.route('/checkout/<tier>')
def checkout(tier):
    if tier == 'free':
        return redirect('/app')
    if tier == 'concierge':
        return redirect('/onboarding?plan=concierge')
    if tier not in PLANS:
        return jsonify({'error': 'Invalid plan'}), 400
    if not stripe.api_key:
        return jsonify({'error': 'Stripe is not configured'}), 500
    plan = PLANS[tier]
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
    return page('Contact — FixMyNameOnline™', '<div class="card"><h1>Contact FixMyNameOnline™</h1><p>Email: <a href="mailto:admin@fixmynameonline.com">admin@fixmynameonline.com</a></p><p class="sub">Private reputation repair operated by MadisonJade Pty Ltd.</p></div>')


@app.route('/privacy')
def privacy():
    return page('Privacy Policy — FixMyNameOnline™', '<div class="card"><h1>Privacy Policy</h1><p class="sub">Draft launch policy: information submitted through FixMyNameOnline™ is used to assess and deliver private reputation services, respond to enquiries, process payments, and maintain case records. We do not publicly disclose client cases without consent.</p><p>Contact: admin@fixmynameonline.com</p></div>')


@app.route('/terms')
def terms():
    return page('Terms — FixMyNameOnline™', '<div class="card"><h1>Terms & Disclaimer</h1><p class="sub">FixMyNameOnline™ provides reputation review, monitoring, content, documentation, and platform-request support. Search engines, publishers, platforms, and courts make their own decisions. We do not guarantee removals, review removals, rankings, de-indexing, or specific outcomes. Legal advice must be obtained from a qualified lawyer.</p></div>')


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
        tier = session.get('metadata', {}).get('tier') or 'starter'
        customer_email = session.get('customer_email') or session.get('customer_details', {}).get('email', '')
        case = safe_create_fulfilment_case(tier, {'email': customer_email}, {'stripe_session_id': session.get('id'), 'tier': tier}, 'stripe_checkout')
        send_telegram_alert('FMNO checkout completed', {'customer_email': customer_email, 'tier': tier, 'session': session.get('id'), 'case_id': case.get('id') if case else ''})
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
    <div class='card' style='margin:16px 0'><form method='get' class='row'><input type='hidden' name='token' value='{safe(request.args.get('token'))}'><select name='status'><option value=''>All statuses</option><option>blocked</option><option>intake_ready</option><option>executing</option><option>qc_pending</option><option>complete</option></select><select name='plan'><option value=''>All plans</option><option>sentinel</option><option>removal-review</option><option>review-defence</option><option>starter</option><option>pro</option><option>premium</option><option>concierge</option></select><button>Filter</button><a class='btn btn2' href='/admin/fulfilment?{token_qs()}'>Reset</a></form></div>
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
          {notes_html}{output_html}{actions}
        </div>
        """)
    source = safe(json.dumps(case.get('source', {}), indent=2, ensure_ascii=False))
    notes = ''.join([f"<div class='small muted'>• {safe(n.get('note'))} — {safe(n.get('author'))} / {safe(n.get('type'))}</div>" for n in case.get('notes', [])[-8:]])
    active_html = ''.join([f"<li>{safe(a.get('task_id'))}: {safe(a.get('title'))} — {safe(a.get('agent'))}</li>" for a in active]) or '<li>No active tasks</li>'
    body = f"""
    <div class='row' style='margin-bottom:14px'><a class='btn btn2' href='/admin/fulfilment?{token_qs()}'>← Back</a>{status_badge(case.get('status'))}<span class='mono'>{safe(case_id)}</span></div>
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


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'fixmynameonline', 'version': 'launch-v5-worker-agents', 'domain': DOMAIN})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
