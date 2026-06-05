# Agent 04 — Research Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Research Agent is the **fourth agent** in the pipeline. For each target company it gathers intelligence from the web — company overview, industry, size, hiring signals, recent news, and company type classification. This intelligence is used by the Email Strategy Agent to choose the right approach and by the Email Generation Agent to personalize the email opener. Research is cached per company and reused if less than 30 days old.

---

## 2. Trigger

```
Contact Discovery Agent completes
        ↓
LangGraph triggers Research Agent
Input: campaign_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the active campaign |
| company_groups | job_matches table | Unique list of target companies |
| company_research | company_research table | Cached research (if exists) |

---

## 4. Output

New or updated rows in `company_research` table in PostgreSQL.

| Field | Type | Description |
|---|---|---|
| research_id | PK | Auto-generated |
| company_name | TEXT | Target company |
| research_summary | TEXT | 2-3 sentence company overview |
| company_type | TEXT | Large Enterprise / Tech Startup / Government / Consulting / SME |
| classification_confidence | TEXT | High / Medium / Low |
| why_interested | TEXT | Why this company might want our graduates |
| recent_news_hook | TEXT | One sentence recent news for email opener — NULL if not found |
| researched_at | TIMESTAMP | When research was first done |
| last_updated | TIMESTAMP | When research was last refreshed |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `check_research_cache()` | Check if fresh research exists (< 30 days old) |
| `web_search()` | Run web searches — Tavily API (tentative) |
| `llm_summarize_research()` | LLM summarizes search results into structured output |
| `classify_company_type()` | LLM classifies company type from research |
| `extract_news_hook()` | LLM extracts recent news hook if available |
| `save_company_research()` | Save research to PostgreSQL |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| Web Search | Tavily API (tentative) | DuckDuckGo API |
| LLM | Tentative — Anthropic / OpenAI | — |
| Database | PostgreSQL | — |

---

## 7. Processing Flow

```
STEP 1 — Load unique company list for this campaign
        ↓
STEP 2 — For each company:

  ── CHECK CACHE ──
  Does company_research table have an entry?
        ↓
  Yes → is research less than 30 days old? (tentative)
    Yes → reuse cached research → skip to next company
    No  → re-research — news may have changed
        ↓
  No → proceed to research

  ── SEARCH 1: Company Overview ──
  Query: "[company name] Saudi Arabia overview industry size"
  Goal: understand what the company does, how big it is,
        what industry it operates in
        ↓
  ── SEARCH 2: Recent News ──
  Query: "[company name] latest news hiring 2025 2026"
  Goal: find recent announcements, expansions,
        new projects, or hiring drives
        ↓
  ── SEARCH 3: Hiring Signals ──
  Query: "[company name] expansion growth jobs Saudi Arabia"
  Goal: confirm company is actively growing
        and likely to need talent
        ↓
  ── LLM SUMMARIZATION ──
  LLM reads all three search results and produces:
    - research_summary (2-3 sentences)
    - company_type classification
    - classification_confidence
    - why_interested (why they need our graduates)
    - recent_news_hook (one sentence — NULL if not found)
        ↓
STEP 3 — Save to company_research table
STEP 4 — Update campaign progress
```

---

## 8. LLM Prompt

```
System:
You are a business research analyst. Your task is to analyze
web search results about a company and produce structured
intelligence for an employer outreach campaign.
Always respond with valid JSON only.
No explanation, no markdown, no extra text.

User:
Analyze the following search results about {company_name}
and produce structured research output.

Search Result 1 — Company Overview:
{search_result_1}

Search Result 2 — Recent News:
{search_result_2}

Search Result 3 — Hiring Signals:
{search_result_3}

Return a JSON object with exactly these fields:
{
  "research_summary": "2-3 sentence overview of what the company does",
  "company_type": "Large Enterprise | Tech Startup | Government | Consulting | SME",
  "classification_confidence": "High | Medium | Low",
  "why_interested": "one sentence — why this company would want our graduates",
  "recent_news_hook": "one sentence recent news for email opener — null if nothing found"
}

Company type definitions:
- Large Enterprise: 1000+ employees, established brand
- Tech Startup: early stage, fast growing, venture backed
- Government: government entity or semi-government (e.g. Aramco, STC)
- Consulting: professional services, advisory firm
- SME: small to medium business, under 1000 employees
```

---

## 9. Example

### Input
```
Company: TAM Development Co.
Search 1 result: "TAM is a Saudi publicly listed company specialized
  in digital solutions for public and private sector clients..."
Search 2 result: "TAM announced expansion into AI advisory services
  in Q1 2026, partnering with three government entities..."
Search 3 result: "TAM is actively hiring across technology and
  consulting roles in Riyadh and Jeddah..."
```

### LLM Output
```json
{
  "research_summary": "TAM Development Co. is a Saudi publicly listed company specializing in digital solutions and advisory services for government and private sector clients. They have been a key partner for Vision 2030 initiatives for over a decade.",
  "company_type": "Consulting",
  "classification_confidence": "High",
  "why_interested": "TAM's expansion into AI advisory services creates strong demand for data science and software engineering graduates.",
  "recent_news_hook": "I noticed TAM recently announced their expansion into AI advisory services in partnership with government entities."
}
```

### How Email Generation Agent Uses This
```
recent_news_hook exists →
Email opener:
"I noticed TAM recently announced their expansion into AI advisory
services — we have graduates with exactly the skills you need."

recent_news_hook is NULL →
Fall back to skills match opener:
"We noticed TAM is actively hiring across technology roles —
we have graduates that match your requirements."
```

---

## 10. Company Type → Playbook Mapping

The company_type classification directly determines which playbook the Email Strategy Agent retrieves from RAG:

| Company Type | Playbook | Tone | Follow-up Timing |
|---|---|---|---|
| Large Enterprise | Enterprise Playbook | Formal | 5 days |
| Tech Startup | Startup Playbook | Conversational | 3 days |
| Government | Government Playbook | Very Formal | 7 days |
| Consulting | Consulting Playbook | Professional | 4 days |
| SME | SME Playbook | Friendly | 3 days |

---

## 11. Cache Freshness Logic

```python
def check_research_cache(company_name: str) -> bool:
    research = db.get_company_research(company_name)

    if not research:
        return False  # no cache — research needed

    age_days = (datetime.now() - research.last_updated).days

    if age_days < 30:  # tentative threshold
        return True   # fresh — reuse
    else:
        return False  # stale — re-research
```

---

## 12. Edge Cases

| Edge Case | Handling |
|---|---|
| Web search returns no results | research_summary = "No information found" — still classify based on company name |
| Company is unknown / very small | classification_confidence = "Low" — use SME as default type |
| Recent news is older than 6 months | recent_news_hook = NULL — not recent enough |
| Search results in Arabic | LLM still processes — it understands Arabic |
| Company name is ambiguous | Add "Saudi Arabia" to all queries to narrow results |
| Tavily API limit reached | Fall back to DuckDuckGo API |
| LLM returns invalid JSON | Retry once — if still invalid log error and use defaults |

---

## 13. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `job_matches` — unique company list
- `company_research` — cached research

This agent writes to:
- `company_research` — new or updated research
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `status` | Start → "researching companies" |
| `last_updated` | After each company researched |
| `completed_at` | When all companies researched |

---

## 14. Pseudocode

```python
def research_agent(campaign_id: int):

    companies = db.get_unique_companies(campaign_id)

    for company in companies:

        # Step 1 — Check cache
        if check_research_cache(company.company_name):
            continue  # fresh cache — skip

        # Step 2 — Run three web searches
        result_1 = web_search(
            f"{company.company_name} Saudi Arabia overview industry size"
        )
        result_2 = web_search(
            f"{company.company_name} latest news hiring 2025 2026"
        )
        result_3 = web_search(
            f"{company.company_name} expansion growth jobs Saudi Arabia"
        )

        # Step 3 — LLM summarization
        prompt = build_research_prompt(
            company.company_name, result_1, result_2, result_3
        )
        response = call_llm(prompt)
        research = parse_json(response)

        # Step 4 — Save to database
        db.save_company_research(
            company_name              = company.company_name,
            research_summary          = research["research_summary"],
            company_type              = research["company_type"],
            classification_confidence = research["classification_confidence"],
            why_interested            = research["why_interested"],
            recent_news_hook          = research["recent_news_hook"]
        )

        db.update_campaign_progress(campaign_id)

    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 15. Connection to Next Agent

```
Research Agent completes
        ↓
Output: company_research table populated
        ↓
LangGraph triggers Email Strategy Agent
Input to Email Strategy Agent:
  - campaign_id
  - company_research table (type, summary, news hook)
  - job_matches table (matched students and roles)
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
