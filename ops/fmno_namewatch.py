#!/usr/bin/env python3
"""FMNO NameWatch Alert™ automation.

Discovers paid, active NameWatch subscriptions in the isolated FMNO Stripe
account, matches them to paid onboarding records archived by the FMNO watchdog,
runs a private scheduled web/news sweep, and sends customer alerts from
admin@fixmynameonline.com through Apple Mail.

The first run creates a baseline. Later runs alert on newly observed results.
A quiet monthly status note is sent when there are no newly observed results.
No publisher/platform request is submitted and no removal outcome is implied.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

ROOT = pathlib.Path('/Users/ellicakar')
STRIPE_ENV = ROOT / '.hermes/credentials/fmno_stripe_live.env'
BACKUP_DIR = ROOT / '.hermes/state/fmno_backups'
STATE_DIR = ROOT / '.hermes/state/fmno_namewatch'
SENDER = os.environ.get('FMNO_NAMEWATCH_SENDER', 'admin@fixmynameonline.com')
INTERNAL_RECIPIENT = os.environ.get('FMNO_NAMEWATCH_INTERNAL', 'Elli35111@gmail.com')
USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36'
MONTHLY_STATUS_SECONDS = 28 * 24 * 60 * 60
MAX_QUERIES = 10
MAX_RESULTS_PER_SOURCE = 20
RISK_TERMS = {
    'arrest', 'arrested', 'charged', 'charge', 'convicted', 'court', 'lawsuit',
    'fraud', 'fraudulent', 'scam', 'complaint', 'mugshot', 'police', 'bankrupt',
    'bankruptcy', 'investigation', 'investigated', 'allegation', 'accused',
    'disciplinary', 'sanction', 'review', 'reviews', 'warning', 'exposed',
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_env(path: pathlib.Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(errors='ignore').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def private_write(path: pathlib.Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    tmp.chmod(0o600)
    tmp.replace(path)
    path.chmod(0o600)


def load_json(path: pathlib.Path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 35) -> bytes:
    merged = {'User-Agent': USER_AGENT, 'Accept-Language': 'en-AU,en;q=0.9'}
    if headers:
        merged.update(headers)
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=merged)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f'HTTP request failed after retries: {type(last_error).__name__}')


def stripe_get(secret_key: str, path: str, params: dict | None = None) -> dict:
    query = urllib.parse.urlencode(params or {})
    url = 'https://api.stripe.com/v1/' + path.lstrip('/') + (('?' + query) if query else '')
    body = http_get(url, headers={'Authorization': 'Bearer ' + secret_key})
    return json.loads(body.decode('utf-8'))


def active_namewatch_checkouts(secret_key: str) -> dict[str, dict]:
    """Return the latest active/trialing paid NameWatch checkout by lower-case email."""
    sessions: list[dict] = []
    starting_after = ''
    while True:
        params = {'limit': 100, 'status': 'complete'}
        if starting_after:
            params['starting_after'] = starting_after
        page = stripe_get(secret_key, 'checkout/sessions', params)
        batch = page.get('data') or []
        sessions.extend(batch)
        if not page.get('has_more') or not batch:
            break
        starting_after = batch[-1].get('id', '')
        if len(sessions) >= 1000:
            break

    active: dict[str, dict] = {}
    for session in sessions:
        if (session.get('metadata') or {}).get('tier') != 'sentinel':
            continue
        if session.get('payment_status') not in {'paid', 'no_payment_required'}:
            continue
        subscription_id = session.get('subscription')
        if not subscription_id:
            continue
        try:
            subscription = stripe_get(secret_key, 'subscriptions/' + urllib.parse.quote(subscription_id, safe=''))
        except Exception:
            continue
        if subscription.get('status') not in {'active', 'trialing'}:
            continue
        details = session.get('customer_details') or {}
        email = (details.get('email') or session.get('customer_email') or '').strip().lower()
        if not email:
            continue
        record = {
            'email': email,
            'session_id': session.get('id'),
            'subscription_id': subscription_id,
            'subscription_status': subscription.get('status'),
            'current_period_end': subscription.get('current_period_end'),
            'created': session.get('created') or 0,
        }
        if email not in active or record['created'] > active[email].get('created', 0):
            active[email] = record
    return active


def backup_payloads() -> list[dict]:
    paths: list[pathlib.Path] = []
    latest = BACKUP_DIR / 'latest.json'
    if latest.exists():
        paths.append(latest)
    paths.extend(sorted(BACKUP_DIR.glob('backup-*.json'), reverse=True)[:200])
    payloads: list[dict] = []
    for path in paths:
        data = load_json(path, {})
        if isinstance(data, dict):
            payloads.append(data)
    return payloads


def sentinel_onboardings(payloads: list[dict]) -> list[dict]:
    seen: set[str] = set()
    rows: list[dict] = []
    for payload in payloads:
        for row in payload.get('onboarding_submissions') or []:
            if row.get('plan') != 'sentinel':
                continue
            key = row.get('queue_id') or row.get('session_id') or '|'.join([
                str(row.get('email') or '').lower(), str(row.get('names') or '')
            ])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def match_paid_customers(active: dict[str, dict], onboardings: list[dict]) -> list[dict]:
    matched: list[dict] = []
    latest_by_email: dict[str, dict] = {}
    for row in onboardings:
        email = (row.get('email') or '').strip().lower()
        if email and email in active:
            latest_by_email[email] = row
    for email, payment in active.items():
        onboarding = latest_by_email.get(email)
        if not onboarding:
            continue
        submitted_session = (onboarding.get('session_id') or '').strip()
        if submitted_session and submitted_session != payment.get('session_id'):
            continue
        matched.append({'payment': payment, 'onboarding': onboarding})
    return matched


def parse_queries(value: str) -> list[str]:
    values = re.split(r'[\n,;|]+', value or '')
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = re.sub(r'\s+', ' ', raw).strip().strip('"\'')
        key = item.casefold()
        if len(item) < 3 or key in seen:
            continue
        seen.add(key)
        cleaned.append(item[:160])
        if len(cleaned) >= MAX_QUERIES:
            break
    return cleaned


def canonical_url(url: str) -> str:
    url = html.unescape((url or '').strip())
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return ''
    query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query_pairs = [(k, v) for k, v in query_pairs if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    path = parsed.path or '/'
    return urllib.parse.urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path.rstrip('/') or '/', urllib.parse.urlencode(query_pairs), ''))


def result_record(query: str, title: str, url: str, source: str, published: str = '') -> dict | None:
    canonical = canonical_url(url)
    if not canonical:
        return None
    clean_title = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', title or ''))).strip()[:300]
    fingerprint = hashlib.sha256((query.casefold() + '|' + canonical).encode()).hexdigest()
    title_words = set(re.findall(r"[a-z0-9']+", clean_title.casefold()))
    risk_hits = sorted(title_words & RISK_TERMS)
    return {
        'fingerprint': fingerprint,
        'query': query,
        'title': clean_title or canonical,
        'url': canonical,
        'source': source,
        'published': published,
        'risk_terms': risk_hits,
        'status': 'watch' if risk_hits else 'clear',
    }


def search_duckduckgo(query: str) -> list[dict]:
    url = 'https://html.duckduckgo.com/html/?' + urllib.parse.urlencode({'q': f'"{query}"'})
    raw = http_get(url).decode('utf-8', 'replace')
    results: list[dict] = []
    pattern = re.compile(r'class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
    for href, title in pattern.findall(raw):
        decoded = html.unescape(href)
        parsed = urllib.parse.urlsplit(decoded)
        if parsed.netloc.endswith('duckduckgo.com'):
            decoded = urllib.parse.parse_qs(parsed.query).get('uddg', [decoded])[0]
        record = result_record(query, title, decoded, 'DuckDuckGo web results')
        if record:
            results.append(record)
        if len(results) >= MAX_RESULTS_PER_SOURCE:
            break
    return results


def search_google_news(query: str) -> list[dict]:
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode({
        'q': f'"{query}"', 'hl': 'en-AU', 'gl': 'AU', 'ceid': 'AU:en'
    })
    raw = http_get(url)
    root = ET.fromstring(raw)
    results: list[dict] = []
    for item in root.findall('.//item'):
        record = result_record(
            query,
            item.findtext('title') or '',
            item.findtext('link') or '',
            'Google News',
            item.findtext('pubDate') or '',
        )
        if record:
            results.append(record)
        if len(results) >= MAX_RESULTS_PER_SOURCE:
            break
    return results


def search_queries(queries: list[str]) -> tuple[list[dict], list[str]]:
    combined: dict[str, dict] = {}
    errors: list[str] = []
    for query in queries:
        for source_name, search_fn in [('web', search_duckduckgo), ('news', search_google_news)]:
            try:
                for result in search_fn(query):
                    combined[result['fingerprint']] = result
            except Exception as exc:
                errors.append(f'{source_name}:{type(exc).__name__}')
    return list(combined.values()), errors


def applescript_escape(value: str) -> str:
    return str(value or '').replace('\\', '\\\\').replace('"', '\\"')


def send_mail(recipient: str, subject: str, body: str, sender: str = SENDER) -> None:
    recipient = applescript_escape(recipient)
    subject = applescript_escape(subject)
    body = applescript_escape(body)
    sender = applescript_escape(sender)
    script = f'''
tell application "Mail"
    set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}", sender:"{sender}", visible:false}}
    tell newMessage
        make new to recipient at end of to recipients with properties {{address:"{recipient}"}}
        send
    end tell
end tell
'''
    subprocess.run(['osascript', '-e', script], check=True, timeout=45, capture_output=True, text=True)


def state_path(email: str) -> pathlib.Path:
    key = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:24]
    return STATE_DIR / f'{key}.json'


def format_results(results: list[dict], limit: int = 12) -> str:
    if not results:
        return 'No result links to list.'
    lines: list[str] = []
    for index, result in enumerate(results[:limit], 1):
        label = 'WATCH' if result.get('risk_terms') else 'OBSERVED'
        lines.append(f"{index}. [{label}] {result.get('title')}\n   Search: {result.get('query')}\n   Source: {result.get('source')}\n   {result.get('url')}")
    return '\n\n'.join(lines)


def baseline_body(customer_name: str, queries: list[str], results: list[dict], errors: list[str]) -> str:
    source_note = 'Both scheduled sources completed.' if not errors else 'One or more sources were temporarily unavailable; the monitor will retry automatically.'
    return f"""Hi {customer_name or 'there'},

Your NameWatch Alert™ monitoring file is active.

Names/search phrases monitored:
- """ + '\n- '.join(queries) + f"""

The first sweep created a private baseline with {len(results)} distinct observed result(s). This baseline is the comparison point for later alerts.

{source_note}

Important: an observed result is not automatically harmful, accurate, new, or about the correct person. It means the public search source returned it for one of the supplied phrases. Review links carefully before taking action.

FixMyNameOnline™
Operated by MadisonJade Pty Ltd
https://fixmynameonline.com/name-watch-alerts
"""


def alert_body(customer_name: str, new_results: list[dict], queries: list[str]) -> str:
    watch_count = sum(1 for item in new_results if item.get('risk_terms'))
    status = 'REVIEW RECOMMENDED' if watch_count else 'WATCH'
    return f"""Hi {customer_name or 'there'},

NameWatch Alert™ status: {status}

The scheduled sweep found {len(new_results)} result(s) that were not in the prior baseline. {watch_count} title(s) contained a watch-term indicator.

{format_results(new_results)}

A newly observed result is not necessarily newly published, harmful, accurate, or about the correct person. Do not contact a publisher or platform until you confirm the identity, URL and facts.

If exactly one old article or bad link needs a structured self-service action, the fixed-price DIY workspace is available here:
https://fixmynameonline.com/diy-action?source=namewatch_alert

Monitored phrases: {', '.join(queries)}

FixMyNameOnline™
Operated by MadisonJade Pty Ltd
"""


def clear_body(customer_name: str, queries: list[str], result_count: int) -> str:
    return f"""Hi {customer_name or 'there'},

NameWatch Alert™ monthly status: CLEAR

The scheduled sweep completed and did not find a result outside the current baseline. The baseline currently contains {result_count} distinct observed result(s).

This is a monitoring status, not a promise that every search engine, private result, social post or data-broker page has been checked.

Monitored phrases: {', '.join(queries)}

FixMyNameOnline™
Operated by MadisonJade Pty Ltd
"""


def process_customer(customer: dict, dry_run: bool = False, force: bool = False) -> dict:
    payment = customer['payment']
    onboarding = customer['onboarding']
    email = payment['email']
    queries = parse_queries(onboarding.get('names') or '')
    if not queries:
        return {'status': 'skipped_missing_queries', 'emails': 0, 'new_results': 0}

    path = state_path(email)
    state = load_json(path, {})
    last_checked = float(state.get('last_checked_epoch') or 0)
    # Avoid repeated sweeps if a cron is accidentally triggered more than once a day.
    if not force and last_checked and time.time() - last_checked < 20 * 60 * 60:
        return {'status': 'not_due', 'emails': 0, 'new_results': 0}

    results, errors = search_queries(queries)
    current = {item['fingerprint']: item for item in results}
    previous = state.get('results') or {}
    new_results = [item for key, item in current.items() if key not in previous]
    customer_name = onboarding.get('name') or ''
    emails = 0
    now = time.time()

    if not state.get('baseline_at'):
        if not dry_run:
            send_mail(email, 'NameWatch Alert™ activated — first baseline created', baseline_body(customer_name, queries, results, errors))
        emails += 1
        status = 'baseline_created'
        state['baseline_at'] = now_iso()
        state['last_status_email_epoch'] = now
    elif new_results:
        if not dry_run:
            send_mail(email, f'NameWatch Alert™ — {len(new_results)} newly observed result(s)', alert_body(customer_name, new_results, queries))
            send_mail(INTERNAL_RECIPIENT, f'FMNO NameWatch alert sent — {len(new_results)} new result(s)', f'A paid NameWatch customer received an automated alert.\n\nCustomer record: {hashlib.sha256(email.encode()).hexdigest()[:12]}\nNew results: {len(new_results)}\nWatch-term titles: {sum(1 for item in new_results if item.get("risk_terms"))}\nQueries monitored: {len(queries)}')
        emails += 2
        status = 'new_results_alerted'
        state['last_status_email_epoch'] = now
    elif now - float(state.get('last_status_email_epoch') or 0) >= MONTHLY_STATUS_SECONDS:
        if not dry_run:
            send_mail(email, 'NameWatch Alert™ monthly status — clear', clear_body(customer_name, queries, len(results)))
        emails += 1
        status = 'monthly_clear_sent'
        state['last_status_email_epoch'] = now
    else:
        status = 'checked_no_change'

    updated_results = dict(previous)
    updated_results.update(current)
    state.update({
        'email_hash': hashlib.sha256(email.encode()).hexdigest(),
        'session_id': payment.get('session_id'),
        'subscription_id': payment.get('subscription_id'),
        'subscription_status': payment.get('subscription_status'),
        'queries': queries,
        'results': updated_results,
        'last_checked_at': now_iso(),
        'last_checked_epoch': now,
        'last_errors': errors,
        'last_result_count': len(results),
    })
    if not dry_run:
        private_write(path, state)
    return {'status': status, 'emails': emails, 'new_results': len(new_results), 'result_count': len(results), 'errors': errors}


def check_sender_account() -> bool:
    escaped = applescript_escape(SENDER)
    script = f'''
tell application "Mail"
    repeat with a in every account
        try
            if (user name of a as text) is "{escaped}" then return "FOUND"
        end try
    end repeat
    return "MISSING"
end tell
'''
    result = subprocess.run(['osascript', '-e', script], check=True, timeout=30, capture_output=True, text=True)
    return result.stdout.strip() == 'FOUND'


def self_test() -> int:
    queries = ['Fix My Name Online']
    results, errors = search_queries(queries)
    print(json.dumps({'ok': bool(results), 'result_count': len(results), 'sources': sorted({r['source'] for r in results}), 'errors': errors}, indent=2))
    return 0 if results else 1


def main() -> int:
    parser = argparse.ArgumentParser(description='FMNO paid NameWatch monitor')
    parser.add_argument('--dry-run', action='store_true', help='run discovery/search without writing state or sending email')
    parser.add_argument('--force', action='store_true', help='ignore the once-per-day guard')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--test-email', action='store_true', help='send a sender-path test only to the internal recipient')
    args = parser.parse_args()

    if args.self_test:
        return self_test()
    if not check_sender_account():
        raise RuntimeError(f'Apple Mail sender account not found: {SENDER}')
    if args.test_email:
        send_mail(INTERNAL_RECIPIENT, 'FMNO NameWatch sender-path test', 'NameWatch Alert™ automation can send from admin@fixmynameonline.com. No customer was contacted.')
        print('TEST_EMAIL_SENT')
        return 0

    env = load_env(STRIPE_ENV)
    secret_key = env.get('STRIPE_SECRET_KEY') or env.get('FMNO_STRIPE_SECRET_KEY') or ''
    if not secret_key:
        raise RuntimeError('FMNO Stripe secret key is missing')
    active = active_namewatch_checkouts(secret_key)
    onboardings = sentinel_onboardings(backup_payloads())
    customers = match_paid_customers(active, onboardings)

    totals = {'customers': len(customers), 'emails': 0, 'new_results': 0, 'errors': 0}
    statuses: dict[str, int] = {}
    for customer in customers:
        try:
            result = process_customer(customer, dry_run=args.dry_run, force=args.force)
            status = result.get('status', 'unknown')
            statuses[status] = statuses.get(status, 0) + 1
            totals['emails'] += int(result.get('emails') or 0)
            totals['new_results'] += int(result.get('new_results') or 0)
            totals['errors'] += len(result.get('errors') or [])
        except Exception:
            totals['errors'] += 1
            statuses['failed'] = statuses.get('failed', 0) + 1

    if args.verbose or totals['emails'] or totals['new_results'] or totals['errors']:
        print('FMNO_NAMEWATCH ' + json.dumps({'totals': totals, 'statuses': statuses, 'dry_run': args.dry_run}, sort_keys=True))
    return 1 if statuses.get('failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
