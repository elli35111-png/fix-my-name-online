"""Build the static FMNO design mockups: python3 design-mock/_build.py"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _partials import (PROBLEMS, HUBS, SAFETY, footer, head, header, icon,  # noqa: E402
                       mock_note, tiles)

LAW_NOTICE = f'''<div class="notice" role="note">
  <div class="wrap">{icon("info", "icon icon-sm")}<p>Came from a law firm directory? <span class="not-phone">We’re not a law firm. We’re a self-service tool you use yourself. </span><span class="only-phone">We’re a self-service tool, not a law firm. </span><a href="/about#legal-help">Need a lawyer?</a></p></div>
</div>
'''

LETTER = '''<div class="letter-body">
  <p><strong>Subject:</strong> Request to update an article about me</p>
  <p>Dear Editor,</p>
  <p>I’m writing about this article on your site:<br><span class="fill">link to the article</span><br>Headline: <span class="fill">headline</span> · Published: <span class="fill">date</span></p>
  <p>The article reports that <span class="fill">what the article says, in one sentence</span>. Since then, <span class="fill">what happened next, e.g. the charge was withdrawn on 3 May 2021</span>.</p>
  <p>I’m asking you to consider adding an update to the article so it reflects this outcome. I’ve attached <span class="fill">the court outcome, letter or other document</span>, and I’m happy to provide anything else you need to check it.</p>
  <p>The article still comes up when people search my name, and without the outcome it gives an unfair picture of what happened. I’d be grateful for a reply within 14 days.</p>
  <p>Kind regards,<br><span class="fill">your name</span><br><span class="fill">your email</span></p>
</div>'''


CARD_NAMES = ['Old news stories', 'People-search sites', 'Fake profiles', 'Court and tribunal records', 'Reviews', 'Photos and images']


def home():
    problem_cards = ''.join(
        f'''<article class="card problem">
          <div class="ico">{icon(ic)}</div>
          <h3>{name}</h3>
          <p class="muted">{desc}</p>
          <p class="who-decides"><strong>Who decides:</strong> {who}</p>
          <p class="links"><a href="/self-service?problem={key}">Start this plan →</a><a href="/help/{hub}">Read the guide</a></p>
        </article>'''
        for (key, ic, label, sub, desc, who, guide), hub, name in zip(PROBLEMS, HUBS, CARD_NAMES))

    body = head('Fix My Name Online | Deal with what shows up when people Google you',
                'Something about you shows up on Google? Get a free step-by-step plan, letters you can edit and the official forms. You send everything yourself.')
    body += LAW_NOTICE + header()
    body += f'''<main id="main">
<section class="hero">
  <div class="wrap hero-grid">
    <div class="hero-copy">
      <p class="eyebrow">Self-service · Free to start</p>
      <h1 style="margin-top:12px">Something about you shows up on Google. Here’s what you can do about it.</h1>
      <p class="lede"><span class="not-phone">Tell us what’s showing up and get a free, step-by-step plan: who decides, what to ask for, a letter you can edit, and the official forms. You send everything yourself, in your own time.</span><span class="only-phone">Get a free step-by-step plan, with a letter you can edit and the official forms. You send everything yourself.</span></p>
      <p class="facts"><span>{icon("check")}Free</span><span>{icon("check")}No account</span><span>{icon("lock")}Nothing you type is sent to us</span></p>
    </div>
    <div class="card card-raised chooser">
      <h2>What’s showing up for your name?</h2>
      <p class="meta" style="margin:4px 0 16px">Pick the closest one. You can change it later.</p>
      {tiles()}
      <p class="small" style="margin-top:14px;display:flex;gap:8px">{icon("nosearch", "icon icon-sm")}<span>We don’t search Google or give you a score. You tell us what you’ve found, and we match it to the steps that fit.</span></p>
    </div>
    <p class="who">{icon("building")}<span>Run by Madison Jade Pty Ltd · ABN 56 661 580 936 · Australia. Not a law firm.</span></p>
  </div>
</section>
{SAFETY}
<section class="section" id="how-it-works">
  <div class="wrap">
    <div class="section-head"><p class="eyebrow">How it works</p><h2>Four steps. You’re in charge of every one.</h2></div>
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
    <div class="section-head"><p class="eyebrow">Before you start</p><h2>Straight answers</h2></div>
    <div class="truths">
      <div class="truth">{icon("info")}<div><h3>Google can drop a result. Only the website can delete the page.</h3><p class="muted" style="margin-top:6px">If Google removes a link, the page still exists. The site owner is the only one who can change or delete it, so most plans start with them.</p></div></div>
      <div class="truth">{icon("clock")}<div><h3>Old isn’t always removable. Out of date often is.</h3><p class="muted" style="margin-top:6px">A story being old usually isn’t enough on its own. A story that’s wrong, or leaves out what happened next, gives you something specific to ask for.</p></div></div>
      <div class="truth">{icon("shield")}<div><h3>No one can promise a result. Including us.</h3><p class="muted" style="margin-top:6px">Publishers, platforms and Google make the decisions. Anyone who guarantees a removal is guessing. We help you ask clearly and politely.</p></div></div>
      <div class="truth">{icon("alert")}<div><h3>Some things need real help first.</h3><p class="muted" style="margin-top:6px">If you’re being threatened, a child is involved, there are intimate images, or a court case is still running, start with eSafety, the police or a lawyer. Your plan will point you to them.</p></div></div>
    </div>
  </div>
</section>
<section class="section" id="problems">
  <div class="wrap">
    <div class="section-head"><p class="eyebrow">What we cover</p><h2>Six common problems, each with its own plan</h2><p class="lede">Every plan says who decides, what to do first, and what to try if the answer is no.</p></div>
    <div class="grid grid-3">{problem_cards}</div>
  </div>
</section>
<section class="section band">
  <div class="wrap">
    <div class="section-head"><p class="eyebrow">No surprises</p><h2>See exactly what you get, before you start</h2><p class="lede">Here’s part of a sample plan for an old news story in Australia. Yours changes with your answers.</p></div>
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
        <div class="letter-fade">{LETTER}</div>
      </div>
    </div>
  </div>
</section>
<section class="section" id="pricing">
  <div class="wrap">
    <div class="section-head"><p class="eyebrow">Pricing</p><h2>Free to use. One optional extra.</h2></div>
    <div class="grid grid-3">
      <article class="card price">
        <div><h3>Free check and plan</h3><p class="amount" style="margin-top:12px">$0</p></div>
        <ul class="ticks"><li>A plan for your problem and your country</li><li>A plain letter you can edit</li><li>Links to the official forms</li><li>A tracker with check-back dates</li><li>Download or print it all</li></ul>
        <a class="btn btn-primary btn-block" href="/self-service">Start free check</a>
      </article>
      <article class="card price featured">
        <div><p class="eyebrow">Optional</p><h3 style="margin-top:6px">Letter pack for one link</h3><p class="amount" style="margin-top:12px">US$19<small>once · about A$29</small></p></div>
        <ul class="ticks"><li>Letters worded for your country’s rules, where they apply</li><li>A follow-up and a second letter for when there’s no answer</li><li>Calendar reminders for each check-back date</li><li>Saved online, with a link to get back in</li><li>Refund within 7 days if you haven’t used it</li></ul>
        <p class="small">You still check and send everything yourself. No subscription.</p>
        <a class="btn btn-secondary btn-block" href="/diy-action">See what’s in the pack</a>
      </article>
      <article class="card price" style="background:var(--surface-2)">
        <div><p class="eyebrow" style="color:var(--ink-3)">Coming back</p><h3 style="margin-top:6px">NameWatch</h3><p class="muted" style="margin-top:8px">Alerts when something new shows up for your name. We’ve paused new sign-ups while we rebuild it.</p></div>
        <p class="small">Join the waitlist and we’ll email you once when it’s back. No charge, and nothing else is sent.</p>
        <a class="btn btn-secondary btn-block" href="/name-watch-alerts#waitlist">{icon("bell", "icon icon-sm")} Join the waitlist</a>
      </article>
    </div>
    <p class="small" style="margin-top:16px">Prices are in US dollars. The Australian dollar figure is a guide only; your bank sets the final amount.</p>
  </div>
</section>
<section class="section band" id="trust">
  <div class="wrap">
    <div class="section-head"><p class="eyebrow">Who’s behind this</p><h2>A small Australian company that builds tools. We don’t act for you.</h2><p class="lede">Fix My Name Online is run by Madison Jade Pty Ltd (ABN 56 661 580 936). Here’s exactly where we stand.</p></div>
    <div class="grid grid-3">
      <div class="card"><h3>What we do</h3><ul class="ticks"><li>Plans for each kind of problem</li><li>Letters you can edit and send</li><li>Links to the official forms</li><li>A tracker so nothing slips</li></ul></div>
      <div class="card"><h3>What we don’t do</h3><ul class="ticks no"><li>Contact anyone on your behalf</li><li>Give legal advice</li><li>Promise any result</li><li>Sell or share what you type</li></ul></div>
      <div class="card"><h3>Your privacy</h3><p class="muted" style="margin-top:8px">The free check and tracker run in your browser. What you type isn’t sent to us, and there’s no analytics on those pages.</p><p style="margin-top:12px"><a href="/privacy">Read the privacy policy</a> · <a href="/about">About and trust</a></p></div>
    </div>
  </div>
</section>
<section class="section faq" id="faq">
  <div class="wrap" style="max-width:860px">
    <div class="section-head"><p class="eyebrow">Questions</p><h2>Good questions, plain answers</h2></div>
    <details open><summary>Do you search Google for my name?</summary><p>No. You tell us what you’ve found. We don’t run a search or give you a score. We match what you tell us to the steps that fit.</p></details>
    <details><summary>Is it really free?</summary><p>Yes. The check, the plan, the plain letter, the official links and the tracker are free, with no account. The only paid thing is the optional US$19 letter pack for one link.</p></details>
    <details><summary>Will you contact the website or Google for me?</summary><p>No. You send every letter and fill in every form yourself. That keeps you in control, and it’s how the official processes are set up to work.</p></details>
    <details><summary>Can you get it removed?</summary><p>We can’t promise that, and no one honestly can. The publisher, the platform or Google decides. We help you make a clear, polite, well-backed request to the right people, in the right order.</p></details>
    <details><summary>Are you lawyers?</summary><p>No. We’re a self-service tool, not a law firm, and nothing here is legal advice. If you need advice, for example about defamation, which has short time limits, talk to a lawyer. <a href="/about#legal-help">How to find one</a>.</p></details>
    <details><summary>What happens to what I type?</summary><p>On the free check and tracker, nothing leaves your browser unless you choose to save or download it. If you buy the letter pack, we store your letters so you can come back to them. The privacy policy has the details.</p></details>
  </div>
</section>
<section class="section-tight">
  <div class="wrap">
    <div class="card card-lg" style="text-align:center;background:var(--brand-soft);border-color:transparent">
      <h2>Start with what’s in front of you.</h2>
      <p class="lede" style="margin:10px auto 22px;max-width:30em">Pick what’s showing up. Your plan is ready in about two minutes.</p>
      <a class="btn btn-primary" href="/self-service">Start free check {icon("arrow", "icon icon-sm")}</a>
      <p class="small" style="margin-top:12px">Free · No account · Nothing you type is sent to us</p>
    </div>
  </div>
</section>
</main>
'''
    body += footer() + mock_note('the blue notice at the top only shows to visitors arriving from a law firm directory')
    return body


def desk_head(step, eyebrow, title, lede):
    labels = ['What’s showing up', 'A few questions', 'Your plan', 'Track it']
    items = ''.join(
        f'<li class="{"done" if i < step else ("now" if i == step else "")}"><span>{lbl}</span></li>'
        for i, lbl in enumerate(labels, 1))
    return f'''<section class="page-head">
  <div class="wrap">
    <ol class="stepper" aria-label="Progress">{items}</ol>
    <p class="step-count">Step {step} of 4 · {labels[step-1]}</p>
    <p class="eyebrow" style="margin-top:28px">{eyebrow}</p>
    <h1 style="margin-top:8px">{title}</h1>
    <p class="lede">{lede}</p>
  </div>
</section>
'''


def choice(label, on=False, small=None, box=False):
    mark = f'<span class="box{" on" if on else ""}"></span>' if box else '<span class="dot"></span>'
    sm = f'<small>{small}</small>' if small else ''
    return f'<div class="choice{" on" if on else ""}" role="{"checkbox" if box else "radio"}" aria-checked="{"true" if on else "false"}">{mark}<span>{label}{sm}</span></div>'


PRIVACY_ASIDE = f'''<div class="card stack">
  <h3 style="display:flex;gap:10px;align-items:center">{icon("lock")} Private by design</h3>
  <ul class="ticks"><li>Nothing you type here is sent to us</li><li>No analytics on this page</li><li>No name or email needed</li><li>Close the tab and it’s gone, unless you choose to save it</li></ul>
</div>'''


def desk_check():
    body = head('Free check | Fix My Name Online', 'Tell us what is showing up for your name and get a free step-by-step plan.')
    body += header(cta=False)
    body += '<main id="main">' + desk_head(2, 'Free check', 'What’s showing up for your name?',
                                           'Pick the closest one, then answer a few quick questions. Your plan comes straight after.')
    body += f'''<div class="wrap split">
  <div class="stack-lg">
    <section class="card">
      <h2 style="font:600 var(--t-lg)/1.3 var(--sans)">1. What did you find?</h2>
      <div style="margin-top:16px">{tiles(selected="old-news", cols3=True, compact=True)}</div>
    </section>
    <section class="card">
      <h2 style="font:600 var(--t-lg)/1.3 var(--sans)">2. A few questions about the news story</h2>
      <p class="meta" style="margin-top:4px">Five questions. They decide which steps and rules fit.</p>
      <div style="margin-top:24px">
        <div class="field"><span class="label">Who is the story about?</span>
          <div class="choices inline">{choice("Me", True)}{choice("Someone I’m helping", small="With their OK")}{choice("Someone with my name", small="People think it’s me")}</div></div>
        <div class="field"><label class="label" for="country">Where do you live?</label><span class="hint">This decides which laws and official routes apply.</span>
          <select class="select" id="country"><option>Australia</option><option>New Zealand</option><option>United Kingdom</option><option>European Union</option><option>United States</option><option>Canada</option><option>Somewhere else</option></select></div>
        <div class="field"><span class="label">What’s the problem with the story now?</span>
          <div class="choices">{choice("It leaves out what happened next", True, "For example, charges were dropped, you won the case, or the business changed hands")}{choice("Parts of it are wrong")}{choice("It’s accurate, but old and no longer relevant")}{choice("I’m not sure")}</div></div>
        <div class="field"><span class="label">Is the matter it describes finished?</span>
          <div class="choices inline">{choice("Yes, it’s over", True)}{choice("No, it’s still going", small="A court case or investigation is still running")}</div></div>
        <div class="field"><label class="label" for="link">Paste the link <span class="meta" style="font-weight:400">(optional)</span></label><span class="hint">It stays in this browser. We use it to fill in your letter.</span>
          <input class="input" id="link" value="https://www.example.com/news/2019/local-business-owner-charged"></div>
      </div>
    </section>
    <section class="card">
      <h2 style="font:600 var(--t-lg)/1.3 var(--sans)">3. One safety check</h2>
      <p class="meta" style="margin-top:4px">Is any of this true right now?</p>
      <div class="choices" style="margin-top:16px">{choice("Someone is threatening or harassing me", box=True)}{choice("A child is involved", box=True)}{choice("There are intimate images of me", box=True)}{choice("None of these", True, box=True)}</div>
      <div class="callout callout-info" style="margin-top:16px">{icon("info", "icon icon-sm")}<p>If any of these are true, your plan starts with the people who can act quickly, like eSafety or the police, then shows the rest of the steps.</p></div>
    </section>
    <div class="btn-row stack-phone"><a class="btn btn-primary" href="desk-2-plan.html">Show my plan {icon("arrow", "icon icon-sm")}</a><a class="btn btn-secondary" href="index.html">Back</a></div>
  </div>
  <aside class="aside stack">
    {PRIVACY_ASIDE}
    <div class="callout callout-brand">{icon("nosearch")}<p><strong>We don’t search Google.</strong>You tell us what you found, and we match it to the steps that fit. No scores, no guesses.</p></div>
  </aside>
</div>
</main>
'''
    body += footer() + mock_note('screen 1 of 3: pick the problem and answer the questions (stepper steps 1 and 2)')
    return body


def desk_plan():
    body = head('Your plan: old news story | Fix My Name Online', 'Your free step-by-step plan.')
    body += header(cta=False)
    body += '<main id="main">' + desk_head(3, 'Your plan · Old news story · Australia',
                                           'Ask the publisher to update the story, then ask Google to catch up.',
                                           'The story leaves out what happened next, so you have a clear and reasonable thing to ask for. Here’s the order to do it in.')
    body += f'''<div class="wrap split">
  <div class="stack-lg">
    <div class="grid grid-2">
      <div class="card"><p class="eyebrow">Who decides</p><p style="margin-top:8px"><strong>The publisher</strong> decides what’s on the page. <strong>Google</strong> decides what shows in search, and only updates once the page changes.</p></div>
      <div class="card"><p class="eyebrow">Time</p><p style="margin-top:8px"><strong>About 30 minutes</strong> of your time. Allow <strong>2 to 6 weeks</strong> for replies. Some publishers take longer, and some don’t reply.</p></div>
    </div>
    <div class="callout callout-warn">{icon("alert", "icon icon-sm")}<p><strong>Do these in order.</strong>Google’s refresh tool only works once the article has actually changed. Asking Google first, while the story is the same, will usually be turned down.</p></div>
    <section class="card card-lg steps-card">
      <ol class="steps">
        <li class="done"><h3>Save your evidence</h3><p class="step-meta"><span>{icon("clock", "icon icon-sm")}5 minutes</span></p>
          <ul class="checklist" style="margin-top:12px">
            <li><span class="box on"></span>The link, headline and date of the article</li>
            <li><span class="box on"></span>A screenshot with today’s date showing</li>
            <li><span class="box"></span>The words you searched when you found it</li>
            <li><span class="box"></span>Proof of what happened next, like a court outcome or letter</li>
          </ul></li>
        <li><h3>Decide what to ask for</h3><p class="step-meta"><span>{icon("clock", "icon icon-sm")}5 minutes</span></p>
          <p class="muted" style="margin:10px 0 14px">You can ask for more than one thing. Start with what matters most to you.</p>
          <div class="choices">{choice("Add an update about what happened next", True, "The smallest change you can ask for", box=True)}{choice("Remove or change my name in the story", box=True)}{choice("Stop the page showing in search engines", small="Called a “noindex” tag. The page stays, but search engines drop it.", box=True)}{choice("Take the story down", box=True)}</div></li>
        <li><h3>Send your letter to the publisher</h3><p class="step-meta"><span>{icon("clock", "icon icon-sm")}15 minutes</span><span>{icon("mail", "icon icon-sm")}You send it</span></p>
          <div class="letter" style="margin-top:14px">
            <div class="letter-bar"><strong>Free letter · Publisher update request</strong><span class="btn-row"><button class="btn btn-secondary btn-sm">{icon("copy", "icon icon-sm")} Copy</button><button class="btn btn-secondary btn-sm">{icon("download", "icon icon-sm")} Download</button></span></div>
            {LETTER}
          </div>
          <p class="meta" style="margin-top:12px"><strong>Where to send it:</strong> look for “Corrections”, “Contact the editor” or “Complaints” on the publisher’s site. Send it to one place and keep a copy.</p></li>
        <li><h3>Wait, then follow up</h3><p class="step-meta"><span>{icon("calendar", "icon icon-sm")}Check back on 28 October</span></p>
          <p class="muted" style="margin-top:8px">If there’s no reply after 14 days, send a short, polite follow-up. Your tracker will show it as due.</p></li>
        <li><h3>Once the page changes, ask Google to refresh it</h3><p class="step-meta"><span>{icon("clock", "icon icon-sm")}5 minutes</span></p>
          <p class="muted" style="margin-top:8px">Paste the same link. Google checks the live page and updates or drops the old result.</p>
          <p class="btn-row" style="margin-top:12px"><a class="btn btn-secondary btn-sm" href="https://search.google.com/search-console/remove-outdated-content">Open Google’s refresh tool {icon("ext", "icon icon-sm")}</a><a class="btn-quiet btn-sm" href="https://support.google.com/websearch/answer/6349986">How it works {icon("ext", "icon icon-sm")}</a></p></li>
        <li><h3>If the answer is no</h3>
          <ul class="ticks" style="margin-top:8px">
            <li>If the publisher belongs to the Australian Press Council, you can complain there once you’ve tried the publisher. <a href="https://www.presscouncil.org.au/">Press Council complaints {icon("ext", "icon icon-sm")}</a></li>
            <li>Australia’s privacy law generally doesn’t cover news reporting by media organisations, so a privacy complaint usually won’t fit a news story.</li>
            <li>If the story is untrue and harming you, talk to a lawyer soon. Defamation claims in Australia generally have to be started within a year of publication.</li>
          </ul></li>
      </ol>
    </section>
    <section class="card" style="display:grid;gap:14px">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline"><h3>Want more help with this one link?</h3><span class="tag">Optional · US$19 once</span></div>
      <p class="muted">The letter pack adds a follow-up letter, a second letter for when there’s no answer, calendar reminders, and saves it all online so you can come back to it. You still send everything yourself. Refund within 7 days if you haven’t used it.</p>
      <p><a href="/diy-action">See what’s in the letter pack →</a></p>
    </section>
    <div class="btn-row stack-phone"><a class="btn btn-primary" href="desk-3-tracker.html">{icon("plus", "icon icon-sm")} Add this plan to my tracker</a><button class="btn btn-secondary">{icon("print", "icon icon-sm")} Print or save as PDF</button></div>
  </div>
  <aside class="aside stack">
    <div class="card stack-sm hide-below-desk">
      <p class="eyebrow">At a glance</p>
      <p><strong>1 of 6 steps done</strong></p>
      <div style="height:6px;border-radius:6px;background:var(--line)"><div style="width:17%;height:6px;border-radius:6px;background:var(--brand)"></div></div>
      <ul class="checklist" style="margin-top:10px">
        <li><span class="box on"></span>Save your evidence</li><li><span class="box"></span>Decide what to ask for</li><li><span class="box"></span>Send your letter</li><li><span class="box"></span>Follow up</li><li><span class="box"></span>Ask Google to refresh</li><li><span class="box"></span>If the answer is no</li>
      </ul>
    </div>
    {PRIVACY_ASIDE}
  </aside>
</div>
</main>
'''
    body += footer() + mock_note('screen 2 of 3: the plan, with the free letter and official links')
    return body


def track_item(ic, title, url, chip_cls, chip, facts, nxt, btn, due=False):
    fl = ''.join(f'<div><dt>{k}</dt><dd>{v}</dd></div>' for k, v in facts)
    nx = f'<span class="due">{nxt}</span>' if due else f'<span class="muted">{nxt}</span>'
    return f'''<article class="track-item">
  <div class="track-top"><div class="track-title"><span class="ico">{icon(ic)}</span><div><h3 style="font-size:var(--t-md)">{title}</h3><p class="track-url">{url}</p></div></div><span class="chip {chip_cls}">{chip}</span></div>
  <dl class="track-facts" style="margin:0">{fl}</dl>
  <div class="track-next">{nx}{btn}</div>
</article>'''


def desk_tracker():
    body = head('My tracker | Fix My Name Online', 'Everything you are working on, in one place.')
    body += header(cta=False)
    body += '<main id="main">' + desk_head(4, 'My tracker', 'Everything you’re working on, in one place.',
                                           'Update each one as things happen. You change every status yourself. We never see this list.')
    items = (
        track_item('news', 'Old news story', 'example.com/news/2019/local-business-owner-charged', 'st-waiting', 'Waiting for a reply',
                   [('Sent to', 'The publisher’s editor'), ('Sent', '14 Oct 2026'), ('Check back', '28 Oct 2026'), ('Asked for', 'An update')],
                   'Due in 2 days: send the follow-up letter', '<a class="btn btn-primary btn-sm" href="#">Open follow-up letter</a>', due=True)
        + track_item('people', 'People-search listing', 'example-people-finder.com/au/listing', 'st-preparing', 'Preparing',
                     [('Send to', 'The site’s opt-out form'), ('Sent', 'Not yet'), ('Check back', 'Not set'), ('Asked for', 'Remove my listing')],
                     'Next: fill in the opt-out form', '<a class="btn btn-secondary btn-sm" href="#">Open the plan</a>')
        + track_item('fake', 'Fake profile', 'instagram.com/fake.account.example', 'st-sent', 'Sent by me',
                     [('Sent to', 'Instagram impersonation form'), ('Sent', '9 Oct 2026'), ('Check back', '16 Oct 2026'), ('Reference', 'Saved in notes')],
                     'Next: check the report status in the app', '<a class="btn btn-secondary btn-sm" href="#">Open the plan</a>')
        + track_item('star', 'Review on a business listing', 'Google Maps · my business', 'st-closed', 'Closed',
                     [('Sent to', 'Google review report'), ('Sent', '2 Sep 2026'), ('Answer', 'Not removed'), ('My note', 'Replied publicly instead')],
                     'You closed this on 20 Sep 2026', '<a class="btn-quiet btn-sm" href="#">Reopen</a>')
    )
    body += f'''<div class="wrap split">
  <div class="stack">
    <div style="display:flex;flex-wrap:wrap;gap:10px;justify-content:space-between;align-items:center">
      <p><strong>4 items</strong> · <span class="due">1 due this week</span></p>
      <a class="btn btn-secondary btn-sm" href="desk-1-check.html">{icon("plus", "icon icon-sm")} Add something else</a>
    </div>
    <div class="track">{items}</div>
    <details class="card" style="padding:16px 20px"><summary style="cursor:pointer;font-weight:600">What the statuses mean</summary>
      <p class="btn-row" style="margin-top:12px;gap:8px"><span class="chip st-not-started">Not started</span><span class="chip st-preparing">Preparing</span><span class="chip st-sent">Sent by me</span><span class="chip st-waiting">Waiting for a reply</span><span class="chip st-answered">Answered</span><span class="chip st-closed">Closed</span></p>
      <p class="meta" style="margin-top:10px">“Answered” means you heard back, whatever the answer was. Write what they said in your notes so you can decide the next step.</p>
    </details>
  </div>
  <aside class="aside stack">
    <div class="card stack-sm">
      <h3 style="display:flex;gap:10px;align-items:center">{icon("lock")} Saved on this browser</h3>
      <p class="meta">Your tracker lives on this device only. Anyone using this browser can see it, so don’t save it on a shared computer.</p>
      <div class="btn-row" style="margin-top:10px"><button class="btn btn-secondary btn-sm">{icon("download", "icon icon-sm")} Download a copy</button><button class="btn btn-secondary btn-sm">Restore a copy</button></div>
      <p style="margin-top:6px"><button class="btn-quiet btn-sm" style="border:0;cursor:pointer;color:var(--safe-ink)">Clear everything from this browser</button></p>
    </div>
    <div class="card stack-sm" id="waitlist" style="background:var(--surface-2)">
      <p class="eyebrow" style="color:var(--ink-3)">Coming back</p>
      <h3 style="display:flex;gap:10px;align-items:center">{icon("bell")} NameWatch</h3>
      <p class="meta">Alerts when something new shows up for your name. New sign-ups are paused while we rebuild it.</p>
      <label class="label" for="wl" style="font-size:var(--t-sm);margin-top:6px">Email me once when it’s back</label>
      <input class="input" id="wl" type="email" placeholder="you@example.com">
      <button class="btn btn-secondary btn-block btn-sm" style="margin-top:8px">Join the waitlist</button>
      <p class="small">One email when it’s back. No charge. Your email isn’t linked to this tracker.</p>
    </div>
  </aside>
</div>
</main>
'''
    body += footer() + mock_note('screen 3 of 3: the tracker. Statuses are set by the user; nothing is sent automatically')
    return body


PAGES = {'index.html': home, 'desk-1-check.html': desk_check, 'desk-2-plan.html': desk_plan, 'desk-3-tracker.html': desk_tracker}

if __name__ == '__main__':
    for name, fn in PAGES.items():
        (HERE / name).write_text(fn(), encoding='utf-8')
        print('wrote', name)
