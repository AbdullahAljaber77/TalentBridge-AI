# TalentBridge AI — Agent Splits & Milestones

### RCP #7 — Employer Outreach Program Agent

### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## Development Philosophy

We build in **4 milestones** — each milestone delivers a working mini-pipeline that can be demoed independently. All three team members work simultaneously on each milestone — no one waits for another to finish.

Each milestone produces something tangible:

- Not just code — a **working, demonstrable feature**
- Integration happens within each milestone — not at the end
- By milestone 4 — the full system is already integrated

---

---

## Milestone 1 — The Core Pipeline

**Goal: Job posting goes in → matched students and HR contact come out**

```
Job postings dataset
        ↓
Agent 01 — Job Analysis Agent
        ↓
Agent 02 — Targeting Agent
        ↓
Agent 03 — Contact Discovery Agent
        ↓
Output: (company, matched students, HR contact)
```

| Agent                              | Owner           | Responsibility Focus                           |
| ---------------------------------- | --------------- | ---------------------------------------------- |
| Agent 01 — Job Analysis Agent      | **Osama**       | LLM extraction + batching + prompt engineering |
| Agent 02 — Targeting Agent         | **Abdulmohsen** | Keyword + semantic matching + company grouping |
| Agent 03 — Contact Discovery Agent | **Abdullah**    | Web search + Hunter.io + fallback strategy     |

### Milestone 1 Deliverable

```
✅ Load job postings from dataset
✅ LLM extracts structured data from descriptions
✅ Students matched to jobs via keyword + semantic scoring
✅ HR contacts discovered per company
✅ Results saved to PostgreSQL
```

### Milestone 1 Demo

> _"Watch the system read a job posting, match it to our students, and find the HR manager — automatically."_

---

## Milestone 2 — The Email Machine

**Goal: Company researched → strategy decided → personalized email generated → human approves → sent**

```
(company, matched students, HR contact)
        ↓
Agent 04 — Research Agent
        ↓
Agent 05 — Email Strategy Agent
        ↓
Agent 06 — Email Generation Agent
        ↓
Agent 07 — Campaign Execution Agent
        ↓
Output: Approved emails sent
```

| Agent                               | Owner           | Responsibility Focus                                         |
| ----------------------------------- | --------------- | ------------------------------------------------------------ |
| Agent 04 — Research Agent           | **Osama**       | Web search + LLM summarization + company classification      |
| Agent 05 — Email Strategy Agent     | **Abdullah**    | RAG playbook retrieval + angle decision                      |
| Agent 06 — Email Generation Agent   | **Abdulmohsen** | Two LLM prompts + RAG templates + link fallback + validation |
| Agent 07 — Campaign Execution Agent | **Abdullah**    | Approval queue UI + send logic + edit/reject workflow        |

### Milestone 2 Deliverable

```
✅ Company researched and classified
✅ Outreach strategy decided from playbook
✅ Personalized employer email generated
✅ Student notification email generated
✅ Human approval queue working
✅ Email sent (simulated or real)
```

### Milestone 2 Demo

> _"Watch the system research TAM, decide to use a professional tone with a news hook, write a personalized email, present it for approval, and send it."_

---

## Milestone 3 — The Intelligence Layer

**Goal: Campaign running → replies detected → classified → follow-ups triggered**

```
Sent emails
        ↓
Agent 08 — Inbox Monitoring Agent (background)
        ↓
Agent 09 — Response Classification Agent
        ↓
Agent 10 — Follow-Up Agent (background)
        ↓
Output: Replies classified + follow-ups queued
```

| Agent                                    | Owner           | Responsibility Focus                                     |
| ---------------------------------------- | --------------- | -------------------------------------------------------- |
| Agent 08 — Inbox Monitoring Agent        | **Osama**       | APScheduler + tracking headers + duplicate detection     |
| Agent 09 — Response Classification Agent | **Abdulmohsen** | LLM classification + confidence scoring + action routing |
| Agent 10 — Follow-Up Agent               | **Abdullah**    | Timing logic + closure logic + campaign expiry           |

### Milestone 3 Deliverable

```
✅ Inbox monitored every X minutes via APScheduler
✅ Replies matched to campaigns via tracking headers
✅ Replies classified as Interested / Scheduled / Not Interested / Undecided
✅ Confidence scoring with human review for low confidence
✅ Scheduling Agent triggered for interested replies
✅ Follow-up emails generated after X days of no reply
✅ Companies auto-closed after campaign end date
```

### Milestone 3 Demo

> _"Watch a reply arrive, get classified as Interested in seconds, and trigger the scheduling workflow automatically."_

---

## Milestone 4 — The Closing Loop

**Goal: Meetings scheduled → campaign complete → full report generated**

```
Interested replies
        ↓
Agent 11 — Scheduling Agent
        ↓
Campaign completes
        ↓
Agent 12 — Reporting Agent
        ↓
Output: Meetings booked + PDF report downloaded
```

| Agent                       | Owner           | Responsibility Focus                                            |
| --------------------------- | --------------- | --------------------------------------------------------------- |
| Agent 11 — Scheduling Agent | **Osama**       | Human scheduling form + LLM email + meeting lifecycle           |
| Agent 12 — Reporting Agent  | **Abdulmohsen** | Live dashboard + full report + PDF export + LLM recommendations |

### Milestone 4 Deliverable

```
✅ Human fills scheduling form
✅ Professional scheduling email generated and sent
✅ Meeting confirmed when employer replies
✅ Live dashboard always showing real-time metrics
✅ Full campaign report generated on completion
✅ PDF report downloadable
✅ LLM recommendations for next campaign
```

### Milestone 4 Demo

> _"Watch the full campaign report generate — funnel metrics, top keywords, student success rates, and AI recommendations for the next campaign."_

---

## Full Agent Ownership Summary

| Agent    | Description                   | Owner       | Milestone |
| -------- | ----------------------------- | ----------- | --------- |
| Agent 01 | Job Analysis Agent            | Osama       | M1        |
| Agent 02 | Targeting Agent               | Abdulmohsen | M1        |
| Agent 03 | Contact Discovery Agent       | Abdullah    | M1        |
| Agent 04 | Research Agent                | Osama       | M2        |
| Agent 05 | Email Strategy Agent          | Abdullah    | M2        |
| Agent 06 | Email Generation Agent        | Abdulmohsen | M2        |
| Agent 07 | Campaign Execution Agent      | Abdullah    | M2        |
| Agent 08 | Inbox Monitoring Agent        | Osama       | M3        |
| Agent 09 | Response Classification Agent | Abdulmohsen | M3        |
| Agent 10 | Follow-Up Agent               | Abdullah    | M3        |
| Agent 11 | Scheduling Agent              | Osama       | M4        |
| Agent 12 | Reporting Agent               | Abdulmohsen | M4        |

---

## Additional Ownership

| Component                                     | Owner                                   |
| --------------------------------------------- | --------------------------------------- |
| shared/ (db.py, models.py, config.py, llm.py) | Abdulmohsen                             |
| database/ (schema.sql, seed_data.sql)         | Abdulmohsen                             |
| data/ (dataset, templates, playbooks)         | Abdulmohsen                             |
| docs/ (all markdown documentation)            | Abdulmohsen                             |
| rag/ (embeddings, vector store, retriever)    | Osama                                   |
| tools/ (web search, Hunter.io, email sender)  | Osama                                   |
| graph/ (LangGraph pipeline, APScheduler)      | Osama                                   |
| api/ (FastAPI backend, all endpoints)         | Abdullah                                |
| frontend/ (Streamlit pages and components)    | Abdullah                                |
| tests/                                        | All three — each tests their own agents |

---

## Merge Order Per Milestone

```
Milestone 1:
  Abdulmohsen merges shared/ + database/ + data/ first
          ↓
  All three build their M1 agents
          ↓
  Merge: Osama → Abdulmohsen → Abdullah
          ↓
  Integration test M1 end to end

Milestone 2:
  Osama merges rag/ + tools/ first
          ↓
  All three build their M2 agents
          ↓
  Merge: Osama → Abdullah → Abdulmohsen
          ↓
  Integration test M2 end to end

Milestone 3:
  All three build their M3 agents
          ↓
  Merge: Osama → Abdulmohsen → Abdullah
          ↓
  Integration test M3 end to end

Milestone 4:
  All three build their M4 agents
          ↓
  Abdullah merges api/ + frontend/ last
          ↓
  Merge: Osama → Abdulmohsen → Abdullah
          ↓
  Full end to end demo ready
```

---

## Definition of Done Per Agent

Before merging any agent — it must:

- [ ] Read from and write to the correct database tables
- [ ] Handle all edge cases documented in its agent doc
- [ ] Pass its test file in tests/
- [ ] Be reviewed by at least one teammate
- [ ] Work end to end with the agents before and after it

---

_TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData_
_Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber_
