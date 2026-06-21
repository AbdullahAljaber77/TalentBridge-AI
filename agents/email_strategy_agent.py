import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from shared import db

try:
    from shared.llm import call_llm
except Exception:
    call_llm = None


BASE_DIR = Path(__file__).resolve().parent.parent
PLAYBOOK_DIR = BASE_DIR / "data" / "playbooks"
MOCK_RESULTS_PATH = BASE_DIR / "data" / "mock_past_results.json"


PLAYBOOK_MAP = {
    "Large Enterprise": {
        "file": "enterprise_playbook.txt",
        "tone": "Formal",
        "email_length": "Medium",
        "call_to_action": "Schedule a 15-minute introductory call",
        "playbook_used": "Enterprise Playbook",
    },
    "Tech Startup": {
        "file": "startup_playbook.txt",
        "tone": "Conversational",
        "email_length": "Short",
        "call_to_action": "Review student profiles online",
        "playbook_used": "Startup Playbook",
    },
    "Government": {
        "file": "government_playbook.txt",
        "tone": "Very Formal",
        "email_length": "Long",
        "call_to_action": "Schedule a formal meeting",
        "playbook_used": "Government Playbook",
    },
    "Government / Semi-Government": {
        "file": "government_playbook.txt",
        "tone": "Very Formal",
        "email_length": "Long",
        "call_to_action": "Schedule a formal meeting",
        "playbook_used": "Government Playbook",
    },
    "Consulting": {
        "file": "consulting_playbook.txt",
        "tone": "Professional",
        "email_length": "Medium",
        "call_to_action": "Schedule a 15-minute introductory call",
        "playbook_used": "Consulting Playbook",
    },
    "SME": {
        "file": "sme_playbook.txt",
        "tone": "Friendly",
        "email_length": "Short",
        "call_to_action": "Review student profiles online",
        "playbook_used": "SME Playbook",
    },
}


def normalize_company_type(company_type: Optional[str]) -> str:
    if not company_type:
        return "Large Enterprise"

    value = company_type.strip()

    if value in PLAYBOOK_MAP:
        return value

    lower = value.lower()

    if "startup" in lower:
        return "Tech Startup"
    if "government" in lower or "semi" in lower:
        return "Government"
    if "consult" in lower:
        return "Consulting"
    if "sme" in lower or "small" in lower:
        return "SME"
    if "enterprise" in lower or "large" in lower:
        return "Large Enterprise"

    return "Large Enterprise"


def load_playbook(company_type: str) -> Dict[str, Any]:
    normalized_type = normalize_company_type(company_type)
    meta = PLAYBOOK_MAP[normalized_type]

    path = PLAYBOOK_DIR / meta["file"]

    if path.exists():
        content = path.read_text(encoding="utf-8")
    else:
        content = f"""
Company Type: {normalized_type}
Tone: {meta["tone"]}
Email Length: {meta["email_length"]}
Call to Action: {meta["call_to_action"]}
Use a professional outreach strategy based on the company type.
"""

    return {
        "company_type": normalized_type,
        "content": content,
        **meta
    }


def load_mock_past_results(company_type: str) -> List[Dict[str, Any]]:
    if not MOCK_RESULTS_PATH.exists():
        return []

    try:
        data = json.loads(MOCK_RESULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    normalized = normalize_company_type(company_type).lower()

    results = []

    for item in data:
        item_type = str(item.get("company_type", "")).lower()
        if normalized in item_type or item_type in normalized:
            results.append(item)

    return results[:5]


def build_angles(research: Dict[str, Any], matches: List[Dict[str, Any]]) -> str:
    angles = ["Skills Match"]

    recent_news_hook = research.get("recent_news_hook")

    if recent_news_hook:
        angles.insert(0, "News Hook")

    unique_students = set()

    for match in matches:
        if match.get("student_id"):
            unique_students.add(match["student_id"])

    if len(unique_students) > 3:
        angles.append("Cohort Size")

    return " + ".join(angles)


def get_matched_roles(matches: List[Dict[str, Any]]) -> List[str]:
    roles = []

    for match in matches:
        title = match.get("job_title")
        if title and title not in roles:
            roles.append(title)

    return roles[:5]


def build_strategy_prompt(
    company_name: str,
    research: Dict[str, Any],
    matches: List[Dict[str, Any]],
    playbook: Dict[str, Any],
    past_results: List[Dict[str, Any]],
    angles: str
) -> str:
    matched_roles = get_matched_roles(matches)
    matched_students_count = len(set(m.get("student_id") for m in matches if m.get("student_id")))

    return f"""
You are an expert email campaign strategist for a recruitment outreach campaign.

Decide the best outreach email strategy for this company.

Company: {company_name}
Company Type: {research.get("company_type")}
Research Summary: {research.get("research_summary")}
Recent News Hook: {research.get("recent_news_hook")}
Why Interested: {research.get("why_interested")}
Number of Matched Students: {matched_students_count}
Matched Roles: {matched_roles}

Playbook:
{playbook.get("content")}

Similar Past Results:
{json.dumps(past_results, ensure_ascii=False)}

Available Angles:
{angles}

Return valid JSON only:
{{
  "tone": "Formal | Conversational | Very Formal | Professional | Friendly",
  "angle": "which angles to use and in what order",
  "email_length": "Short | Medium | Long",
  "call_to_action": "exact CTA from playbook",
  "playbook_used": "name of playbook used",
  "strategy_notes": "brief explanation"
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


def fallback_strategy(
    research: Dict[str, Any],
    matches: List[Dict[str, Any]],
    playbook: Dict[str, Any]
) -> Dict[str, Any]:
    angles = build_angles(research, matches)

    return {
        "tone": playbook["tone"],
        "angle": angles,
        "email_length": playbook["email_length"],
        "call_to_action": playbook["call_to_action"],
        "playbook_used": playbook["playbook_used"],
        "strategy_notes": "Fallback strategy selected from company type playbook."
    }


def validate_strategy(strategy: Dict[str, Any], playbook: Dict[str, Any]) -> Dict[str, Any]:
    allowed_tones = ["Formal", "Conversational", "Very Formal", "Professional", "Friendly"]
    allowed_lengths = ["Short", "Medium", "Long"]

    if strategy.get("tone") not in allowed_tones:
        strategy["tone"] = playbook["tone"]

    if strategy.get("email_length") not in allowed_lengths:
        strategy["email_length"] = playbook["email_length"]

    if not strategy.get("angle"):
        strategy["angle"] = "Skills Match"

    if not strategy.get("call_to_action"):
        strategy["call_to_action"] = playbook["call_to_action"]

    if not strategy.get("playbook_used"):
        strategy["playbook_used"] = playbook["playbook_used"]

    if not strategy.get("strategy_notes"):
        strategy["strategy_notes"] = "Strategy selected based on research and playbook."

    return strategy


def decide_strategy(
    company_name: str,
    research: Dict[str, Any],
    matches: List[Dict[str, Any]]
) -> Dict[str, Any]:
    company_type = normalize_company_type(research.get("company_type"))
    playbook = load_playbook(company_type)
    past_results = load_mock_past_results(company_type)
    angles = build_angles(research, matches)

    if call_llm:
        prompt = build_strategy_prompt(
            company_name=company_name,
            research=research,
            matches=matches,
            playbook=playbook,
            past_results=past_results,
            angles=angles
        )

        try:
            response = call_llm(prompt)
            parsed = parse_json_response(response)

            if parsed:
                return validate_strategy(parsed, playbook)
        except Exception:
            pass

    strategy = fallback_strategy(research, matches, playbook)
    return validate_strategy(strategy, playbook)


def process_company(campaign_id: int, company_name: str) -> Dict[str, Any]:
    research = db.get_company_research(company_name)

    if not research:
        return {
            "company_name": company_name,
            "status": "skipped_no_research",
            "reason": "No company_research row found. Agent 04 must run first."
        }

    matches = db.get_job_matches_for_company(campaign_id, company_name)

    if not matches:
        return {
            "company_name": company_name,
            "status": "skipped_no_matches",
            "reason": "No job_matches found for this campaign/company."
        }

    strategy = decide_strategy(company_name, research, matches)

    saved = db.save_email_strategy(
        campaign_id=campaign_id,
        company_name=company_name,
        tone=strategy["tone"],
        angle=strategy["angle"],
        email_length=strategy["email_length"],
        call_to_action=strategy["call_to_action"],
        playbook_used=strategy["playbook_used"]
    )

    return {
        "company_name": company_name,
        "status": "strategy_saved",
        "strategy_id": saved.get("strategy_id") if saved else None,
        "tone": strategy["tone"],
        "angle": strategy["angle"],
        "email_length": strategy["email_length"],
        "call_to_action": strategy["call_to_action"],
        "playbook_used": strategy["playbook_used"]
    }


def email_strategy_agent(campaign_id: int) -> Dict[str, Any]:
    db.update_campaign_status(campaign_id, "strategizing emails")

    companies = db.get_companies_for_email_strategy(campaign_id)

    results = []

    for company in companies:
        company_name = company["company_name"]
        result = process_company(campaign_id, company_name)
        results.append(result)
        db.touch_campaign(campaign_id)

    db.update_campaign_status(campaign_id, "email strategies ready")

    return {
        "status": "email strategies ready",
        "campaign_id": campaign_id,
        "companies_processed": len(companies),
        "results": results
    }


if __name__ == "__main__":
    output = email_strategy_agent(campaign_id=2)
    print(output)