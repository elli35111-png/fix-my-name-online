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

    send_telegram_alert('FMNO paid/private onboarding', {
        'queue_id': queue_item['id'],
        'plan': plan_label,
        'name': data.get('name'),
        'email': data.get('email'),
        'phone': data.get('phone'),
        'business': data.get('business'),
    })
    email_status = send_onboarding_emails(data, queue_item)
    app.logger.info('Onboarding %s email status: %s', queue_item['id'], email_status)

    body = f"""<div class="card"><span class="pill ok">Received</span><h1>Private onboarding received.</h1><p class="sub">Your details are saved. We’ll use this to begin the correct review/repair path.</p><p class="note">Private reference: {safe(queue_item['id'])}</p><a class="btn" href="/">Back to site</a></div>"""
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
        send_telegram_alert('FMNO checkout completed', {'customer_email': session.get('customer_email'), 'tier': session.get('metadata', {}).get('tier'), 'session': session.get('id')})
    return '', 200


@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'fixmynameonline', 'version': 'launch-v2-automation', 'domain': DOMAIN})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
