"""
TalentBridge AI — Data Models
Dataclasses representing every core entity in the system.
These mirror the PostgreSQL tables and are used by all agents.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Union


# ─────────────────────────────────────────────
# Date utility — used when building models from DB rows or user input
# ─────────────────────────────────────────────

def to_date(value: Union[str, date, datetime, None]) -> Optional[date]:
    """
    Convert anything date-like into a Python date object.

    Handles:
        "2024-11-01"         → date(2024, 11, 1)   string from LLM or DB
        datetime(2024, 11,1) → date(2024, 11, 1)   datetime from psycopg2
        date(2024, 11, 1)    → date(2024, 11, 1)   already correct
        None                 → None                 optional fields
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value.strip())
    raise ValueError(f"Cannot convert {type(value)} to date: {value}")


# ─────────────────────────────────────────────
# Student
# ─────────────────────────────────────────────

@dataclass
class Student:
    student_id:          Optional[int]
    full_name:           str
    email:               str
    skills:              List[str]
    experience_years:    str
    location:            str
    field_of_study:               str = ""
    status:              str = ""
    phone:               Optional[str] = None
    linkedin_url:        Optional[str] = None
    summary:             Optional[str] = None
    preferred_job_type:  List[str] = field(default_factory=list)
    preferred_location:  List[str] = field(default_factory=list)
    expected_salary:     Optional[str] = None
    available_to_start:  str = "Immediately"
    cv_url:              Optional[str] = None
    consent:             bool = False
    is_mock:             bool = False
    created_at:          Optional[datetime] = None


# ─────────────────────────────────────────────
# Campaign      *added 6 missing fields*
# ─────────────────────────────────────────────

@dataclass
class Campaign:
    campaign_id:          Optional[int]
    campaign_name:        str
    selected_keywords:    List[str]
    date_range_start:     date
    date_range_end:       date
    campaign_end_date:    Optional[date] = None
    followup_days:        int = 3
    inbox_check_minutes:  int = 5
    status:               str = "pending"
    total_jobs_found:     int = 0
    jobs_processed:       int = 0
    jobs_failed:          int = 0           
    current_batch:        int = 0          
    total_batches:        int = 0           
    emails_generated:     int = 0
    emails_approved:      int = 0
    emails_sent:          int = 0
    replies_received:     int = 0
    meetings_booked:      int = 0
    started_at:           Optional[datetime] = None   
    completed_at:         Optional[datetime] = None   
    last_updated:         Optional[datetime] = None   
    created_at:           Optional[datetime] = None
 

# ─────────────────────────────────────────────
# Job Posting       *added domain, input_discovery_input_domain, loaded_at*
# ─────────────────────────────────────────────

@dataclass
class JobPosting:
    job_id:               Optional[int]
    company_name:         str
    job_title:            str
    description_text:     str
    location:             str
    country:              str
    date_posted_parsed:   Optional[date] = None
    company_rating:       Optional[float] = None
    company_link:         Optional[str] = None
    domain:               Optional[str] = None                    
    apply_link:           Optional[str] = None
    url:                  Optional[str] = None
    input_discovery_input_domain:          Optional[str] = None  
    input_discovery_input_keyword_search:  str = ""
    loaded_at:            Optional[datetime] = None              
 

# ─────────────────────────────────────────────
# Job Analysis      *added processed_at*
# ─────────────────────────────────────────────

@dataclass
class JobAnalysis:
    analysis_id:            Optional[int]
    job_id:                 int
    campaign_id:            int
    extracted_skills:       List[str]
    experience_level:       str
    job_type:               str
    key_responsibilities:   List[str]
    qualifications_summary: Optional[str] = None
    llm_model_used:         Optional[str] = None
    processed_at:           Optional[datetime] = None   
 

# ─────────────────────────────────────────────
# Job Match
# ─────────────────────────────────────────────

@dataclass
class JobMatch:
    match_id:             Optional[int]
    campaign_id:          int
    job_id:               int
    student_id:           int
    keyword_match_score:  float
    semantic_match_score: float
    overall_match_score:  float
    matched_skills:       List[str]
    matched_at:           Optional[datetime] = None


# ─────────────────────────────────────────────
# Contact
# ─────────────────────────────────────────────

@dataclass
class Contact:
    contact_id:       Optional[int]
    company_name:     str
    contact_email:    str
    contact_source:   str           # Hunter.io | Web Search | Best Guess
    contact_name:     Optional[str] = None
    contact_title:    Optional[str] = None
    contact_verified: bool = False
    confidence_score: float = 0.5
    created_at:       Optional[datetime] = None


# ─────────────────────────────────────────────
# Company Research      *added last_updated*
# ─────────────────────────────────────────────

@dataclass
class CompanyResearch:
    research_id:               Optional[int]
    company_name:              str
    research_summary:          str
    company_type:              str      # Large Enterprise | Tech Startup | Government | Consulting | SME
    classification_confidence: str     # High | Medium | Low
    why_interested:            Optional[str] = None
    recent_news_hook:          Optional[str] = None
    last_updated:              Optional[datetime] = None


# ─────────────────────────────────────────────
# Email Strategy
# ─────────────────────────────────────────────

@dataclass
class EmailStrategy:
    strategy_id:    Optional[int]
    campaign_id:    int
    company_name:   str
    tone:           str     # Formal | Conversational
    angle:          str     # Skills Match | Company News | Cohort Size
    email_length:   str     # Short | Medium | Long
    call_to_action: str
    playbook_used:  str


# ─────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────

@dataclass
class Email:
    email_id:         Optional[int]
    campaign_id:      int
    email_type:       str           # Employer Outreach | Student Notification | Follow-up | Scheduling
    recipient_email:  str
    subject:          str
    body:             str
    status:           str = "Pending Approval"  # Pending Approval | Approved | Rejected | Sent | Failed
    recipient_name:   Optional[str] = None
    company_name:     Optional[str] = None
    student_id:       Optional[int] = None
    contact_id:       Optional[int] = None
    contact_verified: bool = False
    rejection_reason: Optional[str] = None
    approved_by:      Optional[str] = None
    approved_at:      Optional[datetime] = None
    sent_at:          Optional[datetime] = None
    created_at:       Optional[datetime] = None


# ─────────────────────────────────────────────
# Reply
# ─────────────────────────────────────────────

@dataclass
class Reply:
    reply_id:       Optional[int]
    email_id:       int
    campaign_id:    int
    company_name:   str
    reply_from:     str
    reply_body:     str
    classification: str = "Pending Classification"  # Interested | Neutral | Negative | Auto-reply
    reply_subject:  Optional[str] = None
    received_at:    Optional[datetime] = None
    classified_at:  Optional[datetime] = None
    llm_model_used: Optional[str] = None


# ─────────────────────────────────────────────
# Follow-Up
# ─────────────────────────────────────────────

@dataclass
class FollowUp:
    followup_id:       Optional[int]
    campaign_id:       int
    email_id:          int
    company_name:      str
    reason:            str      # No Reply | Neutral Reply | Interested Needs Scheduling
    status:            str = "Pending"  # Pending | Approved | Sent | Skipped
    followup_email_id: Optional[int] = None
    suggested_at:      Optional[datetime] = None
    sent_at:           Optional[datetime] = None


# ─────────────────────────────────────────────
# Meeting
# ─────────────────────────────────────────────

@dataclass
class Meeting:
    meeting_id:          Optional[int]
    campaign_id:         int
    reply_id:            int
    company_name:        str
    contact_email:       str
    proposed_slots:      List[str]
    status:              str = "Proposed"   # Proposed | Confirmed | Cancelled | Completed
    contact_name:        Optional[str] = None
    confirmed_slot:      Optional[datetime] = None
    scheduling_email_id: Optional[int] = None
    reminder_sent:       bool = False
    created_at:          Optional[datetime] = None