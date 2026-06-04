import streamlit as st
import anthropic
from pypdf import PdfReader
import sqlite3, pandas as pd
from datetime import datetime
import io, re, json, html, os, hashlib

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib import colors

st.set_page_config(page_title="Executive Career Hub", layout="wide")

CLAUDE_MODEL = "claude-haiku-4-5"

USER_PROFILE = {
    "name": "Abdelrhman El Shishiny",
    "dob": "28/04/1987",
    "nationality": "Egyptian",
    "gender": "Male",
    "phone": "(+966) 577534641",
    "email": "elshishinyabdelrhman@gmail.com",
    "address": "Jeddah, Saudi Arabia",
}

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
            jd_hash TEXT,
            detected_style TEXT,
            company_type TEXT,
            company_size TEXT,
            company_focus TEXT,
            tailored_resume TEXT,
            score_match INTEGER,
            score_ats INTEGER,
            interview_probability INTEGER,
            missing_keywords TEXT,
            improvement_suggestions TEXT
        )
    """)

    cols = pd.read_sql_query("PRAGMA table_info(applications)", conn)["name"].tolist()

    needed = {
        "raw_jd": "TEXT",
        "jd_hash": "TEXT",
        "detected_style": "TEXT",
        "company_type": "TEXT",
        "company_size": "TEXT",
        "company_focus": "TEXT",
        "interview_probability": "INTEGER",
        "missing_keywords": "TEXT",
        "improvement_suggestions": "TEXT"
    }

    for col, typ in needed.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE applications ADD COLUMN {col} {typ}")

    conn.commit()
    return conn

conn = get_db()

st.markdown("""
<style>
.stApp { background: white !important; color: black !important; }
.stApp, .stApp p, .stApp div, .stApp span, .stApp label { color: black !important; }
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

def make_hash(company, role, jd):
    value = f"{company}|{role}|{jd}".lower().strip()
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def extract_pdf(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return re.sub(r"\s+", " ", text)[:10000]

def parse_json(raw):
    raw = raw.replace("```json", "").replace("```", "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        raise ValueError("Claude did not return valid JSON.")
    return json.loads(match.group(0))

def clean_text(text):
    forbidden = [
        "Abdelrhman El Shishiny",
        "Date of birth",
        "Nationality",
        "Gender",
        "Phone",
        "Email",
        "Address"
    ]

    lines = []
    for line in str(text or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(x.lower() in line.lower() for x in forbidden):
            continue
        line = re.sub(r"^[•\-\d\.\)\s]+", "", line).strip()
        lines.append(line)

    return "\n".join(lines).strip()

def as_bullets(items):
    if isinstance(items, list):
        return "\n".join(f"• {clean_text(x)}" for x in items if clean_text(x))

    parts = re.split(r"\n+|(?<=\.)\s+(?=[A-Z])", clean_text(items))
    return "\n".join(f"• {p.strip()}" for p in parts if len(p.strip()) > 20)

def list_to_lines(items):
    if isinstance(items, list):
        return "\n".join(clean_text(x) for x in items if clean_text(x))
    return clean_text(items)

def list_to_pipe(items):
    if isinstance(items, list):
        return " | ".join(clean_text(x) for x in items if clean_text(x))
    return clean_text(items)

def generate_sections(client, company, role, jd, resume):
    prompt = f"""
Return ONLY valid JSON.

{{
  "detected_company_style": "Financial Services / Enterprise / Big Tech / Startup / Retail / Consulting / E-commerce / Healthcare / Real Estate / Automotive / Other",
  "company_type": "short company type",
  "company_size": "Startup / Mid-Market / Enterprise / Global Enterprise",
  "company_focus": "short focus",
  "style_reason": "short reason",
  "executive_profile": "premium ATS summary 130-160 words",
  "strategic_competencies": [
    "COMMERCIAL GROWTH & BUSINESS STRATEGY: skill | skill | skill",
    "DIGITAL MARKETING & MARTECH: skill | skill | skill",
    "SALES DEVELOPMENT & CUSTOMER ACQUISITION: skill | skill | skill",
    "AI, DATA & PERFORMANCE ANALYTICS: skill | skill | skill",
    "PARTNERSHIPS & STAKEHOLDER MANAGEMENT: skill | skill | skill",
    "MARKET & INDUSTRY EXPERTISE: skill | skill | skill"
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
    "bullet 14",
    "bullet 15",
    "bullet 16"
  ],
  "key_skills": ["skill 1", "skill 2", "skill 3"],
  "missing_keywords": ["keyword 1", "keyword 2"],
  "missing_keywords_added": ["keyword 1", "keyword 2"],
  "improvement_suggestions": ["suggestion 1", "suggestion 2"],
  "interview_probability": 90,
  "match": 95,
  "ats": 96
}}

Company: {company}
Role: {role}

JD:
{jd[:5000]}

Resume:
{resume[:9000]}

Universal ATS Rules:
- First detect the company style and role family from the company name and JD.
- Then rewrite ONLY the allowed sections to maximize ATS alignment.
- Target ATS score should be 95+ when the candidate has transferable experience.
- Do NOT lie, do NOT invent employers, titles, degrees, certificates, or dates.
- You may translate existing experience into role-relevant language if factually reasonable.
- Use exact JD phrases naturally inside executive_profile, strategic_competencies, current_experience, and key_skills.
- Do NOT list a keyword as missing if it has been added anywhere in the generated resume sections.
- missing_keywords should only contain important requirements that are truly unsupported by the resume.
- Do NOT write full resume.
- Do NOT include name, phone, email, address, DOB, nationality, or gender.
- Do NOT rewrite old roles.
- Only update executive_profile, strategic_competencies, current_experience, and key_skills.
- current_experience must be exactly 16 bullets.
- Every current_experience item must be one bullet sentence only.
- No bullet symbols inside JSON values.
- Use strong action verbs.
- Keep all wording professional, persuasive, executive, and recruiter-friendly.
- No markdown.

Company Style Rules:
- Financial Services: emphasize client engagement, partnerships, compliance, stakeholders, analytics, commercial growth, banking/financial relationship management.
- Enterprise: emphasize governance, cross-functional leadership, scale, stakeholder influence, KPIs, performance reporting.
- Big Tech: emphasize innovation, experimentation, product thinking, analytics, automation, user-centric growth, cross-functional execution.
- Startup: emphasize builder mindset, growth, execution, agility, launch, scale, revenue, ownership.
- E-commerce/Retail: emphasize commercial growth, sales strategy, online revenue growth, customer acquisition, retention, AOV growth, basket size optimization, conversion optimization, assortment collaboration, pricing strategy, promotional planning, vendor relationships, supplier negotiations, campaign KPIs, CRM, performance marketing, customer lifecycle, UX/UI collaboration, and profitability.
- Consulting: emphasize advisory, stakeholder management, transformation, strategy, presentations, analysis, executive communication.
- Automotive: emphasize sales growth, lead generation, digital acquisition, partnerships, customer journey, marketplace performance.
- Healthcare: emphasize ethical marketing, patient/customer trust, compliance, partnerships, digital engagement.

Scoring Rules:
- match and ats must reflect the generated resume after optimization.
- If the role is close to candidate experience, score 92-98.
- If the role has major unsupported requirements, score lower and explain through missing_keywords and improvement_suggestions.
"""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=3800,
        temperature=0.12,
        messages=[{"role": "user", "content": prompt}]
    )

    return parse_json(response.content[0].text)

def build_resume(data):
    return f"""EXECUTIVE PROFILE
{clean_text(data.get("executive_profile", ""))}

STRATEGIC COMPETENCIES
{list_to_lines(data.get("strategic_competencies", []))}

WORK EXPERIENCE

13/01/2025 - CURRENT | JEDDAH, SAUDI ARABIA
MARKETING & BUSINESS DEVELOPMENT DIRECTOR
Dabouq Trading Co. (Cars & E-Commerce)
{as_bullets(data.get("current_experience", []))}

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
• Measured campaign performance and analyzed data to optimize digital strategy.
• Developed sales promotions and content initiatives to increase revenue and web traffic.

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
{list_to_pipe(data.get("key_skills", []))}
""".strip()

def profile_contact(profile):
    p1 = [
        f"Date of birth: {profile['dob']}",
        f"Nationality: {profile['nationality']}",
        f"Gender: {profile['gender']}",
        f"Phone: {profile['phone']}"
    ]
    return " | ".join(p1), f"Email: {profile['email']} | Address: {profile['address']}"

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

    title = ParagraphStyle("Title", fontName="Helvetica-Bold", fontSize=19, leading=22, alignment=TA_CENTER)
    contact = ParagraphStyle("Contact", fontName="Helvetica", fontSize=8.3, leading=10.5, alignment=TA_CENTER, spaceAfter=7)
    section = ParagraphStyle("Section", fontName="Helvetica-Bold", fontSize=11.2, leading=14, alignment=TA_LEFT, spaceBefore=9, spaceAfter=4)
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=8.9, leading=11.6, alignment=TA_LEFT, spaceAfter=3)
    bullet = ParagraphStyle("Bullet", fontName="Helvetica", fontSize=8.9, leading=11.6, leftIndent=13, firstLineIndent=-9, spaceAfter=2.6)
    heading = ParagraphStyle("Heading", fontName="Helvetica-Bold", fontSize=9.3, leading=11.6, spaceBefore=6, spaceAfter=2)

    story = []
    story.append(Paragraph(USER_PROFILE["name"], title))

    l1, l2 = profile_contact(USER_PROFILE)
    story.append(Paragraph(f"{html.escape(l1)}<br/>{html.escape(l2)}", contact))
    story.append(HRFlowable(width="100%", thickness=0.9, color=colors.black))
    story.append(Spacer(1, 7))

    sections = {
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
        upper = line.upper()

        if upper in sections:
            story.append(Paragraph(upper, section))
            story.append(HRFlowable(width="100%", thickness=0.35, color=colors.grey))
            story.append(Spacer(1, 3))
        elif date_pattern.search(line):
            story.append(Paragraph(escaped, heading))
        elif line.isupper() and len(line) < 85:
            story.append(Paragraph(escaped, heading))
        elif line.startswith("•"):
            story.append(Paragraph(escaped, bullet))
        else:
            story.append(Paragraph(escaped, body))

    doc.build(story)
    buffer.seek(0)
    return buffer

st.title("Executive Career Hub")

tab1, tab2 = st.tabs(["Generate Resume", "Application History"])

with tab1:
    company = st.text_input("Target Company")
    role = st.text_input("Target Role")
    jd = st.text_area("Paste Job Description", height=250)
    file = st.file_uploader("Upload Master Resume PDF", type=["pdf"])

    if st.button("Generate Smart Resume"):
        if not api_key:
            st.error("Missing ANTHROPIC_API_KEY.")
        elif not company or not role or not jd or not file:
            st.warning("Fill all fields.")
        else:
            with st.spinner("Optimizing resume for 95%+ ATS target..."):
                try:
                    current_hash = make_hash(company, role, jd)
                    resume_text = extract_pdf(file)

                    client = anthropic.Anthropic(api_key=api_key)
                    data = generate_sections(client, company, role, jd, resume_text)
                    final_resume = build_resume(data)

                    detected_style = data.get("detected_company_style", "Auto")
                    company_type = data.get("company_type", "")
                    company_size = data.get("company_size", "")
                    company_focus = data.get("company_focus", "")
                    match = max(0, min(100, int(data.get("match", 90))))
                    ats = max(0, min(100, int(data.get("ats", 90))))
                    interview_probability = max(0, min(100, int(data.get("interview_probability", 80))))

                    missing_keywords = data.get("missing_keywords", [])
                    suggestions = data.get("improvement_suggestions", [])

                    conn.execute("""
                        INSERT INTO applications
                        (
                            date,
                            company,
                            role,
                            raw_jd,
                            jd_hash,
                            detected_style,
                            company_type,
                            company_size,
                            company_focus,
                            tailored_resume,
                            score_match,
                            score_ats,
                            interview_probability,
                            missing_keywords,
                            improvement_suggestions
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        datetime.now().strftime("%Y-%m-%d %H:%M"),
                        company,
                        role,
                        jd,
                        current_hash,
                        detected_style,
                        company_type,
                        company_size,
                        company_focus,
                        final_resume,
                        match,
                        ats,
                        interview_probability,
                        json.dumps(missing_keywords),
                        json.dumps(suggestions)
                    ))

                    conn.commit()

                    safe_company = re.sub(r"[^a-zA-Z0-9_-]+", "_", company)

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Match", f"{match}%")
                    col2.metric("ATS", f"{ats}%")
                    col3.metric("Interview Probability", f"{interview_probability}%")

                    st.success(f"Style: {detected_style}")

                    st.info(f"""
Company Type: {company_type}

Company Size: {company_size}

Company Focus: {company_focus}
""")

                    if data.get("style_reason"):
                        st.write("**Style Reason:**", data["style_reason"])

                    if missing_keywords:
                        st.subheader("ATS Gap Analysis")
                        for kw in missing_keywords:
                            st.write(f"❌ {kw}")

                    if suggestions:
                        st.subheader("How to Reach 95%+")
                        for item in suggestions:
                            st.write(f"✅ {item}")

                    if data.get("missing_keywords_added"):
                        st.subheader("Keywords Added")
                        st.write(", ".join(data["missing_keywords_added"]))

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
        "SELECT * FROM applications ORDER BY id DESC",
        conn
    )

    if logs.empty:
        st.info("No applications yet.")
    else:
        for _, row in logs.iterrows():
            with st.expander(
                f"{row['company']} | {row['role']} | {row.get('detected_style', 'Auto')} | Match {row['score_match']}% | ATS {row['score_ats']}%"
            ):
                st.write("Company:", row["company"])
                st.write("Role:", row["role"])
                st.write("Date:", row["date"])
                st.write("Detected Style:", row.get("detected_style", "Auto"))
                st.write("Company Type:", row.get("company_type", ""))
                st.write("Company Size:", row.get("company_size", ""))
                st.write("Company Focus:", row.get("company_focus", ""))
                st.write("Interview Probability:", f"{row.get('interview_probability', 0)}%")

                st.markdown("### Job Description")
                st.text_area("Saved JD", row.get("raw_jd", "") or "", height=250, key=f"jd_{row['id']}")

                try:
                    missing_saved = json.loads(row.get("missing_keywords") or "[]")
                except Exception:
                    missing_saved = []

                try:
                    suggestions_saved = json.loads(row.get("improvement_suggestions") or "[]")
                except Exception:
                    suggestions_saved = []

                if missing_saved:
                    st.markdown("### ATS Gap Analysis")
                    for kw in missing_saved:
                        st.write(f"❌ {kw}")

                if suggestions_saved:
                    st.markdown("### Improvement Suggestions")
                    for item in suggestions_saved:
                        st.write(f"✅ {item}")

                st.markdown("### Resume")
                st.markdown(
                    f'<div class="paper">{html.escape(row.get("tailored_resume", "") or "")}</div>',
                    unsafe_allow_html=True
                )

                col1, col2 = st.columns(2)

                with col1:
                    safe_company = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(row["company"]))

                    st.download_button(
                        "Download PDF",
                        data=generate_pdf(row.get("tailored_resume", "") or ""),
                        file_name=f"{safe_company}_resume.pdf",
                        mime="application/pdf",
                        key=f"pdf_{row['id']}"
                    )

                with col2:
                    if st.button("Delete Application", key=f"delete_{row['id']}"):
                        conn.execute(
                            "DELETE FROM applications WHERE id=?",
                            (int(row["id"]),)
                        )
                        conn.commit()
                        st.success("Application deleted.")
                        st.rerun()