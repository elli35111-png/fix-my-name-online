"""Snapshot intake regression tests; all records/network effects are isolated."""
import json
import pytest
import server


@pytest.fixture
def client(monkeypatch, tmp_path):
    server.app.testing = True
    for attr in ('LEADS_FILE', 'FULFILMENT_QUEUE_FILE', 'CLICK_EVENTS_FILE', 'CASE_ROOMS_FILE', 'CONCIERGE_TRANSCRIPTS_FILE'):
        monkeypatch.setattr(server, attr, tmp_path / (attr + '.jsonl'))
    monkeypatch.setattr(server, 'safe_create_fulfilment_case', lambda *a, **k: None)
    monkeypatch.setattr(server, 'run_free_snapshot_pipeline', lambda *a: None)
    monkeypatch.setattr(server, 'send_telegram_alert', lambda *a, **k: None)
    monkeypatch.setattr(server, 'record_email_alert_status', lambda *a, **k: None)
    return server.app.test_client()


def valid():
    return {'name': 'QA Person', 'email': 'qa@example.com', 'country_state': 'Australia, NSW',
            'authority': 'self', 'consent': 'yes', 'goal': 'An old article needs current context.',
            'case_type': 'Old article or outdated result', 'problem_links': '', 'source_page': 'qa_test'}


def test_homepage_structured_data_is_valid_json(client):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(client.get('/').get_data(as_text=True), 'html.parser')
    data = json.loads(soup.select_one('script[type="application/ld+json"]').string)
    assert data['@context'] == 'https://schema.org'
    assert {'Organization', 'WebSite', 'FAQPage'} <= {row['@type'] for row in data['@graph']}
    org = next(row for row in data['@graph'] if row['@type'] == 'Organization')
    assert org['legalName'] == 'Madison Jade Pty Ltd' and org['taxID'] == '56661580936'


@pytest.mark.parametrize('route', ['/app', '/free-search-snapshot'])
def test_old_intake_urls_now_open_the_free_check(client, route):
    response = client.get(route)
    assert response.status_code == 301
    assert response.headers['Location'] == '/self-service?from=snapshot'


def no_records():
    for attr in ('LEADS_FILE', 'FULFILMENT_QUEUE_FILE', 'CLICK_EVENTS_FILE', 'CASE_ROOMS_FILE', 'CONCIERGE_TRANSCRIPTS_FILE'):
        assert not getattr(server, attr).exists(), attr


def seed_room(data=None):
    """An existing private room from before the Snapshot was retired."""
    data = data or valid()
    triage = server.triage_snapshot(data)
    queue_item = server.make_queue_item('free_snapshot', data, triage)
    room = server.save_case_room(queue_item, data, triage)
    return queue_item['id'], room['access_token']


@pytest.mark.parametrize('data', [valid(), {**valid(), 'goal': ''}, {**valid(), 'website': 'spam.invalid'}, {}])
def test_retired_snapshot_form_stores_and_sends_nothing(client, monkeypatch, data):
    """Old cached forms can still POST. Nothing is read, stored, emailed or alerted."""
    def forbidden(*args, **kwargs):
        pytest.fail('The retired Snapshot must not create records, email or alerts')
    for name in ('send_brevo_email', 'send_internal_alert_email', 'send_telegram_alert', 'safe_create_fulfilment_case', 'save_case_room', 'append_jsonl'):
        monkeypatch.setattr(server, name, forbidden)
    response = client.post('/submit-snapshot', data=data)
    assert response.status_code == 303
    assert response.headers['Location'] == '/self-service?from=snapshot'
    assert response.headers['Cache-Control'] == 'no-store, private'
    no_records()


@pytest.mark.parametrize('payload', [{'collected': {**valid(), 'contact_name': 'QA Person', 'names_to_check': 'QA Person'}}, {'collected': ['invalid']}, ['invalid'], {}])
def test_retired_concierge_intake_stores_and_sends_nothing(client, monkeypatch, payload):
    def forbidden(*args, **kwargs):
        pytest.fail('The retired concierge intake must not create records or email')
    for name in ('send_brevo_email', 'send_internal_alert_email', 'append_jsonl', 'save_case_room'):
        monkeypatch.setattr(server, name, forbidden)
    response = client.post('/api/concierge/submit', json=payload)
    assert response.status_code == 410
    body = response.get_json()
    assert body['ok'] is False and body['redirect'] == '/self-service?from=snapshot'
    no_records()


def test_snapshot_email_is_gone():
    assert not hasattr(server, 'send_snapshot_emails')


def test_get_submit_returns_form_not_405(client):
    response = client.get('/submit-snapshot')
    assert response.status_code == 303
    assert response.headers['Location'] == '/self-service'


def test_private_room_and_paid_workspace_not_indexable(client):
    for route in ('/private-case-room/not-a-case', '/diy-action/start'):
        response = client.get(route)
        assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
        assert response.headers['Referrer-Policy'] == 'no-referrer'


def test_review_or_high_risk_not_upsold_wrong_pack():
    for key in ('review-defence', 'repair-plan', 'high-risk'):
        assert server.TRIAGE_NEXT_STEPS[key]['url'] != '/diy-action'


def test_room_is_honest_private_and_has_no_external_trackers(client, monkeypatch):
    monkeypatch.setenv('FMNO_GA_MEASUREMENT_ID', 'G-TEST')
    monkeypatch.setenv('FMNO_META_PIXEL_ID', '12345')
    queue_id, token = seed_room()
    response = client.get('/private-case-room/' + queue_id + '?access_token=' + token)
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'not a live Google search' in text
    assert 'Reputation Risk Score™:' not in text
    assert 'Snapshot review / QC' not in text
    assert 'MadisonJade' not in text and 'Madison Jade Pty Ltd' in text
    assert 'googletagmanager' not in text and 'connect.facebook.net' not in text
    assert response.headers['Cache-Control'] == 'no-store, private'
    assert client.get('/private-case-room/' + queue_id + '?access_token=wrong').status_code == 403


def test_snapshot_received_uses_current_wording(client):
    text = client.get('/snapshot-received?ref=FMNO-1').get_data(as_text=True)
    assert 'Free Search Snapshot™' not in text and 'now the free check' in text


def test_keyword_boundaries_avoid_false_high_risk():
    assert server.triage_snapshot({'goal': 'My old WordPress article is outdated.'})['key'] == 'removal-review'
    assert server.triage_snapshot({'goal': 'There are threats to my child.'})['key'] == 'high-risk'
    assert server.triage_snapshot({'case_type': 'Private information showing online', 'goal': 'Remove my information from an article'})['key'] == 'repair-plan'
    assert server.triage_snapshot({'case_type': 'Wrong person / name confusion', 'goal': 'Remove the article'})['key'] == 'repair-plan'
    assert server.triage_snapshot({'case_type': 'Monitoring / new mentions', 'goal': 'An old article exists'})['key'] == 'alerts'


def test_backup_includes_private_workflow_records(client, monkeypatch, tmp_path):
    monkeypatch.setenv('FMNO_ADMIN_TOKEN', 'test-only-admin-token')
    monkeypatch.setattr(server, 'list_cases', lambda **kwargs: [])
    for attr in ('DIY_ACTIONS_FILE', 'ONBOARDING_FILE', 'QUESTIONS_FILE'):
        monkeypatch.setattr(server, attr, tmp_path / (attr + '.jsonl'))
    assert client.get('/admin/fulfilment/export/backup.json').status_code == 401
    data = client.get('/admin/fulfilment/export/backup.json', headers={'X-FMNO-Admin-Token': 'test-only-admin-token'}).get_json()
    for key in ('private_case_rooms', 'concierge_transcripts', 'diy_actions'):
        assert key in data


@pytest.mark.parametrize('goal, key', [('Monitoring new mentions please', 'alerts'), ('My old article is outdated', 'removal-review'),
                                       ('A fake review on Google', 'review-defence'), ('Something else', 'repair-plan'),
                                       ('There are threats to my child', 'high-risk')])
def test_old_snapshot_links_show_todays_products_and_working_links(client, goal, key):
    data = {**valid(), 'goal': goal, 'case_type': ''}
    assert server.triage_snapshot(data)['key'] == key
    queue_id, token = seed_room(data)
    html = client.get('/private-case-room/' + queue_id + '?access_token=' + token).get_data(as_text=True)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    text = soup.get_text(' ', strip=True)
    for old in ('DIY', 'Action Workspace', 'action workspace', 'from US$19', 'fixed-scope', 'Open free self-service',
                'automated', 'pathway', 'exact scope'):
        assert old not in text, (key, old)
    step = server.TRIAGE_NEXT_STEPS[key]
    assert '™' not in step['label'] + step['summary'] + step['cta']
    assert step['summary'] in text
    if key == 'removal-review':
        assert 'letter pack' in text and 'US$19' in text
    # Every link on the page opens a real page (no missing #anchors).
    for a in soup.select('main a[href], .card a[href]'):
        href = a['href']
        if href.startswith('mailto:') or href.startswith('http'):
            continue
        path, _, frag = href.partition('#')
        res = client.get(path)
        assert res.status_code == 200, href
        if frag:
            assert f'id="{frag}"' in res.get_data(as_text=True), href
