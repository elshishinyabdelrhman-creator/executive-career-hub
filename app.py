import streamlit as st
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
import unicodedata

# --- Database Setup (v5) ---
conn = sqlite3.connect('career_hub_v5.db', check_same_thread=False)
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

# --- Configuration ---
st.set_page_config(page_title="Executive Resume Architect", layout="wide")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

# 2026 STABLE PRODUCTION MODEL
# Shorthand for the newly released Stable version
MODEL_ID = "gemini-3.1-flash-lite" 

st.title("🚀 Strategic Resume Architect")
st.caption("v6.0 | Gemini 3.1 Stable Path | Free Tier Optimized")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Extra")
        title = st.text_input("Target Role", placeholder="e.g. Director")
        job_desc = st.text_area("Paste Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")
        engine_choice = st.radio("Primary Writing Engine:", ["Gemini 3.1 Flash-Lite", "Claude (Dormant)"])

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if "Dormant" in engine_choice:
            st.error("Claude is deactivated. Use Gemini 3.1.")
        elif not uploaded_file or not job_desc:
            st.warning("All inputs required.")
        else:
            with st.spinner("Establishing Production Connection..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # CLIENT INITIALIZATION: Explicitly using the production 'v1' route
                    client = genai.Client(
                        api_key=active_api_key,
                        http_options={'api_version': 'v1'}
                    )

                    prompt = f"""
                    Act as an Executive Career Architect. Rewrite this resume for {title} at {company}.
                    1. NO PLACEHOLDERS: Use zero asterisks (*). 
                    2. CURRENT ROLE: 15 exhaustive achievement bullets focusing on P&L and ROI.
                    3. SKILLS: Categorized 'Strategic Competencies' section with 20+ keywords.
                    RESUME: {resume_text} \n JD: {job_desc}
                    """

                    # DYNAMIC ROUTING: If the shorthand fails, the system auto-tries the absolute path
                    try:
                        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
                    except Exception as route_err:
                        if "404" in str(route_err):
                            # Attempting the longhand 'models/' prefix which is sometimes required by the new v1 SDK
                            response = client.models.generate_content(model=f"models/{MODEL_ID}", contents=prompt)
                        else:
                            raise route_err

                    tailored_content = response.text.replace('*', '').replace('#', '')

                    c.execute("INSERT INTO applications (date, company, title, engine, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Gemini 3.1", tailored_content, 0, 0))
                    conn.commit()

                    st.markdown("### 📝 Tailored Executive Document")
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Critical System Error: {e}")

with tab2:
    st.header("Strategic Tracking System")
    try:
        history_df = pd.read_sql_query("SELECT date, company, title, engine FROM applications ORDER BY date DESC", conn)
        st.dataframe(history_df, use_container_width=True)
    except:
        st.info("No logs yet.")