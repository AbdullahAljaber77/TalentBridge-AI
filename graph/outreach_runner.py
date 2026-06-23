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

from shared.config import DATABASE_URL
from graph.outreach_graph import build_outreach_graph


# psycopg3 connection string: PostgresSaver wants a libpq URL. Neon's URL works
# as-is. autocommit is recommended by langgraph for the saver.
_DB_URL = DATABASE_URL

# Open one persistent saver for the process.
_cm = PostgresSaver.from_conn_string(_DB_URL)
checkpointer = _cm.__enter__()
checkpointer.setup()  # creates checkpoint tables if absent; safe to call repeatedly

graph = build_outreach_graph(checkpointer)


def _config(campaign_id: int) -> Dict[str, Any]:
    return {"configurable": {"thread_id": f"campaign-{campaign_id}"}}


def launch_outreach(campaign_id: int, job_limit: int = None) -> Dict[str, Any]:
    """Start a campaign: run 01..06, then pause at the approval gate.

    job_limit caps how many jobs Agent 01 analyzes (small-batch / test runs).
    """
    result = graph.invoke(
        {"campaign_id": campaign_id, "finalize": False, "job_limit": job_limit},
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