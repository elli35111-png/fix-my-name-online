"""Plan content for the free check, the problem pages and the tracker.

One source of truth:
- the desk (assets/self-service.js) reads this as JSON and builds each plan in
  the browser from the visitor's answers (nothing is sent to the server);
- /help/<slug> pages render the default plan outline server-side;
- tests check every official link has a last-checked date.

Conditions (`when`) are {question_id: [allowed values]}. All keys must match.
Everything here is plain text. The browser inserts it with textContent.
"""
import json

LAST_CHECKED = '2026-10-12'

COUNTRIES = [
    ('au', 'Australia'), ('nz', 'New Zealand'), ('uk', 'United Kingdom'), ('eu', 'European Union or EEA'),
    ('us', 'United States'), ('ca', 'Canada'), ('other', 'Somewhere else'),
]

# Official links. `checked` is the date the URL was opened and returned the
# expected page. None = could not be confirmed from here (blocks automated
# checks); see the handover notes. Never invent a URL.
_C = LAST_CHECKED
OFFICIAL_LINKS = {
    'google-refresh-tool': {'label': 'Google’s Refresh Outdated Content tool', 'url': 'https://search.google.com/search-console/remove-outdated-content', 'by': 'Google', 'checked': _C},
    'google-refresh-help': {'label': 'How Google’s refresh tool works', 'url': 'https://support.google.com/websearch/answer/6349986', 'by': 'Google', 'checked': _C},
    'google-removal-overview': {'label': 'Google: remove information from Search', 'url': 'https://support.google.com/websearch/answer/11080680', 'by': 'Google', 'checked': _C},
    'google-personal-info': {'label': 'Google: remove contact details and personal info', 'url': 'https://support.google.com/websearch/answer/9673730', 'by': 'Google', 'checked': _C},
    'google-results-about-you': {'label': 'Google “Results about you”', 'url': 'https://support.google.com/websearch/answer/12719076', 'by': 'Google', 'checked': _C},
    'google-eu-privacy-form': {'label': 'Google’s EU and UK privacy removal form', 'url': 'https://reportcontent.google.com/forms/rtbf', 'by': 'Google', 'checked': _C},
    'google-eu-privacy-help': {'label': 'Google: right to be forgotten overview', 'url': 'https://support.google.com/legal/answer/10769224', 'by': 'Google', 'checked': _C},
    'google-intimate-images': {'label': 'Google: remove personal sexual content', 'url': 'https://support.google.com/websearch/answer/16305143', 'by': 'Google', 'checked': _C},
    'google-copyright-help': {'label': 'Google: report a copyright problem', 'url': 'https://support.google.com/legal/answer/3110420', 'by': 'Google', 'checked': _C},
    'google-copyright-form': {'label': 'Google’s copyright removal form (Search)', 'url': 'https://reportcontent.google.com/forms/dmca_search', 'by': 'Google', 'checked': _C},
    'google-review-report': {'label': 'Google: report a review', 'url': 'https://support.google.com/business/answer/4596773', 'by': 'Google', 'checked': _C},
    'google-review-policy': {'label': 'Google Maps: prohibited content policy', 'url': 'https://support.google.com/contributionpolicy/answer/7400114', 'by': 'Google', 'checked': _C},
    'press-council': {'label': 'Australian Press Council complaints', 'url': 'https://www.presscouncil.org.au/complaints/', 'by': 'Australian Press Council', 'checked': _C},
    'acma': {'label': 'ACMA complaints (TV and radio)', 'url': 'https://www.acma.gov.au/complaints', 'by': 'ACMA', 'checked': _C},
    'oaic-complaint': {'label': 'OAIC: make a privacy complaint', 'url': 'https://www.oaic.gov.au/privacy/privacy-complaints', 'by': 'OAIC', 'checked': _C},
    'oaic-your-info': {'label': 'OAIC: your personal information', 'url': 'https://www.oaic.gov.au/privacy/your-privacy-rights/your-personal-information', 'by': 'OAIC', 'checked': _C},
    'esafety-report': {'label': 'eSafety: make a report', 'url': 'https://www.esafety.gov.au/report', 'by': 'eSafety Commissioner', 'checked': _C},
    'esafety-iba': {'label': 'eSafety: image-based abuse', 'url': 'https://www.esafety.gov.au/key-topics/image-based-abuse', 'by': 'eSafety Commissioner', 'checked': _C},
    'reportcyber': {'label': 'ReportCyber (scams and identity misuse)', 'url': 'https://www.cyber.gov.au/report-and-recover/report', 'by': 'Australian Signals Directorate', 'checked': _C},
    'idcare': {'label': 'IDCARE (identity support, AU and NZ)', 'url': 'https://www.idcare.org/', 'by': 'IDCARE', 'checked': _C},
    'nz-media-council': {'label': 'NZ Media Council', 'url': 'https://www.mediacouncil.org.nz/', 'by': 'NZ Media Council', 'checked': _C},
    'nz-privacy': {'label': 'NZ Privacy Commissioner', 'url': 'https://www.privacy.org.nz/', 'by': 'Office of the Privacy Commissioner', 'checked': _C},
    'netsafe': {'label': 'Netsafe', 'url': 'https://netsafe.org.nz/', 'by': 'Netsafe', 'checked': None},
    'ipso': {'label': 'IPSO (UK press complaints)', 'url': 'https://www.ipso.co.uk/', 'by': 'IPSO', 'checked': None},
    'impress': {'label': 'IMPRESS (UK press complaints)', 'url': 'https://www.impressorg.com/', 'by': 'IMPRESS', 'checked': _C},
    'ico-complaint': {'label': 'ICO: make a complaint', 'url': 'https://ico.org.uk/make-a-complaint/', 'by': 'Information Commissioner’s Office', 'checked': _C},
    'uk-rph': {'label': 'Revenge Porn Helpline', 'url': 'https://revengepornhelpline.org.uk/', 'by': 'Revenge Porn Helpline', 'checked': _C},
    'edpb-members': {'label': 'Find your EU data protection authority', 'url': 'https://www.edpb.europa.eu/about-edpb/our-members_en', 'by': 'EDPB', 'checked': _C},
    'cppa': {'label': 'California Privacy Protection Agency', 'url': 'https://cppa.ca.gov/', 'by': 'CPPA', 'checked': _C},
    'stopncii': {'label': 'StopNCII.org', 'url': 'https://stopncii.org/', 'by': 'StopNCII', 'checked': _C},
    'opc-canada': {'label': 'Office of the Privacy Commissioner of Canada', 'url': 'https://www.priv.gc.ca/', 'by': 'OPC', 'checked': _C},
    'ca-media-council': {'label': 'National NewsMedia Council (Canada)', 'url': 'https://www.mediacouncil.ca/', 'by': 'NNC', 'checked': _C},
    'facebook-impersonation': {'label': 'Facebook: report an impersonation account', 'url': 'https://www.facebook.com/help/174210519303259', 'by': 'Meta', 'checked': None},
    'instagram-impersonation': {'label': 'Instagram: report impersonation', 'url': 'https://help.instagram.com/370054663112398', 'by': 'Meta', 'checked': None},
    'x-impersonation': {'label': 'X: report impersonation', 'url': 'https://help.x.com/en/forms/authenticity/impersonation', 'by': 'X', 'checked': None},
    'tiktok-impersonation': {'label': 'TikTok: report an impersonation account', 'url': 'https://support.tiktok.com/en/safety-hc/report-a-problem/report-an-impersonation-account', 'by': 'TikTok', 'checked': _C},
    'linkedin-impersonation': {'label': 'LinkedIn: report a fake profile', 'url': 'https://www.linkedin.com/help/linkedin/answer/a1338436', 'by': 'LinkedIn', 'checked': _C},
    'spokeo-optout': {'label': 'Spokeo opt-out', 'url': 'https://www.spokeo.com/optout', 'by': 'Spokeo', 'checked': _C},
    'legal-aid-au': {'label': 'Legal Aid (Australia)', 'url': 'https://nationallegalaid.org.au/', 'by': 'National Legal Aid', 'checked': _C},
    'clcs-au': {'label': 'Community legal centres (Australia)', 'url': 'https://clcs.org.au/', 'by': 'Community Legal Centres Australia', 'checked': _C},
    'uk-find-solicitor': {'label': 'Law Society: find a solicitor (England and Wales)', 'url': 'https://solicitors.lawsociety.org.uk/', 'by': 'The Law Society', 'checked': _C},
    'nz-find-lawyer': {'label': 'NZ Law Society: find a lawyer', 'url': 'https://www.lawsociety.org.nz/for-the-public/find-a-lawyer/', 'by': 'NZ Law Society', 'checked': _C},
}

PROBLEMS = [
    {'key': 'old-news', 'icon': 'news', 'label': 'An old news story', 'hint': 'Out of date, wrong or missing what happened next',
     'card': 'An article that’s out of date, wrong, or leaves out what happened next.',
     'who': 'The publisher decides the page. Google decides the search result.', 'hub': 'old-news-articles', 'hub_title': 'Old news stories'},
    {'key': 'people-search', 'icon': 'people', 'label': 'A people-search site', 'hint': 'Your address, phone, age or relatives listed',
     'card': 'Sites that list your address, phone number, age or relatives.',
     'who': 'Each site decides its listing. Google decides contact details in search.', 'hub': 'people-search-sites', 'hub_title': 'People-search sites'},
    {'key': 'fake-profile', 'icon': 'fake', 'label': 'A fake profile', 'hint': 'Someone pretending to be you',
     'card': 'An account pretending to be you, or using your name and photos.',
     'who': 'The platform decides.', 'hub': 'fake-profiles', 'hub_title': 'Fake profiles'},
    {'key': 'court', 'icon': 'court', 'label': 'A court or tribunal record', 'hint': 'A judgment, case listing or a copy of one',
     'card': 'A judgment, a case listing, or a copy of one on another site.',
     'who': 'The court, or the site that copied it.', 'hub': 'court-and-tribunal-records', 'hub_title': 'Court and tribunal records'},
    {'key': 'review', 'icon': 'star', 'label': 'A review', 'hint': 'About you or your business',
     'card': 'A review about you or your business that breaks the platform’s rules.',
     'who': 'The review platform decides.', 'hub': 'reviews', 'hub_title': 'Reviews'},
    {'key': 'images', 'icon': 'image', 'label': 'Photos of you', 'hint': 'Pictures posted without your OK',
     'card': 'Pictures of you posted without your OK, including intimate images.',
     'who': 'The site and Google. For intimate images, eSafety can act.', 'hub': 'photos-and-images', 'hub_title': 'Photos and images'},
]
PROBLEM_KEYS = [p['key'] for p in PROBLEMS] + ['not-sure', 'general']

_WHO = {'id': 'who', 'label': 'Who is it about?', 'options': [
    {'value': 'me', 'label': 'Me'},
    {'value': 'helping', 'label': 'Someone I’m helping', 'small': 'With their OK'},
    {'value': 'same-name', 'label': 'Someone with my name', 'small': 'People think it’s me'}]}
_STATUS = {'id': 'status', 'label': 'Is the matter it describes finished?', 'options': [
    {'value': 'finished', 'label': 'Yes, it’s over'},
    {'value': 'ongoing', 'label': 'No, it’s still going', 'small': 'A court case or investigation is still running'},
    {'value': 'unsure', 'label': 'I’m not sure'}]}

QUESTIONS = {
    'old-news': [
        _WHO,
        {'id': 'now', 'label': 'What’s the problem with the story now?', 'stack': True, 'options': [
            {'value': 'left-out', 'label': 'It leaves out what happened next', 'small': 'For example, charges were dropped, you won the case, or the business changed hands'},
            {'value': 'wrong', 'label': 'Parts of it are wrong'},
            {'value': 'old', 'label': 'It’s accurate, but old and no longer relevant'},
            {'value': 'unsure', 'label': 'I’m not sure'}]},
        _STATUS,
    ],
    'court': [
        _WHO,
        {'id': 'where', 'label': 'Where is it showing?', 'stack': True, 'options': [
            {'value': 'copy', 'label': 'On another website that copied it', 'small': 'A blog, a directory or a “court records” site'},
            {'value': 'news', 'label': 'In a news story about the case'},
            {'value': 'court-site', 'label': 'On the court’s own website or a law database'},
            {'value': 'unsure', 'label': 'I’m not sure'}]},
        _STATUS,
    ],
    'people-search': [
        {'id': 'who', 'label': 'Who is it about?', 'options': [
            {'value': 'me', 'label': 'Me'},
            {'value': 'helping', 'label': 'Someone I’m helping', 'small': 'With their OK'}]},
        {'id': 'listed', 'label': 'What does the listing show?', 'stack': True, 'options': [
            {'value': 'address', 'label': 'My home address'},
            {'value': 'contact', 'label': 'My phone number or email'},
            {'value': 'other', 'label': 'My age, relatives or past addresses'}]},
        {'id': 'sites', 'label': 'How many sites have you found?', 'options': [
            {'value': 'one', 'label': 'One'},
            {'value': 'several', 'label': 'Several'}]},
    ],
    'fake-profile': [
        {'id': 'platform', 'label': 'Where is the fake profile?', 'options': [
            {'value': 'facebook', 'label': 'Facebook'}, {'value': 'instagram', 'label': 'Instagram'},
            {'value': 'tiktok', 'label': 'TikTok'}, {'value': 'x', 'label': 'X (Twitter)'},
            {'value': 'linkedin', 'label': 'LinkedIn'}, {'value': 'other', 'label': 'Somewhere else'}]},
        {'id': 'doing', 'label': 'What is it doing?', 'stack': True, 'options': [
            {'value': 'existing', 'label': 'Just existing, using my name or photos'},
            {'value': 'contacting', 'label': 'Messaging people I know', 'small': 'For example, asking for money or sending links'},
            {'value': 'posting', 'label': 'Posting things that make me look bad'}]},
    ],
    'review': [
        {'id': 'about', 'label': 'Who is the review about?', 'options': [
            {'value': 'business', 'label': 'My business'},
            {'value': 'me', 'label': 'Me personally'}]},
        {'id': 'platform', 'label': 'Where is it?', 'options': [
            {'value': 'google', 'label': 'Google (Maps or Business Profile)'},
            {'value': 'other', 'label': 'Another site or app'}]},
        {'id': 'why', 'label': 'What’s wrong with it?', 'stack': True, 'options': [
            {'value': 'not-customer', 'label': 'They were never a customer', 'small': 'Or it describes something that didn’t happen'},
            {'value': 'conflict', 'label': 'It’s from a competitor, an ex-employee or someone with a grudge'},
            {'value': 'offensive', 'label': 'It’s abusive, hateful or shares personal details'},
            {'value': 'unfair', 'label': 'It’s a real customer, but it’s unfair'}]},
    ],
    'images': [
        {'id': 'whose', 'label': 'Who took the photo?', 'options': [
            {'value': 'mine', 'label': 'I did', 'small': 'A photo you took yourself, like a selfie'},
            {'value': 'other', 'label': 'Someone else'}]},
        {'id': 'where', 'label': 'Where is it?', 'options': [
            {'value': 'website', 'label': 'On a website'},
            {'value': 'social', 'label': 'On social media'}]},
    ],
    'not-sure': [
        {'id': 'where', 'label': 'Where did you find it?', 'stack': True, 'options': [
            {'value': 'news', 'label': 'A news site or blog'},
            {'value': 'listing', 'label': 'A site that lists people'},
            {'value': 'social', 'label': 'Social media'},
            {'value': 'review', 'label': 'A review site'},
            {'value': 'court', 'label': 'A court or legal site'},
            {'value': 'other', 'label': 'Another kind of website'}]},
        {'id': 'wrong', 'label': 'What’s the main problem?', 'stack': True, 'options': [
            {'value': 'wrong', 'label': 'It’s wrong or out of date'},
            {'value': 'private', 'label': 'It shows private details'},
            {'value': 'not-me', 'label': 'It’s about someone else with my name'},
            {'value': 'fake', 'label': 'Someone’s pretending to be me'}]},
        # Asked only when the page can describe a case or investigation about the
        # visitor. A question with `when` is shown (and required) only if it matches.
        dict(_STATUS, when={'where': ['news', 'court'], 'wrong': ['wrong', 'private']}),
    ],
}
# Every problem also asks for the country and a safety check (added by the desk).

# Help-first cards. Shown at the top of a plan when a safety box is ticked.
HELP_FIRST = {
    'threat': {
        'title': 'Start with the people who can act quickly',
        'text': 'If you’re in danger right now, call emergency services. For threats or harassment online, report it to the police and, in Australia, to eSafety. Save screenshots first, but don’t reply to the person.',
        'au': ['esafety-report'], 'nz': ['netsafe'], 'uk': [], 'eu': [], 'us': [], 'ca': [], 'other': [],
        'numbers': {'au': 'Emergency 000 · Police non-urgent 131 444', 'nz': 'Emergency 111 · Police non-urgent 105', 'uk': 'Emergency 999 · Police non-urgent 101', 'eu': 'Emergency 112', 'us': 'Emergency 911', 'ca': 'Emergency 911', 'other': 'Your local emergency number'},
    },
    'child': {
        'title': 'A child is involved: get help first',
        'text': 'Content about a child should be reported straight away. In Australia, eSafety can act quickly on serious online abuse of a child. Elsewhere, report it to the platform and the police.',
        'au': ['esafety-report'], 'nz': ['netsafe'], 'uk': [], 'eu': [], 'us': [], 'ca': [], 'other': [],
        'numbers': {'au': 'Emergency 000', 'nz': 'Emergency 111', 'uk': 'Emergency 999', 'eu': 'Emergency 112', 'us': 'Emergency 911', 'ca': 'Emergency 911', 'other': 'Your local emergency number'},
    },
    'intimate': {
        'title': 'Intimate images: there are fast, free ways to act',
        'text': 'The fastest routes don’t need a letter. In Australia, eSafety can order intimate images taken down. Google has its own removal form, and StopNCII can help stop the images being shared on major platforms.',
        'au': ['esafety-iba', 'google-intimate-images', 'stopncii'], 'nz': ['netsafe', 'google-intimate-images', 'stopncii'],
        'uk': ['uk-rph', 'google-intimate-images', 'stopncii'], 'eu': ['google-intimate-images', 'stopncii'],
        'us': ['google-intimate-images', 'stopncii'], 'ca': ['google-intimate-images', 'stopncii'], 'other': ['google-intimate-images', 'stopncii'],
        'numbers': {},
    },
    'ongoing': {
        'title': 'Talk to a lawyer before you ask for anything',
        'text': 'While a case or investigation is still running, a request to a publisher or a court can affect it. Keep your evidence for now, and get advice before you contact anyone. Legal Aid and community legal centres can help if cost is a worry.',
        'au': ['legal-aid-au', 'clcs-au'], 'nz': ['nz-find-lawyer'], 'uk': ['uk-find-solicitor'], 'eu': [], 'us': [], 'ca': [], 'other': [],
        'numbers': {},
    },
    # Shown when the visitor isn't sure the matter is finished. The steps stay,
    # because it may well be over, but the advice comes first.
    'status-unsure': {
        'title': 'Not sure it’s finished? Talk to a lawyer before you ask for anything',
        'text': 'If a court case or investigation might still be running, a request to a publisher or a court can affect it. Check with your lawyer, the court or Legal Aid before you send anything. Community legal centres can help if cost is a worry. Once you know it’s finished, the steps below are ready.',
        'au': ['legal-aid-au', 'clcs-au'], 'nz': ['nz-find-lawyer'], 'uk': ['uk-find-solicitor'], 'eu': [], 'us': [], 'ca': [], 'other': [],
        'numbers': {},
    },
}

# Letters. Paragraphs can carry `when`. {{key|label}} is a fill-in field.
# {{link}} is filled from the link the visitor pasted (kept in the browser).
# {{ask}} is built from the choices in the "decide" step.
LETTERS = {
    'L1': {'name': 'Publisher update request', 'paras': [
        {'text': 'Subject: Request to update an article about me'},
        {'text': 'Dear Editor,'},
        {'text': 'I’m writing about this article on your site:\n{{link|link to the article}}\nHeadline: {{headline|headline}} · Published: {{date|date}}'},
        {'when': {'now': ['left-out', 'unsure']}, 'text': 'The article reports that {{says|what the article says, in one sentence}}. Since then, {{next|what happened next, e.g. the charge was withdrawn on 3 May 2021}}.'},
        {'when': {'now': ['wrong']}, 'text': 'The article says {{says|what the article says that’s wrong}}. That isn’t correct. {{fact|what actually happened, in one or two sentences}}.'},
        {'when': {'now': ['outdated']}, 'text': 'The article says {{says|what the article says, in one sentence}}. That isn’t accurate now. {{fact|what’s wrong, or what has changed since, in one or two sentences}}.'},
        {'when': {'now': ['old']}, 'text': 'The article was published {{years|how many}} years ago. It’s about {{says|what it’s about, in one sentence}}, and it’s no longer relevant to my life or my work.'},
        {'text': '{{ask}}'},
        {'text': 'I’ve attached {{evidence|the court outcome, letter or other document}}, and I’m happy to provide anything else you need to check it.'},
        {'text': 'The article still comes up when people search my name, and it gives an unfair picture of where things stand now. I’d be grateful for a reply within 14 days.'},
        {'when': {'who': ['helping']}, 'text': '[Note: send this from the person it’s about, or include their written OK for you to write on their behalf.]'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|your email}}'},
    ]},
    'L1C': {'name': 'Request to a site that copied a court record', 'paras': [
        {'text': 'Subject: Request about a court record on your site'},
        {'text': 'Hello,'},
        {'text': 'Your site shows a copy of a court record that names me:\n{{link|link to the page}}'},
        {'when': {'status': ['finished']}, 'text': 'The case was in {{year|year}} and it’s finished. {{outcome|the outcome, if it helps, e.g. the charge was dismissed}}.'},
        {'when': {'status': ['ongoing', 'unsure']}, 'text': 'The case was in {{year|year}}.'},
        {'text': '{{ask}}'},
        {'text': 'The page comes up when people search my name. I’d be grateful for a reply within 14 days.'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|your email}}'},
    ]},
    'L2': {'name': 'Listing removal request', 'paras': [
        {'text': 'Subject: Request to remove my personal information'},
        {'text': 'Hello,'},
        {'text': 'Your site lists my personal information here:\n{{link|link to the listing}}'},
        {'text': 'The listing shows {{details|what it shows, e.g. my home address, phone number and relatives}}. I didn’t agree to this being published.'},
        {'text': 'Please remove this listing and any other listings about me, stop publishing my information, and tell me where you got it from.'},
        {'text': 'Please confirm once it’s done. I’d be grateful for a reply within 30 days.'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|an email address you don’t mind them having}}'},
    ]},
    'L3F': {'name': 'Wording for the platform’s report form', 'paras': [
        {'text': 'This account is pretending to be me:\n{{link|link to the fake account}}'},
        {'text': 'My real account is {{real|link to your real account, if you have one}}. The fake account uses my {{uses|name and photos}} without my permission.'},
        {'when': {'doing': ['contacting']}, 'text': 'It is messaging people I know and {{harm|what it’s asking for, e.g. asking for money}}.'},
        {'when': {'doing': ['posting']}, 'text': 'It is posting things in my name that I didn’t write.'},
        {'text': 'Please remove the account. I can confirm my identity through your official process.'},
    ]},
    'L3R': {'name': 'Wording for the review report', 'paras': [
        {'text': 'This review breaks your policy on {{policy|which policy, e.g. fake engagement or conflict of interest}}.'},
        {'text': 'Review: {{link|link to the review}}\nPosted: {{date|date}} by {{reviewer|reviewer name}}'},
        {'when': {'why': ['not-customer']}, 'text': 'We have no record of this person as a customer. {{detail|one factual detail, e.g. we were closed on the date they describe}}.'},
        {'when': {'why': ['conflict']}, 'text': 'The reviewer is {{relationship|their relationship to us, e.g. a former employee}}, which is a conflict of interest.'},
        {'when': {'why': ['offensive']}, 'text': 'The review {{detail|what it does, e.g. includes a staff member’s home address}}.'},
        {'when': {'why': ['unfair', 'unsure']}, 'text': '{{detail|the specific part that breaks the policy}}.'},
        {'text': 'I’d ask you to review it against that policy.'},
    ]},
    'L3P': {'name': 'A calm public reply', 'paras': [
        {'text': 'Thanks for taking the time to leave a review. We take feedback seriously.'},
        {'text': '{{response|one or two calm, factual sentences, e.g. We can’t find a booking under this name for that date}}.'},
        {'text': 'We’d like to understand what happened. Please contact us on {{contact|your business phone or email}} so we can talk it through.'},
    ]},
    'L4': {'name': 'Photo removal request', 'paras': [
        {'text': 'Subject: Request to remove a photo of me'},
        {'text': 'Hello,'},
        {'text': 'I’m writing about a photo of me on your site:\n{{link|link to the page or image}}'},
        {'when': {'whose': ['mine']}, 'text': 'I took this photo and own the copyright in it. I didn’t give permission for it to be used.'},
        {'when': {'whose': ['other']}, 'text': 'It was posted without my permission, and I’d like it taken down.'},
        {'text': 'Please remove the photo, including any copies elsewhere on your site. I’d be grateful for a reply within 14 days.'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|your email}}'},
    ]},
    'L5': {'name': 'Short follow-up', 'paras': [
        {'text': 'Subject: Following up on my request of {{sent|the date you sent it}}'},
        {'text': 'Hello,'},
        {'text': 'I wrote to you on {{sent|the date you sent it}} about:\n{{link|the link}}'},
        {'text': 'I haven’t had a reply yet. Could you let me know whether you’ve received my request, and when I can expect an answer?'},
        {'text': 'Thank you,\n{{name|your name}}'},
    ]},
    'L6': {'name': '“This isn’t me” request', 'paras': [
        {'text': 'Subject: Request to make clear an article isn’t about me'},
        {'text': 'Dear Editor,'},
        {'text': 'I’m writing about this article:\n{{link|link to the article}}'},
        {'text': 'It’s about a person named {{their|the name in the article}}, which is also my name. I’m not that person. Because we share a name, people searching for me find this article and think it’s about me.'},
        {'text': 'I’m not asking you to change your reporting. I’d be grateful if you would consider adding a detail that helps readers tell us apart, such as the person’s age, suburb or occupation, if that’s already public.'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|your email}}'},
    ]},
    'L6W': {'name': '“This isn’t me” request to a website', 'paras': [
        {'text': 'Subject: Request about a page that mentions someone with my name'},
        {'text': 'Hello,'},
        {'text': 'I’m writing about this page:\n{{link|link to the page or post}}'},
        {'text': 'It’s about a person named {{their|the name on the page}}, which is also my name. I’m not that person. Because we share a name, people searching for me find this page and think it’s about me.'},
        {'text': '{{ask}}'},
        {'text': 'I’d be grateful for a reply within 14 days.'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|your email}}'},
    ]},
    'L7': {'name': 'Request to a website owner', 'paras': [
        {'text': 'Subject: Request about a page that mentions me'},
        {'text': 'Hello,'},
        {'text': 'I’m writing about this page:\n{{link|link to the page or post}}'},
        {'text': 'It says {{says|what it says about you, in one sentence}}. {{why|why that’s a problem, e.g. it’s out of date, wrong, or shows private details}}.'},
        {'text': '{{ask}}'},
        {'text': 'I’d be grateful for a reply within 14 days.'},
        {'text': 'Kind regards,\n{{name|your name}}\n{{email|your email}}'},
    ]},
}

ASKS = {
    'update': {'label': 'Add an update about what happened next', 'small': 'The smallest change you can ask for', 'phrase': 'add an update to the article so it reflects what happened next'},
    'correct': {'label': 'Correct what’s wrong', 'phrase': 'correct the parts that are wrong'},
    'anonymise': {'label': 'Remove or change my name', 'small': 'For example, use initials instead', 'phrase': 'remove my name, or replace it with initials'},
    'noindex': {'label': 'Stop the page showing in search engines', 'small': 'Called a “noindex” tag. The page stays, but search engines drop it.', 'phrase': 'add a “noindex” tag, so search engines stop showing the page while it stays on your site'},
    'remove': {'label': 'Take it down', 'phrase': 'take the page down'},
    'tell-apart': {'label': 'Add a detail that tells us apart', 'small': 'For example, the other person’s age, suburb or job, if that’s already public', 'phrase': 'add a detail that helps readers tell us apart, such as the other person’s age, suburb or occupation, if that’s already public'},
}

EVIDENCE = ['The link, headline and date', 'A screenshot with today’s date showing', 'The words you searched when you found it']

# Plans. Steps can carry `when`. `ongoing_steps` replace `steps` when the matter is still running.
PLANS = {
    'old-news': {
        'title': [
            {'when': {'who': ['same-name']}, 'text': 'Ask the publisher to add a detail that tells you apart.'},
            {'when': {'now': ['wrong']}, 'text': 'Ask the publisher to correct the story, then ask Google to catch up.'},
            {'when': {'now': ['old']}, 'text': 'Ask the publisher to update, anonymise or de-list the story.'},
            {'when': {'now': ['outdated']}, 'text': 'Ask the publisher to fix or update the story, then ask Google to catch up.'},
            {'text': 'Ask the publisher to update the story, then ask Google to catch up.'},
        ],
        'lede': [
            {'when': {'who': ['same-name']}, 'text': 'The story isn’t about you, so you’re not asking anyone to change the reporting. You’re asking for a small detail that stops people confusing the two of you.'},
            {'when': {'now': ['wrong']}, 'text': 'A factual error is the clearest thing you can ask a publisher to fix. Here’s the order to do it in.'},
            {'when': {'now': ['outdated']}, 'text': 'If parts of the story are wrong or out of date, you can ask the publisher to fix them. Here’s the order to do it in.'},
            {'when': {'now': ['old']}, 'text': 'Being old usually isn’t enough on its own. You can still ask the publisher to consider anonymising or de-listing an old story about a private person. Here’s how to ask.'},
            {'text': 'The story leaves out what happened next, so you have a clear and reasonable thing to ask for. Here’s the order to do it in.'},
        ],
        'who_decides': 'The publisher decides what’s on the page. Google decides what shows in search, and only updates once the page changes.',
        'time': 'About 30 minutes of your time. Allow 2 to 6 weeks for replies. Some publishers take longer, and some don’t reply.',
        'order': 'Do these in order. Google’s refresh tool only works once the article has actually changed. Asking Google first, while the story is the same, will usually be turned down.',
        'check_back_days': 14,
        'pack': True,
        'steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes',
             'checklist': EVIDENCE + ['Proof of what happened next, like a court outcome or letter']},
            {'id': 'decide', 'title': 'Decide what to ask for', 'time': '5 minutes', 'when': {'who': ['me', 'helping']},
             'body': 'You can ask for more than one thing. Start with what matters most to you. Smaller asks are more often agreed to.',
             'asks': ['update', 'correct', 'anonymise', 'noindex', 'remove'], 'default_asks': {'left-out': ['update'], 'unsure': ['update'], 'wrong': ['correct'], 'outdated': ['correct', 'update'], 'old': ['anonymise', 'noindex']}},
            {'id': 'letter', 'title': 'Send your letter to the publisher', 'time': '15 minutes', 'you_send': True,
             'letter': 'L1', 'letter_when': [{'when': {'who': ['same-name']}, 'letter': 'L6'}],
             'where': 'Look for “Corrections”, “Contact the editor” or “Complaints” on the publisher’s site. Send it to one place and keep a copy.'},
            {'id': 'follow', 'title': 'Wait, then follow up', 'check_back': True,
             'body': 'If there’s no reply after 14 days, send a short, polite follow-up. Your tracker will show it as due.', 'letter': 'L5', 'letter_collapsed': True},
            {'id': 'refresh', 'title': 'Once the page changes, ask Google to refresh it', 'time': '5 minutes', 'when': {'who': ['me', 'helping']},
             'body': 'Paste the same link. Google rechecks the live page and may update the result, or drop it if the page or the words are gone.',
             'links': ['google-refresh-tool', 'google-refresh-help']},
            {'id': 'own', 'title': 'Make it easy to tell you apart', 'time': '30 minutes', 'when': {'who': ['same-name']},
             'body': 'A simple, accurate profile of your own (LinkedIn, a work page, a short bio) gives people searching for you something that is clearly you. Keep a two-line explanation ready in case an employer asks.'},
        ],
        'ongoing_steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes', 'checklist': EVIDENCE},
            {'id': 'lawyer', 'title': 'Get advice before contacting anyone', 'body': 'Ask a lawyer whether a request now could affect the case, and when the right time to ask is. Come back to this plan once it’s finished.'},
        ],
        'if_no': [
            {'when': {'country': ['au']}, 'text': 'If the publisher belongs to the Australian Press Council, you can complain there once you’ve tried the publisher.', 'link': 'press-council'},
            {'when': {'country': ['au']}, 'text': 'If it was a TV or radio story, complain to the broadcaster first, then to ACMA.', 'link': 'acma'},
            {'when': {'country': ['au']}, 'text': 'Australia’s privacy law generally doesn’t cover news reporting by media organisations, so a privacy complaint usually won’t fit a news story.'},
            {'when': {'country': ['au']}, 'text': 'If the story is untrue and harming you, talk to a lawyer soon. Defamation claims in Australia generally have to be started within a year of publication.'},
            {'when': {'country': ['nz']}, 'text': 'You can complain to the NZ Media Council about member publications once you’ve tried the publisher.', 'link': 'nz-media-council'},
            {'when': {'country': ['uk']}, 'text': 'Most UK papers belong to IPSO or IMPRESS. You can complain to them once you’ve tried the publisher.', 'link': 'ipso'},
            {'when': {'country': ['uk', 'eu']}, 'text': 'You can also ask Google to stop showing the story for searches of your name under UK or EU privacy law. Google weighs your privacy against the public interest.', 'link': 'google-eu-privacy-form'},
            {'when': {'country': ['ca']}, 'text': 'You can complain to the National NewsMedia Council about member publications.', 'link': 'ca-media-council'},
            {'when': {'country': ['us', 'other']}, 'text': 'Some newsrooms have an “unpublishing” or fresh-start policy. Search the publisher’s site for it, and mention it in a second letter.'},
            {'text': 'If the answer is no, write down what they said and the date. A clear “no” is still an outcome, and it tells you what to try next.'},
        ],
    },
    'court': {
        'title': [
            {'when': {'where': ['court-site']}, 'text': 'Check what the court allows, then deal with the copies.'},
            {'when': {'where': ['news']}, 'text': 'Ask the publisher to update the story with the outcome.'},
            {'text': 'Ask the site that copied the record to remove or anonymise it.'},
        ],
        'lede': [
            {'when': {'where': ['court-site']}, 'text': 'Courts rarely change published judgments. What usually helps more is dealing with the copies, and checking whether a rule like a spent-conviction scheme applies to you.'},
            {'text': 'Copies of court records on other websites are often the thing people actually see in search. The site owner can usually remove, anonymise or de-list them.'},
        ],
        'who_decides': 'The court decides its own records. A site that copied a record decides its copy. Google decides what shows in search.',
        'time': 'About 30 minutes of your time. Allow 2 to 6 weeks for replies.',
        'order': 'Check the rules that apply to you before you write. Whether a spent-conviction scheme or a non-publication order applies is a question for a lawyer or Legal Aid, and it can change what you ask for.',
        'check_back_days': 14,
        'pack': True,
        'steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes', 'checklist': EVIDENCE + ['The case outcome, if you have it']},
            {'id': 'rules', 'title': 'Check whether a rule protects you', 'time': '15 minutes',
             'body': 'In Australia each state and territory has a spent-convictions scheme, and some cases have non-publication orders. If either applies, say so in your letter. Legal Aid or a community legal centre can tell you for free.',
             'links': ['legal-aid-au', 'clcs-au'], 'links_when': {'country': ['au']}},
            {'id': 'court-note', 'title': 'Know what Google can see', 'when': {'where': ['court-site', 'unsure']},
             'body': 'Some Australian case-law databases, such as AustLII, ask search engines not to index judgments. So what shows up on Google is often a news story or a copy on another site, not the court’s own page.'},
            {'id': 'decide', 'title': 'Decide what to ask for', 'time': '5 minutes',
             'asks': ['anonymise', 'noindex', 'remove', 'update'], 'default_asks': {'_': ['anonymise']}},
            {'id': 'letter', 'title': 'Send your letter to the site', 'time': '15 minutes', 'you_send': True, 'letter': 'L1C',
             'letter_when': [{'when': {'who': ['same-name']}, 'letter': 'L6'}, {'when': {'where': ['news']}, 'letter': 'L1'}],
             'where': 'Look for a contact, privacy or “remove a record” page. Copy sites often have a removal form. Keep a copy of what you send.'},
            {'id': 'follow', 'title': 'Wait, then follow up', 'check_back': True,
             'body': 'If there’s no reply after 14 days, send a short follow-up.', 'letter': 'L5', 'letter_collapsed': True},
            {'id': 'refresh', 'title': 'Once the page changes, ask Google to refresh it', 'time': '5 minutes',
             'body': 'Paste the same link so Google rechecks the page.', 'links': ['google-refresh-tool', 'google-refresh-help']},
        ],
        'ongoing_steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes', 'checklist': EVIDENCE},
            {'id': 'lawyer', 'title': 'Get advice before contacting anyone', 'body': 'While the case is running, ask your lawyer or Legal Aid before you contact a court, a publisher or a website about it.'},
        ],
        'if_no': [
            {'when': {'country': ['uk', 'eu']}, 'text': 'Ask Google to stop showing the page for searches of your name. Old, spent or minor matters are often the strongest requests under UK and EU privacy law.', 'link': 'google-eu-privacy-form'},
            {'when': {'country': ['au']}, 'text': 'If a spent-conviction scheme or a non-publication order applies and the site still won’t act, get legal advice about what you can do next.'},
            {'text': 'If the page shows your home address or phone number, Google may remove those results even if the site won’t.', 'link': 'google-personal-info'},
            {'text': 'Write down what they said and the date. A “no” is still an outcome, and it tells you what to try next.'},
        ],
    },
    'people-search': {
        'title': [{'text': 'Opt out of each site, then ask Google to drop your contact details.'}],
        'lede': [{'text': 'Most people-search sites have an opt-out page you can use yourself. It’s tedious, and listings can come back, so keep a record. Do the sites first, then Google.'}],
        'who_decides': 'Each site decides its own listing. Google decides whether your phone, email or home address show in search.',
        'time': 'About 10 minutes per site. Listings can take up to 30 days to go, and some come back, so check again later.',
        'order': 'Use a separate email address for opt-outs if you can. Never pay a site to remove your own listing.',
        'check_back_days': 30,
        'pack': True,
        'steps': [
            {'id': 'list', 'title': 'List every site you’ve found', 'time': '10 minutes',
             'checklist': ['The link to each listing', 'A screenshot of each one', 'What each one shows'],
             'body': 'Search your name with your suburb or city. The same listing often appears on several sites owned by one company.'},
            {'id': 'optout', 'title': 'Use each site’s opt-out page', 'time': '10 minutes per site', 'you_send': True,
             'body': 'Look for “opt out”, “remove my information”, “privacy” or “do not sell” at the bottom of the site. Some ask you to confirm by email. They shouldn’t need your ID.',
             'links': ['spokeo-optout'], 'links_when': {'country': ['us']}},
            {'id': 'letter', 'title': 'If there’s no opt-out, send a removal request', 'time': '10 minutes', 'you_send': True, 'letter': 'L2',
             'where': 'Send it to the privacy or contact email on the site. Keep a copy.'},
            {'id': 'google', 'title': 'Ask Google to remove your contact details', 'time': '10 minutes',
             'body': 'Google will consider removing results that show your home address, phone number or email, even if the site keeps the listing. Where it’s available, “Results about you” can also watch for new ones.',
             'links': ['google-personal-info', 'google-results-about-you']},
            {'id': 'recheck', 'title': 'Check again in 30 days', 'check_back': True,
             'body': 'Listings often come back when sites refresh their data. Search again and repeat the opt-out if you need to.'},
        ],
        'if_no': [
            {'when': {'country': ['au']}, 'text': 'Businesses that trade in personal information are generally covered by the Privacy Act, whatever their size. If a site doesn’t deal with your request within 30 days, you can complain to the OAIC.', 'link': 'oaic-complaint'},
            {'when': {'country': ['nz']}, 'text': 'You can ask the agency to correct your information, and complain to the Privacy Commissioner if it won’t.', 'link': 'nz-privacy'},
            {'when': {'country': ['uk']}, 'text': 'Under UK GDPR you can ask for your data to be erased. If a site doesn’t answer within a month, complain to the ICO.', 'link': 'ico-complaint'},
            {'when': {'country': ['eu']}, 'text': 'Under the GDPR you can ask for your data to be erased. If a site doesn’t answer within a month, complain to your national data protection authority.', 'link': 'edpb-members'},
            {'when': {'country': ['us']}, 'text': 'If you live in California, the CCPA gives you a right to ask covered businesses to delete your information. Other states have similar laws.', 'link': 'cppa'},
            {'when': {'country': ['ca']}, 'text': 'You can complain to the Office of the Privacy Commissioner of Canada if a business won’t deal with your request.', 'link': 'opc-canada'},
            {'text': 'If Google turns down your contact-details request, you can resubmit with clearer screenshots showing the details.'},
        ],
    },
    'fake-profile': {
        'title': [{'text': 'Report the account to the platform, and tell people it isn’t you.'}],
        'lede': [{'text': 'Platforms remove impersonation accounts more readily than most other things. The report form is the fastest way. You don’t need a letter.'}],
        'who_decides': 'The platform decides whether the account comes down.',
        'time': 'About 15 minutes. Platforms usually reply within days.',
        'order': 'Screenshot the profile before you report it. Once it’s gone, you can’t prove what it said.',
        'check_back_days': 7,
        'pack': False,
        'steps': [
            {'id': 'evidence', 'title': 'Screenshot the profile and its link', 'time': '5 minutes',
             'checklist': ['The profile page and its web address', 'Any messages it sent people', 'Your own real account, if you have one']},
            {'id': 'report', 'title': 'Report it through the platform’s impersonation form', 'time': '10 minutes', 'you_send': True,
             'body': 'Use the platform’s own form. It may ask you to confirm who you are. Only share ID through the platform’s form, never with someone who contacts you about it.',
             'links_by': {'platform': {'facebook': ['facebook-impersonation'], 'instagram': ['instagram-impersonation'], 'tiktok': ['tiktok-impersonation'], 'x': ['x-impersonation'], 'linkedin': ['linkedin-impersonation']}},
             'letter': 'L3F', 'letter_label': 'Wording you can paste into the form'},
            {'id': 'tell', 'title': 'Tell your contacts it isn’t you', 'time': '5 minutes',
             'body': 'Post a short note from your real account: “There’s a fake account using my name and photos. Please don’t accept requests or reply to it. I’ve reported it.”'},
            {'id': 'follow', 'title': 'Check the report status', 'check_back': True,
             'body': 'Most platforms show report updates in your support inbox or notifications.'},
        ],
        'if_no': [
            {'when': {'country': ['au']}, 'text': 'If it’s being used to scam people or misuse your identity, report it to ReportCyber. IDCARE offers free identity support.', 'link': 'reportcyber'},
            {'when': {'country': ['au']}, 'text': 'If the account is seriously harassing or threatening you, eSafety may be able to help once you’ve reported it to the platform.', 'link': 'esafety-report'},
            {'when': {'country': ['nz']}, 'text': 'Netsafe can help with online harm, including impersonation.', 'link': 'netsafe'},
            {'text': 'Ask a few friends to report the account too, but only if it’s genuinely fake. Don’t organise mass-reporting of real accounts.'},
            {'text': 'Report it again with any new evidence, such as new messages it has sent.'},
        ],
    },
    'review': {
        'title': [
            {'when': {'why': ['unfair']}, 'text': 'Reply calmly in public, and report only the parts that break the rules.'},
            {'text': 'Match the review to a specific rule, then report it.'},
        ],
        'lede': [
            {'when': {'why': ['unfair']}, 'text': 'A real customer’s unfair review usually stays up. A calm public reply often does more for the next customer than removal would.'},
            {'text': 'Platforms remove reviews that break a specific policy, not reviews that are just negative. Name the rule and give one or two facts.'},
        ],
        'who_decides': 'The review platform decides, against its own policy.',
        'time': 'About 20 minutes. Platforms often take a few days to a few weeks.',
        'order': 'Don’t post fake positive reviews, offer incentives for reviews, or ask friends to mass-report. These break platform rules and, in Australia, consumer law.',
        'check_back_days': 14,
        'pack': False,
        'steps': [
            {'id': 'evidence', 'title': 'Screenshot the review', 'time': '5 minutes',
             'checklist': ['The review, with the reviewer’s name and date', 'Anything that shows why it breaks a rule, like booking records']},
            {'id': 'policy', 'title': 'Find the rule it breaks', 'time': '5 minutes',
             'body': 'Common ones: fake engagement (not a real experience), conflict of interest (competitors, ex-staff), off-topic, hate or harassment, and personal information.',
             'links': ['google-review-policy'], 'links_when': {'platform': ['google']}},
            {'id': 'report', 'title': 'Report it through the platform', 'time': '5 minutes', 'you_send': True,
             'body': 'Use the platform’s “report” or “flag” option. Keep it short and factual.',
             'links': ['google-review-report'], 'links_when': {'platform': ['google']}, 'letter': 'L3R', 'letter_label': 'Wording for the report'},
            {'id': 'reply', 'title': 'Write a calm public reply', 'time': '10 minutes', 'you_send': True,
             'body': 'Whatever happens with the report, a polite reply shows future customers how you handle problems. Don’t share the reviewer’s private details.',
             'letter': 'L3P', 'letter_label': 'A reply you can adapt', 'when': {'about': ['business']}},
            {'id': 'follow', 'title': 'Check back on the report', 'check_back': True,
             'body': 'If the platform says no, you can usually appeal once with clearer evidence.'},
        ],
        'if_no': [
            {'text': 'Most platforms allow one appeal. Add any evidence you didn’t include the first time.'},
            {'text': 'If the review is false and causing you serious harm, talk to a lawyer. Defamation has strict time limits, and in Australia most businesses with 10 or more employees can’t sue for it.'},
            {'text': 'Ask happy customers for honest reviews in the normal way, without incentives. Over time that matters more than one review.'},
        ],
    },
    'images': {
        'title': [
            {'when': {'whose': ['mine']}, 'text': 'Ask the site to take your photo down, then use a copyright request if they won’t.'},
            {'text': 'Ask the site to take the photo down, then ask Google to drop it.'},
        ],
        'lede': [
            {'when': {'whose': ['mine']}, 'text': 'If you took the photo, you usually own the copyright. That gives you a clear, formal way to ask for it to be removed.'},
            {'text': 'Start with whoever posted it. If it’s gone from the site, Google can then drop it from image results.'},
        ],
        'who_decides': 'The site or platform decides the photo. Google decides what shows in image search.',
        'time': 'About 20 minutes. Allow 1 to 4 weeks for replies.',
        'order': 'Ask the site first. Google usually only removes an image from search once the page has changed, unless it breaks one of Google’s own policies.',
        'check_back_days': 14,
        'pack': True,
        'steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes',
             'checklist': ['The link to the page and to the image', 'A screenshot with today’s date', 'The original photo, if you took it']},
            {'id': 'report', 'title': 'On social media, use the report button', 'time': '5 minutes', 'you_send': True, 'when': {'where': ['social']},
             'body': 'Report the post as a privacy or copyright issue, using the platform’s own options.'},
            {'id': 'letter', 'title': 'Ask the site owner to remove it', 'time': '10 minutes', 'you_send': True, 'letter': 'L4',
             'where': 'Use the site’s contact page or the email in its privacy policy. Keep a copy.'},
            {'id': 'copyright', 'title': 'If they won’t, send a copyright request', 'time': '15 minutes', 'when': {'whose': ['mine']},
             'body': 'Google has a formal copyright process for images in search. Only use it for photos you took yourself.',
             'links': ['google-copyright-help', 'google-copyright-form']},
            {'id': 'follow', 'title': 'Wait, then follow up', 'check_back': True, 'body': 'If there’s no reply after 14 days, send a short follow-up.', 'letter': 'L5', 'letter_collapsed': True},
            {'id': 'refresh', 'title': 'Once it’s gone, ask Google to refresh it', 'time': '5 minutes',
             'body': 'Google’s refresh tool works for images too.', 'links': ['google-refresh-tool', 'google-personal-info']},
        ],
        'if_no': [
            {'when': {'country': ['au']}, 'text': 'If the image is intimate, or it’s being used to harass you, eSafety can act directly.', 'link': 'esafety-iba'},
            {'when': {'country': ['uk', 'eu']}, 'text': 'You can ask Google to remove the image from searches of your name under UK or EU privacy law.', 'link': 'google-eu-privacy-form'},
            {'text': 'If the image shows personal details, like your address or ID, Google may remove it from search under its personal information policy.', 'link': 'google-personal-info'},
        ],
    },
    'general': {
        'title': [
            {'when': {'who': ['same-name']}, 'text': 'Ask the site to add a detail that tells you apart.'},
            {'text': 'Ask the website owner first, then ask Google to catch up.'},
        ],
        'lede': [
            {'when': {'who': ['same-name']}, 'text': 'The page isn’t about you, so you’re not asking anyone to change what it says about the other person. You’re asking for a small detail that stops people confusing the two of you.'},
            {'text': 'Whatever it is, the person who runs the site is usually the one who can change it. Here’s a simple way to ask.'},
        ],
        'who_decides': 'The website owner decides the page. Google decides what shows in search.',
        'time': 'About 30 minutes. Allow 2 to 6 weeks for replies.',
        'order': 'Ask the site first. Google’s tools mostly work once the page has changed.',
        'check_back_days': 14,
        'pack': True,
        'steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes', 'checklist': EVIDENCE},
            {'id': 'report', 'title': 'On social media, check the report options', 'time': '5 minutes', 'you_send': True, 'when': {'where': ['social']},
             'body': 'If the post breaks one of the platform’s rules, for example by sharing private details, use its report option. The platform decides whether it comes down. You can also send the request below to the person who posted it.'},
            {'id': 'decide', 'title': 'Decide what to ask for', 'time': '5 minutes', 'asks': ['correct', 'update', 'anonymise', 'noindex', 'remove', 'tell-apart'], 'default_asks': {'_': ['correct']}},
            {'id': 'letter', 'title': 'Send your request to the site owner', 'time': '15 minutes', 'you_send': True, 'letter': 'L7',
             'letter_when': [{'when': {'who': ['same-name']}, 'letter': 'L6W'}],
             'where': 'Use the contact page, or the email in the site’s privacy policy. Keep a copy.'},
            {'id': 'follow', 'title': 'Wait, then follow up', 'check_back': True, 'body': 'If there’s no reply after 14 days, send a short follow-up.', 'letter': 'L5', 'letter_collapsed': True},
            {'id': 'refresh', 'title': 'Once the page changes, ask Google to refresh it', 'time': '5 minutes', 'links': ['google-refresh-tool', 'google-removal-overview']},
        ],
        'ongoing_steps': [
            {'id': 'evidence', 'title': 'Save your evidence', 'time': '5 minutes', 'checklist': EVIDENCE},
            {'id': 'lawyer', 'title': 'Get advice before contacting anyone', 'body': 'While the case or investigation is running, ask a lawyer or Legal Aid before you contact the site about it. Come back to this plan once it’s finished.'},
        ],
        'if_no': [
            {'when': {'country': ['uk', 'eu']}, 'text': 'You can ask Google to stop showing the page for searches of your name under UK or EU privacy law.', 'link': 'google-eu-privacy-form'},
            {'text': 'If the page shows your contact details, Google may remove those results even if the site won’t.', 'link': 'google-personal-info'},
            {'text': 'Write down what they said and the date, so you can decide the next step.'},
        ],
    },
}

# "Not sure" answers point to the most likely plan. The not-sure questions are
# different from the target plan's, so each route also says how to answer the
# target plan's questions: `answers` are the starting point and `map` turns the
# visitor's "main problem" answer into the plan's own answers. `pass` lists
# not-sure questions whose answer is copied across as-is (only when that
# question was actually asked). Without this the plan falls back to its
# defaults and the letter claims things the visitor never said (for example
# "the story leaves out what happened next", or "your site lists my personal
# information" when the listing is about someone else). Only these answers,
# plus country and safety, are used to build the plan.
# `looks_like` is the "From your answers, this looks like: ..." wording and the
# tracker label, when the plan's own name would be wrong.
_SAME_NAME = {'who': 'same-name'}
NOT_SURE_ROUTES = [
    {'when': {'wrong': ['fake']}, 'plan': 'fake-profile', 'answers': {'platform': 'other', 'doing': 'existing'},
     'looks_like': 'someone pretending to be you'},
    # Someone else with my name: a tell-us-apart request, wherever it is. Never a
    # removal request for "my" data, an update request, or a court-rules plan.
    {'when': {'where': ['listing'], 'wrong': ['not-me']}, 'plan': 'general', 'answers': dict(_SAME_NAME),
     'looks_like': 'a listing about someone else with your name'},
    {'when': {'where': ['review'], 'wrong': ['not-me']}, 'plan': 'general', 'answers': dict(_SAME_NAME),
     'looks_like': 'a review that mentions someone else with your name'},
    {'when': {'where': ['court'], 'wrong': ['not-me']}, 'plan': 'general', 'answers': dict(_SAME_NAME),
     'looks_like': 'a court record about someone else with your name'},
    {'when': {'where': ['news'], 'wrong': ['not-me']}, 'plan': 'old-news', 'answers': {'who': 'same-name', 'now': 'unsure'},
     'looks_like': 'a news story about someone else with your name'},
    {'when': {'where': ['social'], 'wrong': ['not-me']}, 'plan': 'general', 'answers': {'where': 'social', 'who': 'same-name'},
     'looks_like': 'a post about someone else with your name'},
    {'when': {'where': ['listing']}, 'plan': 'people-search', 'answers': {'who': 'me', 'listed': 'other', 'sites': 'one'}},
    # 'unsure' is a route-only value: the review plan's neutral title and lede,
    # and a neutral fill-in in the report wording (nothing about customers).
    {'when': {'where': ['review']}, 'plan': 'review', 'answers': {'about': 'me', 'platform': 'other', 'why': 'unsure'},
     'map': {'private': {'why': 'offensive'}}},
    # Court and news: the visitor says whether the matter is finished. A running
    # case gets the lawyer card instead of a letter; "not sure" gets it on top.
    {'when': {'where': ['court']}, 'plan': 'court', 'answers': {'who': 'me', 'where': 'court-site', 'status': 'unsure'}, 'pass': ['status']},
    {'when': {'where': ['news'], 'wrong': ['private']}, 'plan': 'general', 'answers': {'status': 'unsure'}, 'asks': ['anonymise', 'noindex'], 'pass': ['status'],
     'looks_like': 'a news story that shows private details'},
    {'when': {'where': ['news']}, 'plan': 'old-news', 'answers': {'who': 'me', 'now': 'outdated', 'status': 'unsure'}, 'pass': ['status']},
    # Social media is never a people-search listing: general plan, with a report step.
    {'when': {'where': ['social']}, 'plan': 'general', 'answers': {'where': 'social'}, 'looks_like': 'a post on social media'},
    # Anything else, including private details on another kind of site: ask the
    # site owner (general plan). Only a site that lists people gets the
    # people-search plan.
    {'plan': 'general', 'answers': {}, 'map': {'not-me': dict(_SAME_NAME)}},
]
# The general plan's ask defaults follow the visitor's main problem.
_GENERAL_ASKS = {'wrong': ['correct', 'update'], 'private': ['anonymise', 'remove'], 'not-me': ['tell-apart']}


def asked_questions(problem, answers):
    """The questions actually shown for these answers (a question with `when` only shows if it matches)."""
    return [q for q in QUESTIONS.get(problem, []) if matches(q.get('when'), answers)]


def route_not_sure(answers):
    """(plan key, answers for that plan, default asks or None). Mirrors planKey/planAnswers in self-service.js."""
    route = next(r for r in NOT_SURE_ROUTES if matches(r.get('when'), answers))
    out = dict(route.get('answers') or {})
    out.update((route.get('map') or {}).get(answers.get('wrong'), {}))
    asked = {q['id'] for q in asked_questions('not-sure', answers)}
    for key in route.get('pass') or []:
        if key in asked and key in answers:
            out[key] = answers[key]
    for key in ('country', 'safety'):
        if key in answers:
            out[key] = answers[key]
    asks = route.get('asks') or (_GENERAL_ASKS.get(answers.get('wrong')) if route['plan'] == 'general' else None)
    return route['plan'], out, asks


def not_sure_looks_like(answers):
    """'From your answers, this looks like: ...'. Mirrors looksLike in self-service.js."""
    route = next(r for r in NOT_SURE_ROUTES if matches(r.get('when'), answers))
    plan, out, _ = route_not_sure(answers)
    if route.get('looks_like'):
        return route['looks_like']
    if out.get('who') == 'same-name':
        return 'a page about someone else with your name'
    problem = next((p for p in PROBLEMS if p['key'] == plan), None)
    return problem['label'].lower() if problem else 'a page on someone else’s site'


def help_first(answers):
    """Help cards that lead the plan. Mirrors buildPlan in self-service.js."""
    out = list(answers.get('safety') or [])
    if answers.get('status') == 'ongoing':
        out.append('ongoing')
    elif answers.get('status') == 'unsure':
        out.append('status-unsure')
    return out


def build(problem, answers):
    """The plan a visitor sees, resolved the way the desk resolves it: plan key,
    plan answers, help cards, steps, title, lede and letters (with the default asks)."""
    if problem == 'not-sure':
        key, a, fixed = route_not_sure(answers)
    else:
        key, a, fixed = problem, dict(answers), None
    plan = PLANS[key]
    ongoing = a.get('status') == 'ongoing'
    steps = [s for s in (plan.get('ongoing_steps') if ongoing and plan.get('ongoing_steps') else plan['steps']) if matches(s.get('when'), a)]
    asks = fixed
    if asks is None:
        step = next((s for s in plan['steps'] if s.get('asks')), None)
        if step:
            d = step.get('default_asks') or {}
            asks = d.get(a.get('now')) or d.get('_') or [step['asks'][0]]
    letters = {}
    for step in steps:
        letter = step.get('letter')
        for alt in step.get('letter_when', []):
            if matches(alt['when'], a):
                letter = alt['letter']
                break
        if letter:
            letters[letter] = letter_text(letter, a, asks or [])
    return {'key': key, 'answers': a, 'asks': asks or [], 'help': help_first(a), 'steps': steps,
            'title': pick(plan['title'], a), 'lede': pick(plan['lede'], a), 'letters': letters,
            'pack': bool(plan.get('pack')) and not a.get('safety') and not ongoing}


STATUSES = [
    ('not-started', 'Not started'), ('preparing', 'Preparing'), ('submitted', 'Sent by me'),
    ('waiting', 'Waiting for a reply'), ('answered', 'Answered'), ('closed', 'Closed'),
]

# Default answers used for the server-rendered outlines on /help pages.
DEFAULT_ANSWERS = {
    'old-news': {'who': 'me', 'now': 'left-out', 'status': 'finished', 'country': 'au'},
    'court': {'who': 'me', 'where': 'copy', 'status': 'finished', 'country': 'au'},
    'people-search': {'who': 'me', 'listed': 'address', 'sites': 'several', 'country': 'au'},
    'fake-profile': {'platform': 'facebook', 'doing': 'existing', 'country': 'au'},
    'review': {'about': 'business', 'platform': 'google', 'why': 'not-customer', 'country': 'au'},
    'images': {'whose': 'other', 'where': 'website', 'country': 'au'},
    'general': {'country': 'au'},
}


def matches(when, answers):
    if not when:
        return True
    return all(answers.get(key) in allowed for key, allowed in when.items())


def pick(variants, answers):
    for item in variants:
        if matches(item.get('when'), answers):
            return item['text']
    return ''


def nice_date(iso):
    """'2026-10-12' -> '12 October 2026'."""
    import datetime
    d = datetime.date.fromisoformat(iso)
    return f'{d.day} {d.strftime("%B")} {d.year}'


def client_payload():
    """Everything the browser needs to build plans. Plain data, no personal info."""
    return {
        'countries': COUNTRIES, 'links': OFFICIAL_LINKS, 'problems': PROBLEMS, 'questions': QUESTIONS,
        'help': HELP_FIRST, 'letters': LETTERS, 'asks': ASKS, 'plans': PLANS, 'notSure': NOT_SURE_ROUTES, 'generalAsks': _GENERAL_ASKS,
        'statuses': STATUSES, 'lastChecked': LAST_CHECKED,
    }


def client_json():
    return json.dumps(client_payload(), ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def outline(problem_key, answers=None):
    """Server-side outline of a plan (for /help pages): resolved title, steps and if-no items."""
    plan = PLANS[problem_key]
    answers = dict(DEFAULT_ANSWERS.get(problem_key, {}), **(answers or {}))
    steps = []
    for step in plan['steps']:
        if not matches(step.get('when'), answers):
            continue
        links = []
        if step.get('links') and matches(step.get('links_when'), answers):
            links = list(step['links'])
        for qid, by_value in (step.get('links_by') or {}).items():
            links += by_value.get(answers.get(qid), [])
        letter = step.get('letter')
        for alt in step.get('letter_when', []):
            if matches(alt['when'], answers):
                letter = alt['letter']
                break
        steps.append({**step, 'links': links, 'letter': letter})
    return {
        'title': pick(plan['title'], answers), 'lede': pick(plan['lede'], answers),
        'who_decides': plan['who_decides'], 'time': plan['time'], 'order': plan.get('order'),
        'steps': steps, 'if_no': [item for item in plan['if_no'] if matches(item.get('when'), answers)],
    }


def letter_text(letter_key, answers=None, asks=None):
    """Plain-text letter with fill-in fields shown as [label]. Used on /help pages and the pack sample."""
    answers = answers or {}
    out = []
    for para in LETTERS[letter_key]['paras']:
        if not matches(para.get('when'), answers):
            continue
        text = para['text']
        if '{{ask}}' in text:
            text = ask_sentence(asks or ['update'])
        out.append(text)
    import re
    return '\n\n'.join(re.sub(r'\{\{(\w+)\|([^}]+)\}\}', lambda m: '[' + m.group(2) + ']', p) for p in out)


def ask_sentence(asks):
    phrases = [ASKS[a]['phrase'] for a in asks if a in ASKS]
    if not phrases:
        return 'I’m writing to ask you to update the page.'
    text = 'I’m writing to ask you to ' + phrases[0] + '.'
    for extra in phrases[1:]:
        text += ' If that isn’t possible, could you ' + extra + '?'
    return text
