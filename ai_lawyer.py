"""
Fix My Name Online — AI Lawyer Agents
Jurisdiction-aware legal persona system for drafting removal requests.
Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
import hashlib


# =============================================================================
# LAWYER PERSONAS
# =============================================================================

@dataclass
class LawyerPersona:
    """AI Lawyer persona with jurisdiction specialty."""
    id: str
    name: str
    title: str
    specialty: str
    jurisdictions: List[str]
    flags: List[str]
    bio: str
    signature: str
    languages: List[str] = field(default_factory=lambda: ["English"])


LAWYERS = {
    "james_whitfield": LawyerPersona(
        id="james_whitfield",
        name="James Whitfield, Esq.",
        title="Data Protection & Privacy Law",
        specialty="GDPR, Right to be Forgotten, UK GDPR, ICO compliance",
        jurisdictions=["UK", "EU", "EEA", "CH"],
        flags=["🇬🇧", "🇪🇺", "🇪🇺"],
        bio="James Whitfield is a specialist in data protection and privacy law with expertise in GDPR compliance, Right to be Forgotten requests, and EU data subject rights. He has successfully filed hundreds of removal requests with Google, social media platforms, and data brokers across the European Union and United Kingdom.",
        signature="James Whitfield, Esq. | Data Protection & Privacy Law",
        languages=["English", "French"]
    ),
    "marcus_reilly": LawyerPersona(
        id="marcus_reilly",
        name="Marcus Reilly",
        title="Internet & Privacy Law",
        specialty="DMCA, Defamation, CCPA, State Privacy Laws",
        jurisdictions=["US"],
        flags=["🇺🇸"],
        bio="Marcus Reilly specializes in US internet law including DMCA takedown notices, defamation claims, and state privacy statutes including California's CCPA, Virginia's CDPA, and Colorado's CPA.",
        signature="Marcus Reilly | Internet & Privacy Law",
        languages=["English"]
    ),
    "david_chen": LawyerPersona(
        id="david_chen",
        name="David Chen",
        title="Australian Privacy & Online Safety Law",
        specialty="Privacy Act 1988, Online Safety Act 2021, Australian Privacy Principles",
        jurisdictions=["AU", "NZ"],
        flags=["🇦🇺", "🇳🇿"],
        bio="David Chen is an Australian privacy and online safety specialist with expertise in the Privacy Act 1988 (Cth), Australian Privacy Principles, and the Online Safety Act 2021 (Cth). He has helped hundreds of Australians remove harmful content from search results and social platforms.",
        signature="David Chen | Australian Privacy & Online Safety Law",
        languages=["English"]
    ),
    "sophia_muller": LawyerPersona(
        id="sophia_muller",
        name="Sophia Müller",
        title="German & French Data Protection Law",
        specialty="BDSG, TMG, CNIL regulations, EU national privacy law",
        jurisdictions=["DE", "FR", "AT", "BE", "NL", "ES", "IT", "PT", "PL"],
        flags=["🇩🇪", "🇫🇷", "🇪🇺"],
        bio="Sophia Müller is a specialist in German and French data protection law including BDSG, TMG, and CNIL regulations with deep expertise in EU member state variations of GDPR implementation.",
        signature="Sophia Müller | German & French Data Protection Law",
        languages=["German", "French", "English", "Dutch"]
    )
}


# =============================================================================
# LEGAL BASIS MAP
# =============================================================================

@dataclass
class LegalBasis:
    name: str
    citation: str
    description: str
    response_days: int
    effectiveness: str
    submission_url: Optional[str] = None


LEGAL_BASIS = {
    "uk": {
        "rtbf": LegalBasis(
            name="Right to be Forgotten",
            citation="UK GDPR Art. 17 + ICO Guidance + CJEU Google Spain v AEPD (C-131/12)",
            description="Right to erasure of personal data from search engine results",
            response_days=30,
            effectiveness="High for search results",
            submission_url="https://www.google.com/webmasters/tools/legal-removal-request"
        ),
        "gdpr_erasure": LegalBasis(
            name="UK GDPR Erasure",
            citation="UK GDPR Art. 17",
            description="Right to erasure of personal data held by controllers",
            response_days=30,
            effectiveness="High within UK",
            submission_url=None
        ),
        "defamation": LegalBasis(
            name="Defamation Act 2013",
            citation="Defamation Act 2013 (UK)",
            description="Remove false statements causing serious harm",
            response_days=14,
            effectiveness="High for serious harm",
            submission_url=None
        ),
        "data_broker": LegalBasis(
            name="Data Broker Removal",
            citation="UK GDPR Art. 17 + PECR",
            description="Remove personal data from people-search sites",
            response_days=30,
            effectiveness="Medium-High",
            submission_url=None
        ),
        "social_media": LegalBasis(
            name="Social Media Removal",
            citation="UK GDPR Art. 17 + Platform ToS",
            description="Remove personal data from social platforms",
            response_days=30,
            effectiveness="High",
            submission_url=None
        )
    },
    "eu": {
        "rtbf": LegalBasis(
            name="Right to be Forgotten",
            citation="GDPR Art. 17 + CJEU Google Spain v AEPD (C-131/12)",
            description="Right to erasure of personal data from search engine results",
            response_days=30,
            effectiveness="High for search results",
            submission_url="https://www.google.com/webmasters/tools/legal-removal-request"
        ),
        "gdpr_erasure": LegalBasis(
            name="GDPR Erasure",
            citation="Regulation (EU) 2016/679 Art. 17",
            description="Right to erasure of personal data",
            response_days=30,
            effectiveness="High within EU",
            submission_url=None
        ),
        "defamation": LegalBasis(
            name="Defamation",
            citation="Member State defamation law (varies by country)",
            description="Civil remedy for reputation damage",
            response_days=30,
            effectiveness="Medium",
            submission_url=None
        ),
        "data_broker": LegalBasis(
            name="Data Broker Removal",
            citation="GDPR Art. 17",
            description="Remove personal data from people-search sites",
            response_days=30,
            effectiveness="High",
            submission_url=None
        ),
        "social_media": LegalBasis(
            name="Social Media Removal",
            citation="GDPR Art. 17",
            description="Remove personal data from social platforms",
            response_days=30,
            effectiveness="High",
            submission_url=None
        ),
        "image_erasure": LegalBasis(
            name="Image Erasure",
            citation="GDPR Art. 17 + Art. 20",
            description="Right to removal of images containing personal data",
            response_days=30,
            effectiveness="Medium-High",
            submission_url=None
        )
    },
    "us": {
        "dmca": LegalBasis(
            name="DMCA Takedown",
            citation="17 U.S.C. § 512(c)(3)",
            description="Digital Millennium Copyright Act takedown for copyrighted content",
            response_days=14,
            effectiveness="High for US hosts",
            submission_url="https://dmca.copyright.gov/osp/"
        ),
        "defamation": LegalBasis(
            name="Defamation / Libel",
            citation="Common law + state statutes",
            description="Remove false statements of fact that harm reputation",
            response_days=30,
            effectiveness="Medium - requires proof",
            submission_url=None
        ),
        "ccpa": LegalBasis(
            name="California Consumer Privacy Act",
            citation="Cal. Civ. Code § 1798.100",
            description="Delete personal information (CA residents only)",
            response_days=45,
            effectiveness="Medium for CA residents",
            submission_url="https://www.reddit.com/report"
        ),
        "platform_removal": LegalBasis(
            name="Platform ToS Violation",
            citation="Platform Terms of Service",
            description="Remove content violating platform rules",
            response_days=7,
            effectiveness="Medium",
            submission_url=None
        ),
        "copyright": LegalBasis(
            name="Copyright Infringement",
            citation="17 U.S.C. § 512",
            description="Takedown for copyright-infringing content",
            response_days=14,
            effectiveness="High",
            submission_url="https://dmca.copyright.gov/osp/"
        ),
        " Erie_doctrine": LegalBasis(
            name="State Image Laws",
            citation="CA SB 822, TX HB 670",
            description="Remove unauthorized use of personal images",
            response_days=30,
            effectiveness="Medium",
            submission_url=None
        )
    },
    "au": {
        "privacy_act": LegalBasis(
            name="Privacy Act 1988",
            citation="Privacy Act 1988 (Cth) + Australian Privacy Principles",
            description="Australian Privacy Principles - delete personal information",
            response_days=30,
            effectiveness="Medium-High",
            submission_url=None
        ),
        "defamation": LegalBasis(
            name="Defamation",
            citation="Civil Liability Act 2002 (NSW) and equivalents",
            description="State-based defamation laws",
            response_days=28,
            effectiveness="Medium",
            submission_url=None
        ),
        "online_safety": LegalBasis(
            name="Online Safety Act 2021",
            citation="Online Safety Act 2021 (Cth)",
            description="Remove cyber abuse, harmful content from platforms",
            response_days=14,
            effectiveness="High for cyber abuse",
            submission_url="https://www.esafety.gov.au/"
        ),
        "data_broker": LegalBasis(
            name="Data Broker Removal",
            citation="Privacy Act 1988 APP 6",
            description="Remove personal data from data brokers",
            response_days=30,
            effectiveness="Medium",
            submission_url=None
        ),
        "social_media": LegalBasis(
            name="Social Media Removal",
            citation="Online Safety Act 2021 + Platform ToS",
            description="Remove harmful content from social platforms",
            response_days=14,
            effectiveness="High",
            submission_url="https://www.esafety.gov.au/"
        )
    },
    "ca": {
        "pipeda": LegalBasis(
            name="PIPEDA Access & Erasure",
            citation="S.C. 2000, c. 5",
            description="Personal Information Protection and Electronic Documents Act",
            response_days=30,
            effectiveness="Medium",
            submission_url=None
        ),
        "defamation": LegalBasis(
            name="Defamation",
            citation="Common law + Quebec Civil Code",
            description="Libel and slander remedies",
            response_days=30,
            effectiveness="Medium",
            submission_url=None
        )
    },
    "br": {
        "lgpd": LegalBasis(
            name="LGPD Erasure",
            citation="Lei 13.709/2018 Art. 18",
            description="Lei Geral de Proteção de Dados - right to erasure",
            response_days=15,
            effectiveness="High within Brazil",
            submission_url=None
        )
    },
    "jp": {
        "appi": LegalBasis(
            name="APPI Erasure",
            citation="Act No. 57 of 2003, as amended",
            description="Act on the Protection of Personal Information - right to erasure",
            response_days=30,
            effectiveness="Medium-High",
            submission_url=None
        )
    }
}


# =============================================================================
# PLATFORM SUBMISSION PORTALS
# =============================================================================

SUBMISSION_PORTALS = {
    "google_search": "https://www.google.com/webmasters/tools/legal-removal-request",
    "google_general": "https://support.google.com/websearch/troubleshooter/9685456",
    "medium": "https://medium.com/policy/abuse",
    "reddit": "https://www.reddit.com/report",
    "yelp": "https://support.yelp.com/s/contact-us",
    "glassdoor": "https://www.glassdoor.com/about/contact.htm",
    "quora": "https://www.quora.com/report",
    "facebook": "https://www.facebook.com/help/contact/575434376018856",
    "twitter": "https://help.twitter.com/forms/privacy",
    "linkedin": "https://www.linkedin.com/help/linkedin/answer/68625",
    "instagram": "https://help.instagram.com/contact/384705456723",
    "youtube": "https://www.youtube.com/howyoutubeworks/policies/copyright/",
    "wordpress": "https://en.wordpress.com/abuse/",
    "blogger": "https://www.blogger.com/go/contentcomplaint",
    "tumblr": "https://www.tumblr.com/abuse",
    "pinterest": "https://help.pinterest.com/en/business-issue/report-copyright-or-trademark",
    "tiktok": "https://www.tiktok.com/report/110188308397",
    "tripadvisor": "https://www.tripadvisor.com/support/contact",
    "homify": "https://www.homify.com/abuse",
    "mugshot_sites": {
        "mugshots.com": "https://mugshots.com/remove/",
        "bustedmugshots.com": "https://bustedmugshots.com/contact/",
        "jaxmugshots.com": "https://www.jaxmugshots.com/contact/",
        "raleighmugshots.com": "https://raleighmugshots.com/contact/",
        "charlottemugshots.com": "https://charlottemugshots.com/contact/",
    }
}


# =============================================================================
# REMOVAL REQUEST DATA CLASS
# =============================================================================

@dataclass
class RemovalRequest:
    lawyer: LawyerPersona
    content_url: str
    content_type: str
    legal_basis_id: str
    legal_basis: LegalBasis
    subject: str
    letter_body: str
    legal_citations: List[str]
    submission_url: str
    submission_instructions: str
    disclaimer: str
    footer: str
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "lawyer": self.lawyer.name,
            "content_url": self.content_url,
            "content_type": self.content_type,
            "legal_basis": self.legal_basis.name,
            "subject": self.subject,
            "letter_body": self.letter_body,
            "submission_url": self.submission_url,
            "created_at": self.created_at.isoformat(),
            "disclaimer": self.disclaimer
        }


# =============================================================================
# CONTENT TYPE MAPPING
# =============================================================================

CONTENT_TYPES = {
    "defamatory_article": {
        "uk": ["defamation", "rtbf"],
        "eu": ["defamation", "rtbf"],
        "us": ["defamation", "platform_removal"],
        "au": ["defamation", "online_safety"],
        "ca": ["defamation"],
        "br": ["lgpd"],
        "jp": ["appi"]
    },
    "mugshot": {
        "uk": ["data_broker"],
        "eu": ["data_broker", "rtbf"],
        "us": ["data_broker", "platform_removal", "ccpa"],
        "au": ["data_broker", "privacy_act"],
        "ca": ["pipeda"],
        "br": ["lgpd"],
        "jp": ["appi"]
    },
    "fake_review": {
        "uk": ["defamation", "platform_removal"],
        "eu": ["defamation", "platform_removal"],
        "us": ["defamation", "platform_removal"],
        "au": ["defamation", "online_safety"],
        "ca": ["defamation"],
        "br": ["lgpd"],
        "jp": ["appi"]
    },
    "personal_data": {
        "uk": ["gdpr_erasure", "rtbf"],
        "eu": ["gdpr_erasure", "rtbf"],
        "us": ["platform_removal", "ccpa"],
        "au": ["privacy_act", "data_broker"],
        "ca": ["pipeda"],
        "br": ["lgpd"],
        "jp": ["appi"]
    },
    "copyright_infringement": {
        "uk": ["dmca"],
        "eu": ["gdpr_erasure"],
        "us": ["dmca", "copyright"],
        "au": ["privacy_act"],
        "ca": ["pipeda"],
        "br": ["lgpd"],
        "jp": ["appi"]
    }
}


# =============================================================================
# LETTER TEMPLATES
# =============================================================================

@dataclass
class LetterTemplate:
    subject: str
    body_template: str


# UK/EU GDPR Erasure Letter
GDPR_ERASURE_TEMPLATE = """Subject: Formal Request for Erasure of Personal Data — Article 17 GDPR / UK GDPR

Dear Data Protection Officer / Privacy Officer,

I, {full_name}, residing at {address}, hereby submit a formal request for erasure of personal data pursuant to Article 17 of the General Data Protection Regulation (EU) 2016/679 (GDPR) / UK GDPR.

SECTION 1 — IDENTIFICATION OF DATA SUBJECT
Full Legal Name: {full_name}
Email Address: {email}
Date of Birth: {date_of_birth}
Address: {address}

SECTION 2 — IDENTITY OF DATA CONTROLLER
Organization: {controller_name}
Website URL: {controller_url}

SECTION 3 — SPECIFIC DATA TO BE ERASED
URL of Content: {content_url}
Description of Harmful Content: {content_description}
Type of Personal Data: {content_type}

SECTION 4 — GROUNDS FOR ERASURE
This request is made pursuant to Article 17(1) GDPR / UK GDPR on the following applicable grounds:

(a) The personal data are no longer necessary in relation to the purposes for which they were collected or otherwise processed;

(b) The data subject withdraws consent on which the processing is based, and there is no other legal ground for the processing;

(c) The data subject objects to the processing pursuant to Article 21(1) and there are no overriding legitimate grounds for the processing;

(d) The personal data have been unlawfully processed;

(e) The personal data must be erased for compliance with a legal obligation in Union or Member State law to which the controller is subject.

SECTION 5 — LEGAL BASIS
This request is made under: {legal_citation}

SECTION 6 — REQUESTED ACTION
I request that you:
1. Erase all personal data relating to me at the URL specified above
2. Remove the content from any publicly accessible location
3. Cease any further processing of this personal data
4. Inform any third parties with whom you have shared this data to also erase copies
5. Provide written confirmation once the erasure has been completed

SECTION 7 — RESPONSE TIMELINE
Under Article 17(3) GDPR / UK GDPR, you are required to respond to this request within one month of receipt. If you do not comply with this request within that timeframe, I reserve the right to lodge a complaint with the relevant supervisory authority:

• United Kingdom: Information Commissioner's Office (ICO) — ico.org.uk
• European Union: National Data Protection Authority (list at edpb.europa.eu)

SECTION 8 — CONSEQUENCES OF NON-COMPLIANCE
Failure to comply with this request may result in a complaint to the supervisory authority and may expose your organization to regulatory action under Article 83 GDPR / UK GDPR.

I look forward to your timely response.

Yours faithfully,

{full_name}
{email}
{address}
Date: {date}

{lawyer_signature}

---
DISCLAIMER: This letter was prepared with AI assistance from FixMyNameOnline. This is not legal advice. The data subject is responsible for reviewing and submitting this request. Consult a qualified attorney for complex matters or if you have not received a response within the statutory timeframe.
"""


# US DMCA Takedown Notice
DMCA_TEMPLATE = """Subject: DMCA Copyright Takedown Notice — 17 U.S.C. § 512(c)(3)

To Whom It May Concern:

I, {full_name}, am the copyright owner of the material that is allegedly being infringed, or am authorized to act on behalf of the owner of an exclusive right that is allegedly infringed.

1. IDENTIFICATION OF COPYRIGHTED WORK:
Description of Work: {content_description}
Type of Work: {content_type}

2. IDENTIFICATION OF INFRINGING MATERIAL:
URL of Alleged Infringing Content: {content_url}

3. CONTACT INFORMATION:
Full Name: {full_name}
Email: {email}
Mailing Address: {address}
Telephone: {phone}

4. STATEMENT OF GOOD FAITH:
I have a good faith belief that the use of the material in the manner complained of is not authorized by the copyright owner, its agent, or the law.

5. STATEMENT OF ACCURACY:
I swear, under penalty of perjury, that the information in this notification is accurate and that I am the copyright owner or am authorized to act on behalf of the owner of an exclusive right that is allegedly infringed.

6. SIGNATURE:
Electronic Signature: {full_name}
Date: {date}

Please act expeditiously to remove or disable access to the allegedly infringing content. Prompt action is appreciated.

{lawyer_signature}

---
DISCLAIMER: This DMCA notice was prepared with AI assistance from FixMyNameOnline. This is not legal advice. The copyright owner is responsible for ensuring the accuracy of this notice. Consult an attorney for complex copyright matters.
"""


# AU Privacy Act Request
AU_PRIVACY_TEMPLATE = """Subject: Formal Request for Access and Correction of Personal Information — Privacy Act 1988 (Cth)

Dear Privacy Officer,

I, {full_name}, of {address}, am writing to make a formal request under the Privacy Act 1988 (Cth) and the Australian Privacy Principles (APPs) for access to and correction of personal information about me held by your organization.

SECTION 1 — APPLICABLE LEGISLATION
This request is made pursuant to:
• Privacy Act 1988 (Cth)
• Australian Privacy Principles (APPs)

SECTION 2 — PERSONAL INFORMATION
Full Legal Name: {full_name}
Email: {email}
Date of Birth: {date_of_birth}
Address: {address}

SECTION 3 — DETAILS OF INFORMATION REQUESTED
I am requesting:
1. Access to all personal information your organization holds about me
2. Correction of any inaccurate personal information
3. Erasure of personal information that is no longer necessary for any purpose

URL of Content: {content_url}
Description of Personal Information: {content_description}

SECTION 4 — SPECIFIC REQUESTS
I request that you:
1. Confirm what personal information about me you hold
2. Provide access to this information
3. Correct any inaccurate information
4. Delete personal information that is no longer necessary (APP 6)
5. Remove the content at the URL specified above which discloses my personal information without my consent

SECTION 5 — RESPONSE TIMELINE
Under the APPs, you are required to respond to this request within 30 days.

SECTION 6 — ESCALATION
If I do not receive a satisfactory response within 30 days, I may escalate this matter to:
• Office of the Australian Information Commissioner (OAIC) — oaic.gov.au

Yours faithfully,

{full_name}
{email}
{address}
Date: {date}

{lawyer_signature}

---
DISCLAIMER: This letter was prepared with AI assistance from FixMyNameOnline. This is not legal advice. Consult a qualified Australian attorney for complex matters.
"""


# Defamation Cease and Desist
DEFAMATION_CND_TEMPLATE = """Subject: CEASE AND DESIST — Defamatory Content Requiring Immediate Removal

Dear Sir/Madam,

RE: Defamatory Content at {content_url}

I, {full_name}, have become aware of content published at the URL specified above which I believe is defamatory of my character and reputation.

SECTION 1 — THE ALLEGEDLY DEFAMATORY CONTENT
URL: {content_url}
Description: {content_description}

SECTION 2 — GROUNDS FOR DEFAMATION CLAIM
The content at the URL specified above is defamatory because:
1. It makes false statements of fact about me
2. These statements have caused or are likely to cause serious harm to my reputation
3. The statements have been published to third parties (the public / identified persons)

SECTION 3 — LEGAL POSITION
{legal_citation}

SECTION 4 — DEMANDS
I hereby demand that you:
1. IMMEDIATELY remove the defamatory content at {content_url}
2. Cease and desist from publishing any further defamatory content about me
3. Provide written confirmation of compliance within 7 days
4. Preserve all evidence related to the publication of the defamatory content

SECTION 5 — CONSEQUENCES OF NON-COMPLIANCE
If you fail to comply with this demand within 7 days, I will have no choice but to pursue all available legal remedies including:
• Commencement of defamation proceedings
• Claim for damages including aggravated damages
• Injunctive relief to prevent further publication
• Costs on an indemnity basis

SECTION 6 — WITHOUT PREJUDICE
This letter is sent on a without prejudice basis and without admission of liability. The purpose of this letter is to resolve this matter without the need for litigation.

Yours faithfully,

{full_name}
{email}
Date: {date}

{lawyer_signature}

---
DISCLAIMER: This letter was prepared with AI assistance from FixMyNameOnline. This is not legal advice and does not constitute a guarantee of any particular legal outcome. Consult a qualified attorney before taking legal action. In Australia, seek specialist defamation law advice.
"""


# =============================================================================
# LAWYER AGENT FUNCTIONS
# =============================================================================

def get_lawyer(jurisdiction: str) -> LawyerPersona:
    """Get the appropriate lawyer for a jurisdiction."""
    jurisdiction = jurisdiction.lower()
    
    if jurisdiction in ["uk", "gb", "england", "scotland", "wales"]:
        return LAWYERS["james_whitfield"]
    elif jurisdiction in ["de", "at", "be", "nl", "es", "it", "pt", "pl", "fr"]:
        return LAWYERS["sophia_muller"]
    elif jurisdiction in ["au", "nz"]:
        return LAWYERS["david_chen"]
    elif jurisdiction in ["us", "usa", "united states"]:
        return LAWYERS["marcus_reilly"]
    else:
        return LAWYERS["marcus_reilly"]  # Default to US


def detect_jurisdiction(customer_country: str) -> LawyerPersona:
    """Auto-detect lawyer based on country."""
    return get_lawyer(customer_country)


def get_available_legal_bases(jurisdiction: str) -> dict:
    """Get available legal bases for a jurisdiction."""
    return LEGAL_BASIS.get(jurisdiction.lower(), LEGAL_BASIS.get("us", {}))


def get_available_lawyers() -> dict:
    """Get all available lawyer personas."""
    return LAWYERS


def generate_gdpr_letter(
    lawyer: LawyerPersona,
    full_name: str,
    email: str,
    address: str,
    date_of_birth: str,
    controller_name: str,
    controller_url: str,
    content_url: str,
    content_description: str,
    content_type: str,
    legal_citation: str
) -> RemovalRequest:
    """Generate a GDPR erasure letter."""
    
    letter_body = GDPR_ERASURE_TEMPLATE.format(
        full_name=full_name,
        email=email,
        address=address,
        date_of_birth=date_of_birth,
        controller_name=controller_name,
        controller_url=controller_url,
        content_url=content_url,
        content_description=content_description,
        content_type=content_type,
        legal_citation=legal_citation,
        date=datetime.now().strftime("%d %B %Y"),
        lawyer_signature=lawyer.signature
    )
    
    legal_basis = LEGAL_BASIS.get("eu", {}).get("gdpr_erasure", 
        LEGAL_BASIS.get("uk", {}).get("gdpr_erasure"))
    
    submission_url = SUBMISSION_PORTALS.get("google_search")
    
    return RemovalRequest(
        lawyer=lawyer,
        content_url=content_url,
        content_type=content_type,
        legal_basis_id="gdpr_erasure",
        legal_basis=legal_basis,
        subject=f"Data Erasure Request — Article 17 GDPR — {full_name}",
        letter_body=letter_body,
        legal_citations=[
            "Regulation (EU) 2016/679 Art. 17",
            "CJEU Google Spain v AEPD (C-131/12)",
            "ICO Guidance on Right to Erasure"
        ],
        submission_url=submission_url or "",
        submission_instructions=f"Submit this letter to {controller_name} via their privacy contact form or email. For Google search removal, use: {SUBMISSION_PORTALS['google_search']}",
        disclaimer="AI-generated draft. Review and submit as self-represented party.",
        footer="Prepared with AI assistance from FixMyNameOnline. Not legal advice. Consult counsel for complex matters. | © 2026 MadisonJade Pty Ltd"
    )


def generate_dmca_notice(
    lawyer: LawyerPersona,
    full_name: str,
    email: str,
    address: str,
    phone: str,
    content_url: str,
    content_description: str,
    content_type: str
) -> RemovalRequest:
    """Generate a DMCA takedown notice."""
    
    letter_body = DMCA_TEMPLATE.format(
        full_name=full_name,
        email=email,
        address=address,
        phone=phone,
        content_url=content_url,
        content_description=content_description,
        content_type=content_type,
        date=datetime.now().strftime("%d %B %Y"),
        lawyer_signature=lawyer.signature
    )
    
    legal_basis = LEGAL_BASIS.get("us", {}).get("dmca")
    
    return RemovalRequest(
        lawyer=lawyer,
        content_url=content_url,
        content_type=content_type,
        legal_basis_id="dmca",
        legal_basis=legal_basis,
        subject=f"DMCA Copyright Takedown Notice — 17 U.S.C. § 512(c)(3)",
        letter_body=letter_body,
        legal_citations=[
            "17 U.S.C. § 512(c)(3) — DMCA Takedown Notice Requirements",
            "17 U.S.C. § 512(g) — Counter-Notification Rights"
        ],
        submission_url=SUBMISSION_PORTALS.get("google_search", ""),
        submission_instructions=f"Submit this DMCA notice to the hosting provider. For Google-hosted content: {SUBMISSION_PORTALS['google_search']}. For DMCA.com: https://dmca.copyright.gov/osp/",
        disclaimer="AI-generated draft. Sworn statement under penalty of perjury. Consult an attorney for complex copyright matters.",
        footer="Prepared with AI assistance from FixMyNameOnline. Not legal advice. Consult counsel for complex matters. | © 2026 MadisonJade Pty Ltd"
    )


def generate_au_privacy_letter(
    lawyer: LawyerPersona,
    full_name: str,
    email: str,
    address: str,
    date_of_birth: str,
    content_url: str,
    content_description: str
) -> RemovalRequest:
    """Generate an Australian Privacy Act request letter."""
    
    letter_body = AU_PRIVACY_TEMPLATE.format(
        full_name=full_name,
        email=email,
        address=address,
        date_of_birth=date_of_birth,
        content_url=content_url,
        content_description=content_description,
        date=datetime.now().strftime("%d %B %Y"),
        lawyer_signature=lawyer.signature
    )
    
    legal_basis = LEGAL_BASIS.get("au", {}).get("privacy_act")
    
    return RemovalRequest(
        lawyer=lawyer,
        content_url=content_url,
        content_type="personal_data",
        legal_basis_id="privacy_act",
        legal_basis=legal_basis,
        subject=f"Privacy Act Request — {full_name}",
        letter_body=letter_body,
        legal_citations=[
            "Privacy Act 1988 (Cth)",
            "Australian Privacy Principles (APPs)",
            "APP 6 — Use or Disclosure of Personal Information"
        ],
        submission_url=SUBMISSION_PORTALS.get("google_search", ""),
        submission_instructions=f"Submit to the organization's privacy officer. For Google search removal: {SUBMISSION_PORTALS['google_search']}. For cyber abuse: https://www.esafety.gov.au/",
        disclaimer="AI-generated draft. Australian residents only. Consult a qualified Australian attorney for complex matters.",
        footer="Prepared with AI assistance from FixMyNameOnline. Not legal advice. Consult counsel for complex matters. | © 2026 MadisonJade Pty Ltd"
    )


def generate_defamation_cnd(
    lawyer: LawyerPersona,
    full_name: str,
    email: str,
    address: str,
    content_url: str,
    content_description: str,
    jurisdiction: str
) -> RemovalRequest:
    """Generate a defamation cease and desist letter."""
    
    legal_citation_map = {
        "uk": "Under the Defamation Act 2013 (UK), a statement is defamatory if it has caused or is likely to cause serious harm to reputation. The publication of false statements of fact about me constitutes defamation.",
        "eu": "Under applicable EU member state defamation law, publication of false statements of fact causing damage to reputation constitutes defamation.",
        "us": "Under common law defamation principles and applicable state statutes, publication of false statements of fact that harm reputation constitutes libel/slander.",
        "au": "Under the Civil Liability Act 2002 (NSW) and equivalents, a person who publishes defamatory matter is liable to damages for defamation.",
        "ca": "Under common law libel and applicable provincial statutes, publication of false statements causing harm to reputation constitutes defamation."
    }
    
    legal_citation = legal_citation_map.get(jurisdiction.lower(), legal_citation_map["us"])
    
    letter_body = DEFAMATION_CND_TEMPLATE.format(
        full_name=full_name,
        email=email,
        address=address,
        content_url=content_url,
        content_description=content_description,
        legal_citation=legal_citation,
        date=datetime.now().strftime("%d %B %Y"),
        lawyer_signature=lawyer.signature
    )
    
    legal_basis_map = {
        "uk": "defamation",
        "eu": "defamation",
        "us": "defamation",
        "au": "defamation",
        "ca": "defamation"
    }
    
    basis_id = legal_basis_map.get(jurisdiction.lower(), "defamation")
    legal_basis = LEGAL_BASIS.get(jurisdiction.lower(), LEGAL_BASIS["us"]).get(basis_id)
    
    return RemovalRequest(
        lawyer=lawyer,
        content_url=content_url,
        content_type="defamatory_content",
        legal_basis_id=basis_id,
        legal_basis=legal_basis,
        subject=f"CEASE AND DESIST — Defamatory Content — {full_name}",
        letter_body=letter_body,
        legal_citations=[
            legal_citation
        ],
        submission_url="",
        submission_instructions="Send this letter via email with read receipt and post with tracking. Keep copies for your records.",
        disclaimer="AI-generated draft. Not legal advice. Consult a qualified defamation attorney before sending, especially in complex cases.",
        footer="Prepared with AI assistance from FixMyNameOnline. Not legal advice. Consult counsel for complex matters. | © 2026 MadisonJade Pty Ltd"
    )


def generate_removal_request(
    lawyer: LawyerPersona,
    content_url: str,
    content_type: str,
    content_description: str,
    requestor_name: str,
    requestor_email: str,
    requestor_address: str = "",
    requestor_phone: str = "",
    requestor_dob: str = "",
    legal_basis_override: str = None
) -> RemovalRequest:
    """Main entry point: generate a complete removal request letter.
    
    Auto-selects the appropriate legal basis and letter template based on
    jurisdiction and content type.
    """
    
    # Determine jurisdiction from lawyer
    jurisdiction = lawyer.jurisdictions[0] if lawyer.jurisdictions else "us"
    
    # Map content type to legal basis
    content_basis_map = CONTENT_TYPES.get(content_type, CONTENT_TYPES["personal_data"])
    available_bases = content_basis_map.get(jurisdiction.lower(), 
        content_basis_map.get("us", ["personal_data"]))
    
    if legal_basis_override and legal_basis_override in available_bases:
        basis_id = legal_basis_override
    else:
        basis_id = available_bases[0] if available_bases else "gdpr_erasure"
    
    # Get legal basis
    basis_dict = LEGAL_BASIS.get(jurisdiction.lower(), LEGAL_BASIS["us"])
    legal_basis = basis_dict.get(basis_id)
    
    if not legal_basis:
        legal_basis = basis_dict.get(list(basis_dict.keys())[0])
    
    # Select template based on basis
    if basis_id in ["gdpr_erasure", "rtbf"]:
        return generate_gdpr_letter(
            lawyer=lawyer,
            full_name=requestor_name,
            email=requestor_email,
            address=requestor_address,
            date_of_birth=requestor_dob,
            controller_name=_extract_domain(content_url),
            controller_url=content_url,
            content_url=content_url,
            content_description=content_description,
            content_type=content_type,
            legal_citation=legal_basis.citation if legal_basis else "GDPR Art. 17"
        )
    elif basis_id == "dmca":
        return generate_dmca_notice(
            lawyer=lawyer,
            full_name=requestor_name,
            email=requestor_email,
            address=requestor_address,
            phone=requestor_phone,
            content_url=content_url,
            content_description=content_description,
            content_type=content_type
        )
    elif jurisdiction.lower() == "au":
        return generate_au_privacy_letter(
            lawyer=lawyer,
            full_name=requestor_name,
            email=requestor_email,
            address=requestor_address,
            date_of_birth=requestor_dob,
            content_url=content_url,
            content_description=content_description
        )
    else:
        return generate_defamation_cnd(
            lawyer=lawyer,
            full_name=requestor_name,
            email=requestor_email,
            address=requestor_address,
            content_url=content_url,
            content_description=content_description,
            jurisdiction=jurisdiction
        )


def generate_appeal(
    original_request: RemovalRequest,
    rejection_reason: str,
    requestor_name: str,
    requestor_email: str,
    additional_arguments: str = ""
) -> RemovalRequest:
    """Generate an appeal when initial removal request was rejected."""
    
    appeal_body = f"""
Subject: APPEAL — Reconsideration of Removal Request

Dear Data Protection Officer / Privacy Officer,

RE: Appeal of Removal Request Decision — {original_request.content_url}

I, {requestor_name}, am writing to appeal the decision to reject my previous removal request dated {original_request.created_at.strftime('%d %B %Y')}.

SECTION 1 — ORIGINAL REQUEST
Original Submission Date: {original_request.created_at.strftime('%d %B %Y')}
URL of Content: {original_request.content_url}
Legal Basis Cited: {original_request.legal_basis.name if original_request.legal_basis else 'N/A'}

SECTION 2 — REASON FOR REJECTION
Your stated reason for rejection was:
{rejection_reason}

SECTION 3 — GROUNDS FOR APPEAL
I respectfully submit the following additional information and arguments:

{additional_arguments if additional_arguments else '1. The original grounds for erasure under ' + (original_request.legal_basis.citation if original_request.legal_basis else 'applicable law') + ' remain valid and applicable.'}

SECTION 4 — RELEVANT CASE LAW AND GUIDANCE
The Court of Justice of the European Union in Google Spain v AEPD (C-131/12) established that data subjects have the right to request removal of links to information that is inadequate, irrelevant, or excessive in light of the purposes for which it was processed.

The European Data Protection Board (EDPB) Guidelines on the Right to Erasure further clarify that erasure requests must be weighed against the data subject's fundamental rights.

SECTION 5 — REQUEST
I respectfully request that you:
1. Reconsider my original removal request
2. Provide a more detailed explanation of your decision if you maintain the rejection
3. Escalate to the relevant supervisory authority if no satisfactory resolution is reached

SECTION 6 — ESCALATION
If this appeal is not resolved within one month, I will lodge a formal complaint with the relevant supervisory authority:
• UK: Information Commissioner's Office (ICO)
• EU: National Data Protection Authority

Yours faithfully,

{requestor_name}
{requestor_email}
Date: {datetime.now().strftime('%d %B %Y')}

{original_request.lawyer.signature}

---
DISCLAIMER: This appeal was prepared with AI assistance from FixMyNameOnline. This is not legal advice. Consult an attorney for complex matters.
"""

    return RemovalRequest(
        lawyer=original_request.lawyer,
        content_url=original_request.content_url,
        content_type=original_request.content_type,
        legal_basis_id=f"appeal_{original_request.legal_basis_id}",
        legal_basis=original_request.legal_basis,
        subject=f"APPEAL — Reconsideration of Removal Request — {requestor_name}",
        letter_body=appeal_body,
        legal_citations=original_request.legal_citations + [
            "CJEU Google Spain v AEPD (C-131/12)",
            "EDPB Guidelines on the Right to Erasure"
        ],
        submission_url=original_request.submission_url,
        submission_instructions=f"Submit this appeal to {original_request.lawyer.signature}. If unresolved within 30 days, escalate to supervisory authority.",
        disclaimer="AI-generated draft. Not legal advice. Consult counsel for complex matters.",
        footer="Prepared with AI assistance from FixMyNameOnline. Not legal advice. Consult counsel for complex matters. | © 2026 MadisonJade Pty Ltd"
    )


def _extract_domain(url: str) -> str:
    """Extract domain name from URL for letter."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain or "the relevant organization"
    except:
        return "the relevant organization"


# =============================================================================
# STATUTE OF LIMITATIONS
# =============================================================================

STATUTE_OF_LIMITATIONS = {
    "uk_defamation": {"years": 1, "note": "Single publication rule applies — time runs from each publication"},
    "us_defamation": {"varies": "1-6 years by state (most are 2-3 years)"},
    "eu_gdpr_complaint": {"months": 3, "note": "For supervisory authority complaints after internal exhaustion"},
    "au_defamation": {"years": 1, "note": "From date of first publication of the defamatory matter"},
    "au_privacy": {"years": 6, "note": "Under Privacy Act 1988 for civil penalty proceedings"},
    "ca_defamation": {"varies": "2-3 years by province"}
}


# =============================================================================
# TIER LIMITS
# =============================================================================

TIER_REMOVAL_LIMITS = {
    "free": {"rtbf": 0, "dmca": 0, "defamation": 0, "lawyer_review": False},
    "sentinel": {"rtbf": 0, "dmca": 0, "defamation": 0, "lawyer_review": False},
    "starter": {"rtbf": 3, "dmca": 0, "defamation": 3, "lawyer_review": False},
    "pro": {"rtbf": 10, "dmca": 5, "defamation": 10, "lawyer_review": False},
    "premium": {"rtbf": -1, "dmca": -1, "defamation": -1, "lawyer_review": False},
    "concierge": {"rtbf": -1, "dmca": -1, "defamation": -1, "lawyer_review": True}
}


def can_file_removal(tier: str, request_type: str, filed_this_period: int) -> bool:
    """Check if a customer can file a removal request based on tier limits."""
    tier = tier.lower()
    if tier not in TIER_REMOVAL_LIMITS:
        return False
    
    limit = TIER_REMOVAL_LIMITS[tier].get(request_type, 0)
    
    if limit == -1:
        return True  # Unlimited
    if limit == 0:
        return False  # Not available
    return filed_this_period < limit


def get_tier_limits(tier: str) -> dict:
    """Get removal filing limits for a tier."""
    return TIER_REMOVAL_LIMITS.get(tier.lower(), TIER_REMOVAL_LIMITS["free"])


def format_removal_as_html(request: RemovalRequest) -> str:
    """Format a removal request as HTML for display/PDF generation."""
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: 'Times New Roman', serif; font-size: 12pt; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 40px; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .subject {{ background: #f5f5f5; padding: 15px; border-left: 4px solid #ff0000; margin: 20px 0; }}
        .section {{ margin: 20px 0; }}
        .section h3 {{ color: #333; border-bottom: 1px solid #ccc; padding-bottom: 5px; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ccc; font-size: 10pt; color: #666; }}
        .disclaimer {{ background: #fff3cd; padding: 15px; border-radius: 5px; margin-top: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>FIX MY NAME ONLINE</h2>
        <p>AI-Powered Legal Request Generator</p>
        <p>Prepared by: {request.lawyer.name}</p>
        <p>Jurisdiction: {', '.join(request.lawyer.jurisdictions)}</p>
    </div>
    
    <div class="subject">
        <strong>SUBJECT:</strong> {request.subject}<br>
        <strong>DATE:</strong> {request.created_at.strftime('%d %B %Y')}
    </div>
    
    <div class="section">
        {request.letter_body.replace('\n', '<br>')}
    </div>
    
    <div class="disclaimer">
        <strong>⚠️ IMPORTANT DISCLAIMER:</strong><br>
        {request.disclaimer}<br><br>
        {request.footer}
    </div>
    
    <div class="footer">
        <p><strong>Legal Basis:</strong> {request.legal_basis.name if request.legal_basis else 'N/A'}</p>
        <p><strong>Citation:</strong> {request.legal_basis.citation if request.legal_basis else 'N/A'}</p>
        <p><strong>Expected Response:</strong> {request.legal_basis.response_days if request.legal_basis else 'N/A'} days</p>
        <p><strong>Effectiveness:</strong> {request.legal_basis.effectiveness if request.legal_basis else 'N/A'}</p>
        <p><strong>Submission URL:</strong> {request.submission_url or 'Direct submission to relevant organization'}</p>
    </div>
</body>
</html>
"""
