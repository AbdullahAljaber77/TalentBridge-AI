# Agent 09 — Response Classification Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Response Classification Agent is the **second background agent** in the system. It is triggered immediately every time the Inbox Monitoring Agent finds a new reply. It reads the reply content and uses an LLM to classify it into one of three categories — Interested, Not Interested, or Undecided — along with a confidence score. Based on the classification it either triggers the Scheduling Agent, marks the company as closed, or flags the reply for human review.

---

## 2. Trigger

```
Inbox Monitoring Agent saves new reply
        ↓
Response Classification Agent immediately triggered
Input: reply_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| reply_id | replies table | ID of the new reply to classify |
| reply_body | replies table | Full reply content |
| reply_from | replies table | Sender email |
| company_name | replies table | Company that replied |
| campaign_id | replies table | Campaign this reply belongs to |
| original_email | emails table | The original outreach email we sent |

---

## 4. Output

Updated row in `replies` table:

| Field | Updated To | Description |
|---|---|---|
| classification | Interested / Not Interested / Undecided | LLM classification result |
| classified_at | Timestamp | When classification was done |
| llm_model_used | Model name | Which LLM was used |

Updated row in `emails` table:

| Field | Updated To | Description |
|---|---|---|
| status | varies | Updated based on classification |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `load_reply()` | Load full reply details from PostgreSQL |
| `load_original_email()` | Load original sent email for context |
| `call_llm()` | Send reply to LLM for classification |
| `parse_classification()` | Parse and validate LLM JSON output |
| `save_classification()` | Update reply row with classification result |
| `trigger_scheduling_agent()` | Trigger if classification is Interested |
| `mark_company_closed()` | Update campaign status if Not Interested |
| `flag_for_human_review()` | Add to dashboard review queue if Undecided |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| LLM | Tentative — Anthropic / OpenAI | — |
| Database | PostgreSQL | — |

---

## 7. Classification Categories

| Category | Meaning | Next Action |
|---|---|---|
| **Interested** | Employer shows clear interest in graduates | Trigger Scheduling Agent immediately |
| **Scheduled** | Employer confirms a specific meeting time | Update meeting status to Confirmed |
| **Not Interested** | Employer clearly declines | Mark company as closed — no further action |
| **Undecided** | Cannot clearly determine — too vague, auto-reply, question, referral | Flag for human review in dashboard |

---

## 8. Processing Flow

```
STEP 1 — Load reply and original email
        ↓
STEP 2 — Send to LLM for classification
  Input: reply body + original email context
  Output: classification + confidence score + reasoning
        ↓
STEP 3 — Evaluate confidence score

  High confidence (>= 0.75):
    Use LLM classification directly
          ↓
  Low confidence (< 0.75):
    Override to "Undecided"
    Flag for human review regardless of LLM result

STEP 4 — Save classification to replies table
        ↓
STEP 5 — Take action based on classification:

  Interested →
    Trigger Scheduling Agent immediately
    Update dashboard notification

  Not Interested →
    Mark company as closed in campaign
    No further outreach to this company
    Update dashboard

  Undecided →
    Add to human review queue in dashboard
    Human reads reply and manually reclassifies
    Human decision triggers next action
        ↓
STEP 6 — Update campaign progress
```

---

## 9. LLM Prompt

```
System:
You are an expert email response analyst for a recruitment
outreach campaign. Your task is to classify an employer's
reply to a talent outreach email.
Always respond with valid JSON only.
No explanation, no markdown, no extra text.

User:
Classify the following employer reply.

Original Email We Sent:
Subject: {original_subject}
Body: {original_body}

Employer Reply:
From: {reply_from}
Subject: {reply_subject}
Body: {reply_body}

Classify the reply into exactly one of these categories:

Interested:
- Employer wants to learn more
- Employer asks to schedule a call or meeting
- Employer asks for student CVs or profiles
- Employer expresses enthusiasm or positive interest

Scheduled:
- Employer confirms a specific meeting time or date
- Employer accepts one of the proposed time slots
- Employer says "confirmed" or "see you then" or similar

Not Interested:
- Employer clearly declines
- Employer says they are not hiring
- Employer asks to be removed from contact list

Undecided:
- Auto-reply or out of office message
- Vague or unclear response
- Employer asks a question without showing clear interest or disinterest
- Employer refers to another contact person
- Any response that does not clearly fit above categories

Return a JSON object:
{
  "classification": "Interested | Scheduled | Not Interested | Undecided",
  "confidence": 0.0 to 1.0,
  "reasoning": "one sentence explanation of why this classification was chosen"
}
```

---

## 10. Confidence Score Logic

```python
def evaluate_classification(llm_result: dict) -> dict:

    classification = llm_result["classification"]
    confidence     = llm_result["confidence"]

    # Low confidence → override to Undecided
    if confidence < 0.75:
        return {
            "classification" : "Undecided",
            "confidence"     : confidence,
            "reasoning"      : f"Low confidence ({confidence}) — "
                               f"original classification was "
                               f"{classification}. Flagged for human review."
        }

    return llm_result
```

---

## 11. Examples

### Example 1 — Interested
```
Reply body:
"Thank you for reaching out. This sounds interesting —
we are currently hiring Data Engineers and would love
to learn more about your graduates. Can we schedule
a call next week?"

LLM Output:
{
  "classification": "Interested",
  "confidence": 0.97,
  "reasoning": "Employer explicitly expresses interest and requests a call."
}

Action: Trigger Scheduling Agent immediately
```

---

### Example 2 — Not Interested
```
Reply body:
"Thank you for your email. We are not currently looking
to hire externally as we have a hiring freeze in place.
Please do not contact us again."

LLM Output:
{
  "classification": "Not Interested",
  "confidence": 0.95,
  "reasoning": "Employer explicitly declines and requests no further contact."
}

Action: Mark company as closed — no further outreach
```

---

### Example 3 — Undecided (Auto-reply)
```
Reply body:
"I am currently out of the office until July 15th.
For urgent matters please contact my colleague at
sara@company.com"

LLM Output:
{
  "classification": "Undecided",
  "confidence": 0.88,
  "reasoning": "Auto-reply — sender is out of office. No clear interest or disinterest expressed."
}

Action: Flag for human review
Human decides: keep monitoring / contact sara@company.com
```

---

### Example 4 — Low Confidence Override
```
Reply body:
"Thank you."

LLM Output:
{
  "classification": "Interested",
  "confidence": 0.41,
  "reasoning": "Reply is too vague to classify with confidence."
}

After confidence check:
{
  "classification": "Undecided",
  "confidence": 0.41,
  "reasoning": "Low confidence (0.41) — original classification was Interested.
                Flagged for human review."
}

Action: Flag for human review
```

---

## 12. Dashboard — Human Review Queue

When classification is Undecided — human sees it in dashboard:

```
┌─────────────────────────────────────────────────────────┐
│  ⚠️  REPLIES NEEDING REVIEW — 2                         │
├─────────────────────────────────────────────────────────┤
│  TAM Development Co.                                    │
│  "Thank you."                                           │
│  Confidence: 0.41 — too vague                           │
│  [✅ Interested]  [❌ Not Interested]  [⏸️ Keep Monitoring] │
├─────────────────────────────────────────────────────────┤
│  Parsons                                                │
│  "I am out of office until July 15th..."               │
│  Auto-reply detected                                    │
│  [✅ Interested]  [❌ Not Interested]  [⏸️ Keep Monitoring] │
└─────────────────────────────────────────────────────────┘
```

Human selects action → system proceeds accordingly.

---

## 13. Edge Cases

| Edge Case | Handling |
|---|---|
| Reply body is empty | Classify as Undecided — flag for human |
| Reply is in Arabic | LLM handles Arabic — classify normally |
| Reply is very long | Truncate to first 1000 chars before sending to LLM |
| LLM returns invalid JSON | Retry once — if still invalid classify as Undecided |
| LLM confidence exactly 0.75 | Treated as high confidence — use classification |
| Human marks Undecided as Interested | Trigger Scheduling Agent manually |
| Human marks Undecided as Not Interested | Mark company closed |
| Same company sends multiple replies | Each reply classified independently |

---

## 14. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `replies` — new reply to classify
- `emails` — original sent email for context

This agent writes to:
- `replies` — classification, confidence, classified_at, llm_model_used
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `last_updated` | After each classification |

---

## 15. Pseudocode

```python
def response_classification_agent(reply_id: int):

    # Load reply and original email
    reply    = db.get_reply(reply_id)
    original = db.get_original_email(reply.email_id)

    # Build prompt
    prompt = build_classification_prompt(reply, original)

    # Call LLM
    try:
        response = call_llm(prompt)
        result   = parse_json(response)
    except:
        # Retry once
        response = call_llm(prompt)
        result   = parse_json(response)
        if not result:
            result = {
                "classification": "Undecided",
                "confidence"    : 0.0,
                "reasoning"     : "LLM failed — defaulting to Undecided"
            }

    # Evaluate confidence
    result = evaluate_classification(result)

    # Save classification
    db.save_classification(
        reply_id        = reply_id,
        classification  = result["classification"],
        confidence      = result["confidence"],
        reasoning       = result["reasoning"],
        classified_at   = datetime.now(),
        llm_model_used  = LLM_MODEL
    )

    # Take action
    if result["classification"] == "Interested":
        trigger_scheduling_agent(reply_id)

    elif result["classification"] == "Scheduled":
        db.mark_meeting_confirmed(reply.campaign_id, reply.company_name)

    elif result["classification"] == "Not Interested":
        db.mark_company_closed(
            campaign_id  = reply.campaign_id,
            company_name = reply.company_name
        )

    elif result["classification"] == "Undecided":
        db.flag_for_human_review(reply_id)

    db.update_campaign_progress(reply.campaign_id)
```

---

## 16. Connection to Next Agents

```
Classification: Interested
        ↓
Scheduling Agent triggered immediately

Classification: Not Interested
        ↓
Company marked closed — no further agents

Classification: Undecided
        ↓
Human reviews in dashboard
Human decision triggers appropriate next agent
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
