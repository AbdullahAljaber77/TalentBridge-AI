# Agent 03 — Contact Discovery Agent
### TalentBridge AI — RCP #7
### Team: Abdulmohsen Alghamdi – Osama Alhazmi – Abdullah Aljaber

---

## 1. Overview

The Contact Discovery Agent is the **third agent** in the pipeline. For each target company identified by the Targeting Agent, it finds the most relevant HR contact — the person who should receive the outreach email. It uses a three-step fallback strategy: web search first, Hunter.io second, best guess third. If no contact is found with confidence — it flags the company for human input.

---

## 2. Trigger

```
Targeting Agent completes
        ↓
LangGraph triggers Contact Discovery Agent
Input: campaign_id
```

---

## 3. Input

| Input | Source | Description |
|---|---|---|
| campaign_id | campaigns table | ID of the active campaign |
| company_groups | job_matches table | Grouped (company → students + roles) |
| job_postings | job_postings table | company_name, domain, company_link |
| contacts | contacts table | Previously discovered contacts (cache) |

---

## 4. Output

New or updated rows in `contacts` table in PostgreSQL.

| Field | Type | Description |
|---|---|---|
| contact_id | PK | Auto-generated |
| company_name | TEXT | Target company |
| contact_name | TEXT | HR manager or hiring lead name |
| contact_email | TEXT | Contact email address |
| contact_title | TEXT | Job title of contact |
| contact_verified | BOOLEAN | True if verified, False if best guess |
| contact_source | TEXT | Hunter.io / Web Search / Best Guess |
| confidence_score | FLOAT | Confidence 0.0 - 1.0 |
| last_used_at | TIMESTAMP | When contact was last used |
| created_at | TIMESTAMP | When contact was first discovered |

---

## 5. Tools

| Tool | Purpose |
|---|---|
| `check_contact_cache()` | Check if company contact already exists in DB |
| `validate_cached_contact()` | Verify cached contact is still valid |
| `web_search_contact()` | Search web for HR contact (Tavily — tentative) |
| `parse_contact_from_search()` | LLM extracts contact info from search results |
| `hunter_io_search()` | Query Hunter.io API for verified contacts |
| `build_best_guess_email()` | Construct email patterns from company domain |
| `save_contact()` | Save discovered contact to PostgreSQL |
| `flag_for_human_review()` | Add company to manual review queue in dashboard |
| `update_campaign_progress()` | Update campaigns table |

---

## 6. Tech Stack

| Component | Technology | Alternative |
|---|---|---|
| Agent Framework | LangGraph | — |
| Web Search | Tavily API (tentative) | DuckDuckGo API |
| Contact Verification | Hunter.io API | Apollo.io / Clearbit |
| LLM for parsing | Tentative — Anthropic / OpenAI | — |
| Database | PostgreSQL | — |

---

## 7. Processing Flow

```
STEP 1 — Load company groups for this campaign
  Get unique list of target companies
        ↓
STEP 2 — For each company:

  ── CHECK CACHE ──
  Does contacts table have an entry for this company?
        ↓
  Yes → validate cached contact:
    Re-run web search to confirm contact still exists
    Still valid? → use cached contact → skip to STEP 3
    No longer valid? → proceed to discovery
        ↓
  No → proceed to discovery

  ── DISCOVERY STEP 1: WEB SEARCH ──
  Queries (Tavily — tentative):
    "[company name] HR manager Saudi Arabia email"
    "[company name] talent acquisition hiring contact"
    "[company name] careers recruiter LinkedIn"
        ↓
  LLM parses search results:
    Extracts: name, email, title
    Found with confidence? → ✅ save as Web Search contact
    Not found? → proceed to Hunter.io

  ── DISCOVERY STEP 2: HUNTER.IO ──
  (Alternative: Apollo.io / Clearbit)
  Input: company domain from job_postings table
  Hunter.io returns:
    List of verified emails at that domain
    Name, title, confidence score for each
        ↓
  Filter for HR / Talent / Recruiting titles:
    "HR Manager", "Talent Acquisition", "Recruiter"
    "People & Culture", "Human Resources Director"
        ↓
  Found? → ✅ save as Hunter.io contact (verified = True)
  Not found? → proceed to best guess

  ── DISCOVERY STEP 3: BEST GUESS ──
  Build email patterns from company domain:
    hr@{domain}
    careers@{domain}
    talent@{domain}
    recruitment@{domain}
        ↓
  Save as Best Guess contact (verified = False)
  ⚠️ NEVER send automatically to best guess contacts
  Always escalate to human approval queue with warning:
    "Best guess email — please verify before sending"
  Human must confirm, edit, or reject before any email is sent

  ── NO CONTACT FOUND ──
  If domain is also missing:
    Flag company as "Contact Needed"
    Add to manual review queue in dashboard
    Human fills contact manually before email is sent

STEP 3 — Save contact to PostgreSQL
STEP 4 — Update campaign progress
```

---

## 8. Contact Validation Logic

When a cached contact is found — we validate it before reusing:

```
cached contact: john.smith@aramco.com
        ↓
Web search: "John Smith Aramco HR Manager"
        ↓
Still appears in recent results? → ✅ valid — reuse
No longer found? → ❌ invalid — re-discover
        ↓
Update contacts table:
  valid   → update last_used_at
  invalid → set contact_verified = False
            trigger re-discovery
```

---

## 9. HR Title Filter Keywords

When parsing Hunter.io or web search results — we prioritize contacts with these title keywords:

```python
hr_title_keywords = [
    "hr", "human resources", "talent", "recruiter",
    "recruiting", "recruitment", "hiring", "people",
    "culture", "workforce", "staffing", "headhunter",
    "acquisition", "resourcing"
]
```

If no HR-specific contact is found — fall back to general management contacts.

---

## 10. Contact Source Confidence

| Source | contact_verified | confidence_score | Approval Warning |
|---|---|---|---|
| Hunter.io | True | 0.85 - 1.0 | None |
| Web Search | False | 0.50 - 0.84 | ⚠️ Verify recommended |
| Best Guess | False | 0.10 - 0.49 | ⚠️ Best guess — please verify |
| Human Input | True | 1.0 | None |

---

## 11. Example

### Input
```
Company: TAM Development Co.
Domain: sa.indeed.com (job board — not useful)
        → agent falls back to web search for real domain
```

### Web Search
```
Query: "TAM Development Co HR manager Saudi Arabia email"
Result: "Contact TAM's talent team at careers@tam.com.sa"
        ↓
LLM extracts:
  contact_email: careers@tam.com.sa
  contact_name: Not found
  contact_title: Talent Team
  source: Web Search
  confidence: 0.65
```

### Output — contacts table row
```
company_name    : TAM Development Co.
contact_name    : NULL
contact_email   : careers@tam.com.sa
contact_title   : Talent Team
contact_verified: False
contact_source  : Web Search
confidence_score: 0.65
```

### Approval Queue Warning
```
Email to: careers@tam.com.sa
Company: TAM Development Co.
⚠️ Web Search contact — verification recommended
```

---

## 12. Dashboard — Manual Review Queue

When a company is flagged as "Contact Needed" — it appears in the dashboard:

```
┌─────────────────────────────────────────────────┐
│  ⚠️  CONTACTS NEEDED — 3 companies              │
├─────────────────────────────────────────────────┤
│  SWATX              [Enter contact email]  ✅   │
│  Rawafid            [Enter contact email]  ✅   │
│  XYZ Technologies   [Enter contact email]  ✅   │
└─────────────────────────────────────────────────┘
```

Human fills in the contact → saved to contacts table → email generation proceeds.

---

## 13. Edge Cases

| Edge Case | Handling |
|---|---|
| Company domain is job board (sa.indeed.com) | Ignore job board domain — use web search to find real domain |
| Hunter.io returns no results | Proceed to best guess |
| Hunter.io API limit reached | Fall back to web search only for remaining companies |
| Web search returns no useful results | Proceed to Hunter.io |
| Company has multiple HR contacts | Pick highest confidence score with HR title |
| Contact email exists but name missing | Save email only — name left NULL |
| Same email found for different companies | Save separately — one row per company |
| Human skips manual review | Company stays flagged — no email sent until contact added |

---

## 14. Database Tables

> See **TalentBridge_AI_Database_Schema.md** for full table definitions.

This agent reads from:
- `job_matches` — company groups
- `job_postings` — company domain
- `contacts` — cached contacts

This agent writes to:
- `contacts` — discovered or updated contacts
- `campaigns` — progress updates

### Fields updated in campaigns table:

| Field | Updated When |
|---|---|
| `status` | Start → "discovering contacts" |
| `last_updated` | After each company processed |
| `completed_at` | When all companies processed |

---

## 15. Pseudocode

```python
def contact_discovery_agent(campaign_id: int):

    companies = db.get_company_groups(campaign_id)

    for company in companies:

        # Step 1 — Check cache
        cached = db.get_contact(company.company_name)

        if cached:
            valid = validate_contact(cached, company.company_name)
            if valid:
                db.update_last_used(cached.contact_id)
                continue

        # Step 2 — Web search
        results = web_search(
            f"{company.company_name} HR manager Saudi Arabia email"
        )
        contact = llm_parse_contact(results)

        if contact:
            db.save_contact(
                company_name     = company.company_name,
                contact_verified = False,
                contact_source   = "Web Search",
                **contact
            )
            continue

        # Step 3 — Hunter.io
        domain = get_real_domain(company.company_name)
        results = hunter_io_search(domain)
        contact = filter_hr_contacts(results)

        if contact:
            db.save_contact(
                company_name     = company.company_name,
                contact_verified = True,
                contact_source   = "Hunter.io",
                **contact
            )
            continue

        # Step 4 — Best guess
        domain = get_real_domain(company.company_name)
        if domain:
            guess_email = f"hr@{domain}"
            db.save_contact(
                company_name     = company.company_name,
                contact_email    = guess_email,
                contact_verified = False,
                contact_source   = "Best Guess",
                confidence_score = 0.2
            )
        else:
            # Flag for human
            db.flag_contact_needed(company.company_name, campaign_id)

        db.update_campaign_progress(campaign_id)

    return {"status": "complete", "campaign_id": campaign_id}
```

---

## 16. Connection to Next Agent

```
Contact Discovery Agent completes
        ↓
Output: contacts table populated
        ↓
LangGraph triggers Research Agent
Input to Research Agent:
  - campaign_id
  - company_groups (company → students + roles)
  - contacts table (contact details)
```

---

*TalentBridge AI — Agentic AI Bootcamp — SDA / WeCloudData*
