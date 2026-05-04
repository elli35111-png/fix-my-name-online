"""
Fix My Name Online — Universal Removal Request Generator
Jurisdiction-aware removal letter generator for worldwide coverage.
Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

from typing import Dict, List, Optional
from datetime import datetime
import re


# ============================================================================
# REMOVAL LAWS BY COUNTRY/JURISDICTION
# ============================================================================

REMOVAL_LAWS = {
    # USA
    "us": {
        "name": "United States",
        "flag": "🇺🇸",
        "laws": [
            {
                "id": "dmca",
                "name": "DMCA Takedown",
                "description": "Digital Millennium Copyright Act - for copyrighted content",
                "legal_basis": "17 U.S.C. § 512",
                "url": "https://www.copyright.gov/dmca/",
                "response_time": "10-14 days",
                "effectiveness": "High for US hosts"
            },
            {
                "id": "defamation",
                "name": "Defamation / Libel Removal",
                "description": "For false statements of fact that harm reputation",
                "legal_basis": "Common law + state statutes",
                "url": None,
                "response_time": "Varies",
                "effectiveness": "Medium - requires proof"
            },
            {
                "id": "ccpa",
                "name": "California Consumer Privacy Act",
                "description": "For CA residents - delete personal information",
                "legal_basis": "Cal. Civ. Code § 1798.100",
                "url": "https://oag.ca.gov/ccpa",
                "response_time": "45 days",
                "effectiveness": "Medium for CA residents"
            }
        ]
    },
    
    # European Union
    "eu": {
        "name": "European Union",
        "flag": "🇪🇺",
        "laws": [
            {
                "id": "gdpr_erasure",
                "name": "GDPR Right to Erasure",
                "description": "Article 17 - Delete personal data",
                "legal_basis": "Regulation (EU) 2016/679 Art. 17",
                "url": "https://gdpr.eu/article-17-right-to-the-erasure-of-personal-data/",
                "response_time": "30 days",
                "effectiveness": "High within EU"
            },
            {
                "id": "right_to_be_forgotten",
                "name": "Right to Be Forgotten",
                "description": "Search engine de-listing from EU results",
                "legal_basis": "CJEU Google Spain v AEPD (2014)",
                "url": "https://www.google.com/webmasters/tools/legal-removal-request",
                "response_time": "Variable",
                "effectiveness": "High for search results"
            },
            {
                "id": "defamation_eu",
                "name": "Defamation",
                "description": "Civil remedy for reputation damage",
                "legal_basis": "Member state law varies",
                "url": None,
                "response_time": "Varies",
                "effectiveness": "Medium"
            }
        ]
    },
    
    # United Kingdom
    "uk": {
        "name": "United Kingdom",
        "flag": "🇬🇧",
        "laws": [
            {
                "id": "uk_gdpr",
                "name": "UK GDPR / Data erasure",
                "description": "Right to erasure of personal data",
                "legal_basis": "UK GDPR Art. 17, Data Protection Act 2018",
                "url": "https://ico.org.uk/for-organisations/uk-gdpr-guidance/",
                "response_time": "30 days",
                "effectiveness": "High within UK"
            },
            {
                "id": "defamation_act",
                "name": "Defamation Act 2013",
                "description": "Remove false statements causing serious harm",
                "legal_basis": "Defamation Act 2013",
                "url": "https://www.legislation.gov.uk/ukpga/2013/26/contents",
                "response_time": "Varies",
                "effectiveness": "High for serious harm"
            },
            {
                "id": "rtbf_uk",
                "name": "Right to Be Forgotten",
                "description": "Search engine de-listing from UK results",
                "legal_basis": "ICO guidance + CJEU precedent",
                "url": "https://ico.org.uk/for-organisations/guide-to-data-protection/",
                "response_time": "Variable",
                "effectiveness": "High for search results"
            }
        ]
    },
    
    # Australia
    "au": {
        "name": "Australia",
        "flag": "🇦🇺",
        "laws": [
            {
                "id": "privacy_act",
                "name": "Privacy Act 1988",
                "description": "Australian Privacy Principles - delete personal info",
                "legal_basis": "Privacy Act 1988 (Cth)",
                "url": "https://www.oaic.gov.au/",
                "response_time": "30 days",
                "effectiveness": "Medium-High"
            },
            {
                "id": "defamation_au",
                "name": "Defamation",
                "description": "State-based defamation laws",
                "legal_basis": "Civil Liability Act 2002 (NSW) and equivalents",
                "url": None,
                "response_time": "Varies",
                "effectiveness": "Medium"
            }
        ]
    },
    
    # Canada
    "ca": {
        "name": "Canada",
        "flag": "🇨🇦",
        "laws": [
            {
                "id": "pipeda",
                "name": "PIPEDA - Access & Erasure",
                "description": "Personal Information Protection and Electronic Documents Act",
                "legal_basis": "S.C. 2000, c. 5",
                "url": "https://www.priv.gc.ca/",
                "response_time": "30 days",
                "effectiveness": "Medium"
            },
            {
                "id": "defamation_ca",
                "name": "Defamation",
                "description": "Common law libel + Quebec Civil Code",
                "legal_basis": "Common law",
                "url": None,
                "response_time": "Varies",
                "effectiveness": "Medium"
            }
        ]
    },
    
    # Brazil
    "br": {
        "name": "Brazil",
        "flag": "🇧🇷",
        "laws": [
            {
                "id": "lgpd",
                "name": "LGPD - Right to Erasure",
                "description": "Lei Geral de Proteção de Dados",
                "legal_basis": "Lei 13.709/2018 Art. 18",
                "url": "https://www.gov.br/cidadania/pt-br/acesso-a-informacao/lgpd",
                "response_time": "15 days",
                "effectiveness": "High within Brazil"
            }
        ]
    },
    
    # Japan
    "jp": {
        "name": "Japan",
        "flag": "🇯🇵",
        "laws": [
            {
                "id": "appi",
                "name": "APPI - Right to Erasure",
                "description": "Act on the Protection of Personal Information",
                "legal_basis": "Act No. 57 of 2003, as amended",
                "url": "https://www.ppc.go.jp/",
                "response_time": "Varies",
                "effectiveness": "Medium"
            }
        ]
    },
    
    # Generic / Worldwide
    "worldwide": {
        "name": "Worldwide / Other",
        "flag": "🌍",
        "laws": [
            {
                "id": "unsubscribe",
                "name": "Data Deletion Request",
                "description": "General request to delete personal data",
                "legal_basis": "Various local laws",
                "url": None,
                "response_time": "30-60 days",
                "effectiveness": "Low-Medium"
            },
            {
                "id": "defamation_general",
                "name": "Defamation Notice",
                "description": "Formal notice of defamatory content",
                "legal_basis": "Local civil law",
                "url": None,
                "response_time": "Varies",
                "effectiveness": "Varies"
            }
        ]
    }
}


# ============================================================================
# TEMPLATE GENERATORS BY LAW TYPE
# ============================================================================

def generate_dmca_takedown(content_url: str, original_url: str, description: str,
                           full_name: str, email: str, signature: str = None) -> str:
    """Generate a DMCA takedown notice for US-based content."""
    sig = signature or full_name
    return f"""DMCA TAKEDOWN NOTICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}

To: DMCA Agent
Website: {content_url}

I, the undersigned, declare under penalty of perjury that:

1. I am the copyright owner of the material described below, or I am 
   authorized to act on behalf of the owner.

2. I have a good faith belief that the material at {original_url} 
   is infringing my copyright.

3. The original material or content I own is located at: [ORIGINAL SOURCE]

DESCRIPTION OF COPYRIGHTED WORK:
{description}

ORIGINAL COPYRIGHTED WORK LOCATION:
[Provide URL where your original content exists]

INFRINGING MATERIAL LOCATION:
{original_url}

I request that the webmaster at {content_url} immediately remove or disable 
access to the infringing material.

I understand that under Section 512(f) of the DMCA, anyone who knowingly 
and materially misrepresents that material or activity is infringing may 
be subject to liability.

HANDLER'S CONTACT INFORMATION:
Full Name: {full_name}
Email: {email}
Phone: [YOUR PHONE NUMBER]
Address: [YOUR ADDRESS]

Signature: {sig}
Date: {datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
This notice is provided in good faith.
"""


def generate_gdpr_erasure(country: str, content_url: str, content_description: str,
                          full_name: str, email: str, address: str = None,
                          nationality: str = None) -> str:
    """Generate a GDPR Article 17 erasure request for EU/EEA residents."""
    country_name = REMOVAL_LAWS.get(country.lower(), {}).get("name", country)
    sig = full_name
    
    addr_block = f"""
Postal Address:
{address or '[YOUR FULL ADDRESS]'}\n""" if address else "\n"
    
    return f"""GDPR ERASURE REQUEST — ARTICLE 17
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}

Data Controller / Website Operator:
[Website Name]
Contact: {content_url}

RE: Request for Erasure of Personal Data under Article 17 GDPR

Dear Data Controller,

I, the undersigned, am writing to exercise my right to erasure of personal 
data under Article 17 of the General Data Protection Regulation (EU) 2016/679.

MY DETAILS:
Full Name: {full_name}
Email: {email}{addr_block}
Nationality: {nationality or '[YOUR NATIONALITY]'}

DESCRIPTION OF DATA PROCESSED:
{content_description}

SPECIFIC URLs/PAGES CONTAINING MY DATA:
{content_url}
[Add any other URLs where your data appears]

LEGAL BASIS FOR REQUEST:
Under Article 17 GDPR, I request that you:
(a) erase the above-mentioned personal data
(b) cease making the data available to third parties
(c) cease any processing of the above-mentioned personal data

This request applies to all copies of the above-mentioned personal data, 
including backups and cached versions.

If you do not respond to this request within one month of receipt, I will 
file a complaint with the relevant supervisory authority (Data Protection 
Commissioner) and may seek judicial remedy under Article 79 GDPR.

Please confirm when you have processed this request.

Yours sincerely,

{sig}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
GDPR Rights: https://gdpr.eu/article-17-right-to-the-erasure-of-personal-data/
"""


def generate_uk_gdpr_request(content_url: str, content_description: str,
                               full_name: str, email: str, address: str = None) -> str:
    """Generate a UK GDPR erasure request."""
    sig = full_name
    addr_block = f"\nAddress:\n{address or '[YOUR FULL ADDRESS]'}\n" if address else "\n"
    
    return f"""UK GDPR DATA ERASURE REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}

To: Data Controller / Website Operator
Website: {content_url}

RE: Subject Access Request & Right to Erasure under UK GDPR

Dear Sir/Madam,

I am writing to exercise my rights under the UK General Data Protection 
Regulation (UK GDPR) and the Data Protection Act 2018.

MY DETAILS:
Full Name: {full_name}
Email: {email}{addr_block}

PERSONAL DATA I WISH TO BE ERASED:
{content_description}

URLS WHERE MY DATA APPEARS:
{content_url}
[Add any other relevant URLs]

Under Article 17 UK GDPR, I request that you:
1. Erase all personal data relating to me as listed above
2. Cease disclosure of this data to third parties
3. Remove all cached or archived copies

Under Article 15 UK GDPR, I also request confirmation of:
- Whether personal data about me is being processed
- The categories of data held
- The purposes of processing
- The recipients to whom data has been disclosed

If you do not comply with this request within one month, I will complain 
to the Information Commissioner's Office (ICO) at ico.org.uk.

Yours faithfully,

{sig}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
ICO Guidance: https://ico.org.uk/your-data-matters/
"""


def generate_defamation_notice(jurisdiction: str, content_url: str,
                               defamatory_statement: str,
                               full_name: str, email: str, address: str = None,
                               lawyer_name: str = None) -> str:
    """Generate a defamation removal notice."""
    country_name = REMOVAL_LAWS.get(jurisdiction.lower(), {}).get("name", jurisdiction)
    sig = full_name
    addr_block = f"\nAddress:\n{address or '[YOUR ADDRESS]'}\n" if address else "\n"
    solicitor_line = f"\nSolicitor: {lawyer_name}" if lawyer_name else ""

    date_str = datetime.now().strftime('%B %d, %Y')

    return f"""DEFAMATION REMOVAL NOTICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {date_str}

To: The Publisher / Webmaster
Website: {content_url}

RE: FORMAL DEMAND FOR REMOVAL OF DEFAMATORY CONTENT

Dear Sir/Madam,

I, the undersigned, formally request the immediate removal of defamatory
content that you have published regarding me.

MY DETAILS:
Full Name: {full_name}
Email: {email}{addr_block}

DEFAMATORY CONTENT LOCATION:
{content_url}

STATEMENT(S) CLAIMED TO BE DEFAMATORY:
"{defamatory_statement}"

NATURE OF HARM:
The above content falsely portrays me in a negative light and has caused /
is likely to cause serious harm to my reputation. The statements are false
and I have evidence to prove this.

LEGAL POSITION:
The publication of false statements of fact constitutes defamation under
{jurisdiction} law. As the publisher of this content, you may also be liable
for defamation.

DEMAND:
I hereby demand that you:
1. Immediately remove the defamatory content at {content_url}
2. Issue a public apology correcting the false statements
3. Provide written confirmation of compliance within 7 days

FAILURE TO COMPLY:
If you fail to remove this content within 7 days of this notice, I will
have no alternative but to commence legal proceedings seeking:
- Damages for defamation
- Costs of this action
- An injunction preventing further publication

This notice is provided without prejudice and without admission of liability.

Yours faithfully,

{sig}
{date_str}{solicitor_line}

---
Sent via FixMyNameOnline.com
This is a formal legal notice. Keep copies for your records.
"""


def generate_ccpa_request(content_url: str, personal_info_description: str,
                          full_name: str, email: str) -> str:
    """Generate a California Consumer Privacy Act (CCPA) request."""
    return f"""CALIFORNIA CONSUMER PRIVACY ACT REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}

To: Business / Data Controller
Website: {content_url}

RE: California Consumer Privacy Act — Right to Delete

Dear Sir/Madam,

I am a California resident exercising my rights under the California 
Consumer Privacy Act of 2018 (CCPA).

MY DETAILS:
Full Name: {full_name}
Email: {email}

PERSONAL INFORMATION TO BE DELETED:
{personal_info_description}

URLS WHERE MY DATA APPEARS:
{content_url}

UNDER CCPA, I REQUEST:
1. Deletion of all personal information you have collected about me
2. That any service providers also delete my data
3. Confirmation of deletion within 45 days

If you fail to respond, I may file a complaint with the California 
Attorney General's Office.

Yours faithfully,

{full_name}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
CCPA Info: https://oag.ca.gov/ccpa
"""


def generate_universal_request(jurisdiction: str, law_type: str,
                                content_url: str, content_description: str,
                                full_name: str, email: str, 
                                address: str = None, nationality: str = None) -> str:
    """Generate a universal/generic removal request."""
    country_name = REMOVAL_LAWS.get(jurisdiction.lower(), {}).get("name", jurisdiction)
    sig = full_name
    
    addr_block = f"\nAddress:\n{address or '[YOUR ADDRESS]'}\n" if address else "\n"
    nat_block = f"Nationality: {nationality or '[YOUR NATIONALITY]'}\n" if nationality else ""
    
    return f"""DATA DELETION / REMOVAL REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}

To: Website Operator / Data Controller
Website: {content_url}

RE: Request for Removal of Personal Data

Dear Sir/Madam,

I, the undersigned, request the removal of personal data concerning me 
from your platform/website.

MY DETAILS:
Full Name: {full_name}
Email: {email}{addr_block}{nat_block}
Jurisdiction: {country_name}

DATA/CONTENT TO BE REMOVED:
{content_description}

LOCATION OF DATA:
{content_url}

BASIS FOR REQUEST:
I believe this data/content violates my rights under applicable data 
protection and privacy laws in {country_name} and/or internationally.

If this data constitutes defamation, I further claim that the content 
is false, harmful, and defamatory.

REQUEST:
I formally request that you:
1. Remove or delete the above-mentioned data/content
2. Confirm removal within 30 days
3. Provide written confirmation once completed

If I do not receive a response within 30 days, I will consider this 
matter unresolved and may seek further remedies.

Yours sincerely,

{sig}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
This request is made in good faith.
"""


# ============================================================================
# MAIN GENERATOR FUNCTION
# ============================================================================

def generate_removal_request(
    jurisdiction: str,
    law_type: str,
    content_url: str,
    content_description: str,
    full_name: str,
    email: str,
    address: str = None,
    nationality: str = None,
    original_url: str = None,
    defamatory_statement: str = None,
    signature: str = None
) -> str:
    """
    Generate a jurisdiction-aware removal request letter.
    
    Args:
        jurisdiction: Country code (us, eu, uk, au, ca, br, jp, worldwide)
        law_type: Type of removal (dmca, gdpr_erasure, right_to_be_forgotten, 
                  defamation, privacy_act, etc.)
        content_url: URL where the content appears
        content_description: Description of the content to remove
        full_name: Requester's full name
        email: Requester's email
        address: Requester's postal address (optional)
        nationality: Requester's nationality (optional)
        original_url: For DMCA - URL of original copyrighted content
        defamatory_statement: For defamation - the exact statement
        signature: Signature name (defaults to full_name)
    
    Returns:
        Formatted removal request letter
    """
    law_type = law_type.lower()
    jurisdiction = jurisdiction.lower()
    
    # DMCA - US specific
    if law_type == "dmca":
        if not original_url:
            original_url = "[PROVIDE URL OF YOUR ORIGINAL/COPYRIGHTED CONTENT]"
        return generate_dmca_takedown(
            content_url, original_url, content_description,
            full_name, email, signature
        )
    
    # GDPR Erasure - EU
    elif law_type in ["gdpr_erasure", "gdpr_delete", "art17"]:
        return generate_gdpr_erasure(
            jurisdiction, content_url, content_description,
            full_name, email, address, nationality
        )
    
    # UK GDPR
    elif law_type in ["uk_gdpr", "uk_erasure", "data_protection_act"]:
        return generate_uk_gdpr_request(
            content_url, content_description,
            full_name, email, address
        )
    
    # CCPA - California
    elif law_type in ["ccpa", "california"]:
        return generate_ccpa_request(
            content_url, content_description,
            full_name, email
        )
    
    # Defamation - any jurisdiction
    elif law_type in ["defamation", "libel", "defamation_act"]:
        if not defamatory_statement:
            defamatory_statement = "[DESCRIBE THE FALSE STATEMENTS]"
        return generate_defamation_notice(
            jurisdiction, content_url, defamatory_statement,
            full_name, email, address
        )
    
    # Universal / fallback
    else:
        return generate_universal_request(
            jurisdiction, law_type,
            content_url, content_description,
            full_name, email, address, nationality
        )


def get_jurisdictions() -> List[Dict]:
    """Get list of all available jurisdictions."""
    return [
        {"code": code, "name": data["name"], "flag": data["flag"]}
        for code, data in REMOVAL_LAWS.items()
    ]


def get_laws_for_jurisdiction(jurisdiction: str) -> List[Dict]:
    """Get available laws for a specific jurisdiction."""
    return REMOVAL_LAWS.get(jurisdiction.lower(), {}).get("laws", [])


def detect_jurisdiction_from_url(url: str) -> str:
    """
    Attempt to detect jurisdiction from a URL.
    Returns country code or 'worldwide' as fallback.
    """
    url_lower = url.lower()
    
    # Country-specific TLDs
    tld_mapping = {
        ".co.uk": "uk", ".org.uk": "uk", ".net.uk": "uk", ".gov.uk": "uk",
        ".de": "eu", ".fr": "eu", ".it": "eu", ".es": "eu", ".nl": "eu",
        ".eu": "eu",
        ".com.au": "au", ".org.au": "au", ".net.au": "au", ".gov.au": "au",
        ".ca": "ca", ".qc.ca": "ca",
        ".jp": "jp",
        ".br": "br",
    }
    
    for tld, country in tld_mapping.items():
        if tld in url_lower:
            return country
    
    # Common US domains
    if any(x in url_lower for x in [".com", ".net", ".org", ".io", ".co"]):
        # Check for common non-US indicators
        non_us = [".co.uk", ".de", ".fr", ".au", ".ca", ".jp", ".br", ".eu"]
        if not any(x in url_lower for x in non_us):
            return "us"
    
    return "worldwide"


# ============================================================================
# ESCALATION TEMPLATES
# ============================================================================

def generate_escalation_letter(original_url: str, original_request_date: str,
                               full_name: str, email: str,
                               escalation_type: str = "follow_up") -> str:
    """Generate a follow-up/escalation letter."""
    
    templates = {
        "follow_up": f"""FOLLOW-UP REMOVAL REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}
Original Request Date: {original_request_date}

To: Website Operator / Data Controller
Website: {original_url}

RE: FOLLOW-UP — Removal Request Not Yet Addressed

Dear Sir/Madam,

I previously submitted a request to remove my personal data/defamatory 
content from your platform on approximately {original_request_date}.

As of today's date, I have not received a response or observed any action 
taken to address my request.

I am following up to remind you of your legal obligations. Depending on 
the applicable law (GDPR, UK GDPR, CCPA, or other regulations), you are 
required to respond to data subject requests within a specified timeframe.

If you continue to ignore this request, I will:
1. File a complaint with the relevant supervisory authority
2. Seek judicial remedies available under applicable law
3. Pursue all available legal remedies

Please confirm within the next 7 days what action you have taken.

Yours sincerely,

{full_name}
{email}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
""",
        
        "ico_complaint": f"""SUPERVISORY AUTHORITY COMPLAINT DRAFT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}
Original Request Date: {original_request_date}

To: Information Commissioner's Office (ICO)
Website: https://ico.org.uk

RE: Complaint — Failure to Respond to Data Erasure Request

Dear ICO,

I am writing to lodge a formal complaint regarding a data controller/website 
operator who has failed to respond to my data subject access and erasure request.

MY DETAILS:
Name: {full_name}
Email: {email}

WEBSITE THAT HAS FAILED TO RESPOND:
{original_url}

DATE I SUBMITTED ORIGINAL REQUEST:
{original_request_date}

SUMMARY OF MY REQUEST:
I requested erasure of my personal data under UK GDPR Article 17.

NO RESPONSE RECEIVED:
Despite follow-up communications, the data controller has failed to respond 
within the statutory 30-day period.

EVIDENCE:
Please find attached copies of:
- My original removal/erasure request
- Any follow-up communications sent
- Evidence of the personal data still being processed/published

I request that the ICO investigate this matter and take appropriate action.

Yours faithfully,

{full_name}
{email}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
This is a draft. Review and customize before submitting to ICO.
""",
        
        "legal_threat": f"""FINAL WARNING — LEGAL ACTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Date: {datetime.now().strftime('%B %d, %Y')}
Original Request Date: {original_request_date}

To: Website Operator / Legal Department
Website: {original_url}

RE: FINAL WARNING — Intent to Commence Legal Proceedings

Dear Sir/Madam,

This letter constitutes my FINAL warning before commencing legal proceedings.

I first requested removal of defamatory content / personal data on 
{original_request_date}. Despite multiple follow-ups, you have failed to:

1. Remove the offending content
2. Respond to my communications
3. Acknowledge my legal rights

I hereby put you on NOTICE that if I do not receive:

- Written confirmation of removal within 7 days, OR
- A substantive response within 3 days

I will immediately commence legal proceedings without further notice. 
This may include claims for:

- Defamation damages
- Data protection violations
- Costs of this action
- Injunctive relief

I reserve all rights and remedies available to me at law and in equity.

This is a serious legal matter.

Yours faithfully,

{full_name}
{email}
{datetime.now().strftime('%B %d, %Y')}

---
Sent via FixMyNameOnline.com
CONSULT A SOLICITOR BEFORE SENDING THIS LETTER
"""
    }
    
    return templates.get(escalation_type, templates["follow_up"])