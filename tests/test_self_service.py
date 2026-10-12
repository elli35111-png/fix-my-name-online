"""Free check, plan and tracker: real Chromium against a local server.

The desk must never send what people type to any server: no POSTs, no
third-party requests, no analytics. Storage is this tab only unless the
visitor opts in to "Save on this browser".
"""
import json
import threading
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from werkzeug.serving import make_server

import plans
import server

KEY = 'fmno_self_service_v2'
OLD_KEY = 'fmno_self_service_v1'
PROOF = Path(__file__).resolve().parents[1] / 'qa_proof'


@pytest.fixture
def origin(monkeypatch, tmp_path):
    monkeypatch.setattr(server, 'CLICK_EVENTS_FILE', tmp_path / 'clicks.jsonl')
    monkeypatch.setattr(server, 'tracking_head', lambda: '<script>window.TRACKING_LOADED=1</script>')
    http = make_server('127.0.0.1', 0, server.app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%s' % http.server_port
    http.shutdown(); thread.join()


def new_page(p, width=1280, js=True):
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': width, 'height': 900}, accept_downloads=True,
                                  java_script_enabled=js, timezone_id='Australia/Adelaide')
    page = context.new_page()
    page.errors, page.requests = [], []
    page.on('pageerror', lambda error: page.errors.append(str(error)))
    page.on('request', lambda req: page.requests.append((req.method, req.url)))
    return browser, page


def answer_old_news(page, origin):
    page.goto(origin + '/self-service?problem=old-news')
    page.locator('[data-q="who"] input[value="me"]').check()
    page.locator('[data-q="now"] input[value="left-out"]').check()
    page.locator('[data-q="status"] input[value="finished"]').check()
    page.fill('#q-link', 'https://example.com/news/2019/story')
    page.check('#safety-none')


@pytest.mark.parametrize('width', [360, 768, 1440])
def test_home_navigation_and_faq(origin, width):
    with sync_playwright() as p:
        browser, page = new_page(p, width)
        page.goto(origin)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        if width < 900:
            assert not page.locator('.nav').is_visible()
            # The way in is visible without opening the menu.
            cta = page.locator('.head-cta')
            assert cta.is_visible() and cta.get_attribute('href') == '/self-service'
            assert cta.bounding_box()['y'] < 60
            page.locator('.menu summary').click()
            assert page.locator('.menu-sheet').is_visible()
            page.keyboard.press('Escape')
            assert not page.locator('.menu-sheet').is_visible()
        else:
            assert page.locator('.nav').is_visible()
            assert not page.locator('.menu summary').is_visible()
            assert not page.locator('.head-cta').is_visible()
        page.locator('#faq summary').nth(1).click()
        assert page.locator('#faq details').nth(1).get_attribute('open') is not None
        PROOF.mkdir(exist_ok=True)
        page.screenshot(path=str(PROOF / ('homepage-%s.png' % width)), full_page=True)
        page.locator('.hero a.tile[data-problem="court"]').click()
        page.wait_for_selector('#questions')
        assert '/self-service?problem=court' in page.url
        # Step 1 is folded into what they picked, so the questions come next.
        assert page.locator('#picked [data-picked="court"]').count() == 1
        assert page.locator('#desk-app .tile').count() == 0
        assert page.locator('#questions').bounding_box()['y'] < 900
        page.click('#change-problem')
        assert page.locator('.tile.is-selected[data-problem="court"]').count() == 1
        page.locator('#desk-app .tile[data-problem="reviews"], #desk-app .tile[data-problem="review"]').first.click()
        page.wait_for_selector('#picked [data-picked="review"]')
        assert not page.errors
        browser.close()


@pytest.mark.parametrize('width', [360, 768, 1440])
def test_check_plan_tracker_round_trip_without_uploads(origin, width):
    with sync_playwright() as p:
        browser, page = new_page(p, width)
        answer_old_news(page, origin)
        assert page.evaluate('localStorage.length') == 0
        page.click('#show-plan')
        page.wait_for_selector('#add-to-tracker')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert 'Ask the publisher to update the story' in page.locator('h1').inner_text()
        # The letter is filled from the link the visitor pasted, in the browser.
        assert 'https://example.com/news/2019/story' in page.locator('#letter-L1').inner_text()
        # Asks change the letter.
        page.locator('#step-decide input[value="anonymise"]').check()
        assert 'remove my name, or replace it with initials' in page.locator('#letter-L1').inner_text()
        # Official links open in a new tab and carry a last-checked note.
        refresh = page.locator('#step-refresh a[href="https://search.google.com/search-console/remove-outdated-content"]')
        assert refresh.get_attribute('target') == '_blank'
        assert 'Official links last checked' in page.locator('#step-refresh').inner_text()
        page.check('#tick-evidence-0')
        with page.expect_download() as text_download:
            page.click('#export-text')
        text = Path(text_download.value.path()).read_text()
        assert '[x]' in text and 'PUBLISHER UPDATE REQUEST' in text
        page.click('#add-to-tracker')
        page.wait_for_selector('.track-item')
        assert '/self-service/tracker' in page.url
        assert page.locator('.track-item').count() == 1
        assert 'Not started' in page.locator('.track-item .chip').inner_text() or 'Preparing' in page.locator('.track-item .chip').inner_text()
        # Item detail: the visitor sets the status.
        page.locator('.track-item a.btn').click()
        page.wait_for_selector('#tracking')
        page.select_option('#item-status', 'waiting')
        page.fill('#item-check', '2026-11-01')
        page.fill('#item-notes', '<img src=x onerror=alert(1)> literal notes')
        page.reload()  # this tab keeps it (sessionStorage) without opting in
        page.wait_for_selector('#tracking')
        assert page.locator('#item-status').input_value() == 'waiting'
        assert page.locator('#item-notes').input_value().startswith('<img')
        assert page.locator('#desk-app img').count() == 0
        assert page.evaluate('localStorage.length') == 0
        with page.expect_download() as ics:
            page.click('#item-ics')
        assert 'DTSTART;VALUE=DATE:20261101' in Path(ics.value.path()).read_text()
        # Opt in to saving on this browser.
        page.check('#desk-save')
        saved = json.loads(page.evaluate('(k) => localStorage.getItem(k)', KEY))
        assert saved['version'] == 2 and saved['items'][0]['status'] == 'waiting'
        with page.expect_download() as backup_download:
            page.click('#export-json')
        backup = Path(backup_download.value.path()).read_text()
        page.once('dialog', lambda dialog: dialog.accept())
        page.click('#clear-desk')
        assert page.evaluate('localStorage.length') == 0
        page.goto(origin + '/self-service/tracker')
        assert page.locator('.track-item').count() == 0
        page.locator('#import-file').set_input_files({'name': 'backup.json', 'mimeType': 'application/json', 'buffer': backup.encode()})
        page.wait_for_selector('.track-item')
        page.locator('#import-file').set_input_files({'name': 'bad.json', 'mimeType': 'application/json', 'buffer': b'{"version":9}'})
        page.wait_for_function("document.getElementById('desk-message').textContent.includes('tracker file')")
        assert page.locator('.track-item').count() == 1
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        PROOF.mkdir(exist_ok=True)
        page.screenshot(path=str(PROOF / ('tracker-%s.png' % width)), full_page=True)
        # Nothing typed ever left the browser: only GETs to this server, no tracking.
        assert all(method == 'GET' and url.startswith(origin) for method, url in page.requests), page.requests
        assert not page.evaluate('window.TRACKING_LOADED || 0')
        assert not page.errors
        browser.close()


def test_safety_and_ongoing_answers_put_help_first_and_hide_the_pack(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 1280)
        page.goto(origin + '/self-service?problem=images')
        page.locator('[data-q="whose"] input[value="other"]').check()
        page.locator('[data-q="where"] input[value="website"]').check()
        page.check('#safety-intimate')
        page.click('#show-plan')
        page.wait_for_selector('.help-first')
        assert page.locator('[data-help="intimate"]').count() == 1
        assert page.locator('[data-help="intimate"] a[href="https://www.esafety.gov.au/key-topics/image-based-abuse"]').count() == 1
        assert page.locator('.pack-offer').count() == 0
        # A case that is still running: lawyer first, no letter, no pack.
        answer_old_news(page, origin)
        page.locator('[data-q="status"] input[value="ongoing"]').check()
        page.click('#show-plan')
        page.wait_for_selector('.help-first')
        assert page.locator('[data-help="ongoing"]').count() == 1
        assert page.locator('.letter').count() == 0
        assert page.locator('.pack-offer').count() == 0
        # Someone with my name: the "this isn't me" letter, not a removal request.
        answer_old_news(page, origin)
        page.locator('[data-q="who"] input[value="same-name"]').check()
        page.click('#show-plan')
        page.wait_for_selector('#letter-L6')
        assert 'I’m not that person' in page.locator('#letter-L6').inner_text()
        assert not page.errors
        browser.close()


@pytest.mark.parametrize('safety,heading', [
    ('intimate', 'Start with eSafety.'),
    ('threat', 'Start with the police and eSafety.'),
    ('child', 'Report it to eSafety first.'),
])
def test_safety_plan_leads_with_help_on_phones(origin, safety, heading):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        page.goto(origin + '/self-service?problem=images')
        page.locator('[data-q="whose"] input[value="mine"]').check()
        page.locator('[data-q="where"] input[value="website"]').check()
        page.check('#safety-' + safety)
        page.click('#show-plan')
        page.wait_for_selector('.help-first')
        assert page.locator('h1').inner_text().startswith(heading)
        # The help comes before the "N steps · Add to my tracker" strip, on the first screen.
        assert page.evaluate("""() => {
          const help = document.querySelector('.help-first'), quick = document.getElementById('quick-actions');
          return !!(help.compareDocumentPosition(quick) & Node.DOCUMENT_POSITION_FOLLOWING);
        }""")
        assert page.locator('.help-first').first.bounding_box()['y'] < 812
        # The usual plan is still there, labelled as coming after.
        assert page.locator('#plan-for-page').inner_text().startswith('Then, for the page itself:')
        assert page.locator('#plan-steps').count() == 1
        assert not page.errors
        browser.close()


def test_plan_without_safety_boxes_keeps_its_own_heading(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        answer_old_news(page, origin)
        page.click('#show-plan')
        page.wait_for_selector('#quick-actions')
        assert page.locator('.help-first').count() == 0 and page.locator('#plan-for-page').count() == 0
        assert 'Ask the publisher to update the story' in page.locator('h1').inner_text()
        browser.close()


def test_copy_button_confirms_next_to_the_letter(origin):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 375, 'height': 812}, timezone_id='Australia/Adelaide')
        context.grant_permissions(['clipboard-read', 'clipboard-write'], origin=origin)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        answer_old_news(page, origin)
        page.click('#show-plan')
        letter = page.locator('.letter').filter(has=page.locator('#letter-L1'))
        letter.locator('button', has_text='Copy').click()
        page.wait_for_function("document.querySelector('.copy-note') && document.querySelector('.copy-note').textContent.includes('copied')")
        assert letter.locator('.btn-row button').nth(1).inner_text().strip() == 'Copied'
        assert 'example.com/news/2019/story' in page.evaluate('navigator.clipboard.readText()')
        note = letter.locator('.copy-note')
        assert note.is_visible() and 'is-error' not in (note.get_attribute('class') or '')
        assert 'didn’t work' not in page.locator('#desk-message').inner_text()
        # When the browser blocks the clipboard, the message shows by the button.
        page.evaluate("() => { navigator.clipboard.writeText = () => Promise.reject(new Error('blocked')); }")
        letter.locator('.btn-row button').nth(1).click()
        page.wait_for_function("document.querySelector('.copy-note').textContent.includes('didn’t work')")
        assert 'is-error' in note.get_attribute('class')
        assert 'didn’t work' not in page.locator('#desk-message').inner_text()
        assert not errors
        browser.close()


def test_unanswered_questions_are_explained_not_ignored(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        page.goto(origin + '/self-service?problem=review')
        page.click('#show-plan')
        assert 'Please answer' in page.locator('#check-error').inner_text()
        assert page.locator('#add-to-tracker').count() == 0
        # The reason is shown beside the question, which is outlined and on screen.
        flagged = page.locator('[data-q="about"].has-error, .has-error').first
        page.wait_for_timeout(600)  # smooth scroll
        box = flagged.bounding_box()
        assert 0 <= box['y'] < 900
        assert 'Please answer' in flagged.locator('.q-error').inner_text()
        assert flagged.locator('input').first.get_attribute('aria-invalid') == 'true'
        # Answering it clears the message.
        flagged.locator('input').first.check()
        assert page.locator('.has-error').count() == 0 and page.locator('.q-error').count() == 0
        assert page.locator('#check-error').inner_text() == ''
        browser.close()


@pytest.mark.parametrize('width', [375, 1280])
def test_add_to_tracker_is_close_at_hand_and_offers_to_keep_it(origin, width):
    with sync_playwright() as p:
        browser, page = new_page(p, width)
        answer_old_news(page, origin)
        page.click('#show-plan')
        if width < 1024:
            page.wait_for_selector('#quick-add')
            assert page.locator('#quick-add').bounding_box()['y'] < 900
            assert not page.locator('#glance').is_visible()
            button = '#quick-add'
        else:
            page.wait_for_selector('#glance-add')
            assert page.locator('#glance-add').bounding_box()['y'] < 900
            assert page.locator('#glance-print').is_visible()
            page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
            page.wait_for_timeout(200)
            assert 0 <= page.locator('#glance').bounding_box()['y'] < 200  # stays on screen
            assert page.locator('#glance-add').is_visible()
            button = '#glance-add'
        page.click(button)
        page.wait_for_selector('#keep-prompt')
        prompt = page.locator('#keep-prompt').inner_text()
        assert 'Want to come back to this on' in prompt and 'only kept in this tab' in prompt
        assert page.locator('#keep-prompt').bounding_box()['y'] < 900
        with page.expect_download() as backup:
            page.click('#keep-download')
        assert json.loads(Path(backup.value.path()).read_text())['items'][0]['checkBack']
        with page.expect_download() as ics:
            page.click('#keep-ics')
        assert 'BEGIN:VCALENDAR' in Path(ics.value.path()).read_text()
        assert page.evaluate('localStorage.length') == 0
        page.click('#keep-save')
        assert 'Saved on this browser' in page.locator('#keep-prompt').inner_text()
        assert page.locator('#desk-save').is_checked()
        assert json.loads(page.evaluate('(k) => localStorage.getItem(k)', KEY))['items']
        page.reload()
        page.wait_for_selector('.track-item')
        assert page.locator('#keep-prompt').count() == 0  # only shown right after adding
        assert all(method == 'GET' and url.startswith(origin) for method, url in page.requests), page.requests
        assert not page.errors
        browser.close()


def test_problem_guides_put_the_plan_within_reach_on_phones(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        for problem in plans.PROBLEMS:
            page.goto(origin + '/help/' + problem['hub'])
            link = page.locator(f'main .short a[href="/self-service?problem={problem["key"]}"]')
            assert link.count() == 1, problem['hub']
            assert link.bounding_box()['y'] < 1100, problem['hub']
        for path in ('/how-it-works', '/about'):
            page.goto(origin + path)
            first = page.locator('main a[href="/self-service"]').first
            assert first.is_visible() and first.bounding_box()['y'] < 1400, path
        browser.close()


def test_v1_saved_desk_migrates_into_the_tracker(origin):
    v1 = {'version': 1, 'issue': 'article', 'status': 'submitted', 'url': 'https://example.com/a', 'region': 'SA',
          'title': 'Old article', 'concern': 'Missing outcome', 'evidence': 'Letter', 'reference': 'REF-9',
          'notes': 'Sent 1 Oct', 'followup': '2026-10-20', 'checks': {}}
    with sync_playwright() as p:
        browser, page = new_page(p, 1280)
        page.goto(origin + '/robots.txt')
        page.evaluate('([k, v]) => localStorage.setItem(k, v)', [OLD_KEY, json.dumps(v1)])
        page.goto(origin + '/self-service/tracker')
        page.wait_for_selector('.track-item')
        assert 'Old article' in page.locator('.track-item').inner_text()
        assert page.evaluate('(k) => localStorage.getItem(k)', OLD_KEY) is None
        migrated = json.loads(page.evaluate('(k) => localStorage.getItem(k)', KEY))
        assert migrated['items'][0]['reference'] == 'REF-9' and migrated['items'][0]['status'] == 'submitted'
        assert 'Missing outcome' in migrated['items'][0]['notes']
        browser.close()


def test_storage_failure_does_not_lose_the_plan(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 1280)
        page.add_init_script("Storage.prototype.setItem = function () { throw new Error('Quota exceeded'); };")
        answer_old_news(page, origin)
        page.click('#show-plan')
        page.wait_for_selector('#add-to-tracker')
        page.click('#desk-save')
        assert not page.locator('#desk-save').is_checked()
        assert 'didn’t work' in page.locator('#desk-message').inner_text()
        assert page.locator('#letter-L1').is_visible()
        browser.close()


def test_routes_links_and_sensitive_tracking(monkeypatch):
    client = server.app.test_client()
    monkeypatch.setenv('FMNO_GA_MEASUREMENT_ID', 'G-TEST')
    monkeypatch.setenv('FMNO_META_PIXEL_ID', '12345')
    for path in ('/self-service', '/self-service/tracker', '/self-service?problem=old-news'):
        body = client.get(path).get_data(as_text=True)
        assert 'googletagmanager.com' not in body and 'connect.facebook.net' not in body, path
    home = client.get('/').get_data(as_text=True)
    assert 'googletagmanager.com' in home
    # Meta's automatic events record clicks (link text + address), which would
    # send the problem tile someone picks. Privacy section 4 says we don't.
    assert home.index("fbq('set', 'autoConfig', false, '12345')") < home.index("fbq('init', '12345')")
    assert client.get('/self-serve').headers['Location'] == '/self-service'
    tracker = client.get('/self-service/tracker')
    assert tracker.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert 'name="robots" content="noindex,nofollow"' in tracker.get_data(as_text=True)
    for route in ('/', '/self-service', '/help/old-news-articles', '/diy-action', '/how-it-works', '/pricing', '/faq', '/about'):
        soup = BeautifulSoup(client.get(route).data, 'html.parser')
        assert len(soup.select('h1')) == 1, route
        for node in soup.select('a[href],script[src],link[href]'):
            href = node.get('href') or node.get('src')
            if href.startswith('/checkout/'):
                continue  # live checkout needs Stripe; covered in test_paid_actions
            if href.startswith('/') and not href.startswith('//'):
                result = client.get(href)
                assert result.status_code < 400, (route, href, result.status_code)
            elif href.startswith('#') and len(href) > 1:
                assert soup.select_one(href), (route, href)


def test_plan_data_is_complete_and_dated():
    data = plans.client_payload()
    for key, plan in plans.PLANS.items():
        assert plan['steps'] and plan['if_no'] and plan['who_decides'] and plan['time'], key
        for step in plan['steps'] + plan.get('ongoing_steps', []):
            for link in step.get('links', []) + [l for by in (step.get('links_by') or {}).values() for ls in by.values() for l in ls]:
                assert link in plans.OFFICIAL_LINKS, (key, link)
            for letter in [step.get('letter')] + [alt['letter'] for alt in step.get('letter_when', [])]:
                assert letter is None or letter in plans.LETTERS, (key, letter)
        for item in plan['if_no']:
            assert item.get('link') is None or item['link'] in plans.OFFICIAL_LINKS
    for problem in plans.PROBLEMS:
        assert problem['key'] in plans.QUESTIONS and problem['key'] in plans.PLANS
    for link_id, link in plans.OFFICIAL_LINKS.items():
        assert link['url'].startswith('https://'), link_id
        assert 'checked' in link, link_id
    checked = [l for l in plans.OFFICIAL_LINKS.values() if l['checked']]
    assert len(checked) >= len(plans.OFFICIAL_LINKS) - 6
    assert all(l['checked'] == plans.LAST_CHECKED for l in checked)
    assert json.loads(plans.client_json())['lastChecked'] == plans.LAST_CHECKED
    assert data['statuses'][2] == ('submitted', 'Sent by me')


def test_desk_without_javascript_still_points_to_every_plan(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 360, js=False)
        page.goto(origin + '/self-service')
        assert page.locator('h1').inner_text() == 'What’s showing up for your name?'
        for problem in plans.PROBLEMS:
            assert page.locator(f'a[href="/help/{problem["hub"]}"]').count() >= 1
        page.goto(origin)
        page.locator('.menu summary').click()
        assert page.locator('.menu-sheet').is_visible()
        browser.close()
