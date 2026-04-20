"""
app.py
------
Optimized Streamlit UI for the Privacy Policy Analyzer.
Features: Async scraping, latency optimizations, and non-technical readability.
"""

import logging
import os
import re
import asyncio
import sys

import streamlit as st
from dotenv import load_dotenv

# ── Fix for Windows asyncio loop policy (Subprocess support) ────────────────
if sys.platform == 'win32':
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

# Load .env variables (GEMINI_API_KEY)
load_dotenv()

from scraper import scrape_privacy_policy_async, ScraperError
from summarizer import analyze_policy, SummarizerError

# ── Logging Setup ─────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Page Config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Privacy Reader | AI Analysis",
    page_icon="🛡️",
    layout="wide",
)

# ── Modern UI (CSS) ────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    
    .stApp { background-color: #0b0e11; color: #f0f2f5; }
    
    /* Custom Sidebar */
    [data-testid="stSidebar"] {
        background-color: #15191e;
        border-right: 1px solid #2d333b;
    }
    
    /* Card Styles for Readability */
    .metric-card {
        background: #1c2128;
        border: 1px solid #2d333b;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .metric-card:hover { transform: translateY(-3px); }
    
    .card-title {
        color: #58a6ff;
        font-weight: 600;
        font-size: 1.1rem;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
    }
    
    .card-title i { margin-right: 10px; }

    /* Risk Badges */
    .badge {
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 0.9rem;
        text-transform: uppercase;
    }
    .badge-low { background: #238636; color: white; }
    .badge-medium { background: #9e6a03; color: white; }
    .badge-high { background: #da3633; color: white; }
    
    /* Bullet points */
    .p-list { list-style: none; padding: 0; margin: 0; }
    .p-list li {
        margin: 8px 0;
        padding-left: 20px;
        position: relative;
        font-size: 0.95rem;
        color: #adbac7;
    }
    .p-list li::before {
        content: "•";
        color: #58a6ff;
        position: absolute;
        left: 0;
        font-weight: bold;
    }

    /* Input Styling */
    .stTextInput input {
        background-color: #1c2128 !important;
        border: 1px solid #2d333b !important;
        color: white !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)


# ── Logic Helpers ─────────────────────────────────────────────────────────────

def get_risk_badge(level):
    level = str(level).strip().capitalize()
    if level == "Low": return '<span class="badge badge-low">🟢 Low Risk</span>'
    if level == "Medium": return '<span class="badge badge-medium">🟡 Medium Risk</span>'
    if level == "High": return '<span class="badge badge-high">🔴 High Risk</span>'
    return f'<span class="badge">{level}</span>'

def render_list(items):
    if not items or len(items) == 0:
        return "<p style='color:#768390;'>Nothing detected.</p>"
    lis = "".join([f"<li>{item}</li>" for item in items])
    return f'<ul class="p-list">{lis}</ul>'


# ── Settings & API Logic ───────────────────────────────────────────────────────
api_key_env = os.getenv("GEMINI_API_KEY", "")

# ── Main UI ────────────────────────────────────────────────────────────────────

# Header with Settings
header_c1, header_c2, header_c3 = st.columns([1, 8, 1])
with header_c2:
    st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>🛡️ Privacy Reader</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #768390;'>Instant, simple privacy summaries for non-technical users.</p>", unsafe_allow_html=True)

with header_c3:
    with st.popover("⚙️"):
        use_cache = st.toggle("Enable Result Caching", value=True)

# URL Input Centering
col1, col2, col3 = st.columns([1, 4, 1])
with col2:
    url_input = st.text_input("Enter a Website URL (e.g. google.com)", placeholder="https://facebook.com", label_visibility="collapsed")
    analyze_btn = st.button("Analyze Policy →", use_container_width=True, type="primary")

st.divider()

if analyze_btn:
    if not url_input:
        st.warning("Please enter a URL first.")
        st.stop()
    
    if not api_key_env:
        st.error("Missing GEMINI_API_KEY. Please set it in your .env file.")
        st.stop()

    # Step 1: Scrape
    scrape_status = st.status("🔍 Scraping website...", expanded=True)
    try:
        # Use asyncio.run to call the async scraper
        scrape_result = asyncio.run(scrape_privacy_policy_async(url_input))
        scrape_status.update(label="✅ Website content fetched!", state="complete", expanded=False)
    except ScraperError as e:
        scrape_status.update(label="❌ Scraping failed.", state="error")
        st.error(f"Error: {e}")
        st.stop()
    except Exception as e:
        scrape_status.update(label="❌ Unexpected error.", state="error")
        st.exception(e)
        st.stop()

    # Step 2: Summarize
    with st.spinner("🧠 AI is reading the legal text..."):
        try:
            analysis = analyze_policy(
                scrape_result["text"],
                use_cache=use_cache,
                api_key=api_key_env
            )
        except SummarizerError as e:
            st.error(f"AI Analysis failed: {e}")
            st.stop()

    # Step 3: Display Results
    st.success(f"Analysis complete! (Source: {scrape_result['policy_url']})")
    
    # Hero Row
    c1, c2 = st.columns([1, 2])
    
    with c1:
        st.markdown(f"""
            <div class="metric-card" style="text-align:center;">
                <div class="card-title" style="justify-content:center;">RISK LEVEL</div>
                {get_risk_badge(analysis['risk_level'])}
                <div style="margin-top:15px; font-size:0.9rem; color:#adbac7;">
                    {analysis['risk_reason']}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # Risk List
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-title">🚨 BIGGEST RISKS</div>
                {render_list(analysis['key_risks'])}
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
            <div class="metric-card" style="min-height: 100%;">
                <div class="card-title">📝 SIMPLE SUMMARY</div>
                <p style="font-size:1.1rem; line-height:1.6; color:#f0f2f5;">
                    {analysis['summary']}
                </p>
                <hr style="border: 0; border-top: 1px solid #2d333b;">
                <div style="display:flex; justify-content:space-between; color:#768390; font-size:0.85rem;">
                    <span>Cached: {"Yes" if analysis.get("_from_cache") else "No"}</span>
                    <span>Length: {len(scrape_result['text'])} chars</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # Detailed Grid
    d1, d2, d3 = st.columns(3)
    
    with d1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-title">👤 INFO TAKEN</div>
                {render_list(analysis['data_collection'])}
            </div>
        """, unsafe_allow_html=True)

    with d2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-title">🤝 SHARED WITH</div>
                {render_list(analysis['third_party_sharing'])}
            </div>
        """, unsafe_allow_html=True)

    with d3:
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-title">🍪 TRACKING</div>
                {render_list(analysis['tracking_cookies'])}
            </div>
        """, unsafe_allow_html=True)

    # Secondary Info
    e1, e2 = st.columns(2)
    with e1:
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-title">🛡️ YOUR RIGHTS</div>
                {render_list(analysis['user_rights'])}
            </div>
        """, unsafe_allow_html=True)
    with e2:
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-title">⚠️ SNEAKY PHRASES</div>
                {render_list(analysis['suspicious_clauses'])}
            </div>
        """, unsafe_allow_html=True)

    # Original text expander
    with st.expander("Show Raw Legal Text"):
        st.code(scrape_result["text"], language="text")

else:
    # Empty State
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.info("💡 **Tip:** Try entering a homepage like `openai.com` - we'll find the privacy link for you!")
    st.markdown("<p style='text-align: center; color: #768390; font-size: 0.9rem;'>Most policies are intentionally long and confusing. We use AI to find exactly <b>what info is taken</b> and <b>who it is shared with</b>.</p>", unsafe_allow_html=True)
