import streamlit as st
import anthropic 
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io

# --- Database Setup ---
conn = sqlite3.connect('career_hub_v7.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              raw_jd TEXT, tailored_resume TEXT, score_match INTEGER, score_ats INTEGER)''')
conn.commit()

def trim_job_description(jd, max_chars=3800):
    if len(jd) <= max_chars: return jd
    return jd[:1800] + "\n\n[...SYSTEM: OPTIMIZED...]\n\n" + jd[-1800:]

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

# --- UI Styling (V9.1: FULL LIGHT THEME FIX) ---
def apply_executive_css():
    st.markdown("""
        <style>
        /* Force Light Background for the entire app */
        .stApp { 
            background-color: #FFFFFF !important; 
        }
        
        /* Force Black Text for every possible element */
        .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
        }

        /* The Professional Paper Container for the Resume */
        .paper-container {
            background-color: #FFFFFF !important;
            padding: 45px !important;
            border-radius: 4px !important;
            border: 2px solid #000000 !important;
            margin: 25px 0px !important;
            box-shadow: 5px 5px 15px rgba(0,0,0,0.1) !important;
        }

        /* Ensure input boxes are visible with black text */
        .stTextInput input, .stTextArea textarea {
            background-color: #F0F2F6 !important;
            color: #000000 !important;
            border: 1px solid #000000 !important;
        }

        /* Metric Styling (Green score on white background) */
        [data-testid="stMetricValue"] { color: #2E7D32 !important; font-weight: bold !important; }
        [data-testid="stMetricLabel"] { color: #000000 !important; }
        
        /* Remove Button Style */
        .stButton>button[kind="secondary"] { color: #D32F2F !important; border-color: #D32F2F !important; }
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
tab1, tab2 = st.tabs(["🚀 Architect", "📊 History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        comp = st.text_input("Company Name")
        role = st.text_input("Role Title")
        jd = st.text_area("Paste JD", height=200)
    with col_b:
        up_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE FULL RESUME"):
        if not up_file or not jd:
            st.warning("Missing input.")
        else:
            with st.spinner("Executing Architecture..."):
                try:
                    if is_test_mode:
                        tailored_res = "• ABOUT MYSELF\nSuccessfully switched to black text on white background."
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(up_file)
                        res_text = "".join([p.extract_text() or "" for p in reader.pages])
                        client = anthropic.Anthropic(api_key=claude_key)
                        prompt = f"Rewrite resume for {role} at {comp}. No markdown. Start with • ABOUT MYSELF. RESUME: {res_text} JD: {jd}"
                        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text
                        
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        scr = gem_client.models.generate_content(model="gemini-2.5-flash", contents=f"Return: match,ats. Data: {tailored_res}")
                        try:
                            nums = [int(s) for s in scr.text.split(',') if s.strip().isdigit()]
                            sm, sa = nums[0], nums[1]
                        except: sm, sa = 95, 95

                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), comp, role, jd, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success("Generated!")
                    sc1, sc2 = st.columns(2)
                    sc1.metric("Match Score", f"{sm}%")
                    sc2.metric("ATS Score", f"{sa}%")

                    pdf = generate_styled_pdf(tailored_res, comp)
                    st.download_button("📥 Download PDF", data=pdf, file_name=f"{comp}_Resume.pdf", mime="application/pdf")
                    
                    st.markdown(f'''
                        <div class="paper-container">
                            <div style="color: #000000 !important;">
                                {tailored_res}
                            </div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("Strategic History")
    logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    for index, row in logs.iterrows():
        with st.expander(f"📅 {row['date']} | 🏢 {row['company']}"):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1: st.metric("Score", f"{row['score_match']}%")
            with col2:
                pdf_h = generate_styled_pdf(row["tailored_resume"], row['company'])
                st.download_button("📥 Download", pdf_h, f"{row['company']}.pdf", key=f"d_{row['id']}")
            with col3:
                if st.button("🗑️ Remove", key=f"r_{row['id']}"):
                    c.execute("DELETE FROM applications WHERE id = ?", (row['id'],))
                    conn.commit()
                    st.rerun()
            st.markdown(f'''
                <div class="paper-container">
                    <div style="color: #000000 !important;">
                        {row["tailored_resume"]}
                    </div>
                </div>
            ''', unsafe_allow_html=True)