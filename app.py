import streamlit as st
from google import genai
from pypdf import PdfReader
from fpdf import FPDF
import markdown2
import unicodedata
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup ---
conn = sqlite3.connect('career_hub_v3.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              status TEXT, notes TEXT, analysis TEXT, 
              score_before INTEGER, score_after INTEGER, ats_score INTEGER)''')
conn.commit()

# --- Professional UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        div[data-testid="metric-container"] {
            background-color: #1E1E1E !important;
            border: 1px solid #333333 !important;
            padding: 20px !important;
            border-radius: 15px !important;
        }
        [data-testid="stMetricLabel"] { color: #B0B0B0 !important; font-size: 0.9rem !important; font-weight: 600; }
        .fix-box {
            background-color: #161B22;
            border-left: 5px solid #00FF00;
            padding: 15px;
            margin: 10px 0px;
            border-radius: 4px;
            font-family: monospace;
            color: #E6EDF3;
        }
        </style>
    """, unsafe_allow_html=True)

def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 22px; border-radius: 12px; border-bottom: 4px solid {color}; margin-bottom: 10px;">
            <p style="color: #888888; margin: 0; font-size: 0.75rem; font-weight: 800;">{label.upper()}</p>
            <span style="color: {color}; margin: 0; font-size: 2.8rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

# --- Main App ---
st.set_page_config(page_title="Executive Career Hub", layout="wide", page_icon="💼")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

tab1, tab2 = st.tabs(["🚀 Strategic Audit & Fixes", "📊 Pipeline Tracker"])

with tab1:
    st.title("Strategic Command Center")
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        company = st.text_input("Company", placeholder="e.g. United Electronics (Extra)")
        title = st.text_input("Target Role", placeholder="e.g. Digital Service Growth Manager")
        job_desc = st.text_area("Job Mandate (Paste JD here)", height=280)
    
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")
        st.info("The app will now provide 'Copy-Paste' fixes for every identified weakness.")

    if st.button("🚀 RUN AUDIT & GENERATE FIXES"):
        if not active_api_key or not uploaded_file or not job_desc:
            st.warning("Please provide Resume, JD, and API Key.")
        else:
            with st.spinner("Analyzing Gaps and Writing Fixes..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = genai.Client(api_key=active_api_key)
                    
                    # THE ULTIMATE "FIX-IT" PROMPT
                    prompt = f"""
                    Act as a Digital Commerce Executive Recruiter. 
                    Audit this Resume for {title} at {company}.
                    
                    REQUIREMENT: For every weakness you find, you MUST provide a 'Ready-to-Use' bullet point that fixes it.

                    STRUCTURE:
                    1. **SCORES**: Match Score, ATS Score, Potential Score (3 integers only).
                    2. **CRITICAL WEAKNESSES & INSTANT FIXES**: 
                       - For each weakness (e.g., Attach Rate, API integration, Unit Economics), write a 'COPY-PASTE FIX' achievement bullet.
                    3. **KEYWORD INJECTION**: Top 10 terms missing.
                    4. **FINAL EXECUTIVE REWRITE**: A 95%-match 'About Me' and 3 AI-Augmented bullets.

                    RESUME: {resume_text}
                    JD: {job_desc}
                    """
                    
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    analysis_text = response.text
                    
                    # Score Extraction
                    score_res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Output ONLY 3 integers separated by commas: {analysis_text}")
                    try: sm, sa, st_score = map(int, score_res.text.strip().split(','))
                    except: sm, sa, st_score = 0, 0, 0

                    # Display
                    st.markdown("### 📊 Scoring & Instant Fixes")
                    m1, m2, m3 = st.columns(3)
                    with m1: display_colored_metric("Experience Match", sm)
                    with m2: display_colored_metric("ATS Technical Score", sa)
                    with m3: display_colored_metric("After-Fix Potential", st_score)
                    
                    st.divider()
                    st.markdown(analysis_text)
                                           
                except Exception as e:
                    st.error(f"Audit Error: {e}")