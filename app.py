import streamlit as st
from google import genai
from pypdf import PdfReader
from fpdf import FPDF
import markdown2
import unicodedata
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup ---
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
        .main { background-color: #0E1117; }
        div[data-testid="metric-container"] {
            background-color: #1E1E1E !important;
            border: 1px solid #333333 !important;
            padding: 20px !important;
            border-radius: 15px !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
        }
        [data-testid="stMetricLabel"] {
            color: #B0B0B0 !important;
            font-size: 0.9rem !important;
            text-transform: uppercase;
            font-weight: 600;
        }
        [data-testid="stSidebar"] {
            background-color: #161B22;
            border-right: 1px solid #30363D;
        }
        </style>
    """, unsafe_allow_html=True)

def display_colored_metric(label, value):
    # Traffic Light Color Logic
    if value >= 80:
        color = "#00FF00"  # Green
        status = "PASSED"
    elif value >= 50:
        color = "#FFD700"  # Yellow
        status = "NEEDS TAILORING"
    else:
        color = "#FF4B4B"  # Red
        status = "WEAK MATCH"
    
    st.markdown(f"""
        <div style="
            background-color: #1E1E1E; 
            padding: 22px; 
            border-radius: 12px; 
            border-bottom: 4px solid {color};
            margin-bottom: 10px;
            box-shadow: 2px 2px 15px rgba(0,0,0,0.4);">
            <p style="color: #888888; margin: 0; font-size: 0.75rem; font-weight: 800; letter-spacing: 1px;">{label.upper()}</p>
            <div style="display: flex; align-items: baseline; gap: 10px;">
                <span style="color: {color}; margin: 0; font-size: 2.8rem; font-weight: 900;">{value}%</span>
                <span style="color: {color}; font-size: 0.8rem; font-weight: 600; opacity: 0.8;">{status}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- PDF Generation Engine ---
def create_pdf(markdown_text):
    try:
        pdf = FPDF()
        pdf.add_page(); pdf.set_font("Arial", size=11)
        html = markdown2.markdown(markdown_text)
        clean_html = unicodedata.normalize('NFKD', html).encode('latin-1', 'ignore').decode('latin-1')
        pdf.write_html(clean_html)
        return bytes(pdf.output())
    except: return None

# --- Main App ---
st.set_page_config(page_title="Executive Career Hub", layout="wide", page_icon="💼")
apply_executive_css()

active_api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.title("👨‍💼 Executive Admin")
    if active_api_key:
        st.success("Cloud Key: ACTIVE")
    else:
        st.error("Missing API Key in Secrets.")
    st.divider()
    st.write("**Target Market:** GCC / Saudi Arabia")
    st.write("**Focus:** Digital Service Growth & P&L")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 Pipeline Tracker"])

with tab1:
    st.title("Strategic Command Center")
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        company = st.text_input("Company (e.g. Extra, Qynda)", placeholder="United Electronics Co.")
        title = st.text_input("Target Role", placeholder="Digital Service Growth Manager")
        job_desc = st.text_area("Job Mandate (Paste JD here)", height=280)
    
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")
        st.info("AI Audit will specifically target 'Service Product' gaps and 'Attach Rate' KPIs.")

    if st.button("🚀 EXECUTE DUAL-SCORE & WEAKNESS AUDIT"):
        if not active_api_key or not uploaded_file or not job_desc:
            st.warning("Ensure Resume, JD, and API Key are present.")
        else:
            with st.spinner("Decoding ATS, Weaknesses, and Market Fit..."):
                try:
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = genai.Client(api_key=active_api_key)
                    
                    # Strategic Audit Prompt
                    prompt = f"""
                    Act as a 2026 Digital Commerce Executive Recruiter. 
                    Perform a high-stakes audit of this Resume against the JD for {title} at {company}.

                    STRICT OUTPUT STRUCTURE:
                    1. **SCORES**: Output ONLY 3 integers (MatchScore, ATSScore, TailoredPotential).
                    2. **CRITICAL WEAKNESS POINTS**: Identify 5 areas where the resume is weak regarding Service Products, Attach Rates, and Marketplace mechanics.
                    3. **THE 'GAP' INJECTION PLAN**: Provide the Top 10 missing keywords (e.g., Attach Rate, PDP Optimization, Subscription Services) and where to put them.
                    4. **EXECUTIVE REWRITE**: Provide a 5-sentence 'About Me' and 3 'AI-Augmented' bullets for the resume.

                    RESUME: {resume_text}
                    JD: {job_desc}
                    """
                    
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    analysis_text = response.text
                    
                    # Numeric Extraction
                    score_res = client.models.generate_content(model="gemini-2.5-flash", 
                                contents=f"Output ONLY 3 integers separated by commas: {analysis_text}")
                    try:
                        sm, sa, st_score = map(int, score_res.text.strip().split(','))
                    except: sm, sa, st_score = 0, 0, 0

                    c.execute('''INSERT INTO applications 
                                 (date, company, title, status, notes, analysis, score_before, score_after, ats_score) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", "", analysis_text, sm, st_score, sa))
                    conn.commit()

                    # Scoring Dashboard
                    st.markdown("### 📊 Scoring & Weakness Dashboard")
                    m1, m2, m3 = st.columns(3)
                    with m1: display_colored_metric("Experience Match", sm)
                    with m2: display_colored_metric("ATS Technical Score", sa)
                    with m3: display_colored_metric("Potential Tailored Score", st_score)
                    
                    st.divider()
                    st.markdown(analysis_text)
                    
                    pdf_data = create_pdf(analysis_text)
                    if pdf_data:
                        st.download_button("📥 Download Full Audit (PDF)", data=pdf_data, file_name=f"Audit_{company}.pdf")
                                           
                except Exception as e:
                    st.error(f"Audit Error: {e}")

with tab2:
    st.header("Strategic Application History")
    df = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    
    if not df.empty:
        for date, group in df.groupby('date'):
            st.subheader(f"📅 {date}")
            for _, row in group.iterrows():
                label = f"{row['company']} | {row['title']} | Score: {row['score_after']}%"
                with st.expander(label):
                    st.markdown(row['analysis'])
    else:
        st.info("Your application pipeline is currently empty.")