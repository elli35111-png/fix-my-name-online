"""Shared page shell for Fix My Name Online.

One header, one footer, one safety strip and one stylesheet for every public
page: homepage, desk, guides, legal pages, the paid workspace and the 404.
Server-side only; no personal data passes through here.
"""
import hashlib
import html
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

COMPANY = 'Madison Jade Pty Ltd'
ABN = '56 661 580 936'
ABN_DIGITS = '56661580936'
BRAND = 'Fix My Name Online'
CONTACT_EMAIL = 'admin@fixmynameonline.com'
LAST_REVIEWED = '12 October 2026'
LAST_REVIEWED_ISO = '2026-10-12'


def esc(value):
    return html.escape(str(value if value is not None else ''), quote=True)


def _asset_version():
    digest = hashlib.sha256()
    for name in ('site.css', 'site.js', 'self-service.js'):
        path = BASE_DIR / 'assets' / name
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


ASSET_VERSION = _asset_version()


def asset(name):
    return f'/assets/{name}?v={ASSET_VERSION}'


ICONS = {
    'news': '<path d="M4 5h12a1 1 0 0 1 1 1v12a2 2 0 0 0 2 2H6a2 2 0 0 1-2-2z"/><path d="M17 9h3v9a2 2 0 0 1-2 2"/><path d="M7.5 9h6M7.5 13h6M7.5 16.5h4"/>',
    'people': '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2"/><path d="M6 16c.7-1.3 1.7-2 3-2s2.3.7 3 2M14.5 10h4M14.5 13.5h3"/>',
    'fake': '<circle cx="10" cy="8" r="4"/><path d="M3 20c1.3-3.2 4-4.8 7-4.8 1.2 0 2.3.2 3.3.7M16 15l5 5M21 15l-5 5"/>',
    'court': '<path d="M12 4v16M8 20h8M5 7h14M5 7l-3 6a3 3 0 0 0 6 0zM19 7l-3 6a3 3 0 0 0 6 0z"/>',
    'star': '<path d="m12 3.5 2.6 5.3 5.9.9-4.3 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.3-4.1 5.9-.9z"/>',
    'image': '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-9 9"/>',
    'help': '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 0 1 4.8 1c0 1.7-2.4 2-2.4 3.6M12 17.2h.01"/>',
    'lock': '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    'shield': '<path d="M12 3 19 6v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="m9 12 2 2 4-4"/>',
    'clock': '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    'arrow': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'ext': '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    'alert': '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4M12 17h.01"/>',
    'phone': '<path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
    'file': '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    'calendar': '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    'download': '<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>',
    'upload': '<path d="M12 20V9M7 14l5-5 5 5M5 4h14"/>',
    'copy': '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h9"/>',
    'building': '<path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M3 21h18M8 8h3M8 12h3M8 16h3"/>',
    'nosearch': '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5M8.5 8.5l5 5"/>',
    'search': '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/>',
    'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
    'close': '<path d="M6 6l12 12M18 6 6 18"/>',
    'bell': '<path d="M6 16v-5a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'check': '<path d="m5 12 5 5 9-10"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    'print': '<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7" rx="1"/>',
    'pause': '<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
    'scales': '<path d="M12 4v16M8 20h8M5 7h14M5 7l-3 6a3 3 0 0 0 6 0zM19 7l-3 6a3 3 0 0 0 6 0z"/>',
}


def sprite():
    symbols = ''.join(f'<symbol id="i-{key}" viewBox="0 0 24 24">{value}</symbol>' for key, value in ICONS.items())
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true" focusable="false">{symbols}</svg>'


def icon(name, cls='icon'):
    return f'<svg class="{cls}" aria-hidden="true" focusable="false"><use href="#i-{name}"/></svg>'


LOGO = f'<a class="logo" href="/"><span class="logo-mark" aria-hidden="true">F<i>.</i></span>{BRAND}</a>'

NAV_LINKS = [
    ('/how-it-works', 'How it works', 'how'),
    ('/learn', 'Guides', 'guides'),
    ('/pricing', 'Pricing', 'pricing'),
    ('/about', 'About', 'about'),
]


def header(current=None, desk=False):
    links = ''.join(
        f'<a href="{href}"' + (' aria-current="page"' if key == current else '') + f'>{label}</a>'
        for href, label, key in NAV_LINKS)
    if desk:
        cta = f'<a class="btn btn-secondary btn-sm" href="/self-service/tracker">{icon("file", "icon icon-sm")}My tracker</a>'
    else:
        cta = '<a class="btn btn-primary btn-sm" href="/self-service">Start free check</a>'
    sheet = ''.join(f'<a href="{href}">{label}</a>' for href, label, _key in NAV_LINKS)
    return f'''<header class="site-header">
<div class="wrap">
{LOGO}
<nav class="nav" aria-label="Main">{links}{cta}</nav>
<details class="menu">
<summary class="menu-btn" aria-label="Open menu">{icon("menu", "icon icon-sm")}<span>Menu</span></summary>
<nav class="menu-sheet" aria-label="Menu">{sheet}<a href="/self-service">Free check and plan</a><a href="/self-service/tracker">My tracker</a><a class="btn btn-primary btn-block" href="/self-service">Start free check</a></nav>
</details>
</div>
</header>'''


LAW_NOTICE = f'''<div class="notice" id="law-notice" role="note" hidden>
<div class="wrap">{icon("info", "icon icon-sm")}<p>Came from a law firm directory? We’re a self-service tool you use yourself, not a law firm. <a href="/about#legal-help">Need a lawyer?</a></p></div>
</div>'''


# Safety numbers by country. Shown on the homepage, problem pages, guides and plans.
SAFETY_SETS = {
    'au': [('In danger now?', 'Call 000.', None, None),
           ('Threats, intimate images or a child involved?', None, 'Report to eSafety', 'https://www.esafety.gov.au/report'),
           ('Need to talk?', None, 'Lifeline 13 11 14', 'tel:131114')],
    'nz': [('In danger now?', 'Call 111.', None, None),
           ('Online harm or threats?', None, 'Netsafe', 'https://netsafe.org.nz/'),
           ('Need to talk?', None, 'Call or text 1737', 'https://1737.org.nz/')],
    'uk': [('In danger now?', 'Call 999.', None, None),
           ('Intimate images shared?', None, 'Revenge Porn Helpline', 'https://revengepornhelpline.org.uk/'),
           ('Need to talk?', None, 'Samaritans 116 123', 'tel:116123')],
    'us': [('In danger now?', 'Call 911.', None, None),
           ('Intimate images shared?', None, 'StopNCII', 'https://stopncii.org/'),
           ('Need to talk?', None, 'Call or text 988', 'https://988lifeline.org/')],
    'other': [('In danger now?', 'Call your local emergency number.', None, None),
              ('Intimate images shared?', None, 'StopNCII', 'https://stopncii.org/'),
              ('Need to talk?', 'Contact a local crisis line.', None, None)],
}


def safety_strip(country='au'):
    items = []
    for lead, text, link_text, href in SAFETY_SETS.get(country, SAFETY_SETS['au']):
        inner = f'<strong>{esc(lead)}</strong> '
        if text:
            inner += esc(text) + ' '
        if link_text:
            rel = '' if href.startswith('tel:') else ' rel="noopener" target="_blank"'
            inner += f'<a href="{esc(href)}"{rel}>{esc(link_text)}</a>'
        items.append(f'<span>{inner.strip()}</span>')
    first = items[0].replace('<span>', '<span>' + icon('phone'), 1)
    return f'<aside class="safety" aria-label="Urgent help" data-safety="{esc(country)}"><div class="wrap">{first}{"".join(items[1:])}</div></aside>'


HUB_LINKS = [
    ('old-news-articles', 'Old news stories'),
    ('people-search-sites', 'People-search sites'),
    ('fake-profiles', 'Fake profiles'),
    ('court-and-tribunal-records', 'Court and tribunal records'),
    ('reviews', 'Reviews'),
    ('photos-and-images', 'Photos and images'),
]


def footer():
    problems = ''.join(f'<li><a href="/help/{slug}">{label}</a></li>' for slug, label in HUB_LINKS)
    return f'''<footer class="site-footer">
<div class="wrap">
<div class="foot-grid">
<div class="foot-brand stack-sm">{LOGO}<p class="muted">Self-service help for what comes up when people search your name. We give you the plan, the letters and the links. You decide what to send, and you send it.</p></div>
<div><h2 class="foot-h">Problems</h2><ul>{problems}</ul></div>
<div><h2 class="foot-h">Tools</h2><ul>
<li><a href="/self-service">Free check and plan</a></li>
<li><a href="/self-service/tracker">My tracker</a></li>
<li><a href="/diy-action">Letter pack, US$19</a></li>
<li><a href="/name-watch-alerts">NameWatch (coming back)</a></li>
<li><a href="/learn">All guides</a></li>
</ul></div>
<div><h2 class="foot-h">Company</h2><ul>
<li><a href="/about">About and trust</a></li>
<li><a href="/how-it-works">How it works</a></li>
<li><a href="/pricing">Pricing</a></li>
<li><a href="/faq">FAQ</a></li>
<li><a href="/contact">Contact</a></li>
</ul></div>
</div>
<div class="foot-legal">
<p>{BRAND}™ is run by {COMPANY}, ABN {ABN}, South Australia. We’re not a law firm and nothing here is legal advice. We never contact publishers, platforms or Google for you, and no one can promise a result.</p>
<p><a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/terms#refunds">Refunds</a> · <a href="/billing">Billing</a> · Last reviewed {LAST_REVIEWED}</p>
</div>
</div>
</footer>'''


def document(*, title, description, canonical, robots, schema_json, tracking, body, current=None,
             desk=False, safety=None, og_image='', law_notice=True, extra_head=''):
    """Render a full HTML document in the shared shell."""
    safety_html = safety_strip(safety) if safety else ''
    return f'''<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="robots" content="{esc(robots)}">
<link rel="canonical" href="{esc(canonical)}">
<meta name="theme-color" content="#f6f4ef" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#11151a" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{BRAND}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{esc(og_image)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%231a1f24'/%3E%3Ctext x='8' y='23' font-family='Georgia,serif' font-size='19' fill='%23f6f4ef'%3EF%3C/text%3E%3Ccircle cx='23' cy='21' r='2.6' fill='%23c8343f'/%3E%3C/svg%3E">
<link rel="stylesheet" href="{asset('site.css')}">
<script type="application/ld+json">{schema_json}</script>
{tracking}{extra_head}
<script src="{asset('site.js')}" defer></script>
</head>
<body>
{sprite()}
<a class="skip" href="#main">Skip to content</a>
{LAW_NOTICE if law_notice else ''}
{header(current, desk)}
{body if body.lstrip().startswith('<main') else '<main id="main">' + body + '</main>'}
{safety_html}
{footer()}
</body>
</html>'''
