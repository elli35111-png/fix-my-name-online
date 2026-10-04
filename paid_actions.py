"""Bounded, customer-controlled paid actions. No publisher requests are submitted."""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from flask import request, redirect, Response, jsonify

CATALOG = {
    'diy-single': {'name': 'Single Action', 'amount': 1900, 'cap': 1, 'env': 'STRIPE_PRICE_DIY_SINGLE'},
    'diy-pack': {'name': 'Action Pack', 'amount': 4900, 'cap': 5, 'env': 'STRIPE_PRICE_DIY_PACK'},
    'diy-action': {'name': 'Legacy DIY Workspace', 'amount': 4900, 'cap': 1, 'env': 'STRIPE_PRICE_DIY_ACTION'},
}
COOKIE = 'fmno_action_access'
PUBLIC_BILLING = json.loads((Path(__file__).with_name('billing_catalog.json')).read_text())
LIMITS = {'name': 160, 'country_state': 160, 'target_url': 2000, 'problem_summary': 3000,
          'evidence_summary': 5000, 'correct_information': 3000, 'draft': 16000,
          'notes': 8000, 'reference': 300, 'followup': 10, 'status': 32}
OUTCOMES = {'correct': 'correct or update the page', 'anonymise': 'anonymise identifying details',
            'noindex': 'consider noindex for search discovery', 'remove': 'remove the page'}
ISSUES = {'outdated': 'outdated information', 'inaccurate': 'inaccurate or incomplete information',
          'privacy': 'personal information', 'wrong-person': 'name confusion'}
STATUSES = {'preparing', 'submitted', 'waiting', 'closed'}


@contextmanager
def db(s):
    path = s.DATA_DIR / 'paid_actions.sqlite3'
    con = sqlite3.connect(str(path), timeout=20)
    path.chmod(0o600)
    con.row_factory = sqlite3.Row
    con.executescript('''CREATE TABLE IF NOT EXISTS workspaces (
      id TEXT PRIMARY KEY, session_id TEXT UNIQUE NOT NULL, tier TEXT NOT NULL,
      cap INTEGER NOT NULL, email TEXT NOT NULL, created TEXT NOT NULL, notified INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE IF NOT EXISTS actions (
      id TEXT PRIMARY KEY, workspace TEXT NOT NULL, url TEXT NOT NULL, payload TEXT NOT NULL,
      UNIQUE(workspace,url));
      CREATE TABLE IF NOT EXISTS recovery_limits (key TEXT PRIMARY KEY, used TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS refund_state (workspace TEXT PRIMARY KEY, state TEXT NOT NULL);''')
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def secret(s):
    value = os.environ.get('FMNO_APPROVAL_SECRET') or os.environ.get('FMNO_ADMIN_TOKEN') or ''
    if len(value) < 24:
        raise RuntimeError('Private workspace signing is not configured')
    return value


def price_id(plan):
    return os.environ.get(plan['env']) or PUBLIC_BILLING.get(plan['env'], '')


def sign(s, purpose, value):
    return hmac.new(secret(s).encode(), f'{purpose}:{value}'.encode(), hashlib.sha256).hexdigest()


def private(s, title, body, status=200):
    response = Response(s.page(title + ' — FixMyNameOnline™', body, robots='noindex,nofollow', analytics=False), status=status, mimetype='text/html')
    response.headers.update({'Cache-Control': 'no-store, private', 'X-Robots-Tag': 'noindex, nofollow',
                             'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'})
    return response


def error(s, text, status=400):
    return private(s, 'Your action workspace', '<div class="card"><h1>Let’s check that.</h1><p>' + s.safe(text) + '</p><p><a class="btn" href="/diy-action/workspace">Return to workspace</a> <a href="/self-service#safety">Free guidance and safety options</a></p></div>', status)


def paid(s, sid):
    if not re.fullmatch(r'cs_(live|test)_[A-Za-z0-9_]{5,240}', sid or '') or not s.stripe.api_key:
        return None
    try:
        row = s.stripe.checkout.Session.retrieve(sid, expand=['line_items'])
        tier = (row.get('metadata') or {}).get('tier')
        plan = CATALOG.get(tier)
        items = (row.get('line_items') or {}).get('data', [])
        if not (plan and row.get('status') == 'complete' and row.get('payment_status') == 'paid'
                and row.get('mode') == 'payment' and row.get('currency') == 'usd'
                and row.get('amount_total') == plan['amount'] and len(items) == 1
                and items[0].get('quantity') == 1
                and (items[0].get('price') or {}).get('id') == price_id(plan)
                and price_id(plan)):
            return None
        pi = row.get('payment_intent')
        if not pi:
            return None
        refunds = s.stripe.Refund.list(payment_intent=pi, limit=100)
        if refunds.get('has_more') or any(x.get('status') in {'succeeded', 'pending', 'requires_action'} for x in refunds.get('data', [])):
            return None
        return row
    except Exception:
        s.app.logger.warning('Paid action verification unavailable; access remains closed')
        return None


def ensure_workspace(s, row):
    tier = row['metadata']['tier']
    with db(s) as con:
        con.execute('INSERT OR IGNORE INTO workspaces(id,session_id,tier,cap,email,created) VALUES(?,?,?,?,?,?)',
                    (secrets.token_hex(24), row['id'], tier, CATALOG[tier]['cap'],
                     ((row.get('customer_details') or {}).get('email') or row.get('customer_email') or '').lower(), s.utc_now()))
        workspace = dict(con.execute('SELECT * FROM workspaces WHERE session_id=?', (row['id'],)).fetchone())
        # Import existing one-URL purchases without modifying old JSONL evidence.
        if tier == 'diy-action' and not con.execute('SELECT 1 FROM actions WHERE workspace=?', (workspace['id'],)).fetchone():
            legacy = [x for x in s.read_jsonl_records(s.DIY_ACTIONS_FILE) if x.get('session_id') == row['id']]
            if legacy:
                item = legacy[-1]
                target = item.get('target_url', '')
                if valid_url(target):
                    payload = {key: str(item.get(key, ''))[:limit] for key, limit in LIMITS.items()}
                    payload.update(status='preparing', followup='', notes='', reference='', followup_draft='Please confirm receipt of my earlier request and advise the status.')
                    con.execute('INSERT INTO actions VALUES(?,?,?,?)', (secrets.token_hex(12), workspace['id'], target, json.dumps(payload)))
        return workspace


def authenticated(s):
    cookie = request.cookies.get(COOKIE, '')
    parts = cookie.split('.')
    if len(parts) != 3 or not re.fullmatch('[a-f0-9]{48}', parts[0]):
        return None
    wid, expiry, sig = parts
    if not expiry.isdigit() or int(expiry) < int(time.time()):
        return None
    if not hmac.compare_digest(sig, sign(s, 'access', wid + '.' + expiry)):
        return None
    with db(s) as con:
        row = con.execute('SELECT * FROM workspaces WHERE id=?', (wid,)).fetchone()
        refund_row = con.execute('SELECT state FROM refund_state WHERE workspace=?', (wid,)).fetchone()
        if refund_row and refund_row['state'] == 'confirmed':
            return None
        return dict(row) if row else None


def csrf_ok(s, workspace):
    return hmac.compare_digest(request.form.get('csrf', ''), sign(s, 'csrf', workspace['id']))


def valid_url(target):
    try:
        parsed = urlparse(target)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password or re.search(r'[\s\x00-\x1f]', target):
            return False
        if '.' not in parsed.hostname or parsed.hostname.endswith(('.local', '.internal')):
            return False
        try:
            if not ipaddress.ip_address(parsed.hostname).is_global:
                return False
        except ValueError:
            pass
        return True
    except ValueError:
        return False


def sales(s):
    body = (Path(__file__).with_name('single_action.html')).read_text(encoding='utf-8')
    return s.page('Single DIY Action — US$19 once', body, canonical_path='/diy-action')


def checkout(s, tier):
    if tier == 'diy-pack':
        return redirect('/diy-action', code=302)
    tier = 'diy-single' if tier == 'diy-action' else tier
    plan = CATALOG[tier]
    try:
        secret(s)
        pid = price_id(plan)
        p = s.stripe.Price.retrieve(pid)
        if not (p.get('active') and p.get('currency') == 'usd' and p.get('unit_amount') == plan['amount'] and p.get('type') == 'one_time'):
            raise ValueError('Price mismatch')
        row = s.stripe.checkout.Session.create(mode='payment', line_items=[{'price': pid, 'quantity': 1}],
            success_url=s.DOMAIN + '/diy-action/start?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=s.DOMAIN + '/diy-action', allow_promotion_codes=False,
            customer_creation='always', metadata={'tier': tier, 'plan_name': plan['name'], 'product_version': 'selfserve-v1'},
            payment_intent_data={'metadata': {'tier': tier, 'brand': 'FixMyNameOnline'}},
            custom_text={'submit': {'message': 'One-time self-service documentation tool. You verify facts and submit requests yourself. No human review or external submissions included.'}})
        return redirect(row['url'], code=302)
    except Exception:
        s.app.logger.warning('Paid action checkout unavailable; no payment created or confirmed')
        return error(s, 'Checkout is temporarily unavailable. No payment has been confirmed. The free self-service desk is still available.', 503)


def start(s):
    row = paid(s, request.args.get('session_id', '').strip())
    if not row:
        return error(s, 'A completed, verified FMNO action purchase is required. Use your original payment return link or recover it by email.', 402)
    workspace = ensure_workspace(s, row)
    expiry = str(int(time.time()) + 86400)
    value = workspace['id'] + '.' + expiry
    response = redirect('/diy-action/workspace', code=303)
    response.set_cookie(COOKIE, value + '.' + sign(s, 'access', value), max_age=86400,
                        secure=not s.app.testing, httponly=True, samesite='Lax', path='/diy-action')
    response.headers['Cache-Control'] = 'no-store, private'
    return response


def records(s, workspace):
    with db(s) as con:
        return [{'id': row['id'], **json.loads(row['payload'])} for row in con.execute('SELECT * FROM actions WHERE workspace=? ORDER BY rowid', (workspace['id'],))]


def workspace_page(s):
    workspace = authenticated(s)
    if not workspace:
        return error(s, 'Open your private payment return link to unlock this browser, or use workspace recovery.', 401)
    rows = records(s, workspace)
    token = sign(s, 'csrf', workspace['id'])
    hidden = '<input type="hidden" name="csrf" value="' + token + '">'
    body = f'''<div class="card"><span class="pill ok">Private DIY Action Workspace™</span><h1>Your next move is ready.</h1><p>{len(rows)} of {workspace['cap']} URL slots used. Your actions are saved on FMNO’s server, not only this browser.</p><p><a class="btn" href="/diy-action/export.txt">Download text pack</a> <a class="btn btn2" href="/diy-action/export.json">Download JSON</a></p><p class="note">Save your original payment return link securely or use <a href="/diy-action/recover">email recovery</a>. Your browser access expires after 24 hours. Download a copy for your own records. Keep identity documents off this workspace.</p></div>'''
    for row in rows:
        choices = ''.join(f'<option value="{v}"' + (' selected' if row.get('status') == v else '') + f'>{v.title()}</option>' for v in sorted(STATUSES))
        body += f'''<section class="card" style="margin-top:20px;overflow-wrap:anywhere"><span class="pill">DIY action pack generated</span><h2>{s.safe(row['target_url'])}</h2><p>Action reference: FMNO-DIY-{row['id'].upper()}</p><form method="post" action="/diy-action/save">{hidden}<input type="hidden" name="action_id" value="{row['id']}"><label for="draft-{row['id']}">Editable request</label><textarea id="draft-{row['id']}" name="draft" maxlength="16000" style="min-height:360px">{s.safe(row.get('draft'))}</textarea><label>Progress<select name="status">{choices}</select></label><label>Submission reference<input name="reference" maxlength="300" value="{s.safe(row.get('reference'))}"></label><label>My notes<textarea name="notes" maxlength="8000">{s.safe(row.get('notes'))}</textarea></label><label>Follow-up date (your local calendar)<input type="date" name="followup" value="{s.safe(row.get('followup'))}"></label><p><button class="btn">Save my changes</button></p></form><h3>Follow-up draft</h3><pre style="white-space:pre-wrap">{s.safe(row.get('followup_draft'))}</pre><p><a href="/diy-action/reminder.ics?action_id={row['id']}">Download calendar reminder</a> — save a date first; import the file into your calendar.</p></section>'''
    if len(rows) < workspace['cap']:
        body += f'''<section class="card" style="margin-top:20px"><h2>Add an action</h2><form method="post" action="/diy-action/generate">{hidden}<label>Your name<input name="name" maxlength="160" required></label><label>Country / state<input name="country_state" maxlength="160" required></label><label>Your authority<select name="authority"><option value="self">I am the person affected</option><option value="authorised">I am authorised to act for the person or business</option></select></label><label>Public target URL<input type="url" name="target_url" maxlength="2000" required></label><label>Issue<select name="issue_type">{''.join(f'<option value="{k}">{v}</option>' for k,v in ISSUES.items())}</select></label><label>Requested outcome<select name="requested_outcome">{''.join(f'<option value="{k}">{v}</option>' for k,v in OUTCOMES.items())}</select></label><label>What is wrong, outdated or sensitive?<textarea name="problem_summary" maxlength="3000" required></textarea></label><label>Evidence available (descriptions, not private documents)<textarea name="evidence_summary" maxlength="5000" required></textarea></label><label>Correct/current information<textarea name="correct_information" maxlength="3000" required></textarea></label><label><input style="width:auto" type="checkbox" name="truth_confirmed" value="yes" required> My facts are accurate. I will review the wording and submit any request myself.</label><label><input style="width:auto" type="checkbox" name="scope_confirmed" value="yes" required> This does not involve threats, minors, emergencies, active proceedings or a complex legal dispute.</label><label><input style="width:auto" type="checkbox" name="related_confirmed" value="yes" required> All URLs concern the same person/business and related issue. I understand saved URL slots cannot be swapped.</label><p><button class="btn">Generate and save my action →</button></p></form></section>'''
    body += '''<section class="recommend"><h2>Evidence checklist</h2><ul><li>Keep the exact URL, date and screenshots privately.</li><li>Check you have the right person; a shared name does not prove identity.</li><li>Keep evidence supporting each correction.</li><li>Find the publisher’s official contact, privacy or corrections channel.</li><li>Only share necessary identity evidence through a verified secure channel.</li></ul><p><a href="https://search.google.com/search-console/remove-outdated-content" rel="noreferrer noopener" target="_blank">Official Google outdated-content tool</a> — only when content has already changed or disappeared. For other issues, see <a href="/self-service">official pathways in the free desk</a>.</p><p class="note">You verify and submit everything. Publishers, platforms and search engines decide outcomes.</p></section>'''
    body += f'<form method="post" action="/diy-action/refund">{hidden}<p class="note">Unused purchase within seven days? <button class="btn btn2" name="confirm" value="refund">Refund this unused purchase</button></p></form><form method="post" action="/diy-action/logout">{hidden}<button class="btn btn2">Lock workspace on this browser</button></form>'
    return private(s, 'My saved action pack', body)


def generate(s):
    workspace = authenticated(s)
    if not workspace or not csrf_ok(s, workspace):
        return error(s, 'Workspace verification failed. Reopen your private link.', 403)
    data = {k: request.form.get(k, '').strip() for k in LIMITS}
    if any(len(data[k]) > limit for k, limit in LIMITS.items()):
        return error(s, 'An entry exceeds its stated length limit.')
    required = ('name', 'country_state', 'target_url', 'problem_summary', 'evidence_summary', 'correct_information')
    if not all(data[k] for k in required) or not valid_url(data['target_url']):
        return error(s, 'Complete the required facts and use a public HTTP/HTTPS URL without login credentials.')
    issue, outcome, authority = (request.form.get(k) for k in ('issue_type', 'requested_outcome', 'authority'))
    if issue not in ISSUES or outcome not in OUTCOMES or authority not in {'self', 'authorised'} or any(request.form.get(k) != 'yes' for k in ('truth_confirmed', 'scope_confirmed', 'related_confirmed')):
        return error(s, 'Confirm your authority, factual accuracy and that this is within the stated DIY scope.')
    if re.search(r'\b(minor|child|suicid\w*|blackmail|sextortion|death threat|active (court|proceeding)|ongoing (trial|proceeding)|complex defamation)\b', ' '.join(data[k] for k in required), re.I):
        return error(s, 'This appears outside the automated tool’s safety scope. Use the free safety guidance and suitable independent support, not an automated request.')
    who = 'I am the person affected' if authority == 'self' else 'I am authorised to act for the affected person or business'
    data['draft'] = f"Subject: Request to {OUTCOMES[outcome]}\n\nHello,\n\nI am writing about {data['target_url']}. {who}.\n\nThe concern:\n{data['problem_summary']}\n\nCorrect/current information:\n{data['correct_information']}\n\nEvidence available:\n{data['evidence_summary']}\n\nPlease {OUTCOMES[outcome]}. Please confirm receipt and explain your decision. Let me know if further evidence is required through a secure official channel.\n\nRegards,\n{data['name']}"
    data.update(issue_type=issue, requested_outcome=outcome, authority=authority, status='preparing', notes='', reference='', followup='')
    data['followup_draft'] = f"Hello,\n\nI am following up on my request about {data['target_url']}. My submission date and reference are recorded separately. Please confirm receipt and advise the status or any further evidence needed.\n\nRegards,\n{data['name']}"
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM refund_state WHERE workspace=?', (workspace['id'],)).fetchone():
            return error(s, 'A refund is pending or confirmed for this purchase. No action can be created.', 409)
        existing = con.execute('SELECT id FROM actions WHERE workspace=? AND url=?', (workspace['id'], data['target_url'])).fetchone()
        if existing:
            return redirect('/diy-action/workspace', code=303)
        count = con.execute('SELECT count(*) FROM actions WHERE workspace=?', (workspace['id'],)).fetchone()[0]
        if count >= workspace['cap']:
            return error(s, 'All URL slots are used. You can still edit your saved actions.', 409)
        con.execute('INSERT INTO actions VALUES(?,?,?,?)', (secrets.token_hex(12), workspace['id'], data['target_url'], json.dumps(data)))
    return redirect('/diy-action/workspace', code=303)


def save(s):
    workspace = authenticated(s)
    if not workspace or not csrf_ok(s, workspace):
        return error(s, 'Workspace verification failed.', 403)
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM actions WHERE id=? AND workspace=?', (request.form.get('action_id', ''), workspace['id'])).fetchone()
        if not row:
            return error(s, 'Action not found.', 404)
        data = json.loads(row['payload'])
        for key in ('draft', 'status', 'notes', 'reference', 'followup'):
            value = request.form.get(key, '').strip()
            if len(value) > LIMITS[key]:
                return error(s, 'An entry is too long.')
            data[key] = value
        if data['status'] not in STATUSES:
            return error(s, 'Choose a valid progress status.')
        try:
            if data['followup']:
                date.fromisoformat(data['followup'])
        except ValueError:
            return error(s, 'Choose a valid calendar date.')
        con.execute('UPDATE actions SET payload=? WHERE id=?', (json.dumps(data), row['id']))
    return redirect('/diy-action/workspace', code=303)


def export(s, kind):
    workspace = authenticated(s)
    if not workspace:
        return error(s, 'Private workspace access required.', 401)
    payload = {'product': CATALOG[workspace['tier']]['name'], 'url_limit': workspace['cap'], 'actions': records(s, workspace)}
    if kind == 'json':
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        mime = 'application/json'
    else:
        body = 'FIX MY NAME ONLINE — MY ACTION PACK\nReview all facts. You submit requests yourself.\n\n'
        for row in payload['actions']:
            body += '\n'.join(f'{k.upper()}: {v}' for k, v in row.items()) + '\n\n'
        body += 'EVIDENCE CHECKLIST: exact URL, screenshots, dates, correction evidence, official contact channel.\nFollow up only after a reasonable response period; 14 days is a suggestion, not a legal deadline.\n'
        mime = 'text/plain'
    return Response(body, mimetype=mime, headers={'Content-Disposition': f'attachment; filename="FMNO-Action-Pack.{kind}"', 'Cache-Control': 'no-store, private'})


def reminder(s):
    workspace = authenticated(s)
    if not workspace:
        return error(s, 'Private workspace access required.', 401)
    row = next((r for r in records(s, workspace) if r['id'] == request.args.get('action_id')), None)
    if not row:
        return error(s, 'Action not found.', 404)
    if not row.get('followup'):
        return error(s, 'Save a follow-up date first.')
    day = date.fromisoformat(row['followup'])
    body = '\r\n'.join(['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//FixMyNameOnline//Self Service//EN', 'BEGIN:VEVENT',
        f'UID:{row["id"]}@fixmynameonline.com', 'DTSTAMP:' + datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'),
        'DTSTART;VALUE=DATE:' + day.strftime('%Y%m%d'), 'DTEND;VALUE=DATE:' + (day + timedelta(days=1)).strftime('%Y%m%d'),
        'SUMMARY:Review my saved action follow-up', 'DESCRIPTION:Check your private saved pack. No request is submitted automatically.',
        'BEGIN:VALARM', 'TRIGGER:-PT9H', 'ACTION:DISPLAY', 'DESCRIPTION:Review my action follow-up', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR', ''])
    return Response(body, mimetype='text/calendar', headers={'Content-Disposition': 'attachment; filename="FMNO-Follow-up.ics"', 'Cache-Control': 'no-store, private'})


def webhook(s, session):
    row = paid(s, session.get('id', ''))
    if not row:
        return False
    workspace = ensure_workspace(s, row)
    if not workspace['notified'] and workspace['email']:
        link = s.DOMAIN + '/diy-action/start?session_id=' + row['id']
        sent = s.send_brevo_email(workspace['email'], '', 'Your private FMNO action workspace',
             '<h1>Your self-service workspace</h1><p>Save this private link securely. Anyone with it can access your workspace.</p><p><a href="' + s.safe(link) + '">Open my action workspace</a></p><p>You review the facts and submit requests yourself. You can recover this link at fixmynameonline.com/diy-action/recover.</p>')
        if sent:
            with db(s) as con:
                con.execute('UPDATE workspaces SET notified=1 WHERE id=?', (workspace['id'],))
    return True


def recover(s):
    if request.method == 'GET':
        return private(s, 'Recover workspace', '<div class="card"><h1>Find your workspace.</h1><p>Use the email entered at Stripe checkout. We will not show whether an address has a purchase.</p><form method="post"><label>Checkout email<input name="email" type="email" maxlength="254" required></label><p><button class="btn">Send my private access link</button></p></form><p>Check spam. If email is unavailable, your original Stripe return link still works.</p></div>')
    email = request.form.get('email', '').strip().lower()[:254]
    now = datetime.utcnow()
    # Render appends its trusted client hop; do not trust the spoofable first hop.
    ip = (request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[-1].strip()
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        keys = [sign(s, 'recovery-email', email), sign(s, 'recovery-ip', ip)]
        allowed = all(not (r := con.execute('SELECT used FROM recovery_limits WHERE key=?', (k,)).fetchone()) or r['used'] < (now - timedelta(minutes=15)).isoformat() for k in keys)
        rows = list(con.execute('SELECT session_id FROM workspaces WHERE email=? ORDER BY created DESC LIMIT 5', (email,))) if allowed else []
        if allowed:
            for key in keys:
                con.execute('INSERT OR REPLACE INTO recovery_limits VALUES(?,?)', (key, now.isoformat()))
    if rows:
        links = ''.join('<p><a href="' + s.safe(s.DOMAIN + '/diy-action/start?session_id=' + r['session_id']) + '">Open my private action workspace</a></p>' for r in rows)
        try:
            s.send_brevo_email(email, '', 'Your FMNO workspace access', '<p>These private links grant access. Keep them secure.</p>' + links)
        except Exception:
            s.app.logger.warning('Workspace recovery email unavailable')
    return private(s, 'Workspace recovery', '<div class="card"><h1>Check your inbox.</h1><p>If an eligible purchase matches and email delivery is available, an access link will arrive shortly. Wait 15 minutes before trying again. Your original payment return link still works.</p></div>')


def refund(s):
    workspace = authenticated(s)
    if not workspace or not csrf_ok(s, workspace) or request.form.get('confirm') != 'refund':
        return error(s, 'Refund verification failed.', 403)
    # Serialize eligibility against action creation. A pending refund blocks new work.
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM actions WHERE workspace=?', (workspace['id'],)).fetchone():
            return error(s, 'The automated unused-purchase refund is not available after an action is saved. Statutory consumer rights remain unchanged. For billing or a faulty product, contact admin@fixmynameonline.com.')
    row = paid(s, workspace['session_id'])
    if not row:
        # Recover a prior Stripe refund accepted before an interrupted readback.
        try:
            row = s.stripe.checkout.Session.retrieve(workspace['session_id'])
            refunds = s.stripe.Refund.list(payment_intent=row.get('payment_intent'), limit=100)
            confirmed = next((r for r in refunds.get('data', []) if r.get('status') in {'pending', 'succeeded'} and (r.get('metadata') or {}).get('workspace') == workspace['id']), None)
            if confirmed:
                with db(s) as con:
                    con.execute('INSERT OR REPLACE INTO refund_state VALUES(?,?)', (workspace['id'], 'confirmed'))
                return private(s, 'Refund recorded', '<div class="card"><h1>Stripe has already recorded your refund.</h1><p>No second refund was created.</p></div>')
            row = None
        except Exception:
            row = None
    if not row or not row.get('created') or time.time() - row['created'] > 7 * 86400:
        return error(s, 'This purchase is not eligible for the seven-day unused-purchase refund.')
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM actions WHERE workspace=?', (workspace['id'],)).fetchone():
            return error(s, 'An action has already been created for this purchase.', 409)
        con.execute('INSERT OR IGNORE INTO refund_state VALUES(?,?)', (workspace['id'], 'pending'))
    try:
        result = s.stripe.Refund.create(payment_intent=row['payment_intent'], reason='requested_by_customer',
            metadata={'policy': 'unused_7_days', 'brand': 'FixMyNameOnline', 'workspace': workspace['id']}, idempotency_key='fmno-unused-' + workspace['id'])
        verified = s.stripe.Refund.retrieve(result['id'])
        if verified.get('status') not in {'succeeded', 'pending'}:
            return error(s, 'Stripe has not confirmed the refund. No success is assumed.', 503)
    except Exception:
        return error(s, 'The refund could not be confirmed. Retrying uses the same request identifier.', 503)
    with db(s) as con:
        con.execute('INSERT OR REPLACE INTO refund_state VALUES(?,?)', (workspace['id'], 'confirmed'))
    response = private(s, 'Refund requested', '<div class="card"><h1>Refund recorded by Stripe.</h1><p>Your bank may take several days to show it. No further purchase is needed.</p><a href="/self-service">Use the free desk</a></div>')
    response.delete_cookie(COOKIE, path='/diy-action')
    return response


def backup(s):
    with db(s) as con:
        return {'workspaces': [dict(r) for r in con.execute('SELECT * FROM workspaces')], 'actions': [dict(r) for r in con.execute('SELECT * FROM actions')], 'refund_state': [dict(r) for r in con.execute('SELECT * FROM refund_state')]}


def register(s):
    app = s.app
    for route, fn, methods in [('/diy-action/workspace', workspace_page, ['GET']),
            ('/diy-action/save', save, ['POST']), ('/diy-action/reminder.ics', reminder, ['GET']),
            ('/diy-action/recover', recover, ['GET', 'POST']), ('/diy-action/refund', refund, ['POST'])]:
        app.add_url_rule(route, 'paid_' + fn.__name__, lambda fn=fn: fn(s), methods=methods)
    app.add_url_rule('/diy-action/export.<kind>', 'paid_export', lambda kind: export(s, kind) if kind in {'txt', 'json'} else error(s, 'Unknown format.', 404))
    @app.route('/diy-action/logout', methods=['POST'])
    def action_logout():
        workspace = authenticated(s)
        if not workspace or not csrf_ok(s, workspace):
            return error(s, 'Workspace verification failed.', 403)
        response = redirect('/diy-action', code=303)
        response.delete_cookie(COOKIE, path='/diy-action')
        return response
    @app.before_request
    def bounded_request():
        if request.path.startswith('/diy-action/') and request.content_length and request.content_length > 65536:
            return error(s, 'Request is too large.', 413)
    @app.after_request
    def private_headers(response):
        if request.path.startswith('/diy-action/'):
            response.headers.update({'Cache-Control': 'no-store, private', 'X-Robots-Tag': 'noindex, nofollow',
                                     'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'})
        return response
