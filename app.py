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


st.set_page_config(page_title="Executive Career Hub", layout="wide")

CLAUDE_MODEL = "claude-haiku-4-5"


def get_api_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY")


api_key = get_api_key()


@st.cache_resource
def get_db():
    conn = sqlite3.connect("career_hub.db", check_same_thread=False)
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


st.markdown("""
<style>
.stApp { background: white !important; color: black !important; }
.stApp, .stApp p, .stApp div, .stApp span, .stApp label {
    color: black !important;
}
.paper {
    background: white;
    border: 1px solid #111;
    padding: 38px;
    white-space: pre-wrap;
    line-height: 1.45;
    font-family: Arial, sans-serif;
}
.stButton>button {
    background: black !important;
    color: white !important;
    width: 100%;
    height: 3.2em;
    border-radius: 0;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)


def extract_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    text = re.sub(r"\s+", " ", text)
    return text[:9000]


def parse_json(raw):
    raw = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("Claude did not return valid JSON.")
    return json.loads(match.group(0))


def clean_generated_section(text):
    text = text or ""

    forbidden = [
        "Abdelrhman El Shishiny",
        "Date of birth",
        "Nationality",
        "Gender",
        "Phone",
        "Email",
        "Address",
        "Sharbatly",
        "Prince Metab",
        "Saudi Arabia"
    ]

    lines = []

    for line in str(text).split("\n"):
        line = line.strip()

        if not line:
            continue

        if any(word.lower() in line.lower() for word in forbidden):
            continue

        line = re.sub(r"^[•\-\d\.\)\s]+", "", line).strip()
        lines.append(line)

    return "\n".join(lines).strip()


def as_bullets(items):
    if isinstance(items, list):
        clean_items = []

        for item in items:
            item = clean_generated_section(str(item))
            if item:
                clean_items.append(f"• {item}")

        return "\n".join(clean_items)

    text = clean_generated_section(str(items))
    parts = re.split(r"\n+|(?<=\.)\s+(?=[A-Z])", text)

    clean_items = []
    for part in parts:
        part = part.strip()
        if len(part) > 20:
            clean_items.append(f"• {part}")

    return "\n".join(clean_items)


def list_to_lines(items):
    if isinstance(items, list):
        return "\n".join([clean_generated_section(str(x)) for x in items if str(x).strip()])
    return clean_generated_section(str(items))


def list_to_pipe(items):
    if isinstance(items, list):
        return " | ".join([clean_generated_section(str(x)) for x in items if str(x).strip()])
    return clean_generated_section(str(items))


def generate_sections(client, company, role, jd, resume):
    prompt = f"""
Return ONLY valid JSON.

{{
  "about": "short ATS summary, 70-90 words",
  "core_competencies": [
    "DIGITAL MARKETING & MARTECH: skill | skill | skill",
    "AI & MARKETING INNOVATION: skill | skill | skill",
    "CLIENT ENGAGEMENT & PARTNERSHIPS: skill | skill | skill",
    "KSA MARKET EXPERTISE: skill | skill | skill"
  ],
  "current_experience": [
    "bullet 1",
    "bullet 2",
    "bullet 3",
    "bullet 4",
    "bullet 5",
    "bullet 6",
    "bullet 7",
    "bullet 8",
    "bullet 9",
    "bullet 10"
  ],
  "key_skills": ["skill 1", "skill 2", "skill 3"],
  "match": 95,
  "ats": 96
}}

Target role: {role}
Target company: {company}

JD:
{jd[:4000]}

Resume:
{resume[:8000]}

Rules:
- Do NOT write full resume.
- Do NOT include name, phone, email, address, date of birth, nationality, or gender.
- Do NOT update old experience.
- ONLY create about, core_competencies, current_experience for Dabouq, and key_skills.
- current_experience must be exactly 10 bullets.
- Each current_experience item must be one bullet sentence only.
- Do not include bullet symbols inside JSON values.
- Match JD required and preferred skills.
- Keep facts realistic and based on resume.
- Strong ATS language.
- No markdown.
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1800,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_json(response.content[0].text)


def build_final_resume(data):
    about = clean_generated_section(data.get("about", ""))
    core_text = list_to_lines(data.get("core_competencies", []))
    current_bullets = as_bullets(data.get("current_experience", []))
    skills_text = list_to_pipe(data.get("key_skills", []))

    return f"""ABOUT MYSELF
{about}

CORE COMPETENCIES
{core_text}

WORK EXPERIENCE

13/01/2025 - CURRENT | JEDDAH, SAUDI ARABIA
MARKETING & BUSINESS DEVELOPMENT DIRECTOR
Dabouq Trading Co. (Cars & E-Commerce)
{current_bullets}

2020 - 01/2025 | JEDDAH, SAUDI ARABIA
MARKETING AND BUSINESS DEVELOPMENT DIRECTOR
Ship Hero / Spelenzo
• Developed strategy for social media marketing with cohesive messaging across multiple platforms.
• Delivered top-quality marketing strategy and consultative services with consistently high client satisfaction scores.
• Cultivated strong partnerships with key influencers, securing valuable media coverage and endorsements to drive growth.
• Oversaw development and execution of multi-channel marketing campaigns to drive growth.
• Boosted click-through rates with targeted email marketing campaigns.
• Reduced expenditures by streamlining workflows with marketing automation tools.
• Conducted market research and analysis to identify emerging opportunities and maintain a competitive market edge.
• Leveraged SEO best practices to optimise website content, resulting in increased organic traffic and improved keyword rankings.
• Maintained client records in CRM systems, ensuring streamlined data processes.
• Prepared and delivered winning client proposals, business presentations, and sales pitches to C-level executives.

2013 - 2020 | JEDDAH, SAUDI ARABIA
SALES AND MARKETING EXECUTIVE
Spelenzo
• Handled clients across perfumes, luxury fashion, watches, cosmetics, and telecommunications including Rubaiyat, Arabian Oud, Casio, and Zain.
• Drove revenue growth across GCC through display advertising, PPC, retargeting, and paid social.
• Planned and optimized digital marketing campaigns across web, SEO/SEM, email, social media, and display advertising.
• Planned, executed, and measured experiments and conversion tests.
• Analyzed online customer behavior and updated action plans to reach defined goals.
• Monitored brand online reputation and awareness through relevant online presence and content management.
• Measured and reported performance of digital marketing campaigns, analyzing data to optimize strategy.
• Developed and executed sales promotions, increasing revenue through targeted campaigns.
• Identified trends and insights to optimize digital marketing spend.
• Improved email marketing campaigns and increased web traffic through content initiatives.

2009 - 2013 | CAIRO, EGYPT
SENIOR RELATIONSHIP MANAGER
Citi Bank
• Managed client relationships in a financial services environment.
• Supported banking products, client advisory, and relationship management activities.

2006 - 2009 | CAIRO, EGYPT
RELATIONSHIP MANAGER
Citi Bank
• Developed client relationships and supported account management within retail banking.

EDUCATION & TRAINING
MASTERS OF BUSINESS ADMINISTRATION - MBA - UNIVERSITY OF CUMBRIA
BACHELOR OF COMMERCE - BUSINESS MANAGEMENT - AIN SHAMS UNIVERSITY

LANGUAGE SKILLS
Arabic: Native
English: C2
German: B2
French: B2

KEY SKILLS
{skills_text}
""".strip()


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
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9.1,
        leading=12,
        alignment=TA_LEFT,
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=9.1,
        leading=12,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    exp_heading_style = ParagraphStyle(
        "ExperienceHeading",
        fontName="Helvetica-Bold",
        fontSize=9.4,
        leading=12,
        spaceBefore=6,
        spaceAfter=2
    )

    story = []

    story.append(Paragraph("Abdelrhman El Shishiny", title_style))

    story.append(Paragraph(
        "Date of birth: 28/04/1987 | Nationality: Egyptian | Gender: Male | Phone: (+966) 577534641<br/>"
        "Email: elshishinyabdelrhman@gmail.com | Address: Jeddah, Saudi Arabia",
        contact_style
    ))

    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
    story.append(Spacer(1, 7))

    section_names = {
        "ABOUT MYSELF",
        "CORE COMPETENCIES",
        "WORK EXPERIENCE",
        "EDUCATION & TRAINING",
        "LANGUAGE SKILLS",
        "KEY SKILLS"
    }

    date_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4}\s*-\s*CURRENT|\d{4}\s*-\s*\d{2}/\d{4}|\d{4}\s*-\s*\d{4})",
        re.I
    )

    for raw in text.split("\n"):
        line = raw.strip()

        if not line:
            story.append(Spacer(1, 3))
            continue

        escaped = html.escape(line)
        upper = line.upper().strip()

        if upper in section_names:
            story.append(Paragraph(upper, section_style))
            story.append(HRFlowable(width="100%", thickness=0.35, color=colors.grey))
            story.append(Spacer(1, 3))

        elif date_pattern.search(line):
            story.append(Paragraph(escaped, exp_heading_style))

        elif line.isupper() and len(line) < 85:
            story.append(Paragraph(escaped, exp_heading_style))

        elif line.startswith("•"):
            story.append(Paragraph(escaped, bullet_style))

        else:
            story.append(Paragraph(escaped, body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer


st.title("Executive Career Hub")

tab1, tab2 = st.tabs(["Generate Resume", "History"])


with tab1:
    company = st.text_input("Target Company")
    role = st.text_input("Target Role")
    jd = st.text_area("Paste Job Description", height=250)
    file = st.file_uploader("Upload Master Resume PDF", type=["pdf"])

    if st.button("Generate ATS Resume"):
        if not api_key:
            st.error("Missing ANTHROPIC_API_KEY.")

        elif not company or not role or not jd or not file:
            st.warning("Fill all fields.")

        else:
            with st.spinner("Updating only competencies, current experience, and skills..."):
                try:
                    resume_text = extract_pdf(file)

                    client = anthropic.Anthropic(api_key=api_key)

                    data = generate_sections(client, company, role, jd, resume_text)
                    final_resume = build_final_resume(data)

                    match = max(0, min(100, int(data.get("match", 85))))
                    ats = max(0, min(100, int(data.get("ats", 85))))

                    conn.execute("""
                        INSERT INTO applications
                        (date, company, role, tailored_resume, score_match, score_ats)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        company,
                        role,
                        final_resume,
                        match,
                        ats
                    ))

                    conn.commit()

                    safe_company = re.sub(r"[^a-zA-Z0-9_-]+", "_", company)

                    st.success(f"Match {match}% | ATS {ats}%")

                    st.download_button(
                        "Download PDF",
                        data=generate_pdf(final_resume),
                        file_name=f"{safe_company}_resume.pdf",
                        mime="application/pdf"
                    )

                    st.markdown(
                        f'<div class="paper">{html.escape(final_resume)}</div>',
                        unsafe_allow_html=True
                    )

                except Exception as e:
                    st.error(f"Error: {type(e).__name__}: {e}")


with tab2:
    logs = pd.read_sql_query(
        "SELECT id, date, company, role, score_match, score_ats FROM applications ORDER BY id DESC",
        conn
    )

    if logs.empty:
        st.info("No history yet.")

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
                    "Download PDF",
                    data=generate_pdf(row["tailored_resume"]),
                    file_name=f"{safe_company}_resume.pdf",
                    mime="application/pdf",
                    key=f"pdf_{row['id']}"
                )

                st.markdown(
                    f'<div class="paper">{html.escape(row["tailored_resume"])}</div>',
                    unsafe_allow_html=True
                )