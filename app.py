import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import base64

# --- Database Setup (v7 Stable) ---
conn = sqlite3.connect('career_hub_v7.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              raw_jd TEXT, tailored_resume TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

# --- Aggressive JD Trimmer ---
def trim_job_description(jd, max_chars=3800):
    if len(jd) <= max_chars:
        return jd
    return jd[:1800] + "\n\n[...SYSTEM: JD OPTIMIZED FOR 95%+ CALIBRATION...]\n\n" + jd[-1800:]

# --- PDF Generation Function ---
def generate_pdf_resume(resume_text, company_name):
    # Professional HTML Template for PDF
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm; background-color: #ffffff; }}
            body {{ font-family: 'Arial', sans-serif; color: #333; line-height: 1.4; font-size: 10pt; }}
            .header {{ text-align: center; border-bottom: 2px solid #1a3a5f; margin-bottom: 15px; padding-bottom: 8px; }}
            h1 {{ color: #1a3a5f; margin: 0; text-transform: uppercase; font-size: 20pt; }}
            pre {{ white-space: pre-wrap; font-family: 'Arial', sans-serif; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>ABDELRHMAN EL SHISHINY</h1>
        </div>
        <pre>{resume_text}</pre>
    </body>
    </html>
    '''
    return HTML(string=html_content).write_pdf()

# --- UI Styling ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        .resume-block {
            background-color: #161B22; border: 1px solid #30363D;
            padding: 35px; border-radius: 10px; color: #E6EDF3;
            line-height: 1.7; white-space: pre-wrap; font-size: 1.05rem;
            font-family: 'Inter', sans-serif;
        }
        .stExpander { border: 1px solid #30363D !important; background-color: #161B22 !important; }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide", page_icon="🚀")
apply_executive_css()

# API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

# Models
CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.5-flash"

# --- SIDEBAR: TEST MODE TOGGLE ---
with st.sidebar:
    st.header("⚙️ Settings")
    is_test_mode = st.checkbox("🛠️ Enable Test Mode", value=False)

st.title("🚀 Executive Career Hub")
st.caption("v7.8 | PDF Export Enabled | Full History Mock Data")

tab1, tab2 = st.tabs(["🚀 Architect", "📊 Deep History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company_name = st.text_input("Company Name")
        job_title = st.text_input("Job Title")
        raw_jd_input = st.text_area("Paste Job Description", height=250)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")

    if st.button("✨ GENERATE & SAVE TO HISTORY"):
        if not uploaded_file or not raw_jd_input:
            st.warning("Please provide both your Resume and the Job Description.")
        else:
            adj_jd = trim_job_description(raw_jd_input)
            
            with st.spinner("Processing Full Document..."):
                try:
                    if is_test_mode:
                        tailored_res = f"""
ABDELRHMAN EL SHISHINY
Jeddah, Saudi Arabia | elshishinyabdelrhman@gmail.com | (+966) 577534641

• STRATEGIC COMPETENCIES
- Digital Leadership: End-to-end Digital Transformation, GCC Market Expansion, Revenue Growth Strategy.
- Marketing Technology: HubSpot & Salesforce CRM Architecture, Marketing Automation, WhatsApp Workflows.
- Performance & Growth: Multi-Channel Paid Media (Meta, Google Ads), Technical SEO, ROI Optimization.

• WORK EXPERIENCE

MARKETING & BUSINESS DEVELOPMENT DIRECTOR | DABOUQ TRADING CO.
Jeddah, Saudi Arabia | 2025 – PRESENT
- Spearheaded full-spectrum digital transformation by architecting the company's platform from inception.
- Driving brand presence and revenue growth across GCC markets through data-driven multi-channel campaigns.
- Integrated HubSpot-aligned CRM and automation workflows to manage sales funnels and improve lead retention.

CONTENT & PARTNERSHIPS MANAGER (KSA & INTL) | HUNGERSTATION (DELIVERY HERO)
Jeddah, Saudi Arabia | 2021 – 2024
- Led content strategy and platform management for the leading delivery app in KSA.
- Managed end-to-end CRM lifecycle campaigns, push notifications, and in-app messaging.

EDUCATION
- MBA | University of Cumbria, UK
- Bachelor of Commerce | Ain Shams University, Egypt
                        """
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(uploaded_file)
                        resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                        claude_client = anthropic.Anthropic(api_key=claude_key)
                        prompt = f"Rewrite full resume for {job_title} at {company_name}. Mirror JD vocabulary. Include full history. RESUME: {resume_text} JD: {adj_jd}"
                        resp = claude_client.messages.create(model=CLAUDE_MODEL, max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text.replace('*', '')
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        score_res = gem_client.models.generate_content(model=GEMINI_MODEL, contents=f"Return match_score,ats_score: {tailored_res} vs {adj_jd}")
                        nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                        sm, sa = nums[0], nums[1]

                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), company_name, job_title, raw_jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success(f"Archived! Match: {sm}% | ATS: {sa}%")
                    
                    # PDF Download Button
                    pdf_data = generate_pdf_resume(tailored_res, company_name)
                    st.download_button("📥 Download Tailored Resume (PDF)", data=pdf_data, file_name=f"{company_name}_Resume.pdf", mime="application/pdf")
                    
                    st.markdown(f'<div class="resume-block">{tailored_res}</div>', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("Strategic Application Logs")
    logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    for index, row in logs.iterrows():
        with st.expander(f"📅 {row['date']} | 🏢 {row['company']} | 💼 {row['title']}"):
            col1, col2 = st.columns(2)
            with col1: st.info(row['raw_jd'])
            with col2:
                st.markdown(f'<div class="resume-block">{row["tailored_resume"]}</div>', unsafe_allow_html=True)
                pdf_archive = generate_pdf_resume(row["tailored_resume"], row['company'])
                st.download_button("Download PDF", pdf_archive, f"{row['company']}_Resume.pdf", key=f"pdf_{row['id']}")