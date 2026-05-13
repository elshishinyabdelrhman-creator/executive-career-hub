import streamlit as st
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup (v4 ensures fresh schema for score_match/score_ats) ---
conn = sqlite3.connect('career_hub_v4.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, 
              date TEXT, 
              company TEXT, 
              title TEXT, 
              status TEXT, 
              analysis TEXT, 
              score_match INTEGER, 
              score_ats INTEGER)''')
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
        [data-testid="stMetricLabel"] {
            color: #B0B0B0 !important;
            font-size: 0.9rem !important;
            text-transform: uppercase;
            font-weight: 600;
        }
        .resume-block {
            background-color: #161B22;
            border: 1px solid #30363D;
            padding: 30px;
            border-radius: 10px;
            color: #E6EDF3;
            line-height: 1.7;
            font-size: 1.1rem;
            white-space: pre-wrap;
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

# --- Main App ---
st.set_page_config(page_title="Executive Resume Tailor", layout="wide", page_icon="💼")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

st.title("🚀 Executive Resume Auto-Tailor")
st.caption("Context-Fluid AI | Resetting Persona for Every Application")

col_a, col_b = st.columns([2, 1])

with col_a:
    company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra, or Aramco")
    title = st.text_input("Target Role", placeholder="e.g. General Manager")
    job_desc = st.text_area("Paste Job Description (JD)", height=300)

with col_b:
    uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
    st.info("The AI will identify the industry tone (Luxury, Retail, etc.) and fully rewrite your resume structure.")

if st.button("✨ GENERATE PERFECT-FIT RESUME"):
    if not active_api_key or not uploaded_file or not job_desc:
        st.warning("All inputs (Resume, JD, and API Key) are required.")
    else:
        with st.spinner(f"Re-architecting profile for {company}..."):
            try:
                # PDF Extraction
                reader = PdfReader(uploaded_file)
                resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                client = genai.Client(api_key=active_api_key)

                # --- Universal Industry-Agnostic Prompt ---
                prompt = f"""
                Act as a world-class Executive Career Architect. 
                Your task is to REWRITE the provided Resume to be a 100% PERFECT FIT for {title} at {company}.
                
                PHASE 1: INDUSTRY CALIBRATION
                - Analyze {company} and the JD to determine the industry (Luxury Hospitality, Retail, Automotive, etc.).
                - Adopt the specific vocabulary and 'Tone of Voice' of that industry.

                PHASE 2: DOCUMENT ARCHITECTURE
                1. SCORES: Two integers (MatchScore, ATSScore).
                2. ADJUSTED ABOUT ME: A high-impact summary that mirrors the brand's culture.
                3. ADJUSTED CORE COMPETENCIES: 12 key terms for this industry's ATS.
                4. ADJUSTED WORK EXPERIENCE: Rewrite the top 3 roles. For each, provide 3 bullets using industry-specific KPIs (e.g. Guest Loyalty for Sofitel, Attach Rates for Extra, P&L Growth for GM roles).
                5. ADJUSTED SKILLS: List technical and leadership skills relevant to this JD.

                RESUME: {resume_text}
                JD: {job_desc}
                """

                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                tailored_content = response.text

                # Score Extraction
                score_res = client.models.generate_content(model="gemini-2.5-flash", 
                            contents=f"Extract only 2 integers separated by a comma (Match, ATS) from this: {tailored_content}")
                try: 
                    sm, sa = map(int, score_res.text.strip().split(','))
                except: 
                    sm, sa = 0, 0

                # Save to Database
                c.execute("INSERT INTO applications (date, company, title, status, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (datetime.now().strftime("%Y-%m-%d"), company, title, "Tailored", tailored_content, sm, sa))
                conn.commit()

                # Results Display
                st.markdown("### 📊 Industry Alignment Scores")
                m1, m2 = st.columns(2)
                with m1: display_colored_metric("Industry Match", sm)
                with m2: display_colored_metric("ATS Visibility", sa)

                st.markdown("### 📝 Your Tailored Resume Architecture")
                st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                
                st.success("Strategy complete. Copy the adjusted content directly into your template.")

            except Exception as e:
                st.error(f"Analysis Failed: {e}")

# History Tab
st.divider()
if st.checkbox("Show Application History"):
    history_df = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    st.dataframe(history_df[['date', 'company', 'title', 'score_match', 'score_ats']])