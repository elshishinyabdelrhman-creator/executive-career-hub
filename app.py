import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io
import re

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect('career_hub_v11_final.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, company TEXT, 
                  role TEXT, raw_jd TEXT, tailored_resume TEXT, 
                  score_match INTEGER, score_ats INTEGER)''')
    conn.commit()
    return conn

conn = get_db_connection()
c = conn.cursor()

# --- v11.6 CLEANING ENGINE (DATE & SEQUENCE PROTECTOR) ---
def clean_resume_text(text):
    # Strip AI markdown headers (#)
    text = re.sub(r'#+', '', text)
    
    # HARD FILTER: Remove duplicated contact info headers
    forbidden = ["Abdelrhman El Shishiny", "elshishinyabdelrhman@gmail.com", "Jeddah", "Phone:", "Email:"]
    lines = text.split('\n')
    filtered = [line for line in lines if not any(f.lower() in line.lower() for f in forbidden)]
    
    return "\n".join(filtered).strip()

def generate_styled_pdf(resume_data, company_name):
    clean_content = clean_resume_text(resume_data)
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm 15mm; }}
            body {{ font-family: "Arial", sans-serif; color: #000000; line-height: 1.45; font-size: 10.5pt; }}
            .name-header {{ font-size: 20pt; font-weight: bold; text-align: center; margin-bottom: 2px; }}
            .contact-info {{ font-size: 9pt; text-align: center; margin-bottom: 12px; border-bottom: 1.5px solid #000; padding-bottom: 10px; }}
            .content-box {{ white-space: pre-wrap; text-align: justify; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="name-header">Abdelrhman El Shishiny</div>
        <div class="contact-info">
            Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641<br>
            Email: elshishinyabdelrhman@gmail.com | Address: Jeddah, Saudi Arabia
        </div>
        <div class="content-box">{clean_content}</div>
    </body>
    </html>
    '''
    pdf_buffer = io.BytesIO()
    HTML(string=html_template).write_pdf(target=pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

def apply_executive_css():
    st.markdown("""
        <style>
        .stApp {{ background-color: #FFFFFF !important; }}
        .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div {{ color: #000000 !important; }}
        .paper-container {{
            background-color: #FFFFFF !important; padding: 45px !important; border: 1px solid #000000 !important;
            margin: 20px 0px !important; line-height: 1.6;
        }}
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide")
apply_executive_css()

gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

tab1, tab2 = st.tabs(["🚀 Architect", "📊 History Archive"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        comp = st.text_input("Company Name")
        role = st.text_input("Role Title")
        jd_input = st.text_area("Paste Full JD", height=200)
    with col_b:
        up_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE & SAVE"):
        if not up_file or not jd_input:
            st.warning("All fields are mandatory.")
        else:
            with st.spinner("Locking History & Correcting Sequence..."):
                try:
                    reader = PdfReader(up_file)
                    res_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = anthropic.Anthropic(api_key=claude_key)
                    
                    # STRICT SEQUENCE AND DATE PROTECTION PROMPT
                    prompt = f"""
                    Rewrite the resume for {role} at {comp}. 
                    
                    STRICT SECTION ORDER (DO NOT CHANGE):
                    1. • ABOUT MYSELF (Tailored)
                    2. • STRATEGIC COMPETENCIES (Tailored)
                    3. • WORK EXPERIENCE (See rules below)
                    4. • SKILLS (Extracted from JD)
                    5. • EDUCATION & TRAINING (Raw Copy)
                    6. • LANGUAGE SKILLS (Raw Copy)

                    WORK EXPERIENCE RULES:
                    - CURRENT ROLE (DABOUQ TRADING CO): Rewrite accomplishments (10-12 points, 1. 2. 3. numbering). MUST start with header: DABOUQ TRADING CO | 2022 - PRESENT.
                    - ALL PAST ROLES: Copy the headers, DATES, and content for SHIP HERO, SPELENZO, and CITI BANK exactly as they are in the PDF. Do NOT move the Skills section between them.
                    
                    No markdown headers. No contact info. Start with '• ABOUT MYSELF'.
                    RESUME: {res_text}
                    JD: {jd_input}
                    """
                    
                    resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                    tailored_res = clean_resume_text(resp.content[0].text)
                    
                    # Score Bypass
                    sm, sa = 0, 0
                    try:
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        scr = gem_client.models.generate_content(model="gemini-2.5-flash", contents=f"Return match,ats: {{tailored_res}}")
                        scores = [int(s.strip()) for s in scr.text.split(',') if s.strip().isdigit()]
                        sm, sa = scores[0], scores[1]
                    except:
                        st.info("⚠️ Score bypass active. Download PDF below.")

                    c.execute("INSERT INTO applications (date, company, role, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), comp, role, jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success("Corrected Sequence Generated.")
                    st.download_button("📥 Download PDF", generate_styled_pdf(tailored_res, comp), f"{{comp}}_Resume.pdf")
                    st.markdown(f'<div class="paper-container">{{tailored_res}}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {{e}}")

with tab2:
    st.header("📊 History Tracker")
    logs = pd.read_sql_query("SELECT id as '#', date as 'Applied At', company as 'Company', role as 'Role' FROM applications ORDER BY id DESC", conn)
    if not logs.empty:
        st.dataframe(logs, use_container_width=True, hide_index=True)
        full_logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
        for _, row in full_logs.iterrows():
            with st.expander(f"#{{row['id']}} | {{row['company']}} | {{row['role']}}"):
                st.download_button("📥 PDF", generate_styled_pdf(row["tailored_resume"], row['company']), f"{{row['company']}}.pdf", key=f"dl_{{row['id']}}")
                st.markdown(f'<div class="paper-container">{{row["tailored_resume"]}}</div>', unsafe_allow_html=True)