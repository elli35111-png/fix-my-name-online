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

HTML = open("landing_page_v2.html", encoding="utf-8").read()


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
    # The Ava video tag must not autoplay or loop a fixed line.
    video_tag = re.search(r"<video[^>]*id=\"ava-video\"[^>]*>", HTML)
    assert video_tag, "ava-video tag not found"
    tag = video_tag.group(0)
    assert "autoplay" not in tag, "avatar must not autoplay"
    assert "loop" not in tag, "avatar must not loop a fixed line"
    # The old 'HEAR FROM AVA' unmute-loop button must be removed.
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


def test_concierge_section_moved_below_fold():
    # Reputation TV / concierge now lives in its own section, not the hero.
    assert 'id="reputation-tv"' in HTML
    hero = HTML.split('id="reputation-tv"')[0]
    assert 'id="private-search-concierge"' not in hero


def test_concierge_no_autocall_on_load_and_initial_field_ready():
    # First page load should not immediately burn a model/voice call or show a
    # temporary thinking state. The first typed answer should map to names_to_check.
    assert "setConciergeTopic('privacy', false)" not in HTML
    assert "Do not auto-call the model" in HTML
    assert "current_field:'names_to_check'" in HTML
    assert "Private Concierge is thinking..." in HTML  # allowed only after explicit action


def test_sticky_boost_bar_not_visible_until_scroll():
    assert "transform:translate(-50%,140%)" in HTML
    assert "boost-visible" in HTML
    assert "window.scrollY > 420" in HTML


def test_claude48_polish_guards():
    assert "Operated by MadisonJade Pty Ltd" in HTML
    assert "ABN 56 661 580 936" in HTML
    assert "function applyVoiceMode()" in HTML
    assert "TEXT CONCIERGE" in HTML
    assert "hasAttribute('data-topic')" in HTML
    assert "ava-no-video" in HTML
    assert "prefers-reduced-motion" in HTML


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
    assert "Get your Private Reputation Risk Score™" in body
    assert "Name / business / search phrase" in body
    assert "Email for private result" in body
    assert "Optional: add links, review details or extra names" in body
    assert "Operated by MadisonJade Pty Ltd" in body
    assert "ABN 56 661 580 936" in body
    assert "snapshot-shell" in body
    assert "What you get" in body
    assert "id=\"snapshot-progress\"" in body
    assert "Opening private case room" in body
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
    assert 'US$49 once' in body
    assert 'You confirm the facts and submit every request yourself' in body
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
            return type('CheckoutSession', (), {'url': 'https://checkout.stripe.test/fmno'})()

    monkeypatch.setattr(server.stripe.checkout, 'Session', FakeSession)
    monkeypatch.setattr(server.stripe, 'api_key', 'sk_test_fmno')
    monkeypatch.setenv('STRIPE_PRICE_DIY_ACTION', 'price_fmno_diy')
    response = client().get('/checkout/diy-action')
    assert response.status_code == 302
    assert response.headers['Location'] == 'https://checkout.stripe.test/fmno'
    assert captured['success_url'] == server.DOMAIN + '/diy-action/start?session_id={CHECKOUT_SESSION_ID}'
    assert captured['line_items'] == [{'price': 'price_fmno_diy', 'quantity': 1}]
    assert captured['metadata']['tier'] == 'diy-action'


def test_namewatch_checkout_alias_uses_the_live_sentinel_subscription(monkeypatch):
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
    assert response.headers['Location'] == 'https://checkout.stripe.test/namewatch'
    assert captured['mode'] == 'subscription'
    assert captured['line_items'] == [{'price': 'price_fmno_namewatch', 'quantity': 1}]
    assert captured['metadata']['tier'] == 'sentinel'
    assert 'tier=sentinel' in captured['success_url']


def test_post_snapshot_paid_paths_only_sell_automated_products():
    body = server.paid_next_steps_html('qa_snapshot')
    assert 'NameWatch Alert™' in body
    assert '/checkout/sentinel?source=qa_snapshot' in body
    assert 'DIY Reputation Action Workspace™' in body
    assert '/diy-action?source=qa_snapshot' in body
    for retired in ('Removal Review™', 'Review Defence™', 'Starter™', '/checkout/removal-review', '/checkout/starter'):
        assert retired not in body


def test_snapshot_email_contains_both_active_self_service_next_steps(monkeypatch):
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
    assert server.DOMAIN + '/checkout/sentinel' in customer_html
    assert server.DOMAIN + '/diy-action' in customer_html
    assert '$29/month' in customer_html
    assert '$49 once' in customer_html
    assert 'Removal Review™' not in customer_html
    assert 'Review Defence™' not in customer_html


def test_namewatch_success_keeps_checkout_session_in_secure_onboarding_link():
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
    assert health['namewatch_checkout_configured'] is True
    assert health['stripe_webhook_configured'] is True


def test_public_services_page_only_sells_automated_products():
    body = client().get('/services').get_data(as_text=True)
    assert 'NameWatch Alert™' in body
    assert 'DIY Reputation Action Workspace™' in body
    assert '/checkout/sentinel?source=services' in body
    assert '/diy-action?source=services' in body
    for retired in ('Removal Review™', 'Review Defence™', 'Starter™', 'Pro™', 'Premium™'):
        assert retired not in body



def test_paid_diy_workspace_generates_action_pack(tmp_path):
    c = client()
    original_actions, original_clicks = server.DIY_ACTIONS_FILE, server.CLICK_EVENTS_FILE
    server.DIY_ACTIONS_FILE = tmp_path / 'diy.jsonl'
    server.CLICK_EVENTS_FILE = tmp_path / 'clicks.jsonl'
    try:
        session_id = 'cs_test_fmno_diy_paid'
        start = c.get('/diy-action/start?session_id=' + session_id)
        assert start.status_code == 200
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
        assert result.status_code == 200
        assert 'DIY action pack generated' in text
        assert 'FMNO-DIY-' in text
        assert 'Official Google outdated-content tool' in text
        assert server.DIY_ACTIONS_FILE.exists()
    finally:
        server.DIY_ACTIONS_FILE, server.CLICK_EVENTS_FILE = original_actions, original_clicks


def test_homepage_retires_human_review_sales_language():
    body = client().get('/').get_data(as_text=True)
    assert 'DIY ACTION WORKSPACE' in body
    assert '$49' in body
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
