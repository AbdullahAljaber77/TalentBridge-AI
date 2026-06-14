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


def get_campaign(campaign_id: int) -> dict:
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        SELECT campaign_id, campaign_name, selected_keywords,
               date_range_start, date_range_end, status
        FROM campaigns
        WHERE campaign_id = %s
    """, (campaign_id,))
 
    row = cursor.fetchone()
    cursor.close()
    conn.close()
 
    if not row:
        return None
 
    return {
        "campaign_id"      : row[0],
        "campaign_name"    : row[1],
        "selected_keywords": row[2],
        "date_range_start" : row[3],
        "date_range_end"   : row[4],
        "status"           : row[5],
    }
 
 
def get_jobs_for_campaign(keywords: list[str], date_from,
                          campaign_id: int, limit: int = None) -> list[JobPosting]:
    conn = get_connection()
    cursor = conn.cursor()
 
    # Filter by selected keywords + date range, and skip jobs already
    # analysed for this campaign (so the agent is safe to restart).
    cursor.execute("""
        SELECT job_id, company_name, job_title, description_text,
               location, country
        FROM job_postings
        WHERE input_discovery_input_keyword_search = ANY(%s)
          AND (%s::date IS NULL OR date_posted_parsed >= %s::date)
          AND job_id NOT IN (
              SELECT job_id FROM job_analysis WHERE campaign_id = %s
          )
        LIMIT %s
    """, (keywords, date_from, date_from, campaign_id, limit))
 
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
 
    jobs = []
    for row in rows:
        jobs.append(JobPosting(
            job_id           = row[0],
            company_name     = row[1],
            job_title        = row[2],
            description_text = row[3],
            location         = row[4],
            country          = row[5],
        ))
 
    return jobs
 
 
def save_job_analysis(campaign_id: int, job_id: int,
                      extracted_skills: list[str], experience_level: str,
                      job_type: str, key_responsibilities: list[str],
                      qualifications_summary: str,
                      llm_model_used: str) -> None:
 
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        INSERT INTO job_analysis
            (job_id, campaign_id, extracted_skills, experience_level,
             job_type, key_responsibilities, qualifications_summary,
             llm_model_used)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (job_id, campaign_id) DO NOTHING
    """, (job_id, campaign_id, extracted_skills, experience_level,
          job_type, key_responsibilities, qualifications_summary,
          llm_model_used))
 
    conn.commit()
    cursor.close()
    conn.close()
 
 
def start_campaign(campaign_id: int, total_jobs_found: int,
                   total_batches: int) -> None:
 
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        UPDATE campaigns
        SET status           = 'running',
            total_jobs_found = %s,
            total_batches    = %s,
            jobs_processed   = 0,
            jobs_failed      = 0,
            started_at       = NOW(),
            last_updated     = NOW()
        WHERE campaign_id = %s
    """, (total_jobs_found, total_batches, campaign_id))
 
    conn.commit()
    cursor.close()
    conn.close()
 
 
def update_current_batch(campaign_id: int, current_batch: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        UPDATE campaigns
        SET current_batch = %s,
            last_updated  = NOW()
        WHERE campaign_id = %s
    """, (current_batch, campaign_id))
 
    conn.commit()
    cursor.close()
    conn.close()
 
 
def increment_jobs_processed(campaign_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        UPDATE campaigns
        SET jobs_processed = jobs_processed + 1,
            last_updated   = NOW()
        WHERE campaign_id = %s
    """, (campaign_id,))
 
    conn.commit()
    cursor.close()
    conn.close()
 
 
def increment_jobs_failed(campaign_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        UPDATE campaigns
        SET jobs_failed  = jobs_failed + 1,
            last_updated = NOW()
        WHERE campaign_id = %s
    """, (campaign_id,))
 
    conn.commit()
    cursor.close()
    conn.close()
 
 
def complete_campaign(campaign_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()
 
    cursor.execute("""
        UPDATE campaigns
        SET status       = 'complete',
            completed_at = NOW(),
            last_updated = NOW()
        WHERE campaign_id = %s
    """, (campaign_id,))
 
    conn.commit()
    cursor.close()
    conn.close()
 
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
        FROM job_analysis
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
        ORDER BY student_id ASC
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

def update_student_summary(student_id: int, summary: str) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE student_profiles
        SET summary = %s
        WHERE student_id = %s
    """, (summary, student_id))

    conn.commit()
    cursor.close()
    conn.close()

# ─────────────────────────────────────────────
# Agent 03 — Contact Discovery Agent
# ─────────────────────────────────────────────

from psycopg2.extras import RealDictCursor


def fetchone(query: str, params: tuple = ()):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return dict(row) if row else None


def fetchall(query: str, params: tuple = ()):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [dict(row) for row in rows]


def execute(query: str, params: tuple = ()):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute(query, params)

    row = None
    try:
        row = cursor.fetchone()
    except Exception:
        row = None

    conn.commit()
    cursor.close()
    conn.close()

    return dict(row) if row else None


def get_company_targets_for_contact_discovery(campaign_id: int):
    query = """
        SELECT DISTINCT
            jp.company_name,
            jp.domain,
            jp.company_link,
            jp.url,
            jp.input_discovery_input_domain
        FROM job_matches jm
        JOIN job_postings jp ON jm.job_id = jp.job_id
        WHERE jm.campaign_id = %s
        ORDER BY jp.company_name
    """
    return fetchall(query, (campaign_id,))


def get_cached_contact(company_name: str):
    query = """
        SELECT
            contact_id,
            company_name,
            contact_name,
            contact_email,
            contact_title,
            contact_verified,
            contact_source,
            confidence_score
        FROM contacts
        WHERE company_name = %s
        ORDER BY confidence_score DESC NULLS LAST, last_used_at DESC NULLS LAST
        LIMIT 1
    """
    return fetchone(query, (company_name,))


def save_contact(
    company_name: str,
    contact_email: str,
    contact_name=None,
    contact_title=None,
    contact_verified: bool = False,
    contact_source: str = "Best Guess",
    confidence_score: float = 0.2
):
    query = """
        INSERT INTO contacts (
            company_name,
            contact_name,
            contact_email,
            contact_title,
            contact_verified,
            contact_source,
            confidence_score,
            last_used_at,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
        ON CONFLICT (company_name, contact_email)
        DO UPDATE SET
            contact_name = COALESCE(EXCLUDED.contact_name, contacts.contact_name),
            contact_title = COALESCE(EXCLUDED.contact_title, contacts.contact_title),
            contact_verified = EXCLUDED.contact_verified,
            contact_source = EXCLUDED.contact_source,
            confidence_score = EXCLUDED.confidence_score,
            last_used_at = NOW()
        RETURNING contact_id
    """
    return execute(query, (
        company_name,
        contact_name,
        contact_email,
        contact_title,
        contact_verified,
        contact_source,
        confidence_score
    ))


def update_contact_last_used(contact_id: int):
    query = """
        UPDATE contacts
        SET last_used_at = NOW()
        WHERE contact_id = %s
    """
    execute(query, (contact_id,))


def update_campaign_status(campaign_id: int, status: str):
    query = """
        UPDATE campaigns
        SET status = %s,
            last_updated = NOW()
        WHERE campaign_id = %s
    """
    execute(query, (status, campaign_id))


def touch_campaign(campaign_id: int):
    query = """
        UPDATE campaigns
        SET last_updated = NOW()
        WHERE campaign_id = %s
    """
    execute(query, (campaign_id,))


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