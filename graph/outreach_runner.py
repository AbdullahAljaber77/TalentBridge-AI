"""
Runner for the outreach graph: owns the PostgresSaver and exposes three calls
the UI/CLI uses to drive a campaign through the approval gate.

  launch_outreach(campaign_id)         -> runs 01..06, pauses at the gate
  resume_outreach(campaign_id, finalize) -> resumes; finalize=False pauses again,
                                            finalize=True closes the campaign
  outreach_state(campaign_id)          -> peek at where a campaign's run is

thread_id = f"campaign-{campaign_id}" ties every visit to the same run, and the
PostgresSaver persists it in Neon so a campaign can pause for days / survive a
server restart mid-approval.
"""

from typing import Dict, Any

from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
from psycopg_pool import ConnectionPool

from shared.config import DATABASE_URL
from graph.outreach_graph import build_outreach_graph


# Neon (serverless) closes idle connections, and a single long-lived connection
# goes stale between user actions. A pool with check=ConnectionPool.check_connection
# validates each connection on checkout and transparently reopens dead ones.
_pool = ConnectionPool(
    conninfo=DATABASE_URL,
    max_size=10,
    open=True,
    check=ConnectionPool.check_connection,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)

checkpointer = PostgresSaver(_pool)
checkpointer.setup()  # creates checkpoint tables if absent; safe to call repeatedly

graph = build_outreach_graph(checkpointer)


def _config(campaign_id: int) -> Dict[str, Any]:
    return {"configurable": {"thread_id": f"campaign-{campaign_id}"}}


def launch_outreach(campaign_id: int, params: Dict[str, Any] = None) -> Dict[str, Any]:
    """Start a campaign: run 01..06, then pause at the approval gate.

    params (all optional) tune the pipeline per campaign:
      job_limit         int   — cap jobs analyzed by Agent 01 (None = all)
      min_match_score   float — Agent 02 minimum score to save a match (default 0.2)
      experience_strict bool  — Agent 02 exact level match (default True)
      top_k             int   — Agent 02 max students per job (default 5)
    """
    result = graph.invoke(
        {"campaign_id": campaign_id, "finalize": False, "params": params or {}},
        config=_config(campaign_id),
    )
    return _describe(campaign_id, result)


def resume_outreach(campaign_id: int, finalize: bool = False) -> Dict[str, Any]:
    """
    Resume a paused campaign after the human sent a batch in the UI.
      finalize=False -> pause again (more to approve later)
      finalize=True  -> finalize and close the campaign
    """
    result = graph.invoke(
        Command(resume={"finalize": finalize}),
        config=_config(campaign_id),
    )
    return _describe(campaign_id, result)


def outreach_state(campaign_id: int) -> Dict[str, Any]:
    """Peek at the current checkpointed state without advancing the graph."""
    snap = graph.get_state(_config(campaign_id))
    return {
        "campaign_id": campaign_id,
        "next": snap.next,                    # () when finished; ('approval_gate',) when paused
        "values": snap.values,
    }


def _describe(campaign_id: int, result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Shape the invoke() return for callers. When the graph is paused at an
    interrupt, langgraph returns an '__interrupt__' payload; when finished,
    it returns the final state (with our 'summary').
    """
    if "__interrupt__" in result:
        intr = result["__interrupt__"][0]
        return {"state": "paused_for_approval",
                "campaign_id": campaign_id,
                "interrupt": intr.value}
    if "summary" in result:
        return {"state": "complete",
                "campaign_id": campaign_id,
                "summary": result["summary"]}
    return {"state": "unknown", "campaign_id": campaign_id, "raw": result}