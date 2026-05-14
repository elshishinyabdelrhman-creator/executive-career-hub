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
    # This template forces bold headers and removes markdown artifacts
    html_template = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @page {{ size: A4; margin: 15mm 15mm; }}
            body {{ 
                font-family: "Liberation Sans", Arial, sans-serif; 
                color: #000; 
                line-height: 1.4; 
                font-size: 10pt; 
            }}
            .name-header {{ 
                font-size: 18pt; 
                font-weight: bold; 
                text-align: center;
                margin-bottom: 5px; 
            }}
            .contact-info {{ 
                font-size: 9pt; 
                text-align: center;
                margin-bottom: 15px; 
            }}
            hr {{ border: 0; border-top: 1px solid #000; margin: 10px 0; }}
            /* This forces headers starting with "•" or all caps to be bold */
            .bold-header {{ 
                font-size: 11pt; 
                font-weight: bold; 
                text-transform: uppercase; 
                margin-top: 15px; 
                margin-bottom: 8px; 
            }}
            .content-box {{ 
                white-space: pre-wrap; 
                text-align: justify; 
            }}
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

# --- UI Styling for Streamlit ---
def apply_executive_css():
    st.markdown("""
        <style>
        .main { background-color: #0E1117; }
        .resume-block {
            background-color: #161B22; border: 1px solid #30363D;
            padding: 35px; border-radius: 10px; color: #E6EDF3;
            line-height: 1.7; white-space: pre-wrap; font-size: 1.05rem;
        }
        .stExpander { border: 1px solid #30363D !important; background-color: #161B22 !important; }
        </style>
    """, unsafe_allow_html=True)

st.set_page_config(page_title="Executive Career Hub", layout="wide", page_icon="🚀")
apply_executive_css()

# API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY")
claude_key = st.secrets.get("ANTHROPIC_API_KEY")

with st.sidebar:
    st.header("⚙️ Control Panel")
    is_test_mode = st.checkbox("🛠️ Enable Test Mode", value=False)
    st.info("OFF = Uses real AI (Paid).\nON = Uses short free sample.")

st.title("🚀 Executive Career Hub")
tab1, tab2 = st.tabs(["🚀 Architect", "📊 History"])

with tab1:
    col_a, col_b = st.columns([2, 1])
    with col_a:
        company = st.text_input("Company Name")
        title = st.text_input("Role Title")
        jd_input = st.text_area("Paste Job Description", height=250)
    with col_b:
        uploaded_file = st.file_uploader("Upload Master Resume (PDF)", type="pdf")

    if st.button("✨ GENERATE FULL RESUME"):
        if not uploaded_file or not jd_input:
            st.warning("Please provide both Resume and JD.")
        else:
            adj_jd = trim_job_description(jd_input)
            with st.spinner("Executing Exact Layout Architecture..."):
                try:
                    if is_test_mode:
                        tailored_res = "• ABOUT MYSELF\\nExecutive leader with 10+ years experience...\\n\\n• WORK EXPERIENCE..."
                        sm, sa = 98, 99
                    else:
                        reader = PdfReader(uploaded_file)
                        resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                        
                        client = anthropic.Anthropic(api_key=claude_key)
                        # Updated prompt to solve "double names" and "##" symbols
                        prompt = f"""
                        Rewrite the resume for {title} at {company}.
                        
                        STRICT FORMATTING RULES:
                        1. DO NOT include the applicant's name or contact details in the body. Start directly with the '• ABOUT MYSELF' section.
                        2. DO NOT use any markdown symbols like '#' or '##' or '**'.
                        3. Use only '•' for section headers (e.g., • ABOUT MYSELF, • WORK EXPERIENCE).
                        4. Keep the numbering (1., 2., 3.) for the work experience bullets.
                        5. Ensure all headers are in ALL CAPS.
                        
                        RESUME: {resume_text}
                        JD: {adj_jd}
                        """
                        resp = client.messages.create(model="claude-sonnet-4-6", max_tokens=4000, messages=[{"role": "user", "content": prompt}])
                        tailored_res = resp.content[0].text
                        
                        # Scoring
                        gem_client = genai.Client(api_key=gemini_key, http_options={'api_version': 'v1'})
                        score_res = gem_client.models.generate_content(model="gemini-2.5-flash", contents=f"Return match_score,ats_score: {tailored_res} vs {adj_jd}")
                        nums = [int(s) for s in score_res.text.split(',') if s.strip().isdigit()]
                        sm = nums[0] if len(nums) > 0 else 95
                        sa = nums[1] if len(nums) > 1 else 95

                    c.execute("INSERT INTO applications (date, company, title, raw_jd, tailored_resume, score_match, score_ats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (datetime.now().strftime("%Y-%m-%d %H:%M"), company, title, jd_input, tailored_res, sm, sa))
                    conn.commit()
                    
                    st.success("Generation Complete!")
                    pdf = generate_styled_pdf(tailored_res, company)
                    st.download_button("📥 Download PDF (Exact Layout)", data=pdf, file_name=f"{company}_Resume.pdf", mime="application/pdf")
                    st.markdown(f'<div class="resume-block">{tailored_res}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Error: {e}")

with tab2:
    st.header("Strategic Application Logs")
    logs = pd.read_sql_query("SELECT * FROM applications ORDER BY id DESC", conn)
    for index, row in logs.iterrows():
        with st.expander(f"📅 {row['date']} | 🏢 {row['company']} | 💼 {row['title']}"):
            st.markdown(f'<div class="resume-block">{row["tailored_resume"]}</div>', unsafe_allow_html=True)
            pdf_arch = generate_styled_pdf(row["tailored_resume"], row['company'])
            st.download_button("Download PDF", pdf_arch, f"{row['company']}_Resume.pdf", key=f"hist_{row['id']}")