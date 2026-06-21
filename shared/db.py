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

def create_campaign(
    campaign_name: str,
    selected_keywords: list[str],
    date_range_start,          # 'YYYY-MM-DD' or date
    date_range_end,            # 'YYYY-MM-DD' or date
    campaign_end_date=None,    # optional
    followup_days: int = 3,
    inbox_check_minutes: int = 5,
) -> int:
    """
    Create a new campaign row and return its campaign_id.
    Status starts at 'pending'. The UI's Launch button calls this.
    """
    query = """
        INSERT INTO campaigns (
            campaign_name, selected_keywords,
            date_range_start, date_range_end, campaign_end_date,
            followup_days, inbox_check_minutes
        )
        VALUES (%s, %s::text[], %s, %s, %s, %s, %s)
        RETURNING campaign_id
    """
    row = execute(query, (
        campaign_name, selected_keywords,
        date_range_start, date_range_end, campaign_end_date,
        followup_days, inbox_check_minutes,
    ))
    return row["campaign_id"] if row else None


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
    try:
        with conn.cursor() as cursor:

            query = """
                SELECT job_id, company_name, job_title, description_text,
               location, country, domain
                FROM job_postings
                WHERE LOWER(input_discovery_input_keyword_search) = ANY(
                    SELECT LOWER(k) FROM UNNEST(%s::text[]) k
                )
                    AND (%s::date IS NULL OR date_posted_parsed >= %s::date)
                    AND job_id NOT IN (
                        SELECT job_id FROM job_analysis WHERE campaign_id = %s
                    )
            """
            params = [keywords, date_from, date_from, campaign_id]

            if limit is not None:
                query += " LIMIT %s"
                params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

        jobs = []
        for row in rows:
            jobs.append(JobPosting(
                job_id           = row[0],
                company_name     = row[1],
                job_title        = row[2],
                description_text = row[3],
                location         = row[4],
                country          = row[5],
                domain           = row[6],
            ))

        return jobs

    finally:
        conn.close()
 
 
def save_job_analysis(campaign_id: int, job_id: int,
                      extracted_skills: list[str], experience_level: str,
                      job_type: str, key_responsibilities: list[str],
                      qualifications_summary: str,
                      llm_model_used: str) -> None:

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO job_analysis
                    (job_id, campaign_id, extracted_skills, experience_level,
                     job_type, key_responsibilities, qualifications_summary,
                     llm_model_used)
                VALUES (%s, %s, %s::text[], %s, %s, %s::text[], %s, %s)
                ON CONFLICT (job_id, campaign_id) DO NOTHING
            """, (job_id, campaign_id, extracted_skills, experience_level,
                  job_type, key_responsibilities, qualifications_summary,
                  llm_model_used))

        conn.commit()
    finally:
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

def fail_campaign(campaign_id: int) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE campaigns
                SET status       = 'failed',
                    completed_at = NOW(),
                    last_updated = NOW()
                WHERE campaign_id = %s
            """, (campaign_id,))
        conn.commit()
    finally:
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
               location, country, company_rating, company_link, apply_link, url
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
        company_rating   = row[6],
        company_link     = row[7],
        apply_link       = row[8],
        url              = row[9],
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
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def fetchall(query: str, params: tuple = ()):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute(query: str, params: tuple = ()):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, params)
            try:
                row = cursor.fetchone()
            except Exception:
                row = None
        conn.commit()
        return dict(row) if row else None
    finally:
        conn.close()


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
          AND contact_source != 'Human Input Required'
          AND contact_email NOT LIKE 'NEEDED:%%'
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

def flag_contact_needed(company_name: str, campaign_id: int) -> None:
    query = """
        INSERT INTO contacts (
            company_name,
            contact_email,
            contact_source,
            contact_verified,
            confidence_score,
            created_at
        )
        VALUES (%s, %s, 'Human Input Required', FALSE, 0.0, NOW())
        ON CONFLICT (company_name, contact_email) DO NOTHING
    """
    execute(query, (company_name, f"NEEDED:{company_name}"))


# ─────────────────────────────────────────────
# Agent 04 — Research Agent
# ─────────────────────────────────────────────


def get_companies_for_research(campaign_id: int):

    query = """
        SELECT DISTINCT jp.company_name
        FROM job_matches jm
        JOIN job_postings jp ON jm.job_id = jp.job_id
        WHERE jm.campaign_id = %s
        ORDER BY jp.company_name
    """
    return fetchall(query, (campaign_id,))
 
 
def get_research_by_company(company_name: str):    
    query = """
        SELECT
            research_id,
            company_name,
            research_summary,
            company_type,
            classification_confidence,
            why_interested,
            recent_news_hook,
            last_updated
        FROM company_research
        WHERE company_name = %s
    """
    return fetchone(query, (company_name,))
 
 
def save_company_research(
    company_name: str,
    research_summary: str,
    company_type: str,
    classification_confidence: str,
    why_interested=None,
    recent_news_hook=None,
):
    query = """
        INSERT INTO company_research (
            company_name,
            research_summary,
            company_type,
            classification_confidence,
            why_interested,
            recent_news_hook,
            last_updated
        )
        VALUES (%s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (company_name)
        DO UPDATE SET
            research_summary          = EXCLUDED.research_summary,
            company_type              = EXCLUDED.company_type,
            classification_confidence = EXCLUDED.classification_confidence,
            why_interested            = EXCLUDED.why_interested,
            recent_news_hook          = EXCLUDED.recent_news_hook,
            last_updated              = NOW()
        RETURNING research_id
    """
    return execute(query, (
        company_name,
        research_summary,
        company_type,
        classification_confidence,
        why_interested,
        recent_news_hook,
    ))


# ─────────────────────────────────────────────
# Agent 05 — Email Strategy Agent
# ─────────────────────────────────────────────

def get_companies_for_email_strategy(campaign_id: int):
    query = """
        SELECT DISTINCT jp.company_name
        FROM job_matches jm
        JOIN job_postings jp ON jm.job_id = jp.job_id
        WHERE jm.campaign_id = %s
        ORDER BY jp.company_name
    """
    return fetchall(query, (campaign_id,))


def get_company_research(company_name: str):
    query = """
        SELECT
            company_name,
            research_summary,
            company_type,
            classification_confidence,
            why_interested,
            recent_news_hook,
            last_updated
        FROM company_research
        WHERE company_name = %s
        LIMIT 1
    """
    return fetchone(query, (company_name,))


def get_job_matches_for_company(campaign_id: int, company_name: str):
    query = """
        SELECT
            jm.match_id,
            jm.campaign_id,
            jm.job_id,
            jm.student_id,
            jm.keyword_match_score,
            jm.semantic_match_score,
            jm.overall_match_score,
            jm.matched_skills,
            jp.company_name,
            jp.job_title,
            jp.location
        FROM job_matches jm
        JOIN job_postings jp ON jm.job_id = jp.job_id
        WHERE jm.campaign_id = %s
        AND jp.company_name = %s
        ORDER BY jm.overall_match_score DESC
    """
    return fetchall(query, (campaign_id, company_name))


def save_email_strategy(
    campaign_id: int,
    company_name: str,
    tone: str,
    angle: str,
    email_length: str,
    call_to_action: str,
    playbook_used: str
):
    query = """
        INSERT INTO email_strategy (
            campaign_id,
            company_name,
            tone,
            angle,
            email_length,
            call_to_action,
            playbook_used,
            created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        ON CONFLICT (campaign_id, company_name)
        DO UPDATE SET
            tone = EXCLUDED.tone,
            angle = EXCLUDED.angle,
            email_length = EXCLUDED.email_length,
            call_to_action = EXCLUDED.call_to_action,
            playbook_used = EXCLUDED.playbook_used,
            created_at = NOW()
        RETURNING strategy_id
    """
    return execute(query, (
        campaign_id,
        company_name,
        tone,
        angle,
        email_length,
        call_to_action,
        playbook_used,
    ))


# ─────────────────────────────────────────────
# Agent 06 — Email Generation Agent
# ─────────────────────────────────────────────

def get_email_strategy(campaign_id: int, company_name: str):
    """
    One email strategy row for a company in a campaign (Agent 05 output).
    Reads the live singular table `email_strategy`.
    """
    query = """
        SELECT strategy_id, campaign_id, company_name, tone, angle,
               email_length, call_to_action, playbook_used
        FROM email_strategy
        WHERE campaign_id = %s AND company_name = %s
        ORDER BY strategy_id DESC
        LIMIT 1
    """
    return fetchone(query, (campaign_id, company_name))

def get_students_by_ids(student_ids: list[int]):
    """Bulk-fetch student profiles for a list of IDs. Returns list of dicts."""
    if not student_ids:
        return []
    query = """
        SELECT student_id, full_name, email, skills, experience_years,
               location, field, status, summary, available_to_start, linkedin_url
        FROM student_profiles
        WHERE student_id = ANY(%s)
        ORDER BY student_id
    """
    return fetchall(query, (student_ids,))

def save_email(email: dict) -> int:
    """
    Insert one generated email into the emails table as 'Pending Approval'.
    Accepts the record produced by Agent 06's generators (the non-column
    'validation' key is ignored). Returns the new email_id.
    Leaves rejection_reason / approved_by / approved_at / sent_at NULL — Agent 07 sets those.
    """
    query = """
        INSERT INTO emails (
            campaign_id, email_type, recipient_email, recipient_name,
            subject, body, company_name, student_id, contact_id,
            contact_verified, status, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING email_id
    """
    params = (
        email.get("campaign_id"),
        email.get("email_type"),
        email.get("recipient_email"),
        email.get("recipient_name"),
        email.get("subject"),
        email.get("body"),
        email.get("company_name"),
        email.get("student_id"),
        email.get("contact_id"),
        email.get("contact_verified"),
        "Pending Approval",                 # status — always this on insert
    )
    row = execute(query, params)
    return row["email_id"] if row else None

def update_campaign_progress(campaign_id: int, status: str,
                             emails_generated: int = None):
    """
    Update a campaign's status during Agent 06's run, always bumping last_updated.
    Pass emails_generated to also record the count (used at the end of the run).
    Does NOT touch completed_at — Agent 06 is one step, not campaign completion.
    """
    if emails_generated is None:
        query = """
            UPDATE campaigns
            SET status = %s, last_updated = NOW()
            WHERE campaign_id = %s
            RETURNING campaign_id, status, emails_generated
        """
        return execute(query, (status, campaign_id))

    query = """
        UPDATE campaigns
        SET status = %s, emails_generated = %s, last_updated = NOW()
        WHERE campaign_id = %s
        RETURNING campaign_id, status, emails_generated
    """
    return execute(query, (status, emails_generated, campaign_id))

# ─────────────────────────────────────────────
# Agent 07 — Campaign Execution Agent
# ─────────────────────────────────────────────

def get_pending_emails(campaign_id: int):
    query = """
        SELECT
            e.email_id,
            e.campaign_id,
            e.email_type,
            e.recipient_email,
            e.recipient_name,
            e.subject,
            e.body,
            e.company_name,
            e.student_id,
            e.contact_id,
            e.contact_verified,
            e.status,
            c.contact_source
        FROM emails e
        LEFT JOIN contacts c ON e.contact_id = c.contact_id
        WHERE e.campaign_id = %s
        AND e.status = 'Pending Approval'
        ORDER BY
            CASE
                WHEN e.email_type = 'Employer Outreach' THEN 1
                WHEN e.email_type = 'Student Notification' THEN 2
                WHEN e.email_type = 'Follow-up' THEN 3
                WHEN e.email_type = 'Scheduling' THEN 4
                ELSE 5
            END,
            e.company_name ASC NULLS LAST,
            e.created_at ASC
    """
    return fetchall(query, (campaign_id,))


def get_email_by_id(email_id: int):
    query = """
        SELECT *
        FROM emails
        WHERE email_id = %s
        LIMIT 1
    """
    return fetchone(query, (email_id,))


def approve_email(email_id: int, approved_by: str = "Human Reviewer"):
    query = """
        UPDATE emails
        SET status = 'Approved',
            approved_by = %s,
            approved_at = NOW()
        WHERE email_id = %s
        RETURNING email_id, status
    """
    return execute(query, (approved_by, email_id))


def reject_email(email_id: int, rejection_reason: str):
    query = """
        UPDATE emails
        SET status = 'Rejected',
            rejection_reason = %s
        WHERE email_id = %s
        RETURNING email_id, status, rejection_reason
    """
    return execute(query, (rejection_reason, email_id))


def update_email_content(email_id: int, subject: str, body: str):
    query = """
        UPDATE emails
        SET subject = %s,
            body = %s,
            status = 'Pending Approval'
        WHERE email_id = %s
        RETURNING email_id, subject, body, status
    """
    return execute(query, (subject, body, email_id))


def mark_email_sent(email_id: int):
    query = """
        UPDATE emails
        SET status = 'Sent',
            sent_at = NOW(),
            tracking_headers = jsonb_build_object(
                'X-TalentBridge-Campaign-ID', campaign_id::TEXT,
                'X-TalentBridge-Email-ID', email_id::TEXT
            )
        WHERE email_id = %s
        RETURNING email_id, status, sent_at
    """
    return execute(query, (email_id,))


def mark_email_failed(email_id: int, error_message: str = None):
    query = """
        UPDATE emails
        SET status = 'Failed',
            rejection_reason = COALESCE(%s, rejection_reason)
        WHERE email_id = %s
        RETURNING email_id, status
    """
    return execute(query, (error_message, email_id))


def increment_emails_approved(campaign_id: int):
    query = """
        UPDATE campaigns
        SET emails_approved = COALESCE(emails_approved, 0) + 1,
            last_updated = NOW()
        WHERE campaign_id = %s
    """
    execute(query, (campaign_id,))


def increment_emails_sent(campaign_id: int):
    query = """
        UPDATE campaigns
        SET emails_sent = COALESCE(emails_sent, 0) + 1,
            last_updated = NOW()
        WHERE campaign_id = %s
    """
    execute(query, (campaign_id,))

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