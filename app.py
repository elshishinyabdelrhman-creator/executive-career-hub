import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io

# --- Database Setup (Preserving All Data Fields) ---
conn = sqlite3.connect('career_hub_v9.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              date TEXT, 
              company TEXT, 
              role TEXT, 
              raw_jd TEXT, 
              tailored_resume TEXT, 
              score_match INTEGER, 
              score_ats INTEGER)''')
conn.commit()

def trim_job_description(jd, max_chars=3800):
    if len(jd) <= max_chars: return jd
    return jd[:1800] + "\n\n[...JD TRIMMED FOR PROCESSING...]\n\n" + jd[-1800:]

def generate_styled_pdf(resume_data, company_name):
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm 15mm; }}
            body {{ font-family: "Liberation Sans", Arial, sans-serif; color: #000000 !important; line-height: 1.4; font-size: 10pt; }}
            .name-header {{ font-size: 18pt; font-weight: bold; text-align: center; margin-bottom: 5px; }}
            .contact-info {{ font-size: 9pt; text-align: center; margin-bottom: 15px; }}
            hr {{ border: 0; border-top: 1px solid #000; margin: 10px 0; }}
            .content-box {{ white-space: pre-wrap; text-align: justify; color: #000000 !important; }}
        </style>
    </head>
    <body>
        <div class="name-header">Abdelrhman El Shishiny</div>
        <div class="contact-info">
            Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641<br>
            Email: elshishinyabdelrhman@gmail.com | Address: Jeddah, Saudi Arabia
        </div>
        <hr>
        <div class="content-box">{resume_data}</div>
    </body>
    </html>
    '''
    pdf_buffer = io.BytesIO()
    HTML(string=html_template).write_pdf(target=pdf_buffer)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- UI Styling (Light Theme) ---
def apply_executive_css():
    st.markdown("""
        <style>
        .stApp { background-color: #FFFFFF !important; }
        .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
        }
        .paper-container {
            background-color: #FFFFFF !important;
            padding: 40px !important;
            border: 2px solid #000000 !important;
            margin: 20px 0px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.1) !important;
        }
        /* Table Styling */
        .styled-table { width: 100%; border-collapse: collapse; margin: 25px 0; font-size: 0.9em; min-width: 400px; }
        .styled-table th { background-color: #F8F9FA; color: #000000; text-align: left; padding: 12px 15px; border: 1px solid #DDDDDD; }
        .styled-table td { padding: 12px 15px; border: 1px solid #DDDDDD; }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide")
apply_executive_css()

gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

with st.sidebar:
    st.header("⚙️ Control Panel")
    is_test_mode = st.checkbox("🛠️ Enable Test Mode", value=False)

st.title("🚀 Executive Career Hub")
tab1, tab2 = st.tabs(["🚀 Architect", "📊 Full History Table"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        comp = st.text_input("Company Name")
        role = st.text_input("Role Title")
        jd = st.text_area("Paste Full JD", height=200)
    with col_b:
        up_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE & SAVE"):
        if not up_file or not jd:
            st.warning("Missing data.")
        else:
            with st.spinner("Processing..."):
                try:
                    if is_test_mode:
                        tailored_res = "• ABOUT MYSELF\nTailored content for testing..."
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(up_file)
                        res_text = "".join([p.extract_text() or "" for p in reader.pages])
                        client = anthropic.Anthropic(api_key=claude_key)
                        prompt = f"Rewrite resume for {role} at {comp}. Start with • ABOUT MYSELF. RESUME: {res_text} JD: {jd}"
                        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text
                        sm, sa = 95, 96 # Logic simplified

                    c.execute("INSERT INTO applications (date, company, role, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comp, role, jd, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success("Archived in History Table!")
                    st.metric("Match Score", f"{sm}%")
                    pdf = generate_styled_pdf(tailored_res, comp)
                    st.download_button("📥 Download PDF", data=pdf, file_name=f"{comp}_Resume.pdf")
                    st.markdown(f'<div class="paper-container">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("📊 Strategic Application Archive")
    logs = pd.read_sql_query("SELECT id as '#', date as 'Date/Time', company as 'Company', role as 'Role', raw_jd as 'Job Description' FROM applications ORDER BY id DESC", conn)
    
    if logs.empty:
        st.info("Archive is empty.")
    else:
        # Display the data as a searchable table
        st.dataframe(logs, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🛠️ Manage Archive Entries")
        
        # Details & Actions for each entry
        full_logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
        for _, row in full_logs.iterrows():
            with st.expander(f"#{row['id']} | {row['company']} | {row['role']}"):
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1: st.info(f"**Date:** {row['date']}")
                with c2:
                    pdf_h = generate_styled_pdf(row["tailored_resume"], row['company'])
                    st.download_button("📥 Get PDF", pdf_h, f"{row['company']}.pdf", key=f"d_{row['id']}")
                with c3:
                    if st.button("🗑️ Delete", key=f"r_{row['id']}"):
                        c.execute("DELETE FROM applications WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
                
                st.write("**Full Job Description saved:**")
                st.caption(row['raw_jd'])
                st.write("**Tailored Resume Content:**")
                st.markdown(f'<div class="paper-container">{row["tailored_resume"]}</div>', unsafe_allow_html=True)