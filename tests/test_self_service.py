"""Home and self-service integration checks using actual Chromium."""
import json
import threading
from pathlib import Path
from urllib.parse import urlparse
import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server
import server

KEY = 'fmno_self_service_v1'
PROOF = Path(__file__).resolve().parents[1] / 'qa_proof'


@pytest.fixture
def origin(monkeypatch, tmp_path):
    monkeypatch.setattr(server, 'CLICK_EVENTS_FILE', tmp_path / 'clicks.jsonl')
    monkeypatch.setattr(server, 'tracking_head', lambda: '')
    http = make_server('127.0.0.1', 0, server.app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%s' % http.server_port
    http.shutdown(); thread.join()


@pytest.mark.parametrize('width', [360, 768, 1440])
def test_responsive_home_navigation_and_faq(origin, width):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':width, 'height':1000})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if width <= 720:
            assert not page.locator('#main-nav').is_visible()
            page.locator('#menu-toggle').click()
            assert page.locator('#main-nav').is_visible()
            assert page.locator('#menu-toggle').get_attribute('aria-expanded') == 'true'
            page.keyboard.press('Escape')
            assert not page.locator('#main-nav').is_visible()
        else:
            assert not page.locator('#menu-toggle').is_visible()
        page.locator('#faq summary').first.click()
        assert page.locator('#faq details').first.get_attribute('open') is not None
        PROOF.mkdir(exist_ok=True)
        page.screenshot(path=str(PROOF / ('homepage-%s.png' % width)), full_page=True)
        page.locator('[data-track="homepage_hero_snapshot"]').click()
        assert '/free-search-snapshot?source=homepage_hero_snapshot' in page.url
        assert not errors
        browser.close()


@pytest.mark.parametrize('width', [360, 768, 1440])
def test_desk_roundtrip_no_uploads_and_safe_import(origin, width, tmp_path):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width':width,'height':1000}, accept_downloads=True)
        page = context.new_page()
        requests, errors = [], []
        page.on('request', lambda req: requests.append((req.method, req.url)))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(origin + '/self-service')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert page.evaluate('localStorage.length') == 0
        page.locator('#desk-concern').fill('A synthetic concern, not a real client.')
        page.locator('#desk-url').fill('https://example.com/article')
        page.locator('#desk-step-0').check()
        assert page.locator('#progress-label').inner_text() == '1 of 5 steps'
        assert page.evaluate('localStorage.length') == 0
        page.locator('#desk-save').check()
        assert json.loads(page.evaluate('(key) => localStorage.getItem(key)',KEY))['concern'].startswith('A synthetic')
        page.reload()
        assert page.locator('#desk-concern').input_value().startswith('A synthetic')
        assert page.locator('#desk-step-0').is_checked()
        page.locator('#desk-issue').select_option('review')
        assert page.locator('#desk-upsell').is_hidden()
        assert 'actual platform policy' in page.locator('#pathway-title').inner_text()
        page.locator('#desk-issue').select_option('safety')
        assert page.locator('#desk-upsell').is_hidden()
        page.locator('#desk-issue').select_option('article')
        assert page.locator('#desk-step-0').is_checked()
        page.locator('#desk-status').select_option('waiting')
        page.locator('#desk-date').fill('2026-11-01')
        page.locator('#desk-notes').fill('<img src=x onerror=alert(1)> literal notes')
        with page.expect_download() as download:
            page.locator('#export-json').click()
        backup = Path(download.value.path()).read_text()
        assert json.loads(backup)['status'] == 'waiting'
        with page.expect_download() as text_download:
            page.locator('#export-text').click()
        assert 'Waiting for a response' in Path(text_download.value.path()).read_text()
        assert '2026-11-01' in Path(text_download.value.path()).read_text()
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('#clear-desk').click()
        assert page.locator('#desk-concern').input_value() == ''
        assert page.evaluate('localStorage.length') == 0
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('#import-file').set_input_files({'name':'backup.json','mimeType':'application/json','buffer':backup.encode()})
        page.wait_for_function("document.getElementById('desk-status').value === 'waiting'")
        assert page.locator('#desk-notes').input_value().startswith('<img')
        assert page.locator('#self-service-desk img').count() == 0
        assert page.evaluate('localStorage.length') == 0
        page.locator('#import-file').set_input_files({'name':'invalid.json','mimeType':'application/json','buffer':b'{"version":9}'})
        page.wait_for_function("document.getElementById('desk-message').textContent.includes('compatible')")
        assert page.locator('#desk-status').input_value() == 'waiting'
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(PROOF / ('self-service-%s.png' % width)), full_page=True)
        assert all(method == 'GET' and url.startswith(origin) for method,url in requests), requests
        assert not errors
        browser.close()


def test_desk_storage_failure_and_print(origin):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.add_init_script("Storage.prototype.setItem = () => { throw new Error('Quota exceeded'); };")
        page.goto(origin + '/self-service')
        page.locator('#desk-concern').fill('PRINT COMPLETE ' + 'long note ' * 250)
        page.locator('#desk-save').click()
        assert not page.locator('#desk-save').is_checked()
        assert 'failed' in page.locator('#desk-message').inner_text()
        with page.expect_popup() as popup:
            page.locator('#print-desk').click()
        assert 'PRINT COMPLETE' in popup.value.locator('pre').inner_text()
        assert len(popup.value.locator('pre').inner_text()) > 2500
        assert popup.value.evaluate('window.opener === null')
        browser.close()


def test_routes_links_and_sensitive_tracking(monkeypatch):
    client = server.app.test_client()
    monkeypatch.setenv('FMNO_GA_MEASUREMENT_ID','G-TEST')
    monkeypatch.setenv('FMNO_META_PIXEL_ID','12345')
    body = client.get('/self-service').get_data(as_text=True)
    assert 'googletagmanager.com' not in body and 'connect.facebook.net' not in body
    assert client.get('/self-serve').headers['Location'] == '/self-service'
    assert '/self-service' in client.get('/sitemap-core.xml').get_data(as_text=True)
    for route in ('/', '/self-service'):
        soup = BeautifulSoup(client.get(route).data,'html.parser')
        assert len(soup.select('h1')) == 1
        for node in soup.select('a[href],script[src],link[href]'):
            href = node.get('href') or node.get('src')
            if href.startswith('/') and not href.startswith('//'):
                result = client.get(href)
                assert result.status_code < 400, (href,result.status_code)
            elif href.startswith('#'):
                assert soup.select_one(href), href


def test_home_usable_without_javascript(origin):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(java_script_enabled=False,viewport={'width':360,'height':900})
        page.goto(origin)
        assert page.locator('#main-nav').is_visible()
        page.locator('[data-track="homepage_hero_snapshot"]').click()
        assert page.locator('#snapshot-name').is_visible()
        browser.close()
