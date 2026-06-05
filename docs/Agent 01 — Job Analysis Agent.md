# Agent 01 — Job Analysis Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Job Analysis Agent is the **first agent** that activates when a human launches a campaign. It reads raw job postings from the dataset, filters them based on campaign configuration, and uses an LLM to extract structured intelligence from each job description. Its output feeds directly into the Targeting Agent.

---

## 2. Trigger

```
Human clicks "Launch Campaign"
        ↓
Campaign configuration saved to PostgreSQL
        ↓
LangGraph activates Job Analysis Agent
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | PostgreSQL — campaigns table | ID of the launched campaign |
| selected_keywords | Campaign config | Keywords human selected (from 61 available) |
| date_range | Campaign config | How recent job postings should be |
| job_postings | PostgreSQL — job_postings table | Full cleaned dataset |

---

## 4. Output

New rows inserted into `job_analysis` table in PostgreSQL:

| Field | Type | Description |
|---|---|---|
| job_id | FK → job_postings | Reference to original job posting |
| campaign_id | FK → campaigns | Campaign this analysis belongs to |
| extracted_skills | list[str] | Required technical and soft skills |
| experience_level | str | Junior / Mid / Senior / Not specified |
| job_type | str | Full-time / Part-time / Remote / Hybrid |
| key_responsibilities | list[str] | Top 3-5 responsibilities |
| qualifications_summary | str | Brief summary of required qualifications |
| processed_at | datetime | When this analysis was completed |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `filter_jobs_by_campaign()` | Filter dataset by keywords and date range |
| `batch_jobs()` | Split filtered jobs into batches of 50 |
| `call_llm()` | Send job description to LLM for extraction |
| `parse_llm_response()` | Parse and validate LLM JSON output |
| `save_job_analysis()` | Save extracted fields to PostgreSQL |
| `update_campaign_progress()` | Update campaign status in real time |

---

## 6. Tech Stack

| Component | Technology |
|---|---|
| Agent Framework | LangGraph |
| LLM | Tentative — Anthropic Claude API / OpenAI |
| Database | PostgreSQL |
| Batching | Python — batch size 50, delay between batches |
| Data Loading | Pandas / SQLAlchemy |

---

## 7. Processing Flow

```
STEP 1 — Load campaign configuration
  Read: selected_keywords, date_range, campaign_id
        ↓
STEP 2 — Filter job postings
  From job_postings table:
    WHERE input_discovery_input_keyword_search IN (selected_keywords)
    AND date_posted_parsed >= date_range_start
        ↓
STEP 3 — Check already processed
  Skip jobs already analysed for this campaign
  (avoid re-processing if agent restarts)
        ↓
STEP 4 — Split into batches
  Batch size: 50 jobs per batch
  Delay between batches: 2 seconds
  (avoids API rate limits)
        ↓
STEP 5 — For each batch:
  For each job in batch:
    Send description_text to LLM
    LLM returns structured JSON
    Validate JSON output
    Save to job_analysis table
        ↓
STEP 6 — Update campaign progress
  Update: jobs_processed count in campaigns table
  Signal: Targeting Agent can begin
```

---

## 8. LLM Prompt

```
System:
You are an expert job description analyst. Your task is to extract
structured information from job postings. Always respond with valid
JSON only. No explanation, no markdown, no extra text.

User:
Analyze the following job posting and extract the required information.

Job Title: {job_title}
Company: {company_name}
Description:
{description_text}

Return a JSON object with exactly these fields:
{
  "extracted_skills": ["skill1", "skill2", ...],
  "experience_level": "Junior | Mid | Senior | Not specified",
  "job_type": "Full-time | Part-time | Remote | Hybrid | Not specified",
  "key_responsibilities": ["responsibility1", "responsibility2", ...],
  "qualifications_summary": "brief summary of required qualifications"
}

Rules:
- extracted_skills: list all technical and soft skills mentioned
- experience_level: base this on years of experience required
  Junior = 0-2 years
  Mid = 3-5 years
  Senior = 6+ years
  Not specified = no experience mentioned
- job_type: extract from description if mentioned, else "Not specified"
- key_responsibilities: maximum 5 most important responsibilities
- qualifications_summary: one sentence summary of key qualifications
```

---

## 9. Example

### Input — Raw Job Description
```
Company: TAM Development Co.
Title: Software Engineer

TAM is a Saudi publicly listed company... Key responsibilities:
Design, implement, and maintain scalable software systems using
microservices architecture. Build, deploy, and manage containerized
applications using Docker...
Requirements: 3+ years of experience in software development.
Proficiency in backend programming languages (Python, Ruby, NodeJS).
Strong knowledge of containerization and cloud services (AWS, GCP).
```

### LLM Output — Structured JSON
```json
{
  "extracted_skills": [
    "Python", "Ruby", "NodeJS", "Docker", "AWS",
    "GCP", "microservices", "CI/CD", "SQL", "NoSQL",
    "Kubernetes", "GitHub Actions"
  ],
  "experience_level": "Mid",
  "job_type": "Full-time",
  "key_responsibilities": [
    "Design and implement scalable software systems",
    "Build and manage containerized applications using Docker",
    "Monitor and troubleshoot application performance",
    "Implement security best practices",
    "Collaborate with cross-functional teams"
  ],
  "qualifications_summary": "3+ years backend development experience
  with strong cloud and containerization skills, Arabic and English
  proficiency required."
}
```

---

## 10. Edge Cases

| Edge Case | Handling |
|---|---|
| LLM returns invalid JSON | Retry once → if still invalid → log and skip job |
| Description too short (under 200 chars) | Already filtered out in data cleaning — won't occur |
| Description too long (over 5000 chars) | Truncate to first 3000 chars before sending to LLM |
| LLM rate limit hit | Exponential backoff — wait and retry |
| Job already processed for this campaign | Skip — check processed_at before calling LLM |
| Network error during LLM call | Retry 3 times → mark job as failed → continue batch |
| experience_level not determinable | Default to "Not specified" — never block processing |

---

## 11. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `job_postings` — source job data
- `campaigns` — campaign configuration

This agent writes to:
- `job_analysis` — extracted structured intelligence
- `campaigns` — real-time progress updates

### Fields updated in campaigns table during processing:

| Field | Updated When |
|---|---|
| `status` | Start → "running", End → "complete" or "failed" |
| `total_jobs_found` | After filtering jobs by keyword and date |
| `jobs_processed` | After each job is successfully analysed |
| `jobs_failed` | After each job fails after retries |
| `current_batch` | After each batch starts |
| `total_batches` | After batching is calculated |
| `started_at` | When agent first activates |
| `completed_at` | When all batches finish |
| `last_updated` | After every single job processed |

---

## 12. Pseudocode

```python
def job_analysis_agent(campaign_id: int):

    # Load campaign config
    campaign = db.get_campaign(campaign_id)
    keywords = campaign.selected_keywords
    date_range = campaign.date_range

    # Filter jobs
    jobs = db.get_jobs(
        keywords=keywords,
        date_from=date_range.start,
        exclude_processed=campaign_id
    )

    # Batch jobs
    batches = batch(jobs, size=50)

    for batch in batches:
        for job in batch:
            try:
                # Call LLM
                prompt = build_prompt(job)
                response = call_llm(prompt)

                # Parse and validate
                analysis = parse_json(response)
                validate_analysis(analysis)

                # Save to database
                db.save_job_analysis(
                    job_id=job.job_id,
                    campaign_id=campaign_id,
                    **analysis
                )

                # Update progress
                db.increment_jobs_processed(campaign_id)

            except InvalidJSONError:
                # Retry once
                response = call_llm(prompt)
                analysis = parse_json(response)
                if not analysis:
                    db.log_failed_job(job.job_id, campaign_id)
                    continue

            except RateLimitError:
                # Exponential backoff
                time.sleep(exponential_backoff())
                continue

        # Delay between batches
        time.sleep(2)

    # Signal next agent
    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 13. Connection to Next Agent

```
Job Analysis Agent completes
        ↓
Output: job_analysis table populated
        ↓
LangGraph triggers Targeting Agent
Input to Targeting Agent:
  - campaign_id
  - job_analysis table (extracted skills, experience level)
  - job_postings table (location, company, title)
  - student_profiles table
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
