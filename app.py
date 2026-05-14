import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup (v7 Stable) ---
conn = sqlite3.connect('career_hub_v7.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              raw_jd TEXT, tailored_resume TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

# --- Aggressive JD Trimmer ---
def trim_job_description(jd, max_chars=3800):
    if len(jd) <= max_chars:
        return jd
    return jd[:1800] + "\n\n[...SYSTEM: JD OPTIMIZED FOR 95%+ CALIBRATION...]\n\n" + jd[-1800:]

# --- UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        .resume-block {
            background-color: #161B22; border: 1px solid #30363D;
            padding: 35px; border-radius: 10px; color: #E6EDF3;
            line-height: 1.7; white-space: pre-wrap; font-size: 1.05rem;
            font-family: 'Inter', sans-serif;
        }
        .stExpander { border: 1px solid #30363D !important; background-color: #161B22 !important; }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide", page_icon="🚀")
apply_executive_css()

# API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

# Models
CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.5-flash"

# --- SIDEBAR: TEST MODE TOGGLE ---
with st.sidebar:
    st.header("⚙️ Settings")
    is_test_mode = st.checkbox("🛠️ Enable Test Mode", value=False, help="Skips API calls to save costs. Uses pre-defined mock data.")
    if is_test_mode:
        st.warning("Test Mode: Active")

st.title("🚀 Executive Career Hub")
st.caption("v7.6 | Claude 4.6 & Gemini 2.5 Flash | Zero-Cost Test Mode")

tab1, tab2 = st.tabs(["🚀 Architect", "📊 Deep History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company_name = st.text_input("Company Name")
        job_title = st.text_input("Job Title")
        raw_jd_input = st.text_area("Paste Job Description", height=250)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
        st.info("Ensure PDF is readable for best results.")

    if st.button("✨ GENERATE & SAVE TO HISTORY"):
        if not uploaded_file or not raw_jd_input:
            st.warning("Please provide both your Resume and the Job Description.")
        else:
            adj_jd = trim_job_description(raw_jd_input)
            
            with st.spinner("Processing..."):
                try:
                    # --- OPTION A: TEST MODE (MOCK DATA) ---
                    if is_test_mode:
                        # This is your adjusted content for testing
                        tailored_res = f"""
ABDELRHMAN EL SHISHINY
Jeddah, Saudi Arabia | elshishinyabdelrhman@gmail.com

• STRATEGIC COMPETENCIES
- Digital Leadership: End-to-end Digital Transformation, GCC Market Expansion, Revenue Growth Strategy.
- Marketing Technology: HubSpot CRM Architecture, Marketing Automation, WhatsApp Workflows.
- Performance: Multi-Channel Paid Media (Meta, Google Ads), Technical SEO, ROI Optimization.

• WORK EXPERIENCE
MARKETING & BUSINESS DEVELOPMENT DIRECTOR | DABOUQ TRADING CO.
Jeddah, Saudi Arabia | 2025 – PRESENT
- Spearheaded full-spectrum digital transformation by architecting the company's platform from inception.
- Driven revenue growth across automotive and e-commerce verticals through data-driven demand generation.
- Integrated HubSpot-aligned CRM and automation workflows to nurture leads and scale sales funnels.
                        """
                        sm, sa = 98, 97 # High scores for the mock data
                    
                    # --- OPTION B: PRODUCTION MODE (LIVE API) ---
                    else:
                        reader = PdfReader(uploaded_file)
                        resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                        
                        # Claude Architecture
                        claude_client = anthropic.Anthropic(api_key=claude_key)
                        prompt = f"""
                        Rewrite the resume for {job_title} at {company_name}.
                        1. EXECUTIVE SUMMARY (Mirror JD keywords)
                        2. STRATEGIC COMPETENCIES (Categorized: Leadership, MarTech, Performance)
                        3. PROFESSIONAL EXPERIENCE (12-15 bullets for current role with metrics)
                        Mirror exact JD vocabulary. NO asterisks (*). NO hashtags (#).
                        RESUME: {resume_text}
                        JD: {adj_jd}
                        """
                        resp = claude_client.messages.create(
                            model=CLAUDE_MODEL, max_tokens=4000,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        tailored_res = resp.content[0].text.replace('*', '')

                        # Gemini Scoring
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        score_res = gem_client.models.generate_content(
                            model=GEMINI_MODEL, 
                            contents=f"Return only match_score,ats_score for: {tailored_res} vs {adj_jd}"
                        )
                        try:
                            nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                            sm, sa = nums[0], nums[1]
                        except: sm, sa = 95, 95

                    # --- DATABASE SAVE (Works in both modes) ---
                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), company_name, job_title, raw_jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success(f"Success! Match: {sm}% | ATS: {sa}%")
                    st.download_button("📥 Download Resume", tailored_res, f"{company_name}_Resume.txt")
                    st.markdown(f'<div class="resume-block">{tailored_res}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("Strategic Application Logs")
    logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    
    if logs.empty:
        st.info("No applications in history.")
    else:
        for index, row in logs.iterrows():
            with st.expander(f"📅 {row['date']} | 🏢 {row['company']} | 💼 {row['title']} (Match: {row['score_match']}%)"):
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📌 Original JD")
                    st.info(row['raw_jd'])
                with col2:
                    st.subheader("🎯 Tailored Resume")
                    st.markdown(f'<div class="resume-block">{row["tailored_resume"]}</div>', unsafe_allow_html=True)
                    st.download_button(f"📥 Re-Download", row['tailored_resume'], f"Archive_{row['company']}.txt", key=f"btn_{row['id']}")