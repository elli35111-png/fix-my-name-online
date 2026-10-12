"""Site-wide contract for the self-serve redesign: honesty, indexing, privacy, layout."""
import re
import sqlite3
import threading
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from werkzeug.serving import make_server

import plans
import server

DOMAIN = 'https://fixmynameonline.com'
# ACL s18: copy that implies a person does the work, promises outcomes or sells a
# heuristic as a search. Checked on every public page's visible text.
BANNED = ['we review', 'we check', 'we map', 'what we check', 'what we privately check', 'our team',
          'managed process', 'private campaign', 'approved assets', 'search protection', 'suppress',
          'risk score', 'private score', 'we guarantee', 'guaranteed removal', 'we remove',
          'we will respond', 'supports clients', 'snapshot™', 'removal review™', 'review defence™',
          # 12 Oct 2026 review: nothing that implies we take cases in, map results or build content for people
          'send first', 'send for review', 'should i send', 'review is needed', 'careful review', 'private map',
          'evidence map', 'private search snapshot', 'reputation work', 'authority assets', 'search-risk',
          'removal-pathway', 'useful deliverable', 'operator base', 'mystery dashboards', 'track impressions',
          'it works more often than not', 'can usually be removed', 'can fix my name online check',
          'public assets are only created', 'automated tool’s safety scope',
          # 12 Oct 2026 audit: myths, overstated outcomes, AI tells and jargon
          'repeated searches', 'personalise what other people see', 'updates or drops the old result',
          'digital life sentence', 'not to sell fantasy', 'we exist because', 'pathway', 'trust signals',
          'reputation signals', 'map page one', 'search paths', 'operator can be australian']


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


def test_short_version_fits_the_guide(client):
    generic = 'ask the website owner first, then ask google to catch up'
    for path, expected in [('/reputation-monitoring-alerts', 'set up a free alert'),
                           ('/online-reputation-management-for-business', 'match the review to a specific rule'),
                           ('/online-reputation-management-australia', 'the first steps are the same in every country'),
                           ('/private-reputation-repair', 'you don’t have to tell anyone'),
                           ('/google-your-name-before-an-employer-does', 'search your name the way a stranger would')]:
        soup = BeautifulSoup(client.get(path).data, 'html.parser')
        short = soup.select_one('.short p').get_text(' ', strip=True).lower()
        assert expected in short and generic not in short, (path, short)
    # No guide still carries the old general-plan box.
    for path in sitemap_paths(client):
        if not path.startswith('/personal-search/'):
            assert generic not in visible_text(client.get(path).get_data(as_text=True)), path


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


# ---- 12 Oct 2026 review ----

def test_no_analytics_where_people_type(monkeypatch):
    monkeypatch.setenv('FMNO_GA_MEASUREMENT_ID', 'G-TEST')
    monkeypatch.setenv('FMNO_META_PIXEL_ID', '12345')
    c = server.app.test_client()
    for path in ('/name-watch-alerts', '/self-service', '/self-service/tracker'):
        body = c.get(path).get_data(as_text=True)
        assert 'googletagmanager.com' not in body and 'connect.facebook.net' not in body, path
    assert 'googletagmanager.com' in c.get('/pricing').get_data(as_text=True)
    site_js = (Path(server.BASE_DIR) / 'assets' / 'site.js').read_text()
    assert 'gtag(' not in site_js and 'choose_problem' not in site_js
    privacy = visible_text(c.get('/privacy').get_data(as_text=True))
    assert 'namewatch page and its waitlist form' in privacy
    assert 'which problem you pick' in privacy


def test_every_guide_reads_as_self_service_including_noindexed_ones():
    import json as _json
    for slug, guide in server.SEO_GUIDES.items():
        text = ' '.join([guide['title'], guide['h1'], guide['description'], guide['intro']] +
                        [a + ' ' + b for a, b in guide['sections']] + [a + ' ' + b for a, b in guide['faqs']]).lower()
        hits = [b for b in BANNED if b in text]
        assert not hits, (slug, hits)
        assert 'snapshot' not in text, slug
        assert not guide['h1'].istitle(), (slug, guide['h1'])  # sentence case, not Title Case
    generated = _json.loads((Path(server.BASE_DIR) / 'generated_seo_guides.json').read_text())
    assert not any(g['intro'].startswith('If ') and ' is the problem' in g['intro'] for g in generated.values())


def test_link_check_dates_are_not_claimed_for_unchecked_links(client):
    text = visible_text(client.get('/help/fake-profiles').get_data(as_text=True))
    assert 'official links last checked' in text
    assert 'haven’t been able to check facebook: report an impersonation account' in text
    unchecked = [l for l in plans.OFFICIAL_LINKS.values() if not l['checked']]
    assert unchecked  # if they all get checked one day, this test can go
    about = visible_text(client.get('/about').get_data(as_text=True))
    assert 'every official link shows the date' not in about


def test_pricing_does_not_undersell_the_free_letter(client):
    text = visible_text(client.get('/pricing').get_data(as_text=True))
    assert 'request letter built from the facts you enter' not in text
    assert 'letters written out in full from a short form' in text


def test_older_managed_packages_promise_no_work(monkeypatch):
    monkeypatch.setattr(server, 'verify_paid_checkout', lambda *a, **k: {'id': 'cs_test_legacy', 'payment_status': 'paid'})
    c = server.app.test_client()
    for res in (c.get('/success.html?tier=starter&session_id=cs_test_legacy'),
                c.get('/onboarding?plan=starter&session_id=cs_test_legacy'),
                c.post('/submit-onboarding', data={'plan': 'starter', 'session_id': 'cs_test_legacy', 'name': 'x', 'email': 'x@example.com'})):
        text = visible_text(res.get_data(as_text=True))
        assert 'no longer offered' in text and 'australian consumer law' in text
        for managed in ('we use careful', 'handle this safely', 'private onboarding', 'reputation repair pathways'):
            assert managed not in text
    assert server.send_onboarding_emails({'plan': 'starter', 'name': 'x', 'email': 'x@example.com'}, {'id': 'q'}) == {}
