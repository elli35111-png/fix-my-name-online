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
    monkeypatch.setattr(server, 'send_snapshot_emails', lambda *a, **k: {})
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
    assert {row['@type'] for row in data['@graph']} == {'Organization', 'WebSite', 'FAQPage'}


@pytest.mark.parametrize('route', ['/app', '/free-search-snapshot'])
def test_complete_accessible_form(client, route):
    from bs4 import BeautifulSoup
    body = client.get(route).get_data(as_text=True)
    soup = BeautifulSoup(body, 'html.parser')
    for name in ('name', 'email', 'country_state', 'authority', 'goal', 'consent'):
        field = soup.select_one('[name="' + name + '"]')
        assert field and field.has_attr('required'), name
        assert soup.select_one('label[for="' + field['id'] + '"]'), name
    assert 'not a live Google search' in body
    assert '/self-service' in body
    assert soup.select_one('[name="problem_links"]') is not None
    assert not soup.select_one('[name="problem_links"]').has_attr('required')


@pytest.mark.parametrize('field,value', [('country_state',''), ('authority',''), ('authority','no'), ('goal',''), ('consent',''), ('email','invalid@'), ('name','<a href="https://spam.invalid">offer</a>')])
def test_invalid_submission_does_not_consume_free_allowance(client, field, value):
    data = valid(); data[field] = value
    result = client.post('/submit-snapshot', data=data)
    assert result.status_code == 400
    assert not server.LEADS_FILE.exists()
    assert 'qa@example.com' in result.get_data(as_text=True) or field == 'email'


def test_honeypot_never_creates_record(client):
    data = valid(); data['website'] = 'spam.invalid'
    assert client.post('/submit-snapshot', data=data).status_code == 400
    assert not server.LEADS_FILE.exists()


def test_valid_no_url_submission_preserves_context(client):
    response = client.post('/submit-snapshot', data=valid())
    assert response.status_code == 200
    lead = json.loads(server.LEADS_FILE.read_text().splitlines()[0])
    assert lead['country_state'] == 'Australia, NSW'
    assert lead['authority'] == 'self'
    assert lead['consent'] == 'yes'
    text = response.get_data(as_text=True)
    assert 'not a live Google search' in text
    assert '/self-service' in text
    assert 'will privately review' not in text
    events = [json.loads(line) for line in server.CLICK_EVENTS_FILE.read_text().splitlines()]
    assert not any('email' in event or 'searched_name' in event for event in events)
    assert response.headers['Cache-Control'] == 'no-store, private'
    assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'


def test_concierge_cannot_bypass_authority(client):
    data = valid(); data.pop('authority')
    data['contact_name'] = data['name']; data['names_to_check'] = data['name']
    response = client.post('/api/concierge/submit', json={'collected': data})
    assert response.status_code == 400
    assert not server.LEADS_FILE.exists()


def test_concierge_success_preserves_location(client):
    data = valid(); data['contact_name'] = data['name']; data['names_to_check'] = data['name']
    response = client.post('/api/concierge/submit', json={'collected': data})
    assert response.status_code == 200
    lead = json.loads(server.LEADS_FILE.read_text().splitlines()[0])
    assert lead['country_state'] == data['country_state']
    assert lead['authority'] == 'self'


def test_get_submit_returns_form_not_405(client):
    response = client.get('/submit-snapshot')
    assert response.status_code == 303
    assert response.headers['Location'] == '/free-search-snapshot'


def test_private_room_and_paid_workspace_not_indexable(client):
    for route in ('/private-case-room/not-a-case', '/diy-action/start'):
        response = client.get(route)
        assert response.headers['X-Robots-Tag'] == 'noindex, nofollow'
        assert response.headers['Referrer-Policy'] == 'no-referrer'


def test_review_or_high_risk_not_upsold_wrong_pack():
    for key in ('review-defence', 'repair-plan', 'high-risk'):
        assert server.TRIAGE_NEXT_STEPS[key]['url'] != '/diy-action'


def test_success_never_creates_manual_work_or_alerts(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Self-service intake must not create owner work or alerts')
    for name in ('safe_create_fulfilment_case', 'run_free_snapshot_pipeline', 'send_telegram_alert'):
        monkeypatch.setattr(server, name, forbidden)
    assert client.post('/submit-snapshot', data=valid()).status_code == 200
    queue = json.loads(server.FULFILMENT_QUEUE_FILE.read_text().splitlines()[0])
    assert queue['status'] == 'automated_guidance_available'


def test_room_is_honest_private_and_has_no_external_trackers(client, monkeypatch):
    monkeypatch.setenv('FMNO_GA_MEASUREMENT_ID', 'G-TEST')
    monkeypatch.setenv('FMNO_META_PIXEL_ID', '12345')
    client.post('/submit-snapshot', data=valid())
    room = json.loads(server.CASE_ROOMS_FILE.read_text().splitlines()[0])
    response = client.get('/private-case-room/' + room['queue_id'] + '?access_token=' + room['access_token'])
    text = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'not a live Google search' in text
    assert 'Reputation Risk Score™:' not in text
    assert 'Snapshot review / QC' not in text
    assert 'googletagmanager' not in text and 'connect.facebook.net' not in text
    assert response.headers['Cache-Control'] == 'no-store, private'
    assert client.get('/private-case-room/' + room['queue_id'] + '?access_token=wrong').status_code == 403


def test_duplicate_does_not_create_more_records(client):
    assert client.post('/submit-snapshot', data=valid()).status_code == 200
    assert client.post('/submit-snapshot', data=valid()).status_code == 429
    assert len(server.LEADS_FILE.read_text().splitlines()) == 1


def test_oversize_and_html_redisplay(client):
    data = valid(); data['goal'] = '<script>alert(1)</script>'; data['country_state'] = ''
    response = client.post('/submit-snapshot', data=data)
    assert response.status_code == 400
    assert '<script>alert(1)</script>' not in response.get_data(as_text=True)
    assert '&lt;script&gt;' in response.get_data(as_text=True)
    data = valid(); data['name'] = 'X' * 161
    assert client.post('/submit-snapshot', data=data).status_code == 400


@pytest.mark.parametrize('payload', [['invalid'], {'collected': ['invalid']}])
def test_bad_json_shape_returns_400(client, payload):
    assert client.post('/api/concierge/submit', json=payload).status_code == 400


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
