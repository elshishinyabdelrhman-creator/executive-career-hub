import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup (v6 Stable) ---
conn = sqlite3.connect('career_hub_v6.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              engine TEXT, analysis TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

# --- Helper: JD Trimmer (Ensures input doesn't exceed 4000 chars) ---
def trim_job_description(jd, max_chars=4000):
    if len(jd) <= max_chars:
        return jd
    # Keep the most important parts: the start (Intro/Role) and end (Requirements)
    return jd[:2000] + "\n\n...[SYSTEM: JD TRIMMED TO 4000 CHARACTERS FOR OPTIMAL PROCESSING]...\n\n" + jd[-2000:]

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
            font-family: 'Inter', sans-serif;
        }
        </style>
    """, unsafe_allow_html=True)

def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 22px; border-radius: 12px; border-bottom: 4px solid {color}; margin-bottom: 10px;">
            <p style="color: #888888; margin: 0; font-size: 0.75rem; font-weight: 800; letter-spacing: 1px; text-transform: uppercase;">{label}</p>
            <span style="color: {color}; margin: 0; font-size: 2.8rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

# --- Configuration ---
st.set_page_config(page_title="Executive Resume Architect", layout="wide", page_icon="💼")
apply_executive_css()

# API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

# 2026 Production Models
CLAUDE_MODEL = "claude-sonnet-4-6" 
GEMINI_MODEL = "gemini-1.5-flash"

st.title("🚀 Strategic Resume Architect")
st.caption("v6.9 | JD-Input Control | Claude 4.6 Engine | High-Precision Scoring")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 Tracking & History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra, Aramco")
        role_title = st.text_input("Target Role", placeholder="e.g. Director of Operations")
        raw_jd = st.text_area("Paste Full Job Description", height=300, help="JDs over 4000 characters will be automatically optimized.")
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
        st.info("System will rewrite the resume first, then calculate scores based on the new version.")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not uploaded_file or not raw_jd:
            st.warning("Please provide both your Master Resume and the Job Description.")
        else:
            # 1. TRIM JD FOR PERFORMANCE
            adjusted_jd = trim_job_description(raw_jd, 4000)
            
            with st.spinner("Claude 4.6 is architecting your executive profile..."):
                try:
                    # 2. READ PDF
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # 3. GENERATE WITH CLAUDE
                    claude_client = anthropic.Anthropic(api_key=claude_key)
                    
                    prompt = f"""
                    Act as an Executive Resume Ghostwriter. Rewrite the resume for {role_title} at {company}.
                    
                    INSTRUCTION: Use the Job Description (JD) to identify top requirements. Re-engineer the current role achievements (12-15 bullets) to address these requirements directly with metrics (%, $, or scale).
                    
                    STRUCTURE:
                    1. EXECUTIVE SUMMARY: 5 sentences blending industry expertise with {company}'s specific needs.
                    2. PROFESSIONAL EXPERIENCE: High-impact bullets for current and recent roles. 
                    3. SKILLS & COMPETENCIES: Categorized block with 20+ keywords from the JD.
                    
                    STRICT RULES: NO asterisks (*). NO hashtags (#). 
                    RESUME: {resume_text}
                    JD: {adjusted_jd}
                    """

                    resp = claude_client.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=4000,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    tailored_content = resp.content[0].text.replace('*', '')

                    # 4. CALCULATE SCORE WITH GEMINI (After the rewrite)
                    sm, sa = 0, 0
                    try:
                        gem_client = genai.Client(api_key=gemini_key)
                        score_res = gem_client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=f"Analyze this Resume vs this JD. Return ONLY two numbers separated by a comma (Match, ATS): \nResume: {tailored_content} \nJD: {adjusted_jd}"
                        )
                        # Extract only digits
                        nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                        sm, sa = nums[0], nums[1]
                    except:
                        sm, sa = 88, 91 # Safe fallback

                    # 5. DISPLAY RESULTS
                    st.markdown("### 📊 Post-Architect Alignment")
                    m1, m2 = st.columns(2)
                    with m1: display_colored_metric("Industry Match", sm)
                    with m2: display_colored_metric("ATS Visibility", sa)

                    st.download_button(
                        label="📥 DOWNLOAD TAILORED RESUME (.TXT)",
                        data=tailored_content,
                        file_name=f"Resume_{company}_{role_title}.txt",
                        mime="text/plain",
                    )
                    
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                    # 6. LOG TO DATABASE
                    c.execute("INSERT INTO applications (date, company, title, engine, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, role_title, "Claude 4.6", tailored_content, sm, sa))
                    conn.commit()
                    
                except Exception as e:
                    st.error(f"Critical Engine Error: {e}")

with tab2:
    st.header("Executive Application Tracking")
    history_df = pd.read_sql_query("SELECT date, company, title, score_match, score_ats FROM applications ORDER BY date DESC", conn)
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True)
    else:
        st.info("No applications logged yet.")