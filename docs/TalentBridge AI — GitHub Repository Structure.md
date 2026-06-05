# TalentBridge AI — GitHub Repository Structure
### RCP #7 — Employer Outreach Program Agent
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## Repository Name
```
talentbridge-ai
```

---

## Full Structure

```
talentbridge-ai/
│
├── README.md                          ← Project overview, setup instructions, team
├── requirements.txt                   ← All Python dependencies
├── .env.example                       ← Environment variables template (no real keys)
├── .gitignore                         ← Ignore .env, __pycache__, data files
│
├── data/
│   ├── saudi_job_market_final.csv     ← Final cleaned dataset
│   ├── student_profiles.json          ← Mock + real student profiles
│   ├── email_templates/               ← Outreach email templates (text files)
│   │   ├── enterprise_template.txt
│   │   ├── startup_template.txt
│   │   ├── government_template.txt
│   │   ├── consulting_template.txt
│   │   └── sme_template.txt
│   ├── playbooks/                     ← Outreach playbooks per company type
│   │   ├── enterprise_playbook.txt
│   │   ├── startup_playbook.txt
│   │   ├── government_playbook.txt
│   │   ├── consulting_playbook.txt
│   │   └── sme_playbook.txt
│   └── mock_past_results.json         ← Mock historical outreach results for RAG
│
├── database/
│   ├── schema.sql                     ← Full PostgreSQL CREATE TABLE statements
│   ├── seed_data.sql                  ← Insert mock data for testing
│   └── migrations/                    ← Future schema changes
│
├── shared/
│   ├── db.py                          ← All database connection + query functions
│   ├── models.py                      ← All data models (Campaign, Email, Student...)
│   ├── config.py                      ← Settings, API keys loader from .env
│   └── llm.py                         ← LLM call wrapper (Anthropic / OpenAI)
│
├── rag/
│   ├── embeddings.py                  ← Embedding functions
│   ├── vector_store.py                ← Chroma / FAISS setup and query functions
│   ├── indexer.py                     ← Index job postings, student profiles, templates
│   └── retriever.py                   ← RAG retrieval functions used by agents
│
├── agents/
│   ├── job_analysis_agent.py          ← Agent 01
│   ├── targeting_agent.py             ← Agent 02
│   ├── contact_discovery_agent.py     ← Agent 03
│   ├── research_agent.py              ← Agent 04
│   ├── email_strategy_agent.py        ← Agent 05
│   ├── email_generation_agent.py      ← Agent 06
│   ├── campaign_execution_agent.py    ← Agent 07
│   ├── inbox_monitoring_agent.py      ← Agent 08
│   ├── response_classification_agent.py ← Agent 09
│   ├── followup_agent.py              ← Agent 10
│   ├── scheduling_agent.py            ← Agent 11
│   └── reporting_agent.py             ← Agent 12
│
├── tools/
│   ├── web_search.py                  ← Tavily / DuckDuckGo web search tool
│   ├── hunter_io.py                   ← Hunter.io contact discovery tool
│   ├── email_sender.py                ← Simulated / real email sending tool
│   ├── pdf_exporter.py                ← PDF report generation tool
│   └── link_validator.py              ← URL validation for apply links
│
├── graph/
│   ├── pipeline.py                    ← LangGraph pipeline — connects all agents
│   ├── background_scheduler.py        ← APScheduler setup for background agents
│   └── state.py                       ← LangGraph shared state definition
│
├── api/
│   ├── main.py                        ← FastAPI app entry point
│   ├── routers/
│   │   ├── campaigns.py               ← Campaign CRUD endpoints
│   │   ├── emails.py                  ← Email approval endpoints
│   │   ├── students.py                ← Student profile endpoints
│   │   ├── reports.py                 ← Report generation endpoints
│   │   └── dashboard.py              ← Live dashboard data endpoints
│   └── middleware/
│       └── auth.py                    ← Basic authentication (optional)
│
├── frontend/
│   ├── app.py                         ← Streamlit main app entry point
│   ├── pages/
│   │   ├── 01_dashboard.py            ← Live campaign dashboard
│   │   ├── 02_new_campaign.py         ← Campaign creation form
│   │   ├── 03_approval_queue.py       ← Email approval workflow
│   │   ├── 04_scheduling.py           ← Meeting scheduling form
│   │   ├── 05_reports.py             ← Campaign reports and PDF download
│   │   └── 06_students.py            ← Student profiles management
│   └── components/
│       ├── email_card.py              ← Reusable email review card component
│       ├── metrics_bar.py             ← Live metrics display component
│       └── pipeline_board.py          ← Kanban pipeline status board
│
├── tests/
│   ├── test_job_analysis_agent.py
│   ├── test_targeting_agent.py
│   ├── test_contact_discovery_agent.py
│   ├── test_email_generation_agent.py
│   ├── test_response_classification_agent.py
│   └── test_reporting_agent.py
│
└── docs/
    ├── TalentBridge_AI_Master_Flow.md
    ├── TalentBridge_AI_Database_Schema.md
    ├── TalentBridge_AI_Bootcamp_Context.md
    ├── TalentBridge_AI_Repo_Structure.md
    ├── Agent_01_Job_Analysis_Agent.md
    ├── Agent_02_Targeting_Agent.md
    ├── Agent_03_Contact_Discovery_Agent.md
    ├── Agent_04_Research_Agent.md
    ├── Agent_05_Email_Strategy_Agent.md
    ├── Agent_06_Email_Generation_Agent.md
    ├── Agent_07_Campaign_Execution_Agent.md
    ├── Agent_08_Inbox_Monitoring_Agent.md
    ├── Agent_09_Response_Classification_Agent.md
    ├── Agent_10_Follow_Up_Agent.md
    ├── Agent_11_Scheduling_Agent.md
    └── Agent_12_Reporting_Agent.md
```

---

## Key Files Explained

---

### `.env.example`
```
# LLM APIs
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/talentbridge

# Search
TAVILY_API_KEY=your_key_here

# Contact Discovery
HUNTER_IO_API_KEY=your_key_here

# Email (stretch goal)
GMAIL_API_KEY=your_key_here
SENDGRID_API_KEY=your_key_here

# App Settings
APP_ENV=development
DEBUG=True
```

---

### `shared/config.py`
```python
import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
DATABASE_URL      = os.getenv("DATABASE_URL")
TAVILY_API_KEY    = os.getenv("TAVILY_API_KEY")
HUNTER_IO_API_KEY = os.getenv("HUNTER_IO_API_KEY")
APP_ENV           = os.getenv("APP_ENV", "development")
```

---

### `shared/models.py`
```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class Campaign:
    campaign_id         : int
    campaign_name       : str
    selected_keywords   : list[str]
    date_range_start    : str
    date_range_end      : str
    campaign_end_date   : str
    followup_days       : int
    inbox_check_minutes : int
    status              : str

@dataclass
class Email:
    email_id        : int
    campaign_id     : int
    email_type      : str
    recipient_email : str
    subject         : str
    body            : str
    status          : str

@dataclass
class Student:
    student_id      : int
    full_name       : str
    email           : str
    skills          : list[str]
    experience_years: str
    location        : str

@dataclass
class Reply:
    reply_id        : int
    email_id        : int
    campaign_id     : int
    company_name    : str
    reply_body      : str
    classification  : str
```

---

### `requirements.txt`
```
# Core
python-dotenv
pandas
sqlalchemy
psycopg2-binary

# AI / Agents
langchain
langgraph
langchain-anthropic
langchain-openai
langchain-community
anthropic
openai

# Vector DB
chromadb
faiss-cpu

# API
fastapi
uvicorn

# Frontend
streamlit

# Search
tavily-python

# Background Tasks
apscheduler

# PDF Export
reportlab

# Testing
pytest

# Utilities
requests
python-dateutil
```

---

### `.gitignore`
```
# Environment
.env

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# Data — large files not in repo
data/saudi_job_market.csv
data/saudi_job_market_cleaned.csv

# Vector DB local files
chroma_db/
faiss_index/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Reports
*.pdf
```

---

## Branching Strategy

```
main
  │
  ├── abdulmohsen/foundation     ← Agents 01-04 + shared/ + database/ + data/ + docs/
  ├── osama/agents               ← Agents 05-07 + rag/ + tools/
  └── abdullah/agents            ← Agents 08-12 + api/ + frontend/
```

### Who Owns What

| Person | Responsibility |
|---|---|
| **Abdulmohsen** | Agents 01-04 + shared/ + database/ + data/ + docs/ |
| **Osama** | Agents 05-07 + rag/ + tools/ |
| **Abdullah** | Agents 08-12 + api/ + frontend/ |

### Rules
- Never push directly to `main`
- Each person works on their own branch
- Open a Pull Request to merge into `main`
- At least one teammate reviews before merging
- Merge order: abdulmohsen/foundation first → osama/agents → abdullah/agents

---

## Setup Instructions (for README)

```bash
# 1. Clone the repo
git clone https://github.com/your-team/talentbridge-ai.git
cd talentbridge-ai

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Fill in your API keys in .env

# 5. Set up database
psql -U postgres -c "CREATE DATABASE talentbridge;"
psql -U postgres -d talentbridge -f database/schema.sql
psql -U postgres -d talentbridge -f database/seed_data.sql

# 6. Run FastAPI backend
uvicorn api.main:app --reload

# 7. Run Streamlit frontend
streamlit run frontend/app.py
```

---

## What Goes in Each Folder — Summary

| Folder | What Goes In |
|---|---|
| `data/` | Dataset, templates, playbooks, mock data |
| `database/` | SQL schema and seed files |
| `shared/` | Database functions, models, config — shared by everyone |
| `rag/` | Vector DB setup, embeddings, retrieval |
| `agents/` | One file per agent |
| `tools/` | Reusable tool functions called by agents |
| `graph/` | LangGraph pipeline, APScheduler, shared state |
| `api/` | FastAPI backend and endpoints |
| `frontend/` | Streamlit pages and components |
| `tests/` | Test files per agent |
| `docs/` | All markdown documentation |

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
*Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber*
