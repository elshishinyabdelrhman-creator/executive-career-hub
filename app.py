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

# --- UI Styling (THE NUCLEAR OPTION FOR VISIBILITY) ---
def apply_executive_css():
    st.markdown("""
        <style>
        .stApp { background-color: #0E1117 !important; }
        
        /* TARGETING EVERY SINGLE TEXT ELEMENT BY ATTRIBUTE */
        [data-testid="stMarkdownContainer"] p, 
        [data-testid="stMarkdownContainer"] span, 
        [data-testid="stMarkdownContainer"] div {
            color: inherit; /* Allow parent to control */
        }

        /* THE PAPER BLOCK */
        .resume-paper {
            background-color: #FFFFFF !important;
            padding: 50px !important;
            border-radius: 4px !important;
            border: 1px solid #000000 !important;
            margin: 20px 0px !important;
            /* FORCING BLACK TEXT AT THE HIGHEST LEVEL */
            color: #000000 !important;
        }

        /* INJECTING BLACK COLOR INTO ALL CHILDREN */
        .resume-paper * {
            color: #000000 !important;
            -webkit-text-fill-color: #000000 !important;
            text-decoration: none !important;
            font-family: 'Arial', sans-serif !important;
        }

        [data-testid="stMetricValue"] { color: #00FF00 !important; }
        label, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 { color: #FFFFFF !important; }
        
        .stButton>button[kind="secondary"] { color: #FF4B4B !important; border-color: #FF4B4B !important; }
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
        company = st.text_input("Company Name")
        title = st.text_input("Role Title")
        jd_input = st.text_area("Paste JD", height=200)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume", type="pdf")

    if st.button("✨ GENERATE FULL RESUME"):
        if not uploaded_file or not jd_input:
            st.warning("Input missing.")
        else:
            adj_jd = trim_job_description(jd_input)
            with st.spinner("Processing..."):
                try:
                    if is_test_mode:
                        tailored_res = "• ABOUT MYSELF\nThis full text is now FORCED to be black."
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(uploaded_file)
                        resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                        client = anthropic.Anthropic(api_key=claude_key)
                        prompt = f"Rewrite resume for {title} at {company}. No markdown like ##. Start with • ABOUT MYSELF. RESUME: {resume_text} JD: {adj_jd}"
                        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text
                        
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        score_res = gem_client.models.generate_content(model="gemini-2.5-flash", contents=f"Return: match,ats. Data: {tailored_res} vs {adj_jd}")
                        try:
                            nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                            sm, sa = nums[0], nums[1]
                        except: sm, sa = 95, 95

                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), company, title, jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success("Generated!")
                    sc1, sc2 = st.columns(2)
                    sc1.metric("Match Score", f"{sm}%")
                    sc2.metric("ATS Score", f"{sa}%")

                    pdf = generate_styled_pdf(tailored_res, company)
                    st.download_button("📥 Download PDF", data=pdf, file_name=f"{company}_Resume.pdf", mime="application/pdf")
                    
                    # --- THE NUCLEAR DISPLAY WRAPPER ---
                    st.markdown(f'''
                        <div class="resume-paper">
                            <div style="color: black !important;">
                                {tailored_res}
                            </div>
                        </div>
                    ''', unsafe_allow_html=True)
                    
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    for index, row in logs.iterrows():
        with st.expander(f"📅 {row['date']} | 🏢 {row['company']}"):
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1: st.metric("Score", f"{row['score_match']}%")
            with col2:
                pdf_arch = generate_styled_pdf(row["tailored_resume"], row['company'])
                st.download_button("📥 Download", pdf_arch, f"{row['company']}.pdf", key=f"dl_{row['id']}")
            with col3:
                if st.button("🗑️ Remove", key=f"del_{row['id']}"):
                    c.execute("DELETE FROM applications WHERE id = ?", (row['id'],))
                    conn.commit()
                    st.rerun()
            # --- THE NUCLEAR DISPLAY WRAPPER ---
            st.markdown(f'''
                <div class="resume-paper">
                    <div style="color: black !important;">
                        {row["tailored_resume"]}
                    </div>
                </div>
            ''', unsafe_allow_html=True)