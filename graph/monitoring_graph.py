"""
Monitoring graph — the re-runnable "Check for replies" cycle.

Two visible stages:
  inbox_node     (Agent 08) — fetch + match + save new replies, classification deferred
  classify_node  (Agent 09) — sweep every unclassified reply and classify it
  summary_node              — assemble counts for the UI / caller

Follow-ups (10), scheduling (11), and reporting (12) are deliberately NOT in
this graph — they are separate human-triggered actions.

This graph is safe to run repeatedly: Agent 08 is idempotent (no duplicate
replies) and the classify node only touches replies still marked unclassified.
"""

from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END

from agents.inbox_monitoring_agent import run_inbox_monitoring_cycle
from agents.response_classification_agent import response_classification_agent
from shared import db


# ─────────────────────────────────────────────
# Shared state — flows through every node
# ─────────────────────────────────────────────

class MonitoringState(TypedDict, total=False):
    campaign_id: int
    inbox_counts: Dict[str, int]      # fetched/matched/saved/... from Agent 08
    classified: int                   # how many replies this run classified
    classification_breakdown: Dict[str, int]
    errors: List[str]
    summary: Dict[str, Any]           # final UI-facing payload


# ─────────────────────────────────────────────
# Node 1 — inbox (Agent 08), classification deferred
# ─────────────────────────────────────────────

def inbox_node(state: MonitoringState) -> MonitoringState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    try:
        result = run_inbox_monitoring_cycle(cid, auto_classify=False)
        counts = result.get("counts", {})
    except Exception as exc:
        counts = {}
        errors.append(f"inbox_node: {exc}")
    return {"inbox_counts": counts, "errors": errors}


# ─────────────────────────────────────────────
# Node 2 — classify (Agent 09) sweep of unclassified replies
# ─────────────────────────────────────────────

def classify_node(state: MonitoringState) -> MonitoringState:
    cid = state["campaign_id"]
    errors = list(state.get("errors", []))
    breakdown: Dict[str, int] = {}
    classified = 0

    try:
        pending = db.get_unclassified_replies(cid) or []
    except Exception as exc:
        errors.append(f"classify_node (fetch): {exc}")
        pending = []

    for reply in pending:
        rid = reply["reply_id"]
        try:
            result = response_classification_agent(rid)
            label = result.get("classification", "Unknown")
            breakdown[label] = breakdown.get(label, 0) + 1
            classified += 1
        except Exception as exc:
            errors.append(f"classify_node (reply {rid}): {exc}")

    return {
        "classified": classified,
        "classification_breakdown": breakdown,
        "errors": errors,
    }


# ─────────────────────────────────────────────
# Node 3 — summary for the caller / UI
# ─────────────────────────────────────────────

def summary_node(state: MonitoringState) -> MonitoringState:
    counts = state.get("inbox_counts", {}) or {}
    summary = {
        "campaign_id": state["campaign_id"],
        "new_replies_saved": counts.get("saved", 0),
        "unmatched": counts.get("unmatched", 0),
        "duplicates": counts.get("duplicates", 0),
        "classified_this_run": state.get("classified", 0),
        "classification_breakdown": state.get("classification_breakdown", {}),
        "errors": state.get("errors", []),
        "status": "ok" if not state.get("errors") else "completed_with_errors",
    }
    return {"summary": summary}


# ─────────────────────────────────────────────
# Build & compile the graph
# ─────────────────────────────────────────────

def build_monitoring_graph():
    g = StateGraph(MonitoringState)
    g.add_node("inbox", inbox_node)
    g.add_node("classify", classify_node)
    g.add_node("summary", summary_node)

    g.set_entry_point("inbox")
    g.add_edge("inbox", "classify")
    g.add_edge("classify", "summary")
    g.add_edge("summary", END)

    return g.compile()


# Module-level compiled graph (import and reuse)
monitoring_graph = build_monitoring_graph()


def run_monitoring(campaign_id: int) -> Dict[str, Any]:
    """Convenience entry point: run one monitoring pass, return the summary."""
    final_state = monitoring_graph.invoke({"campaign_id": campaign_id})
    return final_state["summary"]