import streamlit as st
from google import genai
from pypdf import PdfReader
from fpdf import FPDF
import markdown2
import unicodedata
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database & Config ---
conn = sqlite3.connect('career_hub_v3.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              status TEXT, notes TEXT, analysis TEXT, 
              score_before INTEGER, score_after INTEGER, ats_score INTEGER)''')
conn.commit()

# --- Executive UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .metric-card {
            background: #1a1c24;
            border: 1px solid #3d4150;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .stMetric { background-color: #0e1117 !important; border: 1px solid #30363d !important; padding: 15px; border-radius: 12px; }
        </style>
    """, unsafe_allow_html=True)

# --- PDF Engine ---
def create_pdf(markdown_text):
    try:
        pdf = FPDF()
        pdf.add_page(); pdf.set_font("Arial", size=11)
        html = markdown2.markdown(markdown_text)
        clean_html = unicodedata.normalize('NFKD', html).encode('latin-1', 'ignore').decode('latin-1')
        pdf.write_html(clean_html)
        return bytes(pdf.output())
    except: return None

# --- Main Application ---
st.set_page_config(page_title="Executive Hub", layout="wide")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

tab1, tab2 = st.tabs(["🚀 Dual-Score Analysis", "📅 Application Pipeline"])

with tab1:
    st.title("💼 Strategic Command Center")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        company = st.text_input("Target Organization", placeholder="e.g. Qynda")
        title = st.text_input("Strategic Role", placeholder="e.g. General Manager")
        job_desc = st.text_area("Market Mandate / Job Description", height=250)
    
    with col2:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
        st.info("Operating Mode: 2026 Executive P&L Growth")

    if st.button("🚀 Run Dual-Audit Analysis"):
        if active_api_key and uploaded_file and job_desc:
            with st.spinner("Executing Deep Scan & Keyword Audit..."):
                reader = PdfReader(uploaded_file)
                resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                client = genai.Client(api_key=active_api_key)
                
                # Dual-Score Prompt
                prompt = f"""
                You are a Senior Recruiter and an ATS System. Analyze this Resume for the role of {title} at {company}.
                
                Provide:
                1. **MATCH SCORE**: Overall experience alignment (0-100).
                2. **ATS SCORE**: Technical keyword and formatting density (0-100).
                3. **CRITICAL KEYWORD GAP**: Missing terms for {title}.
                4. **EXECUTIVE REWRITE**: About Me and 3 AI-Augmented bullets.
                
                RESUME: {resume_text}
                JD: {job_desc}
                """
                
                response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                
                # Numeric Extraction
                score_p = client.models.generate_content(model="gemini-2.5-flash", contents=f"Output only 3 numbers (MatchScore, ATSScore, TailoredMatchScore) from: {response.text}")
                try: 
                    sm, sa, st_score = map(int, score_p.text.strip().split(','))
                except: sm, sa, st_score = 0, 0, 0

                c.execute('INSERT INTO applications (date, company, title, status, notes, analysis, score_before, score_after, ats_score) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', 
                          (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", "", response.text, sm, st_score, sa))
                conn.commit()

                # Dashboard Display
                st.markdown("### 📊 Scoring Dashboard")
                m1, m2, m3 = st.columns(3)
                m1.metric("Current Match", f"{sm}%")
                m2.metric("ATS Technical Score", f"{sa}%")
                m3.metric("Tailored Potential", f"{st_score}%", f"+{st_score-sm}%")
                
                st.divider()
                st.markdown(response.text)
                
                pdf = create_pdf(response.text)
                if pdf: st.download_button("📥 Download Strategic Report", data=pdf, file_name=f"{company}_Analysis.pdf")

with tab2:
    st.header("Strategic History")
    df = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    if not df.empty:
        for date, group in df.groupby('date'):
            with st.expander(f"📅 {date} | {len(group)} Applications"):
                for _, row in group.iterrows():
                    st.write(f"**{row['company']}** | ATS: {row['ats_score']}% | Match: {row['score_after']}%")
    else:
        st.info("Dashboard is currently empty.")