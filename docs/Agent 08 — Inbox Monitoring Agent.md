# Agent 08 — Inbox Monitoring Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Inbox Monitoring Agent is the **first background agent** in the system. It runs continuously on a fixed 5-minute schedule using APScheduler. Its job is to check for new employer replies to sent outreach emails, match each reply to the correct campaign and email using tracking headers, save new replies to the database, and immediately trigger the Response Classification Agent for each new reply found.

---

## 2. Trigger

```
Campaign Execution Agent sends first email
        ↓
APScheduler activates Inbox Monitoring Agent
Runs every X minutes — configurable by human in UI
Default: 5 minutes
Runs until campaign is closed
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| sent_emails | emails table | All emails with status "Sent" |
| tracking_headers | emails table | Campaign ID and Email ID per sent email |
| replies | replies table | Already processed replies — avoid duplicates |
| inbox | Simulated DB / Gmail API (tentative) | Incoming reply emails |

---

## 4. Output

New rows inserted into `replies` table in PostgreSQL.

| Field | Type | Description |
|---|---|---|
| reply_id | PK | Auto-generated |
| email_id | FK → emails | The original sent email this replies to |
| campaign_id | FK → campaigns | Campaign this reply belongs to |
| company_name | TEXT | Company that replied |
| reply_from | TEXT | Sender email address |
| reply_subject | TEXT | Reply subject line |
| reply_body | TEXT | Full reply content |
| classification | TEXT | Pending Classification — set by next agent |
| received_at | TIMESTAMP | When reply was received |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `fetch_inbox()` | Fetch new emails from inbox (simulated or real) |
| `extract_tracking_headers()` | Read X-TalentBridge headers from reply |
| `match_reply_to_campaign()` | Link reply to campaign_id and email_id |
| `is_duplicate_reply()` | Check if reply already processed |
| `save_reply()` | Save new reply to PostgreSQL |
| `trigger_classification()` | Immediately trigger Response Classification Agent |
| `update_campaign_progress()` | Update replies_received in campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| Scheduler | APScheduler | — |
| Inbox Source | Simulated (tentative) | Gmail API / Outlook API |
| Database | PostgreSQL | — |

---

## 7. Inbox Source Options

The team member building this agent should choose one of the following options based on time and resources:

---

### Option A — Pre-written Mock Replies (Simplest)
Hardcoded mock replies stored directly in the database. Agent "discovers" them on schedule as if they just arrived.

```python
mock_replies = [
    {
        "from"     : "hr@tam.com.sa",
        "subject"  : "Re: AI & Data Talent for TAM",
        "body"     : "Thank you for reaching out. We are interested in learning more about your graduates. Can we schedule a call?",
        "headers"  : {"X-TalentBridge-Campaign-ID": "1", "X-TalentBridge-Email-ID": "42"},
        "received_at": datetime.now()
    },
    {
        "from"     : "recruitment@parsons.com",
        "subject"  : "Re: Engineering Talent Available",
        "body"     : "Thank you for your email. We are not currently hiring but will keep your details on file.",
        "headers"  : {"X-TalentBridge-Campaign-ID": "1", "X-TalentBridge-Email-ID": "51"},
        "received_at": datetime.now()
    }
]
```

**Best for:** Demo day — full control over what replies come in.

---

### Option B — LLM Generated Mock Replies (More Realistic)
LLM generates realistic replies for each sent email automatically. More variety and harder to predict — good for testing classification.

```python
def generate_mock_reply(sent_email: Email) -> dict:
    prompt = f"""
    Generate a realistic employer reply to this outreach email.
    Company: {sent_email.company_name}
    Original subject: {sent_email.subject}
    Randomly choose one response type:
      - Interested (40% chance)
      - Neutral / needs more info (30% chance)
      - Not interested (20% chance)
      - Auto-reply (10% chance)
    Return JSON: {{"body": "...", "response_type": "..."}}
    """
    return call_llm(prompt)
```

**Best for:** Testing the full pipeline end-to-end realistically.

---

### Option C — Real Gmail API (Stretch Goal)
Connect to a real Gmail inbox using Gmail API. Agent reads actual incoming emails.

```python
from googleapiclient.discovery import build

def fetch_real_inbox(credentials):
    service = build("gmail", "v1", credentials=credentials)
    results = service.users().messages().list(
        userId="me",
        q="is:unread"
    ).execute()
    return results.get("messages", [])
```

**Best for:** Real deployment after demo.

---

## 8. Reply Matching Logic

When a reply arrives — we extract tracking headers to identify which campaign and email it belongs to:

```python
def match_reply_to_campaign(reply: dict) -> dict:

    headers = reply.get("headers", {})

    campaign_id = headers.get("X-TalentBridge-Campaign-ID")
    email_id    = headers.get("X-TalentBridge-Email-ID")

    if campaign_id and email_id:
        # Perfect match via headers
        return {
            "campaign_id" : int(campaign_id),
            "email_id"    : int(email_id),
            "match_method": "Tracking Headers"
        }

    # Fallback — match by sender email
    sent_email = db.get_sent_email_by_recipient(reply["from"])
    if sent_email:
        return {
            "campaign_id" : sent_email.campaign_id,
            "email_id"    : sent_email.email_id,
            "match_method": "Sender Email Fallback"
        }

    # Cannot match — log and skip
    db.log_unmatched_reply(reply)
    return None
```

---

## 9. Processing Flow

```
APScheduler fires every 5 minutes
        ↓
STEP 1 — Fetch inbox
  Simulated / LLM Generated / Gmail API (tentative)
  Get all new unread emails
        ↓
STEP 2 — For each incoming email:

  ── EXTRACT TRACKING HEADERS ──
  Read X-TalentBridge-Campaign-ID
  Read X-TalentBridge-Email-ID
        ↓
  ── MATCH TO CAMPAIGN ──
  Match via tracking headers (primary)
  Match via sender email (fallback)
  Cannot match → log as unmatched → skip
        ↓
  ── CHECK DUPLICATE ──
  Has this reply already been processed?
  Yes → skip
  No  → proceed
        ↓
  ── SAVE REPLY ──
  Insert new row into replies table
  classification = "Pending Classification"
        ↓
  ── TRIGGER CLASSIFICATION ──
  Immediately call Response Classification Agent
  Pass: reply_id
        ↓
  ── UPDATE CAMPAIGN PROGRESS ──
  Increment replies_received in campaigns table

STEP 3 — Sleep until next 5-minute cycle
```

---

## 10. Duplicate Detection

```python
def is_duplicate_reply(reply_from: str, reply_subject: str,
                        received_at: datetime) -> bool:

    existing = db.query("""
        SELECT reply_id FROM replies
        WHERE reply_from = %s
        AND reply_subject = %s
        AND received_at > %s
    """, (reply_from, reply_subject,
          received_at - timedelta(hours=1)))

    return len(existing) > 0
```

If the same email arrives twice within 1 hour — treated as duplicate and skipped.

---

## 11. Edge Cases

| Edge Case | Handling |
|---|---|
| No new replies found | Log "No new replies" — sleep until next cycle |
| Reply has no tracking headers | Fall back to sender email matching |
| Reply cannot be matched to any campaign | Log as unmatched — notify human in dashboard |
| Duplicate reply received | Skip silently — already processed |
| Inbox API unavailable | Log error — retry on next 5-minute cycle |
| Reply body is empty | Save with empty body — pass to classification agent |
| Reply is from unknown sender | Log as unmatched — skip |
| Multiple replies from same company | Each saved as separate reply row |

---

## 12. Dashboard Notification

When new replies are found — human sees notification in dashboard:

```
🔔 3 new replies received
   TAM Development Co.    → Interested
   Parsons                → Not interested
   AECOM                  → Pending classification
```

Classification shown as soon as Response Classification Agent finishes.

---

## 13. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `emails` — sent emails and tracking headers
- `replies` — already processed replies (duplicate check)

This agent writes to:
- `replies` — new reply rows
- `campaigns` — replies_received counter

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `replies_received` | After each new reply saved |
| `last_updated` | After each cycle |

---

## 14. Pseudocode

```python
def inbox_monitoring_agent():

    # Runs every 5 minutes via APScheduler
    while True:

        # Fetch new emails
        new_emails = fetch_inbox()

        for email in new_emails:

            # Match to campaign
            match = match_reply_to_campaign(email)
            if not match:
                db.log_unmatched_reply(email)
                continue

            # Check duplicate
            if is_duplicate_reply(
                email["from"],
                email["subject"],
                email["received_at"]
            ):
                continue

            # Save reply
            reply_id = db.save_reply(
                email_id     = match["email_id"],
                campaign_id  = match["campaign_id"],
                company_name = db.get_company_name(match["email_id"]),
                reply_from   = email["from"],
                reply_subject= email["subject"],
                reply_body   = email["body"],
                received_at  = email["received_at"],
                classification = "Pending Classification"
            )

            # Update campaign progress
            db.increment_replies_received(match["campaign_id"])

            # Immediately trigger classification
            response_classification_agent(reply_id)

        # Sleep until next cycle
        time.sleep(300)  # 5 minutes
```

---

## 15. APScheduler Setup

```python
from apscheduler.schedulers.background import BackgroundScheduler

# Load check interval from campaign config
campaign = db.get_campaign(campaign_id)
check_interval = campaign.inbox_check_minutes  # set by human in UI

scheduler = BackgroundScheduler()

scheduler.add_job(
    func     = inbox_monitoring_agent,
    trigger  = "interval",
    minutes  = check_interval,
    id       = "inbox_monitor",
    name     = "Inbox Monitoring Agent",
    replace_existing = True
)

scheduler.start()
```

> **Note:** Human sets `inbox_check_minutes` from the campaign settings in the UI. Default is 5 minutes. Can be increased to reduce API calls or decreased for faster response detection.

---

## 16. Connection to Next Agent

```
New reply saved to replies table
        ↓
Response Classification Agent immediately triggered
Input to Response Classification Agent:
  - reply_id
  - reply_body
  - company_name
  - campaign_id
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
