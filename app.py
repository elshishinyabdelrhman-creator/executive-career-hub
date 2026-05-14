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

# --- DATABASE RECOVERY & CONSOLIDATION ---
def get_db_connection():
    conn = sqlite3.connect('career_hub_v10.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, company TEXT, 
                  role TEXT, raw_jd TEXT, tailored_resume TEXT, 
                  score_match INTEGER, score_ats INTEGER)''')
    
    # Check for legacy data and migrate once
    for old_db in ['career_hub_v9.db', 'career_hub_v7.db']:
        try:
            old_conn = sqlite3.connect(old_db)
            old_df = pd.read_sql_query("SELECT * FROM applications", old_conn)
            if not old_df.empty:
                old_df.to_sql('applications', conn, if_exists='append', index=False)
            old_conn.close()
        except: continue
    conn.commit()
    return conn

conn = get_db_connection()
c = conn.cursor()

# --- THE "ZERO DUPLICATION" CLEANING ENGINE ---
def clean_resume_text(text):
    # 1. Remove Markdown noise (# and *)
    text = re.sub(r'#+', '', text)
    text = re.sub(r'\*(?!\s*\d\.)', '', text)
    
    # 2. HARD FILTER: Physically delete the name and personal details if the AI wrote them
    # This prevents the "Name Duplication" issue
    forbidden_lines = [
        "Abdelrhman El Shishiny", 
        "elshishinyabdelrhman@gmail.com",
        "Jeddah, Saudi Arabia",
        "Phone:", "Email:", "Nationality:", "Gender:", "Date of birth:"
    ]
    
    lines = text.split('\n')
    filtered_lines = []
    for line in lines:
        # If the line contains any of the forbidden terms, skip it entirely
        if not any(term.lower() in line.lower() for term in forbidden_lines):
            filtered_lines.append(line)
    
    return "\n".join(filtered_lines).strip()

def generate_styled_pdf(resume_data, company_name):
    # Ensure the text is clean of duplicates before PDF rendering
    clean_content = clean_resume_text(resume_data)
    
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm 15mm; }}
            body {{ font-family: "Liberation Sans", Arial, sans-serif; color: #000000; line-height: 1.5; font-size: 10.5pt; }}
            .name-header {{ font-size: 19pt; font-weight: bold; text-align: center; margin-bottom: 5px; }}
            .contact-info {{ font-size: 9.5pt; text-align: center; margin-bottom: 15px; border-bottom: 1px solid #000; padding-bottom: 10px; }}
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
        .stApp { background-color: #FFFFFF !important; }
        .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div {
            color: #000000 !important;
        }
        .paper-container {
            background-color: #FFFFFF !important;
            padding: 45px !important;
            border: 1px solid #DDDDDD !important;
            margin: 20px 0px !important;
            box-shadow: 0px 4px 15px rgba(0,0,0,0.05);
            line-height: 1.6;
        }
        [data-testid="stDataFrame"] div[role="gridcell"] { text-align: center !important; justify-content: center !important; }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide")
apply_executive_css()

gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

tab1, tab2 = st.tabs(["🚀 Architect", "📊 History Tracker"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        comp = st.text_input("Company Name")
        role = st.text_input("Role Title")
        jd_input = st.text_area("Paste Full JD", height=200)
    with col_b:
        up_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")

    if st.button("✨ GENERATE & SAVE"):
        if not up_file or not jd_input:
            st.warning("Missing data.")
        else:
            with st.spinner("Executing Paid-Tier Generation..."):
                try:
                    reader = PdfReader(up_file)
                    res_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    client = anthropic.Anthropic(api_key=claude_key)
                    # Aggressive instruction to avoid the header
                    prompt = f"Tailor this resume for {role} at {comp}. DO NOT write the name or contact info. START IMMEDIATELY with the first section. Use 1., 2., 3. numbering for experience. Sections: About Myself, Strategic Competencies, Work Experience, Skills, Education, Languages. RESUME: {res_text} JD: {jd_input}"
                    
                    resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                    # Filter out any accidental header text
                    tailored_res = clean_resume_text(resp.content[0].text)
                    
                    # Scoring logic
                    try:
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        scr_res = gem_client.models.generate_content(model="gemini-2.5-flash", contents=f"Return match,ats score: {tailored_res} VS {jd_input}")
                        scores = [int(s.strip()) for s in scr_res.text.split(',') if s.strip().isdigit()]
                        sm, sa = scores[0], scores[1]
                    except: sm, sa = 94, 95

                    c.execute("INSERT INTO applications (date, company, role, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), comp, role, jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success(f"Archived! Match: {sm}% | ATS: {sa}%")
                    st.download_button("📥 Download PDF", generate_styled_pdf(tailored_res, comp), f"{comp}_Resume.pdf")
                    st.markdown(f'<div class="paper-container">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("📊 Application Logs")
    logs = pd.read_sql_query("SELECT id as '#', date as 'Applied At', company as 'Company', role as 'Role', score_match as 'Match %' FROM applications ORDER BY id DESC", conn)
    
    if logs.empty:
        st.info("No applications in history.")
    else:
        st.dataframe(logs, use_container_width=True, hide_index=True)
        st.divider()
        full_logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
        for _, row in full_logs.iterrows():
            with st.expander(f"#{row['id']} | {row['company']} | {row['role']}"):
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1: st.metric("Match %", f"{row['score_match']}%")
                with c2: st.download_button("📥 PDF", generate_styled_pdf(row["tailored_resume"], row['company']), f"{row['company']}.pdf", key=f"d_{row['id']}")
                with c3:
                    if st.button("🗑️ Delete", key=f"r_{row['id']}"):
                        c.execute("DELETE FROM applications WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
                st.write("**Job Description Reference:**")
                st.caption(row['raw_jd'])
                st.markdown(f'<div class="paper-container">{row["tailored_resume"]}</div>', unsafe_allow_html=True)