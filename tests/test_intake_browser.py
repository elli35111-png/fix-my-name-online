"""Real Chromium UI checks. Local synthetic records only; no outbound services."""
import json
import threading
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
import server


@pytest.fixture
def intake_origin(monkeypatch, tmp_path):
    for attr in ('LEADS_FILE', 'FULFILMENT_QUEUE_FILE', 'CLICK_EVENTS_FILE', 'CASE_ROOMS_FILE', 'CONCIERGE_TRANSCRIPTS_FILE'):
        monkeypatch.setattr(server, attr, tmp_path / (attr + '.jsonl'))
    def forbidden(*a, **kw):
        raise AssertionError('Unexpected outbound/manual workflow')
    for attr in ('safe_create_fulfilment_case', 'run_free_snapshot_pipeline', 'send_telegram_alert'):
        monkeypatch.setattr(server, attr, forbidden)
    http = make_server('127.0.0.1', 0, server.app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%s' % http.server_port
    http.shutdown(); thread.join()


VALID = {'name': 'Synthetic QA Person', 'email': 'synthetic-browser-qa@example.com', 'country_state': 'Australia, NSW',
         'authority': 'self', 'consent': 'yes', 'goal': 'An old article omits a later correction.',
         'case_type': 'Old article or outdated result', 'problem_links': '', 'source_page': 'browser_qa'}


def seed_room():
    """One existing private room, as the retired Snapshot left them."""
    data = dict(VALID)
    triage = server.triage_snapshot(data)
    queue_item = server.make_queue_item('free_snapshot', data, triage)
    room = server.save_case_room(queue_item, data, triage)
    return '/private-case-room/%s?access_token=%s' % (queue_item['id'], room['access_token'])


@pytest.mark.parametrize('width', [360, 768, 1440])
def test_legacy_intake_and_room_render_in_the_new_shell(intake_origin, width, tmp_path):
    """The old Snapshot form is retired: cached forms land on the free check and
    store nothing. The existing private rooms keep working, inside the shared shell."""
    client = server.app.test_client()
    result = client.post('/submit-snapshot', data=VALID)
    assert result.status_code == 303 and result.headers['Location'] == '/self-service?from=snapshot'
    assert not server.LEADS_FILE.exists()
    room = seed_room()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': width, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(intake_origin + '/free-search-snapshot?source=browser_qa')
        assert page.url.endswith('/self-service?from=snapshot')
        assert 'now this free check' in page.locator('#desk-app').inner_text()
        page.goto(intake_origin + room)
        text = page.locator('body').inner_text()
        assert 'not a live Google search' in text and 'MadisonJade' not in text
        assert page.locator('header.site-header').count() == 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        screenshot_dir = Path(__file__).resolve().parents[1] / 'qa_proof'
        screenshot_dir.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshot_dir / ('case-room-%s.png' % width)), full_page=True)
        assert not errors
        browser.close()
