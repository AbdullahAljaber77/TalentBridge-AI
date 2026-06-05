# Agent 12 — Reporting Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Reporting Agent is the **final agent** in the system. It has two modes — a live dashboard that updates in real time throughout the campaign, and a full report generator that activates when the campaign completes. The live dashboard shows key metrics at a glance. The full report is generated on demand after campaign completion and is downloadable as a PDF. The agent queries PostgreSQL directly — no LLM needed for the dashboard. The LLM is used only for generating recommendations in the full report.

---

## 2. Trigger

```
Mode 1 — Live Dashboard:
  Always active while campaign is running
  Refreshes automatically from PostgreSQL

Mode 2 — Full Report:
  Triggered when human clicks "Generate Report"
  Only available after campaign status = "Complete"
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the campaign to report on |
| campaigns | campaigns table | Campaign config and progress counters |
| emails | emails table | All emails — sent, approved, rejected |
| replies | replies table | All replies and classifications |
| meetings | meetings table | All meetings — proposed and confirmed |
| follow_ups | follow_ups table | All follow-up activity |
| job_matches | job_matches table | Matching scores and keywords |
| student_profiles | student_profiles table | Student match success |

---

## 4. Output

### Mode 1 — Live Dashboard
Real-time metrics displayed in Streamlit UI — no database write.

### Mode 2 — Full Report
New row inserted into `reports` table + downloadable PDF.

| Field | Type | Description |
|---|---|---|
| report_id | PK | Auto-generated |
| campaign_id | FK → campaigns | Campaign this report covers |
| report_type | TEXT | Full Report |
| total_jobs_processed | INTEGER | Jobs analysed by Job Analysis Agent |
| total_companies_targeted | INTEGER | Unique companies contacted |
| total_emails_sent | INTEGER | Employer outreach emails sent |
| total_replies | INTEGER | Total replies received |
| response_rate | FLOAT | replies / emails_sent * 100 |
| interested_count | INTEGER | Interested classifications |
| neutral_count | INTEGER | Undecided classifications |
| negative_count | INTEGER | Not Interested classifications |
| meetings_booked | INTEGER | Confirmed meetings |
| top_performing_keywords | TEXT[] | Keywords with highest response rate |
| top_responding_companies | TEXT[] | Companies that replied positively |
| recommendations | TEXT | LLM generated recommendations |
| generated_at | TIMESTAMP | When report was generated |

---

## 5. Tools

### Live Dashboard Tools
| Tool | Purpose |
|---|---|
| `get_campaign_counters()` | Read live counters from campaigns table |
| `get_pipeline_status()` | Count employers at each pipeline stage |
| `get_reply_breakdown()` | Count Interested / Not Interested / Undecided |
| `get_pending_actions()` | Count emails awaiting approval |

### Full Report Tools
| Tool | Purpose |
|---|---|
| `calculate_response_rate()` | replies / emails_sent * 100 |
| `get_top_keywords()` | Keywords with highest match and response rate |
| `get_top_companies()` | Companies that responded positively |
| `get_student_match_rate()` | How many students got at least one match |
| `get_funnel_metrics()` | Full funnel breakdown |
| `generate_recommendations()` | LLM generates next campaign recommendations |
| `save_report()` | Save report to PostgreSQL |
| `export_pdf()` | Generate downloadable PDF report |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| Frontend | Streamlit | Gradio |
| PDF Export | ReportLab / WeasyPrint | FPDF |
| LLM | Tentative — Anthropic / OpenAI | — |
| Database | PostgreSQL | — |

---

## 7. Live Dashboard

Always visible while campaign is running. Refreshes automatically.

```
┌─────────────────────────────────────────────────────────────┐
│  📊 TALENTBRIDGE AI — LIVE DASHBOARD                        │
│  Campaign: Python Cohort — June 2026    Status: Running ⚙️  │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│  Emails  │ Replies  │ Response │Interested│   Meetings     │
│  Sent    │Received  │  Rate    │          │   Booked       │
│   200    │    45    │  22.5%   │    15    │      8         │
├──────────┴──────────┴──────────┴──────────┴────────────────┤
│  PIPELINE STATUS                                            │
├─────────────────────────────────────────────────────────────┤
│  Pending Approval  : 12  emails                            │
│  Sent              : 200 emails                            │
│  Awaiting Reply    : 143 companies                         │
│  Follow-up Sent    : 34  companies                         │
│  Interested        : 15  companies                         │
│  Meeting Proposed  : 10  companies                         │
│  Meeting Confirmed : 8   companies                         │
│  Closed            : 42  companies                         │
├─────────────────────────────────────────────────────────────┤
│  REPLY BREAKDOWN                                            │
├─────────────────────────────────────────────────────────────┤
│  Interested    ████████░░  15  (33%)                       │
│  Not Interested████████████ 20  (44%)                      │
│  Undecided     █████░░░░░  10  (22%)                       │
├─────────────────────────────────────────────────────────────┤
│  PENDING ACTIONS                                            │
├─────────────────────────────────────────────────────────────┤
│  ⚠️  12 emails awaiting your approval                      │
│  ⚠️  3  replies needing human review                       │
│  ⚠️  2  companies need contact info                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. Full Report — Sections

Generated after campaign completes. Human clicks "Generate Report".

---

### Section 1 — Campaign Summary
```
Campaign Name   : Python Cohort — June 2026
Start Date      : June 1, 2026
End Date        : June 30, 2026
Keywords        : data engineer, ai engineer, data analyst
Students        : 10 profiles
Job Postings    : 1,247 processed
Companies       : 200 targeted
```

---

### Section 2 — Outreach Funnel
```
Jobs Processed          1,247    (100%)
        ↓
Companies Targeted        200    (16%)
        ↓
Emails Sent               200    (100% of targeted)
        ↓
Replies Received           45    (22.5%)
        ↓
Interested                 15    (33% of replies)
        ↓
Meetings Proposed          10    (67% of interested)
        ↓
Meetings Confirmed          8    (80% of proposed)
```

---

### Section 3 — Response Breakdown
```
Interested      : 15  (33%)
Not Interested  : 20  (44%)
Undecided       : 10  (22%)
```

---

### Section 4 — Top Performing Keywords
```
Keyword                    Emails  Replies  Rate
─────────────────────────────────────────────────
data engineer              80      22       27.5%
ai engineer                45      13       28.9%
data analyst               40       8       20.0%
cloud solutions architect  20       2       10.0%
```

---

### Section 5 — Top Responding Companies
```
Company               Reply        Classification
─────────────────────────────────────────────────
TAM Development Co.   Interested   Meeting Confirmed
Lucidya               Interested   Meeting Confirmed
Salla                 Interested   Meeting Proposed
TAWANTECH             Interested   Meeting Confirmed
Accenture             Interested   Meeting Proposed
```

---

### Section 6 — Student Match Success
```
Student              Matches  Emails Sent  Employer Interested
──────────────────────────────────────────────────────────────
Ahmed Al-Rashidi     12       8            3
Sara Al-Otaibi       9        6            2
Mohammed Al-Ghamdi   7        5            1
Fatima Al-Zahrani    5        4            0
Omar Al-Harbi        11       7            2
```

---

### Section 7 — Recommendations (LLM Generated)
```
Based on this campaign's performance:

1. AI Engineer keyword had the highest response rate (28.9%) —
   increase targeting for this keyword in next campaign.

2. Cloud Solutions Architect had the lowest response rate (10%) —
   consider refining student profiles for cloud roles.

3. Consulting firms responded faster (avg 1.8 days) vs Large
   Enterprises (avg 3.2 days) — prioritize consulting outreach.

4. 8 of 10 proposed meetings were confirmed (80%) —
   scheduling email template is performing well.

5. Consider collecting more student CVs — profiles with CVs
   had 40% higher match scores.
```

---

## 9. LLM Prompt — Recommendations

```
System:
You are a campaign analytics expert analyzing an employer
outreach campaign for a training academy.
Generate clear, actionable recommendations for the next campaign.
Always respond with valid JSON only.

User:
Analyze this campaign performance and generate recommendations.

Campaign Stats:
{campaign_summary}

Top Keywords by Response Rate:
{keyword_performance}

Company Type Performance:
{company_type_performance}

Student Match Stats:
{student_match_stats}

Follow-up Performance:
{followup_stats}

Generate 5 specific, actionable recommendations.
Focus on: what worked, what did not, what to improve.

Return JSON:
{
  "recommendations": [
    "recommendation 1",
    "recommendation 2",
    "recommendation 3",
    "recommendation 4",
    "recommendation 5"
  ]
}
```

---

## 10. PDF Export Structure

```
Page 1 — Cover
  TalentBridge AI
  Campaign Report
  Campaign Name
  Date Generated

Page 2 — Campaign Summary + Funnel

Page 3 — Response Breakdown + Charts

Page 4 — Top Keywords + Top Companies

Page 5 — Student Match Success

Page 6 — Recommendations
```

---

## 11. Edge Cases

| Edge Case | Handling |
|---|---|
| Campaign has 0 replies | Report shows 0% response rate — recommendations focus on email quality |
| Campaign has 0 emails sent | Report shows error — campaign incomplete |
| LLM recommendations fail | Skip recommendations section — rest of report still generated |
| PDF generation fails | Show report on screen — notify human PDF unavailable |
| Campaign not yet complete | "Generate Report" button disabled — shows days remaining |
| Human generates report before all meetings confirmed | Report generated with current data — note that meetings may still be pending |

---

## 12. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `campaigns` — counters and config
- `emails` — all email activity
- `replies` — all reply classifications
- `meetings` — all meeting activity
- `follow_ups` — all follow-up activity
- `job_matches` — keyword and match data
- `student_profiles` — student details

This agent writes to:
- `reports` — full report record
- `campaigns` — status update to "Reported"

---

## 13. Pseudocode

```python
# ── Live Dashboard ────────────────────────────────────────────
def get_live_dashboard_data(campaign_id: int) -> dict:

    campaign  = db.get_campaign(campaign_id)
    emails    = db.get_email_stats(campaign_id)
    replies   = db.get_reply_stats(campaign_id)
    meetings  = db.get_meeting_stats(campaign_id)
    pipeline  = db.get_pipeline_status(campaign_id)
    pending   = db.get_pending_actions(campaign_id)

    return {
        "emails_sent"      : campaign.emails_sent,
        "replies_received" : campaign.replies_received,
        "response_rate"    : round(
            campaign.replies_received /
            max(campaign.emails_sent, 1) * 100, 1
        ),
        "interested"       : replies.interested_count,
        "meetings_booked"  : campaign.meetings_booked,
        "pipeline"         : pipeline,
        "reply_breakdown"  : replies.breakdown,
        "pending_actions"  : pending
    }

# ── Full Report ───────────────────────────────────────────────
def generate_full_report(campaign_id: int):

    # Gather all metrics
    summary        = db.get_campaign_summary(campaign_id)
    funnel         = db.get_funnel_metrics(campaign_id)
    keywords       = db.get_keyword_performance(campaign_id)
    companies      = db.get_top_companies(campaign_id)
    students       = db.get_student_match_stats(campaign_id)
    company_types  = db.get_company_type_performance(campaign_id)
    followups      = db.get_followup_stats(campaign_id)

    # Generate recommendations via LLM
    prompt = build_recommendations_prompt(
        summary, keywords, company_types, students, followups
    )
    response = call_llm(prompt)
    recs     = parse_json(response)

    # Save report to database
    report_id = db.save_report(
        campaign_id              = campaign_id,
        report_type              = "Full Report",
        total_jobs_processed     = summary.jobs_processed,
        total_companies_targeted = summary.companies_targeted,
        total_emails_sent        = summary.emails_sent,
        total_replies            = summary.replies_received,
        response_rate            = funnel.response_rate,
        interested_count         = funnel.interested_count,
        neutral_count            = funnel.undecided_count,
        negative_count           = funnel.negative_count,
        meetings_booked          = summary.meetings_booked,
        top_performing_keywords  = keywords.top_5,
        top_responding_companies = companies.top_5,
        recommendations          = "\n".join(recs["recommendations"])
    )

    # Export PDF
    pdf = export_pdf(report_id)

    # Update campaign status
    db.update_campaign_status(campaign_id, "Reported")

    return {"report_id": report_id, "pdf_path": pdf}
```

---

## 14. This is the Final Agent

```
Reporting Agent completes
        ↓
Campaign status = "Reported"
        ↓
Full report saved to database
PDF available for download
        ↓
Past outreach results saved to Vector DB
Used by Email Strategy Agent in future campaigns
        ↓
TalentBridge AI cycle complete
Ready for next campaign
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
