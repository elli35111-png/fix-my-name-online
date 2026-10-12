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
    assert 'haven’t been able to check the “facebook: report an impersonation account” link' in text
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


# ---- 12 Oct 2026 final review ----

def test_comparison_tables_show_every_column_on_phones(origin):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 375, 'height': 812})
        for path, label in (('/pricing', 'Letter pack, US$19'), ('/how-it-works', 'What you can ask for'),
                            ('/privacy', 'Where it’s kept')):
            page.goto(origin + path)
            cells = page.locator('.table-stack td')
            assert cells.count() >= 9, path
            # Every cell, including the last column, sits fully inside the screen.
            right = page.evaluate("Math.max(...[...document.querySelectorAll('.table-stack td')].map(td => td.getBoundingClientRect().right))")
            assert right <= 375 - 16 + 1, (path, right)
            # The column name is shown next to each value.
            assert label in page.locator('.table-stack').inner_text(), path
            assert page.evaluate("document.querySelector('.table-stack').scrollWidth <= document.querySelector('.table-stack').clientWidth")
        # Desktop keeps the normal table.
        page.set_viewport_size({'width': 1280, 'height': 900})
        page.goto(origin + '/pricing')
        assert page.locator('.table-stack thead').is_visible()
        browser.close()


def test_buttons_that_wrap_keep_space_above_and_below(origin):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 375, 'height': 812})
        page.goto(origin + '/self-service?problem=old-news')
        for q, v in (('who', 'me'), ('now', 'left-out'), ('status', 'finished')):
            page.locator(f'[data-q="{q}"] input[value="{v}"]').check()
        page.check('#safety-none')
        page.click('#show-plan')
        page.wait_for_selector('#add-to-tracker')
        sizes = page.evaluate("""[...document.querySelectorAll('.btn')].filter(b => b.offsetParent).map(b => {
            const cs = getComputedStyle(b), pt = parseFloat(cs.paddingTop), pb = parseFloat(cs.paddingBottom);
            return [b.textContent.trim().slice(0, 40), pt, pb, (b.clientHeight - pt - pb) / parseFloat(cs.lineHeight)];
        })""")
        assert sizes
        for label, top, bottom, height in sizes:
            assert top >= 8 and bottom >= 8, (label, top, bottom)
        wrapped = [s for s in sizes if s[3] >= 1.8]  # label runs to two lines
        assert wrapped, 'expected at least one two-line button at 375 (the refresh-tool link)'
        browser.close()


def test_google_removal_is_never_stated_as_certain(client):
    for path in ('/remove-negative-google-results', '/worldwide-reputation-repair', '/learn'):
        text = visible_text(client.get(path).get_data(as_text=True))
        for certain in ('google will also remove', 'what google will remove', 'what it will remove',
                        'google removes contact details'):
            assert certain not in text, (path, certain)
    text = visible_text(client.get('/remove-negative-google-results').get_data(as_text=True))
    assert 'what google may remove directly' in text and 'can say no' in text


def test_terms_and_privacy_cover_namewatch_for_existing_subscribers(client):
    terms = visible_text(client.get('/terms').get_data(as_text=True))
    assert 'apart from namewatch for existing subscribers' in terms
    assert 'we don’t search for information about you.' not in terms.replace('apart from namewatch for existing subscribers (see section 6), we don’t search for information about you.', '')
    privacy = client.get('/privacy').get_data(as_text=True)
    soup = BeautifulSoup(privacy, 'html.parser')
    rows = [tr.get_text(' ', strip=True) for tr in soup.select('#collect ~ .table-wrap tr, .table-wrap tr')]
    namewatch = next(r for r in rows if r.startswith('NameWatch (existing subscribers only)'))
    for fact in ('DuckDuckGo', 'Google News', 'admin@fixmynameonline.com', 'counts only',
                 'phone', 'on our server, hosted by Render', 'backups', 'Brevo', 'Telegram',
                 'search results, and what each check has already seen, are kept on our own computer',
                 'hosted by Microsoft', 'names and phrases we watch', 'links found', 'sent mail'):
        assert fact in namewatch, fact
    assert 'not on Render' not in namewatch
    # NameWatch emails (with the watched names and links) leave copies in the
    # Microsoft-hosted admin@ mailbox, so nothing may say "only" on our computer.
    assert 'kept only on our own computer' not in namewatch
    providers_text = soup.find(id='providers').find_next('ul').get_text(' ', strip=True)
    assert 'NameWatch sign-up records' in providers_text and 'records from our earlier tools' in providers_text
    keep = soup.find(id='keep').find_next('ul').get_text(' ', strip=True)
    assert 'NameWatch: while your subscription runs' in keep
    providers = soup.find(id='providers').find_next('ul').get_text(' ', strip=True)
    assert 'DuckDuckGo' in providers and 'Google News' in providers
    assert 'Microsoft (United States): hosts admin@fixmynameonline.com' in providers
    assert 'NameWatch alerts and status notes' in providers
    # admin@ is Microsoft 365; Google only holds the internal Gmail notices.
    assert 'and our email inbox' not in providers and 'Gmail inbox' in providers


def test_paid_pack_is_not_sold_on_what_the_free_check_already_has(client):
    # The free tracker gives the same calendar file, so reminders are no reason to pay (ACL s18).
    for path in ('/', '/pricing'):
        soup = BeautifulSoup(client.get(path).data, 'html.parser')
        pack = soup.select_one('.price.featured').get_text(' ', strip=True).lower()
        assert 'calendar' not in pack and 'reminder' not in pack, path
    soup = BeautifulSoup(client.get('/diy-action').data, 'html.parser')
    sales = ' '.join(el.get_text(' ', strip=True) for el in soup.select('.lede, .ticks')).lower()
    assert 'calendar' not in sales and 'reminder' not in sales
    js = (Path(server.BASE_DIR) / 'assets' / 'self-service.js').read_text()
    offer = re.search(r"The letter pack saves[^']*'", js).group(0)
    assert 'reminder' not in offer
    # The free side still says it has them.
    assert 'Calendar reminder files' in client.get('/pricing').get_data(as_text=True)


def test_namewatch_and_what_we_dont_do_copy_is_plain_and_accurate(client, monkeypatch):
    guide = visible_text(client.get('/reputation-monitoring-alerts').get_data(as_text=True))
    assert 'alerts are paused' not in guide and 'new sign-ups are paused while we rebuild it' in guide
    assert 'if you already subscribe, your alerts carry on' in guide
    how = visible_text(client.get('/how-it-works').get_data(as_text=True))
    assert 'search google in the free check, or give you a “score”' in how
    about = visible_text(client.get('/about').get_data(as_text=True))
    assert 'search google for you in the free check' in about and 'namewatch, for existing subscribers only, runs searches' in about
    home = visible_text(client.get('/').get_data(as_text=True))
    assert 'check-back dates and notes kept online with each letter' in home
    monkeypatch.setattr(server, 'verify_paid_checkout', lambda *a, **kw: {'payment_status': 'paid', 'customer_details': {'email': 'paid@example.com'}})
    for path in ('/success.html?tier=sentinel&session_id=cs_x', '/onboarding?plan=sentinel&session_id=cs_x'):
        text = visible_text(client.get(path).get_data(as_text=True))
        for old in ('private monitoring file', 'fmno creates', 'first baseline', 'private activation', 'newly observed'):
            assert old not in text, (path, old)
    sent = []
    monkeypatch.setattr(server, 'send_brevo_email', lambda to, name, subject, html, text='': sent.append((to, html)) or True)
    server.send_onboarding_emails({'plan': 'sentinel', 'name': 'Test', 'email': 'paid@example.com'}, {'id': 'q1'})
    customer = visible_text(sent[0][1])
    assert 'private monitoring file' not in customer and 'baseline' not in customer and 'fmno runs' not in customer
    assert 'doesn’t contact anyone or remove anything' in customer
