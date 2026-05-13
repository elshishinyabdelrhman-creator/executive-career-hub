import streamlit as st
from google import genai
from google.genai import types 
from pypdf import PdfReader
from fpdf import FPDF
import sqlite3
import pandas as pd
from datetime import datetime
import unicodedata

# --- Database Setup ---
conn = sqlite3.connect('career_hub_v4.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              status TEXT, analysis TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

# --- Executive UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        div[data-testid="metric-container"] {
            background-color: #1E1E1E !important;
            border: 1px solid #333333 !important;
            padding: 20px !important;
            border-radius: 12px !important;
        }
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

# RESTORED MISSING FUNCTION
def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 22px; border-radius: 12px; border-bottom: 4px solid {color}; margin-bottom: 10px;">
            <p style="color: #888888; margin: 0; font-size: 0.75rem; font-weight: 800; letter-spacing: 1px;">{label.upper()}</p>
            <span style="color: {color}; margin: 0; font-size: 2.8rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

# --- App Logic ---
st.set_page_config(page_title="Executive Resume Architect", layout="wide", page_icon="💼")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")
MODEL_ID = "gemini-2.5-flash" 

st.title("🚀 Strategic Resume Architect")
st.caption("v5.2 | Full Functionality Restored | Gemini 2.5 Flash")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 History & Tracking"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra, Aramco")
        title = st.text_input("Target Role", placeholder="e.g. General Manager")
        job_desc = st.text_area("Paste Full Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not active_api_key or not uploaded_file or not job_desc:
            st.warning("All fields are required.")
        else:
            with st.spinner(f"Connecting to {MODEL_ID} via Production v1 Route..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # Force v1 API version
                    client = genai.Client(
                        api_key=active_api_key,
                        http_options={'api_version': 'v1'}
                    )

                    prompt = f"""
                    Act as an Executive Career Architect. Rewrite this resume for {title} at {company}.
                    1. NO PLACEHOLDERS: Use zero asterisks (*). 
                    2. CURRENT ROLE: 12-15 exhaustive, high-impact achievement bullets.
                    3. PREVIOUS ROLES: Maintain full original text.
                    4. TONE: Industry-specific.
                    RESUME: {resume_text} \n JD: {job_desc}
                    """

                    response = client.models.generate_content(model=MODEL_ID, contents=prompt)
                    tailored_content = response.text.replace('*', '').replace('#', '')

                    score_res = client.models.generate_content(
                        model=MODEL_ID, 
                        contents=f"Return only two integers separated by a comma (Match Score, ATS Score) based on: {tailored_content}"
                    )
                    
                    try:
                        scores = score_res.text.strip().split(',')
                        sm = int(''.join(filter(str.isdigit, scores[0])))
                        sa = int(''.join(filter(str.isdigit, scores[1])))
                    except:
                        sm, sa = 0, 0

                    c.execute("INSERT INTO applications (date, company, title, status, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", tailored_content, sm, sa))
                    conn.commit()

                    st.markdown("### 📊 Alignment Scores")
                    m1, m2 = st.columns(2)
                    with m1: display_colored_metric("Industry Match", sm)
                    with m2: display_colored_metric("ATS Visibility", sa)

                    st.markdown("### 📝 Tailored Resume Document")
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Critical System Error: {e}")

with tab2:
    st.header("Strategic Tracking System")
    history_df = pd.read_sql_query("SELECT id, date, company, title, score_match, score_ats FROM applications ORDER BY id DESC", conn)
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True)