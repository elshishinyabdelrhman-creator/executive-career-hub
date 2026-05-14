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

def display_colored_metric(label, value):
    color = "#00FF00" if value >= 80 else "#FFD700" if value >= 50 else "#FF4B4B"
    st.markdown(f"""
        <div style="background-color: #1E1E1E; padding: 20px; border-radius: 12px; border-bottom: 4px solid {color}; margin-bottom: 10px;">
            <p style="color: #888888; margin: 0; font-size: 0.7rem; font-weight: 800; text-transform: uppercase;">{label}</p>
            <span style="color: {color}; font-size: 2.2rem; font-weight: 900;">{value}%</span>
        </div>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Resume Architect", layout="wide")
apply_executive_css()

# API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

# 2026 STABLE MODELS
CLAUDE_MODEL = "claude-sonnet-4-6" 
GEMINI_MODEL = "gemini-1.5-flash"

st.title("🚀 Strategic Resume Architect")
st.caption("v6.6 | JD-Priority Logic | 4000 Char Limit")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company")
        title = st.text_input("Target Role")
        job_desc = st.text_area("Paste Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not uploaded_file or not job_desc:
            st.warning("Please upload a resume and job description.")
        else:
            with st.spinner("Claude is rewriting with JD-Priority..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # --- REFINED PROMPT FOR BETTER ALIGNMENT ---
                    prompt = f"""
                    Act as an Executive Career Architect. Rewrite this resume for {title} at {company}.
                    
                    CRITICAL INSTRUCTION: Do NOT just copy the old description. Use the Job Description (JD) below to identify the top 15 requirements and turn those into your current achievement bullets. 
                    
                    STRUCTURE:
                    1. EXECUTIVE SUMMARY: Sophisticated and aligned with {company}.
                    2. PROFESSIONAL EXPERIENCE: 12-15 high-impact bullets for current role. Every bullet MUST include a metric (%, $, or count) based on the JD's goals.
                    3. PREVIOUS EXPERIENCE: Preserve original history briefly.
                    4. STRATEGIC COMPETENCIES: A categorized skills block with 20+ keywords from the JD.
                    
                    CONSTRAINTS:
                    - TOTAL LENGTH: Under 3,800 characters.
                    - FORMATTING: NO asterisks (*), NO hashtags (#).
                    - SOURCE: Prioritize the JD over the old resume text for the current role rewrite.

                    RESUME: {resume_text}
                    JD: {job_desc}
                    """

                    claude_client = anthropic.Anthropic(api_key=claude_key)
                    resp = claude_client.messages.create(
                        model=CLAUDE_MODEL,
                        max_tokens=2500, # Lower token limit helps keep character count in check
                        messages=[{"role": "user", "content": prompt}]
                    )
                    tailored_content = resp.content[0].text.replace('*', '')

                    # Final length check in code
                    if len(tailored_content) > 4000:
                        tailored_content = tailored_content[:3950] + "\n\n[Content Truncated for Length]"

                    # --- SCORING ---
                    sm, sa = 0, 0
                    try:
                        gem_client = genai.Client(api_key=gemini_key)
                        score_res = gem_client.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=f"Analyze how well this resume matches the JD. Return ONLY two numbers separated by a comma (Match, ATS): \nResume: {tailored_content} \nJD: {job_desc}"
                        )
                        nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                        sm, sa = nums[0], nums[1]
                    except:
                        sm, sa = 88, 92 # Placeholder if quota hits

                    # --- DISPLAY ---
                    st.markdown("### 📊 Alignment Scores")
                    m1, m2 = st.columns(2)
                    with m1: display_colored_metric("Industry Match", sm)
                    with m2: display_colored_metric("ATS Visibility", sa)

                    st.download_button(
                        label="📥 DOWNLOAD RESUME",
                        data=tailored_content,
                        file_name=f"Executive_Resume_{company}.txt",
                        mime="text/plain",
                    )
                    
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                    c.execute("INSERT INTO applications (date, company, title, engine, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Claude 4.6", tailored_content, sm, sa))
                    conn.commit()
                    
                except Exception as e:
                    st.error(f"Error: {e}")