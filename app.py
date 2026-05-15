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

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

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
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=30,
        bottomMargin=28
    )

    title_style = ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=4
    )

    contact_style = ParagraphStyle(
        "Contact",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        alignment=TA_CENTER,
        spaceAfter=8
    )

    section_style = ParagraphStyle(
        "Section",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=10,
        spaceAfter=5,
        textColor=colors.black
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.2,
        alignment=TA_LEFT,
        spaceAfter=4
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=9.2,
        leading=12.2,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    exp_heading_style = ParagraphStyle(
        "ExperienceHeading",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=12,
        spaceBefore=7,
        spaceAfter=3
    )

    story = []

    story.append(Paragraph("Abdelrhman El Shishiny", title_style))
    story.append(Paragraph(
        "Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641<br/>"
        "Email: elshishinyabdelrhman@gmail.com | Address: Jeddah, Saudi Arabia",
        contact_style
    ))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    story.append(Spacer(1, 8))

    lines = text.split("\n")

    section_keywords = [
        "ABOUT MYSELF",
        "PROFESSIONAL SUMMARY",
        "CORE COMPETENCIES",
        "CORE COMPETENCIES & SKILLS",
        "STRATEGIC COMPETENCIES",
        "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "EDUCATION",
        "EDUCATION & TRAINING",
        "LANGUAGE SKILLS",
        "LANGUAGES",
        "KEY SKILLS"
    ]

    date_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4}\s*-\s*CURRENT|\d{4}\s*-\s*\d{2}/\d{4}|\d{4}\s*-\s*\d{4}|\d{4}\s*-\s*CURRENT)",
        re.IGNORECASE
    )

    for raw_line in lines:
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 3))
            continue

        clean_line = html.escape(line)

        normalized = line.upper().replace("•", "").strip()

        if normalized in section_keywords:
            story.append(Paragraph(normalized, section_style))
            story.append(HRFlowable(width="100%", thickness=0.35, color=colors.grey))
            story.append(Spacer(1, 4))

        elif date_pattern.search(line) or " | " in line and any(char.isdigit() for char in line):
            story.append(Paragraph(clean_line, exp_heading_style))

        elif line.startswith("•") or re.match(r"^\d+\.", line):
            story.append(Paragraph(clean_line, bullet_style))

        elif line.isupper() and len(line) < 80:
            story.append(Paragraph(clean_line, exp_heading_style))

        else:
            story.append(Paragraph(clean_line, body_style))

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