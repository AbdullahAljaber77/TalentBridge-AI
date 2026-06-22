from typing import Dict, Any, Optional

from shared import db


APPROVAL_REASONS = [
    "Wrong contact",
    "Poor email quality",
    "Company not relevant",
    "Student mismatch",
    "Duplicate",
    "Other"
]


def validate_email_for_approval(email: dict) -> tuple[bool, str]:
    if not email:
        return False, "Email not found"

    if not email.get("recipient_email"):
        return False, "Recipient email is missing"

    if not email.get("subject"):
        return False, "Subject is missing"

    if not email.get("body"):
        return False, "Body is missing"

    if len(email["body"].strip()) < 20:
        return False, "Body is too short"

    return True, "Valid"


def send_email_simulated(email: dict) -> bool:
    """
    MVP simulated sending.
    Real Gmail/SendGrid will be added later.
    """
    print("\n[SIMULATED SEND]")
    print(f"To: {email.get('recipient_email')}")
    print(f"Subject: {email.get('subject')}")
    print("-" * 60)
    print(email.get("body"))
    print("-" * 60)

    return True


def load_approval_queue(campaign_id: int) -> Dict[str, Any]:
    emails = db.get_pending_emails(campaign_id)

    return {
        "status": "loaded",
        "campaign_id": campaign_id,
        "pending_count": len(emails),
        "emails": emails
    }


def approve_and_send_email(
    email_id: int,
    approved_by: str = "Human Reviewer",
    simulate_send: bool = True
) -> Dict[str, Any]:
    email = db.get_email_by_id(email_id)

    is_valid, message = validate_email_for_approval(email)

    if not is_valid:
        db.mark_email_failed(email_id, message)
        return {
            "status": "failed validation",
            "email_id": email_id,
            "reason": message
        }

    approved = db.approve_email(email_id, approved_by)
    db.increment_emails_approved(email["campaign_id"])

    if simulate_send:
        success = send_email_simulated(email)
    else:
        # Stretch goal: real email API later
        success = send_email_simulated(email)

    if success:
        sent = db.mark_email_sent(email_id)
        db.increment_emails_sent(email["campaign_id"])

        return {
            "status": "sent",
            "email_id": email_id,
            "approved": approved,
            "sent": sent
        }

    failed = db.mark_email_failed(email_id, "Simulated sending failed")

    return {
        "status": "failed sending",
        "email_id": email_id,
        "failed": failed
    }


def edit_email(
    email_id: int,
    new_subject: Optional[str] = None,
    new_body: Optional[str] = None
) -> Dict[str, Any]:
    email = db.get_email_by_id(email_id)

    if not email:
        return {
            "status": "not found",
            "email_id": email_id
        }

    subject = new_subject if new_subject is not None else email["subject"]
    body = new_body if new_body is not None else email["body"]

    if not subject.strip():
        return {
            "status": "failed validation",
            "reason": "Subject cannot be empty"
        }

    if not body.strip():
        return {
            "status": "failed validation",
            "reason": "Body cannot be empty"
        }

    updated = db.update_email_content(email_id, subject, body)

    return {
        "status": "edited",
        "email_id": email_id,
        "updated": updated
    }

# Modify in the UX/UI to allow selecting from predefined reasons or entering a custom reason for rejection
def reject_email(
    email_id: int,
    reason: str = "Other"
) -> Dict[str, Any]:
    if reason not in APPROVAL_REASONS:
        reason = f"Other: {reason}"

    rejected = db.reject_email(email_id, reason)

    return {
        "status": "rejected",
        "email_id": email_id,
        "rejection_reason": reason,
        "result": rejected
    }


def review_email_action(
    email_id: int,
    action: str,
    approved_by: str = "Human Reviewer",
    rejection_reason: str = "Other",
    new_subject: Optional[str] = None,
    new_body: Optional[str] = None
) -> Dict[str, Any]:
    action = action.lower().strip()

    if action == "approve":
        return approve_and_send_email(
            email_id=email_id,
            approved_by=approved_by,
            simulate_send=True
        )

    if action == "edit":
        return edit_email(
            email_id=email_id,
            new_subject=new_subject,
            new_body=new_body
        )

    if action == "reject":
        return reject_email(
            email_id=email_id,
            reason=rejection_reason
        )

    return {
        "status": "invalid action",
        "email_id": email_id,
        "allowed_actions": ["approve", "edit", "reject"]
    }

def finalize_execution(campaign_id: int) -> Dict[str, Any]:
    """
    Called when the human finishes reviewing the approval queue.
    Marks the campaign 'emails sent' — the handoff to the monitoring phase
    (Agents 08-12). This is NOT campaign completion.
    """
    remaining = db.get_pending_emails(campaign_id)
    db.update_campaign_status(campaign_id, "emails sent")

    return {
        "status": "emails sent",
        "campaign_id": campaign_id,
        "pending_remaining": len(remaining),  # warns if finalized early
    }


def campaign_execution_agent(campaign_id: int) -> Dict[str, Any]:
    """
    MVP:
    - Loads pending emails.
    - Does not auto-approve.
    - Returns approval queue for UI/Frontend.
    """
    db.update_campaign_status(campaign_id, "awaiting approval")

    queue = load_approval_queue(campaign_id)

    return {
        "status": "awaiting human review",
        "campaign_id": campaign_id,
        "pending_count": queue["pending_count"],
        "emails": queue["emails"]
    }


if __name__ == "__main__":
    output = campaign_execution_agent(campaign_id=2)
    print(output)