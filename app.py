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

# --- Professional UI & Traffic Light Logic ---
def apply_executive_css():
    st.markdown("""
        <style>
        /* Base Background and Font */
        .main { background-color: #0E1117; }
        
        /* Glassmorphism Metric Cards */
        div[data-testid="metric-container"] {
            background-color: #1E1E1E !important;
            border: 1px solid #333333 !important;
            padding: 20px !important;
            border-radius: 15px !important;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3) !important;
        }

        /* Metric Labels */
        [data-testid="stMetricLabel"] {
            color: #B0B0B0 !important;
            font-size: 0.9rem !important;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-weight: 600;
        }

        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: #161B22;
            border-right: 1px solid #30363D;
        }
        </style>
    """, unsafe_allow_html=True)

def display_colored_metric(label, value):
    # Traffic Light Color Logic
    if value >= 80:
        color = "#00FF00"  # Professional Green
        status_text = "HIGH"
    elif value >= 50:
        color = "#FFD700"  # Professional Yellow
        status_text = "MEDIUM"
    else:
        color = "#FF4B4B"  # Professional Red
        status_text = "CRITICAL"
    
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
                <span style="color: {color}; font-size: 0.8rem; font-weight: 600; opacity: 0.8;">{status_text}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

# --- PDF Generation Engine ---
def create_pdf(markdown_text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        html = markdown2.markdown(markdown_text)
        clean_html = unicodedata.normalize('NFKD', html).encode('latin-1', 'ignore').decode('latin-1')
        pdf.write_html(clean_html)
        return bytes(pdf.output())
    except: return None

# --- Main App Interface ---
st.set_page_config(page_title="Executive Career Hub", layout="wide", page_icon="💼")
apply_executive_css()

# API Key Retrieval
active_api_key = st.secrets.get("GEMINI_API_KEY")

with st.sidebar:
    st.title("👨‍💼 Admin")
    if active_api_key:
        st.success("Cloud Key: ACTIVE")
    else:
        st.error("No API Key Found in Secrets.")
    st.divider()
    st.write("**Strategy:** GM / P&L Ownership")
    st.write("**Market:** Saudi Arabia (Vision 2030)")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 Pipeline Tracker"])

with tab1:
    st.title("Strategic Command Center")
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        company = st.text_input("Company", placeholder="e.g. Qynda")
        title = st.text_input("Target Role", placeholder="e.g. General Manager")
        job_desc = st.text_area("Job Mandate (Paste JD here)", height=280)
    
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")
        st.info("Analysis prioritizes GCC market growth, AI integration, and operational efficiency.")

    if st.button("🚀 EXECUTE DUAL-SCORE AUDIT"):
        if not active_api_key or not uploaded_file or not job_desc:
            st.warning("All fields and API key are required.")
        else:
            with st.spinner("Decoding ATS and Market Fit..."):
                try:
                    # PDF Extraction
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = genai.Client(api_key=active_api_key)
                    
                    # Strategic Prompt
                    prompt = f"""
                    Role: {title} at {company}.
                    You are a High-Tier Executive Recruiter and a modern ATS.
                    
                    TASK 1: Output 3 integers separated by commas: (MatchScore, ATSScore, TailoredPotential).
                    TASK 2: Generate a 'Match Analysis' including:
                    - THE PERFECT ABOUT ME (Tailored for {company}).
                    - TOP 10 KEYWORDS GAP.
                    - 3 'AI-AUGMENTED' Bullets for your experience.
                    
                    RESUME: {resume_text}
                    JD: {job_desc}
                    """
                    
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                    analysis_text = response.text
                    
                    # Numeric Extraction
                    score_res = client.models.generate_content(model="gemini-2.5-flash", 
                                contents=f"Based on this analysis, output ONLY 3 integers separated by commas: {analysis_text}")
                    try:
                        sm, sa, st_score = map(int, score_res.text.strip().split(','))
                    except: sm, sa, st_score = 0, 0, 0

                    # Save to DB
                    c.execute('''INSERT INTO applications 
                                 (date, company, title, status, notes, analysis, score_before, score_after, ats_score) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", "", analysis_text, sm, st_score, sa))
                    conn.commit()

                    # Scoring Dashboard with Dynamic Colors
                    st.markdown("### 📊 Executive Scoring Dashboard")
                    m1, m2, m3 = st.columns(3)
                    with m1: display_colored_metric("Current Experience Match", sm)
                    with m2: display_colored_metric("ATS Technical Visibility", sa)
                    with m3: display_colored_metric("After-Optimization Match", st_score)
                    
                    st.divider()
                    st.markdown(analysis_text)
                    
                    # PDF Download
                    pdf_data = create_pdf(analysis_text)
                    if pdf_data:
                        st.download_button("📥 Download Executive Strategy (PDF)", 
                                           data=pdf_data, 
                                           file_name=f"Strategy_{company}.pdf")
                                           
                except Exception as e:
                    st.error(f"Execution Error: {e}")

with tab2:
    st.header("Application Pipeline Tracker")
    df = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    
    if not df.empty:
        for date, group in df.groupby('date'):
            st.subheader(f"📅 {date}")
            for _, row in group.iterrows():
                label = f"{row['company']} | {row['title']} | ATS: {row['ats_score']}%"
                with st.expander(label):
                    st.markdown(row['analysis'])
    else:
        st.info("No applications in pipeline.")