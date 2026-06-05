# Agent 02 — Targeting Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Targeting Agent is the **second agent** in the pipeline. It takes the structured job analysis output and matches each job to the most relevant student profiles. It uses a two-step matching strategy — keyword matching first, then semantic RAG matching for ranking. Its output is a list of (company, matched students, matched roles) that feeds into the Contact Discovery Agent.

---

## 2. Trigger

```
Job Analysis Agent completes
        ↓
LangGraph triggers Targeting Agent
Input: campaign_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the active campaign |
| job_analysis | job_analysis table | Extracted skills, experience level, job type |
| job_postings | job_postings table | Company name, title, location, links |
| student_profiles | student_profiles table | Student skills, experience, preferences |
| student_vectors | Vector DB (Chroma/FAISS) | Pre-embedded student profiles |

---

## 4. Output

New rows inserted into `job_matches` table in PostgreSQL.

| Field | Type | Description |
|---|---|---|
| match_id | PK | Auto-generated |
| campaign_id | FK → campaigns | Campaign this match belongs to |
| job_id | FK → job_postings | The matched job |
| student_id | FK → student_profiles | The matched student |
| keyword_match_score | float | Ratio of overlapping skills |
| semantic_match_score | float | Vector similarity score 0.0-1.0 |
| overall_match_score | float | Combined final score |
| matched_skills | list[str] | Skills that overlapped |
| matched_at | datetime | When match was created |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `load_job_analyses()` | Load all job analyses for this campaign |
| `load_student_profiles()` | Load all selected student profiles |
| `keyword_match()` | Compare job skills vs student skills |
| `embed_job_description()` | Embed job description into vector space |
| `semantic_search()` | Query vector DB for similar student profiles |
| `calculate_overall_score()` | Combine keyword and semantic scores |
| `group_by_company()` | Group all matches by company |
| `save_job_matches()` | Save matches to PostgreSQL |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology |
|---|---|
| Agent Framework | LangGraph |
| Vector DB | Chroma / FAISS |
| Embeddings | LangChain Embeddings |
| Matching Logic | Python |
| Database | PostgreSQL |

---

## 7. Student Profile Embedding

Before matching runs — every student profile is embedded once and stored in the Vector DB with their metadata:

### Text Representation Built for Each Student
```
Name: Ahmed Al-Rashidi
Field: Data Science / Machine Learning
Experience: Fresh Graduate
Skills: Python, SQL, Machine Learning, LangChain, Pandas
Preferred Job Type: Full-time, Hybrid
Preferred Location: Riyadh, Anywhere in KSA
Summary: Recent bootcamp graduate looking for data roles
```

### Stored in Vector DB as
```json
{
  "vector": [0.23, 0.87, 0.45, ...],
  "metadata": {
    "student_id": 1,
    "name": "Ahmed Al-Rashidi",
    "skills": ["Python", "SQL", "Machine Learning"],
    "experience_years": "No experience",
    "preferred_location": ["Riyadh", "Anywhere in KSA"]
  }
}
```

Student vectors are created once when a student profile is added — not re-created per campaign.

---

## 8. Processing Flow

```
STEP 1 — Load all job analyses for this campaign
        ↓
STEP 2 — Load all selected student profiles
        ↓
STEP 3 — For each job:

  ── KEYWORD MATCHING ──
  Compare job extracted_skills vs each student's skills
  Calculate keyword_match_score:
    matched_skills = intersection(job_skills, student_skills)
    keyword_match_score = len(matched_skills) / len(job_skills)

  Filter: keep students with at least 1 skill match (tentative)
        ↓
  ── EXPERIENCE FILTER ──
  Compare job experience_level vs student experience_years:
    Junior  → Fresh Graduate, Less than 1 year, 1-2 years
    Mid     → 3-5 years
    Senior  → 5+ years
    Not specified → all students pass
        ↓
  ── LOCATION FILTER ──
  If student preferred_location includes job location
  OR student preferred_location includes "Anywhere in KSA"
  → student passes location filter
        ↓
  ── SEMANTIC MATCHING ──
  Embed job description_text into vector
  Query Vector DB for similar student vectors
  Get semantic_match_score for each remaining student
        ↓
  ── SCORE COMBINATION ──
  overall_match_score = (keyword_match_score * 0.5)
                      + (semantic_match_score * 0.5)
        ↓
  Save all matches to job_matches table

STEP 4 — Group by company
  All matched jobs from same company → one group
  Collect all matched students per company
  Collect all matched roles per company
  Rank roles by overall_match_score
        ↓
STEP 5 — Update campaign progress
  Update: campaigns.status, campaigns.last_updated
        ↓
STEP 6 — Signal Contact Discovery Agent
```

---

## 9. Matching Example

### Job
```
Company: Aramco
Title: Data Engineer
Extracted skills: Python, SQL, Spark, Hadoop, AWS
Experience level: Mid
Location: Dhahran
```

### Students

**Ahmed — Fresh Graduate**
```
Skills: Python, SQL, Machine Learning, Pandas
Experience: Fresh Graduate
Location preference: Riyadh, Anywhere in KSA
```
```
Keyword match:
  matched_skills = [Python, SQL]
  keyword_match_score = 2/5 = 0.40

Experience filter:
  Job = Mid, Ahmed = Fresh Graduate
  → Pass (Not a hard filter — tentative)

Location filter:
  Ahmed prefers "Anywhere in KSA" → Pass ✅

Semantic match score: 0.74

Overall score: (0.40 * 0.5) + (0.74 * 0.5) = 0.57 ✅
```

**Sara — 3 Years Experience**
```
Skills: Python, SQL, Spark, Airflow, AWS
Experience: 3-5 years
Location preference: Dammam, Al Khobar
```
```
Keyword match:
  matched_skills = [Python, SQL, Spark, AWS]
  keyword_match_score = 4/5 = 0.80

Experience filter:
  Job = Mid, Sara = Mid → Pass ✅

Location filter:
  Sara prefers Dammam — Dhahran is nearby → Pass ✅

Semantic match score: 0.91

Overall score: (0.80 * 0.5) + (0.91 * 0.5) = 0.855 ✅
```

### Output — job_matches rows
```
campaign_id: 1, job_id: 42, student_id: 1 (Ahmed), overall_score: 0.57
campaign_id: 1, job_id: 42, student_id: 2 (Sara),  overall_score: 0.855
```

---

## 10. Company Grouping Output

After all jobs are processed — grouped by company:

```
Aramco:
  Matched students: Ahmed, Sara, Omar
  Matched roles:
    - Data Engineer        (score: 0.855)
    - Data Analyst         (score: 0.72)
    - AI Engineer          (score: 0.68)
    - Cloud Engineer       (score: 0.61)
  → ONE outreach email mentioning all roles
    highlighting top matches

Microsoft:
  Matched students: Sara, Fatima
  Matched roles:
    - Software Engineer    (score: 0.79)
    - Cloud Architect      (score: 0.71)
  → ONE outreach email
```

---

## 11. Edge Cases

| Edge Case | Handling |
|---|---|
| No students match a job | Skip job — no email generated |
| No jobs match a student | Student gets no notification — log it |
| All students filtered by experience | Experience filter relaxed — pass all (tentative) |
| Same student matches 50 jobs at one company | Group under one company entry — all roles listed |
| Student has no skills listed | Skip keyword matching — go straight to semantic |
| Vector DB query fails | Fall back to keyword matching only |
| Job has no extracted skills | Skip keyword matching — use semantic only |

---

## 12. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `job_analysis` — extracted job intelligence
- `job_postings` — job details
- `student_profiles` — student data
- `campaigns` — campaign configuration
- Vector DB — student embeddings

This agent writes to:
- `job_matches` — all match results
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `status` | Start → "targeting", End → "targeted" |
| `last_updated` | After every job processed |
| `completed_at` | When all jobs matched |

---

## 13. Pseudocode

```python
def targeting_agent(campaign_id: int):

    # Load data
    job_analyses = db.get_job_analyses(campaign_id)
    students = db.get_student_profiles()

    for job in job_analyses:

        matched_students = []

        for student in students:

            # Step 1 — Keyword matching
            matched_skills = set(job.extracted_skills) & set(student.skills)
            keyword_score = len(matched_skills) / max(len(job.extracted_skills), 1)

            # Step 2 — Filter: at least 1 skill match (tentative)
            if len(matched_skills) < 1:
                continue

            # Step 3 — Experience filter
            if not experience_compatible(job.experience_level, student.experience_years):
                continue  # tentative — may relax this

            # Step 4 — Location filter
            if not location_compatible(job.location, student.preferred_location):
                continue

            # Step 5 — Semantic matching
            job_vector = embed(job.description_text)
            semantic_score = vector_db.similarity(job_vector, student.student_id)

            # Step 6 — Combined score
            overall_score = (keyword_score * 0.5) + (semantic_score * 0.5)

            matched_students.append({
                "student_id"           : student.student_id,
                "keyword_match_score"  : keyword_score,
                "semantic_match_score" : semantic_score,
                "overall_match_score"  : overall_score,
                "matched_skills"       : list(matched_skills)
            })

        # Save matches
        for match in matched_students:
            db.save_job_match(
                campaign_id = campaign_id,
                job_id      = job.job_id,
                **match
            )

        db.update_campaign_progress(campaign_id)

    # Group by company
    company_groups = group_matches_by_company(campaign_id)
    db.save_company_groups(campaign_id, company_groups)

    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 14. Connection to Next Agent

```
Targeting Agent completes
        ↓
Output: job_matches table populated
        ↓
LangGraph triggers Contact Discovery Agent
Input to Contact Discovery Agent:
  - campaign_id
  - company_groups (company → students + roles)
  - job_postings table (company_name, domain)
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
