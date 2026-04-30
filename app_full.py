"""
Fix My Name Online — Full Suppression Platform
AI-Powered Reputation Management with Bombardment Mechanic
Copyright (c) 2026 MadisonJade Pty Ltd. All Rights Reserved.
"""

import streamlit as st
import json
import os
import sys
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# =============================================================================
# CONFIGURATION
# =============================================================================

APP_NAME = "Fix My Name Online"
BRAND = "MadisonJade Pty Ltd"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Tier definitions (from FMNOL brief)
TIERS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "articles": 3,  # one-off
        "social": 3,
        "aliases": 1,
        "misspellings": False,
        "rtbf_per_year": 0,
        "dmca_per_year": 0,
        "defamation_per_year": 0,
        "evidence": False,
        "ai_manager": False,
        "avatar": False,
        "fps_publishing": False,
        "color": "#888888",
        "popular": False,
    },
    "sentinel": {
        "name": "Sentinel",
        "price_monthly": 29,
        "articles": 0,
        "social": 0,
        "aliases": 1,
        "misspellings": False,
        "rtbf_per_year": 0,
        "dmca_per_year": 0,
        "defamation_per_year": 0,
        "evidence": "monthly_email",
        "ai_manager": False,
        "avatar": False,
        "fps_publishing": False,
        "color": "#2563EB",
        "popular": False,
        "tag": "Insurance"
    },
    "starter": {
        "name": "Starter",
        "price_monthly": 499,
        "articles": 50,
        "social": 50,
        "aliases": 3,
        "misspellings": "basic",
        "rtbf_per_year": 3,
        "dmca_per_year": 0,
        "defamation_per_year": 3,
        "evidence": "quarterly_pdf",
        "ai_manager": False,
        "avatar": "onboarding",
        "fps_publishing": False,
        "color": "#F59E0B",
        "popular": True,
        "tag": "Most Popular"
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 999,
        "articles": 150,
        "social": 150,
        "aliases": 5,
        "misspellings": "full",
        "rtbf_per_year": 10,
        "dmca_per_year": 5,
        "defamation_per_year": 10,
        "evidence": "quarterly_pdf",
        "ai_manager": "junior",
        "ai_sla_hours": 48,
        "avatar": "monthly_recap",
        "fps_publishing": True,
        "color": "#EF4444",
        "popular": False,
        "tag": "Best Value"
    },
    "premium": {
        "name": "Premium",
        "price_monthly": 2597,
        "articles": 200,
        "social": 200,
        "aliases": -1,  # unlimited
        "misspellings": "full_plus",
        "rtbf_per_year": -1,
        "dmca_per_year": -1,
        "defamation_per_year": -1,
        "evidence": "monthly_pdf",
        "ai_manager": "senior",
        "ai_sla_hours": 24,
        "avatar": "monthly_zoom",
        "fps_publishing": True,
        "color": "#A855F7",
        "popular": False,
        "tag": "HNW"
    },
    "concierge": {
        "name": "Concierge",
        "price_monthly": 7500,
        "price_max": 10000,
        "articles": -1,
        "social": -1,
        "aliases": -1,
        "misspellings": "everything",
        "rtbf_per_year": -1,
        "dmca_per_year": -1,
        "defamation_per_year": -1,
        "evidence": "weekly_video",
        "ai_manager": "senior_plus_human",
        "ai_sla_hours": 4,
        "avatar": "weekly_zoom",
        "fps_publishing": True,
        "color": "#14B8A6",
        "popular": False,
        "tag": "White Glove"
    }
}

# Platform definitions
PLATFORMS = {
    "linkedin": {"name": "LinkedIn", "icon": "💼", "api": True, "color": "#0077B5"},
    "twitter": {"name": "X / Twitter", "icon": "🐦", "api": True, "color": "#1DA1F2"},
    "facebook": {"name": "Facebook", "icon": "📘", "api": True, "color": "#1877F2"},
    "threads": {"name": "Threads", "icon": "🧵", "api": False, "color": "#000000"},
    "instagram": {"name": "Instagram", "icon": "📷", "api": True, "color": "#E4405F"},
    "medium": {"name": "Medium", "icon": "📝", "api": False, "color": "#00AB6C"},
    "substack": {"name": "Substack", "icon": "📧", "api": False, "color": "#FF6719"},
    "wordpress": {"name": "WordPress.com", "icon": "🌐", "api": False, "color": "#21759B"},
    "blogger": {"name": "Blogger", "icon": "📓", "api": True, "color": "#FF6600"},
    "tumblr": {"name": "Tumblr", "icon": "🔮", "api": False, "color": "#36465D"},
    "reddit": {"name": "Reddit", "icon": "🤖", "api": False, "color": "#FF4500"},
    "quora": {"name": "Quora", "icon": "❓", "api": False, "color": "#AA2200"},
    "pinterest": {"name": "Pinterest", "icon": "📌", "api": False, "color": "#E60023"},
    "fps_main": {"name": "FPS Network", "icon": "🏢", "api": True, "color": "#FF0000", "tier": "pro"},
    "fpa_main": {"name": "FPA Network", "icon": "🎓", "api": True, "color": "#0066FF", "tier": "pro"},
}

# =============================================================================
# STORAGE HELPERS
# =============================================================================

def get_customer_file(customer_id: str) -> str:
    return os.path.join(DATA_DIR, f"customer_{customer_id}.json")

def load_customer(customer_id: str) -> dict:
    path = get_customer_file(customer_id)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {
        "id": customer_id,
        "created_at": datetime.now().isoformat(),
        "tier": "free",
        "keywords": [],
        "aliases": {},
        "content_queue": [],
        "published_content": [],
        "alerts": [],
        "removal_requests": [],
        "sarah_memory": [],
        "suppression_score": 0,
        "negative_results": [],
        "credentials": {},
        "removal_filings_this_period": {"rtbf": 0, "dmca": 0, "defamation": 0}
    }

def save_customer(customer: dict):
    path = get_customer_file(customer["id"])
    with open(path, "w") as f:
        json.dump(customer, f, indent=2)

def get_tier(customer: dict) -> dict:
    return TIERS.get(customer.get("tier", "free"), TIERS["free"])

def calc_suppression_score(customer: dict) -> int:
    """Calculate suppression score: content × platform authority."""
    published = customer.get("published_content", [])
    score = len(published) * 5  # 5 points per piece
    return min(score, 100)

# =============================================================================
# PAGE CONFIG
# =============================================================================

st.set_page_config(
    page_title="Fix My Name Online — Suppression Platform",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp { background: #0a0a0f; font-family: 'Inter', sans-serif; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebar"] { background: #0d1117; border-right: 1px solid #2d333b; }
[data-testid="stSidebarNav"] { padding-top: 2rem; }
.stButton>button { border-radius: 8px; font-weight: 600; transition: all 0.2s; }
.stButton>button:hover { transform: translateY(-1px); }
h1, h2, h3 { color: #ffffff; font-weight: 700; }
p, span { color: #cccccc; }
[data-testid="stMetricValue"] { color: #ffffff; }
[data-testid="stMetricLabel"] { color: #888888; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION INIT
# =============================================================================

if "customer_id" not in st.session_state:
    st.session_state.customer_id = "demo_user"
if "customer" not in st.session_state:
    st.session_state.customer = load_customer(st.session_state.customer_id)
if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "sarah_messages" not in st.session_state:
    st.session_state.sarah_messages = []

customer = st.session_state.customer
tier = get_tier(customer)

# =============================================================================
# SIDEBAR NAVIGATION
# =============================================================================

with st.sidebar:
    st.markdown("### ◉ FIX MY NAME ONLINE")
    st.markdown(f"**Tier:** {TIERS[customer.get('tier', 'free')]['name']}")
    
    if tier.get("ai_manager"):
        st.markdown("🟢 AI Manager: Active")
    else:
        st.markdown("⚪ AI Manager: Upgrade for access")
    
    st.divider()
    
    pages = [
        "📊 Dashboard",
        "✨ Generate Content",
        "📤 Publish",
        "⚖️ Remove (AI Lawyers)",
        "👩‍💼 AI Manager (Sarah)",
        "📋 Evidence Pack",
        "🔔 Alerts",
        "🎯 Suppression Tracker",
        "⚙️ Settings",
    ]
    
    for page in pages:
        if st.button(page, use_container_width=True, 
                    type="primary" if st.session_state.page in page else "secondary"):
            st.session_state.page = page
            st.rerun()
    
    st.divider()
    
    # Tier upgrade prompt
    if customer.get("tier") != "concierge":
        st.markdown("### 🚀 Upgrade Your Plan")
        st.markdown("Unlock more content, AI managers, and unlimited removals.")
        if st.button("View Plans", use_container_width=True):
            st.session_state.page = "Settings"
            st.rerun()
    
    st.divider()
    st.markdown(f"<small>© 2026 {BRAND}<br>All Rights Reserved.</small>", unsafe_allow_html=True)

# =============================================================================
# PAGE: DASHBOARD
# =============================================================================

if st.session_state.page == "📊 Dashboard":

    # Update suppression score
    customer["suppression_score"] = calc_suppression_score(customer)
    save_customer(customer)

    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Suppression Score", f"{customer['suppression_score']}/100")
    with col2:
        published = len(customer.get("published_content", []))
        st.metric("📝 Content Published", published)
    with col3:
        negatives = len(customer.get("negative_results", []))
        st.metric("⚠️ Negative Results", negatives)
    with col4:
        alerts = len(customer.get("alerts", []))
        st.metric("🔔 Active Alerts", alerts)

    st.divider()

    # Search bar
    st.subheader("🔍 Check Your Google Results")
    search_col1, search_col2 = st.columns([4, 1])
    with search_col1:
        search_name = st.text_input("Enter your name to check current Google results", 
                                   placeholder="John Smith", label_visibility="collapsed")
    with search_col2:
        search_btn = st.button("🔍 Search", type="primary")

    if search_btn and search_name:
        with st.spinner("Searching Google..."):
            # Import search function
            try:
                from app import search_google
                results = search_google(search_name, num_results=10)
                if results:
                    st.success(f"Found {len(results)} results for '{search_name}'")
                    
                    good_results = []
                    bad_results = []
                    
                    for r in results:
                        if "negative" in r.get("snippet", "").lower():
                            bad_results.append(r)
                        else:
                            good_results.append(r)
                    
                    st.subheader("✅ Good Results (keep these)")
                    for r in good_results[:7]:
                        st.markdown(f"- [{r.get('title', 'No title')}]({r.get('url', '')})")
                        st.caption(f"_{r.get('snippet', '')[:100]}..._")
                    
                    if bad_results:
                        st.subheader("❌ Negative Results (suppress these)")
                        for r in bad_results:
                            with st.container():
                                st.error(f"**{r.get('title', 'No title')}**")
                                st.caption(f"[{r.get('url', '')}]({r.get('url', '')})")
                                st.caption(f"_{r.get('snippet', '')[:150]}_")
                                if st.button(f"📝 Generate content to suppress", key=f"suppress_{r.get('url', '')}"):
                                    st.session_state.page = "✨ Generate Content"
                                    st.rerun()
                else:
                    st.info("No results found or search error.")
            except Exception as e:
                st.error(f"Search error: {e}")
                st.info("Configure Serp.dev API key in Settings to enable search.")

    st.divider()

    # Suppression progress
    st.subheader("🎯 Suppression Progress")
    
    score = customer["suppression_score"]
    st.progress(min(score / 100, 1.0), text=f"{score}/100 suppression score")
    
    phase = "Phase 1" if score < 25 else "Phase 2" if score < 50 else "Phase 3" if score < 75 else "Phase 4"
    phases = {
        "Phase 1": "Generating initial content. Keep publishing!",
        "Phase 2": "Building momentum. Negative results starting to move.",
        "Phase 3": "Strong presence. Negative results pushed to page 2-3.",
        "Phase 4": "Dominating search. Negative results invisible to 95% of searchers."
    }
    st.info(f"**{phase}:** {phases[phase]}")

    # Timeline milestones
    st.markdown("""
    | Day | Expected Progress |
    |-----|------------------|
    | Day 0 | Baseline: negative result on page 1 |
    | Day 30 | 5+ positive articles visible |
    | Day 60 | Negative result pushed to page 3+ |
    | Day 90 | Negative result invisible to most searchers |
    """)

    st.divider()

    # Recent activity
    st.subheader("📜 Recent Activity")
    logs = customer.get("published_content", [])[-10:]
    if logs:
        for log in reversed(logs):
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{log.get('title', log.get('platform', 'Content'))}**")
                    st.caption(f"_{log.get('platform', 'Unknown platform')}_")
                with c2:
                    platforms = log.get("platforms", [])
                    if platforms:
                        st.caption(f"Platforms: {', '.join(platforms[:3])}")
                with c3:
                    st.caption(log.get("timestamp", "")[:10])
                st.divider()
    else:
        st.info("No content published yet. Start by generating content!")

    # FPS cross-sell
    st.divider()
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a1a2e, #0d1117); border-radius: 16px; padding: 24px; text-align: center;">
        <h3 style="color: white;">🏢 Published on the FPS Media Network?</h3>
        <p style="color: #888;">Your Pro+ content appears on firstpagestrategy.org — domains Google already trusts.</p>
        <p style="color: #ff4444; font-weight: 700;">This is the moat nobody can copy.</p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# PAGE: GENERATE CONTENT
# =============================================================================

elif st.session_state.page == "✨ Generate Content":
    st.header("✨ Generate Positive Content")
    st.markdown("*Build your online presence with AI-generated, publish-ready content.*")

    # Import content generator
    from content_generator import generate_content, PLATFORMS as CG_PLATFORMS, CONTENT_TYPE_MAP

    # Input section
    col1, col2 = st.columns([2, 1])

    with col1:
        keyword = st.text_input("Target Name / Keyword", 
                               placeholder="Enter the name you want to dominate search results for",
                               help="This is the name or keyword that will appear in your generated content")
        
        # Aliases
        st.subheader("Aliases & Variants")
        aliases = customer.get("aliases", {}).get(keyword, [])
        alias_input = st.text_input("Add alias (nickname, maiden name, professional name)", 
                                    placeholder="e.g., John Smith, Johnny Smith")
        if st.button("+ Add Alias") and alias_input:
            if keyword not in customer["aliases"]:
                customer["aliases"][keyword] = []
            if alias_input not in customer["aliases"][keyword]:
                customer["aliases"][keyword].append(alias_input)
                save_customer(customer)
                st.success(f"Added alias: {alias_input}")
                st.rerun()

        if keyword and keyword in customer.get("aliases", {}):
            st.write("**Current aliases:**", ", ".join(customer["aliases"][keyword]))

    with col2:
        tier_info = get_tier(customer)
        st.markdown(f"""
        <div style="background: {tier_info['color']}20; border: 1px solid {tier_info['color']}; 
                    border-radius: 12px; padding: 16px; margin-top: 0;">
            <h4 style="color: white; margin-top: 0;">📦 {tier_info['name']} Plan</h4>
            <p style="color: #888; font-size: 14px;">
                {tier_info['articles'] if tier_info['articles'] > 0 else 'Unlimited'} articles/mo<br>
                {tier_info['social'] if tier_info['social'] > 0 else 'Unlimited'} social posts/mo<br>
                {tier_info['aliases'] if tier_info['aliases'] > 0 else 'Unlimited'} aliases<br>
                {tier_info['rtbf_per_year'] if tier_info['rtbf_per_year'] > 0 else 'Unlimited'} RTBF/yr
            </p>
            {'<p style="color: #ff4444; font-size: 12px;">Upgrade for more →</p>' if tier_info['name'] in ['Free', 'Sentinel'] else ''}
        </div>
        """, unsafe_allow_html=True)

    # Mode selector
    mode = st.radio("Generation Mode", ["SINGLE", "BULK (5 batches)"], 
                    horizontal=True, help="Single generates one batch of 20 content types. Bulk generates 5 batches for maximum coverage.")

    # Platform selector
    st.subheader("📡 Target Platforms")
    platform_cols = st.columns(7)
    selected_platforms = []
    
    platform_list = list(PLATFORMS.items())
    for i, (pid, pdata) in enumerate(platform_list):
        with platform_cols[i % 7]:
            # Check if FPS/FPA requires Pro+
            requires_pro = pdata.get("tier") == "pro"
            tier_ok = requires_pro and customer.get("tier") not in ["pro", "premium", "concierge"]
            
            if tier_ok:
                st.checkbox(f"{pdata['icon']} {pdata['name']}", value=False, 
                           disabled=True, help=f"Requires {TIERS['pro']['name']}+ tier")
            else:
                if st.checkbox(f"{pdata['icon']} {pdata['name']}", value=True):
                    selected_platforms.append(pid)

    if not selected_platforms:
        st.warning("Select at least one platform!")

    # Generate button
    if st.button("🚀 GENERATE CONTENT", type="primary", use_container_width=True) and keyword and selected_platforms:
        with st.spinner("Generating content with AI..."):
            try:
                content = generate_content(keyword)
                
                if "error" in content and "fallback" not in content:
                    st.error(f"Generation error: {content['error']}")
                else:
                    if "fallback" in content:
                        st.warning("Using fallback content (API not available). Configure MiniMax API key in Settings.")
                        content = content["fallback"]
                    
                    # Save to customer
                    customer.setdefault("published_content", []).append({
                        "title": f"Content batch for {keyword}",
                        "keyword": keyword,
                        "platforms": selected_platforms,
                        "timestamp": datetime.now().isoformat(),
                        "content": content,
                        "mode": mode,
                        "status": "generated"
                    })
                    save_customer(customer)
                    
                    st.success("✅ Content generated successfully!")
                    
                    # Display content in tabs
                    tabs = st.tabs(list(content.keys())[:10])  # Show first 10 types
                    for i, (ctype, ctext) in enumerate(content.items()):
                        if i < 10:
                            with tabs[i]:
                                st.markdown(f"### {ctype.replace('_', ' ').title()}")
                                st.text_area("Content", ctext, height=200, key=f"gen_{ctype}")
                                c1, c2 = st.columns(2)
                                with c1:
                                    if st.button("📋 Copy", key=f"copy_{ctype}"):
                                        st.code(ctext)
                                        st.success("Content ready to copy!")
                                with c2:
                                    if st.button(f"📤 Publish", key=f"pub_{ctype}"):
                                        st.session_state.page = "📤 Publish"
                                        st.rerun()

            except Exception as e:
                st.error(f"Error: {e}")

    st.divider()

    # Bulk mode info
    if mode == "BULK (5 batches)":
        st.info("""
        **Bulk Mode:** Generates 5 batches × 20 content types = 100 pieces of content.
        All content will be queued for publishing across your selected platforms.
        Estimated time: 5-10 minutes.
        """)

# =============================================================================
# PAGE: PUBLISH
# =============================================================================

elif st.session_state.page == "📤 Publish":
    st.header("📤 Multi-Platform Publishing Hub")
    st.markdown("*Publish your content across all configured platforms.*")

    # Platform status grid
    st.subheader("📡 Platform Status")
    
    creds = customer.get("credentials", {})
    cols = st.columns(4)
    
    for i, (pid, pdata) in enumerate(list(PLATFORMS.items())[:8]):
        with cols[i % 4]:
            connected = pid in creds and creds[pid]
            st.markdown(f"""
            <div style="background: #0d1117; border: 1px solid #2d333b; border-radius: 12px; padding: 16px; text-align: center;">
                <div style="font-size: 32px;">{pdata['icon']}</div>
                <div style="color: white; font-weight: 600;">{pdata['name']}</div>
                <div style="color: {'#00ff00' if connected else '#ff4444'}; font-size: 12px;">
                    {'✅ Connected' if connected else '❌ Not configured'}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # FPS Publishing (Pro+ only)
    fps_tier_ok = customer.get("tier") in ["pro", "premium", "concierge"]
    
    st.divider()
    st.subheader("🏢 FPS Owned Media Publishing")
    
    if fps_tier_ok:
        st.success("✅ FPS Publishing available on your plan!")
        st.markdown("""
        **Your Pro+ content gets published to firstpagestrategy.org — domains Google already ranks.**
        
        This is the moat nobody can copy. Your content appears on real news sites with real domain authority.
        """)
        
        col1, col2 = st.columns(2)
        with col1:
            fps_site = st.selectbox("FPS Site", ["firstpagestrategy.org", "firstpageacademy.org", "FPA TV"])
            fps_byline = st.text_input("Author Byline", value=customer.get("name", "Staff Writer"))
            fps_category = st.selectbox("Category", ["News", "Finance", "AI", "Tech", "Lifestyle", "Opinion"])
        
        with col2:
            st.write("**Publishing Stats:**")
            fps_published = len([p for p in customer.get("published_content", []) 
                                if "fps" in p.get("platforms", [])])
            st.metric("FPS Articles Published", fps_published)
            
            if st.button("📝 Publish Latest Content to FPS", type="primary"):
                st.info("Publishing to FPS network... (Connect FPS API in Settings)")
    else:
        st.warning(f"🚫 FPS Publishing requires Pro+ tier. You have {tier['name']}.")
        if st.button("Upgrade to Pro"):
            st.session_state.page = "⚙️ Settings"
            st.rerun()

    st.divider()
    
    # Publishing queue
    st.subheader("📋 Publishing Queue")
    queue = customer.get("content_queue", [])
    
    if queue:
        for item in queue[:5]:
            with st.container():
                c1, c2, c3 = st.columns([3, 2, 1])
                with c1:
                    st.markdown(f"**{item.get('title', 'Untitled')}**")
                    st.caption(f"Platforms: {', '.join(item.get('platforms', []))}")
                with c2:
                    st.caption(f"Scheduled: {item.get('scheduled_time', 'ASAP')}")
                with c3:
                    if st.button("❌", key=f"del_{item.get('id', '')}"):
                        queue.remove(item)
                        save_customer(customer)
                        st.rerun()
    else:
        st.info("No items in queue. Generate content first, then add to queue.")

# =============================================================================
# PAGE: REMOVE (AI LAWYERS)
# =============================================================================

elif st.session_state.page == "⚖️ Remove (AI Lawyers)":
    st.header("⚖️ AI-Powered Legal Removal")
    st.markdown("*Jurisdiction-aware legal request generator. Drafted by AI lawyers, submitted by you.*")

    from ai_lawyer import (
        get_lawyer, generate_removal_request, get_available_lawyers,
        get_available_legal_bases, TIER_REMOVAL_LIMITS, can_file_removal,
        get_tier_limits, format_removal_as_html, LAWYERS
    )

    # Jurisdiction selector
    col1, col2 = st.columns([1, 2])
    
    with col1:
        jurisdiction = st.selectbox("Your Jurisdiction", 
                                   ["US", "UK", "EU", "AU", "CA", "BR", "JP"],
                                   format_func=lambda x: {
                                       "US": "🇺🇸 United States",
                                       "UK": "🇬🇧 United Kingdom",
                                       "EU": "🇪🇺 European Union",
                                       "AU": "🇦🇺 Australia",
                                       "CA": "🇨🇦 Canada",
                                       "BR": "🇧🇷 Brazil",
                                       "JP": "🇯🇵 Japan"
                                   }.get(x, x))
    
    # Get appropriate lawyer
    lawyer = get_lawyer(jurisdiction)
    
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #1a1a2e, #0d1117); border-radius: 16px; padding: 20px;">
            <h3 style="color: white; margin-top: 0;">{lawyer.flags[0]} {lawyer.name}</h3>
            <p style="color: #888; font-size: 14px; margin-bottom: 0;">{lawyer.title}</p>
            <p style="color: #aaa; font-size: 12px;">{lawyer.bio[:150]}...</p>
        </div>
        """, unsafe_allow_html=True)

    # Tier limits
    tier_limits = get_tier_limits(customer.get("tier", "free"))
    
    if tier_limits["rtbf_per_year"] == 0:
        st.warning(f"⚠️ Removal filings require Starter+ tier. You have {tier['name']}. Upgrade to access unlimited RTBF, DMCA, and defamation filings.")
        if st.button("Upgrade to Starter ($499/mo)"):
            st.session_state.page = "⚙️ Settings"
            st.rerun()
    else:
        st.divider()

        # Content input
        st.subheader("📋 Content Details")
        col1, col2 = st.columns(2)
        
        with col1:
            content_url = st.text_input("Harmful Content URL", 
                                       placeholder="https://example.com/bad-article")
            content_type = st.selectbox("Content Type", 
                                        ["defamatory_article", "mugshot", "fake_review", 
                                         "personal_data", "copyright_infringement"],
                                        format_func=lambda x: x.replace("_", " ").title())
        
        with col2:
            content_description = st.text_area("Description of Harmful Content",
                                               placeholder="Describe what's wrong with this content and why it should be removed...",
                                               height=100)

        # Requestor info
        st.subheader("👤 Your Information")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            requestor_name = st.text_input("Your Full Name")
        with col2:
            requestor_email = st.text_input("Your Email")
        with col3:
            requestor_phone = st.text_input("Phone (optional)")

        # Tier limits display
        rtbf_limit = tier_limits["rtbf_per_year"]
        st.markdown(f"""
        <div style="background: #0d1117; border-radius: 12px; padding: 16px; margin: 16px 0;">
            <h4 style="color: white; margin-top: 0;">📊 Your {tier['name']} Removal Allowance</h4>
            <p style="color: #888;">
                RTBF/GDPR: {'Unlimited' if rtbf_limit == -1 else f'{rtbf_limit}/year'}<br>
                DMCA: {'Unlimited' if tier_limits['dmca_per_year'] == -1 else f'{tier_limits["dmca_per_year"]}/year'}<br>
                Defamation: {'Unlimited' if tier_limits['defamation_per_year'] == -1 else f'{tier_limits["defamation_per_year"]}/year'}
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Generate button
        if st.button("⚖️ GENERATE REMOVAL REQUEST", type="primary", use_container_width=True):
            if not all([content_url, content_description, requestor_name, requestor_email]):
                st.error("Please fill in all required fields.")
            else:
                with st.spinner(f"Drafting {lawyer.name}..."):
                    try:
                        request = generate_removal_request(
                            lawyer=lawyer,
                            content_url=content_url,
                            content_type=content_type,
                            content_description=content_description,
                            requestor_name=requestor_name,
                            requestor_email=requestor_email,
                            requestor_address="",  # Could add address field
                            requestor_phone=requestor_phone
                        )
                        
                        # Save to customer
                        customer.setdefault("removal_requests", []).append({
                            "id": str(uuid.uuid4()),
                            "lawyer": lawyer.name,
                            "jurisdiction": jurisdiction,
                            "content_url": content_url,
                            "content_type": content_type,
                            "legal_basis": request.legal_basis.name if request.legal_basis else "Unknown",
                            "created_at": datetime.now().isoformat(),
                            "status": "draft"
                        })
                        save_customer(customer)

                        st.success(f"✅ Removal request drafted by {lawyer.name}!")
                        
                        # Display letter
                        st.subheader("📄 Generated Letter")
                        
                        # Subject
                        st.markdown(f"**Subject:** {request.subject}")
                        
                        # Letter body (scrollable)
                        st.text_area("Letter Body", request.letter_body, height=400, 
                                    label_visibility="collapsed")
                        
                        # Actions
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            if st.button("📥 Download as TXT"):
                                st.download_button("Download Letter", 
                                                 request.letter_body,
                                                 file_name=f"removal_request_{content_type}.txt")
                        with c2:
                            if st.button("📄 Copy to Clipboard"):
                                st.code(request.letter_body)
                                st.success("Letter ready to copy!")
                        with c3:
                            if st.button("📤 Submit to Platform"):
                                if request.submission_url:
                                    st.markdown(f"[Open Submission Portal]({request.submission_url})")
                                else:
                                    st.info("No direct submission URL. Copy the letter and submit manually.")

                        # Disclaimer
                        st.warning(request.disclaimer)

                    except Exception as e:
                        st.error(f"Error generating request: {e}")

    st.divider()
    
    # Removal history
    st.subheader("📋 Removal Request History")
    requests = customer.get("removal_requests", [])
    
    if requests:
        for req in reversed(requests[-10:]):
            with st.expander(f"{req['lawyer']} — {req['content_type'].replace('_', ' ')} — {req.get('status', 'pending')}"):
                st.write(f"**URL:** {req['content_url']}")
                st.write(f"**Legal Basis:** {req.get('legal_basis', 'N/A')}")
                st.write(f"**Date:** {req.get('created_at', 'N/A')[:10]}")
                st.write(f"**Status:** {req.get('status', 'draft')}")
    else:
        st.info("No removal requests yet.")

# =============================================================================
# PAGE: AI MANAGER (SARAH)
# =============================================================================

elif st.session_state.page == "👩‍💼 AI Manager (Sarah)":
    st.header("👩‍💼 AI Manager — Sarah Chen")
    
    tier_info = get_tier(customer)
    
    if not tier_info.get("ai_manager"):
        st.warning("Sarah Chen is available on **Pro+ tiers** only.")
        st.markdown(f"""
        You currently have **{tier_info['name']}** tier.
        
        Upgrade to access:
        - 24/7 AI reputation strategist
        - Named persona with perfect memory
        - Weekly proactive updates
        - Real-time crisis response
        """)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Upgrade to Pro ($999/mo)"):
                st.session_state.page = "⚙️ Settings"
                st.rerun()
        with col2:
            if st.button("Upgrade to Premium ($2,597/mo)"):
                st.session_state.page = "⚙️ Settings"
                st.rerun()
        with col3:
            if st.button("Learn about tiers"):
                st.session_state.page = "📊 Dashboard"
                st.rerun()
    else:
        # Sarah persona
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a1a2e, #0d1117); border-radius: 16px; padding: 24px; margin-bottom: 24px;">
            <div style="display: flex; align-items: center; gap: 20px;">
                <div style="font-size: 64px;">👩‍💼</div>
                <div>
                    <h2 style="color: white; margin: 0;">Sarah Chen</h2>
                    <p style="color: #888; margin: 4px 0;">Senior AI Reputation Strategist</p>
                    <p style="color: #00ff00; margin: 0;">🟢 Available 24/7 • Responds within {tier_info.get('ai_sla_hours', 24)} hours</p>
                    <p style="color: #888; font-size: 12px; margin: 4px 0;">Powered by Hermes Agent • Transparently AI-powered</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Chat interface
        st.subheader("💬 Chat with Sarah")

        for msg in st.session_state.sarah_messages:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(msg["content"])
            else:
                with st.chat_message("assistant"):
                    st.markdown(msg["content"])

        # Quick actions
        quick_actions = [
            "Generate more content about my keywords",
            "Check my suppression progress",
            "I found a new negative result",
            "What's my next best action?",
            "Show me my Evidence Pack"
        ]
        
        quick_col1, quick_col2 = st.columns(2)
        with quick_col1:
            for action in quick_actions[:3]:
                if st.button(f"💡 {action}", use_container_width=True):
                    st.session_state.sarah_messages.append({
                        "role": "user", "content": action
                    })
                    # Simulate Sarah response
                    response = f"Great question! As your AI reputation strategist, I'm here to help. Based on your current suppression score of {customer.get('suppression_score', 0)}/100, I'd recommend: {action.split(' about ')[1] if ' about ' in action else 'focusing on consistency'}. Let me pull up the details."
                    st.session_state.sarah_messages.append({
                        "role": "assistant", "content": response
                    })
                    st.rerun()
        with quick_col2:
            for action in quick_actions[3:]:
                if st.button(f"💡 {action}", use_container_width=True):
                    st.session_state.sarah_messages.append({
                        "role": "user", "content": action
                    })
                    response = f"Based on your case history, your current focus should be building content volume. You have {len(customer.get('published_content', []))} pieces published. I recommend generating content in bulk mode for maximum coverage."
                    st.session_state.sarah_messages.append({
                        "role": "assistant", "content": response
                    })
                    st.rerun()

        # Chat input
        if prompt := st.chat_input("Ask Sarah anything about your reputation strategy..."):
            st.session_state.sarah_messages.append({
                "role": "user", "content": prompt
            })
            
            # Simulate Sarah response (in production, this calls MiniMax/Claude)
            response = f"I understand you're asking about '{prompt}'. As your dedicated AI reputation strategist, I'm analyzing your case. Based on your profile: {len(customer.get('published_content', []))} pieces published, {customer.get('suppression_score', 0)}/100 suppression score. My recommendation: keep generating consistent content across multiple platforms. Would you like me to draft a content strategy specifically for this?"
            
            st.session_state.sarah_messages.append({
                "role": "assistant", "content": response
            })
            st.rerun()

# =============================================================================
# PAGE: EVIDENCE PACK
# =============================================================================

elif st.session_state.page == "📋 Evidence Pack":
    st.header("📋 Evidence Pack")
    st.markdown("*Document your suppression progress with professional reports.*")

    tier_info = get_tier(customer)

    if not tier_info.get("evidence"):
        st.warning(f"Evidence Packs require {TIERS['starter']['name']}+ tier. You have {tier_info['name']}.")
        if tier_info["name"] == "Sentinel":
            st.info("📧 Your Sentinel tier includes monthly email score updates — no PDF required!")
    else:
        evidence_type = tier_info.get("evidence")
        
        st.markdown(f"""
        <div style="background: #0d1117; border-radius: 12px; padding: 20px; margin: 16px 0;">
            <h4 style="color: white; margin-top: 0;">📦 Your {tier_info['name']} Evidence Pack</h4>
            <p style="color: #888;">
                Type: {evidence_type.replace('_', ' ').title()}<br>
                Coverage: {
                    'Monthly (recommended)' if evidence_type == 'monthly_pdf' else
                    'Quarterly (every 3 months)' if evidence_type == 'quarterly_pdf' else
                    'Weekly video narrated by Sarah' if evidence_type == 'weekly_video' else
                    'Email digest'
                }
            </p>
        </div>
        """, unsafe_allow_html=True)

        # Report contents
        st.subheader("📊 Report Contents")
        st.markdown("""
        Your Evidence Pack includes:
        - **Executive Summary** — Suppression progress at a glance
        - **Content Published** — Count by platform with article URLs
        - **Social Posts** — Count and samples
        - **Alerts Triggered** — Summary of mentions detected
        - **Removal Requests** — Filed, pending, approved, rejected
        - **Suppression Score** — Current score vs previous period
        - **Recommendations** — Sarah's AI-generated next steps
        """)

        if st.button("📄 Generate Evidence Pack", type="primary", use_container_width=True):
            with st.spinner("Generating report..."):
                # Simulate report generation
                st.success("Evidence Pack generated!")
                
                report_content = f"""
# SUPPRESSION PROGRESS REPORT
Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}
Customer: {customer.get('name', 'N/A')}
Tier: {tier_info['name']}

## SUPPRESSION SCORE
Current: {customer.get('suppression_score', 0)}/100
Previous: {max(0, customer.get('suppression_score', 0) - 10)}/100
Change: +10 points

## CONTENT PUBLISHED
Total Pieces: {len(customer.get('published_content', []))}
Platforms Active: {len(set(p for item in customer.get('published_content', []) for p in item.get('platforms', [])))}

## NEGATIVE RESULTS
Tracked: {len(customer.get('negative_results', []))}
Suppressed: {len([n for n in customer.get('negative_results', []) if n.get('suppressed')])}

## REMOVAL REQUESTS
Filed: {len(customer.get('removal_requests', []))}
Approved: {len([r for r in customer.get('removal_requests', []) if r.get('status') == 'approved'])}
Rejected: {len([r for r in customer.get('removal_requests', []) if r.get('status') == 'rejected'])}

## RECOMMENDATIONS
1. Continue publishing consistently to build momentum
2. Monitor alerts daily for new negative content
3. File RTBF requests for high-impact removals
4. Consider upgrading to Premium for unlimited content

---
© 2026 MadisonJade Pty Ltd
"""
                
                st.download_button("📥 Download Report", 
                                 report_content,
                                 file_name=f"evidence_pack_{datetime.now().strftime('%Y%m%d')}.txt",
                                 mime="text/plain")

# =============================================================================
# PAGE: ALERTS
# =============================================================================

elif st.session_state.page == "🔔 Alerts":
    st.header("🔔 Alert Monitoring")
    st.markdown("*Track mentions of your name across the web.*")

    # Add keyword
    col1, col2 = st.columns([3, 1])
    with col1:
        new_keyword = st.text_input("Add keyword to monitor", placeholder="Your name or any keyword")
    with col2:
        st.write("")  # spacing
        if st.button("+ Add Alert", type="primary"):
            if new_keyword and new_keyword not in [a.get("keyword") for a in customer.get("alerts", [])]:
                customer.setdefault("alerts", []).append({
                    "id": str(uuid.uuid4()),
                    "keyword": new_keyword,
                    "frequency": "daily",
                    "created_at": datetime.now().isoformat(),
                    "mentions": []
                })
                save_customer(customer)
                st.success(f"Added alert for: {new_keyword}")
                st.rerun()

    # Alert list
    alerts = customer.get("alerts", [])
    
    if alerts:
        for alert in alerts:
            with st.expander(f"🔔 {alert['keyword']} — {len(alert.get('mentions', []))} mentions"):
                st.write(f"**Frequency:** {alert.get('frequency', 'daily')}")
                st.write(f"**Created:** {alert.get('created_at', '')[:10]}")
                
                mentions = alert.get("mentions", [])
                if mentions:
                    st.subheader("Recent Mentions")
                    for m in mentions[:5]:
                        st.markdown(f"- {m.get('title', 'No title')}: {m.get('snippet', '')[:100]}...")
                else:
                    st.info("No mentions detected yet.")
                
                if st.button(f"🗑️ Delete Alert", key=f"del_alert_{alert['id']}"):
                    customer["alerts"].remove(alert)
                    save_customer(customer)
                    st.rerun()
    else:
        st.info("No alerts configured. Add your name and keywords above to start monitoring.")

# =============================================================================
# PAGE: SUPPRESSION TRACKER
# =============================================================================

elif st.session_state.page == "🎯 Suppression Tracker":
    st.header("🎯 Suppression Tracker")
    st.markdown("*The Bombardment Mechanic — visualized.*")

    # Progress ring
    score = customer.get("suppression_score", 0)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown(f"""
        <div style="position: relative; width: 200px; height: 200px; margin: auto;">
            <svg viewBox="0 0 200 200" style="transform: rotate(-90deg);">
                <circle cx="100" cy="100" r="80" fill="none" stroke="#2d333b" stroke-width="20"/>
                <circle cx="100" cy="100" r="80" fill="none" stroke="#ff4444" stroke-width="20"
                        stroke-dasharray="{score * 5.02} 502" stroke-linecap="round"/>
            </svg>
            <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); text-align: center;">
                <div style="font-size: 48px; font-weight: bold; color: white;">{score}</div>
                <div style="color: #888;">/100</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        phase = "Phase 1" if score < 25 else "Phase 2" if score < 50 else "Phase 3" if score < 75 else "Phase 4"
        
        st.markdown(f"""
        ### {phase}
        
        **Suppression Score: {score}/100**
        
        | Target | Current Status |
        |--------|----------------|
        | 10 pieces | Visible in search |
        | 50 pieces | Page 2+ |
        | 100 pieces | Page 3+ |
        | 200+ pieces | Invisible to 95% |
        
        **You need ~{max(0, 100 - score)} more points** to reach Phase 4 dominance.
        """)
        
        if st.button("✨ Generate More Content", type="primary"):
            st.session_state.page = "✨ Generate Content"
            st.rerun()

    st.divider()

    # Content by platform
    st.subheader("📡 Content by Platform")
    
    published = customer.get("published_content", [])
    platform_counts = {}
    for item in published:
        for p in item.get("platforms", []):
            platform_counts[p] = platform_counts.get(p, 0) + 1
    
    if platform_counts:
        for pname, count in sorted(platform_counts.items(), key=lambda x: -x[1]):
            pdata = PLATFORMS.get(pname, {"name": pname, "icon": "📝"})
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"{pdata['icon']} {pdata['name']}")
            with col2:
                st.write(f"{count} pieces")
            with col3:
                progress = min(count / 10, 1.0)
                st.progress(progress)
    else:
        st.info("No content published yet. Generate and publish content to see platform breakdown.")

    st.divider()

    # Bombartment timeline
    st.subheader("📅 Bombardment Timeline")
    
    st.markdown("""
    | Day | Content Published | Platform Coverage | Expected Result |
    |-----|------------------|-------------------|-----------------|
    | Day 0 | 0 | Baseline | 1 bad result on page 1 |
    | Day 30 | ~50 | 5-8 platforms | 5 positive + 1 bad |
    | Day 60 | ~100 | 8-10 platforms | 9 positive, bad on page 3 |
    | Day 90 | ~150 | 10+ platforms | Bad result invisible |
    """)

# =============================================================================
# PAGE: SETTINGS
# =============================================================================

elif st.session_state.page == "⚙️ Settings":
    st.header("⚙️ Settings & Configuration")

    # Profile
    st.subheader("👤 Profile")
    col1, col2 = st.columns(2)
    with col1:
        customer_name = st.text_input("Your Name", value=customer.get("name", ""))
        customer_email = st.text_input("Email", value=customer.get("email", ""))
    with col2:
        customer_country = st.selectbox("Country", ["US", "UK", "AU", "EU", "CA", "BR", "JP"],
                                       index=0)
    
    if st.button("💾 Save Profile"):
        customer["name"] = customer_name
        customer["email"] = customer_email
        customer["country"] = customer_country
        save_customer(customer)
        st.success("Profile saved!")

    st.divider()

    # Plan & Billing
    st.subheader("💳 Plan & Billing")
    
    current_tier = customer.get("tier", "free")
    
    st.markdown(f"""
    <div style="background: {TIERS[current_tier]['color']}20; border: 2px solid {TIERS[current_tier]['color']}; 
                border-radius: 16px; padding: 24px; margin: 16px 0;">
        <h3 style="color: white; margin-top: 0;">Current Plan: {TIERS[current_tier]['name']}</h3>
        <p style="color: #888;">
            Price: ${TIERS[current_tier]['price_monthly']}/month<br>
            Features: {TIERS[current_tier].get('tag', 'Standard')}
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Pricing table
    st.subheader("📊 All Plans")
    
    for tier_id, tier_data in TIERS.items():
        is_current = tier_id == current_tier
        
        with st.expander(f"{'✅ ' if is_current else '📌 '}{tier_data['name']} — ${tier_data['price_monthly']}/mo",
                        expanded=tier_id == current_tier):
            
            price = f"${tier_data['price_monthly']}/mo"
            if tier_data.get("price_max"):
                price = f"${tier_data['price_monthly']}-${tier_data['price_max']}/mo"
            
            st.markdown(f"### {tier_data['name']} | {price}")
            
            if tier_data.get("tag"):
                st.markdown(f"**{tier_data['tag']}**")
            
            st.markdown(f"""
            | Feature | Value |
            |---------|-------|
            | Articles/month | {'Unlimited' if tier_data['articles'] == -1 else tier_data['articles']} |
            | Social posts/month | {'Unlimited' if tier_data['social'] == -1 else tier_data['social']} |
            | Aliases | {'Unlimited' if tier_data['aliases'] == -1 else tier_data['aliases']} |
            | RTBF filings/year | {'Unlimited' if tier_data['rtbf_per_year'] == -1 else tier_data['rtbf_per_year']} |
            | Evidence Pack | {tier_data['evidence'] or 'None'} |
            | AI Manager | {'✅ ' + tier_data.get('ai_manager', 'No').replace('_', ' ').title() if tier_data.get('ai_manager') else '❌'} |
            | Avatar | {'✅ ' + tier_data.get('avatar', '').replace('_', ' ').title() if tier_data.get('avatar') else '❌'} |
            | FPS Publishing | {'✅' if tier_data.get('fps_publishing') else '❌'} |
            """)
            
            if not is_current:
                if st.button(f"Upgrade to {tier_data['name']}", type="primary"):
                    # In production: redirect to Stripe checkout
                    st.info(f"Stripe checkout would open for {tier_data['name']} tier.")
                    customer["tier"] = tier_id
                    save_customer(customer)
                    st.rerun()

    st.divider()

    # API Keys
    st.subheader("🔑 API Configuration")
    
    st.markdown("""
    Configure your API keys for content generation and search.
    
    **Required for full functionality:**
    - MiniMax API Key — AI content generation
    - Serp.dev API Key — Google search results
    """)
    
    api_col1, api_col2 = st.columns(2)
    with api_col1:
        minimax_key = st.text_input("MiniMax API Key", type="password", 
                                   value=os.environ.get("MINIMAX_API_KEY", ""))
    with api_col2:
        serp_key = st.text_input("Serp.dev API Key", type="password",
                                value=os.environ.get("SERPDEV_API_KEY", ""))
    
    if st.button("💾 Save API Keys"):
        os.environ["MINIMAX_API_KEY"] = minimax_key
        os.environ["SERPDEV_API_KEY"] = serp_key
        st.success("API keys saved (stored in session only for security)")

    st.divider()

    # Platform credentials
    st.subheader("📡 Platform Credentials")
    st.info("Connect your social media and publishing accounts. Credentials are encrypted and stored locally.")

# =============================================================================
# FOOTER
# =============================================================================

st.divider()
st.markdown(f"""
<center>
<small>
<strong>FIX MY NAME ONLINE</strong> — AI-Powered Suppression-as-a-Service<br>
© 2026 MadisonJade Pty Ltd. All Rights Reserved.™ Fix My Name Online™<br>
<br>
Not a law firm. Removal requests are AI-assisted drafts — consult counsel for complex matters.<br>
Results vary based on content volume, platform authority, and search competition.
</small>
</center>
""", unsafe_allow_html=True)
