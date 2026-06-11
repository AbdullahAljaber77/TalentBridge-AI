# TalentBridge AI — Project Progress Log
**RCP #7 — Employer Outreach Program Agent**
**Team:** Abdulmohsen Alghamdi · Osama Alhazmi · Abdullah Aljaber
**Bootcamp:** Agentic AI Bootcamp — SDA / WeCloudData

---

## Phase 1 — Planning & Architecture
> Completed before setup day

### What We Did
- Defined the full system vision — TalentBridge AI, an end-to-end employer outreach automation platform
- Designed a **12-agent pipeline** across 4 milestones, each milestone producing a working demo-ready output
- Created the project name, logo, and branding
- Built a **Google Form** to collect real student profiles from bootcamp participants
- Wrote full requirements documentation covering business context, objectives, agent responsibilities, and tech stack
- Designed the complete **PostgreSQL schema** — 12 normalized tables covering the full lifecycle from job postings to meetings
- Documented all 12 agents with pseudocode, input/output contracts, and LLM prompt strategies
- Assigned agent ownership across the team by milestone

### Agent Pipeline
| Agent | Description | Milestone |
|---|---|---|
| Agent 01 | Job Analysis Agent | M1 |
| Agent 02 | Targeting Agent | M1 |
| Agent 03 | Contact Discovery Agent | M1 |
| Agent 04 | Research Agent | M2 |
| Agent 05 | Email Strategy Agent | M2 |
| Agent 06 | Email Generation Agent | M2 |
| Agent 07 | Campaign Execution Agent | M2 |
| Agent 08 | Inbox Monitoring Agent | M3 |
| Agent 09 | Response Classification Agent | M3 |
| Agent 10 | Follow-Up Agent | M3 |
| Agent 11 | Scheduling Agent | M4 |
| Agent 12 | Reporting Agent | M4 |

### Tech Stack Decided
| Component | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Anthropic Claude API |
| Backend | FastAPI |
| Frontend | Streamlit |
| Database | PostgreSQL (Neon cloud) |
| Vector store | FAISS / Chroma |
| Background jobs | APScheduler |
| Contact discovery | Hunter.io + Tavily web search |

---

## Phase 2 — Setup Day
> Completed June 11, 2026

### 2.1 GitHub Repository
- Cleaned the repository — removed all empty placeholder files created during initialization
- Recreated all folders with `.gitkeep` to preserve folder structure in Git
- Established proper `.gitignore` covering secrets, CSV files, vector DB stores, IDE files, and OS artifacts
- Final structure: `agents/` `api/` `data/` `database/` `docs/` `frontend/` `graph/` `rag/` `shared/` `tests/` `tools/`

### 2.2 Shared Foundation Layer (`shared/`)
Built the four core files every agent will import from:

**`config.py`**
- Loads all environment variables from `.env` using `python-dotenv`
- Exposes API keys for Anthropic, OpenAI, Tavily, Hunter.io, SendGrid
- Validates critical variables at startup with clear warning messages
- Uses `Path(__file__)` to resolve `.env` location regardless of working directory

**`llm.py`**
- Centralized LLM wrapper — no agent calls the Anthropic SDK directly
- `call_llm()` — plain text prompt → text response
- `call_llm_json()` — prompt → parsed JSON dict with automatic markdown fence stripping and retry on parse failure
- `call_llm_with_data()` — structured dict input → JSON response (used by most agents)
- `call_llm_conversation()` — full conversation history → response (used by Scheduling Agent)
- `build_system_prompt()` — consistent system prompt builder for all agents
- Exponential backoff retry logic for rate limits (5s → 10s)
- `required_keys` validation — retries with feedback if JSON is missing expected fields

**`models.py`**
- Typed Python dataclasses for all 12 entities: `Student`, `Campaign`, `JobPosting`, `JobAnalysis`, `JobMatch`, `Contact`, `CompanyResearch`, `EmailStrategy`, `Email`, `Reply`, `FollowUp`, `Meeting`
- `to_date()` utility — converts any date-like value (string, datetime, NaT, None) to `datetime.date`
- Date fields use proper `datetime.date` type instead of strings
- All ID fields are `Optional[int]` to support pre-insert object creation
- Array fields use `List[str]` with `field(default_factory=list)`

**`db.py`**
- Single database connection manager using `psycopg2` context manager
- Query functions for every table — agents never write raw SQL
- Covers: campaigns, job postings, job analysis, student profiles, job matches, contacts, company research, emails, replies
- `health_check()` function to verify connection and row counts

### 2.3 Cloud Database — Neon PostgreSQL
- Provisioned free cloud PostgreSQL database on **Neon** (AWS Europe Central — Frankfurt)
- Chose Frankfurt region for lower latency from Saudi Arabia
- Created all **12 tables** via `schema.sql` run directly in Neon SQL Editor
- Tables include proper indexes, foreign key constraints, cascade deletes, and default values
- All teammates connect to the same database via `DATABASE_URL` in their `.env`

### 2.4 Data Loading

**Job Postings**
- Source: `saudi_job_market_final.csv` — 16,603 real Saudi job postings scraped from Indeed
- Wrote `database/load_jobs.py` with batch insertion (500 rows/batch), full NaN/NaT/null handling, and `dtype=str` to prevent pandas type inference issues
- Successfully loaded all **16,603 job postings** into `job_postings` table
- Added safety confirmation prompt to prevent accidental re-runs

**Student Profiles**
- Source: Google Form responses (20 real submissions) + synthetic generation
- Wrote `database/load_students.py` that:
  - Renames verbose form column names to clean DB column names
  - Drops unused columns (`Timestamp`, `Email Address`)
  - Normalizes names to title case
  - Removes duplicates by email and full name
  - Generates synthetic students to reach 50 total
  - Handles `TEXT[]` array columns (`skills`, `preferred_job_type`, `preferred_location`) correctly
  - Sets `is_mock = False` for real students, `is_mock = True` for synthetic
  - Sets `consent = True` for all form respondents
- Successfully loaded **50 student profiles** (19 real + 31 synthetic)

---

## Current Database State
| Table | Rows | Status |
|---|---|---|
| `job_postings` | 16,603 | ✅ Loaded from CSV |
| `student_profiles` | 50 | ✅ 19 real + 31 synthetic |
| `campaigns` | 0 | ⏳ Agent 01 creates on run |
| `job_analysis` | 0 | ⏳ Agent 01 fills |
| `job_matches` | 0 | ⏳ Agent 02 fills |
| `contacts` | 0 | ⏳ Agent 03 fills |
| `company_research` | 0 | ⏳ Agent 04 fills |
| `email_strategy` | 0 | ⏳ Agent 05 fills |
| `emails` | 0 | ⏳ Agent 06/07 fill |
| `replies` | 0 | ⏳ Agent 08 fills |
| `followups` | 0 | ⏳ Agent 10 fills |
| `meetings` | 0 | ⏳ Agent 11 fills |

---

## Up Next — Milestone 1
> Starting June 12, 2026

- **Agent 01 — Job Analysis Agent** — LLM extracts structured data from job descriptions in batches
- **Agent 02 — Targeting Agent** — keyword + semantic matching of jobs to students, grouped by company
- **Agent 03 — Contact Discovery Agent** — web search + Hunter.io + best-guess email fallback

**Milestone 1 goal:** Job posting goes in → matched students and HR contact come out → saved to PostgreSQL
