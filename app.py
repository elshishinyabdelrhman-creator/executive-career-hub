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
            padding: 35px;
            border-radius: 10px;
            color: #E6EDF3;
            line-height: 1.8;
            white-space: pre-wrap;
            font-size: 1.05rem;
        }
        /* Style for the Tracking Table */
        .stDataFrame { background-color: #1E1E1E; border-radius: 10px; }
        </style>
    """, unsafe_allow_html=True)

def create_pdf(text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        clean_text = unicodedata.normalize('NFKD', text).encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 7, clean_text)
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
st.caption("Deep-Dive Optimization | Legacy Protection | Integrated Tracking")

# Create Tabs for cleaner UI
tab1, tab2 = st.tabs(["🚀 Strategic Audit & Architecture", "📊 Application Pipeline & History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Extra, Sofitel, or Aramco")
        title = st.text_input("Target Role", placeholder="e.g. Digital Growth Manager")
        job_desc = st.text_area("Paste Full Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
        st.info("ULTRA-MATCH: Generates 10-15 high-impact bullets for current role.")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not active_api_key or not uploaded_file or not job_desc:
            st.warning("All inputs (Resume, JD, and API Key) are required.")
        else:
            with st.spinner(f"Architecting 15-point achievement set for {company}..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = genai.Client(api_key=active_api_key)

                    prompt = f"""
                    Act as a specialized Executive Career Architect. 
                    Rewrite the resume to be a 'Perfect Fit' for {title} at {company}.

                    MANDATORY ARCHITECTURE RULES:
                    1. SCORES: Output (MatchScore, ATSScore).
                    2. SUMMARY: 6-sentence executive summary mirroring {company}'s industry tone.
                    3. CURRENT ROLE OPTIMIZATION: 
                       - Rewrite the MOST RECENT role completely.
                       - Provide EXACTLY 12-15 exhaustive, detail-rich achievement bullets.
                       - Integrate {company}'s specific KPIs (Attach rates, P&L, Guest Experience, etc.).
                    4. PREVIOUS ROLES: Keep them EXACTLY as they are. No shortening.
                    5. SKILLS: Categorize 20+ relevant terms.

                    RESUME: {resume_text}
                    JD: {job_desc}
                    """

                    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    tailored_content = response.text

                    score_res = client.models.generate_content(model="gemini-2.5-flash", contents=f"Extract only 2 integers (Match, ATS) from this: {tailored_content}")
                    try: sm, sa = map(int, score_res.text.strip().split(','))
                    except: sm, sa = 0, 0

                    # SAVE TO DB
                    c.execute("INSERT INTO applications (date, company, title, status, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", tailored_content, sm, sa))
                    conn.commit()

                    # DISPLAY
                    st.markdown("### 📊 Alignment Scores")
                    m1, m2 = st.columns(2)
                    with m1: display_colored_metric("Industry Match", sm)
                    with m2: display_colored_metric("ATS Visibility", sa)

                    st.markdown("### 📝 Tailored Resume Document")
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                    pdf_data = create_pdf(tailored_content)
                    if pdf_data:
                        st.download_button("📥 Download Tailored Strategy (PDF)", data=pdf_data, file_name=f"Executive_Resume_{company}.pdf")

                except Exception as e:
                    st.error(f"Analysis Failed: {e}")

with tab2:
    st.header("Strategic Tracking System")
    history_df = pd.read_sql_query("SELECT id, date, company, title, score_match, score_ats, status FROM applications ORDER BY id DESC", conn)
    
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True)
        
        selected_id = st.selectbox("View Full Analysis for Application ID:", history_df['id'])
        if selected_id:
            detail = pd.read_sql_query(f"SELECT analysis FROM applications WHERE id={selected_id}", conn).iloc[0]['analysis']
            st.markdown("### Historical Analysis Detail")
            st.markdown(f'<div class="resume-block">{detail}</div>', unsafe_allow_html=True)
    else:
        st.info("No applications in the pipeline yet.")