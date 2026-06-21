import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from shared import db

try:
    from shared.llm import call_llm
except Exception:
    call_llm = None


def calculate_days_since(sent_at) -> int:
    if not sent_at:
        return 0

    if isinstance(sent_at, str):
        try:
            sent_at = datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        except Exception:
            return 0

    now = datetime.now(timezone.utc)

    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    return (now - sent_at).days


def build_followup_prompt(email: dict, days_since_sent: int) -> str:
    return f"""
You are a professional recruitment coordinator writing a short follow-up email.

Original Email:
Subject: {email.get("subject")}
Body:
{email.get("body")}

Company: {email.get("company_name")}
Contact Name: {email.get("recipient_name")}
Days Since Original Email: {days_since_sent}

Requirements:
- Subject must be: "Re: {email.get("subject")}"
- Body under 80 words
- Reference original email naturally
- Restate value briefly in one sentence
- Same call to action as original
- Polite and professional tone
- Never sound pushy or desperate
- English only
- Return valid JSON only

Return JSON:
{{
  "subject": "Re: {email.get("subject")}",
  "body": "..."
}}
"""


def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def generate_fallback_followup(email: dict) -> Dict[str, str]:
    contact_name = email.get("recipient_name") or "there"
    subject = f"Re: {email.get('subject')}"

    body = f"""Dear {contact_name},

I wanted to follow up on my previous email regarding our graduates who may align with your hiring needs at {email.get("company_name")}.

We would be happy to share more details or arrange a short introductory call if useful.

Best regards,
TalentBridge AI Team"""

    return {
        "subject": subject,
        "body": body
    }


def generate_followup_email(email: dict, days_since_sent: int) -> Dict[str, str]:
    if call_llm:
        prompt = build_followup_prompt(email, days_since_sent)

        try:
            response = call_llm(prompt)
            parsed = parse_json_response(response)

            if parsed and parsed.get("subject") and parsed.get("body"):
                return {
                    "subject": parsed["subject"],
                    "body": parsed["body"]
                }
        except Exception:
            pass

    return generate_fallback_followup(email)


def should_generate_followup(email: dict, campaign: dict) -> tuple[bool, str, int]:
    email_id = email["email_id"]

    if db.reply_exists_for_email(email_id):
        return False, "Reply already exists", 0

    existing_followup = db.get_followup_for_email(email_id)

    days_since_sent = calculate_days_since(email.get("sent_at"))
    followup_days = campaign.get("followup_days") or 3

    if existing_followup:
        return False, "Follow-up already exists", days_since_sent

    if days_since_sent < followup_days:
        return False, f"Not time yet: {days_since_sent}/{followup_days} days", days_since_sent

    return True, "Follow-up needed", days_since_sent


def process_email_for_followup(email: dict, campaign: dict) -> Dict[str, Any]:
    should_followup, reason, days_since_sent = should_generate_followup(email, campaign)

    if not should_followup:
        return {
            "email_id": email["email_id"],
            "company_name": email.get("company_name"),
            "status": "skipped",
            "reason": reason
        }

    followup = generate_followup_email(email, days_since_sent)

    saved_email = db.save_followup_email(
        campaign_id=email["campaign_id"],
        recipient_email=email["recipient_email"],
        recipient_name=email.get("recipient_name"),
        company_name=email.get("company_name"),
        subject=followup["subject"],
        body=followup["body"]
    )

    followup_email_id = saved_email["email_id"] if saved_email else None

    saved_followup = db.save_followup_record(
        campaign_id=email["campaign_id"],
        email_id=email["email_id"],
        company_name=email.get("company_name"),
        followup_email_id=followup_email_id,
        reason="No Reply",
        status="Pending"
    )

    db.touch_campaign(email["campaign_id"])

    return {
        "email_id": email["email_id"],
        "company_name": email.get("company_name"),
        "status": "followup_created",
        "days_since_sent": days_since_sent,
        "followup_email_id": followup_email_id,
        "followup_id": saved_followup.get("followup_id") if saved_followup else None
    }


def followup_agent(campaign_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Agent 10 MVP:
    - Finds sent Employer Outreach emails.
    - Skips if reply exists.
    - Skips if follow-up already exists.
    - Checks campaign.followup_days.
    - Creates follow-up email in emails table with Pending Approval.
    - Creates follow_ups record.
    """

    if campaign_id:
        campaigns = [db.fetchone(
            """
            SELECT campaign_id, campaign_name, followup_days, status
            FROM campaigns
            WHERE campaign_id = %s
            """,
            (campaign_id,)
        )]
        campaigns = [c for c in campaigns if c]
    else:
        campaigns = db.get_active_campaigns_for_followups()

    results = []

    for campaign in campaigns:
        emails = db.get_sent_employer_emails(campaign["campaign_id"])

        campaign_results = []

        for email in emails:
            result = process_email_for_followup(email, campaign)
            campaign_results.append(result)

        results.append({
            "campaign_id": campaign["campaign_id"],
            "emails_checked": len(emails),
            "results": campaign_results
        })

    return {
        "status": "complete",
        "campaigns_processed": len(campaigns),
        "results": results
    }


if __name__ == "__main__":
    output = followup_agent(campaign_id=2)
    print(output)