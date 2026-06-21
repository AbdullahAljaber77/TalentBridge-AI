"""
TalentBridge AI — Web Search Tool

Primary provider: Tavily. Optional fallback: DuckDuckGo (duckduckgo_search)
when Tavily is unavailable, has no key, or returns nothing. Every network call
is wrapped with a timeout and safe failure handling: a failed search returns []
rather than raising, so a single bad query never crashes the calling agent.
"""

import requests

from shared.config import TAVILY_API_KEY

TAVILY_ENDPOINT     = "https://api.tavily.com/search"
DEFAULT_TIMEOUT     = 20
DEFAULT_MAX_RESULTS = 5


# ─────────────────────────────────────────────
# Providers
# ─────────────────────────────────────────────

def _tavily_search(query: str, max_results: int = DEFAULT_MAX_RESULTS,
                   recent_days: int = None, topic: str = None) -> list[dict]:

    if not TAVILY_API_KEY:
        return []
    try:
        payload = {
            "api_key":      TAVILY_API_KEY,
            "query":        query,
            "search_depth": "basic",
            "max_results":  max_results,
        }
        if topic:
            payload["topic"] = topic
        if recent_days is not None:
            payload["days"] = recent_days
        response = requests.post(TAVILY_ENDPOINT, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
        return response.json().get("results", []) or []
    except Exception as exc:
        print(f"[web_search] Tavily failed for {query!r}: {exc}")
        return []


def _duckduckgo_search(query: str, max_results: int = DEFAULT_MAX_RESULTS) -> list[dict]:
    """Fallback using the optional `duckduckgo_search` package.
    Returns [] if the package is not installed or the call fails."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return []
    try:
        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(query, max_results=max_results):
                results.append({
                    "title":   item.get("title", ""),
                    "content": item.get("body", ""),
                    "url":     item.get("href", ""),
                })
        return results
    except Exception as exc:
        print(f"[web_search] DuckDuckGo failed for {query!r}: {exc}")
        return []


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def web_search(query: str, max_results: int = DEFAULT_MAX_RESULTS,
               recent_days: int = None, topic: str = None) -> list[dict]:
    """
    Run a web search and return a list of {title, content, url} dicts.

    Tries Tavily first; if it returns nothing (no key, error, or empty),
    falls back to DuckDuckGo. Never raises — returns [] when all providers fail.

    recent_days / topic: optional recency controls for Tavily (e.g. topic='news',
    recent_days=180 to restrict to the last 6 months). The DuckDuckGo fallback
    ignores them.
    """
    results = _tavily_search(query, max_results=max_results,
                             recent_days=recent_days, topic=topic)
    if results:
        return results
    return _duckduckgo_search(query, max_results=max_results)


def results_to_text(results: list[dict], limit: int = DEFAULT_MAX_RESULTS) -> str:
    """Flatten search results into a single readable text block for an LLM prompt."""
    if not results:
        return ""
    chunks = []
    for item in results[:limit]:
        title   = item.get("title", "") or ""
        content = item.get("content", "") or ""
        url     = item.get("url", "") or ""
        chunks.append(f"{title}\n{content}\n{url}".strip())
    return "\n\n".join(chunks).strip()