import streamlit as st
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io
import re

# --- 1. DATABASE SETUP ---
def get_db_connection():
    conn = sqlite3.connect('career_hub_v15_final.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, company TEXT, 
                  role TEXT, raw_jd TEXT, tailored_resume TEXT, 
                  score_match INTEGER, score_ats INTEGER)''')
    conn.commit()
    return conn

conn = get_db_connection()
c = conn.cursor()

# --- 2. CLEANING ENGINE (PROTECTS DATES) ---
def clean_resume_text(text):
    text = re.sub(r'#+', '', text)
    forbidden = ["Abdelrhman El Shishiny", "elshishinyabdelrhman@gmail.com", "Jeddah", "Phone:"]
    lines = text.split('\n')
    filtered = [line for line in lines if not any(f.lower() in line.lower() for f in forbidden)]
    return "\n".join(filtered).strip()

# --- 3. STYLING & PDF GENERATOR ---
def generate_styled_pdf(resume_data, company_name):
    clean_content = clean_resume_text(resume_data)
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm 15mm; }}
            body {{ font-family: "Arial", sans-serif; color: #000; line-height: 1.45; font-size: 10.5pt; }}
            .name-header {{ font-size: 22pt; font-weight: bold; text-align: center; margin-bottom: 2px; }}
            .contact-info {{ font-size: 9.5pt; text-align: center; margin-bottom: 12px; border-bottom: 2px solid #000; padding-bottom: 10px; }}
            .content-box {{ white-space: pre-wrap; text-align: justify; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="name-header">Abdelrhman El Shishiny</div>
            <div class="contact-info">
                Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641<br>
                Email: elshishinyabdelrhman@gmail.com | Address: Jeddah, Saudi Arabia
            </div>
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
        .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div { color: #000000 !important; }
        .paper-container {
            background-color: #FFFFFF !important; padding: 45px !important; border: 1px solid #000 !important;
            margin: 20px 0px !important; line-height: 1.6; font-family: 'Arial';
        }
        .stButton>button { background-color: #000; color: white; border-radius: 0px; width: 100%; height: 3.5em; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

# --- 4. MAIN APP FLOW ---
st.set_page_config(page_title="Executive Career Hub v15", layout="wide")
apply_executive_css()

gemini_key = st.secrets.get("GEMINI_API_KEY")

tab1, tab2 = st.tabs(["🚀 Tailor Architect", "📊 History Archive"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        comp = st.text_input("Target Company")
        role = st.text_input("Target Role")
        jd_input = st.text_area("Paste JD", height=250)
    with col_b:
        up_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE FULL EXECUTIVE RESUME"):
        if not up_file or not jd_input:
            st.warning("All inputs required.")
        else:
            with st.spinner("Locking Career Integrity..."):
                try:
                    # 1. Read PDF
                    reader = PdfReader(up_file)
                    res_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # 2. Process with Gemini (Solid & No 404s)
                    client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                    
                    prompt = f"""Rewrite this resume for {role} at {comp}. 
                    
                    CRITICAL: 
                    - Keep SHIP HERO, SPELENZO, and CITI BANK sections exactly as they are (including dates).
                    - Expand DABOUQ TRADING CO | 2022 - PRESENT to 12 points relevant to JD.
                    - Start with '• ABOUT MYSELF'. No markdown symbols.
                    SOURCE: {res_text}"""
                    
                    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                    tailored_res = response.text
                    
                    # 3. Scoring
                    scr_prompt = f"Return 'MatchScore, ATSScore' (0-100) for this resume based on JD: {jd_input}. Resume: {tailored_res}"
                    scr_resp = client.models.generate_content(model="gemini-2.0-flash", contents=scr_prompt)
                    try:
                        scores = [int(s.strip()) for s in scr_resp.text.split(',') if s.strip().isdigit()]
                        sm, sa = scores[0], scores[1]
                    except:
                        sm, sa = 85, 90 # Fallback

                    # 4. Storage & Display
                    c.execute("INSERT INTO applications (date, company, role, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), comp, role, jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success(f"Success! Match: {sm}% | ATS: {sa}%")
                    st.download_button("📥 Download PDF", generate_styled_pdf(tailored_res, comp), f"{comp}_Resume.pdf")
                    st.markdown(f'<div class="paper-container">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("📊 History Archive")
    logs = pd.read_sql_query("SELECT id, date, company, role, score_match FROM applications ORDER BY id DESC", conn)
    if not logs.empty:
        st.dataframe(logs, use_container_width=True, hide_index=True)
        full_logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
        for _, row in full_logs.iterrows():
            with st.expander(f"#{row['id']} | {row['company']} | {row['role']}"):
                st.download_button("📥 PDF", generate_styled_pdf(row["tailored_resume"], row['company']), f"{row['company']}.pdf", key=f"btn_{row['id']}")
                st.markdown(f'<div class="paper-container">{row["tailored_resume"]}</div>', unsafe_allow_html=True)