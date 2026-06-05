# Agent 06 — Email Generation Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Email Generation Agent is the **sixth agent** in the pipeline. For each target company it generates two emails — an employer outreach email and a student notification email. It uses the strategy decided by the Email Strategy Agent, company research, matched student profiles, and RAG-retrieved email templates to produce personalized, contextual emails. All generated emails go into the approval queue — no email is sent without human review.

---

## 2. Trigger

```
Email Strategy Agent completes
        ↓
LangGraph triggers Email Generation Agent
Input: campaign_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the active campaign |
| email_strategies | email_strategies table | Tone, angle, length, CTA per company |
| company_research | company_research table | Summary, news hook, why interested |
| job_matches | job_matches table | Matched students and roles per company |
| contacts | contacts table | Recipient name and email |
| student_profiles | student_profiles table | Student details for both emails |
| email_templates | Vector DB | RAG-retrieved email templates |

---

## 4. Output

New rows inserted into `emails` table in PostgreSQL.

| Field | Type | Description |
|---|---|---|
| email_id | PK | Auto-generated |
| campaign_id | FK → campaigns | Campaign this email belongs to |
| email_type | TEXT | Employer Outreach / Student Notification |
| recipient_email | TEXT | Who receives the email |
| recipient_name | TEXT | Recipient name for personalization |
| subject | TEXT | Email subject line |
| body | TEXT | Full email body |
| company_name | TEXT | Target company |
| student_id | FK → student_profiles | Linked student (for notification emails) |
| contact_id | FK → contacts | Linked contact (for employer emails) |
| contact_verified | BOOLEAN | Whether contact is verified |
| status | TEXT | Pending Approval |
| created_at | TIMESTAMP | When email was generated |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `load_strategy()` | Load email strategy for this company |
| `load_company_research()` | Load research summary and news hook |
| `load_matched_students()` | Load matched student profiles and roles |
| `load_contact()` | Load HR contact details |
| `retrieve_email_template()` | RAG query to get best matching template |
| `generate_employer_email()` | LLM generates employer outreach email |
| `generate_student_email()` | LLM generates student notification email |
| `validate_email()` | Check email length, tone, required sections |
| `resolve_application_link()` | Fallback strategy for application links |
| `save_email()` | Save email to approval queue in PostgreSQL |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| LLM | Tentative — Anthropic / OpenAI | — |
| RAG | LangChain + Chroma / FAISS | — |
| Database | PostgreSQL | — |

---

## 7. Employer Outreach Email Structure

```
1. Subject Line
   Personalized, specific, references company or role

2. Personalized Opener
   Based on angle from strategy:
   - News Hook → reference recent company news
   - Skills Match → reference specific matching roles
   - Cohort Size → mention number of available graduates
   - Combined → mix of above

3. Who We Are
   One sentence about the academy/bootcamp

4. What We Have
   Brief summaries of matched students:
   - Name
   - Top 2-3 skills
   - Experience level
   - Availability

5. Call to Action
   Fixed from playbook:
   - "Schedule a 15-minute introductory call"
   - "Review student profiles online"
   - "Schedule a formal meeting"

6. Sign Off
   Name, title, contact info of placement coordinator
```

---

## 8. Student Notification Email Structure

```
1. Subject Line
   "We found a job match for you — [Company] [Role]"

2. Opener
   Congratulate student on being matched

3. Job Details
   - Company name
   - Job title
   - Location
   - Company rating (if available)

4. Why You Are a Match
   Specific skills that matched this role

5. Application Link
   - Link available → show it clearly
   - Link not available → say so honestly:
     "The direct application link is currently unavailable.
      We recommend visiting [company] careers page directly
      or searching [job title] on LinkedIn."

6. Next Steps
   What the student should do next

7. Sign Off
   Academy name and contact
```

---

## 9. Application Link Fallback Strategy

```python
def resolve_application_link(job: JobPosting) -> dict:

    # Try apply_link first
    if job.apply_link and is_valid_url(job.apply_link):
        return {"link": job.apply_link, "source": "Direct"}

    # Try url
    if job.url and is_valid_url(job.url):
        return {"link": job.url, "source": "Job Posting"}

    # Web search for fresh link
    results = web_search(
        f"{job.company_name} {job.job_title} {job.location} apply"
    )
    fresh_link = extract_link(results)
    if fresh_link:
        return {"link": fresh_link, "source": "Web Search"}

    # Use company careers page
    if job.company_link and is_valid_url(job.company_link):
        return {"link": job.company_link, "source": "Company Page"}

    # No link found
    return {"link": None, "source": "Not Available"}
```

---

## 10. LLM Prompt — Employer Outreach Email

```
System:
You are an expert recruitment outreach writer. Your task is to write
a highly personalized employer outreach email on behalf of a training
academy. The email should feel human, specific, and professional.
Never sound like a template. Never use generic phrases.

User:
Write an employer outreach email using the following information.

Company: {company_name}
Contact Name: {contact_name}
Contact Title: {contact_title}
Company Research: {research_summary}
Recent News Hook: {recent_news_hook}
Tone: {tone}
Angle: {angle}
Email Length: {email_length}
Call to Action: {call_to_action}

Matched Students:
{student_summaries}

Matched Roles at This Company:
{matched_roles}

Email Template to Follow:
{retrieved_template}

Academy Sign Off:
Name: {coordinator_name}
Title: {coordinator_title}
Phone: {coordinator_phone}
Email: {coordinator_email}

Requirements:
- Subject line must be specific and personalized
- Opener must feel genuine — not copy-paste
- Student summaries: name, top 2-3 skills, experience, availability
- End with exact call to action provided
- Length: {email_length} — Short under 100 words body,
  Medium 100-150 words, Long 150-200 words
- Language: English only
- Never mention salary or compensation
- Never make promises about student performance

Return the email as JSON:
{
  "subject": "...",
  "body": "..."
}
```

---

## 11. LLM Prompt — Student Notification Email

```
System:
You are a career placement coordinator writing to a student
about a job opportunity that matches their profile.
Be encouraging, clear, and helpful.
Always respond with valid JSON only.

User:
Write a student notification email using the following information.

Student Name: {student_name}
Matched Company: {company_name}
Matched Role: {job_title}
Location: {location}
Company Rating: {company_rating}
Student Matched Skills: {matched_skills}
Application Link: {application_link}
Link Source: {link_source}

Requirements:
- Subject: "We found a job match for you — [company] [role]"
- Mention why student is a good match (specific skills)
- If link_source is "Not Available":
    Say link is unavailable
    Suggest visiting company careers page or LinkedIn search
- If link is available: show it clearly
- Be warm and encouraging
- Language: English only
- End with clear next steps

Return the email as JSON:
{
  "subject": "...",
  "body": "..."
}
```

---

## 12. Example — Employer Outreach Email

### Input
```
Company: TAM Development Co.
Contact: Mohammed Al-Zahrani, HR Manager
Tone: Professional
Angle: News Hook + Skills Match
Length: Medium
CTA: Schedule a 15-minute introductory call
Matched Students: Ahmed (Python, SQL, AI), Sara (Python, Spark, AWS)
Matched Roles: Data Engineer, AI Engineer
News Hook: TAM recently announced expansion into AI advisory services
```

### Generated Email
```
Subject: AI & Data Engineering Talent — Aligned with TAM's AI Expansion

Dear Mohammed,

I noticed TAM recently announced its expansion into AI advisory
services — congratulations on this exciting milestone. I'm reaching
out because we have graduates whose skills align directly with
this direction.

We are the placement team at SDA/WeCloudData, a leading AI and
data bootcamp in Saudi Arabia.

Two of our graduates stand out for TAM:
• Ahmed Al-Rashidi — Python, SQL, Machine Learning — Fresh Graduate,
  available immediately
• Sara Al-Otaibi — Python, Spark, AWS — 1 year experience,
  available within 2 weeks

Both are ready to contribute to your Data Engineer and AI Engineer
openings from day one.

Would you be open to a 15-minute call this week to learn more?

Best regards,
Abdullah Al-Jaber
Talent Placement Manager — SDA/WeCloudData
+966 50 123 4567
abdullah@weclouddata.com
```

---

## 13. Example — Student Notification Email

### Input
```
Student: Ahmed Al-Rashidi
Company: TAM Development Co.
Role: Data Engineer
Location: Riyadh
Rating: 4.1
Matched Skills: Python, SQL
Link: Not Available
```

### Generated Email
```
Subject: We found a job match for you — TAM Development Co. Data Engineer

Hi Ahmed,

Great news — we found a job that matches your profile!

Company: TAM Development Co.
Role: Data Engineer
Location: Riyadh, Saudi Arabia
Company Rating: 4.1 / 5.0 ⭐

Why you are a match:
Your skills in Python and SQL align directly with what TAM is
looking for in this role.

Application:
The direct application link is currently unavailable. We recommend:
• Visiting TAM's careers page directly at tam.com.sa/careers
• Searching "TAM Development Data Engineer" on LinkedIn

Next Steps:
Prepare your CV and a short cover letter highlighting your
Python and SQL experience. Our team has already reached out
to TAM on your behalf — stay tuned for updates!

Best of luck,
SDA/WeCloudData Placement Team
placement@weclouddata.com
```

---

## 14. Email Validation

After generation — before saving to approval queue:

```python
def validate_email(email: dict, strategy: EmailStrategy) -> bool:

    checks = [
        len(email["subject"]) > 0,           # subject not empty
        len(email["subject"]) <= 100,         # subject not too long
        len(email["body"]) > 50,             # body not too short
        strategy.call_to_action in email["body"],  # CTA present
        email["body"].count("\n\n") >= 2,    # has paragraph breaks
    ]

    return all(checks)
```

If validation fails → retry LLM once → if still fails → flag for manual writing.

---

## 15. Edge Cases

| Edge Case | Handling |
|---|---|
| Contact name is NULL | Use generic opener "Dear Hiring Team" |
| No matched students for company | Should not reach this agent — Targeting Agent filters |
| Application link not available | Honest message in student email with alternatives |
| LLM generates email too long | Truncate and retry with explicit word limit |
| LLM generates email too short | Retry with instruction to elaborate |
| CTA missing from generated email | Validation catches it — retry |
| Student has no summary | Use skills list only for personalization |
| company_rating is NULL | Omit rating from student email — do not mention |

---

## 16. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `email_strategies` — tone, angle, length, CTA
- `company_research` — summary, news hook
- `job_matches` — matched students and roles
- `contacts` — HR contact details
- `student_profiles` — student details
- `job_postings` — application links
- Vector DB — email templates

This agent writes to:
- `emails` — all generated emails in approval queue
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `status` | Start → "generating emails" |
| `emails_generated` | After each email pair generated |
| `last_updated` | After each email saved |
| `completed_at` | When all emails generated |

---

## 17. Pseudocode

```python
def email_generation_agent(campaign_id: int):

    companies = db.get_unique_companies(campaign_id)

    for company in companies:

        # Load all inputs
        strategy  = db.get_email_strategy(campaign_id, company.company_name)
        research  = db.get_company_research(company.company_name)
        matches   = db.get_job_matches(campaign_id, company.company_name)
        contact   = db.get_contact(company.company_name)
        students  = db.get_students_for_matches(matches)
        template  = vector_db.retrieve_template(strategy.tone, strategy.angle)

        # Build student summaries
        summaries = [
            f"{s.full_name} — {', '.join(s.skills[:3])} — "
            f"{s.experience_years} — available {s.available_to_start}"
            for s in students
        ]

        # Generate employer email
        employer_prompt = build_employer_prompt(
            company, contact, research, strategy, summaries, template
        )
        employer_response = call_llm(employer_prompt)
        employer_email = parse_json(employer_response)

        if not validate_email(employer_email, strategy):
            employer_response = call_llm(employer_prompt)
            employer_email = parse_json(employer_response)

        db.save_email(
            campaign_id      = campaign_id,
            email_type       = "Employer Outreach",
            recipient_email  = contact.contact_email,
            recipient_name   = contact.contact_name,
            contact_id       = contact.contact_id,
            contact_verified = contact.contact_verified,
            company_name     = company.company_name,
            subject          = employer_email["subject"],
            body             = employer_email["body"],
            status           = "Pending Approval"
        )

        # Generate student notification emails
        for match in matches:
            student = db.get_student(match.student_id)
            job     = db.get_job(match.job_id)
            link    = resolve_application_link(job)

            student_prompt = build_student_prompt(
                student, job, match.matched_skills, link
            )
            student_response = call_llm(student_prompt)
            student_email = parse_json(student_response)

            db.save_email(
                campaign_id     = campaign_id,
                email_type      = "Student Notification",
                recipient_email = student.email,
                recipient_name  = student.full_name,
                student_id      = student.student_id,
                company_name    = company.company_name,
                subject         = student_email["subject"],
                body            = student_email["body"],
                status          = "Pending Approval"
            )

        db.update_campaign_progress(campaign_id, emails_generated=2)

    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 18. Connection to Next Agent

```
Email Generation Agent completes
        ↓
Output: emails table populated — all status = "Pending Approval"
        ↓
LangGraph triggers Campaign Execution Agent
Input to Campaign Execution Agent:
  - campaign_id
  - emails table (all pending approval emails)
  - contacts table (verified status per contact)
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
