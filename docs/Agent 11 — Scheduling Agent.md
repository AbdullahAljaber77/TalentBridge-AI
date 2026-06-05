# Agent 11 — Scheduling Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Scheduling Agent is the **fourth background agent** in the system. It is triggered immediately when the Response Classification Agent classifies a reply as "Interested". It presents the human with a scheduling form to fill in their available time slots, meeting format, and number of slots to propose. It then generates a professional scheduling email using that information and adds it to the approval queue. When the employer confirms a slot — the Inbox Monitoring Agent detects the reply, the Response Classification Agent classifies it as "Scheduled", and the meeting is marked confirmed in the database.

---

## 2. Trigger

```
Response Classification Agent classifies reply as "Interested"
        ↓
Scheduling Agent triggered immediately
Input: reply_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| reply_id | replies table | The interested reply that triggered scheduling |
| original_email | emails table | Original outreach email for context |
| contact | contacts table | HR contact details |
| company_research | company_research table | Company context for email tone |
| email_strategy | email_strategies table | Tone used in original email |
| human_input | UI form | Time slots, meeting format, number of slots |

---

## 4. Output

New row in `meetings` table:

| Field | Value | Description |
|---|---|---|
| meeting_id | PK | Auto-generated |
| campaign_id | FK → campaigns | Campaign this meeting belongs to |
| reply_id | FK → replies | Interested reply that triggered this |
| company_name | TEXT | Target company |
| contact_name | TEXT | HR contact name |
| contact_email | TEXT | HR contact email |
| proposed_slots | TEXT[] | Time slots proposed to employer |
| confirmed_slot | TIMESTAMP | Set when employer confirms — NULL until then |
| status | TEXT | Proposed |
| scheduling_email_id | FK → emails | The scheduling email sent |
| reminder_sent | BOOLEAN | False until reminder is sent |

New row in `emails` table:

| Field | Value | Description |
|---|---|---|
| email_type | "Scheduling" | Type identifier |
| status | "Pending Approval" | Goes to approval queue |
| subject | Re: original subject | References original thread |
| body | LLM generated | Scheduling email with time slots |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `load_reply_context()` | Load reply, original email, contact, research |
| `present_scheduling_form()` | Show UI form for human to fill time slots |
| `generate_scheduling_email()` | LLM generates scheduling email |
| `save_scheduling_email()` | Save to emails table as Pending Approval |
| `save_meeting_record()` | Save to meetings table with status Proposed |
| `mark_meeting_confirmed()` | Update meeting status when employer confirms |
| `send_meeting_reminder()` | Send reminder before confirmed meeting |
| `update_campaign_progress()` | Update campaigns and meetings_booked counter |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| LLM | Tentative — Anthropic / OpenAI | — |
| Calendar Integration | None — MVP | Google Calendar API (stretch) |
| Database | PostgreSQL | — |
| Frontend | Streamlit | Gradio |

---

## 7. Human Scheduling Form

When Scheduling Agent is triggered — human sees a form in the dashboard:

```
┌─────────────────────────────────────────────────────────┐
│  📅 MEETING REQUESTED — TAM Development Co.             │
│  Contact: Mohammed Al-Zahrani                           │
│  Their reply: "We would love to schedule a call..."     │
├─────────────────────────────────────────────────────────┤
│  Fill in your availability:                             │
│                                                         │
│  Number of slots to propose: [3] ▼                      │
│                                                         │
│  Slot 1: [Monday June 10, 10:00 AM]                    │
│  Slot 2: [Tuesday June 11, 2:00 PM ]                   │
│  Slot 3: [Wednesday June 12, 11:00 AM]                 │
│                                                         │
│  Meeting format:                                        │
│  ○ Video Call (Google Meet)                             │
│  ○ Video Call (Zoom)                                    │
│  ○ Phone Call                                           │
│  ○ In Person                                            │
│  ○ Let employer decide                                  │
│                                                         │
│  Duration: [30 minutes] ▼                              │
│                                                         │
│  [Generate Scheduling Email]                           │
└─────────────────────────────────────────────────────────┘
```

Human fills form → clicks Generate → LLM writes scheduling email → goes to approval queue.

---

## 8. Processing Flow

```
STEP 1 — Load reply context
  Load: reply, original email, contact, research, strategy
        ↓
STEP 2 — Notify human
  Dashboard notification:
  "TAM Development Co. is interested — fill in your availability"
        ↓
STEP 3 — Human fills scheduling form
  Provides: time slots, meeting format, duration
        ↓
STEP 4 — Generate scheduling email
  LLM writes professional scheduling reply
  References employer's interest
  Lists proposed time slots clearly
  Specifies meeting format and duration
        ↓
STEP 5 — Save to approval queue
  Save scheduling email to emails table
  Status = "Pending Approval"
        ↓
STEP 6 — Human reviews and approves
  Same approval queue as all other emails
        ↓
STEP 7 — Email sent
  Save meeting record to meetings table
  Status = "Proposed"
  proposed_slots = human provided slots
        ↓
STEP 8 — Wait for employer confirmation
  Inbox Monitoring Agent detects reply
  Response Classification Agent classifies as "Scheduled"
  mark_meeting_confirmed() called
  Meeting status → "Confirmed"
  confirmed_slot = employer's chosen slot
  meetings_booked counter incremented in campaigns table
        ↓
STEP 9 — Send reminder (stretch goal)
  24 hours before confirmed meeting
  Send reminder email to both coordinator and employer
```

---

## 9. LLM Prompt

```
System:
You are a professional recruitment coordinator writing a
meeting scheduling email. Be warm, professional, and clear.
Make it easy for the employer to pick a slot.
Always respond with valid JSON only.

User:
Write a scheduling email using the following information.

Company: {company_name}
Contact Name: {contact_name}
Their Reply: {employer_reply}
Original Email Subject: {original_subject}
Tone from original: {tone}

Available Time Slots:
{time_slots}

Meeting Format: {meeting_format}
Duration: {duration}

Requirements:
- Subject: "Re: {original_subject}"
- Open by thanking employer for their interest
- Propose time slots clearly and cleanly
- Specify meeting format and duration
- Ask employer to confirm preferred slot
- Close warmly with contact info
- Match tone of original email
- English only
- Under 150 words body

Return JSON:
{
  "subject": "...",
  "body": "..."
}
```

---

## 10. Example

### Input
```
Company: TAM Development Co.
Contact: Mohammed Al-Zahrani
Their reply: "This sounds interesting. Can we set up a call?"
Slots: Monday June 10 10AM, Tuesday June 11 2PM, Wednesday June 12 11AM
Format: Video Call (Google Meet)
Duration: 30 minutes
Tone: Professional
```

### Generated Scheduling Email
```
Subject: Re: AI & Data Engineering Talent — TAM's AI Expansion

Dear Mohammed,

Thank you for your interest — we are excited about the
possibility of connecting our graduates with TAM.

Here are a few times that work for a 30-minute Google Meet call:

• Monday, June 10 — 10:00 AM
• Tuesday, June 11 — 2:00 PM
• Wednesday, June 12 — 11:00 AM

Please let me know which works best for you and I will
send a calendar invite right away.

Looking forward to speaking with you.

Best regards,
Abdullah Al-Jaber
Talent Placement Manager — SDA/WeCloudData
+966 50 123 4567
abdullah@weclouddata.com
```

---

## 11. Meeting Status Lifecycle

```
Interested reply received
        ↓
Status: Proposed
(scheduling email sent with time slots)
        ↓
Employer confirms a slot
        ↓
Status: Confirmed
(confirmed_slot set, meetings_booked incremented)
        ↓
Meeting takes place
        ↓
Status: Completed
(human marks as completed in dashboard)
        ↓
OR employer cancels
        ↓
Status: Cancelled
(human marks as cancelled — may re-schedule)
```

---

## 12. Edge Cases

| Edge Case | Handling |
|---|---|
| Human does not fill scheduling form | Reminder shown in dashboard until filled |
| Employer confirms but slot already passed | Human notified — re-propose new slots |
| Employer proposes different time | Reply classified as Undecided — human reviews and re-schedules |
| Multiple interested replies from same company | One meeting record per reply — human manages |
| Employer confirms via phone not email | Human manually marks meeting as Confirmed in dashboard |
| Scheduling email rejected by human | Meeting record deleted — human re-fills form |
| LLM generates email over 150 words | Retry with stricter word limit |

---

## 13. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `replies` — interested reply context
- `emails` — original outreach email
- `contacts` — HR contact details
- `company_research` — company context
- `email_strategies` — original tone

This agent writes to:
- `emails` — scheduling email in approval queue
- `meetings` — meeting record
- `campaigns` — meetings_booked counter

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `meetings_booked` | After employer confirms a slot |
| `last_updated` | After each scheduling action |

---

## 14. Pseudocode

```python
def scheduling_agent(reply_id: int):

    # Load context
    reply    = db.get_reply(reply_id)
    original = db.get_original_email(reply.email_id)
    contact  = db.get_contact(reply.company_name)
    research = db.get_company_research(reply.company_name)
    strategy = db.get_email_strategy(reply.campaign_id, reply.company_name)

    # Notify human and wait for scheduling form
    ui.show_scheduling_form(
        company_name  = reply.company_name,
        contact_name  = contact.contact_name,
        employer_reply = reply.reply_body
    )

    # Wait for human input
    human_input = ui.wait_for_scheduling_input()

    # Generate scheduling email
    prompt = build_scheduling_prompt(
        company      = reply.company_name,
        contact      = contact,
        reply        = reply,
        original     = original,
        tone         = strategy.tone,
        slots        = human_input.time_slots,
        format       = human_input.meeting_format,
        duration     = human_input.duration
    )
    response = call_llm(prompt)
    scheduling_email = parse_json(response)

    # Save to approval queue
    scheduling_email_id = db.save_email(
        campaign_id     = reply.campaign_id,
        email_type      = "Scheduling",
        recipient_email = contact.contact_email,
        recipient_name  = contact.contact_name,
        company_name    = reply.company_name,
        subject         = scheduling_email["subject"],
        body            = scheduling_email["body"],
        status          = "Pending Approval"
    )

    # Save meeting record
    db.save_meeting(
        campaign_id          = reply.campaign_id,
        reply_id             = reply_id,
        company_name         = reply.company_name,
        contact_name         = contact.contact_name,
        contact_email        = contact.contact_email,
        proposed_slots       = human_input.time_slots,
        status               = "Proposed",
        scheduling_email_id  = scheduling_email_id
    )


def mark_meeting_confirmed(campaign_id: int, company_name: str,
                            confirmed_slot: str):
    db.update_meeting(
        company_name   = company_name,
        confirmed_slot = confirmed_slot,
        status         = "Confirmed"
    )
    db.increment_meetings_booked(campaign_id)
```

---

## 15. Connection to Next Agent

```
Meeting confirmed
        ↓
meetings_booked incremented in campaigns table
        ↓
Reporting Agent tracks all meeting activity
        ↓
Human marks meeting as Completed after it takes place
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
