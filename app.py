import streamlit as st
from google import genai
from pypdf import PdfReader
from fpdf import FPDF
import sqlite3
import pandas as pd
from datetime import datetime
import unicodedata

# --- Database Setup (v4) ---
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
            padding: 30px;
            border-radius: 10px;
            color: #E6EDF3;
            line-height: 1.7;
            white-space: pre-wrap;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        </style>
    """, unsafe_allow_html=True)

def create_pdf(text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        # Use multi_cell for long text blocks
        clean_text = unicodedata.normalize('NFKD', text).encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, clean_text)
        return bytes(pdf.output())
    except: return None

def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 22px; border-radius: 12px; border-bottom: 4px solid {color}; margin-bottom: 10px;">
            <p style="color: #888888; margin: 0; font-size: 0.75rem; font-weight: 800; letter-spacing: 1px;">{label.upper()}</p>
            <span style="color: {color}; margin: 0; font-size: 2.8rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

# --- Main App ---
st.set_page_config(page_title="Executive Resume Architect", layout="wide", page_icon="💼")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

st.title("🚀 Strategic Resume Architect")
st.caption("Deep-Dive Current Role Optimization | Legacy Protection Mode")

col_a, col_b = st.columns([2, 1])

with col_a:
    company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra, or Aramco")
    title = st.text_input("Target Role", placeholder="e.g. General Manager")
    job_desc = st.text_area("Paste Full Job Description", height=300)

with col_b:
    uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
    st.info("PRO MODE: This will provide a full, exhaustive rewrite of your CURRENT role to match the JD perfectly, while keeping all past work history exactly as it is.")

if st.button("✨ ARCHITECT TARGETED RESUME"):
    if not active_api_key or not uploaded_file or not job_desc:
        st.warning("All inputs (Resume, JD, and API Key) are required.")
    else:
        with st.spinner(f"Re-engineering your current impact for {company}..."):
            try:
                reader = PdfReader(uploaded_file)
                resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                client = genai.Client(api_key=active_api_key)

                # --- The "Surgical" Prompt ---
                prompt = f"""
                Act as a specialized Executive Career Architect. 
                Your mission is to generate a copy-paste ready resume for {title} at {company}.

                MANDATORY RULES:
                1. SCORES: Output (MatchScore, ATSScore).
                2. TAILORED SUMMARY: Write a full 5-sentence executive summary mirroring the {company} culture.
                3. TAILORED SKILLS: Provide a full list of 15+ relevant keywords.
                4. CURRENT ROLE OPTIMIZATION (THE FIX): 
                   - Take the MOST RECENT role from the resume and rewrite it COMPLETELY. 
                   - Provide 6-8 comprehensive, detailed bullet points that use industry KPIs (e.g., if luxury, focus on guest journey/brand; if retail, focus on attach rates/P&L). 
                   - Ensure these bullets are long, professional, and exhaustive. No shortcuts.
                5. PREVIOUS ROLES (THE PRESERVATION): 
                   - List every previous role found in the resume exactly as it is, maintaining its original length and detail. Do not summarize or shorten them.

                RESUME: {resume_text}
                JD: {job_desc}
                """

                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                tailored_content = response.text

                # Score Extraction
                score_res = client.models.generate_content(model="gemini-2.5-flash", 
                            contents=f"Extract only 2 integers (Match, ATS) from this: {tailored_content}")
                try: sm, sa = map(int, score_res.text.strip().split(','))
                except: sm, sa = 0, 0

                # Display Results
                st.markdown("### 📊 Alignment Scores")
                m1, m2 = st.columns(2)
                with m1: display_colored_metric("Industry Match", sm)
                with m2: display_colored_metric("ATS Visibility", sa)

                st.markdown("### 📝 Tailored Resume Architecture")
                st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                
                # PDF Download
                pdf_data = create_pdf(tailored_content)
                if pdf_data:
                    st.download_button(
                        label="📥 Download Full Strategy (PDF)",
                        data=pdf_data,
                        file_name=f"Executive_Resume_{company}.pdf",
                        mime="application/pdf"
                    )

            except Exception as e:
                st.error(f"Analysis Failed: {e}")