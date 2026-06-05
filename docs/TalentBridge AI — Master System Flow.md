# TalentBridge AI — Master System Flow
### RCP #7 — Employer Outreach Program Agent
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. System Overview

TalentBridge AI is a multi-agent system that automates employer outreach for training academies and talent platforms. It connects graduates with employers by running an intelligent pipeline of specialized AI agents — from job discovery to meeting scheduling — while keeping humans in full control at every critical decision point.

---

## 2. System Architecture

```
┌─────────────────────────────────────────────────────┐
│              Streamlit Frontend                      │
│   Campaign Dashboard | Approval Queue | Reports      │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                FastAPI Backend                       │
│         REST API | WebSocket | APScheduler           │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│           Multi-Agent System (LangGraph)             │
│     On-Demand Agents | Background Agents             │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
┌──────▼──────┐ ┌─────▼──────┐ ┌────▼────────────────┐
│ PostgreSQL  │ │ Vector DB  │ │   External APIs      │
│  Database   │ │ Chroma/    │ │  Anthropic | Web     │
│             │ │ FAISS(RAG) │ │  Search | APScheduler│
└─────────────┘ └────────────┘ └─────────────────────┘
```

---

## 3. Data Sources

### 3.1 Job Postings Dataset
- **File:** `saudi_job_market_final.csv`
- **Rows:** 16,603 unique job postings
- **Columns:** 13 clean columns
- **Source:** Scraped from sa.indeed.com

| Column | Description |
|---|---|
| company_name | Target employer name |
| job_title | Role being hired for |
| description_text | Full job description — used for RAG and LLM parsing |
| location | City in Saudi Arabia (English normalized) |
| country | Saudi Arabia or UAE |
| date_posted_parsed | Date job was posted (YYYY-MM-DD) |
| company_rating | Indeed rating 1.0-5.0 |
| company_link | Indeed company page URL |
| domain | Job board source domain |
| apply_link | Direct application URL |
| url | Job posting URL |
| input_discovery_input_domain | Source job board |
| input_discovery_input_keyword_search | Skills searched |

### 3.2 Student Profiles
- **Source:** Google Form responses + mock profiles
- **Fields:** name, email, phone, linkedin, location, status, experience, field, skills, summary, job preferences, salary expectation, availability, cv_url

### 3.3 RAG Knowledge Base
| Source | Used For |
|---|---|
| Job postings dataset | Semantic job matching |
| Student profiles | Student-job alignment |
| Email templates | Email generation |
| Outreach playbooks | Email strategy |
| Past outreach results | Strategy optimization |

---

## 4. Agent Roster

### On-Demand Agents
Activated when human starts a campaign. Run sequentially through LangGraph pipeline.

| Agent | Responsibility |
|---|---|
| Job Analysis Agent | Parse job postings, extract structured data |
| Targeting Agent | Match jobs to student profiles |
| Contact Discovery Agent | Find HR manager or hiring lead |
| Research Agent | Gather company insights via web search |
| Email Strategy Agent | Decide outreach tone and angle |
| Email Generation Agent | Write personalized emails using LLM + RAG |
| Campaign Execution Agent | Manage approval queue and sending |
| Reporting Agent | Generate dashboard and full reports |

### Background Agents (APScheduler)
Run continuously while the system is active.

| Agent | Schedule | Responsibility |
|---|---|---|
| Inbox Monitoring Agent | Every 5 minutes | Check for new employer replies |
| Response Classification Agent | Triggered on new reply | Classify reply as interested / neutral / negative |
| Follow-Up Agent | Every 24 hours | Check who needs follow-up based on configured timing |
| Scheduling Agent | Triggered on interested reply | Propose meeting times and draft scheduling email |

---

## 5. Full System Flow

### Phase 1 — Campaign Setup (Human)

```
Human opens TalentBridge AI dashboard
        ↓
Clicks "Start New Campaign"
        ↓
Fills campaign configuration:
  - Campaign name
  - Select student profiles (all or specific)
  - Select target keywords (from 61 available)
  - Date range filter (how recent are job postings)
  - Follow-up timing (configurable — default 3 days)
        ↓
Clicks "Launch Campaign"
        ↓
System saves campaign to PostgreSQL
        ↓
LangGraph pipeline activates
```

---

### Phase 2 — Job Analysis (Job Analysis Agent)

```
Load job postings from dataset
        ↓
Filter by selected keywords and date range
        ↓
For each job posting:
  LLM extracts structured data from description_text:
    - Required skills
    - Experience level (junior / mid / senior)
    - Job type (full-time / part-time / remote)
    - Key responsibilities
    - Required qualifications
        ↓
Save structured job data to PostgreSQL
```

---

### Phase 3 — Targeting (Targeting Agent)

```
Load structured job data
Load selected student profiles
        ↓
Step 1 — Keyword Matching:
  For each job:
    Check if job skills overlap with student skills
    Score match: number of overlapping skills / total required skills
    Filter: keep jobs with match score > threshold
        ↓
Step 2 — Semantic Matching (RAG):
  Embed student profile into vector space
  Find semantically similar job descriptions in Vector DB
  Re-rank results by semantic similarity score
        ↓
Step 3 — Group by company:
  Multiple matching jobs from same company → one outreach
  Collect ALL matched roles per company
  Highlight top 3 most relevant in email subject/opener
  Reference all matches in email body
        ↓
Output: list of (company, matched_students, all_matched_roles)
Save to PostgreSQL
```

---

### Phase 4 — Contact Discovery (Contact Discovery Agent)

```
For each target company:
        ↓
Step 1 — Check database cache:
  Have we found this company's contact before?
  Yes → use cached contact
  No → proceed to discovery
        ↓
Step 2 — Web search:
  Search: "[company name] HR manager Saudi Arabia"
  Search: "[company name] talent acquisition LinkedIn"
  Search: "[company name] careers contact"
  Found contact? → ✅ use it, flag as "Web Search — verify recommended"
  Not found? → proceed to step 3
        ↓
Step 3 — Hunter.io domain search:
  Input: company domain
  Output: real verified contacts with confidence score
  Found? → ✅ use verified contact
  Not found? → proceed to step 4
        ↓
Step 4 — Best guess patterns:
  Use company domain + common HR email patterns:
    hr@company.com
    careers@company.com
    talent@company.com
  Flag contact as ⚠️ "Best Guess — needs human verification"
        ↓
Step 4 — Save to database:
  contact_name, contact_email, contact_title
  contact_verified: True / False
  contact_source: "Hunter.io" / "Best Guess"
        ↓
Step 5 — Approval queue warning:
  Verified contact   → normal approval flow
  Best guess contact → ⚠️ warning shown to human
                       Human confirms or corrects before sending
```

---

### Phase 5 — Research (Research Agent)

```
For each target company:
        ↓
Web search:
  - What does this company do?
  - Recent news or announcements
  - Company size and industry
  - Hiring activity signals
        ↓
LLM summarizes findings into:
  - Company overview (2-3 sentences)
  - Why they might be interested in our graduates
  - Relevant context for email personalization
        ↓
LLM classifies company type:
  - Large Enterprise
  - Tech Startup
  - Government / Semi-Government
  - Consulting Firm
  - SME / Small Company
        ↓
Save to PostgreSQL:
  - research summary
  - company type classification
  - classification confidence
```

---

### Phase 6 — Email Strategy (Email Strategy Agent)

```
For each target company:
        ↓
RAG retrieves using company type classification:
  - Matching outreach playbook
    (Large Enterprise → formal tone, 5 day follow-up)
    (Tech Startup → conversational, 3 day follow-up)
    (Government → very formal, Vision 2030 angle)
        ↓
RAG retrieves:
  - Similar past outreach results for same company type
        ↓
LLM decides based on playbook + past results:
  - Tone (formal / conversational)
  - Angle (lead with skills / company news / cohort size)
  - Email length
  - Call to action
  - Follow-up timing
        ↓
Output: email strategy object per company
Save to PostgreSQL
```

---

### Phase 7 — Email Generation (Email Generation Agent)

```
For each target company:
        ↓
RAG retrieves:
  - Best matching email template
  - Company research summary
  - Matched student profiles and skills
  - Matched job roles
        ↓
LLM generates TWO emails:

Email 1 — Employer Outreach Email:
  To: HR Manager / Hiring Lead
  Content:
    - Personalized opener referencing company/role
    - Highlight matched student skills
    - Mention number of available graduates
    - Clear call to action
    - Professional sign-off

Email 2 — Student Notification Email:
  To: Matched Student(s)
  Content:
    - Job match found notification
    - Company name and role details
    - Company rating if available
    - Application link (with fallback strategy)
    - Encouragement and next steps
        ↓
Both emails saved to approval queue in PostgreSQL
Status: "Pending Approval"
```

---

### Phase 8 — Human Approval (Campaign Execution Agent)

```
Human opens Approval Queue in dashboard
        ↓
Sees list of pending emails (both employer + student)
        ↓
For each email:
  Human can:
    - ✅ Approve → email marked "Approved"
    - ✏️ Edit → human edits content → then approve
    - ❌ Reject → email marked "Rejected" with reason
        ↓
Campaign Execution Agent processes approved emails:
  Sends employer outreach email
  Sends student notification email
  Updates campaign status in PostgreSQL
  Logs send timestamp
```

---

### Phase 9 — Inbox Monitoring (Background — APScheduler)

```
Every 5 minutes:
        ↓
Inbox Monitoring Agent checks for new replies
(Simulated for MVP — reads from mock reply database)
(Real Gmail API for stretch goal)
        ↓
New reply found?
  Yes → trigger Response Classification Agent
  No  → sleep until next check
```

---

### Phase 10 — Response Classification (Background — APScheduler)

```
Triggered when new reply arrives:
        ↓
LLM reads reply content
        ↓
Classifies as:
  - Interested → wants to learn more / schedule a call
  - Neutral    → asked a question / needs more info
  - Negative   → not hiring / not interested
  - Auto-reply → out of office / automated response
        ↓
Updates employer status in PostgreSQL
        ↓
Triggers appropriate next action:
  Interested → activate Scheduling Agent
  Neutral    → activate Follow-Up Agent with draft answer
  Negative   → mark as closed
  Auto-reply → ignore, keep monitoring
```

---

### Phase 11 — Follow-Up (Background — APScheduler)

```
Every 24 hours:
        ↓
Follow-Up Agent checks all sent emails
        ↓
For each email:
  Days since sent >= configured follow-up timing?
  AND status still "Awaiting Reply"?
        ↓
  Yes → generate follow-up email draft
        Add to approval queue
        Notify human
  No  → skip
```

---

### Phase 12 — Scheduling (Background — APScheduler)

```
Triggered when reply classified as "Interested":
        ↓
Scheduling Agent activates
        ↓
Generates 3 available meeting time slots
        ↓
Drafts scheduling reply email:
  "Thank you for your interest!
   Here are some times that work for us..."
        ↓
Adds to approval queue
        ↓
Human approves → email sent
Employer confirms slot → meeting logged in database
System generates reminder
```

---

### Phase 13 — Reporting (Reporting Agent)

```
Two modes:

Mode 1 — Live Dashboard (always visible):
  Real-time metrics:
    - Total emails sent
    - Replies received
    - Response rate %
    - Interested employers
    - Meetings booked
    - Pipeline status board (Kanban)

Mode 2 — Full Report (on demand):
  Human clicks "Generate Report"
        ↓
  Reporting Agent queries PostgreSQL
        ↓
  Generates full campaign report:
    - Campaign summary
    - Funnel metrics
    - Response breakdown by industry
    - Best performing keywords
    - Top responding companies
    - Student match success rate
    - Recommendations for next campaign
```

---

## 6. Application Link Fallback Strategy

```
Agent needs application link for student email
        ↓
Try apply_link from dataset
  Works (200 response)? → ✅ Use it
  Fails (404)?
        ↓
Try url from dataset
  Works? → ✅ Use it
  Fails or null?
        ↓
Web search:
  "[company] [job title] [location] apply"
  Found fresh link? → ✅ Use it
  Not found?
        ↓
Use company careers page:
  "[company website]/careers"
        ↓
Last resort → send company_link (Indeed page)
```

---

## 7. Database Schema (Overview)

| Table | Purpose |
|---|---|
| campaigns | Campaign config and status |
| job_postings | Cleaned job dataset |
| student_profiles | Student data from form |
| job_matches | Student-job matching results |
| contacts | Discovered HR contacts |
| emails | All generated emails + status |
| replies | Incoming employer replies |
| meetings | Scheduled meetings |
| follow_ups | Follow-up recommendations |
| reports | Generated campaign reports |

---

## 8. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Streamlit |
| Backend | FastAPI |
| Agent Orchestration | LangGraph |
| LLM | Anthropic Claude API |
| RAG | LangChain + Chroma / FAISS |
| Database | PostgreSQL |
| Background Tasks | APScheduler |
| Web Search | Tavily / DuckDuckGo API |
| Email (stretch) | Gmail API / SendGrid |

---

## 9. Human-in-the-Loop Checkpoints

| Checkpoint | What Human Does |
|---|---|
| Campaign Launch | Configure and start campaign |
| Email Approval | Review, edit, approve or reject every email |
| Follow-up Approval | Approve suggested follow-up emails |
| Scheduling Approval | Approve meeting time proposal emails |
| Report Generation | Request full campaign report on demand |

---

## 10. Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| One email per company | ✅ Yes | Avoid spamming same company multiple times |
| Company name normalization | ❌ No | Each company treated independently for now |
| Date filter on job postings | Configurable | Human sets date range per campaign |
| Matching strategy | Keywords + RAG | Best of both worlds |
| Background agents | APScheduler | Simple, effective, no extra infrastructure |
| Approval queue | Single unified queue | Both employer and student emails in one place |
| Follow-up timing | Configurable | Human sets per campaign |
| Reporting | Live dashboard + full report | Real-time visibility + detailed analysis |

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
*Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber*
