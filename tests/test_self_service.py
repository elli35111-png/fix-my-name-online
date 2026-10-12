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


def test_not_sure_routes_answer_every_question_of_the_plan_they_pick():
    # Every not-sure answer pair lands on a plan whose own questions are all
    # answered with real options, so nothing falls back to another visitor's story.
    ns = {q['id']: [o['value'] for o in q['options']] for q in plans.QUESTIONS['not-sure']}
    for where in ns['where']:
        for wrong in ns['wrong']:
            plan, answers, asks = plans.route_not_sure({'where': where, 'wrong': wrong, 'country': 'au', 'safety': []})
            assert answers['country'] == 'au' and answers['safety'] == []
            for q in plans.QUESTIONS.get(plan, []):
                values = [o['value'] for o in q['options']]
                if plan == 'old-news' and q['id'] == 'now':
                    values.append('outdated')  # route-only value with its own title, lede and letter text
                if plan == 'review' and q['id'] == 'why':
                    values.append('unsure')  # route-only value: neutral title, lede and report wording
                if q['id'] == 'status' and answers.get('who') == 'same-name':
                    continue  # someone else's case: whether it's over isn't the visitor's to say, and isn't asked
                assert answers.get(q['id']) in values, (where, wrong, plan, q['id'], answers)
            if plan == 'general':
                assert asks, (where, wrong)
    # News site: what they said decides the plan and the letter.
    assert plans.route_not_sure({'where': 'news', 'wrong': 'wrong'})[1]['now'] == 'outdated'
    assert plans.route_not_sure({'where': 'news', 'wrong': 'not-me'})[1]['who'] == 'same-name'
    assert plans.route_not_sure({'where': 'news', 'wrong': 'private'})[0] == 'general'
    outline = plans.outline('old-news', plans.route_not_sure({'where': 'news', 'wrong': 'wrong'})[1])
    assert 'leaves out' not in outline['lede'] and 'wrong or out of date' in outline['lede']
    assert [s['id'] for s in outline['steps']] == ['evidence', 'decide', 'letter', 'follow', 'refresh']
    letter = plans.letter_text('L1', {'now': 'outdated'})
    assert 'isn’t accurate now' in letter and 'Since then' not in letter


@pytest.mark.parametrize('wrong, lede, letter, absent, steps', [
    ('wrong', 'wrong or out of date', 'isn’t accurate now', 'Since then', 5),
    ('not-me', 'isn’t about you', 'I’m not that person', 'Since then', 4),
    ('private', 'person who runs the site', 'remove my name, or replace it with initials', 'Since then', 5),
])
def test_not_sure_news_answers_get_the_plan_and_letter_they_described(origin, wrong, lede, letter, absent, steps):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        page.goto(origin + '/self-service?problem=not-sure')
        page.locator('[data-q="where"] input[value="news"]').check()
        page.locator(f'[data-q="wrong"] input[value="{wrong}"]').check()
        if wrong != 'not-me':
            page.locator('[data-q="status"] input[value="finished"]').check()
        page.check('#safety-none')
        page.click('#show-plan')
        page.wait_for_selector('#add-to-tracker')
        body = page.locator('#desk-app').inner_text()
        assert lede in body, body[:600]
        assert 'The story leaves out what happened next' not in body
        letters = ' '.join(page.locator('.letter-body').all_inner_texts())
        assert letter in letters and absent not in letters
        assert page.locator('ol.steps > li:not(.if-no)').count() == steps
        assert not page.errors
        browser.close()


def _not_sure_letters(where, wrong):
    plan, answers, asks = plans.route_not_sure({'where': where, 'wrong': wrong, 'country': 'au', 'safety': []})
    outline = plans.outline(plan, answers)
    letters = {s['letter']: plans.letter_text(s['letter'], answers, asks) for s in outline['steps'] if s.get('letter')}
    return plan, answers, asks, outline, letters


def test_not_sure_routes_never_claim_what_the_visitor_did_not_say():
    ns = {q['id']: [o['value'] for o in q['options']] for q in plans.QUESTIONS['not-sure']}
    for where in ns['where']:
        for wrong in ns['wrong']:
            plan, answers, asks, outline, letters = _not_sure_letters(where, wrong)
            text = ' '.join(letters.values())
            assert 'no record of this person as a customer' not in text, (where, wrong)
            if wrong == 'not-me':
                # Someone else with my name: a tell-us-apart request, never an update or an "about me" letter.
                assert 'I’m not that person' in text, (where, wrong, list(letters))
                assert 'reflects what happened next' not in text and 'article about me' not in text, (where, wrong)
            if where == 'social' and wrong != 'fake':
                assert plan == 'general' and 'L2' not in letters, (where, wrong, plan)
    # (a) social media or another website, about someone with my name
    for where in ('social', 'other'):
        plan, answers, asks, outline, letters = _not_sure_letters(where, 'not-me')
        assert plan == 'general' and answers['who'] == 'same-name' and asks == ['tell-apart']
        assert 'tells you apart' in outline['title'] and 'isn’t about you' in outline['lede']
        assert list(letters) == ['L6W', 'L5'] and 'helps readers tell us apart' in letters['L6W']
    # (b) social media showing private details: not the people-search plan
    plan, answers, asks, outline, letters = _not_sure_letters('social', 'private')
    assert plan == 'general' and asks == ['anonymise', 'remove']
    assert [s['id'] for s in outline['steps']][:2] == ['evidence', 'report']
    assert 'Opt out' not in outline['title'] and 'L7' in letters and 'remove my name' in letters['L7']
    # (c) review site, wrong: neutral wording, nothing about customers (not me: tell-apart, checked above)
    for wrong in ('wrong',):
        plan, answers, asks, outline, letters = _not_sure_letters('review', wrong)
        assert plan == 'review' and answers['why'] == 'unsure'
        assert 'real customer' not in outline['lede'] and 'Match the review' in outline['title']
        assert '[the specific part that breaks the policy]' in letters['L3R']
    # (d) court or legal site, about someone with my name: no court-rule steps, no letter to an editor
    plan, answers, asks, outline, letters = _not_sure_letters('court', 'not-me')
    assert plan == 'general' and answers['who'] == 'same-name'
    assert 'rules' not in [s['id'] for s in outline['steps']] and 'spent-conviction' not in outline['lede']
    assert 'Dear Editor' not in ' '.join(letters.values())
    # Court problem picked directly, same name + news story: the "isn't me" letter, not an update request.
    steps = plans.outline('court', {'who': 'same-name', 'where': 'news', 'status': 'finished'})['steps']
    assert next(s for s in steps if s['id'] == 'letter')['letter'] == 'L6'


@pytest.mark.parametrize('where, wrong, present, absent, letter', [
    ('social', 'not-me', 'Ask the site to add a detail that tells you apart.', 'reflects what happened next', 'helps readers tell us apart'),
    ('other', 'not-me', 'Ask the site to add a detail that tells you apart.', 'reflects what happened next', 'I’m not that person'),
    ('social', 'private', 'On social media, check the report options', 'Opt out of each site', 'remove my name, or replace it with initials'),
    ('review', 'wrong', 'Match the review to a specific rule', 'no record of this person', 'the specific part that breaks the policy'),
    ('court', 'not-me', 'Ask the site to add a detail that tells you apart.', 'Dear Editor', 'I’m not that person'),
])
def test_not_sure_other_answers_get_the_plan_and_letter_they_described(origin, where, wrong, present, absent, letter):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        page.goto(origin + '/self-service?problem=not-sure')
        page.locator(f'[data-q="where"] input[value="{where}"]').check()
        page.locator(f'[data-q="wrong"] input[value="{wrong}"]').check()
        page.check('#safety-none')
        page.click('#show-plan')
        page.wait_for_selector('#add-to-tracker')
        body = page.locator('#desk-app').inner_text()
        assert present in body, body[:600]
        assert absent not in body
        letters = ' '.join(page.locator('.letter-body').all_inner_texts())
        assert letter in letters and absent not in letters
        assert not page.errors
        browser.close()


@pytest.mark.parametrize('tracked', [False, True])
def test_sticky_glance_card_never_covers_the_other_cards(origin, tracked):
    with sync_playwright() as p:
        browser, page = new_page(p, 1280)
        answer_old_news(page, origin)
        page.click('#show-plan')
        page.wait_for_selector('#glance-add')
        if tracked:
            page.click('#glance-add')
            page.goto(origin + '/self-service/tracker')
            page.locator('.track-item a[href^="#item-"]').first.click()
            page.wait_for_selector('#tracking')
        # The glance card is the only thing in the aside, so nothing can slide under it.
        assert page.locator('.aside-plan > *').count() == 1 and page.locator('.aside-plan > #glance').count() == 1
        for y in (0, 700, 1400, 2400, 10000):
            page.evaluate(f'window.scrollTo(0, {y})')
            page.wait_for_timeout(100)
            glance = page.locator('#glance').bounding_box()
            for sel in ('#desk-save', '#storage-card'):
                box = page.locator(sel).bounding_box()
                overlaps_x = box['x'] < glance['x'] + glance['width'] and glance['x'] < box['x'] + box['width']
                overlaps_y = box['y'] < glance['y'] + glance['height'] and glance['y'] < box['y'] + box['height']
                assert not (overlaps_x and overlaps_y), (y, sel, box, glance)
        page.locator('#desk-save').scroll_into_view_if_needed()
        box = page.locator('#desk-save').bounding_box()
        hit = page.evaluate(f"document.elementFromPoint({box['x'] + box['width'] / 2}, {box['y'] + box['height'] / 2}).closest('#storage-card') !== null")
        assert hit
        assert not page.errors
        browser.close()


def test_small_polish_grammar_empty_tracker_glance_and_checkboxes(origin):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 900}, color_scheme='dark')
        page.errors = []
        page.on('pageerror', lambda e: page.errors.append(str(e)))
        # An empty tracker doesn't claim to be step 4 of 4.
        page.goto(origin + '/self-service/tracker')
        page.wait_for_selector('#view-title')
        assert page.locator('.stepper').count() == 0 and page.locator('.step-count').count() == 0
        # "A few questions about the old news story", not "about old news story".
        page.goto(origin + '/self-service?problem=old-news')
        assert 'A few questions about the old news story' in page.locator('#questions h2').inner_text()
        for q, v in (('who', 'me'), ('now', 'left-out'), ('status', 'finished')):
            page.locator(f'[data-q="{q}"] input[value="{v}"]').check()
        page.check('#safety-none')
        page.click('#show-plan')
        page.wait_for_selector('#glance')
        # At a glance shows status markers, not checkboxes you can't tick.
        assert page.locator('#glance .box, #glance input[type=checkbox]').count() == 0
        page.check('#done-decide')
        assert page.locator('#glance .is-done').count() == 1
        assert 'Done:' in page.locator('#glance .is-done').inner_text()
        # Every checkbox in the plan looks the same in dark mode.
        page.check('#tick-evidence-0')
        native = page.evaluate("getComputedStyle(document.getElementById('tick-evidence-0')).appearance")
        custom = page.evaluate("getComputedStyle(document.querySelector('#step-decide .choice .box')).borderRadius")
        assert native == 'none'
        assert page.evaluate("getComputedStyle(document.getElementById('tick-evidence-0')).borderRadius") == custom
        assert page.evaluate("getComputedStyle(document.getElementById('tick-evidence-0')).backgroundColor") == \
            page.evaluate("getComputedStyle(document.querySelector('#step-decide .choice:has(input:checked) .box')).backgroundColor")
        assert not page.errors
        browser.close()


def test_mobile_menu_has_one_way_to_the_free_check(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        page.goto(origin + '/')
        hrefs = page.eval_on_selector_all('.menu-sheet a', 'els => els.map(a => a.getAttribute("href"))')
        assert hrefs.count('/self-service') == 1 and '/self-service/tracker' in hrefs
        browser.close()


# ---------- systematic guard: every not-sure combination ----------
# Each answer the visitor gives rules something out. No plan title, lede or
# letter may claim what they ruled out, and a case that may still be running
# always gets the lawyer card first.
_NS = {q['id']: [o['value'] for o in q['options']] for q in plans.QUESTIONS['not-sure']}
# Phrases that only fit when the page is about the visitor themselves.
_ABOUT_ME = ('lists my personal information', 'remove my personal information', 'listings about me', 'article about me',
             'page that mentions me', 'court record that names me', 'photo of me', 'reflects what happened next', 'Since then')
_PEOPLE_SEARCH = ('opt out', 'opt-out', 'people-search', 'your site lists', 'listing')


def _not_sure_cases():
    """(answers, status asked?) for every where × wrong, and every status where it's asked.
    Where it isn't asked, also try a stale status left over from an earlier answer."""
    for where in _NS['where']:
        for wrong in _NS['wrong']:
            base = {'where': where, 'wrong': wrong, 'country': 'au', 'safety': []}
            asked = 'status' in [q['id'] for q in plans.asked_questions('not-sure', base)]
            if asked:
                for status in _NS['status']:
                    yield dict(base, status=status), True
            else:
                yield base, False
                yield dict(base, status='finished'), False


def _check_not_sure_case(answers, asked):
    where, wrong, status = answers['where'], answers['wrong'], answers.get('status')
    b = plans.build('not-sure', answers)
    case = (where, wrong, status, b['key'])
    letters = ' '.join(b['letters'].values())
    claims = ' '.join([b['title'], b['lede'], letters])
    # The status is the visitor's, and only when it was asked.
    if asked:
        assert b['answers']['status'] == status, case
    else:
        assert 'status' not in b['answers'], case
    told_finished = asked and status == 'finished'
    if not told_finished:
        assert 'finished' not in claims.lower() and 'it’s over' not in claims, case
    # Running or not sure: the lawyer card comes first; running: no letter at all.
    if asked and status == 'ongoing':
        assert 'ongoing' in b['help'] and not b['letters'] and not b['pack'], case
    elif asked and status == 'unsure':
        assert 'status-unsure' in b['help'], case
    else:
        assert not {'ongoing', 'status-unsure'} & set(b['help']), case
    if b['key'] == 'court':
        assert asked, case  # a court plan always knows whether the case is over
    # Someone else with my name: tell-us-apart, never "my" data or "about me".
    if wrong == 'not-me':
        assert b['answers'].get('who') == 'same-name', case
        assert 'I’m not that person' in letters, case
        assert 'isn’t about you' in b['lede'], case
        assert not [p for p in _ABOUT_ME if p in claims], (case, [p for p in _ABOUT_ME if p in claims])
        assert 'someone else with your name' in plans.not_sure_looks_like(answers), case
    else:
        assert b['answers'].get('who') != 'same-name' and 'I’m not that person' not in letters, case
    # People-search wording only for a site that lists people (about the visitor).
    if where != 'listing' or wrong in ('not-me', 'fake'):
        assert b['key'] != 'people-search', case
        assert not [p for p in _PEOPLE_SEARCH if p in claims.lower()], (case, [p for p in _PEOPLE_SEARCH if p in claims.lower()])
    # Pretending to be me: the impersonation report, described as what they said.
    if wrong == 'fake':
        assert b['key'] == 'fake-profile' and plans.not_sure_looks_like(answers) == 'someone pretending to be you', case
    else:
        assert 'pretending to be me' not in claims, case
    # Only "it's wrong" letters say the page is wrong.
    if wrong != 'wrong':
        assert 'isn’t accurate now' not in letters and 'That isn’t correct' not in letters, case
    return b


def test_every_not_sure_answer_gets_a_plan_that_never_claims_what_was_ruled_out():
    cases = list(_not_sure_cases())
    assert len(cases) == 20 * 2 + 4 * 3  # 4 of the 24 where × wrong pairs ask the status
    for answers, asked in cases:
        _check_not_sure_case(answers, asked)
    # The same rules hold for the plans picked directly.
    for who in ('me', 'helping', 'same-name'):
        for status in _NS['status']:
            for where in ('copy', 'news', 'court-site', 'unsure'):
                b = plans.build('court', {'who': who, 'where': where, 'status': status, 'country': 'au', 'safety': []})
                if status != 'finished':
                    assert 'finished' not in ' '.join(b['letters'].values()), (who, where, status)
                assert ('ongoing' in b['help']) == (status == 'ongoing') and ('status-unsure' in b['help']) == (status == 'unsure')
            for now in ('left-out', 'wrong', 'old', 'unsure'):
                b = plans.build('old-news', {'who': who, 'now': now, 'status': status, 'country': 'au', 'safety': []})
                if status != 'finished':
                    assert 'finished' not in ' '.join(b['letters'].values()), (who, now, status)
                if status == 'ongoing':
                    assert not b['letters'] and 'ongoing' in b['help']
    assert 'The case was in [year] and it’s finished.' in plans.letter_text('L1C', {'status': 'finished'})
    assert 'finished' not in plans.letter_text('L1C', {'status': 'unsure'})


def _norm(text):
    return ' '.join(text.replace('[', '').replace(']', '').split())


def test_every_not_sure_answer_in_the_real_desk_matches_the_guard(origin):
    # The browser builds the plan, so walk every combination there too, and check
    # it builds exactly what plans.build() checked above.
    with sync_playwright() as p:
        browser, page = new_page(p, 1280)
        for answers, asked in _not_sure_cases():
            case = (answers['where'], answers['wrong'], answers.get('status'))
            page.goto(origin + '/self-service?problem=not-sure')
            page.locator(f'[data-q="where"] input[value="{answers["where"]}"]').check()
            if not asked and 'status' in answers:
                # A stale answer: pick a pair that asks, answer it, then change the main problem.
                page.locator('[data-q="wrong"] input[value="wrong"]').check()
                if page.locator('[data-q="status"]').is_visible():
                    page.locator(f'[data-q="status"] input[value="{answers["status"]}"]').check()
            page.locator(f'[data-q="wrong"] input[value="{answers["wrong"]}"]').check()
            assert page.locator('[data-q="status"]').is_visible() == asked, case
            if asked:
                page.locator(f'[data-q="status"] input[value="{answers["status"]}"]').check()
            page.check('#safety-none')
            page.click('#show-plan')
            page.wait_for_selector('#add-to-tracker')
            b = _check_not_sure_case(answers, asked)
            assert page.locator('#looks-like strong').inner_text() == 'From your answers, this looks like: ' + plans.not_sure_looks_like(answers) + '.', case
            shown = sorted(i.replace('letter-', '') for i in page.eval_on_selector_all('.letter-body', 'els => els.map(e => e.id)'))
            assert shown == sorted(b['letters']), (case, shown, list(b['letters']))
            for key, text in b['letters'].items():
                assert _norm(page.locator('#letter-' + key).evaluate('e => [...e.children].map(p => p.textContent).join(" ")')) == _norm(text), (case, key)
            for kind in ('ongoing', 'status-unsure'):
                assert page.locator(f'[data-help="{kind}"]').count() == (1 if kind in b['help'] else 0), (case, kind)
            if 'ongoing' in b['help'] or 'status-unsure' in b['help']:
                assert page.locator('[data-help] a[href="https://nationallegalaid.org.au/"]').count() == 1, case
        assert not page.errors, page.errors
        browser.close()


@pytest.mark.parametrize('where, wrong, looks, same_as, label', [
    ('news', 'fake', 'someone pretending to be you', 'The steps are the same as for a fake profile.', 'Someone pretending to be you'),
    ('review', 'fake', 'someone pretending to be you', 'The steps are the same as for a fake profile.', 'Someone pretending to be you'),
    ('review', 'not-me', 'a review that mentions someone else with your name', None, 'Review that mentions someone else with your name'),
    ('listing', 'not-me', 'a listing about someone else with your name', None, 'Listing about someone else with your name'),
    ('other', 'private', 'a page on someone else’s site', None, 'Page on someone else’s site'),
])
def test_not_sure_banner_and_tracker_label_name_what_was_described(origin, where, wrong, looks, same_as, label):
    with sync_playwright() as p:
        browser, page = new_page(p, 1280)
        page.goto(origin + '/self-service?problem=not-sure')
        page.locator(f'[data-q="where"] input[value="{where}"]').check()
        page.locator(f'[data-q="wrong"] input[value="{wrong}"]').check()
        page.check('#safety-none')
        page.click('#show-plan')
        page.wait_for_selector('#looks-like')
        banner = page.locator('#looks-like').inner_text()
        assert 'this looks like: ' + looks + '.' in banner
        assert 'a fake profile.' not in banner.split('The steps')[0]
        if same_as:
            assert same_as in banner
        page.click('#add-to-tracker')
        page.wait_for_selector('.track-h')
        assert page.locator('.track-h').first.inner_text() == label
        assert not page.errors
        browser.close()


def test_not_sure_court_case_still_running_gets_the_lawyer_first(origin):
    with sync_playwright() as p:
        browser, page = new_page(p, 375)
        page.goto(origin + '/self-service?problem=not-sure')
        page.locator('[data-q="where"] input[value="court"]').check()
        assert not page.locator('[data-q="status"]').is_visible()
        page.locator('[data-q="wrong"] input[value="wrong"]').check()
        assert page.locator('[data-q="status"]').is_visible()
        page.check('#safety-none')
        page.click('#show-plan')
        assert 'Is the matter it describes finished?' in page.locator('#check-error').inner_text()
        page.locator('[data-q="status"] input[value="ongoing"]').check()
        page.click('#show-plan')
        page.wait_for_selector('[data-help="ongoing"]')
        assert page.locator('h1').inner_text().startswith('Get legal advice before you send anything.')
        assert page.locator('.letter').count() == 0 and page.locator('.pack-offer').count() == 0
        # Not sure: the lawyer card first, and the letter doesn't say it's finished.
        page.click('text=Change my answers')
        page.locator('[data-q="status"] input[value="unsure"]').check()
        page.click('#show-plan')
        page.wait_for_selector('[data-help="status-unsure"]')
        assert page.locator('h1').inner_text().startswith('Check the matter is finished before you send anything.')
        letter = page.locator('#letter-L1C').inner_text()
        assert 'The case was in' in letter and 'finished' not in letter
        assert not page.errors
        browser.close()
