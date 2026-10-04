"""Shared, server-validated Free Snapshot intake; no external services."""
import html
import re

LIMITS = {'name': 160, 'email': 254, 'country_state': 160, 'authority': 32,
          'consent': 8, 'goal': 2000, 'problem_links': 2000, 'names_to_check': 500,
          'case_type': 120, 'website': 200}
AUTHORITIES = {'self': 'My own name', 'business': 'My business — I am authorised',
               'authorised': 'Someone else — I have their permission'}


def validate_snapshot(data):
    errors = {}
    for field, limit in LIMITS.items():
        if len(data.get(field, '')) > limit:
            errors[field] = 'Please shorten this field (maximum %s characters).' % limit
    name = data.get('name', '')
    if not name or re.search(r'<[^>]*>|https?://', name, re.I):
        errors['name'] = 'Enter a name or business, not a link or HTML.'
    if not re.fullmatch(r'[^\s<>@]+@[^\s<>@.]+(?:\.[^\s<>@.]+)+', data.get('email', '')):
        errors['email'] = 'Enter a valid email address.'
    if not data.get('country_state', '').strip():
        errors['country_state'] = 'Add the country and state or region so names are not confused.'
    if data.get('authority') not in AUTHORITIES:
        errors['authority'] = 'Confirm this is your name, your business, or you have permission.'
    if not data.get('goal', '').strip():
        errors['goal'] = 'Tell us the concern or exact search phrase in a sentence.'
    if data.get('consent') != 'yes':
        errors['consent'] = 'Confirm you agree to the private intake and its scope.'
    if data.get('website'):
        errors['website'] = 'Please leave the website field empty.'
    return errors


def snapshot_form_body(values=None, errors=None):
    values, errors = values or {}, errors or {}
    def esc(value):
        return html.escape(str(value or ''), quote=True)
    def value(key):
        return esc(str(values.get(key, ''))[:LIMITS.get(key, 500)])
    def attrs(key):
        return ' aria-invalid="true" aria-describedby="error-%s"' % key if key in errors else ''
    def error(key):
        return '<p class="err field-error" id="error-%s">%s</p>' % (key, esc(errors[key])) if key in errors else ''
    options = '<option value="">Choose one</option>' + ''.join(
        '<option value="%s"%s>%s</option>' % (key, ' selected' if values.get('authority') == key else '', esc(label))
        for key, label in AUTHORITIES.items())
    issue_types = ['Not sure yet', 'Old article or outdated result', 'Wrong person / name confusion', 'Private information showing online',
                   'Fake or unfair review', 'Business name / bad search results', 'Monitoring / new mentions',
                   'Threats, minors or active legal proceedings']
    issues = ''.join('<option%s>%s</option>' % (' selected' if values.get('case_type') == item else '', esc(item)) for item in issue_types)
    summary = ''
    if errors:
        summary = '<div class="recommend" role="alert" tabindex="-1" id="form-errors"><h2>Check these details</h2><ul>' + ''.join(
            '<li><a href="#snapshot-%s">%s</a></li>' % (key, esc(message)) for key, message in errors.items()) + '</ul><p>Your request has not been submitted. Your details are still below.</p></div>'
    attribution = ''.join('<input type="hidden" name="%s" value="%s">' % (key, esc(values.get(key, ''))) for key in
                          ['source_page', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid', 'fbclid'])
    return f'''
<style>
.snapshot-shell{{grid-template-columns:minmax(0,1.45fr) minmax(230px,.75fr)}}
.snapshot-shell h1{{font-size:clamp(32px,4.5vw,48px);line-height:1.08;letter-spacing:-.04em}}
.snapshot-shell .sub{{color:#bec4d3}}.snapshot-shell .microcopy{{font-size:13px;color:#aeb6c8}}
.snapshot-shell .note{{color:#b5bdce}}.snapshot-shell textarea{{min-height:100px}}
.snapshot-shell input,.snapshot-shell select,.snapshot-shell textarea{{min-width:0}}
.snapshot-shell .card,.snapshot-shell .grid>div{{min-width:0}}
.snapshot-shell .check-label{{display:flex;align-items:flex-start;gap:10px;font-size:14px;font-weight:400}}
.snapshot-shell input[type=checkbox]{{width:20px;height:20px;flex:none;margin-top:3px}}
.snapshot-hp{{position:absolute;left:-10000px;top:auto;width:1px;height:1px;overflow:hidden}}
.field-error{{font-size:13px;margin:6px 0}}.snapshot-section-title{{margin:12px 0 0;font-size:18px}}
a:focus-visible,button:focus-visible,summary:focus-visible{{outline:3px solid #ff8196;outline-offset:4px}}
@media(max-width:820px){{.snapshot-shell{{grid-template-columns:1fr}}}}
</style>
<div class="snapshot-shell"><div class="card">
<span class="pill">Free · no card required</span><h1>Your next step starts here.</h1>
<p class="sub">A bad search result can feel personal. Give your Free Search Snapshot™ enough context to point you toward a practical route — without confusing you with somebody else.</p>
<p class="note"><strong>What this is:</strong> automated guidance based on what you tell us, not a live Google search or a verified reputation score. No one is contacted for you.</p>
{summary}
<form method="post" action="/submit-snapshot" id="snapshot-form" class="grid">
{attribution}
<div class="snapshot-hp" aria-hidden="true"><label for="snapshot-website">Leave empty</label><input id="snapshot-website" name="website" tabindex="-1" autocomplete="off"></div>
<h2 class="full snapshot-section-title">1. Make sure it is the right person</h2>
<div><label for="snapshot-name">Name / business / search phrase</label><input id="snapshot-name" name="name" required maxlength="160" autocomplete="name" value="{value('name')}"{attrs('name')}>{error('name')}</div>
<div><label for="snapshot-email">Email for your request</label><input id="snapshot-email" name="email" required type="email" maxlength="254" autocomplete="email" value="{value('email')}"{attrs('email')}>{error('email')}<p class="microcopy">Your first guidance appears on screen. Save your private reference rather than relying on an email.</p></div>
<div><label for="snapshot-country_state">Country and state / region</label><input id="snapshot-country_state" name="country_state" required maxlength="160" placeholder="For example: United States, California" value="{value('country_state')}"{attrs('country_state')}>{error('country_state')}</div>
<div><label for="snapshot-authority">Who is this for?</label><select id="snapshot-authority" name="authority" required{attrs('authority')}>{options}</select>{error('authority')}</div>
<h2 class="full snapshot-section-title">2. Tell us what is worrying you</h2>
<div class="full"><label for="snapshot-case_type">Closest match</label><select id="snapshot-case_type" name="case_type">{issues}</select></div>
<div class="full"><label for="snapshot-goal">What would you like to understand or fix?</label><textarea id="snapshot-goal" name="goal" required maxlength="2000" placeholder="A short description is enough. If you have no link, include the exact search phrase and the result you mean."{attrs('goal')}>{value('goal')}</textarea>{error('goal')}<p class="microcopy">Please do not include identity documents, passwords, financial details or private records.</p></div>
<div class="full"><label for="snapshot-problem_links">Public link or result title <span class="sub">(optional)</span></label><textarea id="snapshot-problem_links" name="problem_links" maxlength="2000" placeholder="Paste a public URL, or describe the result."{attrs('problem_links')}>{value('problem_links')}</textarea>{error('problem_links')}</div>
<details class="full"><summary>Optional: add old names or another search phrase</summary><label for="snapshot-names_to_check">Other names / phrases you are authorised to include</label><textarea id="snapshot-names_to_check" name="names_to_check" maxlength="500"{attrs('names_to_check')}>{value('names_to_check')}</textarea>{error('names_to_check')}</details>
<div class="full"><label for="snapshot-consent" class="check-label"><input id="snapshot-consent" name="consent" type="checkbox" value="yes" required {'checked' if values.get('consent') == 'yes' else ''}{attrs('consent')}><span>I confirm my authority above and agree to the <a href="/privacy">Privacy Policy</a> and <a href="/terms">Terms</a>. This is automated guidance; I decide and submit any external request myself.</span></label>{error('consent')}</div>
<div class="full"><button class="btn" type="submit" id="snapshot-submit">Get my Free Snapshot →</button><p class="note">One free intake per email. No payment or public action from this form.</p></div>
</form></div>
<aside class="card side-card"><span class="pill">What you get</span><h2 style="margin-top:14px">Clarity. Then control.</h2><div class="steps">
<div class="step"><b>01 · Explain one concern</b><br><span class="sub">Location and permission help avoid same-name mistakes.</span></div>
<div class="step"><b>02 · See a suggested route</b><br><span class="sub">Based on your answers, not a claim that Google has been searched.</span></div>
<div class="step"><b>03 · Choose your next action</b><br><span class="sub">Use the free self-service checklist, explore an exact paid tool, or stop here.</span></div></div>
<div class="recommend"><h2>Prefer to work privately on your device?</h2><p class="note">Use the free self-service desk without sending an intake. Organise your evidence, record progress and export your notes.</p><a class="btn btn2" href="/self-service">Open self-service →</a></div>
<p class="note">Threats, immediate safety concerns, minors and active legal proceedings need appropriate safety or independent professional help, not a DIY request pack.</p>
<p class="microcopy">Operated by MadisonJade Pty Ltd<br>ABN 56 661 580 936<br>Private intake · no public case disclosure</p></aside></div>
<script src="/assets/snapshot-intake.js" defer></script>'''
