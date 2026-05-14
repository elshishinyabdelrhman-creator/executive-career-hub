import streamlit as st
from google import genai
import anthropic
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
import unicodedata

# --- Database Setup ---
conn = sqlite3.connect('career_hub_v4.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              engine TEXT, analysis TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

# --- Executive UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        .resume-block {
            background-color: #161B22;
            border: 1px solid #30363D;
            padding: 35px;
            border-radius: 10px;
            color: #E6EDF3;
            line-height: 1.8;
            white-space: pre-wrap;
            font-size: 1.05rem;
        }
        </style>
    """, unsafe_allow_html=True)

def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 22px; border-radius: 12px; border-bottom: 4px solid {color}; margin-bottom: 10px;">
            <p style="color: #888888; margin: 0; font-size: 0.75rem; font-weight: 800; letter-spacing: 1px;">{label.upper()}</p>
            <span style="color: {color}; margin: 0; font-size: 2.8rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

# --- Configuration ---
st.set_page_config(page_title="Executive Resume Architect", layout="wide")
apply_executive_css()

# API Keys from Secrets
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

# 2026 Stable Model IDs
GEMINI_MODEL = "gemini-2.5-flash" 
CLAUDE_MODEL = "claude-3-5-sonnet-latest" 

st.title("🚀 Strategic Resume Architect")
st.caption("v5.5 | Hybrid Mode | Connection Stabilized")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Sofitel")
        title = st.text_input("Target Role", placeholder="e.g. General Manager")
        job_desc = st.text_area("Paste Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")
        engine_choice = st.radio("Primary Writing Engine:", ["Claude 3.5 Sonnet", "Gemini 2.5 Flash"])
        st.info("Claude is best for Luxury/Hotel roles.")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not uploaded_file or not job_desc:
            st.warning("All inputs required.")
        else:
            with st.spinner(f"Architecting with {engine_choice}..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    prompt = f"""
                    Act as an Executive Career Architect. Rewrite this resume for {title} at {company}.
                    1. NO PLACEHOLDERS: Use zero asterisks (*). 
                    2. CURRENT ROLE: 12-15 exhaustive achievement bullets.
                    3. SKILLS: Categorized 'Strategic Competencies' section with 20+ keywords.
                    RESUME: {resume_text} \n JD: {job_desc}
                    """

                    if "Claude" in engine_choice:
                        anthro_client = anthropic.Anthropic(api_key=claude_key)
                        resp = anthro_client.messages.create(
                            model=CLAUDE_MODEL,
                            max_tokens=4000,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        tailored_content = resp.content[0].text
                    else:
                        # Production v1 Route for Gemini
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        resp = gem_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
                        tailored_content = resp.text

                    tailored_content = tailored_content.replace('*', '')

                    # Use Gemini for Score Extraction (Cost-efficient)
                    score_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                    score_res = score_client.models.generate_content(
                        model=GEMINI_MODEL, 
                        contents=f"Return only two integers separated by comma (Match, ATS): {tailored_content}"
                    )
                    try:
                        nums = ''.join(c if c.isdigit() or c == ',' else '' for c in score_res.text).split(',')
                        sm, sa = int(nums[0]), int(nums[1])
                    except:
                        sm, sa = 0, 0

                    c.execute("INSERT INTO applications (date, company, title, engine, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, engine_choice, tailored_content, sm, sa))
                    conn.commit()

                    st.markdown("### 📊 Alignment Scores")
                    m1, m2 = st.columns(2)
                    with m1: display_colored_metric("Industry Match", sm)
                    with m2: display_colored_metric("ATS Visibility", sa)

                    st.markdown("### 📝 Tailored Executive Document")
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Critical System Error: {e}")

with tab2:
    st.header("Strategic Tracking System")
    history_df = pd.read_sql_query("SELECT date, company, title, engine, score_match, score_ats FROM applications ORDER BY date DESC", conn)
    st.dataframe(history_df, use_container_width=True)