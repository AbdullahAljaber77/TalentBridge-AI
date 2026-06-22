"""
graph/background_scheduler.py
==============================
Runs background agents on a recurring schedule.

Background agents managed here:
    - Agent 08: Inbox Monitoring  (every 5 minutes)
    - Agent 10: Follow-Up         (every 24 hours)  ← Abdullah adds this later
"""

from apscheduler.schedulers.background import BackgroundScheduler
from agents.inbox_monitoring_agent import start_inbox_monitor

# Shared scheduler instance for all background agents
_scheduler = BackgroundScheduler()


def start_background_agents(campaign_id: int):
    """
    Called once after the first email is sent for a campaign.
    Starts all background agents for that campaign.
    """
    start_inbox_monitor(campaign_id, scheduler=_scheduler)

    # Agent 10 — Follow-Up Agent (Abdullah adds this later)
    # start_followup_monitor(campaign_id, scheduler=_scheduler)


def stop_background_agents():
    """Stops all background agents when a campaign ends."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)