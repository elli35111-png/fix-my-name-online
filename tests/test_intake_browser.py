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
    monkeypatch.setattr(server, 'send_snapshot_emails', lambda *a, **kw: {})
    def forbidden(*a, **kw):
        raise AssertionError('Unexpected outbound/manual workflow')
    for attr in ('safe_create_fulfilment_case', 'run_free_snapshot_pipeline', 'send_telegram_alert'):
        monkeypatch.setattr(server, attr, forbidden)
    http = make_server('127.0.0.1', 0, server.app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%s' % http.server_port
    http.shutdown(); thread.join()


@pytest.mark.parametrize('width', [360, 768, 1440])
def test_real_form_and_room(intake_origin, width, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={'width': width, 'height': 1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(intake_origin + '/free-search-snapshot?source=browser_qa')
        assert page.locator('h1').inner_text() == 'Your next step starts here.'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('#snapshot-submit').click()
        assert page.url.endswith('source=browser_qa')
        assert not server.LEADS_FILE.exists()
        page.locator('#snapshot-name').fill('Synthetic QA Person')
        page.locator('#snapshot-email').fill('synthetic-browser-qa@example.com')
        page.locator('#snapshot-country_state').fill('Australia, NSW')
        page.locator('#snapshot-authority').select_option('self')
        page.locator('#snapshot-goal').fill('An old article omits a later correction.')
        page.locator('#snapshot-consent').check()
        screenshot_dir = Path(__file__).resolve().parents[1] / 'qa_proof'
        screenshot_dir.mkdir(exist_ok=True)
        page.screenshot(path=str(screenshot_dir / ('intake-%s.png' % width)), full_page=True)
        page.locator('#snapshot-submit').click()
        page.wait_for_url('**/submit-snapshot')
        assert 'Your next step. Your decision.' in page.locator('h1').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert len(server.LEADS_FILE.read_text().splitlines()) == 1
        page.get_by_role('link', name='Open your private intake room').click()
        page.wait_for_url('**/private-case-room/**')
        assert 'not a live Google search' in page.locator('body').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
        browser.close()
