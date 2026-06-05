# Agent 05 — Email Strategy Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Email Strategy Agent is the **fifth agent** in the pipeline. For each target company it decides HOW the outreach email should be written — tone, angle, length, and call to action. It retrieves the matching playbook from the RAG Vector DB based on the company type classification from the Research Agent, and learns from past outreach results when available. Its output is a strategy object per company that the Email Generation Agent uses to write the actual email.

---

## 2. Trigger

```
Research Agent completes
        ↓
LangGraph triggers Email Strategy Agent
Input: campaign_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the active campaign |
| company_research | company_research table | Company type, summary, news hook |
| job_matches | job_matches table | Matched students and roles per company |
| playbooks | Vector DB | Outreach playbooks per company type |
| past_results | Vector DB | Past outreach results (mock for first campaign) |

---

## 4. Output

New rows inserted into `email_strategies` table in PostgreSQL.

| Field | Type | Description |
|---|---|---|
| strategy_id | PK | Auto-generated |
| campaign_id | FK → campaigns | Campaign this strategy belongs to |
| company_name | TEXT | Target company |
| tone | TEXT | Formal / Conversational / Very Formal / Professional / Friendly |
| angle | TEXT | Selected angle(s) for email opener |
| email_length | TEXT | Short / Medium / Long |
| call_to_action | TEXT | Fixed CTA from playbook |
| playbook_used | TEXT | Which playbook was retrieved |
| created_at | TIMESTAMP | When strategy was created |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `get_company_research()` | Load company type and research from PostgreSQL |
| `retrieve_playbook()` | RAG query to get matching playbook from Vector DB |
| `retrieve_past_results()` | RAG query to get similar past outreach results |
| `llm_decide_strategy()` | LLM combines playbook + past results into final strategy |
| `save_email_strategy()` | Save strategy object to PostgreSQL |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| RAG | LangChain + Chroma / FAISS | — |
| Embeddings | LangChain Embeddings | — |
| LLM | Tentative — Anthropic / OpenAI | — |
| Database | PostgreSQL | — |

---

## 7. Playbooks

The following playbooks are stored in the Vector DB. They are retrieved based on company type classification from the Research Agent.

---

### Playbook 1 — Large Enterprise
```
Company Type  : Large Enterprise
Tone          : Formal
Email Length  : Medium (100-150 words)
Call to Action: Schedule a 15-minute introductory call

Angle Guidelines:
- Lead with cohort size and track record
- Emphasize quality and training rigor
- Reference company's scale and hiring volume
- Mention specific skills that match their open roles
- If recent news exists — open with it first

Opening Examples:
- "We have a cohort of [X] graduates with [skills] ready to join..."
- "I noticed [company] recently [news hook] — our graduates are..."

Dos:
- Be concise and professional
- Use formal salutation (Dear Mr./Ms.)
- Reference specific role titles

Don'ts:
- Never use casual language
- Never use exclamation marks
- Never make salary assumptions
```

---

### Playbook 2 — Tech Startup
```
Company Type  : Tech Startup
Tone          : Conversational
Email Length  : Short (under 100 words)
Call to Action: Review student profiles online

Angle Guidelines:
- Lead with specific technical skills — startups care about skills first
- Mention portfolio projects if available
- Show energy and enthusiasm
- If recent news exists — reference it as proof you follow them

Opening Examples:
- "Hey [name], I came across [company] and noticed you're building..."
- "Your recent [news hook] caught our attention — we have engineers..."

Dos:
- Keep it punchy and direct
- Use first name in salutation
- Show genuine interest in what they are building

Don'ts:
- Never be overly formal
- Never write long paragraphs
- Never use corporate buzzwords
```

---

### Playbook 3 — Government / Semi-Government
```
Company Type  : Government / Semi-Government
Tone          : Very Formal
Email Length  : Long (150-200 words)
Call to Action: Schedule a formal meeting

Angle Guidelines:
- Lead with Saudization alignment and Vision 2030
- Emphasize certifications, qualifications, and bootcamp credibility
- Reference national talent development initiatives
- If recent news exists — reference government announcements

Opening Examples:
- "In alignment with Vision 2030's workforce development goals..."
- "We are proud to present Saudi national graduates trained in..."

Dos:
- Use very formal salutation (Dear Dr./Eng./H.E.)
- Mention Saudization percentage if relevant
- Reference bootcamp accreditation
- Longer emails are acceptable

Don'ts:
- Never use casual or conversational tone
- Never rush the call to action
- Never omit credentials and qualifications
```

---

### Playbook 4 — Consulting Firm
```
Company Type  : Consulting
Tone          : Professional
Email Length  : Medium (100-150 words)
Call to Action: Schedule a 15-minute introductory call

Angle Guidelines:
- Lead with analytical and problem-solving skills
- Emphasize client-facing and communication abilities
- Mention versatility across industries
- If recent news exists — reference their latest project or expansion

Opening Examples:
- "Consulting firms like [company] need talent that..."
- "We noticed [company] is expanding into [area] — our graduates..."

Dos:
- Be sharp and precise — consultants value clarity
- Highlight soft skills alongside technical ones
- Reference specific consulting skill sets (data analysis, BI, strategy)

Don'ts:
- Never be vague about skills
- Never ignore soft skills
- Never write overly casual emails
```

---

### Playbook 5 — SME (Small-Medium Enterprise)
```
Company Type  : SME
Tone          : Friendly
Email Length  : Short (under 100 words)
Call to Action: Review student profiles online

Angle Guidelines:
- Lead with immediate availability and readiness to contribute
- Emphasize cost-effectiveness and fresh energy
- Show understanding of SME needs — lean teams, versatile skills
- If recent news exists — show you know their business

Opening Examples:
- "We know growing teams need people who hit the ground running..."
- "Our graduates are ready to contribute from day one — no long..."

Dos:
- Keep it warm and human
- Emphasize flexibility and eagerness
- Use first name in salutation

Don'ts:
- Never sound corporate
- Never overwhelm with credentials
- Never write long formal emails
```

---

## 8. Past Outreach Results — RAG Usage

Past outreach results are stored in the Vector DB as structured records:

```json
{
  "company_type": "Consulting",
  "tone_used": "Professional",
  "angle_used": "Skills Match + News Hook",
  "template_used": "Template B",
  "response": "Interested",
  "days_to_reply": 2,
  "lesson": "Combining skills match with news hook worked well for consulting firms"
}
```

### First Campaign — Mock Past Results
For the first campaign there are no real past results. We pre-populate the Vector DB with **20 mock past outreach records** covering all 5 company types. After the first real campaign — real results replace mock ones automatically.

### How RAG Retrieves Past Results
```
Query: company_type + tone + industry
        ↓
Vector DB returns most similar past results
        ↓
LLM reads lessons learned
        ↓
Adjusts strategy accordingly
```

---

## 9. Processing Flow

```
STEP 1 — Load company list for this campaign
        ↓
STEP 2 — For each company:

  ── LOAD RESEARCH ──
  Get company_type, recent_news_hook, why_interested
  from company_research table
        ↓
  ── RETRIEVE PLAYBOOK ──
  RAG query: company_type
  Returns: matching playbook from Vector DB
        ↓
  ── RETRIEVE PAST RESULTS ──
  RAG query: company_type + industry
  Returns: similar past outreach results
  No results found? → use playbook only (mock data for first campaign)
        ↓
  ── DECIDE ANGLES ──
  recent_news_hook exists? → include News Hook angle
  matched students > 3?   → include Cohort Size angle
  Always include          → Skills Match angle
        ↓
  ── LLM STRATEGY DECISION ──
  LLM reads: playbook + past results + angles available
  LLM produces: final strategy object
        ↓
  ── SAVE STRATEGY ──
  Save to email_strategies table

STEP 3 — Update campaign progress
```

---

## 10. LLM Prompt

```
System:
You are an expert email campaign strategist. Your task is to
decide the best outreach strategy for a company based on their
profile and past outreach performance.
Always respond with valid JSON only.

User:
Decide the outreach email strategy for the following company.

Company: {company_name}
Company Type: {company_type}
Research Summary: {research_summary}
Recent News Hook: {recent_news_hook}
Number of Matched Students: {matched_students_count}
Matched Roles: {matched_roles}

Playbook for {company_type}:
{playbook_content}

Similar Past Results:
{past_results}

Available angles (you may combine):
- Skills Match: lead with specific skills that match their roles
- News Hook: open with recent company news (only if news hook exists)
- Cohort Size: mention number of available graduates

Return a JSON object:
{
  "tone": "Formal | Conversational | Very Formal | Professional | Friendly",
  "angle": "which angles to use and in what order",
  "email_length": "Short | Medium | Long",
  "call_to_action": "exact CTA from playbook",
  "playbook_used": "name of playbook used",
  "strategy_notes": "brief explanation of why this strategy was chosen"
}
```

---

## 11. Example

### Input
```
Company: TAM Development Co.
Company Type: Consulting
News Hook: "TAM recently announced expansion into AI advisory services"
Matched Students: 4
Matched Roles: Data Engineer, AI Engineer, Software Engineer
```

### LLM Output
```json
{
  "tone": "Professional",
  "angle": "News Hook + Skills Match",
  "email_length": "Medium",
  "call_to_action": "Schedule a 15-minute introductory call",
  "playbook_used": "Consulting Playbook",
  "strategy_notes": "Opening with TAM's AI expansion news creates immediate relevance. Following with specific AI and data skills reinforces the match. Medium length appropriate for consulting audience."
}
```

---

## 12. Angle Combination Rules

| Condition | Angles Used |
|---|---|
| News hook exists + students > 3 | News Hook + Skills Match + Cohort Size |
| News hook exists + students ≤ 3 | News Hook + Skills Match |
| No news hook + students > 3 | Cohort Size + Skills Match |
| No news hook + students ≤ 3 | Skills Match only |

---

## 13. Edge Cases

| Edge Case | Handling |
|---|---|
| Company type classification confidence is Low | Default to Large Enterprise playbook |
| No past results found in Vector DB | Use playbook only — no past results adjustment |
| News hook is NULL | Skip News Hook angle automatically |
| Matched students count is 0 | Should not reach this agent — Targeting Agent filters these out |
| LLM returns invalid JSON | Retry once — if still invalid use playbook defaults directly |
| All angles produce conflicting instructions | LLM prioritizes playbook over past results |

---

## 14. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `company_research` — company type and research
- `job_matches` — matched students count and roles
- `campaigns` — campaign configuration
- Vector DB — playbooks and past results

This agent writes to:
- `email_strategies` — strategy per company
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `status` | Start → "strategizing emails" |
| `last_updated` | After each company strategy decided |
| `completed_at` | When all strategies decided |

---

## 15. Pseudocode

```python
def email_strategy_agent(campaign_id: int):

    companies = db.get_unique_companies(campaign_id)

    for company in companies:

        # Load research
        research = db.get_company_research(company.company_name)
        matches  = db.get_job_matches(campaign_id, company.company_name)

        # Retrieve playbook from RAG
        playbook = vector_db.retrieve_playbook(research.company_type)

        # Retrieve past results from RAG
        past_results = vector_db.retrieve_past_results(
            company_type = research.company_type
        )

        # Decide angles
        angles = ["Skills Match"]
        if research.recent_news_hook:
            angles.insert(0, "News Hook")
        if len(matches) > 3:
            angles.append("Cohort Size")

        # LLM strategy decision
        prompt = build_strategy_prompt(
            company        = company,
            research       = research,
            matches        = matches,
            playbook       = playbook,
            past_results   = past_results,
            angles         = angles
        )
        response = call_llm(prompt)
        strategy = parse_json(response)

        # Save strategy
        db.save_email_strategy(
            campaign_id  = campaign_id,
            company_name = company.company_name,
            **strategy
        )

        db.update_campaign_progress(campaign_id)

    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 16. Connection to Next Agent

```
Email Strategy Agent completes
        ↓
Output: email_strategies table populated
        ↓
LangGraph triggers Email Generation Agent
Input to Email Generation Agent:
  - campaign_id
  - email_strategies table (tone, angle, length, CTA)
  - company_research table (summary, news hook)
  - job_matches table (students, roles, skills)
  - contacts table (recipient name and email)
  - student_profiles table (student details for notification email)
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
