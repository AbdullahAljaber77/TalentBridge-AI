"""
Outreach graph (Agents 01–07) with a human approval gate.

Linear pipeline 01→06 generates emails into the approval queue, then the graph
INTERRUPTS before execution. A human reviews/approves/edits/rejects emails in
the UI across one or more sessions. Each resume sends the currently-Approved
batch via Agent 07; the campaign only finalizes when the human signals done.

State is persisted with PostgresSaver, keyed by thread_id = "campaign-{id}", so
a campaign can pause for days (and survive server restarts) mid-approval.
"""

from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command

# Agent entry points (verified against the real files; names differ per agent)
from agents.job_analysis_agent import run as run_job_analysis          # 01
from agents.targeting_agent import run_targeting_agent                 # 02
from agents.contact_discovery_agent import contact_discovery_agent     # 03
from agents.research_agent import research_agent                       # 04
from agents.email_strategy_agent import email_strategy_agent           # 05
from agents.email_generation_agent import email_generation_agent       # 06
from agents.campaign_execution_agent import finalize_execution         # 07
from shared import db


# ─────────────────────────────────────────────
# State
# ─────────────────────────────────────────────

class OutreachState(TypedDict, total=False):
    campaign_id: int
    finalize: bool                 # human's signal on resume: done or pause again
    step_counts: Dict[str, Any]    # what each node produced, for visibility
    job_limit: int                 # optional cap on jobs analyzed (None = all)
    errors: List[str]
    summary: Dict[str, Any]


def _record(state, key, value):
    counts = dict(state.get("step_counts", {}))
    counts[key] = value
    return counts


# ─────────────────────────────────────────────
# Nodes 01–06 — linear pipeline
# ─────────────────────────────────────────────

def job_analysis_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = run_job_analysis(cid, limit=state.get("job_limit"))
    except Exception as exc:
        errors.append(f"01 job_analysis: {exc}")
        r = {"status": "error"}
    return {"step_counts": _record(state, "job_analysis", r), "errors": errors}


def targeting_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = run_targeting_agent(cid)
    except Exception as exc:
        errors.append(f"02 targeting: {exc}")
        r = {"status": "error"}
    return {"step_counts": _record(state, "targeting", r), "errors": errors}


def contact_discovery_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = contact_discovery_agent(cid)
    except Exception as exc:
        errors.append(f"03 contact_discovery: {exc}")
        r = {"status": "error"}
    return {"step_counts": _record(state, "contact_discovery", r), "errors": errors}


def research_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = research_agent(cid)
    except Exception as exc:
        errors.append(f"04 research: {exc}")
        r = {"status": "error"}
    return {"step_counts": _record(state, "research", r), "errors": errors}


def email_strategy_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = email_strategy_agent(cid)
    except Exception as exc:
        errors.append(f"05 email_strategy: {exc}")
        r = {"status": "error"}
    return {"step_counts": _record(state, "email_strategy", r), "errors": errors}


def email_generation_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = email_generation_agent(cid)
    except Exception as exc:
        errors.append(f"06 email_generation: {exc}")
        r = {"status": "error"}
    return {"step_counts": _record(state, "email_generation", r), "errors": errors}


# ─────────────────────────────────────────────
# Approval gate — interrupt + send loop
# ─────────────────────────────────────────────

def approval_gate_node(state: OutreachState) -> OutreachState:
    """
    Pause for human approval. The interrupt payload shows the current pending
    queue so the UI can render it. Resumes with {"finalize": bool}:
      False -> human sent a batch, pause again (come back later)
      True  -> human is done, proceed to finalize
    """
    cid = state["campaign_id"]
    try:
        pending = db.get_pending_emails(cid) or []
    except Exception:
        pending = []

    decision = interrupt({
        "message": "Review the queue. Approve/edit/reject emails, then resume.",
        "campaign_id": cid,
        "pending_count": len(pending),
        "pending_emails": [
            {"email_id": e["email_id"], "email_type": e.get("email_type"),
             "company_name": e.get("company_name"), "subject": e.get("subject")}
            for e in pending
        ],
    })
    finalize = bool(decision.get("finalize", False)) if isinstance(decision, dict) else False
    return {"finalize": finalize}


def finalize_router(state: OutreachState) -> str:
    """If the human signaled done, finalize; otherwise pause again."""
    return "finalize" if state.get("finalize") else "approval_gate"


def finalize_node(state: OutreachState) -> OutreachState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        r = finalize_execution(cid)
    except Exception as exc:
        errors.append(f"07 finalize: {exc}")
        r = {"status": "error"}
    summary = {
        "campaign_id": cid,
        "steps": state.get("step_counts", {}),
        "finalize_result": r,
        "errors": errors,
        "status": "complete" if not errors else "completed_with_errors",
    }
    return {"summary": summary, "errors": errors}


# ─────────────────────────────────────────────
# Build & compile
# ─────────────────────────────────────────────

def build_outreach_graph(checkpointer):
    g = StateGraph(OutreachState)

    g.add_node("job_analysis", job_analysis_node)
    g.add_node("targeting", targeting_node)
    g.add_node("contact_discovery", contact_discovery_node)
    g.add_node("research", research_node)
    g.add_node("email_strategy", email_strategy_node)
    g.add_node("email_generation", email_generation_node)
    g.add_node("approval_gate", approval_gate_node)
    g.add_node("finalize", finalize_node)

    g.add_edge(START, "job_analysis")
    g.add_edge("job_analysis", "targeting")
    g.add_edge("targeting", "contact_discovery")
    g.add_edge("contact_discovery", "research")
    g.add_edge("research", "email_strategy")
    g.add_edge("email_strategy", "email_generation")
    g.add_edge("email_generation", "approval_gate")
    g.add_conditional_edges("approval_gate", finalize_router,
                            {"finalize": "finalize", "approval_gate": "approval_gate"})
    g.add_edge("finalize", END)

    return g.compile(checkpointer=checkpointer)