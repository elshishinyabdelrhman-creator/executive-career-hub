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
            font-family: 'Inter', sans-serif;
        }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre;
            background-color: #1E1E1E;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

def create_pdf(text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=10)
        # Clean text for PDF compatibility (Remove AI artifacts)
        clean_text = text.replace('*', '').replace('#', '').replace('•', '-')
        clean_text = unicodedata.normalize('NFKD', clean_text).encode('latin-1', 'ignore').decode('latin-1')
        pdf.multi_cell(0, 8, clean_text)
        return bytes(pdf.output())
    except Exception as e:
        return None

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

# API Configuration
active_api_key = st.secrets.get("GEMINI_API_KEY")
MODEL_ID = "gemini-1.5-flash"

st.title("🚀 Strategic Resume Architect")
st.caption("v4.5 | Luxury & Retail Optimization | Gemini Paid Tier")

tab1, tab2 = st.tabs(["🚀 Strategic Audit", "📊 Application History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Target Company", placeholder="e.g. Sofitel, Extra, Dabouq")
        title = st.text_input("Target Role", placeholder="e.g. General Manager")
        job_desc = st.text_area("Paste Full Job Description", height=300)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")
        st.info("PRO MODE: Generating 12-15 exhaustive achievement bullets for your current role.")

    if st.button("✨ ARCHITECT COMPLETE RESUME"):
        if not active_api_key or not uploaded_file or not job_desc:
            st.warning("All fields (Resume, JD, and API Key) are required.")
        else:
            with st.spinner(f"Curating executive profile for {company}..."):
                try:
                    # PDF Extraction
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = genai.Client(api_key=active_api_key)

                    # --- The "Surgical" Industry-Agnostic Prompt ---
                    prompt = f"""
                    Act as a C-Level Executive Resume Ghostwriter for {company}.
                    Rewrite the candidate's resume to be a 100% PERFECT FIT for {title}.

                    STRICT FORMATTING RULES:
                    1. NO PLACEHOLDERS: Use zero asterisks (*). Do not say [Date] or [Company].
                    2. ABOUT ME: Write 6 sophisticated sentences that blend {company}'s specific industry tone with the candidate's 10+ years of expertise.
                    3. CURRENT ROLE DEEP-DIVE:
                       - Take the MOST RECENT role (Dabouq/Oxygen Saudi) and rewrite it COMPLETELY.
                       - Provide EXACTLY 15 exhaustive, detail-rich achievement bullets.
                       - Each bullet must be 2 lines long, focusing on a RESULT + a specific METRIC.
                       - If it's luxury ({company}=Sofitel), use terms like 'Guest Journey Artistry' and 'Brand Stewardship'.
                       - If it's retail/tech ({company}=Extra), use 'Unit Economics', 'P&L Ownership', and 'Ecosystem Conversion'.
                    4. PREVIOUS ROLES: Maintain their full original length and text exactly as they are.
                    5. COMPETENCIES: Categorize 20+ relevant technical and leadership keywords for the ATS.

                    RESUME: {resume_text}
                    JD: {job_desc}
                    """

                    # Generate Content
                    response = client.models.generate_content(model=MODEL_ID, contents=prompt)
                    tailored_content = response.text.replace('*', '').replace('#', '')

                    # Extract Scores
                    score_res = client.models.generate_content(
                        model=MODEL_ID, 
                        contents=f"Return only two integers separated by a comma (Match, ATS) for this: {tailored_content}"
                    )
                    try:
                        scores = score_res.text.strip().split(',')
                        sm = int(''.join(filter(str.isdigit, scores[0])))
                        sa = int(''.join(filter(str.isdigit, scores[1])))
                    except:
                        sm, sa = 0, 0

                    # Save to DB
                    c.execute("INSERT INTO applications (date, company, title, status, analysis, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", tailored_content, sm, sa))
                    conn.commit()

                    # UI Results
                    st.markdown("### 📊 Alignment Scores")
                    m1, m2 = st.columns(2)
                    with m1: display_colored_metric("Industry Match", sm)
                    with m2: display_colored_metric("ATS Visibility", sa)

                    st.markdown("### 📝 Tailored Executive Document")
                    st.markdown(f'<div class="resume-block">{tailored_content}</div>', unsafe_allow_html=True)
                    
                    # PDF Download
                    pdf_data = create_pdf(tailored_content)
                    if pdf_data:
                        st.download_button(
                            label="📥 Download Tailored Strategy (PDF)",
                            data=pdf_data,
                            file_name=f"Executive_Resume_{company}.pdf",
                            mime="application/pdf"
                        )

                except Exception as e:
                    st.error(f"System Error: {e}")

with tab2:
    st.header("Strategic Tracking System")
    history_df = pd.read_sql_query("SELECT id, date, company, title, score_match, score_ats FROM applications ORDER BY id DESC", conn)
    if not history_df.empty:
        st.dataframe(history_df, use_container_width=True)
        
        selected_id = st.selectbox("View Details for Past Application:", history_df['id'])
        if selected_id:
            detail = pd.read_sql_query(f"SELECT analysis FROM applications WHERE id={selected_id}", conn).iloc[0]['analysis']
            st.markdown(f'<div class="resume-block">{detail}</div>', unsafe_allow_html=True)
    else:
        st.info("No applications in the pipeline yet.")