"""
Fix My Name Online — Evidence Pack Generator
Generates professional PDF reports for customer suppression progress.
Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
import json
import os


# =============================================================================
# EVIDENCE PACK DATA STRUCTURES
# =============================================================================

@dataclass
class EvidenceSection:
    title: str
    content: str
    data: Optional[Dict] = None
    subsections: Optional[List['EvidenceSection']] = None


@dataclass
class EvidencePack:
    customer_name: str
    customer_email: str
    tier: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    
    # Metrics
    suppression_score: int
    previous_score: int
    content_published: int
    social_published: int
    platforms_active: int
    negative_tracked: int
    negative_suppressed: int
    alerts_triggered: int
    
    # Removal
    removal_requests_filed: int
    removal_requests_approved: int
    removal_requests_rejected: int
    removal_requests_pending: int
    
    # Content
    articles: List[Dict]
    social_posts: List[Dict]
    alerts: List[Dict]
    removal_requests: List[Dict]
    
    # Recommendations
    recommendations: List[str]
    
    # Scorecard
    scorecard: Dict[str, str]


# =============================================================================
# SCORECARD DEFINITIONS
# =============================================================================

SCORECARD_ITEMS = {
    "content_volume": {
        "Excellent": 150,
        "Good": 100,
        "Fair": 50,
        "Poor": 0
    },
    "platform_diversity": {
        "Excellent": 10,
        "Good": 7,
        "Fair": 4,
        "Poor": 0
    },
    "suppression_progress": {
        "Excellent": 80,
        "Good": 50,
        "Fair": 25,
        "Poor": 0
    },
    "removal_success": {
        "Excellent": 0.6,  # 60%+ approval
        "Good": 0.4,
        "Fair": 0.2,
        "Poor": 0.0
    }
}


def get_score_rating(value: float, thresholds: Dict[str, float]) -> str:
    """Get rating based on thresholds."""
    if value >= thresholds.get("Excellent", 999):
        return "Excellent"
    elif value >= thresholds.get("Good", 999):
        return "Good"
    elif value >= thresholds.get("Fair", 999):
        return "Fair"
    else:
        return "Poor"


# =============================================================================
# GENERATE EVIDENCE PACK
# =============================================================================

def generate_evidence_pack(customer: dict, period_days: int = 30) -> EvidencePack:
    """Generate an Evidence Pack from customer data."""
    
    tier = customer.get("tier", "free")
    now = datetime.now()
    period_start = now - datetime.timedelta(days=period_days)
    
    # Get published content from period
    published = customer.get("published_content", [])
    period_content = [
        p for p in published
        if p.get("timestamp") and 
        datetime.fromisoformat(p["timestamp"].replace("Z", "+00:00")) > period_start
    ] if published else []
    
    # Count articles vs social
    articles = [p for p in period_content if "article" in p.get("platforms", [])]
    social = [p for p in period_content if any(s in p.get("platforms", []) for s in ["twitter", "linkedin", "facebook"])]
    
    # Platform count
    platforms = set()
    for p in period_content:
        for plat in p.get("platforms", []):
            platforms.add(plat)
    
    # Alerts
    alerts = customer.get("alerts", [])
    period_alerts = [
        m for a in alerts
        for m in a.get("mentions", [])
        if a.get("created_at") and 
        datetime.fromisoformat(a["created_at"].replace("Z", "+00:00")) > period_start
    ] if alerts else []
    
    # Removal requests
    removals = customer.get("removal_requests", [])
    period_removals = [
        r for r in removals
        if r.get("created_at") and
        datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) > period_start
    ] if removals else []
    
    # Removal stats
    removal_approved = len([r for r in period_removals if r.get("status") == "approved"])
    removal_rejected = len([r for r in period_removals if r.get("status") == "rejected"])
    removal_pending = len([r for r in period_removals if r.get("status") == "pending"])
    
    # Suppression score
    current_score = customer.get("suppression_score", 0)
    previous_score = max(0, current_score - int(len(period_content) * 5))
    
    # Scorecard
    scorecard = {
        "Content Volume": get_score_rating(len(period_content), SCORECARD_ITEMS["content_volume"]),
        "Platform Diversity": get_score_rating(len(platforms), SCORECARD_ITEMS["platform_diversity"]),
        "Suppression Progress": get_score_rating(current_score, SCORECARD_ITEMS["suppression_progress"]),
        "Removal Success": get_score_rating(
            removal_approved / len(period_removals) if period_removals else 0,
            SCORECARD_ITEMS["removal_success"]
        )
    }
    
    # Recommendations
    recommendations = []
    
    if current_score < 25:
        recommendations.append("Focus on generating and publishing content consistently. Aim for 50+ pieces to reach Phase 2.")
    elif current_score < 50:
        recommendations.append("Great progress! Expand to additional platforms to accelerate suppression.")
    elif current_score < 75:
        recommendations.append("Strong presence forming. Monitor for new negative content and file RTBF requests for high-impact removals.")
    else:
        recommendations.append("Excellent progress! Maintain consistent publishing cadence to lock in results.")
    
    if len(platforms) < 5:
        recommendations.append("Consider expanding to 5+ platforms for maximum coverage.")
    
    if removal_pending > 0:
        recommendations.append(f"Track {removal_pending} pending removal request(s). Follow up if no response within legal timeframe.")
    
    if not any(p in platforms for p in ["fps_main", "fpa_main"]):
        recommendations.append("FPS Owned Media publishing available on your tier. Publish to firstpagestrategy.org for domain authority boost.")
    
    return EvidencePack(
        customer_name=customer.get("name", "Customer"),
        customer_email=customer.get("email", "N/A"),
        tier=tier,
        generated_at=now,
        period_start=period_start,
        period_end=now,
        suppression_score=current_score,
        previous_score=previous_score,
        content_published=len(period_content),
        social_published=len(social),
        platforms_active=len(platforms),
        negative_tracked=customer.get("negative_results", []).__len__() if isinstance(customer.get("negative_results"), list) else 0,
        negative_suppressed=0,
        alerts_triggered=len(period_alerts),
        removal_requests_filed=len(period_removals),
        removal_requests_approved=removal_approved,
        removal_requests_rejected=removal_rejected,
        removal_requests_pending=removal_pending,
        articles=articles[:20],  # Limit for PDF
        social_posts=social[:20],
        alerts=period_alerts[:10],
        removal_requests=period_removals[:10],
        recommendations=recommendations,
        scorecard=scorecard
    )


# =============================================================================
# FORMAT AS HTML
# =============================================================================

def format_evidence_pack_html(pack: EvidencePack) -> str:
    """Format Evidence Pack as HTML for PDF conversion."""
    
    score_color = {
        "Excellent": "#00ff00",
        "Good": "#88ff00",
        "Fair": "#ffaa00",
        "Poor": "#ff4444"
    }
    
    tier_badge = {
        "free": "FREE",
        "sentinel": "SENTINEL",
        "starter": "STARTER",
        "pro": "PRO",
        "premium": "PREMIUM",
        "concierge": "CONCIERGE"
    }.get(pack.tier, pack.tier.upper())
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 11pt; line-height: 1.5; color: #333; background: #fff; }}
        
        .page {{ padding: 40px; max-width: 800px; margin: 0 auto; }}
        
        .header {{ text-align: center; border-bottom: 3px solid #ff0000; padding-bottom: 30px; margin-bottom: 30px; }}
        .header h1 {{ font-size: 28pt; color: #1a1a1a; margin-bottom: 5px; }}
        .header .brand {{ font-size: 12pt; color: #888; letter-spacing: 2px; }}
        .header .tier {{ display: inline-block; background: #ff0000; color: white; padding: 4px 16px; border-radius: 20px; font-size: 10pt; font-weight: bold; margin-top: 10px; letter-spacing: 1px; }}
        
        .meta {{ background: #f8f8f8; padding: 20px; border-radius: 8px; margin-bottom: 30px; font-size: 10pt; }}
        .meta table {{ width: 100%; }}
        .meta td {{ padding: 4px 0; }}
        .meta td:first-child {{ color: #888; width: 150px; }}
        
        .section {{ margin-bottom: 35px; page-break-inside: avoid; }}
        .section h2 {{ font-size: 14pt; color: #1a1a1a; border-left: 4px solid #ff0000; padding-left: 12px; margin-bottom: 15px; }}
        
        .score-ring {{ text-align: center; margin: 30px 0; }}
        .score-ring svg {{ transform: rotate(-90deg); }}
        .score-ring text {{ transform: rotate(90deg); text-anchor: middle; }}
        .score-display {{ font-size: 48pt; font-weight: bold; color: #1a1a1a; text-align: center; margin-top: -60px; }}
        .score-display span {{ font-size: 14pt; color: #888; font-weight: normal; }}
        
        .metrics-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }}
        .metric-card {{ background: #f8f8f8; border-radius: 8px; padding: 20px; text-align: center; }}
        .metric-card .value {{ font-size: 24pt; font-weight: bold; color: #1a1a1a; }}
        .metric-card .label {{ font-size: 9pt; color: #888; text-transform: uppercase; letter-spacing: 1px; margin-top: 5px; }}
        .metric-card.highlight {{ background: linear-gradient(135deg, #ff0000, #cc0000); }}
        .metric-card.highlight .value {{ color: white; }}
        .metric-card.highlight .label {{ color: rgba(255,255,255,0.8); }}
        
        .scorecard {{ width: 100%; border-collapse: collapse; }}
        .scorecard th {{ background: #1a1a1a; color: white; padding: 10px 15px; text-align: left; font-size: 10pt; }}
        .scorecard td {{ padding: 10px 15px; border-bottom: 1px solid #eee; }}
        .scorecard .rating {{ font-weight: bold; padding: 4px 12px; border-radius: 20px; display: inline-block; font-size: 9pt; }}
        
        .recommendations {{ background: #fff8e6; border-left: 4px solid #ffaa00; padding: 20px; border-radius: 0 8px 8px 0; }}
        .recommendations li {{ margin: 8px 0; padding-left: 5px; }}
        
        .content-list {{ font-size: 10pt; }}
        .content-list li {{ padding: 8px 0; border-bottom: 1px solid #eee; }}
        .content-list .url {{ color: #0066cc; font-size: 9pt; }}
        .content-list .meta {{ font-size: 9pt; color: #888; background: none; padding: 0; }}
        
        .removal-table {{ width: 100%; border-collapse: collapse; font-size: 10pt; }}
        .removal-table th {{ background: #1a1a1a; color: white; padding: 10px; text-align: left; }}
        .removal-table td {{ padding: 10px; border-bottom: 1px solid #eee; }}
        .removal-table .status {{ padding: 3px 10px; border-radius: 20px; font-size: 9pt; font-weight: bold; }}
        .removal-table .approved {{ background: #d4edda; color: #155724; }}
        .removal-table .rejected {{ background: #f8d7da; color: #721c24; }}
        .removal-table .pending {{ background: #fff3cd; color: #856404; }}
        .removal-table .draft {{ background: #e2e3e5; color: #383d41; }}
        
        .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #eee; font-size: 8pt; color: #888; text-align: center; }}
        .footer .disclaimer {{ background: #f8f8f8; padding: 15px; border-radius: 8px; margin-bottom: 15px; text-align: left; }}
        
        @media print {{
            .page {{ padding: 20px; }}
            .section {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="page">
        <!-- HEADER -->
        <div class="header">
            <div class="brand">FIX MY NAME ONLINE</div>
            <h1>Suppression Progress Report</h1>
            <div class="tier">{tier_badge} TIER</div>
        </div>
        
        <!-- META -->
        <div class="meta">
            <table>
                <tr><td>Generated:</td><td>{pack.generated_at.strftime('%d %B %Y, %H:%M')}</td></tr>
                <tr><td>Report Period:</td><td>{pack.period_start.strftime('%d %B %Y')} — {pack.period_end.strftime('%d %B %Y')}</td></tr>
                <tr><td>Customer:</td><td>{pack.customer_name}</td></tr>
                <tr><td>Email:</td><td>{pack.customer_email}</td></tr>
            </table>
        </div>
        
        <!-- SUPPRESSION SCORE -->
        <div class="section">
            <h2>Suppression Score</h2>
            <div class="score-ring">
                <svg width="200" height="200" viewBox="0 0 200 200">
                    <circle cx="100" cy="100" r="85" fill="none" stroke="#eee" stroke-width="15"/>
                    <circle cx="100" cy="100" r="85" fill="none" stroke="#ff0000" stroke-width="15"
                            stroke-dasharray="{pack.suppression_score * 5.34} 534" stroke-linecap="round"/>
                </svg>
                <div class="score-display">{pack.suppression_score}<span>/100</span></div>
            </div>
            <p style="text-align: center; color: #666; font-size: 10pt;">
                Previous Score: {pack.previous_score}/100 &nbsp;|&nbsp; 
                Change: {'+' if pack.suppression_score - pack.previous_score > 0 else ''}{pack.suppression_score - pack.previous_score} points
            </p>
            <p style="text-align: center; color: #888; font-size: 10pt; margin-top: 10px;">
                {"🌟 Excellent progress! You're dominating search results." if pack.suppression_score >= 75 else
                 "📈 Good momentum. Keep publishing to accelerate." if pack.suppression_score >= 50 else
                 "⚡ Building foundation. Consistency is key." if pack.suppression_score >= 25 else
                 "🚀 Just starting. Generate and publish content consistently."}
            </p>
        </div>
        
        <!-- KEY METRICS -->
        <div class="section">
            <h2>Key Metrics</h2>
            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="value">{pack.content_published}</div>
                    <div class="label">Content Published</div>
                </div>
                <div class="metric-card">
                    <div class="value">{pack.social_published}</div>
                    <div class="label">Social Posts</div>
                </div>
                <div class="metric-card">
                    <div class="value">{pack.platforms_active}</div>
                    <div class="label">Active Platforms</div>
                </div>
                <div class="metric-card highlight">
                    <div class="value">{pack.alerts_triggered}</div>
                    <div class="label">Alerts Triggered</div>
                </div>
            </div>
        </div>
        
        <!-- SCORECARD -->
        <div class="section">
            <h2>Performance Scorecard</h2>
            <table class="scorecard">
                <thead>
                    <tr><th>Metric</th><th>Rating</th><th>Details</th></tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Content Volume</td>
                        <td><span class="rating" style="background: {score_color.get(pack.scorecard.get('Content Volume', 'Poor'), '#ff4444')}; color: white;">{pack.scorecard.get('Content Volume', 'N/A')}</span></td>
                        <td>{pack.content_published} pieces published this period</td>
                    </tr>
                    <tr>
                        <td>Platform Diversity</td>
                        <td><span class="rating" style="background: {score_color.get(pack.scorecard.get('Platform Diversity', 'Poor'), '#ff4444')}; color: white;">{pack.scorecard.get('Platform Diversity', 'N/A')}</span></td>
                        <td>{pack.platforms_active} platforms active</td>
                    </tr>
                    <tr>
                        <td>Suppression Progress</td>
                        <td><span class="rating" style="background: {score_color.get(pack.scorecard.get('Suppression Progress', 'Poor'), '#ff4444')}; color: white;">{pack.scorecard.get('Suppression Progress', 'N/A')}</span></td>
                        <td>Score: {pack.suppression_score}/100</td>
                    </tr>
                    <tr>
                        <td>Removal Success</td>
                        <td><span class="rating" style="background: {score_color.get(pack.scorecard.get('Removal Success', 'Poor'), '#ff4444')}; color: white;">{pack.scorecard.get('Removal Success', 'N/A')}</span></td>
                        <td>{pack.removal_requests_approved}/{pack.removal_requests_filed or 'N/A'} approved</td>
                    </tr>
                </tbody>
            </table>
        </div>
        
        <!-- RECOMMENDATIONS -->
        <div class="section">
            <h2>Recommendations</h2>
            <div class="recommendations">
                <ol>
                    {"".join(f"<li>{r}</li>" for r in pack.recommendations)}
                </ol>
            </div>
        </div>
        
        <!-- CONTENT PUBLISHED -->
        {"".join(f"""
        <div class="section">
            <h2>Content Published ({len(pack.articles)} articles)</h2>
            <ul class="content-list">
                {chr(10).join(f'<li><strong>{a.get("title", a.get("keyword", "Untitled"))}</strong><br><span class="meta">Platforms: {", ".join(a.get("platforms", ["N/A"])[:5])} &nbsp;|&nbsp; {a.get("timestamp", "N/A")[:10]}</span></li>' for a in pack.articles[:20])}
            </ul>
        </div>
        """ if pack.articles else '<div class="section"><h2>Content Published</h2><p>No content published in this period.</p></div>')}
        
        <!-- REMOVAL REQUESTS -->
        {"".join(f"""
        <div class="section">
            <h2>Removal Requests ({pack.removal_requests_filed} filed)</h2>
            <table class="removal-table">
                <thead>
                    <tr><th>Type</th><th>URL</th><th>Legal Basis</th><th>Status</th><th>Date</th></tr>
                </thead>
                <tbody>
                    {chr(10).join(f'<tr><td>{r.get("content_type", "N/A").replace("_", " ").title()}</td><td><a href="{r.get("content_url", "#")}">{r.get("content_url", "N/A")[:50]}...</a></td><td>{r.get("legal_basis", "N/A")}</td><td><span class="status {r.get("status", "draft")}">{r.get("status", "draft").upper()}</span></td><td>{r.get("created_at", "N/A")[:10]}</td></tr>' for r in pack.removal_requests[:20])}
                </tbody>
            </table>
        </div>
        """ if pack.removal_requests else '<div class="section"><h2>Removal Requests</h2><p>No removal requests filed in this period.</p></div>')}
        
        <!-- FOOTER -->
        <div class="footer">
            <div class="disclaimer">
                <strong>⚠️ DISCLAIMER:</strong> This report was generated by FixMyNameOnline AI. 
                FixMyNameOnline does not guarantee specific search rankings. Results vary based on content volume, 
                platform authority, and search competition. Not a law firm. Removal request outcomes depend on 
                platform/third-party response. Evidence Pack is informational only.
            </div>
            <p>FIX MY NAME ONLINE™ — A MadisonJade Pty Ltd Product™<br>
            © 2026 MadisonJade Pty Ltd. All Rights Reserved.<br>
            Generated: {pack.generated_at.strftime('%d %B %Y %H:%M')}</p>
        </div>
    </div>
</body>
</html>
"""
    return html


def format_evidence_pack_text(pack: EvidencePack) -> str:
    """Format Evidence Pack as plain text for email/download."""
    
    text = f"""
================================================================================
FIX MY NAME ONLINE — SUPPRESSION PROGRESS REPORT
================================================================================

Generated: {pack.generated_at.strftime('%d %B %Y, %H:%M')}
Report Period: {pack.period_start.strftime('%d %B %Y')} — {pack.period_end.strftime('%d %B %Y')}
Customer: {pack.customer_name}
Email: {pack.customer_email}
Tier: {pack.tier.upper()}

--------------------------------------------------------------------------------
SUPPRESSION SCORE: {pack.suppression_score}/100
--------------------------------------------------------------------------------

Previous Score: {pack.previous_score}/100
Change: {'+' if pack.suppression_score - pack.previous_score > 0 else ''}{pack.suppression_score - pack.previous_score} points

{"🌟 Excellent progress!" if pack.suppression_score >= 75 else
 "📈 Good momentum!" if pack.suppression_score >= 50 else
 "⚡ Building foundation!" if pack.suppression_score >= 25 else
 "🚀 Just starting!"}

--------------------------------------------------------------------------------
KEY METRICS
--------------------------------------------------------------------------------

Content Published: {pack.content_published} pieces
Social Posts: {pack.social_published} pieces
Active Platforms: {pack.platforms_active}
Alerts Triggered: {pack.alerts_triggered}

--------------------------------------------------------------------------------
REMOVAL REQUESTS
--------------------------------------------------------------------------------

Filed: {pack.removal_requests_filed}
Approved: {pack.removal_requests_approved}
Rejected: {pack.removal_requests_rejected}
Pending: {pack.removal_requests_pending}

--------------------------------------------------------------------------------
RECOMMENDATIONS
--------------------------------------------------------------------------------

"""
    
    for i, rec in enumerate(pack.recommendations, 1):
        text += f"{i}. {rec}\n"
    
    text += f"""
--------------------------------------------------------------------------------
SCORECARD
--------------------------------------------------------------------------------

Content Volume: {pack.scorecard.get('Content Volume', 'N/A')}
Platform Diversity: {pack.scorecard.get('Platform Diversity', 'N/A')}
Suppression Progress: {pack.scorecard.get('Suppression Progress', 'N/A')}
Removal Success: {pack.scorecard.get('Removal Success', 'N/A')}

================================================================================
© 2026 MadisonJade Pty Ltd. All Rights Reserved. FixMyNameOnline™
================================================================================

⚠️ DISCLAIMER: This report was generated by FixMyNameOnline AI. Results vary.
Not a law firm. Removal outcomes depend on third-party response.
"""
    
    return text


# =============================================================================
# PDF GENERATION (requires weasyprint or reportlab)
# =============================================================================

def generate_pdf(evidence_pack: EvidencePack, output_path: str = None) -> str:
    """Generate PDF from Evidence Pack.
    
    Requires: pip install weasyprint
    Falls back to HTML if weasyprint not available.
    """
    html = format_evidence_pack_html(evidence_pack)
    
    if output_path is None:
        from datetime import datetime as dt
        output_path = f"evidence_pack_{evidence_pack.customer_name.replace(' ', '_')}_{dt.now().strftime('%Y%m%d_%H%M')}.pdf"
    
    try:
        from weasyprint import HTML
        HTML(string=html).write_pdf(output_path)
        return output_path
    except ImportError:
        # Fallback: save as HTML
        html_path = output_path.replace('.pdf', '.html')
        with open(html_path, 'w') as f:
            f.write(html)
        return html_path


# =============================================================================
# TIER-SPECIFIC EVIDENCE PACK
# =============================================================================

def get_evidence_pack_type(tier: str) -> str:
    """Get the evidence pack type for a tier."""
    types = {
        "free": "dashboard_only",
        "sentinel": "monthly_email",
        "starter": "quarterly_pdf",
        "pro": "quarterly_pdf",
        "premium": "monthly_pdf",
        "concierge": "weekly_video"
    }
    return types.get(tier, "quarterly_pdf")


# =============================================================================
# SARAH'S VIDEO EVIDENCE PACK (for Concierge)
# =============================================================================

def generate_video_script(pack: EvidencePack) -> str:
    """Generate a video script narrated by Sarah Chen for Concierge tier."""
    
    score_phrase = {
        "Excellent": "Outstanding progress! You're absolutely dominating search results.",
        "Good": "Solid progress. You're well on your way to suppression success.",
        "Fair": "Good start. Let's work together to accelerate your results.",
        "Poor": "We're just getting started. Let me outline your path forward."
    }.get(pack.scorecard.get("Suppression Progress", "Fair"), "")
    
    script = f"""
# VIDEO EVIDENCE PACK — NARRATED BY SARAH CHEN
## Concierge Weekly Report for {pack.customer_name}
## Generated: {pack.generated_at.strftime('%d %B %Y')}

---

[HOOK — 0:00-0:05]
Hi {pack.customer_name}, it's Sarah. Welcome to your weekly suppression evidence pack.

[SCORE — 0:05-0:15]
Your suppression score is now {pack.suppression_score} out of 100. {score_phrase}

{score_phrase}

[CONTENT SUMMARY — 0:15-0:25]
This week, we published {pack.content_published} pieces of content across {pack.platforms_active} platforms. 
{("Social media posts accounted for " + str(pack.social_published) + " of those.") if pack.social_published > 0 else ""}

[METRICS — 0:25-0:35]
Here's where you stand:
- {pack.content_published} content pieces published
- {pack.platforms_active} platforms active
- {pack.alerts_triggered} alerts triggered
- {pack.removal_requests_filed} removal requests filed

{("Great news on removals: " + str(pack.removal_requests_approved) + " approved out of " + str(pack.removal_requests_filed) + " filed.") if pack.removal_requests_filed > 0 else "No removal requests this week — let's discuss if we should file any."}

[RECOMMENDATIONS — 0:35-0:50]
Based on your progress, here are my top recommendations:

{chr(10).join(chr(10).join([f"{i+1}. " + r for i, r in enumerate(pack.recommendations)])).split(chr(10))[0:5]}

[CLOSING — 0:50-1:00]
Remember, consistency is the key to long-term suppression. Keep publishing, and we'll keep pushing those negative results further down.

If you need anything, I'm always here. Talk soon!

Sarah Chen
Senior AI Reputation Strategist
FixMyNameOnline

---

Script Duration: ~1 minute (150 words)
Avatar: Sarah Chen (Hedra Professional)
Platform: Zoom / Video hosting
"""
    
    return script
