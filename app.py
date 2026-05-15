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
            raw_jd TEXT,
            resume_style TEXT,
            tailored_resume TEXT,
            score_match INTEGER,
            score_ats INTEGER
        )
    """)

    existing_cols = pd.read_sql_query("PRAGMA table_info(applications)", conn)["name"].tolist()

    if "raw_jd" not in existing_cols:
        conn.execute("ALTER TABLE applications ADD COLUMN raw_jd TEXT")

    if "resume_style" not in existing_cols:
        conn.execute("ALTER TABLE applications ADD COLUMN resume_style TEXT")

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
        return "\n".join([
            clean_generated_section(str(x))
            for x in items
            if str(x).strip()
        ])

    return clean_generated_section(str(items))


def list_to_pipe(items):
    if isinstance(items, list):
        return " | ".join([
            clean_generated_section(str(x))
            for x in items
            if str(x).strip()
        ])

    return clean_generated_section(str(items))


def get_style_rules(style):
    rules = {
        "Executive": """
Use senior executive positioning, commercial impact, strategic leadership, market expansion, stakeholder influence, and transformation language.
Make the resume sound premium, confident, and boardroom-ready.
""",
        "Corporate": """
Use polished corporate language suitable for banks, global enterprises, payment companies, and consulting environments.
Prioritize governance, stakeholder management, measurable business outcomes, and cross-functional collaboration.
""",
        "Startup": """
Use growth-focused, agile, builder-oriented language.
Emphasize experimentation, speed, ownership, scaling, automation, and commercial traction.
""",
        "ATS Maximum": """
Prioritize ATS keyword density while keeping natural executive language.
Mirror required and preferred skills from the JD aggressively but truthfully.
""",
        "Concise": """
Use concise, direct, high-impact language.
Avoid long sentences. Keep bullets sharp and recruiter-friendly.
""",
        "Achievement Focused": """
Prioritize measurable impact, outcomes, growth, optimization, revenue, acquisition, retention, efficiency, and performance improvement.
Every bullet should imply business value.
"""
    }

    return rules.get(style, rules["Executive"])


def generate_sections(client, company, role, jd, resume, resume_style):
    style_rules = get_style_rules(resume_style)

    prompt = f"""
Return ONLY valid JSON.

{{
  "executive_profile": "premium ATS summary, 120-150 words, strongly aligned to the JD",
  "strategic_competencies": [
    "GROWTH MARKETING & DEMAND GENERATION: skill | skill | skill",
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
    "bullet 10",
    "bullet 11",
    "bullet 12",
    "bullet 13",
    "bullet 14"
  ],
  "key_skills": ["skill 1", "skill 2", "skill 3"],
  "missing_keywords_added": ["keyword 1", "keyword 2"],
  "match": 95,
  "ats": 96
}}

Target role: {role}
Target company: {company}
Resume style: {resume_style}

Style rules:
{style_rules}

JD:
{jd[:4500]}

Resume:
{resume[:8500]}

Rules:
- Do NOT write full resume.
- Do NOT include name, phone, email, address, date of birth, nationality, or gender.
- Do NOT update old experience.
- ONLY create executive_profile, strategic_competencies, current_experience for Dabouq, key_skills, and missing_keywords_added.
- current_experience must be exactly 14 bullets.
- Each current_experience item must be one bullet sentence only.
- Do not include bullet symbols inside JSON values.
- Use strong action verbs: Led, Spearheaded, Optimized, Scaled, Delivered, Directed, Drove, Expanded, Strengthened, Transformed, Implemented.
- Each bullet must show business value, commercial impact, campaign performance, client engagement, growth, retention, acquisition, optimization, or strategic contribution.
- Mirror required and preferred JD skills where factually reasonable.
- Use keywords from client engagement, digital marketing, martech, AI, analytics, KSA market, campaign optimization, financial services, B2B/B2B2C, partnerships, stakeholder management, and transformation.
- Strategic competencies must directly mirror required and preferred JD skills.
- Key skills must include 35-50 ATS keywords from the JD.
- Keep facts realistic and based on resume.
- Strong ATS language.
- No markdown.
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3000,
        temperature=0.15,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_json(response.content[0].text)


def build_final_resume(data):
    executive_profile = clean_generated_section(data.get("executive_profile", ""))
    competencies = list_to_lines(data.get("strategic_competencies", []))
    current_bullets = as_bullets(data.get("current_experience", []))
    skills_text = list_to_pipe(data.get("key_skills", []))

    return f"""EXECUTIVE PROFILE
{executive_profile}

STRATEGIC COMPETENCIES
{competencies}

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
        rightMargin=34,
        leftMargin=34,
        topMargin=28,
        bottomMargin=26
    )

    title_style = ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=22,
        alignment=TA_CENTER,
        spaceAfter=4
    )

    contact_style = ParagraphStyle(
        "Contact",
        fontName="Helvetica",
        fontSize=8.3,
        leading=10.5,
        alignment=TA_CENTER,
        spaceAfter=7
    )

    section_style = ParagraphStyle(
        "Section",
        fontName="Helvetica-Bold",
        fontSize=11.2,
        leading=14,
        alignment=TA_LEFT,
        spaceBefore=9,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=8.9,
        leading=11.6,
        alignment=TA_LEFT,
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        "Bullet",
        fontName="Helvetica",
        fontSize=8.9,
        leading=11.6,
        leftIndent=13,
        firstLineIndent=-9,
        spaceAfter=2.6
    )

    exp_heading_style = ParagraphStyle(
        "ExperienceHeading",
        fontName="Helvetica-Bold",
        fontSize=9.3,
        leading=11.6,
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

    story.append(HRFlowable(width="100%", thickness=0.9, color=colors.black))
    story.append(Spacer(1, 7))

    section_names = {
        "EXECUTIVE PROFILE",
        "STRATEGIC COMPETENCIES",
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
            story.append(Spacer(1, 2.5))
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

tab1, tab2 = st.tabs(["Generate Resume", "Application History"])


with tab1:
    company = st.text_input("Target Company")
    role = st.text_input("Target Role")
    resume_style = st.selectbox(
        "Resume Style",
        [
            "Executive",
            "Corporate",
            "Startup",
            "ATS Maximum",
            "Concise",
            "Achievement Focused"
        ]
    )
    jd = st.text_area("Paste Job Description", height=250)
    file = st.file_uploader("Upload Master Resume PDF", type=["pdf"])

    if st.button("Generate ATS Resume"):
        if not api_key:
            st.error("Missing ANTHROPIC_API_KEY.")

        elif not company or not role or not jd or not file:
            st.warning("Fill all fields.")

        else:
            with st.spinner("Creating professional targeted resume..."):
                try:
                    resume_text = extract_pdf(file)
                    client = anthropic.Anthropic(api_key=api_key)

                    data = generate_sections(client, company, role, jd, resume_text, resume_style)
                    final_resume = build_final_resume(data)

                    match = max(0, min(100, int(data.get("match", 90))))
                    ats = max(0, min(100, int(data.get("ats", 90))))

                    conn.execute("""
                        INSERT INTO applications
                        (
                            date,
                            company,
                            role,
                            raw_jd,
                            resume_style,
                            tailored_resume,
                            score_match,
                            score_ats
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        company,
                        role,
                        jd,
                        resume_style,
                        final_resume,
                        match,
                        ats
                    ))

                    conn.commit()

                    safe_company = re.sub(r"[^a-zA-Z0-9_-]+", "_", company)

                    st.success(f"Match {match}% | ATS {ats}% | Style: {resume_style}")

                    if data.get("missing_keywords_added"):
                        st.info("Keywords added: " + ", ".join(data["missing_keywords_added"]))

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
    st.header("Application History")

    logs = pd.read_sql_query(
        """
        SELECT *
        FROM applications
        ORDER BY id DESC
        """,
        conn
    )

    if logs.empty:
        st.info("No applications yet.")

    else:
        for _, row in logs.iterrows():
            company_value = row.get("company", "")
            role_value = row.get("role", "")
            style_value = row.get("resume_style", "") or "N/A"
            match_value = row.get("score_match", 0)
            ats_value = row.get("score_ats", 0)

            with st.expander(
                f"{company_value} | {role_value} | {style_value} | Match {match_value}% | ATS {ats_value}%"
            ):
                st.markdown("### Company")
                st.write(company_value)

                st.markdown("### Role")
                st.write(role_value)

                st.markdown("### Resume Style")
                st.write(style_value)

                st.markdown("### Date")
                st.write(row.get("date", ""))

                st.markdown("### Scores")
                st.write(f"Match: {match_value}% | ATS: {ats_value}%")

                st.markdown("### Job Description")
                st.text_area(
                    "Saved JD",
                    row.get("raw_jd", "") or "",
                    height=250,
                    key=f"jd_{row['id']}"
                )

                st.markdown("### Resume")
                st.markdown(
                    f'<div class="paper">{html.escape(row.get("tailored_resume", "") or "")}</div>',
                    unsafe_allow_html=True
                )

                col1, col2 = st.columns(2)

                with col1:
                    safe_company = re.sub(
                        r"[^a-zA-Z0-9_-]+",
                        "_",
                        str(company_value)
                    )

                    st.download_button(
                        "Download PDF",
                        data=generate_pdf(row.get("tailored_resume", "") or ""),
                        file_name=f"{safe_company}_resume.pdf",
                        mime="application/pdf",
                        key=f"pdf_{row['id']}"
                    )

                with col2:
                    if st.button(
                        "Delete Application",
                        key=f"delete_{row['id']}"
                    ):
                        conn.execute(
                            "DELETE FROM applications WHERE id=?",
                            (int(row["id"]),)
                        )
                        conn.commit()
                        st.success("Application deleted.")
                        st.rerun()