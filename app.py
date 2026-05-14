import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io

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

# --- Hyper-Accurate Styled PDF Generation Function ---
def generate_styled_pdf(resume_data, company_name):
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 12mm 15mm; }}
            /* Use Liberation Sans for Linux compatibility to prevent blank pages */
            body {{ font-family: "Liberation Sans", Arial, sans-serif; color: #000; line-height: 1.3; font-size: 9.5pt; }}
            .name-header {{ font-size: 18pt; font-weight: bold; margin-bottom: 5px; }}
            .contact-info {{ font-size: 9pt; margin-bottom: 15px; }}
            hr {{ border: 0; border-top: 1px solid #000; margin: 10px 0; }}
            h2 {{ font-size: 11pt; font-weight: bold; text-transform: uppercase; margin-top: 15px; margin-bottom: 8px; }}
            .content-box {{ white-space: pre-wrap; font-family: "Liberation Sans", sans-serif; font-size: 9.5pt; text-align: justify; }}
        </style>
    </head>
    <body>
        <div class="name-header">Abdelrhman El Shishiny</div>
        <div class="contact-info">
            Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641 (Mobile) |<br>
            Email address: elshishinyabdelrhman@gmail.com |<br>
            Address: Sharbatly Village, Prince Metab Road, Marwa district, Jeddah, Saudi Arabia (Home)
        </div>
        <hr>
        <div class="content-box">{resume_data}</div>
    </body>
    </html>
    '''
    # Create the PDF in a memory buffer to ensure it isn't blank
    pdf_buffer = io.BytesIO()
    HTML(string=html_template).write_pdf(target=pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

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

with st.sidebar:
    st.header("⚙️ Settings")
    is_test_mode = st.checkbox("🛠️ Enable Test Mode", value=False)

st.title("🚀 Executive Career Hub")
st.caption("v7.9.2 | Styled PDF Fix | Claude 4.6 & Gemini 2.5 Flash")

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
            st.warning("Please provide both Resume and JD.")
        else:
            adj_jd = trim_job_description(raw_jd_input)
            with st.spinner("Executing Exact Layout Architecture..."):
                try:
                    if is_test_mode:
                        tailored_res = "• ABOUT MYSELF\nResults-driven leader with 10+ years experience...\n\n• STRATEGIC COMPETENCIES\nDIGITAL LEADERSHIP: End-to-end Transformation...\n\n• WORK EXPERIENCE\n13/01/2025–CURRENT\nMARKETING & BUSINESS DEVELOPMENT DIRECTOR – DABOUQ TRADING CO.\n1. Spearheaded digital transformation...\n2. Integrated HubSpot CRM..."
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(uploaded_file)
                        resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                        
                        claude_client = anthropic.Anthropic(api_key=claude_key)
                        prompt = f"""
                        Rewrite the resume for {job_title} at {company_name}.
                        STRICT REQUIREMENT: Maintain the EXACT layout, numbering (1., 2., 3.), and header style (• ABOUT MYSELF, • STRATEGIC COMPETENCIES, • WORK EXPERIENCE) of the original resume.
                        RESUME: {resume_text}
                        JD: {adj_jd}
                        """
                        resp = claude_client.messages.create(model=CLAUDE_MODEL, max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text.replace('*', '')
                        
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        score_res = gem_client.models.generate_content(model=GEMINI_MODEL, contents=f"Return match,ats: {tailored_res} vs {adj_jd}")
                        nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                        sm, sa = nums[0], nums[1]

                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), company_name, job_title, raw_jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success(f"Archived! Match: {sm}% | ATS: {sa}%")
                    
                    # Styled PDF Buffer
                    pdf_buffer = generate_styled_pdf(tailored_res, company_name)
                    st.download_button("📥 Download PDF (Exact Layout)", data=pdf_buffer, file_name=f"{company_name}_Resume.pdf", mime="application/pdf")
                    
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
                pdf_archive = generate_styled_pdf(row["tailored_resume"], row['company'])
                st.download_button("Download PDF", pdf_archive, f"{row['company']}_Resume.pdf", key=f"pdf_{row['id']}")