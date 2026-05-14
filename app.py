import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io

# --- DATABASE SETUP ---
def migrate_data():
    new_conn = sqlite3.connect('career_hub_v9.db', check_same_thread=False)
    new_c = new_conn.cursor()
    new_c.execute('''CREATE TABLE IF NOT EXISTS applications 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, company TEXT, 
                  role TEXT, raw_jd TEXT, tailored_resume TEXT, 
                  score_match INTEGER, score_ats INTEGER)''')
    return new_conn

conn = migrate_data()
c = conn.cursor()

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
        }
        /* Table Centering Fix */
        [data-testid="stDataFrame"] div[role="gridcell"] {
            text-align: center !important;
            justify-content: center !important;
        }
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
            st.warning("Please provide data.")
        else:
            with st.spinner("Archiving Full Application..."):
                try:
                    reader = PdfReader(up_file)
                    res_text = "".join([p.extract_text() or "" for p in reader.pages])
                    client = anthropic.Anthropic(api_key=claude_key)
                    prompt = f"Rewrite resume for {role} at {comp}. Structure: About Myself, Strategic Competencies, Work Experience, Skills, Education, Languages. RESUME: {res_text} JD: {jd_input}"
                    
                    if is_test_mode:
                        tailored_res = "• ABOUT MYSELF\nTesting..."
                        sm, sa = 98, 99
                    else:
                        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text
                        # Get real scores from Gemini
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        scr_res = gem_client.models.generate_content(model="gemini-2.5-flash", contents=f"Return: match_score, ats_score. Data: {tailored_res} vs {jd_input}")
                        try:
                            nums = [int(s) for s in scr_res.text.split(',') if s.strip().isdigit()]
                            sm, sa = nums[0], nums[1]
                        except: sm, sa = 95, 95

                    c.execute("INSERT INTO applications (date, company, role, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), comp, role, jd_input, tailored_res, sm, sa))
                    conn.commit()
                    st.success(f"Archived! Match Score: {sm}%")
                    st.metric("Match Score", f"{sm}%")
                    st.download_button("📥 Download PDF", generate_styled_pdf(tailored_res, comp), f"{comp}_Resume.pdf")
                    st.markdown(f'<div class="paper-container">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("📊 Strategic Application Archive")
    # UPDATED SELECT: Now includes score_match and raw_jd preview
    logs = pd.read_sql_query("""
        SELECT id as '#', 
               date as 'Applied At', 
               company as 'Company', 
               role as 'Role', 
               score_match as 'Match %',
               raw_jd as 'Full JD' 
        FROM applications ORDER BY id DESC
    """, conn)
    
    if not logs.empty:
        # Centering configuration
        st.dataframe(logs, use_container_width=True, hide_index=True)
        st.divider()
        
        full_logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
        for _, row in full_logs.iterrows():
            with st.expander(f"Entry #{row['id']} | {row['company']} | Score: {row['score_match']}%"):
                c1, c2, c3 = st.columns([1, 1, 1])
                with c1: st.metric("Match Score", f"{row['score_match']}%")
                with c2:
                    st.download_button("📥 Get PDF", generate_styled_pdf(row["tailored_resume"], row['company']), f"{row['company']}.pdf", key=f"d_{row['id']}")
                with c3:
                    if st.button("🗑️ Remove", key=f"r_{row['id']}"):
                        c.execute("DELETE FROM applications WHERE id = ?", (row['id'],))
                        conn.commit()
                        st.rerun()
                
                st.subheader("📌 Full Job Description Saved:")
                st.text_area("JD Content", value=row['raw_jd'], height=200, key=f"jd_{row['id']}", disabled=True)
                
                st.subheader("📄 Tailored Resume Preview:")
                st.markdown(f'<div class="paper-container">{row["tailored_resume"]}</div>', unsafe_allow_html=True)