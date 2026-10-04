"""Smoke checks for the FixMyNameOnline homepage overhaul.

Run:  python -m pytest test_homepage.py   (or)   python test_homepage.py

These tests focus on the conversion-oriented homepage rules requested:
- Homepage route still serves the landing page (SEO/routes preserved).
- The hero has a single primary CTA to the Free Search Snapshot.
- The Ava avatar does NOT autoplay or loop a fixed line (no autoplay/loop attrs).
- The avatar/concierge never falls back to cheap browser speechSynthesis TTS.
- The optional ElevenLabs voice endpoint stays silent (204) when unconfigured.
- Core routes/forms/concierge API remain intact.
"""

import os
import re
import json
from xml.etree import ElementTree as ET

os.environ.setdefault("FMNO_DATA_DIR", "data")

import server  # noqa: E402

HTML = open("homepage.html", encoding="utf-8").read()


def client():
    server.app.testing = True
    return server.app.test_client()


def test_homepage_route_serves_landing():
    res = client().get("/")
    assert res.status_code == 200
    body = res.get_data(as_text=True)
    assert "FIX MY NAME ONLINE" in body
    assert "Free Search Snapshot" in body


def test_canonical_and_seo_preserved():
    # SEO canonical + structured data must remain on the homepage.
    body = client().get("/").get_data(as_text=True)
    assert 'rel="canonical"' in body
    assert "application/ld+json" in body
    assert "FAQPage" in body


def test_single_primary_hero_cta():
    # Exactly one primary hero snapshot CTA (the decluttered single primary action).
    hero = HTML.split('id="reputation-tv"')[0]
    primary = re.findall(r'data-track="homepage_hero_snapshot"', hero)
    assert len(primary) == 1, f"expected 1 primary hero CTA, found {len(primary)}"
    # The old cluttered mini-form + triple CTA row should be gone from the hero.
    assert "homepage_name_miniform" not in hero
    assert "See What We Handle" not in hero


def test_avatar_not_autoplay_or_loop():
    # Redesigned homepage intentionally has no media/voice concierge.
    assert '<video' not in HTML and '<audio' not in HTML
    assert "HEAR FROM AVA" not in HTML
    assert "ava-play-btn" not in HTML


def test_no_browser_tts():
    # No cheap browser TTS anywhere.
    assert "speechSynthesis" not in HTML
    assert "SpeechSynthesisUtterance" not in HTML


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


def test_homepage_routes_to_complete_intake_not_mini_form():
    assert '/free-search-snapshot?source=homepage_hero_snapshot' in HTML
    assert 'action="/submit-snapshot"' not in HTML
    assert '/self-service' in HTML


def test_homepage_never_calls_concierge_model_or_voice():
    script = open('assets/homepage.js', encoding='utf-8').read()
    assert '/api/concierge/' not in HTML + script
    assert 'speechSynthesis' not in script


def test_accessible_navigation_and_legacy_anchors():
    assert 'aria-controls="main-nav"' in HTML
    assert 'aria-expanded="false"' in HTML
    for anchor in ('how-it-works', 'pricing', 'faq'):
        assert 'id="' + anchor + '"' in HTML


def test_claude48_polish_guards():
    assert "Operated by MadisonJade Pty Ltd" in HTML
    assert "ABN 56 661 580 936" in HTML
    assert 'cdn.tailwindcss.com' not in HTML
    assert 'fonts.googleapis.com' not in HTML
    assert "prefers-reduced-motion" in open('assets/homepage.css', encoding='utf-8').read()


def test_core_routes_preserved():
    c = client()
    for path in (
        "/free-search-snapshot",
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


def test_snapshot_form_conversion_polish():
    body = client().get("/app?source=qa_test").get_data(as_text=True)
    assert "Your next step starts here." in body
    assert "Name / business / search phrase" in body
    assert "Email for your request" in body
    assert "Country and state / region" in body
    assert "Who is this for?" in body
    assert 'name="source_page" value="qa_test"' in body
    assert "Operated by MadisonJade Pty Ltd" in body
    assert "ABN 56 661 580 936" in body
    assert "snapshot-shell" in body
    assert "What you get" in body
    assert "not a live Google search" in body
    assert '/assets/snapshot-intake.js' in body
    assert "Private intake · no public case disclosure" in body


def test_inner_page_header_is_fmno_only():
    body = client().get('/diy-action').get_data(as_text=True)
    assert '<a class="logo" href="/">FIX MY NAME ONLINE™</a>' in body
    assert 'aria-label="Main navigation"' in body
    assert 'FIXMYNAMEONLINE™ · MADISONJADE PTY LTD' not in body



def test_diy_product_and_legacy_offer_gates():
    c = client()
    sales = c.get('/diy-action')
    assert sales.status_code == 200
    body = sales.get_data(as_text=True)
    assert 'US$19' in body and 'US$49' not in body
    assert 'submit requests yourself' in body
    checkout = c.get('/checkout/diy-action')
    assert checkout.status_code == 503
    assert 'Checkout is temporarily unavailable' in checkout.get_data(as_text=True)
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


def test_snapshot_email_contains_one_matching_route_and_free_self_service(monkeypatch):
    sent = []
    monkeypatch.setattr(server, 'send_brevo_email', lambda *args: sent.append(args) or True)
    monkeypatch.setattr(server, 'send_internal_alert_email', lambda *args: {'admin@example.com': True})
    result = server.send_snapshot_emails(
        {'name': 'Test Person', 'email': 'person@example.com'},
        server.TRIAGE_NEXT_STEPS['alerts'],
        {'id': 'FMNO-TEST', 'priority': 'standard'},
        case=None,
        report=None,
        case_room=None,
    )
    assert result['customer_email_sent'] is True
    customer_html = sent[0][3]
    assert server.DOMAIN + '/name-watch-alerts' in customer_html
    assert server.DOMAIN + '/self-service' in customer_html
    assert server.DOMAIN + '/diy-action' not in customer_html
    assert 'not a live Google search' in customer_html
    assert 'privately review' not in customer_html
    assert result['internal_email_sent'] == {}
    assert 'Removal Review™' not in customer_html
    assert 'Review Defence™' not in customer_html


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
    assert 'Single Action' in body and 'Action Pack' not in body
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
    assert 'DIY Action' in body and 'Workspace™' in body
    assert '$19' in body and '$49' not in body
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
