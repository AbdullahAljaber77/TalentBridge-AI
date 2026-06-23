"""
TalentBridge AI — FastAPI backend.

Thin API layer over the agents + graphs. Endpoints map 1:1 to the actions
already tested at the agent/graph level. Built incrementally; this first slice
covers listing and creating campaigns.
"""

from typing import Optional, List
from datetime import date

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from pathlib import Path

from shared import db

app = FastAPI(title="TalentBridge AI", version="0.1.0")

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────
# Request/response models
# ─────────────────────────────────────────────

class CampaignCreate(BaseModel):
    campaign_name: str = Field(..., min_length=1)
    selected_keywords: List[str] = Field(..., min_length=1)
    date_range_start: date
    date_range_end: date
    campaign_end_date: Optional[date] = None
    followup_days: int = 3
    inbox_check_minutes: int = 60

# ─────────────────────────────────────────────
# Launch (slow pipeline) — background task + status polling
# ─────────────────────────────────────────────

# In-process launch state per campaign. Keys: "running" | "paused_for_approval"
# | "complete" | "error", plus the last result/interrupt payload.
_launch_status: dict = {}


class LaunchParams(BaseModel):
    job_limit: Optional[int] = None
    min_match_score: float = 0.2
    experience_strict: bool = True
    top_k: int = 5

class EmailEdit(BaseModel):
    new_subject: Optional[str] = None
    new_body: Optional[str] = None


class EmailReject(BaseModel):
    reason: str = "Other"


class ResumeRequest(BaseModel):
    finalize: bool = False

def _run_launch(campaign_id: int, params: dict):
    """Background worker: runs the outreach graph 01->06 until it pauses."""
    _launch_status[campaign_id] = {"state": "running"}
    try:
        # Imported lazily so the heavy graph/model load happens in the worker,
        # not at API import time.
        from graph.outreach_runner import launch_outreach
        result = launch_outreach(campaign_id, params=params)
        _launch_status[campaign_id] = result   # {"state": "paused_for_approval", ...}
    except Exception as exc:
        _launch_status[campaign_id] = {"state": "error", "detail": str(exc)}


@app.post("/api/campaigns/{campaign_id}/launch")
def launch(campaign_id: int, params: LaunchParams, background: BackgroundTasks):
    """
    Kick off the outreach pipeline in the background and return immediately.
    The frontend polls GET .../launch-status until it leaves 'running'.
    """
    camp = db.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")

    current = _launch_status.get(campaign_id, {}).get("state")
    if current == "running":
        raise HTTPException(status_code=409, detail="Launch already in progress")

    background.add_task(_run_launch, campaign_id, params.model_dump())
    return {"campaign_id": campaign_id, "state": "running"}


@app.get("/api/campaigns/{campaign_id}/launch-status")
def launch_status(campaign_id: int):
    """Poll the background launch state."""
    status = _launch_status.get(campaign_id)
    if status is None:
        return {"campaign_id": campaign_id, "state": "idle"}
    return {"campaign_id": campaign_id, **status}

# ─────────────────────────────────────────────
# Approval queue — view, edit, approve/send, reject, resume
# ─────────────────────────────────────────────

@app.get("/api/campaigns/{campaign_id}/queue")
def get_queue(campaign_id: int):
    """Full pending-approval queue with editable subject/body per email."""
    emails = db.get_pending_emails(campaign_id) or []
    return {"campaign_id": campaign_id, "pending_count": len(emails), "emails": emails}


@app.post("/api/emails/{email_id}/edit")
def edit_email_endpoint(email_id: int, payload: EmailEdit):
    from agents.campaign_execution_agent import edit_email
    result = edit_email(email_id, new_subject=payload.new_subject, new_body=payload.new_body)
    if result.get("status") == "not found":
        raise HTTPException(status_code=404, detail="Email not found")
    if result.get("status") == "failed validation":
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return result


@app.post("/api/emails/{email_id}/approve")
def approve_email_endpoint(email_id: int):
    """Approve + send a single email (simulated send)."""
    from agents.campaign_execution_agent import approve_and_send_email
    result = approve_and_send_email(email_id)
    if result.get("status", "").startswith("failed"):
        raise HTTPException(status_code=400, detail=result.get("reason", result["status"]))
    return result


@app.post("/api/emails/{email_id}/reject")
def reject_email_endpoint(email_id: int, payload: EmailReject):
    from agents.campaign_execution_agent import reject_email
    return reject_email(email_id, reason=payload.reason)


@app.post("/api/campaigns/{campaign_id}/resume")
def resume_endpoint(campaign_id: int, payload: ResumeRequest):
    """
    Resume the paused outreach graph after a batch of approvals.
      finalize=False -> pause again (come back later)
      finalize=True  -> finalize and close the campaign
    """
    from graph.outreach_runner import resume_outreach
    result = resume_outreach(campaign_id, finalize=payload.finalize)
    _launch_status[campaign_id] = result   # keep status endpoint in sync
    return result

# ─────────────────────────────────────────────
# Monitoring — check for replies + view classified replies
# ─────────────────────────────────────────────

@app.post("/api/campaigns/{campaign_id}/check-replies")
def check_replies(campaign_id: int):
    """Run one monitoring pass (Agent 08 inbox + Agent 09 classify)."""
    from graph.monitoring_graph import run_monitoring
    try:
        return run_monitoring(campaign_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/campaigns/{campaign_id}/replies")
def get_replies(campaign_id: int):
    """All replies for a campaign, with classification."""
    rows = db.get_replies_for_campaign(campaign_id) or []
    return {"campaign_id": campaign_id, "count": len(rows), "replies": rows}

# ─────────────────────────────────────────────
# API: campaigns
# ─────────────────────────────────────────────

@app.get("/api/campaigns")
def list_campaigns():
    """Retrieve all campaigns (the 'Retrieve campaigns' button)."""
    return {"campaigns": db.list_campaigns()}


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    camp = db.get_campaign(campaign_id)
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return camp


@app.post("/api/campaigns")
def create_campaign(payload: CampaignCreate):
    """Create a new campaign row (status starts at 'pending')."""
    cid = db.create_campaign(
        campaign_name=payload.campaign_name,
        selected_keywords=payload.selected_keywords,
        date_range_start=payload.date_range_start.isoformat(),
        date_range_end=payload.date_range_end.isoformat(),
        campaign_end_date=payload.campaign_end_date.isoformat() if payload.campaign_end_date else None,
        followup_days=payload.followup_days,
        inbox_check_minutes=payload.inbox_check_minutes,
    )
    if not cid:
        raise HTTPException(status_code=500, detail="Failed to create campaign")
    return {"campaign_id": cid, "status": "created"}



# ─────────────────────────────────────────────
# Frontend (single-page) + health
# ─────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index():
    idx = STATIC_DIR / "index.html"
    if idx.exists():
        return FileResponse(idx)
    return {"message": "TalentBridge AI API. Frontend not built yet."}


# Serve static assets (index.html, later css/js) at /static
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")