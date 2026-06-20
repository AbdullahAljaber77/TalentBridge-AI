# TalentBridge AI — Database Schema
### RCP #7 — Employer Outreach Program Agent
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## Overview

This document defines the complete PostgreSQL database schema for TalentBridge AI. All agents read from and write to these tables. This is the single source of truth for all data structures.

---

## Table Index

| # | Table | Written By | Read By |
|---|---|---|---|
| 1 | `campaigns` | Human / All Agents | All Agents |
| 2 | `job_postings` | Data Pipeline | All Agents |
| 3 | `job_analysis` | Job Analysis Agent | Targeting Agent |
| 4 | `student_profiles` | Data Pipeline / Form | Targeting Agent |
| 5 | `job_matches` | Targeting Agent | Contact Discovery, Email Generation |
| 6 | `contacts` | Contact Discovery Agent | Email Generation Agent |
| 7 | `company_research` | Research Agent | Email Strategy, Email Generation |
| 8 | `email_strategies` | Email Strategy Agent | Email Generation Agent |
| 9 | `emails` | Email Generation Agent | Campaign Execution, Reporting |
| 10 | `replies` | Inbox Monitoring Agent | Response Classification Agent |
| 11 | `follow_ups` | Follow-Up Agent | Campaign Execution Agent |
| 12 | `meetings` | Scheduling Agent | Reporting Agent |
| 13 | `reports` | Reporting Agent | Human |

---

## 1. campaigns

Stores every campaign created by the human. Tracks campaign configuration and real-time progress.

```sql
CREATE TABLE campaigns (
    campaign_id         SERIAL PRIMARY KEY,
    campaign_name       TEXT NOT NULL,
    selected_keywords   TEXT[] NOT NULL,
    date_range_start    DATE NOT NULL,
    date_range_end      DATE NOT NULL,
    campaign_end_date   DATE NOT NULL,
    -- date after which campaign auto-completes
    -- remaining no-reply companies marked closed automatically
    followup_days       INTEGER NOT NULL DEFAULT 3,
    inbox_check_minutes INTEGER NOT NULL DEFAULT 5,
    -- how often inbox monitoring agent checks for new replies
    -- configurable by human from UI — default 5 minutes
    status              TEXT NOT NULL DEFAULT 'pending',
    -- status values: pending | running | paused | complete | failed
    total_jobs_found    INTEGER DEFAULT 0,
    jobs_processed      INTEGER DEFAULT 0,
    jobs_failed         INTEGER DEFAULT 0,
    current_batch       INTEGER DEFAULT 0,
    total_batches       INTEGER DEFAULT 0,
    emails_generated    INTEGER DEFAULT 0,
    emails_approved     INTEGER DEFAULT 0,
    emails_sent         INTEGER DEFAULT 0,
    replies_received    INTEGER DEFAULT 0,
    meetings_booked     INTEGER DEFAULT 0,
    started_at          TIMESTAMP,
    completed_at        TIMESTAMP,
    last_updated        TIMESTAMP DEFAULT NOW(),
    created_at          TIMESTAMP DEFAULT NOW()
);
```

---

## 2. job_postings

Stores the cleaned job postings dataset. Loaded once from `saudi_job_market_final.csv`. Read-only for all agents.

```sql
CREATE TABLE job_postings (
    job_id                               SERIAL PRIMARY KEY,
    company_name                         TEXT NOT NULL,
    job_title                            TEXT NOT NULL,
    description_text                     TEXT NOT NULL,
    location                             TEXT NOT NULL,
    country                              TEXT NOT NULL,
    date_posted_parsed                   DATE,
    company_rating                       FLOAT,
    company_link                         TEXT,
    domain                               TEXT,
    apply_link                           TEXT,
    url                                  TEXT,
    input_discovery_input_domain         TEXT,
    input_discovery_input_keyword_search TEXT NOT NULL,
    loaded_at                            TIMESTAMP DEFAULT NOW()
);
```

---

## 3. job_analysis

Stores structured intelligence extracted from job descriptions by the Job Analysis Agent.

```sql
CREATE TABLE job_analysis (
    analysis_id              SERIAL PRIMARY KEY,
    job_id                   INTEGER NOT NULL REFERENCES job_postings(job_id),
    campaign_id              INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    extracted_skills         TEXT[] NOT NULL DEFAULT '{}',
    experience_level         TEXT NOT NULL DEFAULT 'Not specified',
    -- experience_level values: Junior | Mid | Senior | Not specified
    job_type                 TEXT NOT NULL DEFAULT 'Not specified',
    -- job_type values: Full-time | Part-time | Remote | Hybrid | Not specified
    key_responsibilities     TEXT[] NOT NULL DEFAULT '{}',
    qualifications_summary   TEXT,
    llm_model_used           TEXT,
    processed_at             TIMESTAMP DEFAULT NOW(),
    UNIQUE (job_id, campaign_id)
);
```

---

## 4. student_profiles

Stores student profiles collected from the Google Form and mock profiles.

```sql
CREATE TABLE student_profiles (
    student_id          SERIAL PRIMARY KEY,
    full_name           TEXT NOT NULL,
    email               TEXT NOT NULL UNIQUE,
    phone               TEXT,
    linkedin_url        TEXT,
    location            TEXT NOT NULL,
    status              TEXT NOT NULL,
    -- status values: Fresh Graduate | Currently Employed | Unemployed | Freelancer | Student
    experience_years    TEXT NOT NULL,
    -- values: No experience | Less than 1 year | 1-2 years | 3-5 years | 5+ years
    field               TEXT NOT NULL,
    skills              TEXT[] NOT NULL DEFAULT '{}',
    summary             TEXT,
    preferred_job_type  TEXT[] NOT NULL DEFAULT '{}',
    preferred_location  TEXT[] NOT NULL DEFAULT '{}',
    expected_salary     TEXT,
    available_to_start  TEXT NOT NULL,
    cv_url              TEXT,
    is_mock             BOOLEAN DEFAULT FALSE,
    consent             BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

---

## 5. job_matches

Stores the matching results between student profiles and job postings produced by the Targeting Agent.

```sql
CREATE TABLE job_matches (
    match_id                SERIAL PRIMARY KEY,
    campaign_id             INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    job_id                  INTEGER NOT NULL REFERENCES job_postings(job_id),
    student_id              INTEGER NOT NULL REFERENCES student_profiles(student_id),
    keyword_match_score     FLOAT NOT NULL DEFAULT 0.0,
    semantic_match_score    FLOAT NOT NULL DEFAULT 0.0,
    overall_match_score     FLOAT NOT NULL DEFAULT 0.0,
    matched_skills          TEXT[] NOT NULL DEFAULT '{}',
    matched_at              TIMESTAMP DEFAULT NOW(),
    UNIQUE (campaign_id, job_id, student_id)
);
```

---

## 6. contacts

Stores discovered HR contacts for each company. Cached across campaigns.

```sql
CREATE TABLE contacts (
    contact_id          SERIAL PRIMARY KEY,
    company_name        TEXT NOT NULL,
    contact_name        TEXT,
    contact_email       TEXT NOT NULL,
    contact_title       TEXT,
    contact_verified    BOOLEAN NOT NULL DEFAULT FALSE,
    contact_source      TEXT NOT NULL,
    -- source values: Hunter.io | Web Search | Best Guess
    confidence_score    FLOAT,
    last_used_at        TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (company_name, contact_email)
);
```

---

## 7. company_research

Stores research summaries and company type classifications produced by the Research Agent.

```sql
CREATE TABLE company_research (
    research_id               SERIAL PRIMARY KEY,
    company_name              TEXT NOT NULL UNIQUE,
    research_summary          TEXT NOT NULL,
    company_type              TEXT NOT NULL,
    -- type values: Large Enterprise | Tech Startup | Government | Consulting | SME
    classification_confidence TEXT NOT NULL,
    -- values: High | Medium | Low
    why_interested            TEXT,
    recent_news_hook          TEXT,
    -- one sentence recent news for email opener — NULL if no news found
    last_updated              TIMESTAMP DEFAULT NOW()
);
```

---

## 8. email_strategies

Stores the email strategy decisions produced by the Email Strategy Agent for each company per campaign.

```sql
CREATE TABLE email_strategies (
    strategy_id         SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    company_name        TEXT NOT NULL,
    tone                TEXT NOT NULL,
    -- values: Formal | Conversational
    angle               TEXT NOT NULL,
    -- values: Skills Match | Company News | Cohort Size
    email_length        TEXT NOT NULL,
    -- values: Short | Medium | Long
    call_to_action      TEXT NOT NULL,
    playbook_used       TEXT NOT NULL,
    created_at          TIMESTAMP DEFAULT NOW(),
    UNIQUE (campaign_id, company_name)
);
```

---

## 9. emails

Stores all generated emails — both employer outreach and student notifications. Central table for the approval queue.

```sql
CREATE TABLE emails (
    email_id            SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    email_type          TEXT NOT NULL,
    -- values: Employer Outreach | Student Notification | Follow-up | Scheduling
    recipient_email     TEXT NOT NULL,
    recipient_name      TEXT,
    subject             TEXT NOT NULL,
    body                TEXT NOT NULL,
    company_name        TEXT,
    student_id          INTEGER REFERENCES student_profiles(student_id),
    contact_id          INTEGER REFERENCES contacts(contact_id),
    contact_verified    BOOLEAN DEFAULT FALSE,
    tracking_headers    JSONB,
    -- stores: {"X-TalentBridge-Campaign-ID": "1", "X-TalentBridge-Email-ID": "42"}
    -- used for reply matching — set on send, read on reply received
    status              TEXT NOT NULL DEFAULT 'Pending Approval',
    -- values: Pending Approval | Approved | Rejected | Sent | Failed
    rejection_reason    TEXT,
    approved_by         TEXT,
    approved_at         TIMESTAMP,
    sent_at             TIMESTAMP,
    created_at          TIMESTAMP DEFAULT NOW()
);
```

---

## 10. replies

Stores incoming employer replies monitored by the Inbox Monitoring Agent.

```sql
CREATE TABLE replies (
    reply_id            SERIAL PRIMARY KEY,
    email_id            INTEGER NOT NULL REFERENCES emails(email_id),
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    company_name        TEXT NOT NULL,
    reply_from          TEXT NOT NULL,
    reply_subject       TEXT,
    reply_body          TEXT NOT NULL,
    classification      TEXT,
    -- values: Interested | Neutral | Negative | Auto-reply | Pending Classification
    received_at         TIMESTAMP NOT NULL,
    classified_at       TIMESTAMP,
    llm_model_used      TEXT
);
```

---

## 11. follow_ups

Stores follow-up recommendations produced by the Follow-Up Agent.

```sql
CREATE TABLE follow_ups (
    followup_id         SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    email_id            INTEGER NOT NULL REFERENCES emails(email_id),
    company_name        TEXT NOT NULL,
    followup_email_id   INTEGER REFERENCES emails(email_id),
    reason              TEXT NOT NULL,
    -- values: No Reply | Neutral Reply Needs Answer | Interested Needs Scheduling
    status              TEXT NOT NULL DEFAULT 'Pending',
    -- values: Pending | Approved | Sent | Skipped
    suggested_at        TIMESTAMP DEFAULT NOW(),
    sent_at             TIMESTAMP
);
```

---

## 12. meetings

Stores scheduled meetings produced by the Scheduling Agent.

```sql
CREATE TABLE meetings (
    meeting_id          SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    reply_id            INTEGER NOT NULL REFERENCES replies(reply_id),
    company_name        TEXT NOT NULL,
    contact_name        TEXT,
    contact_email       TEXT NOT NULL,
    proposed_slots      TEXT[] NOT NULL DEFAULT '{}',
    confirmed_slot      TIMESTAMP,
    status              TEXT NOT NULL DEFAULT 'Proposed',
    -- values: Proposed | Confirmed | Cancelled | Completed
    scheduling_email_id INTEGER REFERENCES emails(email_id),
    reminder_sent       BOOLEAN DEFAULT FALSE,
    created_at          TIMESTAMP DEFAULT NOW(),
    last_updated        TIMESTAMP DEFAULT NOW()
);
```

---

## 13. reports

Stores generated campaign reports produced by the Reporting Agent.

```sql
CREATE TABLE reports (
    report_id           SERIAL PRIMARY KEY,
    campaign_id         INTEGER NOT NULL REFERENCES campaigns(campaign_id),
    report_type         TEXT NOT NULL,
    -- values: Full Report | Summary
    total_jobs_processed INTEGER NOT NULL DEFAULT 0,
    total_companies_targeted INTEGER NOT NULL DEFAULT 0,
    total_emails_sent   INTEGER NOT NULL DEFAULT 0,
    total_replies       INTEGER NOT NULL DEFAULT 0,
    response_rate       FLOAT NOT NULL DEFAULT 0.0,
    interested_count    INTEGER NOT NULL DEFAULT 0,
    neutral_count       INTEGER NOT NULL DEFAULT 0,
    negative_count      INTEGER NOT NULL DEFAULT 0,
    meetings_booked     INTEGER NOT NULL DEFAULT 0,
    top_performing_keywords TEXT[],
    top_responding_companies TEXT[],
    recommendations     TEXT,
    generated_at        TIMESTAMP DEFAULT NOW()
);
```

---

## Entity Relationship Overview

```
campaigns
    │
    ├── job_analysis (campaign_id)
    ├── job_matches (campaign_id)
    ├── email_strategies (campaign_id)
    ├── emails (campaign_id)
    ├── replies (campaign_id)
    ├── follow_ups (campaign_id)
    ├── meetings (campaign_id)
    └── reports (campaign_id)

job_postings
    │
    ├── job_analysis (job_id)
    └── job_matches (job_id)

student_profiles
    │
    ├── job_matches (student_id)
    └── emails (student_id)

contacts
    └── emails (contact_id)

emails
    ├── replies (email_id)
    ├── follow_ups (email_id, followup_email_id)
    └── meetings (scheduling_email_id)

replies
    └── meetings (reply_id)
```

---

## Notes

- All tables use `SERIAL PRIMARY KEY` — PostgreSQL auto-increments
- All foreign keys enforce referential integrity
- `campaigns` is the central table — almost every other table references it
- `job_postings` is read-only after initial data load
- `company_research` and `contacts` are cached across campaigns — not re-created per campaign
- Timestamps use PostgreSQL `TIMESTAMP` — store in UTC

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
*Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber*
