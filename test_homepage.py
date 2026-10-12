"""Homepage and site contract for the self-serve redesign (Oct 2026).

Run:  python -m pytest test_homepage.py

- The homepage names the visitor's problem on the first screen: six problem
  tiles plus "not sure", each opening the free check with that problem.
- The who line (company + ABN), "not a law firm" and the safety strip are visible.
- No video/voice concierge, no browser TTS, no tracking on desk links.
- Core routes, checkout gates and the concierge API remain intact.
"""

import os
import re
import json
from xml.etree import ElementTree as ET

os.environ.setdefault("FMNO_DATA_DIR", "data")

import server  # noqa: E402

import plans  # noqa: E402


def home_html():
    return client().get("/").get_data(as_text=True)


def client():
    server.app.testing = True
    return server.app.test_client()


def test_homepage_route_serves_landing():
    res = client().get("/")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "Something about you shows up on Google. Here’s what you can do about it." in body
    assert "What’s showing up for your name?" in body
    assert "Free Search Snapshot" not in body


def test_canonical_and_seo_preserved():
    # SEO canonical + structured data must remain on the homepage.
    body = client().get("/").get_data(as_text=True)
    assert 'rel="canonical"' in body
    assert "application/ld+json" in body
    assert "FAQPage" in body


def test_hero_names_six_problems_and_links_into_the_free_check():
    hero = home_html().split('class="hero"')[1].split('class="safety"')[0]
    for p in plans.PROBLEMS:
        assert f'href="/self-service?problem={p["key"]}"' in hero, p["key"]
        assert p["label"] in hero
    assert 'href="/self-service?problem=not-sure"' in hero
    assert "We don’t search Google or give you a score." in hero


def test_avatar_not_autoplay_or_loop():
    # Redesigned homepage intentionally has no media/voice concierge.
    html = home_html()
    assert '<video' not in html and '<audio' not in html
    assert "HEAR FROM AVA" not in html
    assert "ava-play-btn" not in html


def test_no_browser_tts():
    html = home_html() + open('assets/site.js', encoding='utf-8').read() + open('assets/self-service.js', encoding='utf-8').read()
    assert "speechSynthesis" not in html
    assert "SpeechSynthesisUtterance" not in html


def test_voice_endpoint_silent_when_unconfigured():
    # Force "unconfigured" regardless of the ambient environment, then assert the
    # endpoint stays silent (204) instead of erroring or using browser TTS.
    original = server.concierge_voice_configured
    server.concierge_voice_configured = lambda: False
    try:
        res = client().post("/api/concierge/voice", json={"text": "Hello there."})
        assert res.status_code == 204
        assert not res.get_data()
    finally:
        server.concierge_voice_configured = original


def test_voice_config_uses_owned_bridge_without_render_keys():
    # Render does not need a browser/system voice or exposed key; when direct
    # ElevenLabs env is absent, the server uses the owned FPS Netlify Bill bridge.
    saved = {k: os.environ.pop(k, None) for k in ("ELEVENLABS_API_KEY", "XI_API_KEY")}
    try:
        cfg = server.concierge_voice_config()
        assert cfg is not None
        assert cfg.get("mode") == "bridge"
        assert server.concierge_voice_configured() is True
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_voice_configured_flag_in_health():
    body = client().get("/health").get_json()
    assert "concierge_voice_configured" in body
    assert isinstance(body["concierge_voice_configured"], bool)


def test_concierge_chat_exposes_voice_flag():
    res = client().post("/api/concierge/chat", json={"topic": "privacy"})
    assert res.status_code == 200
    data = res.get_json()
    assert data.get("ok") is True
    assert "voice_available" in data
    assert isinstance(data["voice_available"], bool)


def test_homepage_has_no_intake_form_and_no_model_calls():
    html = home_html()
    assert 'action="/submit-snapshot"' not in html
    assert '/free-search-snapshot' not in html and 'href="/app' not in html
    script = open('assets/site.js', encoding='utf-8').read()
    assert '/api/concierge/' not in html + script
    assert 'fetch(' not in script and 'sendBeacon' not in script


def test_accessible_navigation_and_legacy_anchors():
    html = home_html()
    assert '<a class="skip" href="#main">' in html
    assert '<details class="menu">' in html and 'aria-label="Main"' in html
    for anchor in ('how-it-works', 'pricing', 'faq'):
        assert 'id="' + anchor + '"' in html


def test_trust_line_safety_strip_and_no_cdn():
    html = home_html()
    assert "Run by Madison Jade Pty Ltd · ABN 56 661 580 936 · Australia. Not a law firm." in html
    assert 'class="safety"' in html and 'Call 000.' in html and 'https://www.esafety.gov.au/report' in html
    assert "MadisonJade" not in html
    assert 'cdn.tailwindcss.com' not in html
    assert 'fonts.googleapis.com' not in html
    assert "prefers-reduced-motion" in open('assets/site.css', encoding='utf-8').read()
    assert '"legalName": "Madison Jade Pty Ltd"' in html and '"taxID": "56661580936"' in html


def test_core_routes_preserved():
    c = client()
    for path in (
        "/free-search-snapshot",
        "/self-service",
        "/self-service/tracker",
        "/how-it-works",
        "/faq",
        "/pricing",
        "/privacy",
        "/terms",
        "/sitemap.xml",
        "/robots.txt",
    ):
        assert c.get(path).status_code in (200, 301, 302), f"{path} broke"


def test_private_data_files_are_never_publicly_served():
    c = client()
    for path in (
        "/data/snapshot_leads.jsonl",
        "/data/private_case_rooms.jsonl",
        "/data/fulfilment_queue.jsonl",
        "/data/onboarding_submissions.jsonl",
    ):
        response = c.get(path)
        assert response.status_code == 404, f"private path was public: {path}"
        assert response.get_data() == b""


def test_allowlisted_public_assets_still_serve():
    c = client()
    assert c.get("/assets/ava_concierge_poster.jpg").status_code == 200
    assert c.get("/static/personal/ilija-cakar-approved-profile-photo-square.jpg").status_code == 200


def test_old_snapshot_urls_redirect_to_the_free_check():
    c = client()
    for path in ('/app?source=qa_test', '/free-search-snapshot', '/free-snapshot', '/snapshot'):
        res = c.get(path)
        assert res.status_code == 301, path
        assert res.headers['Location'] == '/self-service?from=snapshot'
    assert c.get('/submit-snapshot').headers['Location'] == '/self-service'


def test_inner_pages_share_one_header_and_footer():
    c = client()
    for path in ('/diy-action', '/terms', '/learn', '/old-news-article-on-google', '/help/reviews', '/self-service'):
        body = c.get(path).get_data(as_text=True)
        assert '<header class="site-header">' in body, path
        assert '<footer class="site-footer">' in body, path
        assert 'ABN 56 661 580 936' in body, path
        assert '/assets/site.css?v=' in body, path
        assert 'FIX MY NAME ONLINE™' not in body and 'class="seo-nav"' not in body, path



def test_diy_product_and_legacy_offer_gates():
    c = client()
    sales = c.get('/diy-action')
    assert sales.status_code == 200
    body = sales.get_data(as_text=True)
    assert 'US$19' in body and 'US$49' not in body
    assert 'You still check and send everything yourself.' in body
    assert 'Sample with example details' in body
    checkout = c.get('/checkout/diy-action')
    assert checkout.status_code == 503
    assert 'Checkout isn’t available right now, and no payment has been taken.' in checkout.get_data(as_text=True)
    for legacy in ('removal-review', 'review-defence', 'starter', 'pro', 'premium'):
        res = c.get('/checkout/' + legacy)
        assert res.status_code == 302
        assert '/diy-action?legacy_offer_retired=1' in res.headers['Location']


def test_diy_checkout_redirects_paid_customer_to_workspace(monkeypatch):
    captured = {}

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return {'url': 'https://checkout.stripe.test/fmno'}

    monkeypatch.setattr(server.stripe.checkout, 'Session', FakeSession)
    monkeypatch.setattr(server.stripe, 'api_key', 'sk_test_fmno')
    monkeypatch.setenv('FMNO_APPROVAL_SECRET', 'synthetic-approval-secret-at-least-32-characters')
    monkeypatch.setenv('STRIPE_PRICE_DIY_SINGLE', 'price_fmno_diy')
    monkeypatch.setattr(server.stripe.Price, 'retrieve', lambda pid: {'active': True, 'currency': 'usd', 'unit_amount': 1900, 'type': 'one_time'})
    response = client().get('/checkout/diy-action')
    assert response.status_code == 302
    assert response.headers['Location'] == 'https://checkout.stripe.test/fmno'
    assert captured['success_url'] == server.DOMAIN + '/diy-action/start?session_id={CHECKOUT_SESSION_ID}'
    assert captured['line_items'] == [{'price': 'price_fmno_diy', 'quantity': 1}]
    assert captured['metadata']['tier'] == 'diy-single'


def test_namewatch_checkout_alias_pauses_new_sales(monkeypatch):
    captured = {}

    class FakeSession:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type('CheckoutSession', (), {'url': 'https://checkout.stripe.test/namewatch'})()

    monkeypatch.setattr(server.stripe.checkout, 'Session', FakeSession)
    monkeypatch.setattr(server.stripe, 'api_key', 'sk_test_fmno')
    monkeypatch.setenv('STRIPE_PRICE_SENTINEL', 'price_fmno_namewatch')
    response = client().get('/checkout/name-watch?source=qa_alias')
    assert response.status_code == 302
    assert response.headers['Location'] == '/name-watch-alerts'
    assert captured == {}


def test_post_snapshot_paid_paths_only_sell_automated_products():
    body = server.paid_next_steps_html('qa_snapshot')
    assert 'US$19' in body and 'US$49' not in body
    assert '/checkout/sentinel' not in body
    assert '/self-service' in body
    assert '/diy-action?source=qa_snapshot' in body
    for retired in ('Removal Review™', 'Review Defence™', 'Starter™', '/checkout/removal-review', '/checkout/starter'):
        assert retired not in body


def test_retired_snapshot_never_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(server, 'send_brevo_email', lambda *args: sent.append(args) or True)
    client().post('/submit-snapshot', data={'name': 'Test Person', 'email': 'person@example.com', 'goal': 'x'})
    assert sent == []
    assert not hasattr(server, 'send_snapshot_emails')


def test_namewatch_success_keeps_checkout_session_in_secure_onboarding_link(monkeypatch):
    monkeypatch.setattr(server, 'verify_paid_checkout', lambda *a, **kw: {'payment_status': 'paid'})
    body = client().get('/success.html?tier=sentinel&session_id=cs_live_example').get_data(as_text=True)
    assert '/onboarding?plan=sentinel&amp;session_id=cs_live_example' in body
    assert 'Activate NameWatch monitoring' in body


def test_namewatch_onboarding_requires_verified_paid_session(monkeypatch):
    monkeypatch.setattr(server, 'verify_paid_checkout', lambda session_id, expected_tier=None: None)
    denied = client().get('/onboarding?plan=sentinel&session_id=cs_live_unpaid')
    assert denied.status_code == 402
    monkeypatch.setattr(server, 'verify_paid_checkout', lambda session_id, expected_tier=None: {
        'id': session_id,
        'payment_status': 'paid',
        'status': 'complete',
        'metadata': {'tier': 'sentinel'},
        'customer_details': {'email': 'paid@example.com'},
    })
    allowed = client().get('/onboarding?plan=sentinel&session_id=cs_live_paid')
    text = allowed.get_data(as_text=True)
    assert allowed.status_code == 200
    assert 'Activate NameWatch monitoring' in text
    assert 'name="session_id" value="cs_live_paid"' in text
    assert 'value="paid@example.com"' in text


def test_health_reports_namewatch_and_webhook_readiness(monkeypatch):
    monkeypatch.setattr(server.stripe, 'api_key', 'sk_test_fmno')
    monkeypatch.setenv('STRIPE_PRICE_SENTINEL', 'price_fmno_namewatch')
    monkeypatch.setattr(server, 'STRIPE_WEBHOOK_SECRET', 'whsec_test')
    health = client().get('/health').get_json()
    assert health['namewatch_checkout_configured'] is False
    assert health['namewatch_new_sales'] == 'paused'
    assert health['stripe_webhook_configured'] is True


def test_public_services_page_only_sells_automated_products():
    body = client().get('/services').get_data(as_text=True)
    assert 'Letter pack (Single Action), US$19' in body and 'Action Pack' not in body
    assert 'US$19' in body and 'US$49' not in body
    assert '/checkout/sentinel' not in body
    assert '/diy-action?source=services' in body
    for retired in ('Removal Review™', 'Review Defence™', 'Starter™', 'Pro™', 'Premium™'):
        assert retired not in body



def test_legacy_synthetic_session_id_is_not_a_payment_bypass(tmp_path):
    c = client()
    original_actions, original_clicks = server.DIY_ACTIONS_FILE, server.CLICK_EVENTS_FILE
    server.DIY_ACTIONS_FILE = tmp_path / 'diy.jsonl'
    server.CLICK_EVENTS_FILE = tmp_path / 'clicks.jsonl'
    try:
        session_id = 'cs_test_fmno_diy_paid'
        start = c.get('/diy-action/start?session_id=' + session_id)
        assert start.status_code == 402
        token = server.diy_access_token(session_id)
        result = c.post('/diy-action/generate', data={
            'session_id': session_id, 'access_token': token, 'name': 'Test Person',
            'email': 'test@example.com', 'target_url': 'https://example.com/old-article',
            'issue_type': 'outdated', 'requested_outcome': 'correct',
            'problem_summary': 'The page omits the later corrected outcome.',
            'evidence_summary': 'Correction document dated 2025-01-01.',
            'correct_information': 'The matter was corrected on 2025-01-01.',
            'truth_confirmed': 'yes',
        })
        text = result.get_data(as_text=True)
        assert result.status_code == 403
        assert 'DIY action pack generated' not in text
        assert not server.DIY_ACTIONS_FILE.exists()
    finally:
        server.DIY_ACTIONS_FILE, server.CLICK_EVENTS_FILE = original_actions, original_clicks


def test_homepage_retires_human_review_sales_language():
    body = client().get('/').get_data(as_text=True)
    assert 'Letter pack for one link' in body and 'US$19' in body
    assert '$49' not in body and 'US$29' not in body
    assert 'NameWatch' in body and 'Join the waitlist' in body
    assert 'HUMAN REVIEW' not in body
    assert 'REMOVAL REVIEW™</h3><div class="text-4xl font-bold">$297' not in body


def test_exact_brand_and_query_guides_are_index_ready():
    c = client()
    for path in ('/fix-my-name-online', '/fix-your-name-online', '/how-to-fix-your-reputation-online'):
        res = c.get(path)
        body = res.get_data(as_text=True)
        assert res.status_code == 200
        assert 'name="robots" content="index,follow,max-image-preview:large"' in body
        assert '<link rel="canonical" href="https://fixmynameonline.com' + path + '">' in body
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
        assert match
        schema = json.loads(match.group(1))
        assert schema['@context'] == 'https://schema.org'
    assert 'does not process legal name changes' in c.get('/fix-my-name-online').get_data(as_text=True)
    assert 'max-image-preview' in c.get('/help/old-news-articles').get_data(as_text=True)


def test_sitemap_index_separates_core_guides_and_profiles():
    c = client()
    root = ET.fromstring(c.get('/sitemap.xml').data)
    locations = [node.text for node in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap/{http://www.sitemaps.org/schemas/sitemap/0.9}loc')]
    assert locations == [
        'https://fixmynameonline.com/sitemap-core.xml',
        'https://fixmynameonline.com/sitemap-guides.xml',
        'https://fixmynameonline.com/sitemap-personal-search.xml',
    ]
    core = c.get('/sitemap-core.xml').get_data(as_text=True)
    for removed in ('/app<', '/free-search-snapshot<', '/questions<'):
        assert 'https://fixmynameonline.com' + removed not in core
    assert 'https://fixmynameonline.com/help/people-search-sites' in core
    assert 'https://fixmynameonline.com/fix-your-name-online' in core
    assert 'https://fixmynameonline.com/how-to-fix-your-reputation-online' in core


def test_near_duplicate_generated_guides_are_noindex_and_not_submitted():
    assert server.LOW_VALUE_SEO_GUIDES
    slug = sorted(server.LOW_VALUE_SEO_GUIDES - {'fix-my-name-on-line'})[0]
    body = client().get('/' + slug).get_data(as_text=True)
    assert 'name="robots" content="noindex,follow"' in body
    guide_sitemap = client().get('/sitemap-guides.xml').get_data(as_text=True)
    assert f'https://fixmynameonline.com/{slug}<' not in guide_sitemap


if __name__ == "__main__":
    passed = 0
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
                passed += 1
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL {name}: {exc}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)
