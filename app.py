import streamlit as st
from google import genai
from pypdf import PdfReader
from fpdf import FPDF
import markdown2
import unicodedata
import sqlite3
import pandas as pd
from datetime import datetime

# --- Database Setup ---
# Note: On Streamlit Cloud, this file resets on reboot unless connected to a persistent disk.
conn = sqlite3.connect('career_hub_2026.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS applications 
             (id INTEGER PRIMARY KEY, date TEXT, company TEXT, title TEXT, 
              status TEXT, notes TEXT, analysis TEXT, 
              score_before INTEGER, score_after INTEGER)''')
c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
conn.commit()

def save_setting(key, value):
    c.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()

def get_setting(key):
    c.execute('SELECT value FROM settings WHERE key = ?', (key,))
    res = c.fetchone()
    return res[0] if res else ""

# --- PDF Engine (Handled Unicode for ligatures/special chars) ---
def create_pdf(markdown_text):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        html_content = markdown2.markdown(markdown_text)
        # NFKD Normalization prevents crashes from 'smart' characters
        clean_html = unicodedata.normalize('NFKD', html_content).encode('latin-1', 'ignore').decode('latin-1')
        pdf.write_html(clean_html)
        return bytes(pdf.output())
    except Exception: return None

# --- UI Header ---
st.set_page_config(page_title="Executive Career Hub 2026", layout="wide", page_icon="🎯")

# --- API Key Management (Cloud Secrets + Local DB) ---
if "GEMINI_API_KEY" in st.secrets:
    active_api_key = st.secrets["GEMINI_API_KEY"]
    sidebar_msg = "✅ API Key: Cloud Secrets"
else:
    db_key = get_setting("gemini_api_key")
    if db_key:
        active_api_key = db_key
        sidebar_msg = "✅ API Key: Local Memory"
    else:
        active_api_key = None
        sidebar_msg = "⚠️ API Key Required"

with st.sidebar:
    st.title("⚙️ Control Panel")
    st.info(sidebar_msg)
    
    # Manual Override / Initial Setup
    new_key = st.text_input("Update API Key", type="password", placeholder="Enter new key...")
    if st.button("Save & Lock Key"):
        save_setting("gemini_api_key", new_key)
        st.success("Key updated!")
        st.rerun()
    
    st.divider()
    st.write("**Strategy Mode:** Executive 2026")
    st.write("**Region:** GCC / Saudi Arabia")

# --- Main Application Tabs ---
tab1, tab2 = st.tabs(["🚀 New Strategic Application", "📅 Application Tracker"])

with tab1:
    st.header("Opportunity Analysis & Tailoring")
    
    col1, col2 = st.columns(2)
    with col1:
        company = st.text_input("Company Name", placeholder="e.g. Qynda")
        title = st.text_input("Job Title", placeholder="e.g. General Manager")
    with col2:
        uploaded_file = st.file_uploader("Upload Your Latest Resume (PDF)", type="pdf")
    
    job_desc = st.text_area("Target Job Description", height=250, placeholder="Paste the vacancy details here...")

    if st.button("🚀 Analyze & Generate Best-Fit Strategy"):
        if not active_api_key:
            st.error("Please provide an API Key in the sidebar.")
        elif not uploaded_file or not job_desc:
            st.error("Please upload your resume and paste the job description.")
        else:
            with st.spinner("Executing Executive Audit..."):
                try:
                    # 1. Read PDF
                    reader = PdfReader(uploaded_file)
                    resume_text = "".join([p.extract_text() or "" for p in reader.pages])
                    
                    # 2. Connect to Gemini 2.5
                    client = genai.Client(api_key=active_api_key)
                    
                    # 3. Strategic Prompt for 2026 GCC Market
                    main_prompt = f"""
                    Role: {title} at {company}.
                    Analyze this resume against the JD using 2026 Executive standards.
                    
                    STRUCTURE YOUR RESPONSE AS FOLLOWS:
                    
                    1. **MATCH SCORING**:
                       - Original Match: [Percentage]%
                       - Tailored Match: [Percentage]% (After applying changes)
                    
                    2. **THE PERFECT 'ABOUT ME'**:
                       - A 5-sentence executive summary highlighting P&L ownership, regional GCC impact, and e-commerce growth.
                    
                    3. **STRATEGIC KEYWORDS & SKILLS**:
                       - List 10 mandatory ATS keywords.
                       - List 3 AI/Automation skills that give an edge for this role.
                    
                    4. **AI-AUGMENTED ACHIEVEMENTS**:
                       - Rewrite 3 current resume bullets using the 'AI + Google XYZ' formula.
                    
                    RESUME: {resume_text}
                    JD: {job_desc}
                    """
                    
                    response = client.models.generate_content(model="gemini-2.5-flash", contents=main_prompt)
                    analysis = response.text
                    
                    # 4. Extract Scores for Tracker
                    score_prompt = f"From the following analysis, extract ONLY the Original Match % and Tailored Match % as two numbers separated by a comma (e.g., 65,95). Analysis: {analysis}"
                    scores = client.models.generate_content(model="gemini-2.5-flash", contents=score_prompt)
                    try:
                        s_before, s_after = scores.text.strip().split(',')
                        sb, sa = int(s_before), int(s_after)
                    except: sb, sa = 0, 0

                    # 5. Save to Database
                    c.execute('''INSERT INTO applications (date, company, title, status, notes, analysis, score_before, score_after) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', 
                              (datetime.now().strftime("%Y-%m-%d"), company, title, "Applied", "", analysis, sb, sa))
                    conn.commit()
                    
                    st.session_state.current_analysis = analysis
                    st.success(f"Analysis Complete! Improvement: {sb}% ➔ {sa}%")
                    st.markdown(analysis)
                    
                except Exception as e:
                    st.error(f"Error during analysis: {e}")

    if 'current_analysis' in st.session_state:
        pdf_bytes = create_pdf(st.session_state.current_analysis)
        if pdf_bytes:
            st.download_button("📥 Download Strategic Report (PDF)", data=pdf_bytes, file_name=f"Strategy_{company}.pdf")

with tab2:
    st.header("Executive Application Tracker")
    
    # Fetch records
    df = pd.read_sql_query("SELECT * FROM applications ORDER BY date DESC, id DESC", conn)
    
    if not df.empty:
        # Grouping display by Date
        for date, group in df.groupby('date'):
            st.subheader(f"📅 {date}")
            for idx, row in group.iterrows():
                # Score-based color coding logic could go here
                label = f"{row['company']} | {row['title']} | Fit: {row['score_before']}% → {row['score_after']}% | [{row['status']}]"
                
                with st.expander(label):
                    col_left, col_right = st.columns([1, 2])
                    
                    with col_left:
                        new_status = st.selectbox("Update Pipeline Status", 
                                                ["Applied", "Called", "Interviewing", "Offer", "Rejected"], 
                                                index=["Applied", "Called", "Interviewing", "Offer", "Rejected"].index(row['status']),
                                                key=f"status_{row['id']}")
                        new_notes = st.text_area("HR Notes / Interview Feedback", value=row['notes'], key=f"notes_{row['id']}")
                        
                        if st.button("Update Tracker", key=f"upd_{row['id']}"):
                            c.execute("UPDATE applications SET status=?, notes=? WHERE id=?", (new_status, new_notes, row['id']))
                            conn.commit()
                            st.rerun()
                    
                    with col_right:
                        st.markdown("#### Saved Best-Fit Strategy")
                        st.write(row['analysis'])
    else:
        st.info("No applications found in the tracker. Start by analyzing a vacancy in the first tab.")