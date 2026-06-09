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


def test_snapshot_form_conversion_polish():
    body = client().get("/app?source=qa_test").get_data(as_text=True)
    assert "Start your Free Search Snapshot™" in body
    assert "Operated by MadisonJade Pty Ltd" in body
    assert "ABN 56 661 580 936" in body
    assert "snapshot-shell" in body
    assert "What happens next" in body
    assert "id=\"snapshot-progress\"" in body
    assert "Submitting private snapshot" in body
    assert "Private intake · no public case disclosure" in body


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
