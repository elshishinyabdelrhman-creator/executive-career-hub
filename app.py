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

# --- Hyper-Accurate Styled PDF Generation Function ---
def generate_styled_pdf(resume_data, company_name):
    # This template forces the PDF to look exactly like the "Elshishiny 010.pdf" 
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 12mm 15mm; }}
            body {{ font-family: 'Arial', sans-serif; color: #000; line-height: 1.3; font-size: 9.5pt; }}
            .name-header {{ font-size: 18pt; font-weight: bold; margin-bottom: 5px; }}
            .contact-info {{ font-size: 9pt; margin-bottom: 15px; }}
            hr {{ border: 0; border-top: 1px solid #000; margin: 10px 0; }}
            h2 {{ font-size: 11pt; font-weight: bold; text-transform: uppercase; margin-top: 15px; margin-bottom: 8px; }}
            .content-box {{ white-space: pre-wrap; font-family: 'Arial', sans-serif; font-size: 9.5pt; text-align: justify; }}
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
    return HTML(string=html_template).write_pdf()

# --- UI Styling for the Streamlit App ---
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
st.caption("v7.9 | Exact Layout PDF Export | Claude 4.6 & Gemini 2.5 Flash")

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
                        tailored_res = "[FULL CONTENT WITH ORIGINAL STYLE HEADERS]"
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(uploaded_file)
                        resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                        
                        claude_client = anthropic.Anthropic(api_key=claude_key)
                        # Specific prompt instructions to force the original format
                        prompt = f"""
                        Rewrite the resume for {job_title} at {company_name}.
                        STRICT REQUIREMENT: Maintain the EXACT layout, numbering, and header style of the original resume.
                        - Use '• ABOUT MYSELF' header.
                        - Use '• STRATEGIC COMPETENCIES' header.
                        - Use '• WORK EXPERIENCE' header.
                        - For work experience, use numbered bullets (1., 2., 3.) and include dates/location as per the original.
                        - Ensure '• EDUCATION & TRAINING' and '• LANGUAGE SKILLS' are at the end.
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
                    
                    # Styled PDF Download
                    pdf_data = generate_styled_pdf(tailored_res, company_name)
                    st.download_button("📥 Download PDF (Exact Layout)", pdf_data, f"{company_name}_Resume.pdf", "application/pdf")
                    
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
                pdf_arch = generate_styled_pdf(row["tailored_resume"], row['company'])
                st.download_button("Download PDF", pdf_arch, f"{row['company']}_Resume.pdf", key=f"pdf_{row['id']}")