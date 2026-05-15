import streamlit as st
from google import genai
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
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER


st.set_page_config(page_title="Executive Career Hub", layout="wide")

PREFERRED_MODELS = [

    "gemini-1.5-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-flash-8b",
]


def get_gemini_key():
    try:
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return os.getenv("GEMINI_API_KEY")


gemini_key = get_gemini_key()


@st.cache_resource
def get_db_connection():
    conn = sqlite3.connect("career_hub.db", check_same_thread=False)

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


st.markdown("""
<style>
.stApp { background-color: #FFFFFF !important; }

.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp span, .stApp div {
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


def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text.strip()


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
        line for line in lines
        if not any(f.lower() in line.lower() for f in forbidden)
    ]

    return "\n".join(filtered).strip()


def safe_pdf_text(text):
    text = html.escape(text or "")
    text = text.replace("\n", "<br/>")
    return text


def generate_styled_pdf(resume_data):
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=6
    )

    contact_style = ParagraphStyle(
        "Contact",
        parent=styles["BodyText"],
        fontSize=8.5,
        alignment=TA_CENTER,
        leading=11,
        spaceAfter=10
    )

    body_style = ParagraphStyle(
        "ResumeBody",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=13,
        spaceAfter=6
    )

    heading_style = ParagraphStyle(
        "ResumeHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=8,
        spaceAfter=6
    )

    story = []

    story.append(Paragraph("Abdelrhman El Shishiny", title_style))

    story.append(Paragraph(
        "Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641<br/>"
        "Email: elshishinyabdelrhman@gmail.com | Address: Jeddah, Saudi Arabia",
        contact_style
    ))

    story.append(HRFlowable(width="100%"))
    story.append(Spacer(1, 10))

    clean_text = clean_resume_text(resume_data)
    lines = clean_text.split("\n")

    for line in lines:
        line = line.strip()

        if not line:
            story.append(Spacer(1, 4))
            continue

        escaped_line = safe_pdf_text(line)

        if line.startswith("• ") and len(line) < 90:
            story.append(Paragraph(escaped_line, heading_style))
        else:
            story.append(Paragraph(escaped_line, body_style))

    doc.build(story)
    buffer.seek(0)

    return buffer


def safe_json_parse(raw_text):
    raw = raw_text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))

    raise ValueError("AI response was not valid JSON.")


def get_available_generate_models(client):
    models = client.models.list()
    available = []

    for model in models:
        name = model.name.replace("models/", "")

        methods = (
            getattr(model, "supported_actions", None)
            or getattr(model, "supported_generation_methods", None)
            or []
        )

        if "generateContent" in methods:
            available.append(name)

    return available


def call_gemini(client, prompt):
    available_models = get_available_generate_models(client)

    for preferred_model in PREFERRED_MODELS:
        if preferred_model in available_models:
            response = client.models.generate_content(
                model=preferred_model,
                contents=prompt
            )
            return response, preferred_model

    if available_models:
        fallback_model = available_models[0]

        response = client.models.generate_content(
            model=fallback_model,
            contents=prompt
        )

        return response, fallback_model

    raise RuntimeError(
        "No Gemini model available for generateContent with this API key."
    )


st.title("Executive Career Hub")

tab1, tab2 = st.tabs(["🚀 Tailor Architect", "📊 History Archive"])


with tab1:
    col_a, col_b = st.columns([2, 1])

    with col_a:
        comp = st.text_input("Target Company")
        role = st.text_input("Target Role")
        jd_input = st.text_area("Paste Job Description", height=250)

    with col_b:
        up_file = st.file_uploader("Upload Master Resume", type=["pdf"])

    if st.button("✨ GENERATE FULL EXECUTIVE RESUME"):
        if not gemini_key:
            st.error("Missing GEMINI_API_KEY.")

        elif not comp.strip() or not role.strip() or not jd_input.strip() or not up_file:
            st.warning("Please fill all fields.")

        else:
            with st.spinner("Generating ATS Resume..."):
                try:
                    res_text = extract_pdf_text(up_file)

                    if not res_text:
                        st.error("Could not extract text from PDF.")
                        st.stop()

                    client = genai.Client(api_key=gemini_key)

                    prompt = f"""
You are an elite ATS resume optimizer and executive resume writer.

Return ONLY valid JSON.

Required JSON format:
{{
  "tailored_resume": "full rewritten resume text here",
  "match_score": 95,
  "ats_score": 96,
  "keywords_added": ["keyword 1", "keyword 2", "keyword 3"],
  "adjusted_skills": ["skill 1", "skill 2", "skill 3"]
}}

Target Company:
{comp}

Target Role:
{role}

Job Description:
{jd_input}

Original Resume:
{res_text}

CRITICAL RULES:
- Never invent fake companies.
- Never invent fake degrees.
- Never invent fake certificates.
- Never invent fake tools.
- Never invent fake employment dates.
- Never invent fake job titles.
- Preserve factual accuracy.

DATE RULES:
- Every work experience MUST include company name, job title, and employment date.
- Never remove employment dates.
- Never change employment dates.
- If a date exists in the original resume, it must appear in the tailored resume.
- Keep SHIP HERO, SPELENZO, CITI BANK, and DABOUQ TRADING CO dates exactly as written in the original resume.
- Format every experience heading exactly like:
  COMPANY NAME | JOB TITLE | DATE

SKILLS RULES:
- Add a section called:
• CORE COMPETENCIES & SKILLS
- Adjust this section to match required and preferred skills from the job description.
- Include ATS keywords from the JD naturally.
- Only include skills supported by the original resume or reasonably connected to real experience.
- Group skills clearly, for example:
  Sales & Business Development: ...
  Operations & CRM: ...
  Digital Marketing: ...
  Leadership & Team Management: ...
  Customer Relationship Management: ...
  Data Analysis & Reporting: ...

RESUME STRUCTURE:
The resume must follow this exact order:

• ABOUT MYSELF

• CORE COMPETENCIES & SKILLS

• PROFESSIONAL EXPERIENCE

• EDUCATION

• LANGUAGES

EXPERIENCE RULES:
- Keep SHIP HERO, SPELENZO, and CITI BANK sections factually unchanged, including dates.
- Expand DABOUQ TRADING CO | 2022 - PRESENT to 12 strong bullet points relevant to the job description.
- Optimize all bullet points for ATS matching.
- Add relevant job description keywords naturally.
- Do not use markdown headings like # or **.
- Do not include explanations outside JSON.
"""

                    response, used_model = call_gemini(client, prompt)

                    data = safe_json_parse(response.text)

                    tailored_res = data.get("tailored_resume", "").strip()
                    sm = int(data.get("match_score", 85))
                    sa = int(data.get("ats_score", 85))

                    sm = max(0, min(100, sm))
                    sa = max(0, min(100, sa))

                    if not tailored_res:
                        st.error("AI returned empty resume.")
                        st.stop()

                    conn.execute("""
                        INSERT INTO applications
                        (date, company, role, raw_jd, tailored_resume, score_match, score_ats)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        comp,
                        role,
                        jd_input,
                        tailored_res,
                        sm,
                        sa
                    ))

                    conn.commit()

                    safe_company = re.sub(r"[^a-zA-Z0-9_-]+", "_", comp.strip())

                    st.success(
                        f"Success! Match: {sm}% | ATS: {sa}% | Model: {used_model}"
                    )

                    st.download_button(
                        "📥 Download PDF",
                        data=generate_styled_pdf(tailored_res),
                        file_name=f"{safe_company}_Resume.pdf",
                        mime="application/pdf"
                    )

                    st.subheader("Generated Resume")

                    st.markdown(
                        f'<div class="paper-container">{html.escape(tailored_res)}</div>',
                        unsafe_allow_html=True
                    )

                    if data.get("keywords_added"):
                        st.subheader("Keywords Added")
                        st.write(", ".join(data["keywords_added"]))

                    if data.get("adjusted_skills"):
                        st.subheader("Adjusted Skills")
                        st.write(", ".join(data["adjusted_skills"]))

                except Exception as e:
                    st.error(f"Error: {type(e).__name__}: {e}")


with tab2:
    st.header("📊 History Archive")

    logs = pd.read_sql_query(
        """
        SELECT id, date, company, role, score_match, score_ats
        FROM applications
        ORDER BY id DESC
        """,
        conn
    )

    if logs.empty:
        st.info("No applications saved yet.")

    else:
        st.dataframe(logs, use_container_width=True, hide_index=True)

        full_logs = pd.read_sql_query(
            "SELECT * FROM applications ORDER BY id DESC",
            conn
        )

        for _, row in full_logs.iterrows():
            with st.expander(f"#{row['id']} | {row['company']} | {row['role']}"):
                safe_company = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(row["company"]))

                st.download_button(
                    "📥 PDF",
                    data=generate_styled_pdf(row["tailored_resume"]),
                    file_name=f"{safe_company}.pdf",
                    mime="application/pdf",
                    key=f"btn_{row['id']}"
                )

                st.markdown(
                    f'<div class="paper-container">{html.escape(row["tailored_resume"])}</div>',
                    unsafe_allow_html=True
                )