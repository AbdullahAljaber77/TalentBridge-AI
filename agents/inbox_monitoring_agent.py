"""
TalentBridge AI — Agent 08: Inbox Monitoring Agent
==================================================

The first BACKGROUND agent in the system.

What it does (one cycle):
    1. Fetch new inbox replies for a campaign (pluggable source).
    2. For each reply: extract X-TalentBridge tracking headers.
    3. Match the reply to its campaign_id + email_id
       (headers first, sender-email fallback, else log as unmatched and skip).
    4. Skip duplicates (same sender + subject within 1 hour).
    5. Save the reply to the `replies` table with
       classification = "Pending Classification".
    6. Increment campaigns.replies_received and touch last_updated.
    7. Immediately trigger Agent 09 (Response Classification) for that reply.

Design notes:
    * This module separates the *cycle* (`run_inbox_monitoring_cycle`) from the
      *scheduler* (`start_inbox_monitor`). The cycle is a single pass and is the
      unit that APScheduler fires on an interval. There is NO `while True` loop
      here — that keeps the logic fully testable and non-blocking.
    * No raw SQL lives in this file. Every DB touch goes through `shared.db`.
    * The classification agent is triggered through a thin, lazily-imported
      wrapper so this module imports cleanly even if downstream deps are absent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared import db

# call_llm_json is only needed for the (optional) LLM inbox source.
# Mirror the resilient import pattern used by Agent 09 so this module stays
# importable even when the LLM layer cannot load (e.g. in unit tests).
try:
    from shared.llm import call_llm_json
except Exception:  # pragma: no cover - defensive import guard
    call_llm_json = None  # type: ignore[assignment]


logger = logging.getLogger("talentbridge.agents.inbox_monitor")

# ─────────────────────────────────────────────
# Configuration (module-level — swap in one line)
# ─────────────────────────────────────────────

# Active inbox source: "mock" | "llm" | "gmail"
INBOX_SOURCE: str = "mock"

# Fallback interval if a campaign has no inbox_check_minutes configured.
DEFAULT_CHECK_MINUTES: int = 5

# Duplicate window — a reply with the same sender+subject inside this many
# hours is treated as already processed.
DUPLICATE_WINDOW_HOURS: int = 1

# Value written on insert. Agent 08 never sets the final classification.
PENDING_CLASSIFICATION: str = "Pending Classification"

# Safety cap on how many mock replies to synthesise per cycle.
MAX_MOCK_REPLIES_PER_CYCLE: int = 50

# Tracking-header key names — must match what Agent 07 writes on send.
HEADER_CAMPAIGN_ID: str = "X-TalentBridge-Campaign-ID"
HEADER_EMAIL_ID: str = "X-TalentBridge-Email-ID"


# ─────────────────────────────────────────────
# Time helpers
# ─────────────────────────────────────────────

def _utc_now_naive() -> datetime:
    """
    Current UTC time as a naive datetime.

    The `replies.received_at` column is `TIMESTAMP` (without time zone) and the
    schema requires UTC storage. We compute in timezone-aware UTC, then drop the
    tzinfo so psycopg2 hands Postgres a clean UTC value with no implicit
    session-timezone conversion.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _coerce_received_at(value: Any) -> datetime:
    """Return a naive-UTC datetime for any reasonable `received_at` input."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    return _utc_now_naive()


# ─────────────────────────────────────────────
# Tool 1 — fetch_inbox (pluggable source)
# ─────────────────────────────────────────────

def fetch_inbox(campaign_id: int) -> List[Dict[str, Any]]:
    """
    Fetch new inbound replies for one campaign.

    Returns a list of normalised dicts, each shaped as:
        {
            "from":        str,    # employer sender address
            "subject":     str | None,
            "body":        str,
            "headers":     dict,   # X-TalentBridge-* tracking headers
            "received_at": datetime (naive UTC),
        }

    The active strategy is chosen by the module-level `INBOX_SOURCE` constant.
    """
    if INBOX_SOURCE == "mock":
        return _fetch_inbox_mock(campaign_id)
    if INBOX_SOURCE == "llm":
        return _fetch_inbox_llm(campaign_id)
    if INBOX_SOURCE == "gmail":
        return _fetch_inbox_gmail(campaign_id)

    logger.warning("Unknown INBOX_SOURCE=%r — returning empty inbox.", INBOX_SOURCE)
    return []


def _headers_for(sent_email: Dict[str, Any]) -> Dict[str, str]:
    """
    Return correct tracking headers for a sent email.

    Prefer the JSONB `tracking_headers` already written by Agent 07; if absent
    (older rows), rebuild them from the email's own ids so matching still works.
    """
    raw = sent_email.get("tracking_headers")

    # psycopg2 decodes jsonb to dict; guard the rare case it arrives as text.
    if isinstance(raw, str):
        import json
        try:
            raw = json.loads(raw)
        except Exception:
            raw = None

    if isinstance(raw, dict) and raw.get(HEADER_CAMPAIGN_ID) and raw.get(HEADER_EMAIL_ID):
        return {
            HEADER_CAMPAIGN_ID: str(raw[HEADER_CAMPAIGN_ID]),
            HEADER_EMAIL_ID: str(raw[HEADER_EMAIL_ID]),
        }

    return {
        HEADER_CAMPAIGN_ID: str(sent_email.get("campaign_id")),
        HEADER_EMAIL_ID: str(sent_email.get("email_id")),
    }


# Deterministic mock bodies — variety without unpredictability (good for demos).
_MOCK_TEMPLATES = [
    ("Interested",
     "Thank you for reaching out. We are interested in learning more about your "
     "graduates. Could we schedule a short call this week?"),
    ("Neutral",
     "Thanks for your email. Could you share a few sample profiles before we "
     "decide on next steps?"),
    ("Not interested",
     "We appreciate the note but are not hiring at the moment. We'll keep your "
     "details on file."),
    ("Auto-reply",
     "Automatic reply: I am currently out of office and will respond on my return."),
]


def _fetch_inbox_mock(campaign_id: int) -> List[Dict[str, Any]]:
    """
    Build mock replies FROM real sent emails so foreign keys are always valid.

    Only emails that do not already have a reply are answered, which makes the
    cycle naturally idempotent across runs.
    """
    try:
        sent_emails = db.get_sent_emails_for_inbox(campaign_id) or []
    except Exception as exc:
        logger.error("Mock inbox: failed to load sent emails for campaign %s: %s",
                     campaign_id, exc)
        return []

    inbox: List[Dict[str, Any]] = []
    for idx, sent in enumerate(sent_emails):
        if len(inbox) >= MAX_MOCK_REPLIES_PER_CYCLE:
            break

        email_id = sent.get("email_id")
        try:
            if email_id is not None and db.reply_exists_for_email(email_id):
                continue  # already answered — keep the mock idempotent
        except Exception as exc:
            logger.warning("Mock inbox: reply_exists check failed for email %s: %s",
                           email_id, exc)

        _, body = _MOCK_TEMPLATES[idx % len(_MOCK_TEMPLATES)]
        subject = sent.get("subject") or ""
        inbox.append({
            "from": sent.get("recipient_email") or "unknown@unknown.com",
            "subject": f"Re: {subject}" if subject else "Re:",
            "body": body,
            "headers": _headers_for(sent),
            "received_at": _utc_now_naive(),
        })

    return inbox


def _fetch_inbox_llm(campaign_id: int) -> List[Dict[str, Any]]:
    """
    LLM-generated realistic replies, still anchored to real sent emails and
    carrying correct tracking headers. Falls back to a mock body per-email if
    the LLM layer is unavailable or errors.
    """
    try:
        sent_emails = db.get_sent_emails_for_inbox(campaign_id) or []
    except Exception as exc:
        logger.error("LLM inbox: failed to load sent emails for campaign %s: %s",
                     campaign_id, exc)
        return []

    inbox: List[Dict[str, Any]] = []
    for idx, sent in enumerate(sent_emails):
        if len(inbox) >= MAX_MOCK_REPLIES_PER_CYCLE:
            break

        email_id = sent.get("email_id")
        try:
            if email_id is not None and db.reply_exists_for_email(email_id):
                continue
        except Exception as exc:
            logger.warning("LLM inbox: reply_exists check failed for email %s: %s",
                           email_id, exc)

        body = _generate_llm_reply_body(sent) or _MOCK_TEMPLATES[idx % len(_MOCK_TEMPLATES)][1]
        subject = sent.get("subject") or ""
        inbox.append({
            "from": sent.get("recipient_email") or "unknown@unknown.com",
            "subject": f"Re: {subject}" if subject else "Re:",
            "body": body,
            "headers": _headers_for(sent),
            "received_at": _utc_now_naive(),
        })

    return inbox


def _generate_llm_reply_body(sent_email: Dict[str, Any]) -> Optional[str]:
    """Ask the LLM for one realistic employer reply body. Returns None on failure."""
    if call_llm_json is None:
        return None

    prompt = (
        "Generate a realistic employer reply to a recruitment outreach email.\n"
        f"Company: {sent_email.get('company_name')}\n"
        f"Original subject: {sent_email.get('subject')}\n"
        "Randomly choose one response type using this distribution:\n"
        "  Interested (40%) | Neutral/needs more info (30%) | "
        "Not interested (20%) | Auto-reply (10%)\n"
        'Return JSON only: {"body": "...", "response_type": "..."}'
    )
    try:
        result = call_llm_json(prompt, required_keys=["body", "response_type"])
        body = (result or {}).get("body")
        return body if isinstance(body, str) and body.strip() else None
    except Exception as exc:
        logger.warning("LLM inbox: generation failed (%s) — using fallback body.", exc)
        return None


def _fetch_inbox_gmail(campaign_id: int) -> List[Dict[str, Any]]:
    """
    STUB — Option C (real Gmail API). Not implemented for the MVP/demo.

    A real implementation would read unread messages, parse the
    X-TalentBridge-* headers, and return them in the normalised shape above.
    """
    logger.info("Gmail inbox source is a stretch-goal stub — returning empty inbox.")
    return []


# ─────────────────────────────────────────────
# Tool 2 — extract_tracking_headers
# ─────────────────────────────────────────────

def extract_tracking_headers(reply: Dict[str, Any]) -> Dict[str, Optional[int]]:
    """
    Read and safely parse the X-TalentBridge tracking headers from a reply.

    Returns {"campaign_id": int|None, "email_id": int|None}. Any value that is
    missing or non-numeric becomes None rather than raising.
    """
    headers = reply.get("headers") or {}

    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    return {
        "campaign_id": _safe_int(headers.get(HEADER_CAMPAIGN_ID)),
        "email_id": _safe_int(headers.get(HEADER_EMAIL_ID)),
    }


# ─────────────────────────────────────────────
# Tool 3 — match_reply_to_campaign
# ─────────────────────────────────────────────

def match_reply_to_campaign(reply: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Resolve which campaign/email a reply belongs to.

    Strategy:
        1. Tracking headers (primary, exact).
        2. Sender-email fallback against Sent emails.
        3. Otherwise log as unmatched and return None.
    """
    headers = extract_tracking_headers(reply)
    if headers["campaign_id"] is not None and headers["email_id"] is not None:
        return {
            "campaign_id": headers["campaign_id"],
            "email_id": headers["email_id"],
            "match_method": "Tracking Headers",
        }

    sender = reply.get("from")
    if sender:
        try:
            sent_email = db.get_sent_email_by_recipient(sender)
        except Exception as exc:
            logger.error("Fallback match query failed for %s: %s", sender, exc)
            sent_email = None

        if sent_email:
            return {
                "campaign_id": sent_email.get("campaign_id"),
                "email_id": sent_email.get("email_id"),
                "match_method": "Sender Email Fallback",
            }

    # Cannot match — record and skip.
    try:
        db.log_unmatched_reply(reply)
    except Exception as exc:
        logger.error("log_unmatched_reply failed: %s", exc)
    logger.info("Unmatched reply from %s skipped.", reply.get("from"))
    return None


# ─────────────────────────────────────────────
# Tool 4 — is_duplicate_reply
# ─────────────────────────────────────────────

def is_duplicate_reply(reply_from: str, reply_subject: Optional[str],
                       received_at: datetime) -> bool:
    """
    True if the same sender+subject was already saved within the dedupe window.

    Fails OPEN on a DB error (returns False) so a transient glitch never blocks
    a genuine reply — at worst a duplicate is created and harmlessly classified.
    """
    try:
        return db.is_duplicate_reply(
            reply_from=reply_from,
            reply_subject=reply_subject,
            received_at=_coerce_received_at(received_at),
            window_hours=DUPLICATE_WINDOW_HOURS,
        )
    except Exception as exc:
        logger.error("Duplicate check failed for %s: %s", reply_from, exc)
        return False


# ─────────────────────────────────────────────
# Tool 5 — save_reply
# ─────────────────────────────────────────────

def save_reply(match: Dict[str, Any], reply: Dict[str, Any]) -> Optional[int]:
    """
    Persist one reply and return its new reply_id (or None on failure).

    Guarantees the NOT NULL contracts of the `replies` table:
        * reply_from -> never NULL (placeholder if missing)
        * reply_body -> "" instead of NULL
        * received_at -> naive UTC, always set
        * classification -> "Pending Classification"
    """
    email_id = match.get("email_id")
    campaign_id = match.get("campaign_id")

    try:
        company_name = db.get_company_name_for_email(email_id)
    except Exception as exc:
        logger.warning("Company-name lookup failed for email %s: %s", email_id, exc)
        company_name = None
    company_name = company_name or reply.get("company_name") or "Unknown"

    reply_from = reply.get("from") or "unknown@unknown.com"
    reply_body = reply.get("body") or ""           # NOT NULL — never None
    reply_subject = reply.get("subject")           # nullable
    received_at = _coerce_received_at(reply.get("received_at"))

    try:
        return db.save_reply(
            email_id=email_id,
            campaign_id=campaign_id,
            company_name=company_name,
            reply_from=reply_from,
            reply_subject=reply_subject,
            reply_body=reply_body,
            received_at=received_at,
            classification=PENDING_CLASSIFICATION,
        )
    except Exception as exc:
        logger.error("save_reply failed (email_id=%s, campaign_id=%s): %s",
                     email_id, campaign_id, exc)
        return None


# ─────────────────────────────────────────────
# Tool 6 — trigger_classification
# ─────────────────────────────────────────────

def trigger_classification(reply_id: int) -> bool:
    """
    Synchronously trigger Agent 09 for a freshly saved reply.

    The import is lazy so this module loads even if the classification agent's
    own dependencies are unavailable, and so unit tests can patch this function
    directly. Returns True on success, False if classification raised.
    """
    try:
        from agents.response_classification_agent import response_classification_agent
        response_classification_agent(reply_id)
        return True
    except Exception as exc:
        logger.error("Classification trigger failed for reply %s: %s", reply_id, exc)
        return False


# ─────────────────────────────────────────────
# Tool 7 — update_campaign_progress
# ─────────────────────────────────────────────

def update_campaign_progress(campaign_id: int) -> None:
    """Increment campaigns.replies_received and bump last_updated."""
    try:
        db.increment_replies_received(campaign_id)
    except Exception as exc:
        logger.error("increment_replies_received failed for campaign %s: %s",
                     campaign_id, exc)


# ─────────────────────────────────────────────
# Per-reply pipeline
# ─────────────────────────────────────────────

def _new_summary() -> Dict[str, int]:
    return {
        "fetched": 0,
        "matched": 0,
        "unmatched": 0,
        "duplicates": 0,
        "saved": 0,
        "classified": 0,
        "errors": 0,
    }


def _process_single_reply(reply: Dict[str, Any], summary: Dict[str, int]) -> None:
    """
    Run one reply through match -> dedupe -> save -> progress -> classify.

    Every failure is contained here so a single bad reply can never abort the
    whole cycle. Counters in `summary` are mutated in place.
    """
    try:
        match = match_reply_to_campaign(reply)
        if not match or match.get("campaign_id") is None or match.get("email_id") is None:
            summary["unmatched"] += 1
            return
        summary["matched"] += 1

        if is_duplicate_reply(reply.get("from"), reply.get("subject"),
                              reply.get("received_at")):
            summary["duplicates"] += 1
            return

        reply_id = save_reply(match, reply)
        if not reply_id:
            summary["errors"] += 1
            return
        summary["saved"] += 1

        update_campaign_progress(match["campaign_id"])

        if trigger_classification(reply_id):
            summary["classified"] += 1

    except Exception as exc:  # last line of defence — never propagate
        summary["errors"] += 1
        logger.exception("Unexpected error processing reply from %s: %s",
                         reply.get("from"), exc)


# ─────────────────────────────────────────────
# Public: one monitoring cycle
# ─────────────────────────────────────────────

def _resolve_campaign_ids(campaign_id: Optional[int]) -> List[int]:
    """Return the campaigns to scan: the given one, or all active campaigns."""
    if campaign_id is not None:
        return [campaign_id]
    try:
        active = db.get_active_campaigns_for_followups() or []
    except Exception as exc:
        logger.error("Failed to load active campaigns: %s", exc)
        return []
    return [c["campaign_id"] for c in active if c.get("campaign_id") is not None]


def run_inbox_monitoring_cycle(campaign_id: Optional[int] = None) -> Dict[str, Any]:
    """
    Run ONE inbox-monitoring pass.

    Args:
        campaign_id: scan just this campaign, or None to scan all active ones.

    Returns:
        A structured summary, e.g.:
        {
          "status": "ok",
          "campaigns_scanned": 1,
          "counts": {fetched, matched, unmatched, duplicates, saved, classified, errors}
        }
    """
    summary = _new_summary()
    campaign_ids = _resolve_campaign_ids(campaign_id)

    if not campaign_ids:
        logger.info("Inbox monitor: no campaigns to scan.")
        return {"status": "ok", "campaigns_scanned": 0, "counts": summary}

    for cid in campaign_ids:
        # Forward-only phase marker: first monitoring pass advances the campaign
        # to 'monitoring'. Guarded so repeated cycles never thrash the status.
        try:
            db.mark_campaign_monitoring(cid)
        except Exception as exc:
            logger.warning("Could not set 'monitoring' for campaign %s: %s", cid, exc)

        try:
            inbox = fetch_inbox(cid)
        except Exception as exc:
            # Inbox source unavailable — log and move on; next cycle retries.
            logger.error("Inbox fetch failed for campaign %s: %s", cid, exc)
            summary["errors"] += 1
            continue

        if not inbox:
            logger.info("Inbox monitor: no new replies for campaign %s.", cid)
            continue

        summary["fetched"] += len(inbox)
        for reply in inbox:
            _process_single_reply(reply, summary)

    logger.info("Inbox monitor cycle complete: %s", summary)
    return {
        "status": "ok",
        "campaigns_scanned": len(campaign_ids),
        "counts": summary,
    }


# ─────────────────────────────────────────────
# Public: APScheduler registration
# ─────────────────────────────────────────────

def start_inbox_monitor(campaign_id: int, scheduler: Any = None) -> Any:
    """
    Register the monitoring cycle on an interval and start the scheduler.

    The interval comes from campaigns.inbox_check_minutes (default 5). Pass an
    existing BackgroundScheduler to share one across agents, or let this create
    one. Returns the scheduler so the caller can shut it down later.
    """
    try:
        minutes = db.get_inbox_check_minutes(campaign_id) or DEFAULT_CHECK_MINUTES
    except Exception as exc:
        logger.warning("Could not read inbox_check_minutes for campaign %s (%s); "
                       "using default %s.", campaign_id, exc, DEFAULT_CHECK_MINUTES)
        minutes = DEFAULT_CHECK_MINUTES

    # Lazy import so the module (and tests) don't require apscheduler installed.
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = scheduler or BackgroundScheduler()
    scheduler.add_job(
        func=run_inbox_monitoring_cycle,
        trigger="interval",
        minutes=minutes,
        args=[campaign_id],
        id="inbox_monitor",
        name="Inbox Monitoring Agent",
        replace_existing=True,
    )

    if not getattr(scheduler, "running", False):
        scheduler.start()

    logger.info("Inbox monitor scheduled every %s min for campaign %s.",
                minutes, campaign_id)
    return scheduler


# ─────────────────────────────────────────────
# Manual smoke test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    cid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    outcome = run_inbox_monitoring_cycle(campaign_id=cid)
    print(outcome)