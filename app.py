import streamlit as st
import anthropic
from pypdf import PdfReader
import sqlite3
import pandas as pd
from datetime import datetime
import io
import re
import json
import html
import os

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="ATS Resume Tailor", layout="wide")

CLAUDE_MODEL = "claude-haiku-4-5"

# =========================
# API KEY
# =========================
def get_api_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except:
        return os.getenv("ANTHROPIC_API_KEY")

api_key = get_api_key()

# =========================
# DATABASE
# =========================
@st.cache_resource
def get_db():
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
            tailored_resume TEXT,
            score_match INTEGER,
            score_ats INTEGER
        )
    """)

    conn.commit()
    return conn

conn = get_db()

# =========================
# CSS
# =========================
st.markdown("""
<style>
.stApp {
    background: white;
    color: black;
}

.paper {
    border: 1px solid black;
    padding: 30px;
    white-space: pre-wrap;
    line-height: 1.5;
}
</style>
""", unsafe_allow_html=True)

# =========================
# PDF EXTRACT
# =========================
def extract_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)

    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    return text[:12000]

# =========================
# SHORTEN JD
# =========================
def compress_jd(text):
    return text[:6000]

# =========================
# JSON PARSER
# =========================
def parse_json(raw):

    raw = (
        raw
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    match = re.search(
        r"\{.*\}",
        raw,
        re.DOTALL
    )

    if match:
        return json.loads(match.group(0))

    raise ValueError("Invalid JSON")

# =========================
# PDF GENERATOR
# =========================
def generate_pdf(text):

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    story = []

    lines = text.split("\n")

    for line in lines:

        if line.strip():

            story.append(
                Paragraph(
                    html.escape(line),
                    styles['BodyText']
                )
            )

            story.append(Spacer(1, 6))

    doc.build(story)

    buffer.seek(0)

    return buffer

# =========================
# CLAUDE CALL
# =========================
def generate_resume(
    client,
    company,
    role,
    jd,
    resume
):

    prompt = f"""
Return ONLY JSON.

{{
"resume":"...",
"match":95,
"ats":96
}}

Role:{role}

Company:{company}

JD:
{jd}

Resume:
{resume}

Rules:
- Keep dates.
- Keep factual accuracy.
- Add matching skills.
- ATS optimize.
- Add skills section.
- Short concise bullets.
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        temperature=0.2,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    return response.content[0].text

# =========================
# UI
# =========================
st.title("ATS Resume Tailor")

tab1, tab2 = st.tabs([
    "Generate Resume",
    "History"
])

# =========================
# TAB 1
# =========================
with tab1:

    company = st.text_input(
        "Target Company"
    )

    role = st.text_input(
        "Target Role"
    )

    jd = st.text_area(
        "Paste JD",
        height=250
    )

    file = st.file_uploader(
        "Upload Resume PDF",
        type=["pdf"]
    )

    if st.button("Generate ATS Resume"):

        if not api_key:
            st.error("Missing ANTHROPIC_API_KEY")

        elif not company or not role or not jd or not file:
            st.warning("Fill all fields")

        else:

            with st.spinner("Generating..."):

                try:

                    resume_text = extract_pdf(file)

                    short_jd = compress_jd(jd)

                    client = anthropic.Anthropic(
                        api_key=api_key
                    )

                    raw = generate_resume(
                        client,
                        company,
                        role,
                        short_jd,
                        resume_text
                    )

                    data = parse_json(raw)

                    tailored = data["resume"]

                    match = int(
                        data.get("match", 85)
                    )

                    ats = int(
                        data.get("ats", 85)
                    )

                    conn.execute("""
                        INSERT INTO applications
                        (
                            date,
                            company,
                            role,
                            tailored_resume,
                            score_match,
                            score_ats
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        company,
                        role,
                        tailored,
                        match,
                        ats
                    ))

                    conn.commit()

                    st.success(
                        f"Match {match}% | ATS {ats}%"
                    )

                    st.download_button(
                        "Download PDF",
                        data=generate_pdf(tailored),
                        file_name=f"{company}_resume.pdf",
                        mime="application/pdf"
                    )

                    st.markdown(
                        f"""
                        <div class="paper">
                        {html.escape(tailored)}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                except Exception as e:

                    st.error(str(e))

# =========================
# TAB 2
# =========================
with tab2:

    logs = pd.read_sql_query(
        """
        SELECT *
        FROM applications
        ORDER BY id DESC
        """,
        conn
    )

    if logs.empty:

        st.info("No history")

    else:

        st.dataframe(
            logs,
            use_container_width=True,
            hide_index=True
        )