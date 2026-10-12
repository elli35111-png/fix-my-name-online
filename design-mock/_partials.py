"""Shared partials for the FMNO design mockups.

Run `python3 design-mock/_build.py` to regenerate the static pages.
The live build will move these into server.py as one SITE_HEADER / SITE_FOOTER
so the homepage, desk, guides, legal pages and personal-search pages share them.
"""

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
    'copy': '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h9"/>',
    'building': '<path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M3 21h18M8 8h3M8 12h3M8 16h3"/>',
    'nosearch': '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5M8.5 8.5l5 5"/>',
    'menu': '<path d="M4 7h16M4 12h16M4 17h16"/>',
    'bell': '<path d="M6 16v-5a6 6 0 1 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    'plus': '<path d="M12 5v14M5 12h14"/>',
    'check': '<path d="m5 12 5 5 9-10"/>',
    'info': '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    'mail': '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    'print': '<path d="M7 9V3h10v6M7 17H5a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-2"/><rect x="7" y="14" width="10" height="7" rx="1"/>',
    'pause': '<circle cx="12" cy="12" r="9"/><path d="M10 9v6M14 9v6"/>',
}


def sprite():
    syms = ''.join(f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in ICONS.items())
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true">{syms}</svg>'


def icon(name, cls='icon'):
    return f'<svg class="{cls}" aria-hidden="true"><use href="#i-{name}"/></svg>'


PROBLEMS = [
    # key, icon, tile label, tile sub, card description, who decides, guide
    ('old-news', 'news', 'An old news story', 'Out of date, wrong or missing what happened next',
     'An article that’s out of date, wrong, or leaves out what happened next.',
     'The publisher decides the page. Google decides the search result.', 'old-news-article-still-ranking-for-my-name'),
    ('people-search', 'people', 'A people-search site', 'Your address, phone, age or relatives listed',
     'Sites that list your address, phone number, age or relatives.',
     'Each site decides its listing. Google decides contact details in search.', 'help/people-search-sites'),
    ('fake-profile', 'fake', 'A fake profile', 'Someone pretending to be you',
     'An account pretending to be you, or using your name and photos.',
     'The platform decides.', 'help/fake-profile'),
    ('court', 'court', 'A court or tribunal record', 'A judgment, case listing or a copy of one',
     'A judgment, a case listing, or a copy of one on another site.',
     'The court, or the site that copied it.', 'old-court-records-showing-on-google'),
    ('review', 'star', 'A review', 'About you or your business',
     'A review about you or your business that breaks the platform’s rules.',
     'The review platform decides.', 'false-review-damaging-my-name-or-business'),
    ('images', 'image', 'Photos of you', 'Pictures posted without your OK',
     'Pictures of you posted without your OK, including intimate images.',
     'The site and Google. For intimate images, eSafety can act.', 'help/photos-and-images'),
]


HUBS = ['old-news-articles', 'people-search-sites', 'fake-profiles', 'court-and-tribunal-records', 'reviews', 'photos-and-images']


def tiles(selected=None, cols3=False, compact=False):
    out = []
    for key, ic, label, sub, *_ in PROBLEMS:
        sel = ' is-selected' if key == selected else ''
        pressed = 'true' if key == selected else 'false'
        out.append(f'<a class="tile{sel}" href="/self-service?problem={key}" aria-pressed="{pressed}">{icon(ic)}<strong>{label}</strong><span>{sub}</span></a>')
    out.append(f'<a class="tile tile-wide" href="/self-service?problem=not-sure"><strong>Something else, or I’m not sure</strong>{icon("arrow", "icon icon-sm")}</a>')
    cls = ('tiles tiles-3' if cols3 else 'tiles') + (' compact-phone' if compact else '')
    return f'<div class="{cls}">' + ''.join(out) + '</div>'


def head(title, desc):
    return f'''<!doctype html>
<html lang="en-AU">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<meta name="description" content="{desc}">
<meta name="robots" content="noindex,nofollow">
<link rel="stylesheet" href="fmno.css">
</head>
<body>
{sprite()}
<a class="skip" href="#main">Skip to content</a>
'''


def header(current=None, cta=True):
    def a(href, label, key):
        cur = ' aria-current="page"' if key == current else ''
        return f'<a href="{href}"{cur}>{label}</a>'
    nav = (a('/how-it-works', 'How it works', 'how') + a('/learn', 'Guides', 'guides') + a('/pricing', 'Pricing', 'pricing')
           + a('/about', 'About', 'about'))
    if cta:
        nav += '<a class="btn btn-primary btn-sm" href="/self-service" style="color:var(--brand-ink)">Start free check</a>'
    else:
        nav += f'<a class="btn btn-secondary btn-sm" href="/self-service/tracker">{icon("file", "icon icon-sm")} My tracker</a>'
    return f'''<header class="site-header">
  <div class="wrap">
    <a class="logo" href="/"><span class="logo-mark" aria-hidden="true">F<i>.</i></span>Fix My Name Online</a>
    <nav class="nav" aria-label="Main">{nav}</nav>
    <button class="menu-btn" aria-expanded="false" aria-controls="menu">{icon("menu", "icon icon-sm")} Menu</button>
  </div>
</header>
'''


SAFETY = f'''<aside class="safety" aria-label="Urgent help">
  <div class="wrap">
    <span>{icon("phone")}<strong>In danger now?</strong> Call 000, or your local emergency number.</span>
    <span>Threats, intimate images or a child involved? <a href="https://www.esafety.gov.au/report">Report to eSafety</a></span>
    <span>Need to talk? <a href="tel:131114">Lifeline 13 11 14</a></span>
  </div>
</aside>
'''


def footer():
    names = ['Old news stories', 'People-search sites', 'Fake profiles', 'Court and tribunal records', 'Reviews', 'Photos and images']
    probs = ''.join(f'<li><a href="/help/{h}">{n}</a></li>' for h, n in zip(HUBS, names))
    return f'''<footer class="site-footer">
  <div class="wrap">
    <div class="foot-grid">
      <div class="foot-brand stack-sm">
        <a class="logo" href="/"><span class="logo-mark" aria-hidden="true">F<i>.</i></span>Fix My Name Online</a>
        <p class="muted" style="max-width:30em">Self-service help for what comes up when people search your name. We give you the plan, the letters and the links. You decide what to send, and you send it.</p>
      </div>
      <div><h4>Problems</h4><ul>{probs}</ul></div>
      <div><h4>Tools</h4><ul>
        <li><a href="/self-service">Free check and plan</a></li>
        <li><a href="/self-service/tracker">My tracker</a></li>
        <li><a href="/diy-action">Letter pack, US$19</a></li>
        <li><a href="/name-watch-alerts">NameWatch (coming back)</a></li>
        <li><a href="/learn">All guides</a></li>
      </ul></div>
      <div><h4>Company</h4><ul>
        <li><a href="/about">About and trust</a></li>
        <li><a href="/how-it-works">How it works</a></li>
        <li><a href="/pricing">Pricing</a></li>
        <li><a href="/faq">FAQ</a></li>
        <li><a href="/contact">Contact</a></li>
      </ul></div>
    </div>
    <div class="foot-legal">
      <p>Fix My Name Online is run by Madison Jade Pty Ltd, ABN 56 661 580 936, Australia. We’re not a law firm and nothing here is legal advice. We never contact publishers, platforms or Google for you, and no one can promise a result.</p>
      <p><a href="/terms">Terms</a> · <a href="/privacy">Privacy</a> · <a href="/terms#refunds">Refunds</a> · Last reviewed 12 October 2026</p>
    </div>
  </div>
</footer>
'''


def mock_note(text):
    return f'<p class="mock-note">Design mockup · static HTML · example content only · {text}</p>\n</body>\n</html>\n'
