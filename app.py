import streamlit as st
import anthropic 
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io
import re

# --- DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect('career_hub_stable_v3.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, company TEXT, 
                  role TEXT, raw_jd TEXT, tailored_resume TEXT)''')
    conn.commit()
    return conn

conn = get_db_connection()
c = conn.cursor()

# --- v12.8 CLEANING ENGINE (ZERO-STRIP) ---
def clean_resume_text(text):
    # Only remove AI hashtags. Protect all numbers, dates, and dashes.
    text = re.sub(r'#+', '', text)
    forbidden = ["Abdelrhman El Shishiny", "elshishinyabdelrhman@gmail.com", "Jeddah", "Phone:"]
    lines = text.split('\n')
    filtered = [line for line in lines if not any(f.lower() in line.lower() for f in forbidden)]
    return "\n".join(filtered).strip()

def generate_styled_pdf(resume_data):
    clean_content = clean_resume_text(resume_data)
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm 15mm; }}
            body {{ font-family: "Arial", sans-serif; color: #000; line-height: 1.45; font-size: 10.5pt; }}
            .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; margin-bottom: 15px; }}
            .content {{ white-space: pre-wrap; text-align: justify; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div style="font-size: 22pt; font-weight: bold;">Abdelrhman El Shishiny</div>
            <div style="font-size: 9pt; margin-top: 5px;">Jeddah, Saudi Arabia | elshishinyabdelrhman@gmail.com | (+966) 577534641</div>
        </div>
        <div class="content">{clean_content}</div>
    </body>
    </html>
    '''
    pdf_buffer = io.BytesIO()
    HTML(string=html_template).write_pdf(target=pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

st.set_page_config(page_title="Executive Career Hub v12.8", layout="wide")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

tab1, tab2 = st.tabs(["🚀 Architect", "📊 History Archive"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        comp = st.text_input("Target Company")
        role = st.text_input("Target Role")
        jd_input = st.text_area("Paste JD Here", height=150)
    with col_b:
        up_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE FULL RESUME"):
        if not up_file or not jd_input:
            st.warning("All fields are required.")
        else:
            with st.spinner("Locking History & Restoring Stability..."):
                try:
                    reader = PdfReader(up_file)
                    res_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = anthropic.Anthropic(api_key=claude_key)
                    
                    # STABLE PROMPT
                    prompt = f"""
                    Tailor this resume for {role} at {comp}. 

                    CRITICAL INSTRUCTIONS:
                    1. EDIT ONLY: 'About Myself', 'Strategic Competencies', 'Skills', and 'Dabouq Trading Co'.
                    2. LOCK ALL DATES: Every job must include its Company Name and Date Range (e.g., 2022 - Present).
                    3. CURRENT JOB (Dabouq): Rewrite accomplishments with 12 points relevant to JD.
                    4. PAST ROLES: Copy Ship Hero (2021-2022), Spelenzo (2013-2021), and Citi Bank (2006-2013) headers and bullets exactly.
                    5. SEQUENCE: About Myself > Strategic Competencies > Work Experience > Skills > Education > Languages.

                    Rules: No markdown. Start with '• ABOUT MYSELF'.
                    SOURCE: {res_text}
                    """
                    
                    # USING THE MOST COMPATIBLE SONNET MODEL ID
                    resp = client.messages.create(
                        model="claude-3-sonnet-20240229", 
                        max_tokens=4000, 
                        messages=[{"role": "user", "content": prompt}]
                    )
                    tailored_res = resp.content[0].text

                    c.execute("INSERT INTO applications (date, company, role, raw_jd, tailored_resume) VALUES (?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), comp, role, jd_input, tailored_res))
                    conn.commit()
                    
                    st.success("Resume Optimized Successfully!")
                    st.download_button("📥 Download PDF", generate_styled_pdf(tailored_res), f"{comp}_Resume.pdf")
                    st.markdown(f'<div style="background-color:white; color:black; padding:35px; border:2px solid #000;">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("📊 History Archive")
    logs = pd.read_sql_query("SELECT id, date, company, role FROM applications ORDER BY id DESC", conn)
    if not logs.empty:
        st.dataframe(logs, use_container_width=True, hide_index=True)
        full_logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
        for _, row in full_logs.iterrows():
            with st.expander(f"#{row['id']} | {row['company']} | {row['role']}"):
                st.download_button("📥 PDF", generate_styled_pdf(row["tailored_resume"]), f"{row['company']}.pdf", key=f"final_fix_{row['id']}")
                st.write(row["tailored_resume"])