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
from typing import Any

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
STATUS_LABELS = {'preparing': 'Preparing', 'submitted': 'Sent by me', 'waiting': 'Waiting for a reply', 'closed': 'Closed'}
# Plain-English wording used inside the letters (keys unchanged for stored data).
# {my} becomes "their" when someone writes for the person the page is about.
ASK = {'correct': 'correct or update the page so it reflects the current facts',
       'anonymise': 'remove {my} name and other identifying details from the page',
       'noindex': 'add a “noindex” tag to the page, so search engines stop showing it',
       'remove': 'take the page down'}
# Short form for the later letters, where the link follows straight after.
ASK_SHORT = {'correct': 'correct or update this page',
             'anonymise': 'remove {my} name and other identifying details from this page',
             'noindex': 'add a “noindex” tag to this page, so search engines stop showing it',
             'remove': 'take this page down'}
SUBJECT = {'correct': 'Request to update a page about {me}', 'anonymise': 'Request to remove {my} name from a page',
           'noindex': 'Request to stop a page showing in search engines', 'remove': 'Request to remove a page about {me}'}
# What's wrong, said properly for each kind of problem. Second item is used in the second letter.
ISSUE_SENTENCE = {
    'outdated': ('The page contains outdated information about {me}.', 'The page still shows outdated information about {me}, and it comes up when people search {my} name.'),
    'inaccurate': ('The page contains inaccurate or incomplete information about {me}.', 'The page still shows inaccurate or incomplete information about {me}, and it comes up when people search {my} name.'),
    'privacy': ('The page shows {my} personal information.', 'The page still shows {my} personal information, and it comes up when people search {my} name.'),
    'wrong-person': ('People searching {my} name are confusing {me} with the person this page is about. {i_am_not} that person.',
                     'People searching {my} name are still confusing {me} with the person this page is about.'),
}
VOICE = {'self': {'me': 'me', 'my': 'my', 'i_am_not': 'I’m not'},
         'authorised': {'me': 'them', 'my': 'their', 'i_am_not': 'They’re not'}}


def _say(template, voice):
    return template.format(**voice)


def draft_letters(data):
    """The three letters in the pack, built only from the buyer's own answers.
    Plain requests: no legal claims, no threats, no deadlines presented as law."""
    outcome = data.get('requested_outcome') or 'correct'
    if outcome not in ASK:
        outcome = 'correct'
    authority = 'authorised' if data.get('authority') == 'authorised' else 'self'
    voice = VOICE[authority]
    url, name = data.get('target_url', ''), data.get('name', '')
    ask, ask_short = _say(ASK[outcome], voice), _say(ASK_SHORT[outcome], voice)
    issue_key = data.get('issue_type') if data.get('issue_type') in ISSUE_SENTENCE else 'outdated'
    issue_first, issue_still = (_say(t, voice) for t in ISSUE_SENTENCE[issue_key])
    summary = (data.get('problem_summary') or '').strip()
    on_behalf = ('I’m writing on behalf of [name of the person the page is about], who has asked me to help with this.\n\n'
                 if authority == 'authorised' else '')
    subject = _say(SUBJECT[outcome], voice)
    request_letter = (f"Subject: {subject}\n\nHello,\n\nI’m writing about this page on your site:\n{url}\n\n"
        f"{on_behalf}{issue_first}{' ' + summary if summary else ''}\n\n"
        f"The current, correct position is:\n{data.get('correct_information', '')}\n\n"
        f"I can provide evidence of this: {data.get('evidence_summary', '')}\n\n"
        f"I’m asking you to {ask}. Could you please confirm you’ve received this request and let me know your decision? "
        f"If you need anything else to check it, please tell me how to send it securely.\n\n"
        f"I’d be grateful for a reply within 14 days.\n\nKind regards,\n{name}")
    followup = (f"Subject: Following up on my request about {url}\n\nHello,\n\nI wrote to you on [date you sent your first letter] about this page:\n{url}\n\n"
        f"I asked you to {ask}. I haven’t had a reply yet. Could you let me know whether you’ve received my request, and when I can expect an answer?\n\nKind regards,\n{name}")
    second = (f"Subject: Second request about {url}\n\nHello,\n\nI first wrote to you on [date of your first letter], and followed up on [date of your follow-up], "
        f"asking you to {ask_short}:\n{url}\n\nI still haven’t had a reply. {issue_still}\n\n"
        f"I’d appreciate a decision either way. If you’re not able to make this change, could you tell me why, and whether there’s a complaints or review process I can use?\n\nKind regards,\n{name}")
    return request_letter, followup, second


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


def stripe_data(value: Any) -> Any:
    """Normalize SDK resources at the boundary (Stripe 16 is not dict-like)."""
    if isinstance(value, dict):
        return {key: stripe_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [stripe_data(item) for item in value]
    converter = getattr(value, 'to_dict', None)
    if callable(converter):
        return stripe_data(converter())
    return value


def price_id(plan):
    return os.environ.get(plan['env']) or PUBLIC_BILLING.get(plan['env'], '')


def sign(s, purpose, value):
    return hmac.new(secret(s).encode(), f'{purpose}:{value}'.encode(), hashlib.sha256).hexdigest()


def private(s, title, body, status=200):
    response = Response(s.page(title, body, robots='noindex,nofollow', analytics=False), status=status, mimetype='text/html')
    response.headers.update({'Cache-Control': 'no-store, private', 'X-Robots-Tag': 'noindex, nofollow',
                             'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'DENY'})
    return response


def error(s, text, status=400):
    return private(s, 'Your letter pack', '<div class="card"><h1>Let’s check that.</h1><p>' + s.safe(text) + '</p><p><a class="btn" href="/diy-action/workspace">Back to my letter pack</a> <a class="btn btn2" href="/self-service">Free check and plan</a></p></div>', status)


def paid(s, sid):
    if not re.fullmatch(r'cs_(live|test)_[A-Za-z0-9_]{5,240}', sid or '') or not s.stripe.api_key:
        return None
    try:
        row = stripe_data(s.stripe.checkout.Session.retrieve(sid, expand=['line_items']))
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
        refunds = stripe_data(s.stripe.Refund.list(payment_intent=pi, limit=100))
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


SAMPLE = {'target_url': 'https://www.example-news.com.au/2019/local-man-charged', 'name': 'Sam Example', 'authority': 'self',
          'issue_type': 'outdated', 'requested_outcome': 'correct',
          'problem_summary': 'It reports that I was charged in 2019, but not that the charge was withdrawn in 2020.',
          'correct_information': 'The charge was withdrawn on 3 March 2020. No conviction was recorded.',
          'evidence_summary': 'a letter from the court registry confirming the charge was withdrawn.'}


def sales(s):
    request_letter, followup, second = draft_letters(SAMPLE)
    body = (Path(__file__).with_name('single_action.html')).read_text(encoding='utf-8')
    body = (body.replace('{{SAMPLE_REQUEST}}', s.safe(request_letter)).replace('{{SAMPLE_FOLLOWUP}}', s.safe(followup))
            .replace('{{SAMPLE_SECOND}}', s.safe(second)).replace('{{BUILDING}}', s.icon('building')))
    faq = [(q, a) for q, a in SALES_FAQ]
    schema = [{'@type': 'Product', 'name': 'Letter pack for one link', 'description': 'Request, follow-up and second letters for one link, saved online with reminders. You send everything yourself.',
               'brand': {'@type': 'Brand', 'name': 'Fix My Name Online'},
               'offers': {'@type': 'Offer', 'price': '19.00', 'priceCurrency': 'USD', 'url': s.DOMAIN + '/diy-action', 'availability': 'https://schema.org/InStock'}},
              {'@type': 'FAQPage', 'mainEntity': [{'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]}]
    return s.page('Letter pack for one link: US$19 once', body,
                  'Your request letter, a follow-up and a second letter for one link, saved online with reminders. US$19 once, refund within 7 days if unused. You send everything yourself.',
                  canonical_path='/diy-action', schema_items=schema, safety='au')


SALES_FAQ = [
    ('What happens after I pay?', 'You go straight to your private workspace. Enter your facts, and your request letter, follow-up and second letter are created for that link. You can edit them, then send them yourself.'),
    ('Can I use it on another device?', 'Yes. Your letters are saved online. Use the link from your payment confirmation, or get a new access link by email from the recovery page.'),
    ('What if they say no?', 'Record the answer in your workspace. The free plan for your problem lists what to try next in your country.'),
    ('Can I get a refund?', 'Yes, within 7 days if you haven’t created your letters yet, straight from your workspace. Your Australian Consumer Law rights always apply.'),
]


def checkout(s, tier):
    if tier == 'diy-pack':
        return redirect('/diy-action', code=302)
    tier = 'diy-single' if tier == 'diy-action' else tier
    plan = CATALOG[tier]
    try:
        secret(s)
        pid = price_id(plan)
        p = stripe_data(s.stripe.Price.retrieve(pid))
        if not (p.get('active') and p.get('currency') == 'usd' and p.get('unit_amount') == plan['amount'] and p.get('type') == 'one_time'):
            raise ValueError('Price mismatch')
        row = s.stripe.checkout.Session.create(mode='payment', line_items=[{'price': pid, 'quantity': 1}],
            success_url=s.DOMAIN + '/diy-action/start?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=s.DOMAIN + '/diy-action', allow_promotion_codes=False,
            customer_creation='always', metadata={'tier': tier, 'plan_name': plan['name'], 'product_version': 'selfserve-v1'},
            payment_intent_data={'metadata': {'tier': tier, 'brand': 'FixMyNameOnline'}},
            custom_text={'submit': {'message': 'One-time letter pack for one link. You check the facts and send the letters yourself. Nobody at Fix My Name Online reviews your case or contacts anyone for you.'}})
        return redirect(stripe_data(row)['url'], code=302)
    except Exception:
        s.app.logger.warning('Paid action checkout unavailable; no payment created or confirmed')
        return error(s, 'Checkout isn’t available right now, and no payment has been taken. The free check and plan still work.', 503)


def start(s):
    row = paid(s, request.args.get('session_id', '').strip())
    if not row:
        return error(s, 'We couldn’t confirm a letter pack purchase for this link. Use the link from your payment confirmation, or get a new one by email from the recovery page.', 402)
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


def _field(label, control, hint=''):
    hint_html = f'<span class="hint">{hint}</span>' if hint else ''
    return f'<div class="field-sm"><label class="label-sm">{label}{hint_html}{control}</label></div>'


def _letter(s, title, text, key, row_id, note=''):
    note_html = f'<p class="letter-hint small">{note}</p>' if note else ''
    return (f'<div class="letter"><div class="letter-bar"><strong>{title}</strong><span class="btn-row">'
            f'<button type="button" class="btn btn-secondary btn-sm" data-copy="#{key}-{row_id}">{s.icon("copy", "icon icon-sm")}<span>Copy</span></button></span></div>'
            f'<pre class="letter-body letter-pre" id="{key}-{row_id}">{s.safe(text)}</pre>{note_html}</div>')


def workspace_page(s):
    workspace = authenticated(s)
    if not workspace:
        return error(s, 'Open the link from your payment confirmation to unlock your letter pack on this browser, or get a new link by email from the recovery page.', 401)
    rows = records(s, workspace)
    token = sign(s, 'csrf', workspace['id'])
    hidden = '<input type="hidden" name="csrf" value="' + token + '">'
    used = f'{len(rows)} of {workspace["cap"]} link{"s" if workspace["cap"] != 1 else ""} used'
    first_host = (urlparse(rows[0]['target_url']).hostname or '').removeprefix('www.') if rows else ''
    title = 'Your letter pack is ready' if not rows else ('Your letters for ' + (s.safe(first_host) if len(rows) == 1 else f'{len(rows)} links'))
    lede = ('Enter the facts for your link and we’ll build your request letter, a follow-up and a second letter. You check them and send them yourself.'
            if not rows else 'Edit your request letter, send it yourself, then record what happens. Your letters are saved online, so you can come back to them.')
    body = f'''<section class="page-head"><div class="wrap"><p class="eyebrow">Letter pack · Private workspace · {used}</p><h1 style="margin-top:8px;overflow-wrap:anywhere">{title}</h1><p class="lede">{lede}</p></div></section><div class="wrap split"><div class="stack-lg">'''
    for row in rows:
        rid = row['id']
        choices = ''.join(f'<option value="{v}"' + (' selected' if row.get('status') == v else '') + f'>{STATUS_LABELS[v]}</option>' for v in ('preparing', 'submitted', 'waiting', 'closed'))
        _, followup_default, second_default = draft_letters(row)
        followup = row.get('followup_draft') or followup_default
        second = row.get('second_draft') or second_default
        body += f'''<section class="card card-lg steps-card" style="overflow-wrap:anywhere"><p class="eyebrow">Link · Reference FMNO-DIY-{rid.upper()}</p><p class="track-url" style="white-space:normal">{s.safe(row['target_url'])}</p>
<ol class="steps mt-3">
<li><h3>Check and edit your request letter</h3><p class="step-meta"><span>{s.icon("clock", "icon icon-sm")}10 minutes</span><span>{s.icon("mail", "icon icon-sm")}You send it</span></p>
<form method="post" action="/diy-action/save" class="stack mt-2">{hidden}<input type="hidden" name="action_id" value="{rid}">
<label class="label-sm" for="draft-{rid}">Your request letter (edit it here, then save)</label><textarea class="textarea letter-edit" id="draft-{rid}" name="draft" maxlength="16000">{s.safe(row.get('draft'))}</textarea>
<p class="btn-row"><button type="button" class="btn btn-secondary btn-sm" data-copy="#draft-{rid}">{s.icon("copy", "icon icon-sm")}<span>Copy</span></button></p>
<p class="meta"><strong>Where to send it:</strong> look for “Corrections”, “Contact”, “Privacy” or “Complaints” on the site. Send it to one place and keep a copy.</p>
<div class="form-grid">
{_field('Status', f'<select class="select" name="status">{choices}</select>')}
{_field('Reference number', f'<input class="input" name="reference" maxlength="300" value="{s.safe(row.get("reference"))}">')}
{_field('Check back on', f'<input class="input" type="date" name="followup" value="{s.safe(row.get("followup"))}">', ' (for your calendar)')}
</div>
{_field('My notes', f'<textarea class="textarea" name="notes" maxlength="8000">{s.safe(row.get("notes"))}</textarea>')}
<p><button class="btn btn-primary">Save my changes</button></p></form></li>
<li><h3>If there’s no reply after 14 days, send the follow-up</h3><p class="step-meta"><span>{s.icon("calendar", "icon icon-sm")}Day 14</span></p><div class="mt-2">{_letter(s, 'Follow-up letter', followup, 'followup', rid, 'Fill in the dates in square brackets before you send it.')}</div>
<p class="btn-row mt-2"><a class="btn btn-secondary btn-sm" href="/diy-action/reminder.ics?action_id={rid}">{s.icon("calendar", "icon icon-sm")}Add my check-back date to my calendar</a></p><p class="small">Save a check-back date first. The file works in Apple, Google and Outlook calendars.</p></li>
<li><h3>Still nothing after about 30 days? Send the second letter</h3><p class="step-meta"><span>{s.icon("calendar", "icon icon-sm")}Day 30</span></p><div class="mt-2">{_letter(s, 'Second letter', second, 'second', rid, 'It asks for a decision either way, and whether there’s a complaints process. It makes no threats.')}</div></li>
<li><h3>Once the page changes, ask Google to refresh it</h3><p class="muted mt-1">Paste the same link. Google checks the live page and updates or drops the old result.</p><p class="btn-row mt-2"><a class="btn btn-secondary btn-sm" href="https://search.google.com/search-console/remove-outdated-content" target="_blank" rel="noopener noreferrer">Google’s Refresh Outdated Content tool {s.icon("ext", "icon icon-sm")}</a></p></li>
</ol></section>'''
    if len(rows) < workspace['cap']:
        issues = ''.join(f'<option value="{k}">{v[0].upper() + v[1:]}</option>' for k, v in ISSUES.items())
        outcomes = ''.join(f'<option value="{k}">{(t := _say(ASK[k], VOICE["self"]))[0].upper() + t[1:]}</option>' for k in OUTCOMES)
        body += f'''<section class="card stack"><h2 class="h-sans">Create your letters{' for another link' if rows else ''}</h2><p class="meta">Use plain facts. Don’t include passwords, ID numbers or private documents. Once you create letters for a link, that link can’t be swapped.</p>
<form method="post" action="/diy-action/generate" class="stack">{hidden}
<div class="form-grid">
{_field('Your name', '<input class="input" name="name" maxlength="160" required autocomplete="name">')}
{_field('Country and state', '<input class="input" name="country_state" maxlength="160" required>')}
</div>
{_field('Who is it about?', '<select class="select" name="authority"><option value="self">Me</option><option value="authorised">Someone who has asked me to help</option></select>')}
{_field('The link', '<input class="input" type="url" name="target_url" maxlength="2000" required placeholder="https://">', ' (the page, not the Google result)')}
<div class="form-grid">
{_field('What’s the problem?', f'<select class="select" name="issue_type">{issues}</select>')}
{_field('What are you asking for?', f'<select class="select" name="requested_outcome">{outcomes}</select>')}
</div>
{_field('What’s wrong, out of date or private on the page?', '<textarea class="textarea" name="problem_summary" maxlength="3000" required></textarea>', ' One or two sentences.')}
{_field('What’s the correct, current position?', '<textarea class="textarea" name="correct_information" maxlength="3000" required></textarea>')}
{_field('What evidence can you provide?', '<textarea class="textarea" name="evidence_summary" maxlength="5000" required></textarea>', ' Describe it; don’t paste private documents.')}
<label class="check-row"><input type="checkbox" name="truth_confirmed" value="yes" required><span>My facts are accurate. I’ll check the letters and send them myself.</span></label>
<label class="check-row"><input type="checkbox" name="scope_confirmed" value="yes" required><span>This doesn’t involve threats, a child, an emergency, a case that’s still running, or a complex legal dispute.</span></label>
<label class="check-row"><input type="checkbox" name="related_confirmed" value="yes" required><span>I understand the link can’t be swapped once my letters are created.</span></label>
<p><button class="btn btn-primary">Create my letters</button></p></form></section>'''
    body += '</div><aside class="aside stack">'
    body += f'''<div class="card stack-sm"><h3 class="h-icon">{s.icon("download")} Keep a copy</h3><p class="btn-row"><a class="btn btn-secondary btn-sm" href="/diy-action/export.txt">Download as text</a><a class="btn btn-secondary btn-sm" href="/diy-action/export.json">Download data (JSON)</a></p><p class="small">Print the page to save it as a PDF.</p></div>
<div class="card stack-sm"><h3 class="h-icon">{s.icon("lock")} Getting back in</h3><p class="meta">This browser stays unlocked for 24 hours. After that, use the link from your payment confirmation, or get a new one from <a href="/diy-action/recover">workspace recovery</a>. Anyone with your link can open this workspace.</p>
<form method="post" action="/diy-action/logout">{hidden}<button class="btn btn-secondary btn-sm">Lock this browser now</button></form></div>
<div class="callout callout-info">{s.icon("info", "icon icon-sm")}<p>You send everything yourself. Publishers, platforms and Google make their own decisions, and no one can promise a result.</p></div>'''
    if not rows:
        body += f'''<form method="post" action="/diy-action/refund" class="card stack-sm">{hidden}<h3>Changed your mind?</h3><p class="meta">You can refund this pack yourself within 7 days, as long as you haven’t created your letters yet.</p><button class="btn btn-secondary btn-sm" name="confirm" value="refund">Refund this unused purchase</button></form>'''
    body += '</aside></div>'
    return private(s, 'My letter pack', '<main id="main">' + body + '</main>')


# Things a letter isn't the right first step for. "minor" only counts when it means a child,
# so "a minor offence" or "a minor error" is fine.
OUT_OF_SCOPE = re.compile(
    r'\b(child(ren)?|kids?|under ?age|(a|the|is|was|involving|about|of) minors?\b(?!\s+(offen[cs]es?|traffic|matters?|errors?|mistakes?|issues?|details?|changes?|charges?|convictions?|breach(es)?|incidents?|corrections?|points?))|minors\b|suicid\w*|self[- ]harm|blackmail|sextortion|death threats?|threaten\w*|active (court|proceedings?|case)|ongoing (trial|proceedings?|case)|(case|matter|trial) (is )?still (running|ongoing|open)|complex defamation)\b', re.I)


def generate(s):
    workspace = authenticated(s)
    if not workspace or not csrf_ok(s, workspace):
        return error(s, 'This page has expired. Open your letter pack again from the link in your payment confirmation.', 403)
    data = {k: request.form.get(k, '').strip() for k in LIMITS}
    if any(len(data[k]) > limit for k, limit in LIMITS.items()):
        return error(s, 'An entry exceeds its stated length limit.')
    required = ('name', 'country_state', 'target_url', 'problem_summary', 'evidence_summary', 'correct_information')
    if not all(data[k] for k in required) or not valid_url(data['target_url']):
        return error(s, 'Complete the required facts and use a public HTTP/HTTPS URL without login credentials.')
    issue, outcome, authority = (request.form.get(k) for k in ('issue_type', 'requested_outcome', 'authority'))
    if issue not in ISSUES or outcome not in OUTCOMES or authority not in {'self', 'authorised'} or any(request.form.get(k) != 'yes' for k in ('truth_confirmed', 'scope_confirmed', 'related_confirmed')):
        return error(s, 'Confirm your authority, factual accuracy and that this is within the stated DIY scope.')
    if OUT_OF_SCOPE.search(' '.join(data[k] for k in required)):
        return error(s, 'The letter pack isn’t the right tool for this one. From what you wrote, it may involve a child, threats, self-harm, or a case that’s still running, and those need other help first. The free check puts the right help at the top of your plan. If we’ve read it wrong, reword your answers and try again. Nothing has been created or sent, and you can still refund this unused pack within 7 days.')
    data.update(issue_type=issue, requested_outcome=outcome, authority=authority, status='preparing', notes='', reference='', followup='')
    data['draft'], data['followup_draft'], data['second_draft'] = draft_letters(data)
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM refund_state WHERE workspace=?', (workspace['id'],)).fetchone():
            return error(s, 'A refund is pending or confirmed for this purchase. No action can be created.', 409)
        existing = con.execute('SELECT id FROM actions WHERE workspace=? AND url=?', (workspace['id'], data['target_url'])).fetchone()
        if existing:
            return redirect('/diy-action/workspace', code=303)
        count = con.execute('SELECT count(*) FROM actions WHERE workspace=?', (workspace['id'],)).fetchone()[0]
        if count >= workspace['cap']:
            return error(s, 'This pack covers one link, and you’ve already created letters for it. You can still edit them.', 409)
        con.execute('INSERT INTO actions VALUES(?,?,?,?)', (secrets.token_hex(12), workspace['id'], data['target_url'], json.dumps(data)))
    return redirect('/diy-action/workspace', code=303)


def save(s):
    workspace = authenticated(s)
    if not workspace or not csrf_ok(s, workspace):
        return error(s, 'This page has expired. Open your letter pack again from the link in your payment confirmation.', 403)
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
        return error(s, 'Open your letter pack from the link in your payment confirmation first.', 401)
    payload = {'product': CATALOG[workspace['tier']]['name'], 'url_limit': workspace['cap'], 'actions': records(s, workspace)}
    if kind == 'json':
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        mime = 'application/json'
    else:
        parts = ['FIX MY NAME ONLINE · MY LETTER PACK', 'You check the facts and send everything yourself. Nothing has been sent for you.', '']
        for row in payload['actions']:
            _, followup_default, second_default = draft_letters(row)
            parts += [f"LINK: {row.get('target_url', '')}", f"Reference: FMNO-DIY-{str(row.get('id', '')).upper()}",
                      f"Status: {STATUS_LABELS.get(row.get('status'), row.get('status', ''))}", f"Your reference number: {row.get('reference', '') or '-'}",
                      f"Check back on: {row.get('followup', '') or '-'}", f"My notes: {row.get('notes', '') or '-'}", '',
                      '=== 1. REQUEST LETTER ===', row.get('draft', ''), '',
                      '=== 2. FOLLOW-UP LETTER (send if there’s no reply after 14 days) ===', row.get('followup_draft') or followup_default, '',
                      '=== 3. SECOND LETTER (send if there’s still no reply after about 30 days) ===', row.get('second_draft') or second_default, '',
                      'Once the page changes, ask Google to refresh it: https://search.google.com/search-console/remove-outdated-content', '', '']
        parts.append('Before you send: check every fact, fill in anything in [square brackets], and keep a copy. 14 and 30 days are suggestions, not legal deadlines.')
        body = '\n'.join(parts) + '\n'
        mime = 'text/plain'
    return Response(body, mimetype=mime, headers={'Content-Disposition': f'attachment; filename="FMNO-Action-Pack.{kind}"', 'Cache-Control': 'no-store, private'})


def reminder(s):
    workspace = authenticated(s)
    if not workspace:
        return error(s, 'Open your letter pack from the link in your payment confirmation first.', 401)
    row = next((r for r in records(s, workspace) if r['id'] == request.args.get('action_id')), None)
    if not row:
        return error(s, 'Action not found.', 404)
    if not row.get('followup'):
        return error(s, 'Save a follow-up date first.')
    day = date.fromisoformat(row['followup'])
    body = '\r\n'.join(['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//FixMyNameOnline//Self Service//EN', 'BEGIN:VEVENT',
        f'UID:{row["id"]}@fixmynameonline.com', 'DTSTAMP:' + datetime.utcnow().strftime('%Y%m%dT%H%M%SZ'),
        'DTSTART;VALUE=DATE:' + day.strftime('%Y%m%d'), 'DTEND;VALUE=DATE:' + (day + timedelta(days=1)).strftime('%Y%m%d'),
        'SUMMARY:Check for a reply to my letter', 'DESCRIPTION:Open your letter pack and check for a reply. If there isn’t one, send the follow-up yourself. Nothing is sent automatically.',
        'BEGIN:VALARM', 'TRIGGER:-PT9H', 'ACTION:DISPLAY', 'DESCRIPTION:Check for a reply to my letter', 'END:VALARM', 'END:VEVENT', 'END:VCALENDAR', ''])
    return Response(body, mimetype='text/calendar', headers={'Content-Disposition': 'attachment; filename="FMNO-Follow-up.ics"', 'Cache-Control': 'no-store, private'})


def webhook(s, session):
    row = paid(s, session.get('id', ''))
    if not row:
        return False
    workspace = ensure_workspace(s, row)
    if not workspace['notified'] and workspace['email']:
        link = s.DOMAIN + '/diy-action/start?session_id=' + row['id']
        sent = s.send_brevo_email(workspace['email'], '', 'Your Fix My Name Online letter pack',
             '<h1>Your letter pack is ready</h1><p>Thanks for buying the letter pack. Use this link to open it and create your letters:</p><p><a href="' + s.safe(link) + '">Open my letter pack</a></p><p>Keep this email private: anyone with the link can open your letter pack. If you lose it, get a new link at fixmynameonline.com/diy-action/recover.</p><p>You check the letters and send them yourself. We don’t send anything for you.</p><p>Fix My Name Online · Madison Jade Pty Ltd</p>')
        if sent:
            with db(s) as con:
                con.execute('UPDATE workspaces SET notified=1 WHERE id=?', (workspace['id'],))
    return True


def recover(s):
    if request.method == 'GET':
        return private(s, 'Get back into your letter pack', '<div class="card"><h1>Get back into your letter pack.</h1><p>Enter the email you used at checkout and we’ll send you a new link. For privacy, we won’t say on screen whether an address has a purchase.</p><form method="post"><label>Checkout email<input name="email" type="email" maxlength="254" required></label><p><button class="btn">Email me a new link</button></p></form><p>Check your spam folder too. The link from your payment confirmation also still works.</p></div>')
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
        links = ''.join('<p><a href="' + s.safe(s.DOMAIN + '/diy-action/start?session_id=' + r['session_id']) + '">Open my letter pack</a></p>' for r in rows)
        try:
            s.send_brevo_email(email, '', 'Your link to get back into your letter pack',
                '<p>Here’s the link you asked for. Keep this email private: anyone with the link can open your letter pack.</p>' + links +
                '<p>If you didn’t ask for this, you can ignore this email.</p><p>Fix My Name Online · Madison Jade Pty Ltd</p>')
        except Exception:
            s.app.logger.warning('Workspace recovery email unavailable')
    return private(s, 'Check your inbox', '<div class="card"><h1>Check your inbox.</h1><p>If that email matches a letter pack, a new link is on its way. If nothing arrives, check your spam folder, and wait 15 minutes before trying again. The link from your payment confirmation also still works.</p></div>')


def refund(s):
    workspace = authenticated(s)
    if not workspace or not csrf_ok(s, workspace) or request.form.get('confirm') != 'refund':
        return error(s, 'Refund verification failed.', 403)
    # Serialize eligibility against action creation. A pending refund blocks new work.
    with db(s) as con:
        con.execute('BEGIN IMMEDIATE')
        if con.execute('SELECT 1 FROM actions WHERE workspace=?', (workspace['id'],)).fetchone():
            return error(s, 'The 7-day refund button only works for packs that haven’t been used, and you’ve already created your letters. Your Australian Consumer Law rights still apply: if the pack doesn’t work as described, email admin@fixmynameonline.com.')
    row = paid(s, workspace['session_id'])
    if not row:
        # Recover a prior Stripe refund accepted before an interrupted readback.
        try:
            row = stripe_data(s.stripe.checkout.Session.retrieve(workspace['session_id']))
            refunds = stripe_data(s.stripe.Refund.list(payment_intent=row.get('payment_intent'), limit=100))
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
        verified = stripe_data(s.stripe.Refund.retrieve(stripe_data(result)['id']))
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
