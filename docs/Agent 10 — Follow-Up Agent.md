# Agent 10 — Follow-Up Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Follow-Up Agent is the **third background agent** in the system. It runs every 24 hours via APScheduler. Its job is to check all sent outreach emails that have received no reply and determine if it is time to send a follow-up based on the campaign's configured follow-up timing. It generates a short, polite follow-up email, adds it to the approval queue, and notifies the human. Each company gets one follow-up only — if still no reply after the follow-up, the company is marked as closed.

---

## 2. Trigger

```
APScheduler fires every 24 hours
        ↓
Follow-Up Agent checks all sent emails
across all active campaigns
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| sent_emails | emails table | All emails with status "Sent" |
| replies | replies table | Check if any reply exists per email |
| follow_ups | follow_ups table | Check if follow-up already sent |
| campaigns | campaigns table | Follow-up timing configuration |
| original_email | emails table | Original email content for context |

---

## 4. Output

New rows inserted into `emails` table (follow-up email):

| Field | Value | Description |
|---|---|---|
| email_type | "Follow-up" | Type identifier |
| status | "Pending Approval" | Goes to approval queue |
| company_name | From original email | Target company |
| recipient_email | From original email | Same recipient |
| subject | Re: original subject | References original |
| body | LLM generated | Short polite reminder |

New rows inserted into `follow_ups` table:

| Field | Type | Description |
|---|---|---|
| followup_id | PK | Auto-generated |
| campaign_id | FK → campaigns | Campaign this belongs to |
| email_id | FK → emails | Original email being followed up |
| followup_email_id | FK → emails | Generated follow-up email |
| reason | TEXT | No Reply |
| status | TEXT | Pending |
| suggested_at | TIMESTAMP | When follow-up was suggested |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `load_sent_emails()` | Load all sent emails across active campaigns |
| `check_reply_exists()` | Check if any reply received for this email |
| `check_followup_exists()` | Check if follow-up already sent for this email |
| `calculate_days_since_sent()` | Calculate days elapsed since email was sent |
| `generate_followup_email()` | LLM generates follow-up email |
| `save_followup_email()` | Save to emails table as Pending Approval |
| `save_followup_record()` | Save to follow_ups table |
| `mark_company_closed()` | Close company if follow-up also ignored |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| Scheduler | APScheduler | — |
| LLM | Tentative — Anthropic / OpenAI | — |
| Database | PostgreSQL | — |

---

## 7. Processing Flow

```
APScheduler fires every 24 hours
        ↓
STEP 1 — Load all sent employer outreach emails
  Filter: email_type = "Employer Outreach"
          status = "Sent"
        ↓
STEP 2 — For each sent email:

  ── CHECK IF REPLY EXISTS ──
  Has any reply been received for this email?
  Yes → skip — no follow-up needed
  No  → proceed
        ↓
  ── CHECK IF FOLLOW-UP ALREADY SENT ──
  Has a follow-up already been sent for this email?
  Yes → check if follow-up also ignored:
          Days since follow-up sent >= followup_days?
          Yes → mark company as closed
          No  → skip — still waiting
  No  → proceed
        ↓
  ── CHECK TIMING ──
  Days since original email sent >= campaign.followup_days?
  Yes → generate follow-up
  No  → skip — not yet time
        ↓
  ── GENERATE FOLLOW-UP EMAIL ──
  LLM generates short polite reminder
  References original email
  Restates value proposition briefly
  Same call to action as original
        ↓
  ── SAVE TO APPROVAL QUEUE ──
  Save follow-up email to emails table
  Status = "Pending Approval"
  Save record to follow_ups table
        ↓
  ── NOTIFY HUMAN ──
  Dashboard notification:
  "X follow-up emails ready for review"

STEP 3 — Sleep until next 24-hour cycle
```

---

## 8. Follow-Up Lifecycle

```
Day 0  → Original email sent
         ↓
Day N  → Follow-up timing reached (configured by human)
         ↓
Follow-Up Agent generates follow-up email
         ↓
Human approves → follow-up sent
         ↓
Day N + followup_days → Still no reply?
         ↓
Mark company as closed — no further outreach
```

---

## 9. LLM Prompt

```
System:
You are a professional recruitment coordinator writing a
short follow-up email. The follow-up should be polite,
brief, and reference the original email naturally.
Never sound pushy or desperate.
Always respond with valid JSON only.

User:
Write a follow-up email for the following outreach.

Original Email:
Subject: {original_subject}
Body: {original_body}

Company: {company_name}
Contact Name: {contact_name}
Days Since Original Email: {days_since_sent}

Requirements:
- Subject: "Re: {original_subject}"
- Under 80 words body
- Reference original email naturally
- Restate value briefly in one sentence
- Same call to action as original
- Polite and professional tone
- Never sound desperate or pushy
- English only

Return JSON:
{
  "subject": "...",
  "body": "..."
}
```

---

## 10. Example

### Original Email
```
Subject: AI & Data Engineering Talent — TAM's AI Expansion
Sent: June 1, 2026
Follow-up timing: 3 days
```

### Follow-Up Generated (Day 3)
```
Subject: Re: AI & Data Engineering Talent — TAM's AI Expansion

Dear Mohammed,

I wanted to follow up on my previous email regarding our
AI and Data Engineering graduates.

We have four candidates with strong Python, SQL, and AI
skills who are available immediately and aligned with
TAM's expansion into AI advisory services.

Would you be open to a 15-minute call this week?

Best regards,
Abdullah Al-Jaber
Talent Placement Manager — SDA/WeCloudData
+966 50 123 4567
```

---

## 11. Company Closure Logic

```python
def check_and_close_company(email_id: int, campaign_id: int):

    followup = db.get_followup(email_id)

    if not followup:
        return  # no follow-up sent yet

    campaign = db.get_campaign(campaign_id)
    days_since_followup = calculate_days_since(followup.sent_at)

    if days_since_followup >= campaign.followup_days:
        # Follow-up also ignored — close company
        db.mark_company_closed(
            campaign_id  = campaign_id,
            company_name = db.get_company_name(email_id),
            reason       = "No reply after follow-up"
        )
```

---

## 12. Edge Cases

| Edge Case | Handling |
|---|---|
| Reply received after follow-up generated but before approval | Cancel follow-up — remove from approval queue |
| Human rejects follow-up email | Mark follow-up as rejected — company stays open |
| Follow-up timing not yet reached | Skip — check again tomorrow |
| Company already marked closed | Skip — no follow-up for closed companies |
| Original email was rejected by human | Skip — no follow-up for rejected emails |
| Contact email bounced on original send | Skip — no point following up to bounced address |
| Multiple campaigns targeting same company | Each campaign manages its own follow-up independently |
| LLM generates follow-up over 80 words | Retry with stricter word limit instruction |

---

## 13. APScheduler Setup

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

scheduler.add_job(
    func     = followup_agent,
    trigger  = "interval",
    hours    = 24,
    id       = "followup_agent",
    name     = "Follow-Up Agent",
    replace_existing = True
)

scheduler.start()
```

---

## 14. Dashboard Notification

When follow-up emails are generated — human sees:

```
🔔 3 follow-up emails ready for your review
   TAM Development Co.    → No reply for 3 days
   Parsons                → No reply for 3 days
   AECOM                  → No reply for 5 days
```

Human reviews and approves each follow-up one by one in the approval queue — same flow as original emails.

---

## 15. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `emails` — sent outreach emails
- `replies` — check for existing replies
- `follow_ups` — check for existing follow-ups
- `campaigns` — follow-up timing configuration

This agent writes to:
- `emails` — new follow-up email in approval queue
- `follow_ups` — follow-up record
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `last_updated` | After each follow-up generated |

---

## 16. Pseudocode

```python
def followup_agent():

    # Load all active campaigns
    campaigns = db.get_active_campaigns()

    for campaign in campaigns:

        # Load sent employer outreach emails
        sent_emails = db.get_sent_emails(
            campaign_id = campaign.campaign_id,
            email_type  = "Employer Outreach"
        )

        for email in sent_emails:

            # Check if reply exists
            if db.reply_exists(email.email_id):
                continue

            # Check if follow-up already sent
            existing_followup = db.get_followup(email.email_id)

            if existing_followup:
                # Check if follow-up also ignored
                check_and_close_company(
                    email.email_id,
                    campaign.campaign_id
                )
                continue

            # Check timing
            days_since_sent = calculate_days_since(email.sent_at)
            if days_since_sent < campaign.followup_days:
                continue

            # Generate follow-up email
            original = db.get_email(email.email_id)
            contact  = db.get_contact_by_email(email.recipient_email)

            prompt = build_followup_prompt(original, contact, days_since_sent)
            response = call_llm(prompt)
            followup_email = parse_json(response)

            # Save to approval queue
            followup_email_id = db.save_email(
                campaign_id     = campaign.campaign_id,
                email_type      = "Follow-up",
                recipient_email = email.recipient_email,
                recipient_name  = email.recipient_name,
                company_name    = email.company_name,
                subject         = followup_email["subject"],
                body            = followup_email["body"],
                status          = "Pending Approval"
            )

            # Save follow-up record
            db.save_followup(
                campaign_id       = campaign.campaign_id,
                email_id          = email.email_id,
                followup_email_id = followup_email_id,
                reason            = "No Reply",
                status            = "Pending"
            )

            db.update_campaign_progress(campaign.campaign_id)

    # Sleep until next 24-hour cycle
    time.sleep(86400)
```

---

## 17. Connection to Next Agents

```
Follow-up email approved and sent
        ↓
Inbox Monitoring Agent watches for reply
        ↓
If reply received → Response Classification Agent
        ↓
If no reply after followup_days → Company marked closed
        ↓
Reporting Agent tracks all follow-up activity
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
