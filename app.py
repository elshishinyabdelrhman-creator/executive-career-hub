import streamlit as st
from google import genai
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
from weasyprint import HTML
import io
import re
import json
import html
import os
import time

# =====================================
# PAGE CONFIG
# =====================================
st.set_page_config(
    page_title="Executive Career Hub",
    layout="wide"
)

# =====================================
# GEMINI MODEL
# =====================================
GEMINI_MODEL = "gemini-1.5-flash-latest"

# =====================================
# GET API KEY
# =====================================
def get_gemini_key():
    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return os.getenv("GEMINI_API_KEY")

gemini_key = get_gemini_key()

# =====================================
# DATABASE
# =====================================
@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect(
        "career_hub.db",
        check_same_thread=False
    )

    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            company TEXT,
            role TEXT,
            raw_jd TEXT,
            tailored_resume TEXT,
            score_match INTEGER,
            score_ats INTEGER
        )
    """)

    conn.commit()
    return conn

conn = get_db_connection()

# =====================================
# CUSTOM CSS
# =====================================
st.markdown("""
<style>

.stApp {
    background-color: #FFFFFF !important;
}

.stApp,
.stApp p,
.stApp label,
.stApp h1,
.stApp h2,
.stApp h3,
.stApp span,
.stApp div {
    color: #000000 !important;
}

.paper-container {
    background-color: #FFFFFF !important;
    padding: 45px !important;
    border: 1px solid #000 !important;
    margin: 20px 0px !important;
    line-height: 1.6;
    font-family: Arial;
    white-space: pre-wrap;
}

.stButton>button {
    background-color: #000 !important;
    color: white !important;
    border-radius: 0px !important;
    width: 100% !important;
    height: 3.5em !important;
    font-weight: bold !important;
}

</style>
""", unsafe_allow_html=True)

# =====================================
# PDF EXTRACTION
# =====================================
def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)

    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    return text.strip()

# =====================================
# CLEAN TEXT
# =====================================
def clean_resume_text(text):
    text = re.sub(r"#+", "", text or "")

    forbidden = [
        "Abdelrhman El Shishiny",
        "elshishinyabdelrhman@gmail.com",
        "Jeddah",
        "Phone:"
    ]

    lines = text.split("\n")

    filtered = [
        line
        for line in lines
        if not any(
            f.lower() in line.lower()
            for f in forbidden
        )
    ]

    return "\n".join(filtered).strip()

# =====================================
# PDF GENERATOR
# =====================================
def generate_styled_pdf(resume_data):

    clean_content = html.escape(
        clean_resume_text(resume_data)
    )

    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">

        <style>

        @page {{
            size: A4;
            margin: 15mm;
        }}

        body {{
            font-family: Arial, sans-serif;
            color: #000;
            line-height: 1.45;
            font-size: 10.5pt;
        }}

        .name-header {{
            font-size: 22pt;
            font-weight: bold;
            text-align: center;
            margin-bottom: 2px;
        }}

        .contact-info {{
            font-size: 9.5pt;
            text-align: center;
            margin-bottom: 12px;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }}

        .content-box {{
            white-space: pre-wrap;
            text-align: justify;
            margin-top: 10px;
        }}

        </style>
    </head>

    <body>

        <div class="name-header">
            Abdelrhman El Shishiny
        </div>

        <div class="contact-info">
            Date of birth: 28/04/1987 |
            Nationality: Egyptian |
            Gender: Male |
            Phone: (+966) 577534641
            <br>
            Email: elshishinyabdelrhman@gmail.com |
            Address: Jeddah, Saudi Arabia
        </div>

        <div class="content-box">
            {clean_content}
        </div>

    </body>
    </html>
    """

    pdf_buffer = io.BytesIO()

    HTML(
        string=html_template
    ).write_pdf(
        target=pdf_buffer
    )

    pdf_buffer.seek(0)

    return pdf_buffer

# =====================================
# SAFE JSON PARSER
# =====================================
def safe_json_parse(raw_text):

    raw = raw_text.strip()

    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    try:
        return json.loads(raw)

    except Exception:

        match = re.search(
            r"\{.*\}",
            raw,
            re.DOTALL
        )

        if match:
            return json.loads(match.group(0))

        raise ValueError(
            "AI response was not valid JSON."
        )

# =====================================
# GEMINI CALL
# =====================================
def call_gemini_with_retry(client, prompt):

    try:

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )

        return response

    except Exception as e:

        if "429" in str(e):

            st.warning(
                "Quota exceeded. Retrying in 25 seconds..."
            )

            time.sleep(25)

            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )

            return response

        raise e

# =====================================
# TITLE
# =====================================
st.title("Executive Career Hub")

# =====================================
# TABS
# =====================================
tab1, tab2 = st.tabs([
    "🚀 Tailor Architect",
    "📊 History Archive"
])

# =====================================
# TAB 1
# =====================================
with tab1:

    col_a, col_b = st.columns([2, 1])

    with col_a:

        comp = st.text_input(
            "Target Company"
        )

        role = st.text_input(
            "Target Role"
        )

        jd_input = st.text_area(
            "Paste Job Description",
            height=250
        )

    with col_b:

        up_file = st.file_uploader(
            "Upload Master Resume",
            type=["pdf"]
        )

    if st.button(
        "✨ GENERATE FULL EXECUTIVE RESUME"
    ):

        if not gemini_key:

            st.error(
                "Missing GEMINI_API_KEY."
            )

        elif (
            not comp.strip()
            or not role.strip()
            or not jd_input.strip()
            or not up_file
        ):

            st.warning(
                "Please fill all fields."
            )

        else:

            with st.spinner(
                "Generating ATS Resume..."
            ):

                try:

                    # =========================
                    # EXTRACT RESUME TEXT
                    # =========================
                    res_text = extract_pdf_text(
                        up_file
                    )

                    if not res_text:

                        st.error(
                            "Could not extract text from PDF."
                        )

                        st.stop()

                    # =========================
                    # GEMINI CLIENT
                    # =========================
                    client = genai.Client(
                        api_key=gemini_key
                    )

                    # =========================
                    # PROMPT
                    # =========================
                    prompt = f"""
You are an elite ATS resume optimizer and executive resume writer.

Return ONLY valid JSON.

Required JSON format:

{{
  "tailored_resume": "full rewritten resume text here",
  "match_score": 95,
  "ats_score": 96,
  "keywords_added": [
    "keyword 1",
    "keyword 2",
    "keyword 3"
  ]
}}

Target Company:
{comp}

Target Role:
{role}

Job Description:
{jd_input}

Original Resume:
{res_text}

Rules:
- Never invent fake companies.
- Never invent fake degrees.
- Never invent fake certificates.
- Never invent fake tools.
- Never invent fake dates.
- Never invent fake job titles.
- Preserve factual accuracy.
- Keep employment dates accurate.
- Optimize for ATS matching.
- Add relevant JD keywords naturally.
- Resume must start with:
• ABOUT MYSELF
- No markdown headings like # or **.
- Do not include explanations outside JSON.
"""

                    # =========================
                    # CALL GEMINI
                    # =========================
                    response = call_gemini_with_retry(
                        client,
                        prompt
                    )

                    # =========================
                    # PARSE JSON
                    # =========================
                    data = safe_json_parse(
                        response.text
                    )

                    tailored_res = data.get(
                        "tailored_resume",
                        ""
                    ).strip()

                    sm = int(
                        data.get(
                            "match_score",
                            85
                        )
                    )

                    sa = int(
                        data.get(
                            "ats_score",
                            85
                        )
                    )

                    sm = max(
                        0,
                        min(100, sm)
                    )

                    sa = max(
                        0,
                        min(100, sa)
                    )

                    if not tailored_res:

                        st.error(
                            "AI returned empty resume."
                        )

                        st.stop()

                    # =========================
                    # SAVE DATABASE
                    # =========================
                    conn.execute("""
                        INSERT INTO applications
                        (
                            date,
                            company,
                            role,
                            raw_jd,
                            tailored_resume,
                            score_match,
                            score_ats
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        comp,
                        role,
                        jd_input,
                        tailored_res,
                        sm,
                        sa
                    ))

                    conn.commit()

                    safe_company = re.sub(
                        r"[^a-zA-Z0-9_-]+",
                        "_",
                        comp.strip()
                    )

                    # =========================
                    # SUCCESS
                    # =========================
                    st.success(
                        f"Success! Match: {sm}% | ATS: {sa}%"
                    )

                    # =========================
                    # DOWNLOAD PDF
                    # =========================
                    st.download_button(
                        "📥 Download PDF",
                        data=generate_styled_pdf(
                            tailored_res
                        ),
                        file_name=f"{safe_company}_Resume.pdf",
                        mime="application/pdf"
                    )

                    # =========================
                    # DISPLAY RESUME
                    # =========================
                    st.subheader(
                        "Generated Resume"
                    )

                    st.markdown(
                        f'''
                        <div class="paper-container">
                        {html.escape(tailored_res)}
                        </div>
                        ''',
                        unsafe_allow_html=True
                    )

                    # =========================
                    # KEYWORDS
                    # =========================
                    if data.get(
                        "keywords_added"
                    ):

                        st.subheader(
                            "Keywords Added"
                        )

                        st.write(
                            ", ".join(
                                data["keywords_added"]
                            )
                        )

                except Exception as e:

                    st.error(
                        f"Error: {type(e).__name__}: {e}"
                    )

# =====================================
# TAB 2
# =====================================
with tab2:

    st.header(
        "📊 History Archive"
    )

    logs = pd.read_sql_query(
        """
        SELECT
            id,
            date,
            company,
            role,
            score_match,
            score_ats
        FROM applications
        ORDER BY id DESC
        """,
        conn
    )

    if logs.empty:

        st.info(
            "No applications saved yet."
        )

    else:

        st.dataframe(
            logs,
            use_container_width=True,
            hide_index=True
        )

        full_logs = pd.read_sql_query(
            """
            SELECT *
            FROM applications
            ORDER BY id DESC
            """,
            conn
        )

        for _, row in full_logs.iterrows():

            with st.expander(
                f"""
                #{row['id']} |
                {row['company']} |
                {row['role']}
                """
            ):

                safe_company = re.sub(
                    r"[^a-zA-Z0-9_-]+",
                    "_",
                    str(row["company"])
                )

                st.download_button(
                    "📥 PDF",
                    data=generate_styled_pdf(
                        row["tailored_resume"]
                    ),
                    file_name=f"{safe_company}.pdf",
                    mime="application/pdf",
                    key=f"btn_{row['id']}"
                )

                st.markdown(
                    f'''
                    <div class="paper-container">
                    {html.escape(row["tailored_resume"])}
                    </div>
                    ''',
                    unsafe_allow_html=True
                )