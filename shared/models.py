"""
TalentBridge AI — Data Models
Dataclasses representing every core entity in the system.
These mirror the PostgreSQL tables and are used by all agents.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class Student:
    student_id:          Optional[int]
    full_name:           str
    email:               str
    skills:              List[str]
    experience_years:    str
    location:            str
    field:               str = ""
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


@dataclass
class Campaign:
    campaign_id:          Optional[int]
    campaign_name:        str
    selected_keywords:    List[str]
    date_range_start:     str
    date_range_end:       str
    campaign_end_date:    str = ""
    followup_days:        int = 3
    inbox_check_minutes:  int = 5
    status:               str = "pending"
    total_jobs_found:     int = 0
    jobs_processed:       int = 0
    emails_generated:     int = 0
    emails_approved:      int = 0
    emails_sent:          int = 0
    replies_received:     int = 0
    meetings_booked:      int = 0
    created_at:           Optional[datetime] = None


@dataclass
class JobPosting:
    job_id:               Optional[int]
    company_name:         str
    job_title:            str
    description_text:     str
    location:             str
    country:              str
    date_posted_parsed:   Optional[str] = None
    company_rating:       Optional[float] = None
    company_link:         Optional[str] = None
    apply_link:           Optional[str] = None
    url:                  Optional[str] = None
    input_discovery_input_keyword_search: str = ""


@dataclass
class JobAnalysis:
    analysis_id:           Optional[int]
    job_id:                int
    campaign_id:           int
    extracted_skills:      List[str]
    experience_level:      str        # Junior | Mid | Senior | Not specified
    job_type:              str        # Full-time | Part-time | Remote | Hybrid | Not specified
    key_responsibilities:  List[str]
    qualifications_summary: Optional[str] = None
    llm_model_used:        Optional[str] = None


@dataclass
class JobMatch:
    match_id:              Optional[int]
    campaign_id:           int
    job_id:                int
    student_id:            int
    keyword_match_score:   float
    semantic_match_score:  float
    overall_match_score:   float
    matched_skills:        List[str]
    matched_at:            Optional[datetime] = None


@dataclass
class Contact:
    contact_id:        Optional[int]
    company_name:      str
    contact_email:     str
    contact_source:    str            # Hunter.io | Web Search | Best Guess
    contact_name:      Optional[str] = None
    contact_title:     Optional[str] = None
    contact_verified:  bool = False
    confidence_score:  float = 0.5
    created_at:        Optional[datetime] = None


@dataclass
class CompanyResearch:
    research_id:               Optional[int]
    company_name:              str
    research_summary:          str
    company_type:              str    # Large Enterprise | Tech Startup | Government | Consulting | SME
    classification_confidence: str   # High | Medium | Low
    why_interested:            Optional[str] = None
    recent_news_hook:          Optional[str] = None


@dataclass
class EmailStrategy:
    strategy_id:   Optional[int]
    campaign_id:   int
    company_name:  str
    tone:          str    # Formal | Conversational
    angle:         str    # Skills Match | Company News | Cohort Size
    email_length:  str    # Short | Medium | Long
    call_to_action: str
    playbook_used: str


@dataclass
class Email:
    email_id:          Optional[int]
    campaign_id:       int
    email_type:        str            # Employer Outreach | Student Notification | Follow-up | Scheduling
    recipient_email:   str
    subject:           str
    body:              str            # ← was "text" in original — that's a Python keyword, use str
    status:            str = "Pending Approval"   # Pending Approval | Approved | Rejected | Sent | Failed
    recipient_name:    Optional[str] = None
    company_name:      Optional[str] = None
    student_id:        Optional[int] = None
    contact_id:        Optional[int] = None
    contact_verified:  bool = False
    rejection_reason:  Optional[str] = None
    approved_by:       Optional[str] = None
    approved_at:       Optional[datetime] = None
    sent_at:           Optional[datetime] = None
    created_at:        Optional[datetime] = None


@dataclass
class Reply:
    reply_id:        Optional[int]
    email_id:        int
    campaign_id:     int
    company_name:    str
    reply_from:      str
    reply_body:      str
    classification:  str = "Pending Classification"  # Interested | Neutral | Negative | Auto-reply
    reply_subject:   Optional[str] = None
    received_at:     Optional[datetime] = None
    classified_at:   Optional[datetime] = None
    llm_model_used:  Optional[str] = None


@dataclass
class FollowUp:
    followup_id:       Optional[int]
    campaign_id:       int
    email_id:          int
    company_name:      str
    reason:            str    # No Reply | Neutral Reply Needs Answer | Interested Needs Scheduling
    status:            str = "Pending"   # Pending | Approved | Sent | Skipped
    followup_email_id: Optional[int] = None
    suggested_at:      Optional[datetime] = None
    sent_at:           Optional[datetime] = None


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