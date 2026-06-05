# Agent 07 — Campaign Execution Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Campaign Execution Agent is the **seventh agent** in the pipeline. It manages the human approval workflow — presenting generated emails to the human one by one for review, handling approvals, edits, and rejections, and sending approved emails. It is the critical human-in-the-loop checkpoint — no email is ever sent without explicit human approval. Sending is tentative between simulated and real email API.

---

## 2. Trigger

```
Email Generation Agent completes
        ↓
LangGraph triggers Campaign Execution Agent
Input: campaign_id
        ↓
Human is notified: "X emails ready for your review"
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the active campaign |
| emails | emails table | All emails with status "Pending Approval" |
| contacts | contacts table | Contact verification status |

---

## 4. Output

Updated rows in `emails` table:

| Field | Updated To | When |
|---|---|---|
| status | "Approved" | Human clicks Approve |
| status | "Rejected" | Human clicks Reject |
| status | "Sent" | Email successfully sent |
| status | "Failed" | Email sending failed |
| approved_by | Human name | After approval |
| approved_at | Timestamp | After approval |
| rejection_reason | Text | After rejection |
| sent_at | Timestamp | After successful send |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `load_pending_emails()` | Load all emails with status "Pending Approval" |
| `present_email_for_review()` | Display email in approval queue UI |
| `approve_email()` | Mark email as approved in database |
| `edit_email()` | Save human edits to email body/subject |
| `reject_email()` | Mark email as rejected with reason |
| `send_email()` | Send approved email (tentative — simulated or real API) |
| `mark_email_sent()` | Update email status to "Sent" in database |
| `mark_email_failed()` | Update email status to "Failed" in database |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| Email Sending | Simulated (tentative) | Gmail API / SendGrid |
| Frontend | Streamlit | Gradio |
| Database | PostgreSQL | — |

---

## 7. Approval Queue UI

Each email is presented to the human one at a time:

```
┌─────────────────────────────────────────────────────────┐
│  📧 EMAIL REVIEW — 1 of 47                              │
│  Campaign: Python Cohort — June 2026                    │
├─────────────────────────────────────────────────────────┤
│  Type     : Employer Outreach                           │
│  Company  : TAM Development Co.                         │
│  To       : Mohammed Al-Zahrani                         │
│  Email    : mohammed@tam.com.sa                         │
│  Verified : ✅ Hunter.io                                │
│                                                         │
│  ⚠️  Best Guess Contact — please verify before sending  │
│  (shown only when contact_verified = False)             │
├─────────────────────────────────────────────────────────┤
│  Subject:                                               │
│  AI & Data Engineering Talent — TAM's AI Expansion      │
├─────────────────────────────────────────────────────────┤
│  Body:                                                  │
│  Dear Mohammed,                                         │
│                                                         │
│  I noticed TAM recently announced its expansion into    │
│  AI advisory services...                                │
│  [full email body shown here]                           │
├─────────────────────────────────────────────────────────┤
│  [✅ Approve]  [✏️ Edit]  [❌ Reject]                   │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Processing Flow

```
STEP 1 — Load all pending emails for this campaign
  Order by: email_type (Employer first, Student second)
  Then by: company_name alphabetically
        ↓
STEP 2 — Present emails one by one to human

  For each email:
          ↓
    ── HUMAN REVIEWS ──
    Human reads subject and body
    Human checks contact verification status
          ↓
    ── HUMAN DECIDES ──

    Option 1 → ✅ APPROVE
      Mark email status = "Approved"
      Save approved_by and approved_at
      Immediately trigger sending
              ↓
      ── SEND EMAIL ──
      Simulated (tentative) or real API
      Success → status = "Sent", save sent_at
      Failure → status = "Failed", log error
                retry once after 60 seconds
                still fails → flag for manual review

    Option 2 → ✏️ EDIT
      Human edits subject and/or body in UI
      Human clicks Save
      Email shown again for final review
      Human then approves or rejects

    Option 3 → ❌ REJECT
      Human selects rejection reason:
        - Wrong contact
        - Poor email quality
        - Company not relevant
        - Other (free text)
      Email status = "Rejected"
      Rejection reason saved to database
      Email stays in database for reporting
      Move to next email

STEP 3 — After all emails reviewed:
  Update campaign status
  Notify human: "Campaign execution complete
                X sent, Y rejected, Z failed"
```

---

## 9. Email Sending — Simulated vs Real

### Simulated (MVP — tentative)
```python
def send_email_simulated(email: Email) -> bool:
    # Log the send attempt
    print(f"[SIMULATED] Sending to {email.recipient_email}")
    print(f"Subject: {email.subject}")

    # Mark as sent in database
    db.mark_email_sent(email.email_id)
    return True
```

### Real API (Stretch Goal — tentative)
```python
def send_email_real(email: Email) -> bool:
    # Gmail API or SendGrid
    # Custom headers embedded for reply tracking
    response = email_api.send(
        to      = email.recipient_email,
        subject = email.subject,
        body    = email.body,
        from    = coordinator_email,
        headers = {
            "X-TalentBridge-Campaign-ID" : str(email.campaign_id),
            "X-TalentBridge-Email-ID"    : str(email.email_id)
        }
    )
    if response.status == 200:
        db.mark_email_sent(email.email_id)
        db.save_tracking_headers(email.email_id, {
            "X-TalentBridge-Campaign-ID" : str(email.campaign_id),
            "X-TalentBridge-Email-ID"    : str(email.email_id)
        })
        return True
    else:
        db.mark_email_failed(email.email_id, response.error)
        return False
```

---

## 10. Rejection Reasons

When human rejects an email — they select from:

| Reason | Description |
|---|---|
| Wrong contact | Email address or person is incorrect |
| Poor email quality | Email does not meet quality standards |
| Company not relevant | Company is not a good fit after review |
| Student mismatch | Student does not actually match this role |
| Duplicate | Similar email already sent to this company |
| Other | Human types custom reason |

All rejection reasons saved to `emails.rejection_reason` for reporting and improvement.

---

## 11. Edge Cases

| Edge Case | Handling |
|---|---|
| Human closes browser mid-review | Resume from last unreviewed email on next login |
| Email sending fails after approval | Retry once after 60 seconds — if still fails mark as Failed |
| Human edits email to be empty | Validation — prevent saving empty email |
| All emails rejected | Campaign marked as "Complete — all rejected" — no sends |
| Best guess contact approved | Send normally — human took responsibility by approving |
| Sending API unavailable | Queue email for retry — notify human |
| Human approves but contact email bounces | Mark as Failed — add to follow-up queue for manual fix |

---

## 12. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `emails` — all pending approval emails
- `contacts` — contact verification status

This agent writes to:
- `emails` — status, approved_by, approved_at, sent_at, rejection_reason
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `status` | "awaiting approval" → "executing" → "complete" |
| `emails_approved` | After each approval |
| `emails_sent` | After each successful send |
| `last_updated` | After each action |
| `completed_at` | When all emails reviewed |

---

## 13. Pseudocode

```python
def campaign_execution_agent(campaign_id: int):

    # Load pending emails
    emails = db.get_pending_emails(campaign_id)
    db.update_campaign_status(campaign_id, "awaiting approval")

    for email in emails:

        # Present to human via Streamlit UI
        action = ui.present_email_for_review(email)

        if action.type == "approve":
            # Mark approved
            db.approve_email(
                email_id    = email.email_id,
                approved_by = action.approved_by
            )

            # Send email
            success = send_email(email)

            if success:
                db.mark_email_sent(email.email_id)
                db.increment_emails_sent(campaign_id)
            else:
                # Retry once
                time.sleep(60)
                success = send_email(email)
                if success:
                    db.mark_email_sent(email.email_id)
                    db.increment_emails_sent(campaign_id)
                else:
                    db.mark_email_failed(email.email_id)

        elif action.type == "edit":
            # Save edits
            db.update_email_content(
                email_id = email.email_id,
                subject  = action.new_subject,
                body     = action.new_body
            )
            # Re-present for final review
            # (handled by UI loop)

        elif action.type == "reject":
            db.reject_email(
                email_id         = email.email_id,
                rejection_reason = action.reason
            )

        db.update_campaign_progress(campaign_id)

    # Campaign execution complete
    db.update_campaign_status(campaign_id, "complete")

    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 14. Connection to Next Agents

```
Campaign Execution Agent completes
        ↓
Emails sent → status = "Sent" in emails table
        ↓
Background Agents activate via APScheduler:

Inbox Monitoring Agent  → checks for replies every 5 minutes
Follow-Up Agent         → checks for needed follow-ups every 24 hours
Reporting Agent         → live dashboard always active
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
