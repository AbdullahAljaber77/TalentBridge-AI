# TalentBridge AI — Milestone 1 Summary
### RCP #7 — Employer Outreach Program Agent
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## Overview

Milestone 1 covers the first three agents in the TalentBridge AI pipeline: the Job Analysis Agent (Agent 01), the Targeting Agent (Agent 02), and the Contact Discovery Agent (Agent 03). This document summarizes the integration testing performed after merging all three agents, every bug found, every fix applied, and the final verified end-to-end test results.

**Status: ✅ Complete — all three agents verified end to end on `campaign_id = 2`**

---

## Pipeline Flow

```
job_postings (16,603 rows)
        ↓
Agent 01 — Job Analysis Agent (Osama)
  Filters jobs by keyword + date, sends each description to Claude,
  extracts skills / experience level / job type, saves to job_analysis
        ↓
job_analysis table
        ↓
Agent 02 — Targeting Agent (Abdulmohsen)
  Joins job_analysis + job_postings, scores students via keyword
  overlap + FAISS semantic similarity, filters by experience/location,
  saves top_k matches to job_matches
        ↓
job_matches table
        ↓
Agent 03 — Contact Discovery Agent (Abdullah)
  Groups matches by company, finds HR contact via cache → Hunter.io →
  web search → best guess → human review flag, saves to contacts
        ↓
contacts table
        ↓
✅ Milestone 1 complete — ready for Agent 04+
```

---

## Schema Fixes (Pre-Testing)

Before any code ran, the live Neon schema was compared against the team's mock tables and found out of sync.

| Table | Issue | Fix |
|---|---|---|
| `job_analysis` | Live column `analyzed_at` didn't match spec `processed_at` | `ALTER TABLE ... RENAME COLUMN` |
| `campaigns` | Missing `jobs_failed`, `current_batch`, `total_batches`, `started_at`, `completed_at` | `ALTER TABLE ... ADD COLUMN` (×5) |

Mock tables (`os_job_analysis_mock1`, `os_campaigns_mock1`) were dropped after verification.

---

## Agent 01 — Job Analysis Agent

### Bugs found and fixed

| # | Issue | Root cause | Fix |
|---|---|---|---|
| 1 | `LIMIT %s` with `limit=None` | Fragile reliance on `LIMIT NULL` behavior | Build query conditionally — only append `LIMIT` clause when `limit is not None` |
| 2 | `TEXT[]` insert failure | psycopg2 didn't know Python lists map to PostgreSQL arrays | Added `::text[]` cast in the `INSERT` statement |
| 3 | Campaign marked `complete` even on total failure | No check for `processed == 0` | Added `fail_campaign()` function + check before marking complete |
| 4 | Keyword filter returned 0 jobs | Case-sensitive exact match (`'Python'` vs `'python'` in DB) | Wrapped both sides in `LOWER()` |
| 5 | `experience_level` returned `"Mid (3-5y)"` instead of `"Mid"` | LLM prompt allowed free-form years | Tightened prompt to enforce exactly 4 allowed values, no parentheses |
| 6 | Missing `domain` field | `JobPosting` dataclass didn't include it | Added `domain: Optional[str] = None` |
| 7 | Connection leaks | No `try/finally` around `conn.close()` | Wrapped every db function body in `try/finally` |

### Test results

```
Campaign 2: 5 jobs to analyze in 1 batches.
✓ job 83   (Salla)          — 32 skills, level=Mid
✓ job 59   (SWATX)          — 28 skills, level=Mid
✓ job 67   (Foodics)        — 20 skills, level=Mid
✓ job 1323 (AECOM)          — 15 skills, level=Mid
✓ job 69   (Pipecare Group) — Not specified
Done. processed=5 failed=0
```

All experience levels returned clean (`"Mid"`, `"Not specified"`) — no parenthetical years, confirming the prompt fix.

---

## Agent 02 — Targeting Agent

### Bugs found and fixed

| # | Issue | Root cause | Fix |
|---|---|---|---|
| 1 | Function returned `None` | No `return` statement at the end of `run_targeting_agent()` | Added return dict with `status`, `campaign_id`, `total_matches` |
| 2 | Sentence transformer reloaded every call | `embed_model = SentenceTransformer(...)` instantiated inside the function | Moved to module level, loaded once on import |
| 3 | **0/50 students passed experience filter on every job** | `EXPERIENCE_MAP` used en dash (`–`) while `student_profiles.experience_years` used regular hyphen (`-`) for `"1-2 years"` / `"3-5 years"` | Diagnosed via `repr()` comparison, then corrected the database values: `UPDATE student_profiles SET experience_years = '1-2 years' WHERE experience_years = '1–2 years'` (and same for `3-5 years`) |

### Diagnostic process

A per-filter breakdown script was used to isolate which of the three filters (experience, location, keyword) was killing matches:

```
=== Senior Data Analyst at Salla ===
students passing experience filter : 0/50   ← culprit identified
students passing location filter   : 38/50
students passing keyword filter    : 39/50
```

This confirmed the experience filter was rejecting 100% of students before the en dash bug was found.

### Test results — before fix

```
Senior Data Analyst at Salla        — 0 matches
Data Scientist at SWATX             — 0 matches
Business Analyst at Foodics         — 0 matches
Contracts Administrator at AECOM    — 0 matches
Data Analyst at Pipecare Group      — 5 matches (only job with "Not specified" level)
Total: 5 matches
```

### Test results — after fix

```
Senior Data Analyst at Salla        — 5 matches
Data Scientist at SWATX             — 3 matches
Business Analyst at Foodics         — 3 matches
Contracts Administrator at AECOM    — 2 matches
Data Analyst at Pipecare Group      — 5 matches
Total: 18 matches saved
```

Sample match quality verified in Neon — `semantic_match_score` (FAISS) carried most of the weight given low `keyword_match_score` values (0.000–0.057), which is expected for entry-level student profiles against jobs requiring 15–32 skills.

**Stretch goal flagged (not applied):** rebalance `combined_score()` weights from 50/50 to 30/70 (keyword/semantic) once more student data is available.

---

## Agent 03 — Contact Discovery Agent

### Bugs found and fixed

| # | Issue | Root cause | Fix |
|---|---|---|---|
| 1 | Connection leaks | No `try/finally` in `fetchone()`, `fetchall()`, `execute()` | Wrapped all three in `try/finally` |
| 2 | Hunter.io never tried before web search | `process_company()` called `web_search_contact()` first and returned immediately if found | Reordered: find domain → try Hunter.io first → web search fallback → best guess → human review flag |
| 3 | Invalid campaign status string | `update_campaign_status(campaign_id, "contacts_discovered")` didn't match schema's enum-like convention | Standardized to lowercase phrase pairs across all three agents (see below) |
| 4 | No DB record for human review queue | `process_company()` returned `"contact_needed_human_review"` in the result dict but never wrote to the database | Added `flag_contact_needed()` — inserts a placeholder row with `contact_email = "NEEDED:{company}"` and `contact_source = "Human Input Required"` |
| 5 | Best-guess contacts not flagged for verification | Best guess saved with `contact_verified=False` but no review-queue entry | Added `flag_contact_needed()` call after best-guess save too |
| 6 | `confidence = item.get("confidence") or 80` | `0 or 80` evaluates to `80` — a zero-confidence email would be miscoded as 80% | Replaced with explicit `is not None` check, default lowered to `50` |
| 7 | `max(float(confidence) / 100, 0.85)` | Forced minimum confidence regardless of actual API response | Removed the floor — `round(float(confidence) / 100, 2)` |
| 8 | `contact_verified: True` hardcoded for all Hunter.io results | Didn't reflect whether the email itself was verified | Changed to `item.get("type") == "personal"` |
| 9 | Hardcoded `contact_title` / `confidence_score` in web search results | Same value regardless of email quality found | Title derived from email prefix via lookup map; confidence tiered based on whether prefix matches HR keywords |
| 10 | `psycopg2.errors` on `LIKE 'NEEDED:%'` | `%` in a parameterized query is interpreted as a placeholder | Escaped as `LIKE 'NEEDED:%%'` |
| 11 | `get_cached_contact()` returned placeholder rows | No filter excluding `Human Input Required` / `NEEDED:` rows from being treated as valid cached contacts | Added `AND contact_source != 'Human Input Required' AND contact_email NOT LIKE 'NEEDED:%%'` |

### Key dataset finding

All four domain-related columns (`domain`, `company_link`, `url`, `input_discovery_input_domain`) in `job_postings` point to `sa.indeed.com` — the entire dataset was scraped from Indeed Saudi Arabia. `extract_domain()` correctly blocks all of these as job-board domains, meaning `find_real_domain()` always falls through to Tavily web search for the real company domain. This is expected behavior and was documented inline in the code rather than treated as a bug.

### Test results

With no Tavily/Hunter.io API keys configured (both blank in `.env`), every company correctly fell through the entire fallback chain and was flagged for human review:

```
AECOM           → contact_needed_human_review
Foodics         → contact_needed_human_review
Pipecare Group  → contact_needed_human_review
SWATX           → contact_needed_human_review
Salla           → contact_needed_human_review
```

Verified in Neon — all 5 companies present in `contacts` with `contact_source = 'Human Input Required'`, `contact_email = 'NEEDED:{company}'`, `confidence_score = 0.0`.

**Next step:** sign up for free-tier Tavily and Hunter.io API keys to test the full discovery chain with real results.

---

## Campaign Status Convention (Standardized Across All 3 Agents)

To make campaign progress meaningful on the dashboard, all three agents now update `campaigns.status` with consistent before/after phrase pairs:

```
pending               ← campaign created by human
analyzing jobs        ← Agent 01 starts
jobs analyzed         ← Agent 01 done
matching students     ← Agent 02 starts
students matched      ← Agent 02 done
discovering contacts  ← Agent 03 starts
contacts discovered   ← Agent 03 done
complete              ← full pipeline done
failed                ← something went wrong
```

---

## Database Hygiene Issues Found

| Issue | Fix |
|---|---|
| En dash (`–`) vs hyphen (`-`) in `student_profiles.experience_years` | Updated via `UPDATE` statements; `EXPERIENCE_MAP` in `targeting_agent.py` corrected to match |
| Connection leaks across all db helper functions (Agent 01 + 03) | Standardized `try/finally` pattern adopted project-wide |
| `wrong venv` causing confusing `pip show` results | Confirmed correct venv activation before installing packages |

---

## Verified End-to-End Result (Campaign 2)

```
✅ Agent 01 — 5 jobs analyzed, 0 failed, clean experience_level values
✅ Agent 02 — 18 matches saved across 5 jobs, all filters working correctly
✅ Agent 03 — 5 companies processed, all correctly flagged for human review
              (expected outcome with no API keys configured)
```

**Milestone 1 is complete and the pipeline runs cleanly end to end.**

---

## Outstanding Items / Stretch Goals for Later

- [ ] Obtain Tavily and Hunter.io API keys and retest Agent 03's full discovery chain
- [ ] Consider rebalancing `combined_score()` weights (keyword 0.5/0.5 → 0.3/0.7 semantic) once more diverse student/job data is available
- [ ] Wrap `run()` / `run_targeting_agent()` / `contact_discovery_agent()` in FastAPI `BackgroundTasks` so the "Launch Campaign" button doesn't block on long-running jobs
- [ ] Wire the three agents into the LangGraph `graph/pipeline.py` state machine for automatic sequential triggering
- [ ] Add `build_best_guess_emails()` (plural, multiple prefixes) as a stretch goal beyond the single `hr@{domain}` guess
