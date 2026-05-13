import streamlit as st
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup ---
conn = sqlite3.connect('career_hub_v3.db', check_same_thread=False)
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
            padding: 25px;
            border-radius: 8px;
            color: #E6EDF3;
            line-height: 1.6;
        }
        </style>
    """, unsafe_allow_html=True)

def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 20px; border-radius: 10px; border-bottom: 4px solid {color};">
            <p style="color: #888888; margin: 0; font-size: 0.8rem; font-weight: 800;">{label.upper()}</p>
            <span style="color: {color}; margin: 0; font-size: 2.5rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

# --- Main App ---
st.set_page_config(page_title="Executive Resume Tailor", layout="wide", page_icon="💼")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

st.title("🚀 Executive Resume Auto-Tailor")
st.caption("Industry-Agnostic | 2026 AI-Driven Precision")

col_a, col_b = st.columns([2, 1])

with col_a:
    company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra, or Saudi Aramco")
    title = st.text_input("Target Role", placeholder="e.g. General Manager or Digital Director")
    job_desc = st.text_area("Paste Job Description (JD)", height=300)

with col_b:
    uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
    st.info("The AI will now fully rewrite your profile, experience, and skills to mirror this specific role.")

if st.button("✨ GENERATE PERFECT-FIT RESUME"):
    if not active_api_key or not uploaded_file or not job_desc:
        st.warning("Please provide the Resume, JD, and API Key.")
    else:
        with st.spinner(f"Architecting your profile for {company}..."):
            try:
                reader = PdfReader(uploaded_file)
                resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                client = genai.Client(api_key=active_api_key)

                # --- The "Universal Architect" Prompt ---
                prompt = f"""
                Act as a specialized Executive Career Architect for the {company} industry.
                Your mission is to rewrite the provided Resume to be a 100% PERFECT FIT for the role of {title}.

                OUTPUT STRUCTURE:
                1. SCORES: Two integers (MatchScore, ATSScore).
                2. ADJUSTED ABOUT ME: A high-impact summary mirroring the company's culture and the JD's seniority.
                3. ADJUSTED CORE COMPETENCIES: A list of 12 keywords tailored for this JD's ATS.
                4. ADJUSTED WORK EXPERIENCE: Rewrite the top 3 roles from the resume. For each role, provide 3 bullets that use the industry's specific KPIs (e.g. Guest Journey for Luxury, Attach Rates for Retail, P&L for GM).
                5. ADJUSTED SKILLS: A categorized list of hard and soft skills.

                RESUME: {resume_text}
                JD: {job_desc}
                """

                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                tailored_content = response.text

                # Score Extraction
                score_res = client.models.generate_content(model="gemini-2.5-flash", 
                            contents=f"Extract only 2 integers (Match, ATS) from this text: {tailored_content}")
                try: sm, sa = map(int, score_res.text.strip().split(','))
                except: sm, sa = 0, 0

                # Save to History
                c.execute("INSERT INTO applications (date, company, title, status, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (datetime.now().strftime("%Y-%m-%d"), company, title, "Tailored", tailored_content, sm, sa))
                conn.commit()

                # Display Results
                st.markdown("### 📊 Alignment Scores")
                m1, m2 = st.columns(2)
                with m1: display_colored_metric("Industry Match", sm)
                with m2: display_colored_metric("ATS Visibility", sa)

                st.markdown("### 📝 Your Tailored Resume Content")
                st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                st.success("Copy the sections above directly into your Master Template.")

            except Exception as e:
                st.error(f"Error: {e}")