"""
Agent 04 — Research Agent
TalentBridge AI — RCP #7

Fourth agent in the pipeline. For each unique target company in a campaign it
gathers web intelligence (overview, recent news, hiring signals), asks the LLM
to summarize and classify the company, and saves the result to company_research.
Research is cached per company and reused when it is
less than 30 days old.

Flow:
  load companies -> (cache fresh? reuse) -> 3 web searches -> LLM summarize
  -> save (UPSERT) -> update campaign progress
"""

from datetime import date, datetime

from shared import db
from shared.llm import call_llm_with_data, build_system_prompt
from tools.web_search import web_search, results_to_text


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

CACHE_MAX_AGE_DAYS = 30
NEWS_RECENCY_DAYS  = 180   # 6 months — matches the recent_news_hook freshness rule

VALID_COMPANY_TYPES = {
    "Large Enterprise", "Tech Startup", "Government", "Consulting", "SME",
}
VALID_CONFIDENCE = {"High", "Medium", "Low"}

REQUIRED_FIELDS = [
    "research_summary",
    "company_type",
    "classification_confidence",
    "why_interested",
    "recent_news_hook",
]

SYSTEM_PROMPT = build_system_prompt(
    role="business research analyst",
    instructions=(
        "Analyze web search results about a company and produce structured "
        "intelligence for an employer outreach campaign. "
        "Always respond with valid JSON only — no markdown, no explanation.\n"
        "Company type definitions:\n"
        "- Large Enterprise: 1000+ employees, established brand\n"
        "- Tech Startup: early stage, under 5 years old, under 200 employees, "
        "venture backed and still in growth/funding phase\n"
        "- Government: government or semi-government entity (e.g. Aramco, STC)\n"
        "- Consulting: professional services / advisory firm\n"
        "- SME: small to medium business under 1000 employees — includes grown "
        "startups that have scaled beyond early stage (e.g. 5+ years old, "
        "large user base, or significant revenue)\n"
        "Only include a recent_news_hook if the news is from the last 6 months; "
        "otherwise return null. Search results may be in Arabic — that is fine."
    ),
)

INSTRUCTION = (
    "Analyze the following search results about the company and produce "
    "structured research output. Return JSON with exactly these keys:\n"
    "- research_summary: 2-3 sentence overview of what the company does\n"
    "- company_type: use EXACTLY one of these values with no modifications: "
    "Large Enterprise | Tech Startup | Government | Consulting | SME. "
    "No hyphens, no punctuation, no variations.\n"
    "- classification_confidence: one of High | Medium | Low\n"
    "- why_interested: one sentence on why this company would want our graduates\n"
    "- recent_news_hook: one sentence recent news for an email opener "
    "(last 6 months only) — null if nothing recent was found\n"
    "Always write all field values in English, even if the search results "
    "are in Arabic."
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _add_region(company_name: str) -> str:
    """Append 'Saudi Arabia' to disambiguate company names that don't already
    reference the region."""
    lowered = company_name.lower()
    if "saudi" in lowered or "ksa" in lowered:
        return company_name
    return f"{company_name} Saudi Arabia"


def _cache_is_fresh(research_row: dict) -> bool:
    """True if a cached row exists and is younger than CACHE_MAX_AGE_DAYS."""
    if not research_row:
        return False
    last_updated = research_row.get("last_updated")
    if isinstance(last_updated, datetime):
        last_updated = last_updated.date()
    if not isinstance(last_updated, date):
        return False
    age_days = (date.today() - last_updated).days
    return age_days < CACHE_MAX_AGE_DAYS


def _as_optional_text(value):
    """Coerce a value into a clean str, or None. Guards against the LLM
    returning a non-string (list/dict/number) for a TEXT column."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _normalize_news_hook(value):
    """The LLM may emit 'null' / 'none' / '' for no news — normalize to None.
    Non-string, non-None values are dropped (an unusable hook is no hook)."""
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned == "" or cleaned.lower() in {"null", "none", "n/a", "na"}:
        return None
    return cleaned


def _default_research() -> dict:
    """Safe defaults used when search yields nothing or the LLM fails."""
    return {
        "research_summary":          "No information found",
        "company_type":              "SME",
        "classification_confidence": "Low",
        "why_interested":            None,
        "recent_news_hook":          None,
    }


def _sanitize(analysis: dict) -> dict:
    """Coerce LLM output into safe, schema-valid values."""
    company_type = analysis.get("company_type")
    if company_type not in VALID_COMPANY_TYPES:
        company_type = "SME"  # safe default for unknown / small companies

    confidence = analysis.get("classification_confidence")
    if confidence not in VALID_CONFIDENCE:
        confidence = "Low"

    return {
        "research_summary":          _as_optional_text(analysis.get("research_summary")) or "No information found",
        "company_type":              company_type,
        "classification_confidence": confidence,
        "why_interested":            _as_optional_text(analysis.get("why_interested")),
        "recent_news_hook":          _normalize_news_hook(analysis.get("recent_news_hook")),
    }


# ─────────────────────────────────────────────
# Per-company research
# ─────────────────────────────────────────────

def research_company(company_name: str) -> dict:
    """Run the three web searches + LLM summarization for one company.
    Always returns a sanitized research dict — never raises."""
    region_name = _add_region(company_name)

    # Use a rolling two-year window computed at runtime (never hardcode the year,
    # or the query silently goes stale — e.g. searching "2025 2026" in 2027).
    current_year = date.today().year
    recent_years = f"{current_year - 1} {current_year}"

    overview = results_to_text(web_search(
        f"{region_name} overview industry size"))
    # News: enforce the 6-month recency rule at the source (Tavily topic=news,
    # days=180) so recent_news_hook is fed fresh inputs rather than stale ones.
    news = results_to_text(web_search(
        f"{region_name} company news hiring {recent_years}",
        recent_days=NEWS_RECENCY_DAYS, topic="news"))
    hiring = results_to_text(web_search(
        f"{region_name} expansion growth jobs"))

    # No web signal at all → safe default, classified Low.
    if not (overview or news or hiring):
        return _default_research()

    try:
        analysis = call_llm_with_data(
            instruction=INSTRUCTION,
            data={
                "company_name":                    company_name,
                "search_result_1_overview":        overview or "No results",
                "search_result_2_recent_news":     news or "No results",
                "search_result_3_hiring_signals":  hiring or "No results",
            },
            system=SYSTEM_PROMPT,
            required_keys=REQUIRED_FIELDS,
        )
    except Exception as exc:
        print(f"   ✗ LLM failed for {company_name}: {exc}")
        return _default_research()

    return _sanitize(analysis)


def process_company(company_name: str) -> dict:
    """Cache-aware processing for a single company."""
    cached = db.get_research_by_company(company_name)
    if _cache_is_fresh(cached):
        return {
            "company_name": company_name,
            "status":       "cached_research_used",
            "company_type": cached.get("company_type"),
        }

    research = research_company(company_name)

    saved = db.save_company_research(
        company_name              = company_name,
        research_summary          = research["research_summary"],
        company_type              = research["company_type"],
        classification_confidence = research["classification_confidence"],
        why_interested            = research["why_interested"],
        recent_news_hook          = research["recent_news_hook"],
    )

    return {
        "company_name": company_name,
        "status":       "research_saved",
        "company_type": research["company_type"],
        "research_id":  saved["research_id"] if saved else None,
    }


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def research_agent(campaign_id: int) -> dict:
    db.update_campaign_status(campaign_id, "researching companies")

    companies = db.get_companies_for_research(campaign_id)
    print(f"Campaign {campaign_id}: {len(companies)} companies to research.")

    results = []
    for row in companies:
        company_name = (row or {}).get("company_name")
        if not company_name:
            print("   ✗ skipping row with missing company_name")
            continue
        try:
            result = process_company(company_name)
        except Exception as exc:
            print(f"   ✗ unexpected error for {company_name}: {exc}")
            result = {"company_name": company_name, "status": "failed", "error": str(exc)}

        results.append(result)
        print(f"   • {company_name} — {result['status']}")
        db.touch_campaign(campaign_id)

    db.update_campaign_status(campaign_id, "companies_researched")

    return {
        "status":              "complete",
        "campaign_id":         campaign_id,
        "companies_processed": len(results),
        "results":             results,
    }


if __name__ == "__main__":
    output = research_agent(campaign_id=1)
    print(output)