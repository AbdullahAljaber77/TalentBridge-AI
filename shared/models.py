"""
TalentBridge AI - Enterprise Data Models
Description: Standardized data schemas representing core entities mapped across DB tables, APIs, and LangGraph states.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class Student:
    """Represents a student profile parsed for the job matching ecosystem."""
    student_id: Optional[int]
    full_name: str
    email: str
    skills: List[str]                      # Array of technical tags/skills
    experience_years: str
    location: str
    created_at: Optional[datetime] = None

@dataclass
class Campaign:
    """Represents an active or planned automated employer outreach campaign."""
    campaign_id: Optional[int]
    campaign_name: str
    selected_keywords: List[str]           # Target market/niche search keywords
    date_range_start: str                  # ISO date format or string date
    date_range_end: str
    campaign_end_date: Optional[str] = None
    followup_days: int = 3
    inbox_check_minutes: int = 60
    status: str = "draft"                  # e.g., 'draft', 'active', 'completed'
    created_at: Optional[datetime] = None

@dataclass
class Email:
    """Represents an AI-generated outbound email assigned to a specific campaign."""
    email_id: Optional[int]
    campaign_id: int
    email_type: str                        # e.g., 'enterprise', 'startup', 'government'
    recipient_email: str
    subject: str
    body: text                             # Full generated contextual markdown/text body
    status: str = "pending"                # e.g., 'pending', 'approved', 'sent', 'failed'
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

@dataclass
class Reply:
    """Represents an incoming tracking reply response analyzed and classified by AI."""
    reply_id: Optional[int]
    email_id: int
    campaign_id: int
    company_name: str
    reply_body: str
    classification: str                    # e.g., 'interested', 'not_interested', 'out_of_office'
    received_at: Optional[datetime] = None