# TalentBridge AI — Milestone 2 Summary
### RCP #7 — Employer Outreach Program Agent
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## Overview

Milestone 2 covers the **Email Generation Agent (Agent 06)** — the agent that turns the upstream pipeline's matches, strategies, research, and contacts into ready-to-review outreach emails. This document summarizes how Agent 06 was built (function by function, tested at each step), the input/output contracts it had to honor with the agents on either side of it, every cross-agent issue surfaced during the build, the design decisions made, and the final verified end-to-end run.

Agent 06 reads from five upstream tables (`email_strategy`, `company_research`, `job_matches`, `contacts`, `student_profiles` + `job_postings`) and writes to a single `emails` table, which the **Campaign Execution Agent (Agent 07)** then consumes for the human approval workflow.

**Status: ✅ Complete — Agent 06 verified end to end on `campaign_id = 2`: 23 emails generated (5 employer + 18 student), 0 errors, all `Pending Approval`.**

---

## Pipeline Flow (where Agent 06 sits)

```
job_matches + contacts (Milestone 1 output)
        ↓
Agent 04 — Research Agent (Osama)        → company_research
Agent 05 — Email Strategy Agent (Abdullah) → email_strategy
        ↓
email_strategy + company_research + job_matches + contacts + student_profiles + job_postings
        ↓
Agent 06 — Email Generation Agent (Abdulmohsen)
  For each company that has student matches:
    • 1 Employer Outreach email  → pitches the whole matched cohort to the HR contact
    • 1 Student Notification email per match → tells each student about a specific job posting
  Each email: assemble context → LLM generate {subject, body} → validate → save as 'Pending Approval'
        ↓
emails table  (status = 'Pending Approval')
        ↓
Agent 07 — Campaign Execution Agent (Abdullah)
  Loads the approval queue, lets a human approve / edit / reject, then sends
```

---

## Build Approach

Agent 06 was built incrementally — one function at a time, each tested in isolation before moving on, mirroring the Milestone 1 discipline. Pure-logic functions were unit-tested with mock data; DB and LLM functions were tested live against `campaign_id = 2`.

| Step | What was built | Type |
|---|---|---|
| 1 | Seed mock `company_research` + `email_strategy` rows (Agents 04/05 not yet run) | SQL |
| 2 | DB loaders: `get_email_strategy`, `get_students_by_ids`; widen `get_job_posting` | DB reads |
| 3 | `normalize_url` + `resolve_application_link` | pure logic |
| 4 | `validate_email` (+ `_email_looks_valid`) | pure logic |
| 5 | `generate_employer_email` (+ `_build_employer_roster`, `EMPLOYER_SYSTEM`) | LLM |
| 6 | `generate_student_email` (+ `STUDENT_SYSTEM`) | LLM |
| 7 | `save_email` | DB write |
| 8 | `update_campaign_progress` | DB write |
| 9 | `email_generation_agent` orchestrator | orchestration |
| 10 | Full end-to-end run + verification on campaign 2 | test |

---

## Input / Output Contracts

These were confirmed by reading the **actual code** of Agents 05 and 07 (not the spec docs), because the live schema had already drifted from the docs twice.

### Inputs Agent 06 reads

| Source | Via | Notes |
|---|---|---|
| `email_strategy` | `get_email_strategy(campaign_id, company)` | `tone` is one of **five** values (`Formal / Conversational / Very Formal / Professional / Friendly`), `angle` is a **free-text composite** (e.g. `"News Hook + Skills Match + Cohort Size"`) — both richer than the schema doc claimed |
| `company_research` | `get_company_research(company)` | `recent_news_hook` and `why_interested` may be NULL |
| `job_matches` | `get_job_matches_for_company(campaign_id, company)` | includes `matched_skills`, `job_title`, `student_id`, `job_id` |
| `contacts` | `get_cached_contact(company)` | placeholders already filtered out by the function |
| `student_profiles` | `get_students_by_ids([...])` | bulk fetch via `= ANY(%s)` |
| `job_postings` | `get_job_posting(job_id)` (widened) | now also returns `apply_link`, `url`, `company_link`, `company_rating` |

### Output Agent 06 writes — and the Agent 07 floor it must clear

Every row written to `emails` must satisfy Agent 07's `validate_email_for_approval()` or Agent 07 marks it failed:

- `recipient_email` non-empty
- `subject` non-empty
- `body` non-empty **and ≥ 20 characters**
- `status = 'Pending Approval'` (so `get_pending_emails()` returns it)

Agent 06 leaves `rejection_reason`, `approved_by`, `approved_at`, `sent_at` NULL — those belong to Agent 07. Note: Agent 07's check is **presence + length only**; it does not validate email *format*, which is why Salla's malformed address passes downstream and is instead surfaced as a warning by Agent 06's own validator.

---

## Schema Fixes & Cross-Agent Items Surfaced

The build surfaced several issues that reach beyond Agent 06. These are listed so they are not lost — most require a teammate or a `database/` change.

| # | Issue | Resolution | Owner / Action |
|---|---|---|---|
| 1 | Table named `email_strategy` (singular) in Neon, but schema doc + `save_email_strategy` referenced `email_strategies` (plural) | Standardized on **`email_strategy`** (the live table); `save_email_strategy` rewritten to target it directly | `database/schema.sql` — confirm singular name |
| 2 | `email_strategy` missing `UNIQUE (campaign_id, company_name)` — Agent 05's `ON CONFLICT` upsert (and our seed) failed with `42P10` | Added the constraint via `ALTER TABLE` | Add to `schema.sql`; benefits Agent 05 |
| 3 | `save_email_strategy` had a `try/except` that silently fell back from plural to singular and swallowed all real errors | Removed the fallback — direct insert, errors now surface | Done (Abdullah's file) |
| 4 | `emails` table has **no `tracking_headers` column**, but Agent 07 tries to write one via `jsonb_build_object` | **Decision pending:** add `ALTER TABLE emails ADD COLUMN tracking_headers jsonb` (recommended) *or* remove from Agent 07 | `database/` + Agent 07 |
| 5 | `build_system_prompt()` hardcoded "TalentBridge AI / training academy" into every agent's prompt | Rebranded to **WeCloudData, a data & AI bootcamp** | `shared/llm.py` — affects all agents, tell teammates |
| 6 | Header names `X-TalentBridge-*` in Agent 07's tracking headers | Rename to `X-WeCloudData-*` for consistency | Agent 07 |
| 7 | `Student` dataclass field named `field` but `get_all_students` constructed `Student(field_of_study=...)` → `TypeError` | Renamed dataclass attribute to `field_of_study` | Done (`shared/models.py`) |
| 8 | `get_job_posting` returned only 6 columns — link/rating fields always NULL | Widened SELECT + constructor to include `apply_link`, `url`, `company_link`, `company_rating` (additive, safe for Agents 01/02) | Done |
| 9 | `Decimal` (Postgres NUMERIC `company_rating`) not JSON-serializable → crash in `call_llm_with_data`'s `json.dumps` | Coerced rating to `float()` in Agent 06; **optional** system-wide hardening: add `default=str` to `json.dumps` in `llm.py` | Done locally; `llm.py` hardening optional |

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Employer email granularity | **One per company** | A single HR contact should receive one message pitching the whole matched cohort, not several emails the same day (deliverability + goodwill) |
| Student email granularity | **One per match (per job posting)** | Each email is about one specific posting with its own apply link and rating |
| Roster coverage | **One entry per `(student, job)` pair** (Option 1) | Guarantees every job posting a company has is represented, even if two postings share a candidate; headline count uses **distinct people** so the email never overclaims |
| Empty `matched_skills` | **Fall back to the student's profile `skills`** | Real data either way; gives the LLM something concrete to reference when Agent 02 stored an empty match-skills list |
| Student email tone | **Own warm/encouraging tone, ignores employer `strategy`** | The strategy tone (e.g. "Very Formal") is calibrated for the *employer*, not for the bootcamp's own graduate |
| Validation | **Hard errors vs. warnings split** | Hard errors (missing subject/recipient, body < 20) block + trigger one regeneration; warnings (malformed address, thin body) let the email through but flag it for the human reviewer |
| Missing contact | **Still generate the email** with a `NEEDED:{company}` placeholder recipient | The email body is the valuable part; the recipient is cheap to fill in later. Placeholder is non-empty so it passes Agent 07's floor and reaches the human queue |
| Apply link | **Resolved in Python**, passed to the LLM as a value or `null` | Stops the model from hallucinating a fake apply URL; `null` triggers the "search the company careers page" wording |
| RAG email templates | **Stubbed (deferred)** | `retrieve_email_template()` left as a default-returning stub until Osama's `rag/retriever.py` exists; swappable without touching anything else |

---

## Functions Built

**In `shared/db.py` (Agent 06 section):**
- `get_email_strategy(campaign_id, company)` — reads the live singular `email_strategy` table
- `get_students_by_ids([ids])` — bulk profile fetch via `= ANY(%s)`, returns dicts
- `save_email(email)` — inserts one record as `Pending Approval`, drops the non-column `validation` key, returns `email_id`
- `update_campaign_progress(campaign_id, status, emails_generated=None)` — status + count + `last_updated` in one round-trip
- **widened** `get_job_posting(job_id)` — now includes the 4 link/rating columns

**Reused (written by teammates, no duplication):** `get_company_research`, `get_job_matches_for_company`, `get_cached_contact`, `get_company_targets_for_contact_discovery`, `fetchone` / `fetchall` / `execute`.

**In `agents/email_generation_agent.py`:**
- `normalize_url(value)` — salvages schemeless URLs (`salla.sa.` → `https://salla.sa`), rejects junk (`N/A`, empty)
- `resolve_application_link(job)` — fallback chain: `apply_link` → `url` → (web search, TODO) → `company_link` → Not Available
- `_email_looks_valid(email)` + `validate_email(email)` — quality gate returning `{valid, errors, warnings}`
- `_build_employer_roster(matches, students)` — joins + one entry per `(student, job)`
- `generate_employer_email(...)` (+ `EMPLOYER_SYSTEM`) — one LLM-generated email per company, validate + one regeneration on failure
- `generate_student_email(...)` (+ `STUDENT_SYSTEM`) — one LLM-generated email per match
- `email_generation_agent(campaign_id)` — orchestrator with per-company error isolation, returns a summary dict

---

## Edge Cases Handled (verified on real data)

| Case | Company | Behavior |
|---|---|---|
| Malformed contact email (trailing dot, unverified) | Salla (`support@salla.sa.`) | Email still generated; `contact_verified=False` carried through; validator raises a **warning**, not a hard error |
| No contact name | Salla | Greeting falls back to "Dear Hiring Team" |
| NULL `company_rating` | SWATX, Foodics, Salla | Rating line omitted entirely — no "rated None/5" |
| No `apply_link` | SWATX, Foodics, Salla | Falls back to the job-posting `url` ("Job Posting" source), no fabricated link |
| Empty `matched_skills` | AECOM | Falls back to the student's profile skills |
| Cross-domain contact emails | Pipecare (`@zoominfo.com`), SWATX (`@noon.com`) | Used as-is from `contacts`; human approval catches wrong recipients |
| Per-candidate accuracy | All | Prompt rule forbids stating one experience range as if it applies to all candidates |

---

## Test Results (Campaign 2)

### Per-company breakdown

| Company | Employer email | Student emails | Contact used | Verified |
|---|---|---|---|---|
| AECOM | 1 | 2 | richard.greenhalgh@aecom.com | ✅ |
| Foodics | 1 | 3 | amy.ahmed@foodics.com | ✅ |
| Pipecare Group | 1 | 5 | rob.pappalardo@zoominfo.com | ✅ (cross-domain) |
| SWATX | 1 | 3 | fharis@noon.com | ✅ (cross-domain) |
| Salla | 1 | 5 | support@salla.sa. | ❌ (malformed, web search) |
| **Total** | **5** | **18** | | |

### Orchestrator summary

```json
{
  "campaign_id": 2,
  "companies": 5,
  "employer_emails": 5,
  "student_emails": 18,
  "total": 23,
  "errors": []
}
```

### Database verification

```
by type:   Employer Outreach = 5,  Student Notification = 18
total:     23
by status: Pending Approval = 23
campaign:  status = 'emails_generated',  emails_generated = 23
```

Code-reported counts matched the database exactly. Subject lines varied correctly by company and email type (formal employer subjects vs. warm "Great News, {name}…" student subjects), confirming the tone split.

---

## Campaign Status Convention (extended)

Agent 06 slots cleanly into the standardized status sequence, between Agent 05's output and Agent 07's queue:

```
...
email_strategies_ready  ← Agent 05 done
generating emails       ← Agent 06 starts
emails_generated        ← Agent 06 done
awaiting approval       ← Agent 07 starts
...
```

---

## Verified End-to-End Result (Campaign 2)

```
✅ Agent 06 — 23 emails generated (5 employer + 18 student) across 5 companies
              0 errors, all rows 'Pending Approval'
              campaign status = 'emails_generated', emails_generated = 23
              clean handoff to Agent 07's approval queue
```

**Milestone 2 (Agent 06) is complete and runs cleanly end to end.**

---

## Outstanding Items / Stretch Goals for Later

- [ ] **Decide on `tracking_headers`** — add the `jsonb` column to `emails` (recommended) or remove the block from Agent 07; rename `X-TalentBridge-*` → `X-WeCloudData-*`
- [ ] **Run Agents 04 & 05 for real** on campaign 2 to replace the mock `company_research` / `email_strategy` seed rows, then re-run Agent 06 against genuine research + strategies
- [ ] **Wire `retrieve_email_template()` to Osama's `rag/retriever.py`** once it exists — insert into the generators with no other changes
- [ ] **Add the web-search step** to `resolve_application_link()` (currently a TODO between `url` and `company_link`) once `tools/web_search.py` is available
- [ ] **Optional `llm.py` hardening** — add `default=str` to `json.dumps` so any `Decimal`/non-serializable value is handled system-wide, not just in Agent 06
- [ ] **Note for real campaigns:** many seeded students use `@synthetic.com` addresses (test data) — Agent 07 would attempt to send to them
- [ ] **Upstream data feedback (Agent 02):** some matches are semantically off (e.g. AI/software graduates → "Contracts Administrator"); Agent 06 reports faithfully, but match quality is worth revisiting
- [ ] **Tune validator thresholds** (`< 150` thin body, `> 120` long subject) if they fire too often/rarely on real Agent 05 strategies
