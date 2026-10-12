"""Site-wide contract for the self-serve redesign: honesty, indexing, privacy, layout."""
import re
import sqlite3
import threading

import pytest
from bs4 import BeautifulSoup
from werkzeug.serving import make_server

import server

DOMAIN = 'https://fixmynameonline.com'
# ACL s18: copy that implies a person does the work, promises outcomes or sells a
# heuristic as a search. Checked on every public page's visible text.
BANNED = ['we review', 'we check', 'we map', 'what we check', 'what we privately check', 'our team',
          'managed process', 'private campaign', 'approved assets', 'search protection', 'suppress',
          'risk score', 'private score', 'we guarantee', 'guaranteed removal', 'we remove',
          'we will respond', 'supports clients', 'snapshot™', 'removal review™', 'review defence™']


@pytest.fixture(scope='module')
def client():
    server.app.testing = True
    return server.app.test_client()


def sitemap_paths(client):
    paths = []
    for child in ('/sitemap-core.xml', '/sitemap-guides.xml', '/sitemap-personal-search.xml'):
        paths += re.findall(r'<loc>' + re.escape(DOMAIN) + r'([^<]*)</loc>', client.get(child).get_data(as_text=True))
    return paths


def visible_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    return soup.get_text(' ', strip=True).lower()


def test_sitemap_lists_232_indexable_pages_and_nothing_else(client):
    paths = sitemap_paths(client)
    assert len(paths) == len(set(paths)) == 232
    for removed in ('/app', '/free-search-snapshot', '/questions'):
        assert removed not in paths
    for path in paths:
        res = client.get(path)
        assert res.status_code == 200, path
        assert 'noindex' not in res.headers.get('X-Robots-Tag', ''), path
        if path.startswith('/personal-search/'):
            continue  # owner's static pages are left exactly as they are
        html = res.get_data(as_text=True)
        robots = re.search(r'<meta name="robots" content="([^"]+)"', html).group(1)
        assert robots.startswith('index'), (path, robots)
        assert f'<link rel="canonical" href="{DOMAIN}{path}">' in html, path


def test_every_original_url_still_resolves(client):
    # The 226 URLs live on 12 Oct 2026: the 3 intake/redirect URLs now 301 on purpose.
    expected = {'/app': '/self-service?from=snapshot', '/free-search-snapshot': '/self-service?from=snapshot', '/questions': '/contact'}
    for path, target in expected.items():
        res = client.get(path)
        assert res.status_code == 301 and res.headers['Location'] == target
    for path in ('/how-it-works', '/pricing', '/faq'):
        assert client.get(path).status_code == 200  # were 301s to homepage anchors


def test_meta_robots_matches_x_robots_tag(client):
    for path in ('/self-service/tracker', '/billing', '/private-case-room/x', '/diy-action/workspace', '/no-such-page', '/learn/x'):
        res = client.get(path)
        header = res.headers.get('X-Robots-Tag', '')
        html = res.get_data(as_text=True)
        if html:
            meta = re.search(r'<meta name="robots" content="([^"]+)"', html).group(1)
            assert ('noindex' in header) == ('noindex' in meta), (path, header, meta)


def test_real_404_is_useful_and_not_indexed(client):
    for path in ('/no-such-page', '/learn/x', '/help/unknown', '/personal-search/foo'):
        res = client.get(path)
        assert res.status_code == 404, path
        html = res.get_data(as_text=True)
        assert 'That page isn’t here.' in html and 'noindex' in res.headers['X-Robots-Tag']
        assert '/self-service?problem=old-news' in html
    assert client.get('/data/snapshot_leads.jsonl').get_data() == b''


def test_no_agency_voice_or_promises_on_public_pages(client):
    paths = [p for p in sitemap_paths(client) if not p.startswith('/personal-search/')]
    paths += ['/no-such-page', '/diy-action/recover', '/billing', '/cancel.html']
    for path in paths:
        text = visible_text(client.get(path).get_data(as_text=True))
        hits = [b for b in BANNED if b in text]
        assert not hits, (path, hits)
        assert 'madisonjade pty' not in text, path


def test_desk_plan_text_is_also_clean():
    import json
    import plans
    text = json.dumps(plans.client_payload(), ensure_ascii=False).lower()
    assert not [b for b in BANNED if b in text]
    assert 'suppression' not in text


def test_analytics_only_on_marketing_pages(client, monkeypatch):
    monkeypatch.setenv('FMNO_GA_MEASUREMENT_ID', 'G-TEST')
    for path in ('/', '/help/reviews', '/learn', '/diy-action', '/pricing', '/old-news-article-on-google'):
        assert 'googletagmanager.com' in client.get(path).get_data(as_text=True), path
    for path in ('/self-service', '/self-service/tracker', '/billing', '/no-such-page', '/diy-action/workspace',
                 '/private-case-room/x', '/cancel.html'):
        assert 'googletagmanager.com' not in client.get(path).get_data(as_text=True), path
    res = client.post('/name-watch-alerts/waitlist', data={'email': 'bad'})
    assert 'googletagmanager.com' not in res.get_data(as_text=True)


def test_terms_and_privacy_are_real_and_match_the_site(client):
    terms = client.get('/terms').get_data(as_text=True)
    privacy = client.get('/privacy').get_data(as_text=True)
    for html in (terms, privacy):
        text = visible_text(html)
        assert 'draft' not in text
        assert 'madison jade pty ltd' in text and '56 661 580 936' in text
        assert 'effective 12 october 2026' in text
    assert 'Australian Consumer Law' in terms and 'South Australia' in terms and '7 days' in terms
    for name in ('Stripe', 'Render', 'Brevo', 'Google Analytics', 'OAIC', 'Telegram'):
        assert name in privacy, name
    assert 'we never see what you type there' in visible_text(privacy)


def test_namewatch_waitlist_stores_one_email_and_sends_nothing(client, monkeypatch, tmp_path):
    db = tmp_path / 'waitlist.sqlite3'
    monkeypatch.setattr(server, 'WAITLIST_DB', db)
    monkeypatch.setattr(server, 'send_brevo_email', lambda *a, **k: pytest.fail('No email may be sent'))
    assert client.post('/name-watch-alerts/waitlist', data={'email': 'not-an-email', 'consent': 'yes'}).status_code == 400
    assert client.post('/name-watch-alerts/waitlist', data={'email': 'a@example.com'}).status_code == 400
    assert not db.exists()
    ok = client.post('/name-watch-alerts/waitlist', data={'email': 'Person@Example.com', 'consent': 'yes'})
    assert ok.status_code == 200 and 'You’re on the list' in ok.get_data(as_text=True)
    client.post('/name-watch-alerts/waitlist', data={'email': 'person@example.com', 'consent': 'yes'})
    client.post('/name-watch-alerts/waitlist', data={'email': 'bot@example.com', 'consent': 'yes', 'website': 'spam'})
    rows = sqlite3.connect(db).execute('SELECT email FROM waitlist').fetchall()
    assert rows == [('person@example.com',)]
    assert ok.headers['X-Robots-Tag'] == 'noindex, nofollow'
    assert client.get('/name-watch-alerts/waitlist').status_code == 303


def test_asset_urls_are_versioned_and_cacheable(client):
    html = client.get('/').get_data(as_text=True)
    css = re.search(r'href="(/assets/site\.css\?v=[0-9a-f]+)"', html).group(1)
    res = client.get(css)
    assert res.status_code == 200 and 'max-age=31536000' in res.headers['Cache-Control']
    assert 'og:image" content="https://fixmynameonline.com/assets/fmno-share-1080.jpg"' in html
    assert len(html) < 60000


@pytest.fixture(scope='module')
def origin():
    http = make_server('127.0.0.1', 0, server.app)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:%s' % http.server_port
    http.shutdown(); thread.join()


def test_phone_layout_has_no_horizontal_scroll(origin):
    from playwright.sync_api import sync_playwright
    pages = ['/', '/self-service', '/self-service/tracker', '/help/old-news-articles', '/help/people-search-sites',
             '/how-it-works', '/pricing', '/faq', '/about', '/contact', '/learn', '/terms', '/privacy',
             '/name-watch-alerts', '/diy-action', '/old-court-records-showing-on-google', '/remove-bad-google-results',
             '/fix-my-name-online', '/google-your-name', '/when-google-makes-your-past-look-like-your-present', '/no-such-page']
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in ('light', 'dark'):
            page = browser.new_page(viewport={'width': 375, 'height': 812}, color_scheme=scheme)
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            for path in pages:
                page.goto(origin + path)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (scheme, path)
                bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
                assert bg in (('rgb(246, 244, 239)',) if scheme == 'light' else ('rgb(17, 21, 26)',)), (scheme, path, bg)
            assert not errors, errors
            page.close()
        browser.close()
