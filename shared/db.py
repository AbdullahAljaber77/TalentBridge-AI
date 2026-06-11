"""
TalentBridge AI — Database Functions
All agents read from and write to the database through this file.
No agent writes raw SQL directly.

Note: DB column "field" in student_profiles is mapped to
      "field_of_study" in the Student model to avoid conflict
      with Python's dataclasses.field() function.
"""

import psycopg2
from shared.config import DATABASE_URL
from shared.models import JobAnalysis, Student, JobPosting


# ─────────────────────────────────────────────
# Connection
# ─────────────────────────────────────────────

def get_connection():
    return psycopg2.connect(DATABASE_URL)


# ─────────────────────────────────────────────
# Agent 01 — Job Analysis Agent
# ─────────────────────────────────────────────

# TODO: Osama will add functions here
# Examples:
#   save_job_analysis(...)
#   update_campaign_status(...)


# ─────────────────────────────────────────────
# Agent 02 — Targeting Agent
# ─────────────────────────────────────────────

def get_job_analyses(campaign_id: int) -> list[JobAnalysis]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT analysis_id, job_id, campaign_id, extracted_skills,
               experience_level, job_type, key_responsibilities,
               qualifications_summary, llm_model_used
        FROM job_analysis_mock
        WHERE campaign_id = %s
    """, (campaign_id,))

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    analyses = []
    for row in rows:
        analyses.append(JobAnalysis(
            analysis_id            = row[0],
            job_id                 = row[1],
            campaign_id            = row[2],
            extracted_skills       = row[3],
            experience_level       = row[4],
            job_type               = row[5],
            key_responsibilities   = row[6],
            qualifications_summary = row[7],
            llm_model_used         = row[8],
        ))

    return analyses


def get_all_students() -> list[Student]:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT student_id, full_name, email, skills, experience_years,
               location, field AS field_of_study, status, phone, linkedin_url,
               summary, preferred_job_type, preferred_location,
               expected_salary, available_to_start, cv_url, consent, is_mock
        FROM student_profiles
    """)

    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    students = []
    for row in rows:
        students.append(Student(
            student_id         = row[0],
            full_name          = row[1],
            email              = row[2],
            skills             = row[3],
            experience_years   = row[4],
            location           = row[5],
            field_of_study     = row[6],
            status             = row[7],
            phone              = row[8],
            linkedin_url       = row[9],
            summary            = row[10],
            preferred_job_type = row[11],
            preferred_location = row[12],
            expected_salary    = row[13],
            available_to_start = row[14],
            cv_url             = row[15],
            consent            = row[16],
            is_mock            = row[17],
        ))

    return students


def get_job_posting(job_id: int) -> JobPosting:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT job_id, company_name, job_title, description_text,
               location, country
        FROM job_postings
        WHERE job_id = %s
    """, (job_id,))

    row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not row:
        return None

    return JobPosting(
        job_id           = row[0],
        company_name     = row[1],
        job_title        = row[2],
        description_text = row[3],
        location         = row[4],
        country          = row[5],
    )


def save_job_match(campaign_id: int, job_id: int, student_id: int,
                   keyword_match_score: float, semantic_match_score: float,
                   overall_match_score: float, matched_skills: list[str]) -> None:

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO job_matches
            (campaign_id, job_id, student_id, keyword_match_score,
             semantic_match_score, overall_match_score, matched_skills)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (campaign_id, job_id, student_id) DO NOTHING
    """, (campaign_id, job_id, student_id, keyword_match_score,
          semantic_match_score, overall_match_score, matched_skills))

    conn.commit()
    cursor.close()
    conn.close()


# ─────────────────────────────────────────────
# Agent 03 — Contact Discovery Agent
# ─────────────────────────────────────────────

# TODO: Abdullah will add functions here
# Examples:
#   save_contact(...)
#   get_contacts_by_company(...)


# ─────────────────────────────────────────────
# Agent 04 — Research Agent
# ─────────────────────────────────────────────

# TODO: Osama will add functions here
# Examples:
#   save_company_research(...)
#   get_company_research(...)


# ─────────────────────────────────────────────
# Agent 05 — Email Strategy Agent
# ─────────────────────────────────────────────

# TODO: Abdullah will add functions here
# Examples:
#   save_email_strategy(...)
#   get_email_strategy(...)


# ─────────────────────────────────────────────
# Agent 06 — Email Generation Agent
# ─────────────────────────────────────────────

# TODO: Abdulmohsen will add functions here
# Examples:
#   save_email(...)
#   get_pending_emails(...)


# ─────────────────────────────────────────────
# Agent 07 — Campaign Execution Agent
# ─────────────────────────────────────────────

# TODO: Abdullah will add functions here
# Examples:
#   get_approved_emails(...)
#   mark_email_sent(...)


# ─────────────────────────────────────────────
# Agent 08 — Inbox Monitoring Agent
# ─────────────────────────────────────────────

# TODO: Osama will add functions here
# Examples:
#   save_reply(...)
#   get_unclassified_replies(...)


# ─────────────────────────────────────────────
# Agent 09 — Response Classification Agent
# ─────────────────────────────────────────────

# TODO: Abdulmohsen will add functions here
# Examples:
#   update_reply_classification(...)


# ─────────────────────────────────────────────
# Agent 10 — Follow-Up Agent
# ─────────────────────────────────────────────

# TODO: Abdullah will add functions here
# Examples:
#   save_followup(...)
#   get_pending_followups(...)


# ─────────────────────────────────────────────
# Agent 11 — Scheduling Agent
# ─────────────────────────────────────────────

# TODO: Osama will add functions here
# Examples:
#   save_meeting(...)
#   update_meeting_status(...)


# ─────────────────────────────────────────────
# Agent 12 — Reporting Agent
# ─────────────────────────────────────────────

# TODO: Abdulmohsen will add functions here
# Examples:
#   save_report(...)
#   get_campaign_summary(...)