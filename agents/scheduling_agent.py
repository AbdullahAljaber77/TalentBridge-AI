import json
from typing import Dict, Any, List, Optional

from shared import db

try:
    from shared.llm import call_llm
except Exception:
    call_llm = None


def build_scheduling_prompt(
    reply: dict,
    original_email: dict,
    contact: dict,
    strategy: dict,
    time_slots: List[str],
    meeting_format: str,
    duration: str
) -> str:
    return f"""
You are a professional recruitment coordinator writing a meeting scheduling email.
Be warm, professional, and clear.
Always respond with valid JSON only.

Company: {reply.get("company_name")}
Contact Name: {contact.get("contact_name") if contact else reply.get("reply_from")}
Their Reply:
{reply.get("reply_body")}

Original Email Subject:
{original_email.get("subject")}

Tone from original:
{strategy.get("tone") if strategy else "Professional"}

Available Time Slots:
{time_slots}

Meeting Format: {meeting_format}
Duration: {duration}

Requirements:
- Subject: "Re: {original_email.get("subject")}"
- Thank employer for their interest
- Propose the time slots clearly
- Mention meeting format and duration
- Ask employer to confirm preferred slot
- English only
- Under 150 words body

Return JSON only:
{{
  "subject": "Re: {original_email.get("subject")}",
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


def generate_fallback_scheduling_email(
    reply: dict,
    original_email: dict,
    contact: dict,
    time_slots: List[str],
    meeting_format: str,
    duration: str
) -> Dict[str, str]:
    contact_name = (
        contact.get("contact_name")
        if contact and contact.get("contact_name")
        else "there"
    )

    subject = f"Re: {original_email.get('subject')}"

    slots_text = "\n".join([f"• {slot}" for slot in time_slots])

    body = f"""Dear {contact_name},

Thank you for your interest. We would be happy to schedule a {duration} {meeting_format} to discuss the opportunity further.

Here are a few available time slots:

{slots_text}

Please let us know which option works best for you, and we will confirm the meeting details.

Best regards,
TalentBridge AI Team"""

    return {
        "subject": subject,
        "body": body
    }


def generate_scheduling_email(
    reply: dict,
    original_email: dict,
    contact: dict,
    strategy: dict,
    time_slots: List[str],
    meeting_format: str,
    duration: str
) -> Dict[str, str]:
    if call_llm:
        prompt = build_scheduling_prompt(
            reply=reply,
            original_email=original_email,
            contact=contact,
            strategy=strategy,
            time_slots=time_slots,
            meeting_format=meeting_format,
            duration=duration
        )

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

    return generate_fallback_scheduling_email(
        reply=reply,
        original_email=original_email,
        contact=contact,
        time_slots=time_slots,
        meeting_format=meeting_format,
        duration=duration
    )


def validate_human_input(
    time_slots: List[str],
    meeting_format: str,
    duration: str
) -> tuple[bool, str]:
    if not time_slots:
        return False, "At least one time slot is required."

    clean_slots = [slot for slot in time_slots if str(slot).strip()]

    if not clean_slots:
        return False, "Time slots cannot be empty."

    if not meeting_format:
        return False, "Meeting format is required."

    if not duration:
        return False, "Duration is required."

    return True, "Valid"


def scheduling_agent(
    reply_id: int,
    time_slots: List[str],
    meeting_format: str = "Google Meet",
    duration: str = "30 minutes"
) -> Dict[str, Any]:
    """
    Agent 11 MVP:
    - Triggered when reply is Interested.
    - Human provides available slots.
    - Generates scheduling email.
    - Saves email to approval queue.
    - Saves meeting record as Proposed.
    """

    valid, message = validate_human_input(time_slots, meeting_format, duration)

    if not valid:
        return {
            "status": "failed_validation",
            "reply_id": reply_id,
            "reason": message
        }

    reply = db.get_reply_by_id(reply_id)

    if not reply:
        return {
            "status": "not_found",
            "reply_id": reply_id,
            "reason": "Reply not found."
        }

    original_email = db.get_original_email(reply["email_id"])

    if not original_email:
        return {
            "status": "missing_original_email",
            "reply_id": reply_id,
            "email_id": reply["email_id"]
        }

    contact = db.get_contact_by_company(reply["company_name"])

    if not contact:
        return {
            "status": "missing_contact",
            "reply_id": reply_id,
            "company_name": reply["company_name"]
        }

    strategy = db.get_email_strategy(
        campaign_id=reply["campaign_id"],
        company_name=reply["company_name"]
    )

    scheduling_email = generate_scheduling_email(
        reply=reply,
        original_email=original_email,
        contact=contact,
        strategy=strategy,
        time_slots=time_slots,
        meeting_format=meeting_format,
        duration=duration
    )

    try:
        saved = db.save_scheduling_email_and_meeting(
            campaign_id=reply["campaign_id"],
            reply_id=reply_id,
            company_name=reply["company_name"],
            contact_name=contact.get("contact_name"),
            contact_email=contact["contact_email"],
            subject=scheduling_email["subject"],
            body=scheduling_email["body"],
            proposed_slots=time_slots,
            contact_id=contact.get("contact_id"),
        )
    except Exception as exc:
        return {
            "status": "failed_to_save",
            "reply_id": reply_id,
            "company_name": reply["company_name"],
            "reason": f"Atomic save failed, no partial rows written: {exc}",
        }

    scheduling_email_id = saved["email_id"]
    meeting_id = saved["meeting_id"]

    db.touch_campaign(reply["campaign_id"])

    return {
        "status": "complete",
        "reply_id": reply_id,
        "campaign_id": reply["campaign_id"],
        "company_name": reply["company_name"],
        "scheduling_email_id": scheduling_email_id,
        "meeting_id": meeting_id,
        "subject": scheduling_email["subject"],
        "body": scheduling_email["body"]
    }


def confirm_meeting(
    campaign_id: int,
    company_name: str,
    confirmed_slot: str
) -> Dict[str, Any]:
    result = db.mark_meeting_confirmed(
        campaign_id=campaign_id,
        company_name=company_name,
        confirmed_slot=confirmed_slot
    )

    if not result:
        return {
            "status": "not_found",
            "campaign_id": campaign_id,
            "company_name": company_name
        }

    return {
        "status": "confirmed",
        "campaign_id": campaign_id,
        "company_name": company_name,
        "confirmed_slot": confirmed_slot,
        "meeting": result
    }


if __name__ == "__main__":
    output = scheduling_agent(
        reply_id=1,
        time_slots=[
            "Monday, June 10 — 10:00 AM",
            "Tuesday, June 11 — 2:00 PM",
            "Wednesday, June 12 — 11:00 AM"
        ],
        meeting_format="Google Meet",
        duration="30 minutes"
    )
    print(json.dumps(output, indent=2, default=str))