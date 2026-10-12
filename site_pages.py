"""Page bodies for the public site, rendered inside site_shell.

Copy rules (see DESIGN.md section 1): answer first; the visitor does every
action; no promised outcomes; no scores; calm, plain Australian English.
"""
import plans
from site_shell import (ABN, BRAND, COMPANY, CONTACT_EMAIL, LAST_REVIEWED, esc, icon, safety_strip)

PROBLEMS = plans.PROBLEMS
HUB_BY_SLUG = {p['hub']: p for p in PROBLEMS}


def stack_table(html):
    """Label every cell with its column heading, so on phones each row can stack
    as the row label plus labelled values instead of scrolling sideways (and
    hiding the last column). The wrapper needs the `table-stack` class."""
    import re
    heads = [re.sub(r'<[^>]+>', '', h) for h in re.findall(r'<th>(.*?)</th>', html)]

    def row(match):
        cells = iter(range(len(heads)))
        return re.sub(r'<td>', lambda _: f'<td data-label="{esc(heads[next(cells)])}">', match.group(0))
    return re.sub(r'<tr>(?:(?!</tr>).)*?<td>.*?</tr>', row, html, flags=re.S)


def tiles(selected=None, cols3=False, compact=False, track=False):
    out = []
    for p in PROBLEMS:
        sel = ' is-selected' if p['key'] == selected else ''
        data = f' data-problem="{p["key"]}"' if track else ''
        out.append(f'<a class="tile{sel}" href="/self-service?problem={p["key"]}"{data}>{icon(p["icon"])}<strong>{esc(p["label"])}</strong><span>{esc(p["hint"])}</span></a>')
    data = ' data-problem="not-sure"' if track else ''
    out.append(f'<a class="tile tile-wide" href="/self-service?problem=not-sure"{data}><strong>Something else, or I’m not sure</strong>{icon("arrow", "icon icon-sm")}</a>')
    cls = ('tiles tiles-3' if cols3 else 'tiles') + (' compact-phone' if compact else '')
    return f'<div class="{cls}">' + ''.join(out) + '</div>'


def problem_cards():
    return ''.join(f'''<article class="card problem">
<div class="ico">{icon(p["icon"])}</div>
<h3>{esc(p["hub_title"])}</h3>
<p class="muted">{esc(p["card"])}</p>
<p class="who-decides"><strong>Who decides:</strong> {esc(p["who"])}</p>
<p class="links"><a href="/self-service?problem={p["key"]}" data-problem="{p["key"]}">Start this plan →</a><a href="/help/{p["hub"]}">Read the guide</a></p>
</article>''' for p in PROBLEMS)


def section_head(eyebrow, title, lede=''):
    lede_html = f'<p class="lede">{lede}</p>' if lede else ''
    return f'<div class="section-head"><p class="eyebrow">{eyebrow}</p><h2>{title}</h2>{lede_html}</div>'


def faq_html(items, open_first=True):
    out = []
    for i, (q, a) in enumerate(items):
        out.append(f'<details{" open" if open_first and i == 0 else ""}><summary>{esc(q)}</summary><p>{a}</p></details>')
    return ''.join(out)


def faq_schema(items, page_id):
    import re
    return {'@type': 'FAQPage', '@id': page_id + '#faq', 'mainEntity': [
        {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': re.sub(r'<[^>]+>', '', a)}} for q, a in items]}


SAMPLE_LETTER = '''<div class="letter-body">
<p><strong>Subject:</strong> Request to update an article about me</p>
<p>Dear Editor,</p>
<p>I’m writing about this article on your site:<br><span class="fill">link to the article</span><br>Headline: <span class="fill">headline</span> · Published: <span class="fill">date</span></p>
<p>The article reports that <span class="fill">what the article says, in one sentence</span>. Since then, <span class="fill">what happened next, e.g. the charge was withdrawn on 3 May 2021</span>.</p>
<p>I’m writing to ask you to add an update to the article so it reflects what happened next. I’ve attached <span class="fill">the court outcome, letter or other document</span>, and I’m happy to provide anything else you need to check it.</p>
<p>The article still comes up when people search my name, and it gives an unfair picture of where things stand now. I’d be grateful for a reply within 14 days.</p>
<p>Kind regards,<br><span class="fill">your name</span><br><span class="fill">your email</span></p>
</div>'''

HOME_FAQ = [
    ('Do you search Google for my name?', 'No. You tell us what you’ve found. We don’t run a search or give you a score. We match what you tell us to the steps that fit.'),
    ('Is it really free?', 'Yes. The check, the plan, the letters, the official links and the tracker are free, with no account. The only paid thing is the optional US$19 letter pack for one link.'),
    ('Will you contact the website or Google for me?', 'No. You send every letter and fill in every form yourself. That keeps you in control, and it’s how the official processes are set up to work.'),
    ('Can you get it removed?', 'We can’t promise that, and no one honestly can. The publisher, the platform or Google decides. We help you make a clear, polite, well-backed request to the right people, in the right order.'),
    ('Are you lawyers?', 'No. We’re a self-service tool, not a law firm, and nothing here is legal advice. If you need advice, for example about defamation, which has short time limits, talk to a lawyer. <a href="/about#legal-help">How to find one</a>.'),
    ('What happens to what I type?', 'On the free check and tracker, nothing leaves your browser unless you choose to save or download it. If you buy the letter pack, we store what you put in it so you can come back to it. The <a href="/privacy">privacy policy</a> has the details.'),
]


def price_cards(featured_cta='/diy-action'):
    return f'''<div class="grid grid-3">
<article class="card price">
<div><h3>Free check and plan</h3><p class="amount" style="margin-top:12px">$0</p></div>
<ul class="ticks"><li>A plan for your problem and your country</li><li>Letters you can edit, copy or download</li><li>Links to the official forms</li><li>A tracker with check-back dates</li><li>Print it, or save it as a PDF</li></ul>
<a class="btn btn-primary btn-block" href="/self-service">Start free check</a>
</article>
<article class="card price featured">
<div><p class="eyebrow">Optional</p><h3 style="margin-top:6px">Letter pack for one link</h3><p class="amount" style="margin-top:12px">US$19<small>once · about A$29</small></p></div>
<ul class="ticks"><li>Your request letter written out in full from a short form</li><li>A follow-up and a second letter, ready for when there’s no answer</li><li>Check-back dates and notes saved with each letter</li><li>Saved online, with an email link to get back in</li><li>Refund within 7 days if you haven’t used it</li></ul>
<p class="small">You still check and send everything yourself. No subscription.</p>
<a class="btn btn-secondary btn-block" href="{featured_cta}">See what’s in the pack</a>
</article>
<article class="card price muted-card">
<div><p class="eyebrow muted-eyebrow">Coming back</p><h3 style="margin-top:6px">NameWatch</h3><p class="muted" style="margin-top:8px">Alerts when something new shows up for your name. We’ve paused new sign-ups while we rebuild it.</p></div>
<p class="small">Join the waitlist and we’ll email you once when it’s back. No charge, and nothing else is sent.</p>
<a class="btn btn-secondary btn-block" href="/name-watch-alerts#waitlist">{icon("bell", "icon icon-sm")} Join the waitlist</a>
</article>
</div>
<p class="small" style="margin-top:16px">Prices are in US dollars. The Australian dollar figure is a guide only; your bank sets the final amount.</p>'''


def home():
    who = f'Run by {COMPANY} · ABN {ABN} · Australia. Not a law firm.'
    body = f'''<main id="main">
<section class="hero">
<div class="wrap hero-grid">
<div class="hero-copy">
<p class="eyebrow">Self-service · Free to start</p>
<h1 style="margin-top:12px">Something about you shows up on Google. Here’s what you can do about it.</h1>
<p class="lede"><span class="not-phone">Tell us what’s showing up and get a free, step-by-step plan: who decides, what to ask for, a letter you can edit, and the official forms. You send everything yourself, in your own time.</span><span class="only-phone">Get a free step-by-step plan, with a letter you can edit and the official forms. You send everything yourself.</span></p>
<p class="facts"><span>{icon("check")}Free</span><span>{icon("check")}No account</span><span>{icon("lock")}Nothing you type is sent to us</span></p>
</div>
<div class="card card-raised chooser" id="start">
<h2>What’s showing up for your name?</h2>
<p class="meta" style="margin:4px 0 16px">Pick the closest one. You can change it later.</p>
{tiles(compact=True, track=True)}
<p class="small" style="margin-top:14px;display:flex;gap:8px">{icon("nosearch", "icon icon-sm")}<span>We don’t search Google or give you a score. You tell us what you’ve found, and we match it to the steps that fit.</span></p>
</div>
<p class="who">{icon("building")}<span>{who}</span></p>
</div>
</section>
{safety_strip('au')}
<section class="section" id="how-it-works">
<div class="wrap">
{section_head('How it works', 'Four steps. You’re in charge of every one.')}
<ol class="how">
<li><h3>Tell us what you found</h3><p class="muted" style="margin-top:6px">Pick the kind of result and answer a few quick questions. No name, no email, no search.</p></li>
<li><h3>Get your plan</h3><p class="muted" style="margin-top:6px">Who decides, what to ask for, what to do first, and roughly how long each step takes.</p></li>
<li><h3>Send it yourself</h3><p class="muted" style="margin-top:6px">Edit the letter, then send it or use the official form. We never contact anyone for you.</p></li>
<li><h3>Keep track</h3><p class="muted" style="margin-top:6px">Tick off each step and set a date to check back. It all stays in your browser.</p></li>
</ol>
</div>
</section>
<section class="section band">
<div class="wrap">
{section_head('Before you start', 'Straight answers')}
<div class="truths">
<div class="truth">{icon("info")}<div><h3>Google can drop a result. Only the website can delete the page.</h3><p class="muted" style="margin-top:6px">If Google removes a link, the page still exists. The site owner is the only one who can change or delete it, so most plans start with them.</p></div></div>
<div class="truth">{icon("clock")}<div><h3>“It’s old” is a weak reason. “It’s out of date” is a specific one.</h3><p class="muted" style="margin-top:6px">A story being old usually isn’t enough on its own. A story that’s wrong, or leaves out what happened next, gives you something specific to ask the publisher to fix.</p></div></div>
<div class="truth">{icon("shield")}<div><h3>No one can promise a result. Including us.</h3><p class="muted" style="margin-top:6px">Publishers, platforms and Google make the decisions. Anyone who guarantees a removal is guessing. We help you ask clearly and politely.</p></div></div>
<div class="truth">{icon("alert")}<div><h3>Some things need real help first.</h3><p class="muted" style="margin-top:6px">If you’re being threatened, a child is involved, there are intimate images, or a court case is still running, start with eSafety, the police or a lawyer. Your plan will point you to them.</p></div></div>
</div>
</div>
</section>
<section class="section" id="problems">
<div class="wrap">
{section_head('What we cover', 'Six common problems, each with its own plan', 'Every plan says who decides, what to do first, and what to try if the answer is no.')}
<div class="grid grid-3">{problem_cards()}</div>
</div>
</section>
<section class="section band">
<div class="wrap">
{section_head('No surprises', 'See exactly what you get, before you start', 'Here’s part of a sample plan for an old news story in Australia. Yours changes with your answers.')}
<div class="sample">
<div class="card">
<p class="eyebrow">Your plan · Old news story · Australia</p>
<h3 style="margin-top:8px">Ask the publisher to update the story, then ask Google to catch up.</h3>
<ol class="steps" style="margin-top:24px">
<li class="done"><h4>Save your evidence</h4><p class="meta">The link, a dated screenshot, and proof of what happened next.</p></li>
<li><h4>Send your letter to the publisher</h4><p class="meta">Use their corrections or editor contact. Keep a copy.</p></li>
<li><h4>Wait 14 days, then follow up</h4><p class="meta">Your tracker shows when it’s due.</p></li>
<li><h4>Once the page changes, ask Google to refresh it</h4><p class="meta">Using Google’s own Refresh Outdated Content tool.</p></li>
</ol>
</div>
<div class="letter">
<div class="letter-bar"><strong>Free letter · Publisher update request</strong><span class="tag">You edit, you send</span></div>
<div class="letter-fade">{SAMPLE_LETTER}</div>
</div>
</div>
</div>
</section>
<section class="section" id="pricing">
<div class="wrap">
{section_head('Pricing', 'Free to use. One optional extra.')}
{price_cards()}
</div>
</section>
<section class="section band" id="trust">
<div class="wrap">
{section_head('Who’s behind this', 'A small Australian company that builds tools. We don’t act for you.', f'{BRAND} is run by {COMPANY} (ABN {ABN}). Here’s exactly where we stand.')}
<div class="grid grid-3">
<div class="card"><h3>What we do</h3><ul class="ticks"><li>Plans for each kind of problem</li><li>Letters you can edit and send</li><li>Links to the official forms</li><li>A tracker so nothing slips</li></ul></div>
<div class="card"><h3>What we don’t do</h3><ul class="ticks no"><li>Contact anyone on your behalf</li><li>Give legal advice</li><li>Promise any result</li><li>Sell or share what you type</li></ul></div>
<div class="card"><h3>Your privacy</h3><p class="muted" style="margin-top:8px">The free check and tracker run in your browser. What you type isn’t sent to us, and there’s no analytics on those pages.</p><p style="margin-top:12px"><a href="/privacy">Read the privacy policy</a> · <a href="/about">About and trust</a></p></div>
</div>
</div>
</section>
<section class="section faq" id="faq">
<div class="wrap" style="max-width:860px">
{section_head('Questions', 'Good questions, plain answers')}
{faq_html(HOME_FAQ)}
<p class="mt-3"><a href="/faq">More questions and answers →</a></p>
</div>
</section>
<section class="section-tight">
<div class="wrap">
<div class="card card-lg cta-card">
<h2>Start with what’s in front of you.</h2>
<p class="lede" style="margin:10px auto 22px;max-width:30em">Pick what’s showing up. Your plan is ready in about two minutes.</p>
<a class="btn btn-primary" href="/self-service">Start free check {icon("arrow", "icon icon-sm")}</a>
<p class="small" style="margin-top:12px">Free · No account · Nothing you type is sent to us</p>
</div>
</div>
</section>
</main>'''
    return body


def desk(plan_json):
    """The free check app. Server renders a fast first view; self-service.js takes over."""
    noscript_links = ''.join(f'<li><a href="/help/{p["hub"]}">{esc(p["hub_title"])}: the plan, step by step</a></li>' for p in PROBLEMS)
    return f'''<main id="main">
<div id="desk-app" aria-busy="true" aria-live="polite">
<section class="page-head"><div class="wrap">
<ol class="stepper" aria-label="Progress"><li class="now" aria-current="step"><span>What’s showing up</span></li><li><span>A few questions</span></li><li><span>Your plan</span></li><li><span>Track it</span></li></ol>
<p class="step-count">Step 1 of 4 · What’s showing up</p>
<p class="eyebrow" style="margin-top:28px">Free check</p>
<h1 style="margin-top:8px">What’s showing up for your name?</h1>
<p class="lede">Pick the closest one, then answer a few quick questions. Your plan comes straight after. It takes about two minutes.</p>
</div></section>
<div class="wrap split"><div class="stack-lg">
<section class="card"><h2 class="h-sans">1. What did you find?</h2><div class="mt-2">{tiles(cols3=True, compact=True)}</div></section>
<noscript><div class="callout callout-warn desk-noscript">{icon("info", "icon icon-sm")}<div><p><strong>The free check needs JavaScript to build your plan in your browser.</strong> Without it, each plan is also written out on its own page:</p><ul>{noscript_links}</ul></div></div></noscript>
</div>
<aside class="aside stack"><div class="card stack"><h3 class="h-icon">{icon("lock")} Private by design</h3><ul class="ticks"><li>Nothing you type here is sent to us</li><li>No analytics on this page</li><li>No name or email needed</li><li>Close the tab and it’s gone, unless you choose to save it</li></ul></div></aside>
</div>
</div>
<script type="application/json" id="plan-data">{plan_json}</script>
</main>'''


# ---------- problem hubs (/help/<slug>) ----------

HUB_INTRO = {
    'old-news-articles': ('Old news stories about you', 'An old article is the most common reason people Google themselves and wince. You can’t make a publisher change it. What you can do is ask the right person for one specific thing, in the right order, with the evidence to back it up.'),
    'people-search-sites': ('People-search sites', 'People-search and “background check” sites collect addresses, phone numbers, ages and relatives into listings. Most have an opt-out page you can use yourself. It’s tedious, and listings can come back, so it’s worth keeping a record. Google also has a form to ask it to remove your contact details from search.'),
    'fake-profiles': ('Fake profiles and impersonation', 'A fake account using your name or photos can be upsetting and, if it’s messaging people you know, urgent. Platforms take impersonation seriously, and their own report forms are the fastest route.'),
    'court-and-tribunal-records': ('Court and tribunal records', 'Court records, and copies of them on other websites, can follow people long after a matter is finished. Courts rarely change published judgments. Copies on other websites are a different matter: you can ask the site owner to remove or anonymise them, and in some places a spent-conviction scheme or a non-publication order may apply.'),
    'reviews': ('Reviews about you or your business', 'A bad review hurts, but platforms only remove reviews that break a specific rule. Knowing which rule, and replying calmly in public, does more than any amount of arguing.'),
    'photos-and-images': ('Photos of you online', 'If a photo of you is online without your OK, you can ask the site to take it down, use a copyright request if you took the photo, or use the platform’s own reporting tools. Intimate images have their own free routes, and eSafety can act quickly in Australia.'),
}

HUB_GUIDES = {
    'old-news-articles': ['how-to-get-an-old-news-article-removed-australia', 'how-to-ask-a-publisher-to-correct-an-old-article', 'how-to-request-anonymisation-from-a-news-website', 'publisher-will-not-remove-old-article', 'how-to-update-an-outdated-google-search-result', 'old-news-article-on-google', 'employer-googled-me-found-old-article'],
    'people-search-sites': ['what-shows-up-when-someone-googles-my-name', 'wrong-information-about-me-appears-on-google'],
    'fake-profiles': ['false-information-about-me-online', 'someone-posted-false-claims-about-me'],
    'court-and-tribunal-records': ['old-court-records-showing-on-google', 'old-court-article-appearing-in-google', 'background-check-found-old-article'],
    'reviews': ['false-review-damaging-my-name', 'google-review-defence'],
    'photos-and-images': ['remove-outdated-google-search-results', 'how-to-request-noindex-for-an-old-webpage'],
}


def checked_note(link_ids):
    """Say when the links shown were last checked, and name any we couldn't check."""
    links = [plans.OFFICIAL_LINKS[i] for i in dict.fromkeys(link_ids) if i in plans.OFFICIAL_LINKS]
    dates = sorted(l['checked'] for l in links if l['checked'])
    unchecked = [l['label'] for l in links if not l['checked']]
    parts = []
    if dates:
        parts.append('Official links last checked ' + plans.nice_date(dates[0]) + '.')
    if unchecked:
        names = unchecked[0] if len(unchecked) == 1 else ', '.join(unchecked[:-1]) + ' and ' + unchecked[-1]
        parts.append(f'We haven’t been able to check {names} ourselves. If {"it doesn’t" if len(unchecked) == 1 else "one doesn’t"} open the right page, search that site’s help pages instead.')
    return f'<p class="small mt-3">{esc(" ".join(parts))}</p>' if parts else ''


def link_html(link_id, primary=False):
    link = plans.OFFICIAL_LINKS[link_id]
    cls = 'btn btn-secondary btn-sm' if primary else 'btn-quiet btn-sm'
    return f'<a class="{cls}" href="{esc(link["url"])}" target="_blank" rel="noopener noreferrer">{esc(link["label"])} {icon("ext", "icon icon-sm")}<span class="sr"> (opens in a new tab)</span></a>'


def hub(slug, guide_titles):
    p = HUB_BY_SLUG[slug]
    title, intro = HUB_INTRO[slug]
    plan = plans.outline(p['key'])
    steps = []
    for step in plan['steps']:
        parts = [f'<h3>{esc(step["title"])}</h3>']
        meta = []
        if step.get('time'):
            meta.append(f'<span>{icon("clock", "icon icon-sm")}{esc(step["time"])}</span>')
        if step.get('you_send'):
            meta.append(f'<span>{icon("mail", "icon icon-sm")}You send it</span>')
        if meta:
            parts.append(f'<p class="step-meta">{"".join(meta)}</p>')
        if step.get('body'):
            parts.append(f'<p class="muted mt-1">{esc(step["body"])}</p>')
        if step.get('checklist'):
            parts.append('<ul class="ticks mt-1">' + ''.join(f'<li>{esc(c)}</li>' for c in step['checklist']) + '</ul>')
        if step.get('asks'):
            parts.append('<ul class="ticks mt-1">' + ''.join(f'<li>{esc(plans.ASKS[a]["label"])}</li>' for a in step['asks']) + '</ul>')
        if step.get('letter') and not step.get('letter_collapsed'):
            parts.append(f'<p class="meta mt-1">{icon("file", "icon icon-sm inline-icon")} Your plan includes a free letter for this step: <strong>{esc(plans.LETTERS[step["letter"]]["name"])}</strong>.</p>')
        if step.get('where'):
            parts.append(f'<p class="meta mt-1"><strong>Where to send it:</strong> {esc(step["where"])}</p>')
        if step['links']:
            parts.append('<p class="btn-row mt-2">' + ''.join(link_html(l, i == 0) for i, l in enumerate(step['links'])) + '</p>')
        steps.append('<li>' + ''.join(parts) + '</li>')
    if_no = ''.join(f'<li>{esc(i["text"])}' + (f' {link_html(i["link"])}' if i.get('link') else '') + '</li>' for i in plan['if_no'])
    steps.append(f'<li class="if-no"><h3>If the answer is no</h3><ul class="ticks mt-1">{if_no}</ul></li>')
    shown_links = [l for step in plan['steps'] for l in step['links']] + [i['link'] for i in plan['if_no'] if i.get('link')]
    guides = ''.join(f'<a href="/{esc(s)}">{esc(t)} {icon("arrow", "icon icon-sm")}</a>' for s, t in guide_titles)
    related = f'<section class="mt-4"><h2 class="h-sans">Related guides</h2><div class="related mt-2">{guides}</div></section>' if guides else ''
    other = ''.join(f'<a href="/help/{q["hub"]}">{esc(q["hub_title"])} {icon("arrow", "icon icon-sm")}</a>' for q in PROBLEMS if q['hub'] != slug)
    order = f'<div class="callout callout-warn">{icon("alert", "icon icon-sm")}<p>{esc(plan["order"])}</p></div>' if plan.get('order') else ''
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li><a href="/learn">Guides</a></li><li>{esc(p["hub_title"])}</li></ol></nav>
<p class="eyebrow" style="margin-top:20px">Problem guide · Last reviewed {LAST_REVIEWED}</p>
<h1 style="margin-top:8px">{esc(title)}</h1>
<p class="lede">{esc(intro)}</p>
</div></section>
<div class="wrap doc-grid">
<div class="stack-lg">
<div class="short"><h2>The short version</h2><p>{esc(plan["title"])} {esc(p["who"])} The free check gives you the plan for your situation and your country, with a letter you can edit.</p>
<p class="btn-row mt-2"><a class="btn btn-primary" href="/self-service?problem={p["key"]}" data-problem="{p["key"]}">Start this plan {icon("arrow", "icon icon-sm")}</a><span class="small">About two minutes · Free · Nothing you type is sent to us</span></p></div>
<div class="grid grid-2">
<div class="card"><p class="eyebrow">Who decides</p><p class="mt-1">{esc(plan["who_decides"])}</p></div>
<div class="card"><p class="eyebrow">Time</p><p class="mt-1">{esc(plan["time"])}</p></div>
</div>
{order}
<section class="card card-lg steps-card">
<p class="eyebrow">The plan, in outline</p>
<p class="meta mt-1">This is the plan for someone in Australia. The free check changes the steps, letters and official links for your answers and your country.</p>
<ol class="steps mt-3">{"".join(steps)}</ol>
{checked_note(shown_links)}
<p><a class="btn btn-secondary" href="/self-service?problem={p["key"]}" data-problem="{p["key"]}">Get this plan for your country {icon("arrow", "icon icon-sm")}</a></p>
</section>
{related}
<section class="mt-4"><h2 class="h-sans">Other problems</h2><div class="related mt-2">{other}</div></section>
</div>
<aside class="aside stack">
<div class="card stack-sm"><p class="eyebrow">Start this plan</p><h3>Get the steps for your situation</h3><p class="meta">A few questions, then your plan with letters you can edit. Free, no account, nothing sent to us.</p><a class="btn btn-primary btn-block" href="/self-service?problem={p["key"]}" data-problem="{p["key"]}">Start this plan</a></div>
<div class="callout callout-brand">{icon("nosearch")}<p><strong>We don’t search Google.</strong> You tell us what you found, and we match it to the steps that fit.</p></div>
</aside>
</div>
</main>'''


# ---------- how it works, pricing, FAQ ----------

WHO_DECIDES_TABLE = '''<div class="table-wrap table-stack prose" style="max-width:none"><table>
<thead><tr><th>Who</th><th>What they decide</th><th>What you can ask for</th></tr></thead>
<tbody>
<tr><td>The publisher or website owner</td><td>What’s on the page</td><td>An update, a correction, removing your name, a “noindex” tag, or taking it down</td></tr>
<tr><td>The platform (Facebook, Google Maps, TikTok…)</td><td>Accounts, posts and reviews, against its own rules</td><td>Removal of things that break a specific rule</td></tr>
<tr><td>Google</td><td>What shows in search results</td><td>Refreshing a result once the page has changed; removing contact details, intimate images and some other personal information</td></tr>
<tr><td>A regulator or complaints body</td><td>Complaints about members or organisations it covers</td><td>A review of how the publisher or business handled your request</td></tr>
<tr><td>A court</td><td>Its own records and any non-publication orders</td><td>Usually only through a lawyer</td></tr>
</tbody></table></div>'''


def how_it_works():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">How it works</p>
<h1 style="margin-top:8px">You do the asking. We make it clear what to ask, who to ask, and when.</h1>
<p class="lede">Fix My Name Online is a set of free tools you use yourself. Here’s what happens at each step, and what we do and don’t do.</p>
</div></section>
<section class="section-tight"><div class="wrap">
<ol class="how">
<li><h3>Tell us what you found</h3><p class="muted mt-1">Pick the kind of result: an old news story, a people-search listing, a fake profile, a court record, a review or a photo. Then answer three to five quick questions. We don’t need your name or email, and we don’t search for you.</p></li>
<li><h3>Get your plan</h3><p class="muted mt-1">Your plan says who decides, what to ask for, the order to do things in, and roughly how long each step takes. It includes a letter you can edit and the official forms for your country.</p></li>
<li><h3>Send it yourself</h3><p class="muted mt-1">You copy or download the letter and send it, or fill in the official form. We never contact a publisher, a platform or Google for you.</p></li>
<li><h3>Keep track</h3><p class="muted mt-1">Add the plan to your tracker, set a check-back date and update the status as things happen. A “no” is a normal outcome, and the plan tells you what to try next.</p></li>
</ol>
<p class="btn-row mt-3"><a class="btn btn-primary" href="/self-service">Start free check {icon("arrow", "icon icon-sm")}</a><span class="small">About two minutes · Free · No account · Nothing you type is sent to us</span></p>
</div></section>
<section class="section band"><div class="wrap">
{section_head('Who decides what', 'Knowing who decides saves weeks', 'Most wasted effort comes from asking the wrong people, or asking in the wrong order.')}
{stack_table(WHO_DECIDES_TABLE)}
</div></section>
<section class="section"><div class="wrap">
{section_head('Where we stand', 'What we do, and what we don’t')}
<div class="grid grid-2">
<div class="card"><h3>What we do</h3><ul class="ticks"><li>Give you a plan for your problem and your country</li><li>Give you letters you can edit, copy and download</li><li>Link to the official forms, and say when we last checked them</li><li>Give you a tracker that stays in your browser</li><li>Sell one optional extra: a US$19 letter pack for one link</li></ul></div>
<div class="card"><h3>What we don’t do</h3><ul class="ticks no"><li>Search Google or give you a “score”</li><li>Contact anyone on your behalf</li><li>Give legal advice, or act as your lawyer</li><li>Promise any result</li><li>Sell or share what you type</li></ul></div>
</div>
</div></section>
<section class="section band"><div class="wrap">
{section_head('Pick a problem', 'Each one has its own plan')}
{tiles(cols3=True, track=True)}
</div></section>
</main>'''


def pricing():
    rows = [
        ('A plan for your problem and country', '✓', '✓'),
        ('Letters you can edit, copy and download', '✓', '✓'),
        ('Links to the official forms', '✓', '✓'),
        ('Tracker with check-back dates', '✓ (in your browser)', '✓ (saved online)'),
        ('Letters written out in full from a short form, saved online', '', '✓'),
        ('Follow-up letter and a second letter', 'Follow-up only', '✓'),
        ('Calendar reminder files', '✓', '✓'),
        ('Get back in from another device', '', '✓ (by email link)'),
        ('Number of links', 'As many as you like', 'One'),
        ('Someone contacts the publisher for you', 'No', 'No'),
    ]
    table = ''.join(f'<tr><td>{esc(a)}</td><td>{esc(b) or "—"}</td><td>{esc(c) or "—"}</td></tr>' for a, b, c in rows)
    compare = stack_table('<div class="table-wrap table-stack prose compare" style="max-width:none"><table>\n'
                          '<thead><tr><th>What you get</th><th>Free</th><th>Letter pack, US$19</th></tr></thead>\n'
                          f'<tbody>{table}</tbody></table></div>')
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Pricing</p>
<h1 style="margin-top:8px">Free to use. One optional extra.</h1>
<p class="lede">Everything you need to act is free. The letter pack is for people who want their letters for one link saved online, with a follow-up and second letter ready to go.</p>
</div></section>
<section class="section-tight"><div class="wrap">{price_cards()}</div></section>
<section class="section band"><div class="wrap">
{section_head('Side by side', 'Free compared with the letter pack')}
{compare}
</div></section>
<section class="section"><div class="wrap prose">
<h2 id="refunds">Refunds</h2>
<p>If you buy the letter pack and haven’t created your letter yet, you can refund it yourself from your workspace within 7 days. It goes back to the card you paid with, and your bank may take a few days to show it.</p>
<p>Once you’ve created your letter, that automatic refund isn’t available. Your rights under the Australian Consumer Law still apply: if the pack doesn’t work as described, email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> and we’ll put it right or refund you.</p>
<h2>What we’ll never do</h2>
<ul><li>Sign you up for a subscription you didn’t choose</li><li>Use countdown timers or “only 2 left” pressure</li><li>Add fees at checkout that weren’t on this page</li><li>Charge you to remove anything, or promise a result for money</li></ul>
<p class="small">Prices are in US dollars because our payment account is set up that way. The Australian dollar figure is a guide only; your bank sets the final amount.</p>
</div></section>
</main>'''


FULL_FAQ = [
    ('The free check', [
        ('Do you search Google for my name?', 'No. You tell us what you’ve found. We don’t run a search or give you a score. We match what you tell us to the steps that fit.'),
        ('What does the free check include?', 'A plan for your problem and your country: who decides, what to ask for, the order to do things in, letters you can edit, the official forms, a check-back date and what to try if the answer is no. You can add it to a tracker and print or download it.'),
        ('Do I need an account?', 'No. There’s no sign-up and no email. Your plan and tracker live in your browser.'),
    ]),
    ('Letters and sending', [
        ('Will you contact the website or Google for me?', 'No. You send every letter and fill in every form yourself. That keeps you in control, and it’s how the official processes are set up to work.'),
        ('Can I change the letter?', 'Yes. Click into the letter to edit it, then copy or download it. The highlighted parts are for you to fill in.'),
        ('Can I use this for someone else?', 'Yes, if they’ve asked you to help. The letter should come from them, or include their written OK for you to write on their behalf.'),
    ]),
    ('Results and limits', [
        ('Can you get it removed?', 'We can’t promise that, and no one honestly can. The publisher, the platform or Google decides. We help you make a clear, polite, well-backed request to the right people, in the right order.'),
        ('How long does it take?', 'Usually about 30 minutes of your time. Replies often take 2 to 6 weeks, and some sites don’t reply at all. Your plan includes a follow-up step for that.'),
        ('What if they say no?', 'Every plan has an “If the answer is no” section with the next options for your country, such as a complaints body, a privacy regulator or Google’s own forms.'),
    ]),
    ('Privacy and data', [
        ('What happens to what I type?', 'On the free check and tracker, nothing leaves your browser unless you choose to save or download it. If you buy the letter pack, we store what you put in it so you can come back to it. The <a href="/privacy">privacy policy</a> has the details.'),
        ('Do you use analytics?', 'Only on our information pages, like this one, to count visits and see which pages help. There are none on the free check, the tracker, the letter pack workspace, the NameWatch page with its waitlist form, or anywhere else you type something.'),
    ]),
    ('Money', [
        ('Is it really free?', 'Yes. The check, the plan, the letters, the official links and the tracker are free. The only paid thing is the optional US$19 letter pack for one link.'),
        ('Can I get a refund?', 'If you haven’t created your letter yet, you can refund the letter pack yourself within 7 days. Your rights under the Australian Consumer Law always apply. See <a href="/pricing#refunds">refunds</a>.'),
    ]),
    ('Safety and legal help', [
        ('Are you lawyers?', 'No. We’re a self-service tool, not a law firm, and nothing here is legal advice. If you need advice, for example about defamation, which has short time limits, talk to a lawyer. <a href="/about#legal-help">How to find one</a>.'),
        ('What if I’m being threatened, or a child is involved?', 'Start with the people who can act quickly: emergency services if you’re in danger, the police, and in Australia, eSafety. The free check asks about this and puts the right help at the top of your plan.'),
    ]),
]


def faq_page():
    groups = ''.join(f'<h2 class="h-sans mt-4">{esc(name)}</h2>{faq_html(items, open_first=False)}' for name, items in FULL_FAQ)
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Questions</p>
<h1 style="margin-top:8px">Good questions, plain answers</h1>
<p class="lede">If yours isn’t here, email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We can help with the site, purchases and privacy requests, but we can’t review your case.</p>
</div></section>
<section class="section-tight faq"><div class="wrap" style="max-width:860px">{groups}</div></section>
</main>'''


def faq_items_flat():
    return [qa for _name, items in FULL_FAQ for qa in items]


# ---------- about, contact ----------

def about():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">About and trust</p>
<h1 style="margin-top:8px">A small Australian company that builds self-service tools.</h1>
<p class="lede">{BRAND} is run by {COMPANY}, ABN {ABN}, in South Australia. We make plans, letters and trackers you use yourself. We don’t act for you, and we’re not a law firm.</p>
<p class="btn-row mt-3 only-below-desk"><a class="btn btn-primary" href="/self-service">Start free check {icon("arrow", "icon icon-sm")}</a></p>
</div></section>
<div class="wrap doc-grid"><div class="prose">
<h2>Who we are</h2>
<p>{COMPANY} is an Australian private company (ABN {ABN}). You can check the ABN on the <a href="https://abr.business.gov.au/ABN/View?abn={ABN.replace(" ", "")}" rel="noopener" target="_blank">Australian Business Register</a>. You can reach us at <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
<h2>What we do</h2>
<ul><li>Plans for each kind of problem, matched to your answers and your country</li><li>Letters you can edit, copy and send yourself</li><li>Links to the official forms, and when we last checked them</li><li>A tracker that stays in your browser</li></ul>
<h2>What we don’t do</h2>
<ul><li>Search Google for you or give you a score</li><li>Contact publishers, platforms, Google or anyone else on your behalf</li><li>Give legal advice or act as your lawyer</li><li>Promise any result</li><li>Sell or share what you type</li></ul>
<h2>How we make money</h2>
<p>From one optional product: the US$19 letter pack for one link. NameWatch, our alerts service, will be paid when it comes back. We don’t sell data, we don’t take money from publishers or platforms, and there are no ads on our tools.</p>
<h2>How we write the plans</h2>
<p>Each plan is written from the official sources it links to: Google’s help pages, regulators, complaints bodies and the platforms themselves. Each official link shows the date it was last confirmed to open the right page. A few sites, such as Facebook and Instagram, block that kind of check; where a link couldn’t be confirmed, the plan says so. Every guide shows when it was last reviewed. If you spot something out of date, please tell us.</p>
<h2 id="legal-help">Need a lawyer?</h2>
<p>Some problems need legal advice, not a letter. That includes defamation (which has short time limits), anything to do with a case that’s still running, and whether a spent-conviction scheme or a non-publication order applies to you. Here’s where to start:</p>
<ul>
<li><strong>Australia:</strong> your state or territory Law Society runs a referral service. <a href="https://nationallegalaid.org.au/" target="_blank" rel="noopener">Legal Aid</a> and <a href="https://clcs.org.au/" target="_blank" rel="noopener">community legal centres</a> can help for free or at low cost.</li>
<li><strong>New Zealand:</strong> <a href="https://www.lawsociety.org.nz/for-the-public/find-a-lawyer/" target="_blank" rel="noopener">NZ Law Society: find a lawyer</a>.</li>
<li><strong>England and Wales:</strong> <a href="https://solicitors.lawsociety.org.uk/" target="_blank" rel="noopener">Law Society: find a solicitor</a>.</li>
<li><strong>Elsewhere:</strong> your local law society or bar association usually has a referral service.</li>
</ul>
<p>If you found us through a law firm directory: we’re listed there because people with these problems often look for a lawyer first. We’re a self-service tool, not a firm, and we won’t pretend otherwise.</p>
<h2>What we’ll never do</h2>
<ul><li>Claim to be a law firm</li><li>Show fake reviews or made-up numbers</li><li>Promise outcomes</li><li>Submit anything for you</li></ul>
</div>
<aside class="aside stack"><div class="card stack-sm"><p class="eyebrow">Company details</p><p><strong>{COMPANY}</strong><br>ABN {ABN}<br>South Australia, Australia</p><p><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p><p class="small">Last reviewed {LAST_REVIEWED}</p></div>
<div class="card stack-sm"><h3>Start with the free check</h3><p class="meta">Free, no account, nothing sent to us.</p><a class="btn btn-primary btn-block" href="/self-service">Start free check</a></div></aside>
</div>
</main>'''


def contact():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Contact</p>
<h1 style="margin-top:8px">Get in touch</h1>
<p class="lede">Email is the best way to reach us: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We usually reply within two business days.</p>
</div></section>
<div class="wrap"><div class="grid grid-2">
<div class="card"><h3>We can help with</h3><ul class="ticks"><li>Problems using the site or the tracker</li><li>Your letter pack purchase, access or refund</li><li>Billing for an existing NameWatch subscription</li><li>Privacy requests: access, correction or deletion</li></ul></div>
<div class="card"><h3>We can’t help with</h3><ul class="ticks no"><li>Reviewing your case or telling you what to do</li><li>Contacting a publisher, platform or Google for you</li><li>Legal advice. See <a href="/about#legal-help">how to find a lawyer</a></li></ul></div>
</div>
<div class="grid grid-3 mt-3">
<a class="card guide-link" href="/diy-action/recover"><strong>Lost your letter pack link?</strong><span>Get a new access link by email</span></a>
<a class="card guide-link" href="/billing"><strong>Billing and cancellation</strong><span>Invoices and existing subscriptions</span></a>
<a class="card guide-link" href="/faq"><strong>Questions and answers</strong><span>The common questions, answered</span></a>
</div>
<p class="small mt-3">{BRAND} is run by {COMPANY}, ABN {ABN}, South Australia. Please don’t email identity documents or passwords.</p>
</div>
</main>'''


def services():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Our tools</p>
<h1 style="margin-top:8px">Self-service tools. No agency, no retainer.</h1>
<p class="lede">Start free. If one link needs more, there’s one optional extra. Everything else on this site is free to read and use.</p>
</div></section>
<div class="wrap stack-lg">
<div class="grid grid-3">
<a class="card guide-link" href="/self-service"><strong>Free check and plan</strong><span>Answer a few questions, get a step-by-step plan with letters and official forms.</span></a>
<a class="card guide-link" href="/self-service/tracker"><strong>My tracker</strong><span>Keep every request, date and reply in one place, in your browser.</span></a>
<a class="card guide-link" href="/diy-action?source=services"><strong>Letter pack (Single Action), US$19</strong><span>Your letters for one link saved online, with a follow-up and second letter.</span></a>
<a class="card guide-link" href="/learn"><strong>Guides</strong><span>Plain-English guides to old articles, reviews, court records and more.</span></a>
<a class="card guide-link" href="/name-watch-alerts"><strong>NameWatch (coming back)</strong><span>New sign-ups are paused. Join the waitlist.</span></a>
<a class="card guide-link" href="/pricing"><strong>Pricing</strong><span>Free compared with the letter pack, and refunds.</span></a>
</div>
<p class="muted">We don’t offer managed services, retainers or anyone working on your case. You stay in charge of every step.</p>
</div>
</main>'''


# ---------- NameWatch ----------

def namewatch(message='', error=''):
    msg = f'<p class="form-msg" role="alert">{esc(error)}</p>' if error else ''
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">NameWatch · Coming back</p>
<h1 style="margin-top:8px">NameWatch is coming back.</h1>
<p class="lede">It will check regularly for new results about your name and tell you when something new appears. New sign-ups are paused while we rebuild it.</p>
</div></section>
<div class="wrap doc-grid">
<div class="stack-lg">
<div class="grid grid-2">
<div class="card"><h3>What it will do</h3><ul class="ticks"><li>Check a set of search and news sources for your name on a schedule</li><li>Tell you when it sees something it hasn’t seen before</li><li>Link straight to the free plan for that kind of result</li></ul></div>
<div class="card"><h3>What it won’t do</h3><ul class="ticks no"><li>Remove anything</li><li>Contact anyone for you</li><li>See every result: no tool can check all of Google, every image or every site</li></ul></div>
</div>
<section class="card stack" id="waitlist">
<h2 class="h-sans">{icon("bell", "icon inline-icon")} Join the waitlist</h2>
<p class="muted">Leave your email and we’ll send you one email when NameWatch is back. Nothing else, no charge, and we won’t add you to anything.</p>
{msg}
<form method="post" action="/name-watch-alerts/waitlist" class="stack" novalidate>
<label class="label" for="wl-email">Email address</label>
<input class="input" id="wl-email" name="email" type="email" autocomplete="email" maxlength="254" required inputmode="email">
<label class="check-row" for="wl-ok"><input type="checkbox" id="wl-ok" name="consent" value="yes" required><span>I’d like one email when NameWatch is back.</span></label>
<div class="honey" aria-hidden="true"><label for="wl-website">Leave this empty</label><input id="wl-website" name="website" tabindex="-1" autocomplete="off"></div>
<p><button class="btn btn-primary" type="submit">Join the waitlist</button></p>
<p class="small">We keep only your email and the date you joined. See the <a href="/privacy">privacy policy</a>. To be removed, email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
</form>
</section>
<p class="muted">Already a NameWatch customer? <a href="/billing">Manage your billing</a>. Your existing subscription isn’t affected by the pause.</p>
</div>
<aside class="aside stack"><div class="card stack-sm"><h3>In the meantime</h3><p class="meta">You can check your own name for free. Google’s “Results about you” tool can also alert you to new results showing your contact details, where it’s available.</p><a class="btn btn-primary btn-block" href="/self-service">Start free check</a><p class="small"><a href="{plans.OFFICIAL_LINKS["google-results-about-you"]["url"]}" target="_blank" rel="noopener">Google “Results about you” {icon("ext", "icon icon-sm inline-icon")}</a></p></div></aside>
</div>
</main>'''


def namewatch_thanks():
    return f'''<main id="main"><section class="status-page"><div class="wrap">
<div class="card card-lg stack"><p class="eyebrow">NameWatch waitlist</p><h1>Thanks. You’re on the list.</h1><p class="lede">We’ll send you one email when it’s back, and nothing else.</p><p class="muted">Changed your mind? Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a> and we’ll remove your address.</p><p class="btn-row"><a class="btn btn-primary" href="/self-service">Start a free check</a><a class="btn btn-secondary" href="/">Back home</a></p></div>
</div></section></main>'''


# ---------- 404 ----------

def not_found():
    return f'''<main id="main"><section class="status-page"><div class="wrap stack-lg">
<div><p class="eyebrow">Page not found</p><h1 style="margin-top:8px">That page isn’t here.</h1><p class="lede mt-2">It may have moved, or the link may be wrong. Here’s where most people want to go.</p></div>
<div class="card stack"><h2 class="h-sans">What’s showing up for your name?</h2>{tiles(cols3=True, compact=True)}</div>
<p class="btn-row"><a class="btn btn-primary" href="/">Go to the homepage</a><a class="btn btn-secondary" href="/learn">Browse the guides</a></p>
</div></section></main>'''


# ---------- Terms and Privacy ----------

def terms():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Terms of use</p>
<h1 style="margin-top:8px">Terms of use</h1>
<p class="lede">The short version: our tools help you ask for things yourself. We don’t act for you, we don’t give legal advice, and no one can promise a result. Your consumer rights always apply.</p>
<p class="meta mt-2">Effective {LAST_REVIEWED}</p>
</div></section>
<div class="wrap"><div class="prose">
<h2 id="who">1. Who we are</h2>
<p>{BRAND} (“we”, “us”) is run by {COMPANY}, ABN {ABN}, South Australia. Contact: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
<h2 id="what">2. What the service is, and isn’t</h2>
<p>We provide self-service tools and information: the free check and plans, letters you can edit, links to official forms, a tracker that runs in your browser, guides, and an optional paid letter pack. You decide whether to send anything, and you send it yourself.</p>
<p>We are not a law firm. Nothing on this site is legal advice, and using it doesn’t create a lawyer–client relationship. We don’t contact publishers, platforms, search engines or anyone else for you. Apart from NameWatch for existing subscribers (see section 6), we don’t search for information about you.</p>
<p>Publishers, platforms, Google and regulators make their own decisions. We can’t promise that anything will be removed, changed or ranked differently, and we don’t.</p>
<h2 id="your-part">3. Your part</h2>
<ul>
<li>Use the tools only for matters about you, or for someone who has asked you to help.</li>
<li>Make sure what you send is true. Don’t make false reports, impersonate anyone, or use our letters to harass or threaten.</li>
<li>Check each letter and official form before you send it. Official requirements can change; the date we last checked each link is shown next to it.</li>
<li>If you’re in danger, or a child is involved, contact emergency services or the right authority first.</li>
</ul>
<h2 id="pack">4. The letter pack (US$19)</h2>
<p>The letter pack is a one-off purchase for one link. After payment you get a private online workspace where you enter your facts and create a request letter, a follow-up letter and a second letter for that link. You can edit them, save notes and dates, download them, and add reminders to your own calendar. Once you’ve created a letter for a link, the link can’t be swapped for a different one.</p>
<p>Your workspace opens from your payment confirmation link, and stays unlocked on that browser for 24 hours. You can get a new access link by email at any time from the <a href="/diy-action/recover">recovery page</a>. Anyone with your access link can open your workspace, so keep it private. We’ll keep workspaces available while we run the service; please download a copy for your records.</p>
<p>The price is shown in US dollars before you pay. The price at checkout is the price you pay.</p>
<h2 id="refunds">5. Refunds and your consumer rights</h2>
<p>If you haven’t created a letter yet, you can refund the letter pack yourself from your workspace within 7 days of buying it. This is on top of your legal rights, not instead of them.</p>
<p>Our services come with guarantees that cannot be excluded under the Australian Consumer Law. If the letter pack doesn’t do what we said it would, or there’s a major failure, you’re entitled to a refund or another remedy. Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
<h2 id="namewatch">6. NameWatch</h2>
<p>New NameWatch sign-ups are paused. If you already subscribe, your subscription continues on its original terms: an automated search runs on a schedule for the names and phrases you gave us, and we email you when new results appear, or a short status note if there are none. It doesn’t contact anyone or remove anything. You can cancel any time through <a href="/billing">billing</a>; cancelling takes effect at the end of the period you’ve paid for. Joining the waitlist is free and doesn’t commit you to anything.</p>
<h2 id="liability">7. Our responsibility</h2>
<p>We work hard to keep plans, letters and links accurate, but the law and official processes change, and every situation is different. To the extent the law allows, we aren’t responsible for decisions made by publishers, platforms, search engines or regulators, or for loss caused by relying on general information instead of advice about your situation.</p>
<p>Where the law lets us limit our liability for a failure to meet a consumer guarantee, we limit it to supplying the service again or refunding what you paid. Nothing in these terms excludes, restricts or changes rights you have under the Australian Consumer Law or other laws that can’t be excluded.</p>
<h2 id="changes">8. Changes</h2>
<p>We may update these terms. We’ll change the effective date at the top when we do. Changes don’t affect a purchase you’ve already made.</p>
<h2 id="law">9. Governing law</h2>
<p>These terms are governed by the law of South Australia, Australia. This doesn’t take away any protection you have under the laws of the country you live in.</p>
<h2 id="contact">10. Contact</h2>
<p>{COMPANY}, ABN {ABN} · <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></p>
</div></div>
</main>'''


PRIVACY_COLLECT_TABLE = '''<div class="table-wrap table-stack" style="max-width:none"><table>
<thead><tr><th>Where</th><th>What we receive</th><th>Where it’s kept</th></tr></thead>
<tbody>
<tr><td>Free check, plans and tracker</td><td>Nothing. Your answers, links, letters and notes stay in your browser.</td><td>In your browser tab, or on your browser if you switch on “Save on this browser”. You can clear it any time.</td></tr>
<tr><td>Letter pack (paid)</td><td>Your checkout email and payment confirmation from Stripe, and what you enter in the workspace: name, country or state, the link, your facts, letters, notes, status and dates.</td><td>Our server, hosted by Render in the United States, and our backups.</td></tr>
<tr><td>NameWatch (existing subscribers only)</td><td>Your email, your sign-up record, and the names and phrases you asked us to watch. We send those names and phrases to DuckDuckGo and Google News as searches, and keep the results each check finds.</td><td>On our own computer in Australia, not on Render, with backups there. Alerts and status notes are emailed to you from admin@fixmynameonline.com. We get an internal note with counts only, not your names or results.</td></tr>
<tr><td>NameWatch waitlist</td><td>Your email address and the date you joined.</td><td>Our server, hosted by Render in the United States.</td></tr>
<tr><td>Emails you send us</td><td>Whatever you include.</td><td>Our email inbox.</td></tr>
<tr><td>Earlier tools (Free Search Snapshot and NameWatch sign-ups before October 2026)</td><td>What you entered at the time, such as your name, email, country and description.</td><td>Our server and backups, with a private link for you.</td></tr>
</tbody></table></div>'''


def privacy(ga_id=''):
    ga = f' (property {esc(ga_id)})' if ga_id else ''
    collected = stack_table(PRIVACY_COLLECT_TABLE)
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Privacy policy</p>
<h1 style="margin-top:8px">Privacy policy</h1>
<p class="lede">The short version: the free check and tracker run in your browser, and we never see what you type there. If you buy the letter pack or join a waitlist, we keep only what we need to provide it.</p>
<p class="meta mt-2">Effective {LAST_REVIEWED}</p>
</div></section>
<div class="wrap"><div class="prose">
<h2 id="who">1. Who we are</h2>
<p>{BRAND} is run by {COMPANY}, ABN {ABN}, South Australia (“we”, “us”). We handle personal information under the Australian Privacy Principles in the Privacy Act 1988. Contact: <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
<h2 id="collect">2. What we collect, tool by tool</h2>
{collected}
<p>We don’t ask for identity documents, and please don’t send them. Card details go straight to Stripe; we never see your card number.</p>
<h2 id="use">3. How we use it</h2>
<ul>
<li>To provide the letter pack: open your workspace, save your letters, and email you access and recovery links.</li>
<li>To send one email to the NameWatch waitlist when it’s back.</li>
<li>For existing NameWatch subscribers: to run the scheduled searches for the names you gave us, and email you alerts and status notes.</li>
<li>To reply to you, and to handle refunds, billing and privacy requests.</li>
<li>When a purchase completes, we get a private notification with the checkout email so we know a sale happened.</li>
<li>When someone clicks through to checkout, we record the click (the page, the time and the page they came from, plus a scrambled version of the IP address) so we can see which pages lead to purchases.</li>
</ul>
<p>We don’t sell personal information, we don’t share it for advertising, and we don’t use what you type to contact anyone.</p>
<h2 id="analytics">4. Analytics and cookies</h2>
<p>Our information pages (the homepage, guides, pricing and similar) use Google Analytics{ga} to count visits and see which pages help people. If we run advertising, those same pages may also use Meta’s (Facebook’s) measurement pixel. These tools use cookies and send data to Google or Meta.</p>
<p>Analytics see the page address, the page you came from, and general device and location information. They don’t see what you type on our tools, because there are no analytics or advertising tools on the free check, the tracker, the letter pack workspace, or the NameWatch page and its waitlist form. We don’t send which problem you pick, or anything else you choose in the free check, to Google or Meta.</p>
<p>The letter pack workspace uses one essential cookie to keep you signed in on that browser for 24 hours.</p>
<h2 id="providers">5. Who else handles it</h2>
<p>We use these providers to run the service. Some are outside Australia, so your information may be stored or processed overseas, mainly in the United States and the European Union:</p>
<ul>
<li><strong>Render</strong> (United States): hosts the website and stores letter pack and waitlist data.</li>
<li><strong>Stripe</strong>: processes payments and refunds.</li>
<li><strong>Brevo</strong> (European Union): sends workspace access and recovery emails.</li>
<li><strong>DuckDuckGo</strong> and <strong>Google News</strong> (United States): receive the names and phrases existing NameWatch subscribers asked us to watch, as search queries. They don’t receive your email address.</li>
<li><strong>Google</strong>: analytics on information pages, and our email inbox.</li>
<li><strong>Telegram</strong>: carries our private purchase notifications.</li>
</ul>
<h2 id="keep">6. How long we keep it</h2>
<ul>
<li>Free check and tracker: we never have it. It stays until you clear it, or until you close the tab if you didn’t choose to save it.</li>
<li>Letter pack: while we run the service, so you can come back to it, unless you ask us to delete it. Payment records are kept as tax law requires (generally five years in Australia).</li>
<li>NameWatch waitlist: until we send the one email, or until you ask us to remove you. After the email is sent, we delete the list.</li>
<li>Earlier tools: until you ask us to delete them, or until we no longer need them to give you access to your guidance.</li>
</ul>
<h2 id="rights">7. Your rights</h2>
<p>You can ask to see, correct or delete the personal information we hold about you. Email <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We’ll reply within 30 days. We may need to keep payment records the law requires us to keep.</p>
<h2 id="complaints">8. Complaints</h2>
<p>If you’re unhappy with how we’ve handled your information, email us first and we’ll try to fix it. If you’re still not satisfied, you can complain to the <a href="https://www.oaic.gov.au/privacy/privacy-complaints" target="_blank" rel="noopener">Office of the Australian Information Commissioner (OAIC)</a>.</p>
<h2 id="security">9. Keeping it safe</h2>
<p>Workspace data is stored on a private disk that isn’t publicly reachable, over encrypted connections. Access links work like keys: anyone with your link can open your workspace, so keep it private and don’t use a shared computer.</p>
<h2 id="changes">10. Changes</h2>
<p>If we change how we handle personal information, we’ll update this page and the effective date at the top.</p>
</div></div>
</main>'''


# ---------- guides ----------

# Guides whose slug doesn't say what they're about, mapped by hand to the plan
# that matches their content.
GUIDE_PROBLEM = {
    'online-reputation-management-for-business': 'review',
}

# "The short version" box. Problem guides use their plan's first line; guides
# that aren't about one kind of result get a summary that fits what they cover,
# instead of the general plan's line.
GUIDE_SHORT = {
    'check': 'Search your name the way a stranger would, in a private window, and write down what’s on the first page. Most of it will be fine. For anything that isn’t, save the link and a dated screenshot, then get a free plan for that one link.',
    'monitoring': 'Check your name every month or two, and set up a free alert for it. If something new turns up, save the link and a dated screenshot before you decide what, if anything, to do.',
    'business': 'Search your business the way a customer would, then sort what you find. Reviews are reported to the platform against its own rules. Old or wrong pages go to the site that runs them. Your own listings you can fix today.',
    'removal': 'There’s no single button to remove your name from Google, because Google mostly shows other people’s pages. Take one link at a time: ask the site that runs the page first, then use Google’s forms once the page has changed. Some things have their own removal forms, like contact details and intimate images.',
    'country': 'The first steps are the same in every country: save the link, ask the site that runs the page, then use Google’s forms. What changes is who can help if the answer is no, such as a privacy regulator, a press council or, in Australia, eSafety.',
    'private': 'You don’t have to tell anyone what you found to get a plan. The free check runs in your browser, and every request is one you send yourself, quietly, to the people who can change the page.',
    'false': 'Save everything before you reply. Then work out who can fix it: the site or platform that published it, and Google once the page has changed. If it’s seriously damaging, talk to a lawyer early, because defamation claims have short time limits.',
    'general': 'Take one link at a time. The site that runs a page decides what’s on it, and Google decides what shows in search, so ask the site first and then ask Google to catch up. Start by saving the link and a dated screenshot.',
}
GUIDE_THEME = {
    **dict.fromkeys(['how-to-check-your-online-reputation', 'what-shows-up-when-someone-googles-my-name',
                     'google-your-name-before-an-employer-does', 'google-your-name-before-a-job-interview',
                     'what-do-employers-see-when-they-google-me', 'online-reputation-repair-for-professionals',
                     'fix-my-search-results-before-clients-see-them'], 'check'),
    'reputation-monitoring-alerts': 'monitoring',
    'google-search-results-hurting-my-business': 'business',
    **dict.fromkeys(['can-i-remove-my-name-from-google', 'remove-my-name-from-google-search',
                     'remove-bad-google-results', 'remove-negative-google-results', 'hide-bad-google-results'], 'removal'),
    **dict.fromkeys(['online-reputation-management-australia', 'reputation-repair-australia',
                     'worldwide-reputation-repair'], 'country'),
    'private-reputation-repair': 'private',
    **dict.fromkeys(['someone-posted-false-claims-about-me-online', 'false-information-about-me-online'], 'false'),
    'fix-my-name': 'general',
}


def guide_problem(slug, text=''):
    """Which plan a guide should start. Codes only; used for /self-service?problem=…"""
    if slug in GUIDE_PROBLEM:
        return GUIDE_PROBLEM[slug]
    s = (slug + ' ' + text[:400]).lower()
    if 'review' in slug:
        return 'review'
    if 'court' in slug or 'criminal' in slug or 'charge' in slug:
        return 'court'
    if any(k in slug for k in ('people-search', 'data-broker', 'personal-information', 'address')):
        return 'people-search'
    if any(k in slug for k in ('impersonat', 'fake-profile', 'fake-account')):
        return 'fake-profile'
    if any(k in slug for k in ('photo', 'image')):
        return 'images'
    if any(k in s for k in ('article', 'news', 'publisher', 'outdated', 'old-', 'noindex', 'anonymis')):
        return 'old-news'
    return 'not-sure'


PROBLEM_BY_KEY = {p['key']: p for p in PROBLEMS}


def slugify(text):
    import re
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')[:60] or 'section'


def guide_page(*, slug, h1, eyebrow, intro, sections, faqs, related, checklist=None, problem=None, extra_top=''):
    """One template for every guide, hand-written or generated.

    sections: [(heading, text)], faqs: [(q, a)], related: [(href, title)].
    """
    problem = GUIDE_PROBLEM.get(slug) or problem or guide_problem(slug, intro)
    p = PROBLEM_BY_KEY.get(problem)
    hub_crumb = f'<li><a href="/help/{p["hub"]}">{esc(p["hub_title"])}</a></li>' if p else ''
    theme = GUIDE_THEME.get(slug) or ('' if problem in plans.PLANS else 'general')
    if theme:
        short = GUIDE_SHORT[theme]
    else:
        outline = plans.outline(problem)
        short = f'{outline["title"]} {outline["who_decides"]} Start by saving the link and a dated screenshot, then get a free plan for your situation.'
    toc_items, body = [], []
    for heading, text in sections:
        anchor = slugify(heading)
        toc_items.append(f'<li><a href="#{anchor}">{esc(heading)}</a></li>')
        body.append(f'<h2 id="{anchor}">{esc(heading)}</h2><p>{esc(text)}</p>')
    check_html = ''
    if checklist:
        check_html = '<h2 id="checklist">Checklist</h2><ul class="ticks">' + ''.join(f'<li>{esc(c)}</li>' for c in checklist) + '</ul>'
        toc_items.append('<li><a href="#checklist">Checklist</a></li>')
    faq = ''
    if faqs:
        faq = '<h2 id="questions">Questions</h2><div class="faq">' + faq_html(faqs, open_first=False) + '</div>'
        toc_items.append('<li><a href="#questions">Questions</a></li>')
    pack = ''
    if problem in ('old-news', 'court', 'images', 'people-search', 'not-sure'):
        pack = '<div class="card stack-sm"><div class="kicker-row" style="justify-content:space-between"><h3>Want your letters for one link saved online?</h3><span class="tag">Optional · US$19 once</span></div><p class="muted">The free plan has everything you need to act. The letter pack saves a request letter, a follow-up and a second letter for one link, online with your dates and notes. You still send everything yourself.</p><p><a href="/diy-action">See what’s in the letter pack →</a></p></div>'
    rel = ''.join(f'<a href="{esc(href)}">{esc(title)} {icon("arrow", "icon icon-sm")}</a>' for href, title in related)
    start_label = 'Start this plan' if p else 'Start free check'
    start_href = f'/self-service?problem={problem}'
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li><a href="/learn">Guides</a></li>{hub_crumb}</ol></nav>
<p class="eyebrow" style="margin-top:20px">{esc(eyebrow)} · Last reviewed {LAST_REVIEWED}</p>
<h1 style="margin-top:8px">{esc(h1)}</h1>
<p class="lede">{esc(intro)}</p>
</div></section>
<div class="wrap doc-grid">
<article class="prose">
<div class="short"><h2>The short version</h2><p>{esc(short)}</p></div>
<div class="card stack-sm start-card"><p class="eyebrow">Free · No account · Nothing sent to us</p><p><strong>Get the steps, letters and official forms for your situation.</strong></p><p><a class="btn btn-primary" href="{start_href}" data-problem="{problem}">{start_label} {icon("arrow", "icon icon-sm")}</a></p></div>
{extra_top}
{"".join(body)}
{check_html}
{faq}
<div class="callout callout-info">{icon("info", "icon icon-sm")}<p>Fix My Name Online is a self-service tool, not a law firm, and this isn’t legal advice. Publishers, platforms and search engines make their own decisions; no one can promise a result. <a href="/about#legal-help">Need a lawyer?</a></p></div>
{pack}
{f'<h2 id="related">Related guides</h2><div class="related">{rel}</div>' if rel else ''}
</article>
<aside class="aside stack">
<nav class="card toc hide-below-desk" aria-label="On this page"><p class="eyebrow">On this page</p><ol>{"".join(toc_items)}</ol></nav>
<div class="card stack-sm"><p class="eyebrow">{esc(p["hub_title"]) if p else "Free check"}</p><h3>{start_label}</h3><p class="meta">A few questions, then your plan with letters you can edit.</p><a class="btn btn-primary btn-block" href="{start_href}" data-problem="{problem}">{start_label}</a></div>
</aside>
</div>
</main>'''


# Acquisition pages: same URLs and search intent, rewritten in the self-serve voice.
_NO_PROMISE = ('Can anyone guarantee a result?', 'No. Publishers, platforms and Google make their own decisions. Be wary of anyone who promises a removal or a ranking for money.')
ACQUISITION = {
    'online-reputation-repair': {
        'title': 'Online Reputation Repair You Can Do Yourself',
        'eyebrow': 'Online reputation repair', 'problem': 'not-sure',
        'h1': 'Online reputation repair you can do yourself',
        'description': 'A practical, self-service approach to online reputation repair: find what’s showing up, ask the right people in the right order, and keep track. Free plan and letters.',
        'intro': 'Most of what people call “reputation repair” is asking the right person for the right thing, clearly and politely, then following up. You can do that yourself. Here’s how.',
        'sections': [
            ('Start with what people actually see', 'Search your name the way someone else would: full name, common spellings, your suburb or city, your job and your business. Note the first page of results, images and news. Save links and dated screenshots.'),
            ('Work out who decides each result', 'The website owner decides what’s on a page. A platform decides about accounts, posts and reviews. Google decides what shows in search, and mostly follows what’s on the page. Ask the person who decides.'),
            ('Ask for something specific', 'An update, a correction, removing your name, a “noindex” tag, or taking a page down. Specific, reasonable requests with evidence get further than general complaints.'),
            ('Add accurate information of your own', 'A clear profile or work page gives people searching for you something current to find. Keep it true and modest. Fake reviews or made-up pages break platform rules and can make things worse.'),
            ('Keep a record and follow up', 'Write down what you sent, when and to whom. If there’s no reply in two weeks, follow up once. A “no” is still an answer, and it tells you what to try next.'),
        ],
        'faqs': [
            ('What is online reputation repair?', 'Dealing with what shows up when people search your name: asking for outdated or wrong information to be updated or removed, reporting things that break platform rules, and making sure accurate, current information about you is easy to find.'),
            ('How long does it take?', 'Usually about 30 minutes of your time per request. Replies often take two to six weeks. Changes in Google can take longer after the page itself changes.'),
            _NO_PROMISE,
        ],
    },
    'worldwide-reputation-repair': {
        'title': 'Reputation Repair Wherever You Are: Self-Service Plans for Your Country',
        'eyebrow': 'Worldwide', 'problem': 'not-sure',
        'h1': 'Reputation repair wherever you are',
        'description': 'Free, self-service plans for what shows up when people search your name, with the official routes for Australia, New Zealand, the UK, the EU, the US and Canada.',
        'intro': 'The basic steps are the same everywhere: ask the website first, then use the official forms. What changes from country to country is which laws and complaints bodies can help if the answer is no.',
        'sections': [
            ('The same first steps everywhere', 'Save the link and a dated screenshot. Work out who runs the site. Ask them for one specific change. Follow up once if they don’t reply. Then use Google’s refresh tool once the page has changed.'),
            ('UK and EU: stronger privacy rights', 'People in the UK and EU can ask Google to stop showing some results for searches of their name, and can ask organisations to erase personal data. If they don’t answer within a month, you can complain to the data protection authority.'),
            ('Australia and New Zealand', 'Privacy law covers many businesses, including most people-search sites, but generally not news reporting. Press councils handle complaints about member publications. In Australia, eSafety can act on serious online abuse and intimate images.'),
            ('United States and Canada', 'There’s no general right to have results removed, but many people-search sites have opt-outs, some states give deletion rights, and Google will consider removing contact details and certain personal information on request.'),
        ],
        'faqs': [
            ('Does it matter where the website is based?', 'Sometimes. Privacy laws usually depend on where you live and where the business operates. Your plan uses the country you live in and points to the routes that apply.'),
            ('Can I use the free check outside Australia?', 'Yes. Pick your country in the questions and the plan changes its official links and next steps.'),
            _NO_PROMISE,
        ],
    },
    'reputation-repair-australia': {
        'title': 'Reputation Repair in Australia: What You Can Do Yourself',
        'eyebrow': 'Australia', 'problem': 'not-sure',
        'h1': 'Reputation repair in Australia: what you can do yourself',
        'description': 'What Australians can do about old articles, people-search listings, reviews and court records online: the Press Council, OAIC, eSafety and Google’s own forms. Free plan.',
        'intro': 'Australia has its own set of routes: publishers and the Press Council for news, the Privacy Act and the OAIC for businesses that hold your information, eSafety for serious online abuse, and Google’s forms for search.',
        'sections': [
            ('Old news stories', 'Ask the publisher for an update, a correction or anonymisation. If they’re a Press Council member, you can complain there after trying them. The Privacy Act generally doesn’t cover news reporting by media organisations.'),
            ('People-search and data sites', 'Businesses that trade in personal information are generally covered by the Privacy Act, whatever their size. Ask them to correct or remove your details, and complain to the OAIC if they don’t deal with it within 30 days.'),
            ('Threats, intimate images and children', 'eSafety can act quickly on serious online abuse, image-based abuse and harmful content about children. If you’re in danger, call 000.'),
            ('Court records and copies', 'Spent-conviction schemes and non-publication orders vary by state. Legal Aid and community legal centres can tell you whether one applies before you write to a site that has copied a record.'),
            ('Defamation', 'If something false is seriously harming you, talk to a lawyer soon. Claims generally have to be started within a year of publication, and most businesses with 10 or more employees can’t sue.'),
        ],
        'faqs': [
            ('Is Fix My Name Online Australian?', f'Yes. It’s run by {COMPANY}, ABN {ABN}, in South Australia. It’s a self-service tool, not a law firm.'),
            ('Can I complain to the OAIC about a news article?', 'Usually not. Media organisations are generally exempt from the Privacy Act for journalism. The Press Council or the publisher is the better route.'),
            _NO_PROMISE,
        ],
    },
    'remove-negative-google-results': {
        'title': 'Remove Negative Google Results? What’s Possible and How to Ask',
        'eyebrow': 'Negative Google results', 'problem': 'not-sure',
        'h1': 'Remove negative Google results? What’s possible, and how to ask',
        'description': 'Google rarely removes a result on its own. Here’s what it may remove, what only the website can change, and how to ask both in the right order. Free plan and letters.',
        'intro': 'Google mostly shows what’s on other people’s websites. So the most effective route is usually to get the page changed first, then ask Google to catch up. Google will also consider removing some things directly, though it decides each request.',
        'sections': [
            ('What Google may remove directly', 'Google will consider removing your contact details (phone, email, home address), intimate images shared without consent, some financial and identity information, content that breaks its policies, and, in the UK and EU, some results under privacy law. It reviews each request and can say no.'),
            ('What only the website can change', 'Everything else on the page. If an article is out of date or wrong, the publisher is the one who can update it, remove your name, add a “noindex” tag or take it down.'),
            ('Ask in the right order', 'Ask the website first. Once the page changes, use Google’s Refresh Outdated Content tool so the search result updates. Asking Google first, while the page is unchanged, is usually turned down.'),
            ('If it can’t be removed', 'Write down the answer. Then consider the complaint routes for your country, and make sure accurate, current information about you is easy to find.'),
        ],
        'faqs': [
            ('Can negative Google results be removed?', 'Some can. Many can’t, or only once the website changes the page. Your plan shows which route fits your situation.'),
            ('What should I avoid?', 'Threats, public arguments, fake reviews, fake profiles, and anyone who claims they can control Google.'),
            _NO_PROMISE,
        ],
    },
    'google-review-defence-worldwide': {
        'title': 'Google Review Problems: Report, Reply and Recover, Anywhere',
        'eyebrow': 'Google reviews', 'problem': 'review',
        'h1': 'Google review problems: report, reply and recover, wherever you are',
        'description': 'How to report a Google review that breaks the rules, write a calm public reply, and avoid the mistakes that make it worse. Free step-by-step plan.',
        'intro': 'Google only removes reviews that break a specific policy. The skill is matching the review to the right rule, reporting it with one or two facts, and replying calmly in public either way.',
        'sections': [
            ('Find the rule it breaks', 'The common ones are fake engagement (not a real experience), conflict of interest (competitors, ex-staff), off-topic content, harassment or hate, and personal information.'),
            ('Report it properly', 'Use the report option on the review, or Google’s review management tool. Keep it short and factual. Reporting the same review over and over doesn’t help.'),
            ('Reply in public', 'A calm, brief reply shows future customers how you handle problems. Don’t argue, and don’t share the reviewer’s private details.'),
            ('What not to do', 'Don’t post fake positive reviews, offer incentives for reviews, or ask people to mass-report. These break Google’s rules and, in many countries, consumer law.'),
        ],
        'faqs': [
            ('Can anyone delete a Google review for me?', 'No. Only Google can remove a review. Anyone who says they can delete reviews directly is not being straight with you.'),
            ('How long does a report take?', 'Often a few days, sometimes weeks. You can usually appeal once if it’s turned down.'),
            _NO_PROMISE,
        ],
    },
    'google-review-defence-australia': {
        'title': 'Unfair Google Reviews in Australia: What You Can Do',
        'eyebrow': 'Google reviews · Australia', 'problem': 'review',
        'h1': 'Unfair Google reviews in Australia: what you can do',
        'description': 'For Australian businesses: how to report a Google review that breaks the rules, reply calmly, and stay on the right side of consumer law. Free plan.',
        'intro': 'For an Australian business, a bad Google review is stressful. The good news is there’s a clear process, and the reply you write often matters more than the review.',
        'sections': [
            ('Check it against Google’s policies', 'Fake engagement, conflicts of interest, off-topic content, harassment and personal information are the main grounds. A real customer’s fair criticism usually stays up.'),
            ('Report and keep a record', 'Report it with a short factual note and keep a screenshot. If it’s turned down, you can usually appeal once with clearer evidence.'),
            ('Reply calmly', 'Thank them, state one fact, and offer a way to talk it through. Future customers read replies.'),
            ('Know the consumer law limits', 'Fake reviews, paying for reviews and hiding negative reviews can breach the Australian Consumer Law. Getting more honest reviews, without incentives, is the long-term fix.'),
            ('Defamation is a lawyer question', 'If a review is false and seriously harmful, get legal advice soon. In Australia most businesses with 10 or more employees can’t sue for defamation.'),
        ],
        'faqs': [
            ('Can I make Google remove a bad review?', 'No one can make Google remove a review. You can report one that breaks a policy, and Google decides.'),
            ('Is it OK to ask customers for reviews?', 'Yes, as long as you ask everyone fairly and don’t offer anything in return or only ask happy customers.'),
            _NO_PROMISE,
        ],
    },
    'google-review-defence': {
        'title': 'Fake or Unfair Google Reviews: How to Report Them and Reply',
        'eyebrow': 'Google reviews', 'problem': 'review',
        'h1': 'Fake or unfair Google reviews: how to report them and reply',
        'description': 'A step-by-step plan for fake or unfair Google reviews: find the rule it breaks, report it, reply in public, and avoid mistakes that make it worse.',
        'intro': 'A fake or unfair review can cost real customers. Here’s the process that gives you the best chance, without risking your listing.',
        'sections': [
            ('Screenshot it first', 'Save the review, the reviewer’s name and the date, plus anything that shows why it breaks a rule, like booking records.'),
            ('Match it to a policy', 'Name the rule: fake engagement, conflict of interest, off-topic, harassment or personal information. “It’s unfair” on its own isn’t a policy.'),
            ('Report it through Google', 'Use the report option on the review or Google’s review management tool. Keep it to the facts.'),
            ('Reply in public', 'A short, calm reply helps future customers see the full picture, whatever happens with the report.'),
        ],
        'faqs': [
            ('Who is this for?', 'Business owners, sole traders, clinics, trades and anyone with a Google Business Profile.'),
            ('What if Google says no?', 'You can usually appeal once with clearer evidence. If it’s false and seriously harmful, talk to a lawyer.'),
            _NO_PROMISE,
        ],
    },
    'remove-bad-google-results': {
        'title': 'Bad Google Results: What Can Be Removed and How to Ask',
        'eyebrow': 'Bad Google results', 'problem': 'not-sure',
        'h1': 'Bad Google results: what can be removed, and how to ask',
        'description': 'What you can do about bad Google results for your name: who decides, what to ask for, and the official forms. Free step-by-step plan and letters.',
        'intro': 'Bad results don’t have to be the only thing people see. Some can be removed, many can be updated, and almost all of them have someone you can ask.',
        'sections': [
            ('Work out what kind of result it is', 'An old news story, a people-search listing, a fake profile, a court record, a review or a photo each have their own route. The free check asks a few questions and picks the right one.'),
            ('Ask the person who decides', 'The website owner for the page, the platform for accounts and reviews, Google for search. Asking the right one first saves weeks.'),
            ('Be specific and keep evidence', 'Give the link, say exactly what’s wrong or out of date, and attach proof. Ask for one clear thing.'),
            ('If removal isn’t realistic', 'Record the answer, try the complaint routes for your country, and make sure accurate, current information about you is easy to find.'),
        ],
        'faqs': [
            ('Can bad Google results always be removed?', 'No. Some can, many can be updated, and some will stay. Your plan shows which routes fit.'),
            ('Is this confidential?', 'The free check runs in your browser and nothing you type is sent to us. You send any request yourself.'),
            _NO_PROMISE,
        ],
    },
    'private-reputation-repair': {
        'title': 'Private Reputation Repair: Deal With It Quietly, Yourself',
        'eyebrow': 'Private and self-service', 'problem': 'not-sure',
        'h1': 'Private reputation repair: deal with it quietly, yourself',
        'description': 'A private, self-service way to deal with what shows up for your name. The free check runs in your browser; nothing you type is sent to anyone.',
        'intro': 'You don’t need to tell anyone what you found to get a plan. The free check runs entirely in your browser, and every request is sent by you, to the people who decide.',
        'sections': [
            ('Nothing leaves your browser', 'Your answers, the link and your letters stay on your device. Close the tab and they’re gone, unless you choose to save them or download a copy.'),
            ('Quiet, specific requests', 'A polite, private letter to a publisher or site owner is often more effective than anything public. Your plan includes one you can edit.'),
            ('Don’t make it louder', 'Public arguments, angry posts and threats can create new search results. Keep it calm and keep records.'),
            ('Get help where it’s needed', 'If you’re being threatened, a child is involved, there are intimate images, or a case is still running, your plan puts the right help first.'),
        ],
        'faqs': [
            ('Who uses this?', 'Everyday people, professionals and small business owners who want to deal with what shows up for their name without hiring anyone.'),
            ('Do you see what I type?', 'No. The free check and tracker run in your browser. If you buy the letter pack, we store what you enter in it so you can come back to it.'),
            _NO_PROMISE,
        ],
    },
}


# ---------- guide index and collection pages ----------

def learn(groups, featured):
    """groups: [(title, hub_href or None, [(href, title, description)])]"""
    out = []
    for title, hub_href, items in groups:
        if not items:
            continue
        links = ''.join(f'<a class="guide-link" href="{esc(h)}" data-guide="{esc((t + " " + d).lower())}"><strong>{esc(t)}</strong><span>{esc(d)}</span></a>' for h, t, d in items)
        hub_link = f' <a class="small" href="{esc(hub_href)}">See the plan →</a>' if hub_href else ''
        out.append(f'<section class="guide-group"><h2 class="h-sans">{esc(title)}{hub_link}</h2><div class="guide-list">{links}</div></section>')
    feat = ''.join(f'<a class="guide-link" href="{esc(h)}"><strong>{esc(t)}</strong><span>{esc(d)}</span></a>' for h, t, d in featured)
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Guides</p>
<h1 style="margin-top:8px">Plain-English guides to what shows up when people search your name</h1>
<p class="lede">Grouped by problem. Each one says who decides, what you can ask for, and what to try if the answer is no.</p>
<div class="search-box mt-3">{icon("search")}<label class="sr" for="guide-search">Search the guides</label><input class="input" id="guide-search" type="search" placeholder="Search the guides, e.g. old article, review, court" autocomplete="off"></div>
</div></section>
<div class="wrap stack-lg">
<section class="card stack"><h2 class="h-sans">Start with your problem</h2>{tiles(cols3=True, compact=True, track=True)}</section>
<section class="guide-group"><h2 class="h-sans">Start here</h2><div class="guide-list">{feat}</div></section>
{"".join(out)}
<p id="guide-empty" class="muted" hidden>No guides match that. Try a shorter word, or <a href="/self-service">start the free check</a>.</p>
</div>
</main>'''


def collection(*, eyebrow, h1, lede, short, cards, problem):
    links = ''.join(f'<a class="guide-link" href="{esc(h)}"><strong>{esc(t)}</strong><span>{esc(d)}</span></a>' for h, t, d in cards)
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<nav class="crumbs" aria-label="Breadcrumb"><ol><li><a href="/">Home</a></li><li><a href="/learn">Guides</a></li></ol></nav>
<p class="eyebrow" style="margin-top:20px">{esc(eyebrow)}</p>
<h1 style="margin-top:8px">{esc(h1)}</h1>
<p class="lede">{esc(lede)}</p>
</div></section>
<div class="wrap stack-lg">
<div class="short"><h2>The short version</h2><p>{esc(short)}</p></div>
<p><a class="btn btn-primary" href="/self-service?problem={problem}" data-problem="{problem}">Start free check {icon("arrow", "icon icon-sm")}</a></p>
<div class="guide-list">{links}</div>
</div>
</main>'''


def google_your_name():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">Google your name</p>
<h1 style="margin-top:8px">Google your name. Here’s what to look for, and what to do.</h1>
<p class="lede">It’s worth doing every so often, the way an employer, a client or a landlord would. Most of what you find will be fine. For anything that isn’t, there’s usually someone you can ask.</p>
</div></section>
<div class="wrap doc-grid"><div class="prose">
<h2>How to search like someone else would</h2>
<ul><li>Use a private or incognito window, so your own history doesn’t change the results.</li><li>Search your full name, then add your suburb or city, your job, and your business name.</li><li>Check the Images and News tabs, not just the main results.</li><li>Try old names and common misspellings.</li><li>Look at the first two pages. Most people don’t go further.</li></ul>
<h2>What to look for</h2>
<ul><li>Old news stories that leave out what happened next</li><li>People-search sites listing your address, phone or relatives</li><li>Accounts pretending to be you</li><li>Court or tribunal records, or copies of them</li><li>Reviews about you or your business</li><li>Photos posted without your OK</li><li>Results about someone else with your name</li></ul>
<h2>What to do with what you find</h2>
<p>Save the link and a dated screenshot of anything that worries you. Then pick what it is in the free check. You’ll get a plan that says who decides, what to ask for, and the official forms. You send everything yourself.</p>
<p>Google’s own “Results about you” tool can also alert you to new results showing your contact details, where it’s available.</p>
</div>
<aside class="aside stack"><div class="card stack-sm"><p class="eyebrow">Found something?</p><h3>Get a plan for it</h3><p class="meta">Free, no account, nothing sent to us.</p><a class="btn btn-primary btn-block" href="/self-service">Start free check</a><a class="btn btn-secondary btn-block" href="/contact">Questions about the site</a></div></aside>
</div>
<section class="section-tight"><div class="wrap"><div class="card stack"><h2 class="h-sans">What did you find?</h2>{tiles(cols3=True, compact=True, track=True)}</div></div></section>
</main>'''


def fix_my_name_online():
    return f'''<main id="main">
<section class="page-head"><div class="wrap">
<p class="eyebrow">About the name</p>
<h1 style="margin-top:8px">Fix My Name Online</h1>
<p class="lede">{BRAND} is a set of free, self-service tools for dealing with what shows up when people search your name: old news stories, people-search listings, fake profiles, court records, reviews and photos.</p>
</div></section>
<div class="wrap doc-grid"><div class="prose">
<div class="callout callout-info">{icon("info", "icon icon-sm")}<p><strong>Looking to change your legal name?</strong> Fix My Name Online does not process legal name changes, passports, licences or identity documents. Those belong with your government’s registry. This site is about what people see when they search your name online.</p></div>
<h2>What “fix my name online” means here</h2>
<p>It means giving you what you need to deal with a search result yourself: who decides, what to ask for, a letter you can edit, the official forms, and a tracker. It doesn’t mean anyone does it for you, and it doesn’t mean a result is guaranteed.</p>
<h2>How it works</h2>
<ol><li><strong>Tell us what you found.</strong> Pick the kind of result and answer a few questions. No name, no email, no search.</li><li><strong>Get your plan.</strong> Steps in order, with times, letters and official links for your country.</li><li><strong>Send it yourself.</strong> We never contact anyone for you.</li><li><strong>Keep track.</strong> Set a check-back date and record the answer.</li></ol>
<h2>Who runs it</h2>
<p>{BRAND} is run by {COMPANY} (ABN {ABN}) in South Australia. The website is fixmynameonline.com. People sometimes search for it as “Fix My Name On Line”; that’s the same site. It isn’t a law firm. See <a href="/about">about and trust</a>.</p>
<h2>Questions</h2>
<div class="faq">{faq_html(FIX_FAQ, open_first=False)}</div>
</div>
<aside class="aside stack"><div class="card stack-sm"><h3>Start with the free check</h3><p class="meta">About two minutes. Nothing you type is sent to us.</p><a class="btn btn-primary btn-block" href="/self-service">Start free check</a><a class="btn btn-secondary btn-block" href="/diy-action">See the US$19 letter pack</a></div></aside>
</div>
</main>'''


FIX_FAQ = [
    ('Is Fix My Name Online a legal name-change service?', 'No. It deals with what shows up when people search your name online. Legal name changes are handled by your government’s registry.'),
    ('Can every bad result be removed?', 'No. What’s possible depends on the source, the facts, the platform’s rules and the law where you live. Your plan shows the routes that fit.'),
    ('Does it work outside Australia?', 'Yes. Pick your country in the free check and the plan changes its official links and next steps.'),
    ('What should I do first?', 'Save the link and a dated screenshot of what you found, then start the free check.'),
]
