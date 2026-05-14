import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
from datetime import datetime

# --- Database Setup ---
conn = sqlite3.connect('career_hub_v6.db', check_same_thread=False)
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

st.set_page_config(page_title="Executive Resume Architect", layout="wide")
apply_executive_css()

# API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

# --- 2026 STABLE PRODUCTION MODEL IDs ---
# Using the standard dateless format required for 2026
CLAUDE_MODEL = "claude-sonnet-4-6" 
GEMINI_MODEL = "gemini-1.5-flash"

st.title("🚀 Strategic Resume Architect")
st.caption("v6.4 | Claude Sonnet 4.6 (Primary) | Database v6 Stable")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra")
        title = st.text_input("Target Role", placeholder="e.g. General Manager")
        job_desc = st.text_area("Paste Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")
        st.success("Claude 4.6 Engine Ready")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not uploaded_file or not job_desc:
            st.warning("Please upload a resume and job description.")
        else:
            with st.spinner("Claude 4.6 is architecting your resume..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # 1. ARCHITECT WITH CLAUDE
                    claude_client = anthropic.Anthropic(api_key=claude_key)
                    
                    prompt = f"""
                    Act as an Executive Career Architect. Rewrite this resume for {title} at {company}.
                    - NO PLACEHOLDERS: Use zero asterisks (*). 
                    - IMPACT: 15 exhaustive achievement bullets focusing on P&L, ROI, and Saudi market scale.
                    - SKILLS: Categorized 'Strategic Competencies' section with 20+ keywords.
                    RESUME: {resume_text} \n JD: {job_desc}
                    """

                    resp = claude_client.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    tailored_content = resp.content[0].text.replace('*', '')

                    # 2. SAVE & DISPLAY
                    c.execute("INSERT INTO applications (date, company, title, engine, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Claude 4.6", tailored_content, 0, 0))
                    conn.commit()

                    st.markdown("### 📝 Tailored Executive Document")
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Claude Engine Error: {e}")
                    st.info("Ensure your Anthropic key has active credits and that the model ID is correct.")

with tab2:
    import pandas as pd
    st.header("Strategic Tracking System")
    try:
        history_df = pd.read_sql_query("SELECT date, company, title, engine FROM applications ORDER BY date DESC", conn)
        st.dataframe(history_df, use_container_width=True)
    except:
        st.info("No logs found in Database v6.")