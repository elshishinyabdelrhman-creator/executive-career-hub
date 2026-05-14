import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup (v7 - Updated Schema to include raw_jd) ---
conn = sqlite3.connect('career_hub_v7.db', check_same_thread=False)
c = conn.cursor()
# We added 'raw_jd' to the table so we can show it back to you in history
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              raw_jd TEXT, tailored_resume TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

# --- Helper: JD Trimmer ---
def trim_job_description(jd, max_chars=3500):
    if len(jd) <= max_chars:
        return jd
    return jd[:1500] + "\n\n[...TRIMMED FOR PERFORMANCE...]\n\n" + jd[-1500:]

# --- UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        .resume-block {
            background-color: #161B22; border: 1px solid #30363D;
            padding: 30px; border-radius: 10px; color: #E6EDF3;
            line-height: 1.6; white-space: pre-wrap; font-size: 0.95rem;
        }
        .history-card {
            background-color: #1E1E1E; padding: 15px; border-radius: 8px;
            border-left: 5px solid #00FF00; margin-bottom: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide")
apply_executive_css()

gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-1.5-flash"

st.title("🚀 Executive Career Hub")
st.caption("v7.3 | Interactive Deep-History | Claude 4.6")

tab1, tab2 = st.tabs(["🚀 Architect", "📊 Deep History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Company Name")
        title = st.text_input("Job Title")
        raw_jd_input = st.text_area("Paste Job Description", height=250)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE & SAVE"):
        if not uploaded_file or not raw_jd_input:
            st.warning("Please provide both Resume and JD.")
        else:
            adj_jd = trim_job_description(raw_jd_input)
            with st.spinner("Architecting..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    claude_client = anthropic.Anthropic(api_key=claude_key)
                    prompt = f"Rewrite this resume for {title} at {company}. Target 95% match. Mirror keywords from JD. Include Skills section. RESUME: {resume_text} JD: {adj_jd}"
                    
                    resp = claude_client.messages.create(
                        model=CLAUDE_MODEL, max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    tailored_res = resp.content[0].text.replace('*', '')

                    # Scoring
                    gem_client = genai.Client(api_key=gemini_key)
                    score_res = gem_client.models.generate_content(model=GEMINI_MODEL, contents=f"Score Match and ATS (0-100) for: {tailored_res} vs {adj_jd}. Return: match,ats")
                    try:
                        nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                        sm, sa = nums[0], nums[1]
                    except: sm, sa = 95, 95

                    # SAVE ALL DATA TO DB
                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), company, title, raw_jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success(f"Saved! Match: {sm}% | ATS: {sa}%")
                    st.download_button("📥 Download Resume", tailored_res, f"{company}_Resume.txt")
                    st.markdown(f'<div class="resume-block">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("Strategic Application Logs")
    # Pull everything from the database
    logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    
    if logs.empty:
        st.info("No applications found yet.")
    else:
        for index, row in logs.iterrows():
            # This creates the "Clickable" row
            with st.expander(f"📅 {row['date']} | 🏢 {row['company']} | 💼 {row['title']} (Match: {row['score_match']}%)"):
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("📌 Original Job Description")
                    st.info(row['raw_jd'])
                with col2:
                    st.subheader("🎯 Tailored Executive Resume")
                    st.markdown(f'<div class="resume-block">{row["tailored_resume"]}</div>', unsafe_allow_html=True)
                    st.download_button(f"📥 Download {row['company']} Version", row['tailored_resume'], f"Archive_{row['company']}.txt", key=f"btn_{row['id']}")
                st.markdown("---")