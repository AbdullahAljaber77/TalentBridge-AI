import json
from typing import Dict, Any, Optional

from shared import db

try:
    from shared.llm import call_llm, DEFAULT_MODEL
except Exception:
    call_llm = None
    DEFAULT_MODEL = "unknown"


VALID_CLASSIFICATIONS = [
    "Interested",
    "Scheduled",
    "Not Interested",
    "Undecided"
]



def build_classification_prompt(reply: dict, original_email: dict) -> str:
    return f"""
You are an expert email response analyst for a recruitment outreach campaign.
Your task is to classify an employer's reply.

Always respond with valid JSON only.
No markdown. No explanation outside JSON.

Original Email We Sent:
Subject: {original_email.get("subject")}
Body:
{original_email.get("body")}

Employer Reply:
From: {reply.get("reply_from")}
Subject: {reply.get("reply_subject")}
Body:
{reply.get("reply_body")}

Classify the reply into exactly one category:

Interested:
- Employer wants to learn more
- Employer asks to schedule a call or meeting
- Employer asks for student CVs or profiles
- Employer expresses positive interest

Scheduled:
- Employer confirms a specific meeting time or date
- Employer accepts a proposed time slot
- Employer says confirmed, see you then, or similar

Not Interested:
- Employer clearly declines
- Employer says they are not hiring
- Employer asks to be removed

Undecided:
- Auto-reply or out of office
- Vague or unclear response
- Employer asks a question without clear interest
- Employer refers to another contact
- Any response that does not clearly fit above

Return JSON only:
{{
  "classification": "Interested | Scheduled | Not Interested | Undecided",
  "confidence": 0.0,
  "reasoning": "one sentence explanation"
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


def keyword_fallback_classification(reply_body: str) -> Dict[str, Any]:
    body = (reply_body or "").lower()

    scheduled_keywords = [
        "confirmed",
        "see you then",
        "that works",
        "works for me",
        "calendar invite",
        "meeting confirmed"
    ]

    interested_keywords = [
        "interested",
        "learn more",
        "schedule",
        "call",
        "meeting",
        "send cv",
        "send profiles",
        "share profiles",
        "sounds good",
        "would like to know more"
    ]

    not_interested_keywords = [
        "not interested",
        "not hiring",
        "no longer hiring",
        "hiring freeze",
        "remove me",
        "do not contact",
        "no need",
        "decline"
    ]

    auto_reply_keywords = [
        "out of office",
        "automatic reply",
        "auto-reply",
        "on vacation",
        "away from office"
    ]

    if any(keyword in body for keyword in scheduled_keywords):
        return {
            "classification": "Scheduled",
            "confidence": 0.85,
            "reasoning": "Keyword fallback detected a confirmed meeting response."
        }

    if any(keyword in body for keyword in not_interested_keywords):
        return {
            "classification": "Not Interested",
            "confidence": 0.85,
            "reasoning": "Keyword fallback detected a clear negative response."
        }

    if any(keyword in body for keyword in auto_reply_keywords):
        return {
            "classification": "Undecided",
            "confidence": 0.9,
            "reasoning": "Keyword fallback detected an auto-reply or out-of-office message."
        }

    if any(keyword in body for keyword in interested_keywords):
        return {
            "classification": "Interested",
            "confidence": 0.8,
            "reasoning": "Keyword fallback detected interest or a request to continue."
        }

    return {
        "classification": "Undecided",
        "confidence": 0.5,
        "reasoning": "Reply is too vague to classify confidently."
    }


def normalize_classification(value: str) -> str:
    if not value:
        return "Undecided"

    value = value.strip()

    for valid in VALID_CLASSIFICATIONS:
        if value.lower() == valid.lower():
            return valid

    lowered = value.lower()

    if "interested" in lowered and "not" not in lowered:
        return "Interested"

    if "scheduled" in lowered or "confirmed" in lowered:
        return "Scheduled"

    if "not" in lowered or "negative" in lowered:
        return "Not Interested"

    return "Undecided"


def evaluate_classification(result: Dict[str, Any]) -> Dict[str, Any]:
    classification = normalize_classification(result.get("classification"))
    confidence = result.get("confidence", 0.0)

    try:
        confidence = float(confidence)
    except Exception:
        confidence = 0.0

    confidence = max(0.0, min(confidence, 1.0))

    reasoning = result.get("reasoning") or "No reasoning provided."

    if confidence < 0.75:
        return {
            "classification": "Undecided",
            "confidence": confidence,
            "reasoning": (
                f"Low confidence ({confidence}). Original classification was "
                f"{classification}. Flagged for human review."
            )
        }

    return {
        "classification": classification,
        "confidence": confidence,
        "reasoning": reasoning
    }


def classify_reply(reply: dict, original_email: dict) -> Dict[str, Any]:
    if call_llm:
        prompt = build_classification_prompt(reply, original_email)

        try:
            response = call_llm(prompt)
            parsed = parse_json_response(response)

            if parsed:
                result = evaluate_classification(parsed)
                result["model_used"] = DEFAULT_MODEL
                return result
        except Exception:
            pass

    fallback = keyword_fallback_classification(reply.get("reply_body", ""))
    result = evaluate_classification(fallback)
    result["model_used"] = "keyword-fallback"
    return result


def take_action_after_classification(reply: dict, result: Dict[str, Any]) -> Dict[str, Any]:
    classification = result["classification"]

    if classification == "Interested":
        # Scheduling Agent يشتغل لاحقاً على الردود المهتمة
        return {
            "next_action": "trigger_scheduling_agent",
            "message": "Employer is interested. Scheduling Agent should be triggered."
        }

    if classification == "Scheduled":
        return {
            "next_action": "mark_meeting_confirmed",
            "message": "Employer appears to have confirmed a meeting slot."
        }

    if classification == "Not Interested":
        closed = db.mark_company_closed(
            campaign_id=reply["campaign_id"],
            company_name=reply["company_name"]
        )
        return {
            "next_action": "company_closed",
            "message": "Employer is not interested. Company marked as closed for MVP.",
            "result": closed
        }

    db.flag_reply_for_human_review(reply["reply_id"])
    return {
        "next_action": "human_review",
        "message": "Reply is undecided or low confidence. Human review required."
    }


def response_classification_agent(reply_id: int) -> Dict[str, Any]:
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

    result = classify_reply(reply, original_email)

    saved = db.save_reply_classification(
        reply_id=reply_id,
        classification=result["classification"],
        confidence=result["confidence"],
        llm_model_used=result.get("model_used", "unknown")
    )

    action = take_action_after_classification(reply, result)

    db.touch_campaign(reply["campaign_id"])

    return {
        "status": "complete",
        "reply_id": reply_id,
        "classification": result["classification"],
        "confidence": result["confidence"],
        "reasoning": result["reasoning"],
        "saved": saved,
        "action": action
    }


if __name__ == "__main__":
    output = response_classification_agent(reply_id=1)
    print(output)