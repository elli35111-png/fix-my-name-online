"""Paid self-service contract; synthetic Stripe only, no customer data."""
import json
from urllib.parse import urlparse

import pytest
from bs4 import BeautifulSoup
import server
import paid_actions as actions


@pytest.fixture
def shop(tmp_path, monkeypatch):
    server.app.config.update(TESTING=True)
    monkeypatch.setattr(server, 'DATA_DIR', tmp_path)
    monkeypatch.setattr(server, 'CLICK_EVENTS_FILE', tmp_path / 'clicks.jsonl')
    monkeypatch.setattr(server, 'DIY_ACTIONS_FILE', tmp_path / 'legacy.jsonl')
    monkeypatch.setattr(server.stripe, 'api_key', 'sk_test_synthetic')
    monkeypatch.setenv('FMNO_APPROVAL_SECRET', 'synthetic-secret-with-at-least-32-characters')
    monkeypatch.setenv('STRIPE_PRICE_DIY_SINGLE', 'price_single')
    monkeypatch.setenv('STRIPE_PRICE_DIY_PACK', 'price_pack')
    monkeypatch.setenv('STRIPE_PRICE_DIY_ACTION', 'price_legacy')
    monkeypatch.setattr(server, 'send_brevo_email', lambda *a, **kw: True)
    monkeypatch.setattr(server, 'tracking_head', lambda: '<script>TRACKING_FOR_TEST</script>')
    for name in ('safe_create_fulfilment_case', 'send_telegram_alert', 'send_paid_customer_alert'):
        monkeypatch.setattr(server, name, lambda *a, **kw: pytest.fail('No manual fulfilment or owner alert'))
    sessions = {}
    def session_for(sid, plan='single', **overrides):
        row = {'id': sid, 'status': 'complete', 'payment_status': 'paid', 'mode': 'payment',
               'currency': 'usd', 'amount_total': 1900 if plan == 'single' else 4900,
               'metadata': {'tier': 'diy-single' if plan == 'single' else 'diy-pack'},
               'customer_details': {'email': 'person@example.com'}, 'payment_intent': 'pi_synthetic',
               'line_items': {'data': [{'quantity': 1, 'price': {'id': 'price_' + plan}}]}}
        row.update(overrides)
        sessions[sid] = row
        return row
    monkeypatch.setattr(server.stripe.checkout.Session, 'retrieve', lambda sid, **kw: sessions.get(sid, {}))
    monkeypatch.setattr(server.stripe.Refund, 'list', lambda **kw: {'data': []})
    return server.app.test_client(), session_for


def start(client, sid):
    res = client.get('/diy-action/start?session_id=' + sid)
    assert res.status_code == 303
    page = client.get(res.headers['Location'])
    assert page.status_code == 200
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(page.data, 'html.parser')
    return soup.select_one('[name=csrf]')['value']


def fields(csrf, target='https://example.com/article', **extra):
    return dict(csrf=csrf, target_url=target, name='Test Person', country_state='Australia',
                authority='self', issue_type='outdated', requested_outcome='correct',
                problem_summary='The page omits a later update.', evidence_summary='A dated correction.',
                correct_information='The corrected outcome is recorded.', truth_confirmed='yes',
                scope_confirmed='yes', related_confirmed='yes', **extra)


@pytest.mark.parametrize('plan,cap', [('single', 1), ('pack', 5)])
def test_caps_persist_and_same_url_edit_is_not_another_slot(shop, plan, cap):
    client, session_for = shop
    sid = 'cs_test_purchase_' + plan
    session_for(sid, plan)
    csrf = start(client, sid)
    for i in range(cap):
        assert client.post('/diy-action/generate', data=fields(csrf, f'https://example.com/{i}')).status_code == 303
    assert client.post('/diy-action/generate', data=fields(csrf, 'https://example.com/0')).status_code == 303
    assert client.post('/diy-action/generate', data=fields(csrf, 'https://example.com/overflow')).status_code == 409
    body = client.get('/diy-action/workspace').get_data(as_text=True)
    assert f'{cap} of {cap}' in body
    assert 'TRACKING_FOR_TEST' not in body
    assert 'csrf' in body


@pytest.mark.parametrize('overrides', [
    {'payment_status': 'unpaid'}, {'status': 'open'}, {'metadata': {'tier': 'sentinel'}},
    {'currency': 'aud'}, {'line_items': {'data': [{'quantity': 1, 'price': {'id': 'price_other'}}]}},
    {'amount_total': 0}, {'mode': 'subscription'},
])
def test_wrong_or_unpaid_checkout_cannot_unlock(shop, overrides):
    client, session_for = shop
    session_for('cs_test_denied', **overrides)
    assert client.get('/diy-action/start?session_id=cs_test_denied').status_code == 402
    assert client.get('/diy-action/workspace').status_code == 401


def test_access_errors_point_to_recovery_not_back_to_the_same_error(shop):
    client, _ = shop
    for path, status in [('/diy-action/workspace', 401), ('/diy-action/start?session_id=cs_test_nothing', 402),
                         ('/success.html?tier=sentinel&session_id=cs_test_nothing', 402)]:
        res = client.get(path)
        assert res.status_code == status, path
        soup = BeautifulSoup(res.data, 'html.parser')
        buttons = soup.select('.card a.btn')
        assert buttons[0]['href'] == '/diy-action/recover' and buttons[0].get_text(strip=True) == 'Get a new access link', path
        assert '/self-service' in [a['href'] for a in buttons], path
        assert not soup.select('a[href="/diy-action/workspace"]'), path
        assert res.headers['X-Robots-Tag'] == 'noindex, nofollow'
    success = client.get('/success.html?tier=sentinel&session_id=cs_test_nothing').get_data(as_text=True)
    assert 'Payment has not been verified' not in success and 'nothing new has been charged' in success
    # Errors inside an unlocked workspace still go back to it.
    assert 'href="/diy-action/workspace"' in client.get('/diy-action/export.pdf').get_data(as_text=True)


def test_old_static_token_never_unlocks(shop):
    client, _ = shop
    assert client.get('/diy-action/start?session_id=cs_live_madeup&checkout_token=old').status_code == 402


def test_legacy_paid_customer_keeps_one_url_access(shop):
    client, session_for = shop
    session_for('cs_test_old_paid', 'pack', metadata={'tier': 'diy-action'},
                line_items={'data': [{'quantity': 1, 'price': {'id': 'price_legacy'}}]})
    csrf = start(client, 'cs_test_old_paid')
    assert client.post('/diy-action/generate', data=fields(csrf)).status_code == 303
    assert client.post('/diy-action/generate', data=fields(csrf, 'https://example.com/second')).status_code == 409


def test_csrf_validation_url_limits_and_safety(shop):
    client, session_for = shop
    session_for('cs_test_checks')
    csrf = start(client, 'cs_test_checks')
    assert client.post('/diy-action/generate', data=fields('bad')).status_code == 403
    for update in ({'target_url': 'javascript:alert(1)'}, {'target_url': 'https://user:password@example.com'},
                   {'name': 'X' * 161}, {'scope_confirmed': ''}, {'authority': 'stranger'},
                   {'problem_summary': 'There is an active court proceeding involving a minor.'}):
        data = fields(csrf)
        data.update(update)
        assert client.post('/diy-action/generate', data=data).status_code == 400


def test_exports_save_updates_and_isolation(shop):
    client, session_for = shop
    session_for('cs_test_export')
    csrf = start(client, 'cs_test_export')
    client.post('/diy-action/generate', data=fields(csrf))
    pack = client.get('/diy-action/export.json')
    assert pack.status_code == 200
    assert 'no-store' in pack.headers['Cache-Control']
    data = pack.get_json()
    aid = data['actions'][0]['id']
    assert 'session_id' not in pack.get_data(as_text=True)
    assert 'csrf' not in pack.get_data(as_text=True)
    assert client.post('/diy-action/save', data={'csrf': csrf, 'action_id': aid, 'draft': '<script>bad</script>',
        'notes': 'My own note', 'status': 'submitted', 'reference': 'REF-1', 'followup': '2026-11-20'}).status_code == 303
    text = client.get('/diy-action/export.txt').get_data(as_text=True)
    assert 'REF-1' in text and 'My own note' in text and '<script>bad</script>' in text
    html = client.get('/diy-action/workspace').get_data(as_text=True)
    assert '&lt;script&gt;bad&lt;/script&gt;' in html and '<script>bad</script>' not in html
    cal = client.get('/diy-action/reminder.ics?action_id=' + aid)
    assert 'BEGIN:VCALENDAR' in cal.get_data(as_text=True)
    assert 'DTSTART;VALUE=DATE:20261120' in cal.get_data(as_text=True)
    session_for('cs_test_other')
    other = server.app.test_client()
    other_csrf = start(other, 'cs_test_other')
    assert other.get('/diy-action/reminder.ics?action_id=' + aid).status_code == 404
    assert other.post('/diy-action/save', data={'csrf': other_csrf, 'action_id': aid}).status_code == 404
    assert 'REF-1' not in other.get('/diy-action/export.txt').get_data(as_text=True)


def test_refunded_checkout_cannot_unlock(shop, monkeypatch):
    client, session_for = shop
    session_for('cs_test_refunded')
    monkeypatch.setattr(server.stripe.Refund, 'list', lambda **kw: {'data': [{'status': 'succeeded'}]})
    assert client.get('/diy-action/start?session_id=cs_test_refunded').status_code == 402


def test_new_namewatch_sales_paused(shop):
    client, _ = shop
    for tier in ('sentinel', 'namewatch', 'name-watch', 'name-watch-alerts'):
        r = client.get('/checkout/' + tier)
        assert r.status_code == 302 and urlparse(r.headers['Location']).path == '/name-watch-alerts'
    body = client.get('/name-watch-alerts').get_data(as_text=True)
    assert 'NameWatch is coming back.' in body and 'New sign-ups are paused' in body
    assert 'action="/name-watch-alerts/waitlist"' in body
    assert '/billing' in body
    assert '/checkout/sentinel' not in body


def test_pricing_and_checkout_amounts(shop, monkeypatch):
    client, _ = shop
    calls = []
    monkeypatch.setattr(server.stripe.Price, 'retrieve', lambda pid: {'id': pid, 'active': True,
        'unit_amount': 1900 if pid == 'price_single' else 4900, 'currency': 'usd', 'type': 'one_time'})
    monkeypatch.setattr(server.stripe.checkout.Session, 'create', lambda **kw: calls.append(kw) or {'url': 'https://checkout.stripe.test/ok'})
    for tier, price in [('diy-single', 'price_single'), ('diy-action', 'price_single')]:
        result = client.get('/checkout/' + tier)
        assert result.status_code == 302
        assert calls[-1]['line_items'] == [{'price': price, 'quantity': 1}]
        assert calls[-1]['mode'] == 'payment'
        assert calls[-1]['allow_promotion_codes'] is False
    body = client.get('/diy-action').get_data(as_text=True)
    assert 'US$19' in body and 'US$49' not in body and 'five related URLs' not in body
    assert client.get('/checkout/diy-pack').headers['Location'] == '/diy-action'


def test_wrong_configured_price_fails_closed(shop, monkeypatch):
    client, _ = shop
    monkeypatch.setattr(server.stripe.Price, 'retrieve', lambda pid: {'active': True, 'unit_amount': 4900, 'currency': 'usd', 'type': 'one_time'})
    assert client.get('/checkout/diy-single').status_code == 503


def test_webhook_no_owner_queue_idempotent(shop, monkeypatch):
    client, session_for = shop
    session = session_for('cs_test_webhook')
    monkeypatch.setattr(server, 'STRIPE_WEBHOOK_SECRET', 'whsec_synthetic')
    monkeypatch.setattr(server.stripe.Webhook, 'construct_event', lambda *a: {'id': 'evt_synthetic',
        'type': 'checkout.session.completed', 'data': {'object': session}})
    for _ in range(2):
        assert client.post('/webhook', data=b'synthetic').status_code == 200
    assert len(actions.backup(server)['workspaces']) == 1


def test_questions_no_longer_creates_manual_work(shop):
    client, _ = shop
    response = client.get('/questions')
    assert response.status_code == 301 and response.headers['Location'] == '/contact'
    assert client.post('/submit-question', data={'name': 'x', 'email': 'x@example.com', 'question': 'x'}).status_code == 410


def test_refund_button_hidden_once_letters_exist_and_letters_are_readable(shop):
    client, session_for = shop
    session_for('cs_test_refund_ui')
    csrf = start(client, 'cs_test_refund_ui')
    assert 'Refund this unused purchase' in client.get('/diy-action/workspace').get_data(as_text=True)
    data = fields(csrf)
    data['requested_outcome'] = 'anonymise'
    assert client.post('/diy-action/generate', data=data).status_code == 303
    html = client.get('/diy-action/workspace').get_data(as_text=True)
    assert 'Refund this unused purchase' not in html
    assert 'Follow-up letter' in html and 'Second letter' in html
    assert 'remove my name and other identifying details from the page' in html
    text = client.get('/diy-action/export.txt').get_data(as_text=True)
    assert '=== 1. REQUEST LETTER ===' in text and '=== 3. SECOND LETTER' in text
    assert 'ISSUE_TYPE:' not in text  # no raw key dump
    for banned in ('lawsuit', 'legal action', 'we will sue', 'defamation'):
        assert banned not in text.lower()


def test_unused_refund_verified_and_existing_cookie_revoked(shop, monkeypatch):
    import time
    client, session_for = shop
    session_for('cs_test_unused_refund', created=int(time.time()))
    csrf = start(client, 'cs_test_unused_refund')
    cookie = client.get_cookie(actions.COOKIE, path='/diy-action').value
    calls = []
    monkeypatch.setattr(server.stripe.Refund, 'create', lambda **kw: calls.append(kw) or {'id': 're_synthetic'})
    monkeypatch.setattr(server.stripe.Refund, 'retrieve', lambda rid: {'id': rid, 'status': 'succeeded'})
    response = client.post('/diy-action/refund', data={'csrf': csrf, 'confirm': 'refund'})
    assert response.status_code == 200 and 'Refund recorded by Stripe' in response.get_data(as_text=True)
    assert len(calls) == 1 and calls[0]['idempotency_key'].startswith('fmno-unused-')
    client.set_cookie(actions.COOKIE, cookie, path='/diy-action')
    assert client.get('/diy-action/workspace').status_code == 401


def test_used_or_old_purchase_not_auto_refunded(shop, monkeypatch):
    import time
    client, session_for = shop
    monkeypatch.setattr(server.stripe.Refund, 'create', lambda **kw: pytest.fail('Refund must be rejected'))
    session_for('cs_test_old_refund', created=int(time.time()) - 8 * 86400)
    csrf = start(client, 'cs_test_old_refund')
    assert client.post('/diy-action/refund', data={'csrf': csrf, 'confirm': 'refund'}).status_code == 400
    session_for('cs_test_used_refund', created=int(time.time()))
    csrf = start(client, 'cs_test_used_refund')
    client.post('/diy-action/generate', data=fields(csrf))
    assert client.post('/diy-action/refund', data={'csrf': csrf, 'confirm': 'refund'}).status_code == 400


def test_pending_refund_blocks_racing_action_and_retries_same_key(shop, monkeypatch):
    import time
    client, session_for = shop
    session_for('cs_test_pending_refund', created=int(time.time()))
    csrf = start(client, 'cs_test_pending_refund')
    calls = []
    def failed(**kw):
        calls.append(kw['idempotency_key'])
        raise TimeoutError('synthetic')
    monkeypatch.setattr(server.stripe.Refund, 'create', failed)
    for _ in range(2):
        assert client.post('/diy-action/refund', data={'csrf': csrf, 'confirm': 'refund'}).status_code == 503
    assert calls[0] == calls[1]
    assert client.post('/diy-action/generate', data=fields(csrf)).status_code == 409


def test_recovery_has_same_response_and_throttles(shop, monkeypatch):
    client, session_for = shop
    session_for('cs_test_recover')
    start(client, 'cs_test_recover')
    sent = []
    monkeypatch.setattr(server, 'send_brevo_email', lambda *a: sent.append(a) or True)
    first = client.post('/diy-action/recover', data={'email': 'person@example.com'})
    again = client.post('/diy-action/recover', data={'email': 'person@example.com'})
    absent = client.post('/diy-action/recover', data={'email': 'absent@example.com'})
    assert first.data == again.data == absent.data
    assert len(sent) == 1 and sent[0][0] == 'person@example.com'
    assert 'cs_test_recover' in sent[0][3]
    assert 'cs_test_recover' not in first.get_data(as_text=True)


def test_customer_browser_flow_mobile(shop, tmp_path):
    from threading import Thread
    from werkzeug.serving import make_server
    from playwright.sync_api import sync_playwright
    _, session_for = shop
    session_for('cs_test_browser_flow')
    http = make_server('127.0.0.1', 0, server.app)
    thread = Thread(target=http.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{http.server_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 360, 'height': 800})
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(base + '/diy-action/start?session_id=cs_test_browser_flow')
            assert page.url.endswith('/diy-action/workspace')
            for key, value in fields('').items():
                loc = page.locator('[name="' + key + '"]')
                if key == 'csrf':
                    continue
                if key.endswith('_confirmed'):
                    loc.check()
                elif key in {'authority', 'issue_type', 'requested_outcome'}:
                    loc.select_option(value)
                else:
                    loc.fill(value)
            page.get_by_role('button', name='Create my letters').click()
            page.locator('[name=draft]').fill('Customer edited request')
            page.locator('[name=reference]').fill('REF-BROWSER')
            page.locator('[name=followup]').fill('2026-11-20')
            page.get_by_role('button', name='Save my changes').click()
            page.reload()
            assert page.locator('[name=draft]').input_value() == 'Customer edited request'
            with page.expect_download() as event:
                page.get_by_role('link', name='Download as text').click()
            event.value.save_as(tmp_path / 'pack.txt')
            assert 'REF-BROWSER' in (tmp_path / 'pack.txt').read_text()
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            (server.BASE_DIR / 'qa_proof').mkdir(exist_ok=True)
            page.screenshot(path=str(server.BASE_DIR / 'qa_proof' / 'paid-action-mobile.png'), full_page=True)
            assert errors == []
            browser.close()
    finally:
        http.shutdown()
        thread.join()


# ---- 12 Oct 2026 review: the letters people pay for must read properly ----

@pytest.mark.parametrize('outcome', list(actions.ASK))
@pytest.mark.parametrize('issue', list(actions.ISSUES))
@pytest.mark.parametrize('authority', ['self', 'authorised'])
def test_letters_read_properly_for_every_choice(outcome, issue, authority):
    data = dict(actions.SAMPLE, requested_outcome=outcome, issue_type=issue, authority=authority)
    letters = actions.draft_letters(data)
    text = '\n'.join(letters)
    assert 'on this page:\n' not in text.replace('this page:\n' + data['target_url'], '')  # the old doubled phrase
    for doubled in ('from the page on this page', 'take the page down on this page', 'stop showing it on this page',
                    'contains name confusion', '{', '}'):
        assert doubled not in text, (doubled, outcome, issue, authority)
    request_letter, followup, second = letters
    if authority == 'authorised':
        assert 'on behalf of [name of the person the page is about]' in request_letter
        for first_person in ('about me', 'my name', 'my personal'):
            assert first_person not in request_letter and first_person not in second, first_person
    else:
        assert 'on behalf of' not in request_letter
    if issue == 'wrong-person':
        assert ('I’m not that person' if authority == 'self' else 'They’re not that person') in request_letter
    # The second letter names the link once, straight after the ask.
    assert second.count('asking you to ') == 1
    assert second.split('asking you to ')[1].split(':\n')[1].startswith(data['target_url'])


def test_scope_check_allows_ordinary_words_and_still_stops_real_risks():
    ok = ['It was a minor offence in 2012.', 'A minor traffic matter from 2015.', 'There is a minor error in the date.',
          'Review of my childcare centre.']
    stop = ['There is an active court proceeding involving a minor.', 'It names my child.', 'The case is still running.',
            'He threatened me after it was posted.', 'Someone is trying sextortion.']
    assert not [t for t in ok if actions.OUT_OF_SCOPE.search(t)]
    assert all(actions.OUT_OF_SCOPE.search(t) for t in stop)


def test_out_of_scope_message_is_plain_and_creates_nothing(shop):
    client, session_for = shop
    session_for('cs_test_scope')
    csrf = start(client, 'cs_test_scope')
    risky = fields(csrf); risky['problem_summary'] = 'It names my child.'
    res = client.post('/diy-action/generate', data=risky)
    text = res.get_data(as_text=True)
    assert res.status_code == 400
    assert 'automated' not in text.lower() and 'isn’t the right tool' in text
    assert actions.backup(server)['actions'] == []
    ordinary = fields(csrf); ordinary['problem_summary'] = 'It was a minor offence in 2012.'
    assert client.post('/diy-action/generate', data=ordinary).status_code == 303


def test_pack_emails_use_plain_names(shop, monkeypatch):
    client, session_for = shop
    session = session_for('cs_test_mailer')
    sent = []
    monkeypatch.setattr(server, 'send_brevo_email', lambda *a: sent.append(a) or True)
    monkeypatch.setattr(server, 'STRIPE_WEBHOOK_SECRET', 'whsec_synthetic')
    monkeypatch.setattr(server.stripe.Webhook, 'construct_event', lambda *a: {'id': 'evt_mail',
        'type': 'checkout.session.completed', 'data': {'object': session}})
    assert client.post('/webhook', data=b'synthetic').status_code == 200
    start(client, 'cs_test_mailer')
    client.post('/diy-action/recover', data={'email': 'person@example.com'})
    assert len(sent) == 2
    for _to, _name, subject, html in sent:
        words = (subject + html).lower()
        assert 'letter pack' in words
        for old in ('action workspace', 'fmno workspace', 'grant access', 'automated'):
            assert old not in words, old
