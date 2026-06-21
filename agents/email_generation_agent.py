from shared.llm import call_llm_with_data, build_system_prompt
from shared.db import (
    get_company_targets_for_contact_discovery,
    get_email_strategy, get_company_research, get_cached_contact,
    get_job_matches_for_company, get_students_by_ids, get_job_posting,
    save_email, update_campaign_progress,
)

JUNK_URL_VALUES = {"", "-", "n/a", "na", "none", "null", "not found",
                   "not available", "tbd", "pending"}

LENGTH_GUIDANCE = {
    "Short":  "about 60-100 words",
    "Medium": "about 110-150 words",
    "Long":   "about 160-200 words",
}

EMPLOYER_SYSTEM = build_system_prompt(
    role="employer outreach email writer",
    instructions=(
        "Write a concise, personalized B2B outreach email to an employer's hiring "
        "contact, proposing graduates whose skills match the company's open roles.\n"
        "Rules:\n"
        "- Choose the opening hook in this priority order, using the first that is "
        "available: (1) recent_news_hook, (2) why_interested, (3) the company profile "
        "in company_research. (4) If none of those are provided, open directly from the "
        "matched candidates — e.g. that strong graduates have been identified whose "
        "skills align with roles at the company.\n"
        "- If contact_name is provided, address them by name (e.g. 'Dear Mr. Greenhalgh'); "
        "if it is null, use 'Dear Hiring Team'.\n"
        "- Reference the matched candidates concretely (the roles they fit and 2-3 key "
        "skills), but summarize naturally — do NOT paste a raw list.\n"
        "- Match the requested tone and the length_guidance.\n"
        "- Close by inviting the reader to take the action described in "
        "call_to_action, phrased naturally as part of a sentence (e.g. 'Would you "
        "be open to a 15-minute introductory call?'). Convey that exact action, but "
        "do NOT paste the call_to_action text verbatim as a standalone line or label.\n"
        "- Close with a brief professional sign-off (e.g. 'Best regards').\n"
        "- Be precise per candidate: experience level and skills differ between "
        "candidates. Never state a single experience range as if it applies to all of "
        "them. Either attribute experience to each candidate individually, or omit "
        "experience entirely — never generalize it.\n"
        "- The matched_candidates list may include the same person more than once when "
        "they fit multiple roles. Use candidate_count (distinct people) for any headline "
        "number — never imply there are more people than candidate_count. When a person "
        "appears for multiple roles, you may mention their roles together rather than "
        "repeating their full profile.\n"
        "- Use only facts present in the data. Never output placeholders like [Name] or [Company].\n"
        "Return JSON with exactly two keys: 'subject' and 'body'."
    ),
)

STUDENT_SYSTEM = build_system_prompt(
    role="career advisor writing to a bootcamp graduate",
    instructions=(
        "Write a warm, encouraging email notifying a graduate that they have been "
        "matched to a specific job opening. Keep it personal and motivating, not corporate.\n"
        "Rules:\n"
        "- Greet the student by first name (e.g. 'Hi Ahmed,').\n"
        "- Share the good news: they matched with the company (company_name) for the "
        "role (job_title).\n"
        "- Briefly say why they're a good fit, referencing 2-3 of their relevant skills "
        "and their field. Be genuine, not flattering.\n"
        "- Include the job details that are present: role title and location. Mention "
        "company_rating ONLY if it is provided and not null; if it is null, do not "
        "mention any rating at all.\n"
        "- Application link: if application_link is provided, include it clearly as where "
        "to apply. If application_link is null, do NOT invent a link — instead encourage "
        "the student to search for the company's careers page and look for the role there.\n"
        "- Keep it concise (about 90-140 words).\n"
        "- Close warmly and sign off as 'The WeCloudData Team'.\n"
        "- Use only facts present in the data. Never output placeholders like [Name].\n"
        "Return JSON with exactly two keys: 'subject' and 'body'."
    ),
)

def normalize_url(value):
    """
    Turn a raw link field into a usable URL, or None if it can't be salvaged.
      - None / non-string / whitespace / known junk      -> None
      - already has an http(s) scheme                     -> returned as-is
      - schemeless but domain-like (has a dot, no spaces) -> https:// prepended
      - anything else (has spaces, no dot)                -> None
    """
    if not isinstance(value, str):
        return None

    cleaned = value.strip().rstrip(".,")          # drop scraping artifacts
    if cleaned.lower() in JUNK_URL_VALUES:
        return None

    if cleaned.lower().startswith(("http://", "https://")):
        return cleaned

    if "." in cleaned and " " not in cleaned:     # bare domain/path -> add scheme
        return "https://" + cleaned

    return None


def resolve_application_link(job) -> dict:
    """
    Pick the best application link for a job, trying fields in priority order.
    Returns {"link": <url or None>, "source": <label>}.

    Priority: apply_link -> url -> (web search, TODO) -> company_link -> none.
    """
    candidates = [
        (job.apply_link,   "Direct Application"),
        (job.url,          "Job Posting"),
        # 3. web-search fallback -> TODO: wire to Osama's tools/web_search.py
        (job.company_link, "Company Page"),
    ]

    for raw, source in candidates:
        link = normalize_url(raw)
        if link:
            return {"link": link, "source": source}

    return {"link": None, "source": "Not Available"}

def _email_looks_valid(email: str) -> bool:
    """Lightweight plausibility check — catches trailing dots, double dots, spaces."""
    e = email.strip()
    if not e or " " in e or e.count("@") != 1:
        return False
    local, _, domain = e.partition("@")
    if not local or not domain or "." not in domain:
        return False
    if domain.startswith(".") or domain.endswith(".") or ".." in e:
        return False
    return True


def validate_email(email: dict) -> dict:
    """
    Quality gate run after generation, before save.
    Returns {"valid": bool, "errors": [...], "warnings": [...]}.

    errors   -> hard fails: block + trigger one regeneration. These mirror
                Agent 07's approval floor, so nothing we save dies downstream.
    warnings -> let it through but attach a note for the human reviewer.
    """
    errors, warnings = [], []

    subject   = (email.get("subject") or "").strip()
    body      = (email.get("body") or "").strip()
    recipient = (email.get("recipient_email") or "").strip()

    # ---- hard errors (Agent 07's floor) ----
    if not subject:
        errors.append("Subject is missing")
    if not recipient:
        errors.append("Recipient email is missing")
    if not body:
        errors.append("Body is missing")
    elif len(body) < 20:
        errors.append(f"Body too short ({len(body)} chars, min 20)")

    # ---- warnings (don't block) ----
    if subject and len(subject) > 120:
        warnings.append(f"Subject is unusually long ({len(subject)} chars)")
    if body and 20 <= len(body) < 150:
        warnings.append(f"Body is short ({len(body)} chars) — may read thin")
    if recipient and not _email_looks_valid(recipient):
        warnings.append(f"Recipient email looks malformed: {recipient}")
    if body and len(body) > 400 and "\n" not in body:
        warnings.append("Body has no paragraph breaks")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}

def _build_employer_roster(matches: list[dict], students: list[dict]) -> list[dict]:
    """
    One entry per (student, job) match, so every job posting a company has is
    represented. A student who matched multiple roles appears once per role.
    """
    by_id = {s["student_id"]: s for s in students}
    roster, seen = [], set()
    for m in matches:                       # matches arrive ordered by score desc
        key = (m["student_id"], m.get("job_id"))
        if key in seen:                     # guard against duplicate match rows
            continue
        seen.add(key)
        s = by_id.get(m["student_id"], {})
        skills = m.get("matched_skills") or s.get("skills") or []
        roster.append({
            "name": s.get("full_name", "A candidate"),
            "field": s.get("field"),
            "experience": s.get("experience_years"),
            "matched_role": m.get("job_title"),
            "matched_skills": skills,
        })
    return roster


def generate_employer_email(campaign_id: int, company_name: str, strategy: dict,
                            research: dict, contact: dict | None,
                            matches: list[dict], students: list[dict]) -> dict:
    """
    One employer-outreach email pitching the matched cohort to the HR contact.
    Always returns an email record. If no contact exists yet, the recipient is a
    'NEEDED:{company}' placeholder so a human can fill it before sending.
    """
    contact = contact or {}          # no contact yet -> still generate the email

    roster = _build_employer_roster(matches, students)
    unique_people = len({m["student_id"] for m in matches})

    data = {
        "company_name":       company_name,
        "company_type":       (research or {}).get("company_type"),
        "company_research":   (research or {}).get("research_summary"),
        "recent_news_hook":   (research or {}).get("recent_news_hook"),
        "why_interested":     (research or {}).get("why_interested"),
        "contact_name":       contact.get("contact_name"),
        "contact_title":      contact.get("contact_title"),
        "tone":               strategy.get("tone"),
        "angle":              strategy.get("angle"),
        "length_guidance":    LENGTH_GUIDANCE.get(strategy.get("email_length"), LENGTH_GUIDANCE["Medium"]),
        "call_to_action":     strategy.get("call_to_action"),
        "candidate_count":    unique_people,
        "opportunity_count":  len(roster),
        "matched_candidates": roster,
    }

    instruction = "Generate a personalized employer outreach email using this context."
    result = call_llm_with_data(
        instruction=instruction, data=data,
        system=EMPLOYER_SYSTEM, required_keys=["subject", "body"],
    )

    email = {
        "campaign_id":      campaign_id,
        "email_type":       "Employer Outreach",
        "company_name":     company_name,
        "recipient_email":  contact.get("contact_email") or f"NEEDED:{company_name}",
        "recipient_name":   contact.get("contact_name"),
        "contact_id":       contact.get("contact_id"),
        "student_id":       None,
        "contact_verified": contact.get("contact_verified", False),
        "subject":          (result.get("subject") or "").strip(),
        "body":             (result.get("body") or "").strip(),
    }

    check = validate_email(email)
    if not check["valid"]:
        result = call_llm_with_data(
            instruction=instruction + f"\n\nThe previous draft failed validation: "
                        f"{check['errors']}. Fix these and ensure a non-empty subject "
                        f"and a body of at least a few sentences.",
            data=data, system=EMPLOYER_SYSTEM, required_keys=["subject", "body"],
        )
        email["subject"] = (result.get("subject") or "").strip()
        email["body"]    = (result.get("body") or "").strip()
        check = validate_email(email)

    email["validation"] = check
    return email

def generate_student_email(campaign_id: int, company_name: str, match: dict,
                           student: dict, job, research: dict = None) -> dict:
    """
    One notification email to a student about a specific matched job posting.
    Resolves the apply link and omits the rating line when rating is null.
    """
    link_info = resolve_application_link(job) if job else {"link": None, "source": "Not Available"}
    skills = match.get("matched_skills") or student.get("skills") or []
    fn = (student.get("full_name") or "").strip()
    first = fn.split()[0] if fn else "there"

    data = {
        "company_name":       company_name,
        "company_blurb":      (research or {}).get("research_summary"),
        "student_first_name": first,
        "student_full_name":  student.get("full_name"),
        "student_field":      student.get("field"),
        "student_skills":     skills,
        "student_experience": student.get("experience_years"),
        "available_to_start": student.get("available_to_start"),
        "job_title":          match.get("job_title") or (job.job_title if job else None),
        "job_location":       (job.location if job else None),
        "company_rating":     float(job.company_rating) if (job and job.company_rating is not None) else None,
        "application_link":   link_info["link"],                        # None -> follow-up
        "application_source": link_info["source"],
    }

    instruction = "Write a personalized job-match notification email to this graduate."
    result = call_llm_with_data(
        instruction=instruction, data=data,
        system=STUDENT_SYSTEM, required_keys=["subject", "body"],
    )

    email = {
        "campaign_id":      campaign_id,
        "email_type":       "Student Notification",
        "company_name":     company_name,
        "recipient_email":  student.get("email"),
        "recipient_name":   student.get("full_name"),
        "contact_id":       None,
        "student_id":       student.get("student_id"),
        "contact_verified": None,
        "subject":          (result.get("subject") or "").strip(),
        "body":             (result.get("body") or "").strip(),
    }

    check = validate_email(email)
    if not check["valid"]:
        result = call_llm_with_data(
            instruction=instruction + f"\n\nThe previous draft failed validation: "
                        f"{check['errors']}. Fix these and ensure a non-empty subject and "
                        f"a body of at least a few sentences.",
            data=data, system=STUDENT_SYSTEM, required_keys=["subject", "body"],
        )
        email["subject"] = (result.get("subject") or "").strip()
        email["body"]    = (result.get("body") or "").strip()
        check = validate_email(email)

    email["validation"] = check
    return email

def email_generation_agent(campaign_id: int) -> dict:
    """
    Agent 06 orchestrator. For each company with student matches in this campaign,
    generate one employer outreach email plus one student notification per match,
    save them all as 'Pending Approval', and report a summary.

    One company failing does not stop the run — its error is logged and the rest proceed.
    """
    update_campaign_progress(campaign_id, "generating emails")

    companies = get_company_targets_for_contact_discovery(campaign_id)

    summary = {
        "campaign_id": campaign_id,
        "companies": 0,
        "employer_emails": 0,
        "student_emails": 0,
        "total": 0,
        "errors": [],
    }

    for row in companies:
        company = row["company_name"]
        summary["companies"] += 1
        try:
            strategy = get_email_strategy(campaign_id, company)
            research = get_company_research(company)
            contact  = get_cached_contact(company)

            matches  = get_job_matches_for_company(campaign_id, company)
            students = get_students_by_ids([m["student_id"] for m in matches])
            students_by_id = {s["student_id"]: s for s in students}

            # 1 employer email for the whole company
            employer = generate_employer_email(
                campaign_id, company, strategy, research, contact,
                matches, list(students_by_id.values()),
            )
            save_email(employer)
            summary["employer_emails"] += 1

            # 1 student email per match (per job posting)
            for m in matches:
                student = students_by_id.get(m["student_id"])
                if not student:
                    summary["errors"].append(f"{company}: no profile for student {m['student_id']}")
                    continue
                job = get_job_posting(m["job_id"])
                student_email = generate_student_email(
                    campaign_id, company, m, student, job, research,
                )
                save_email(student_email)
                summary["student_emails"] += 1

        except Exception as e:
            summary["errors"].append(f"{company}: {type(e).__name__}: {e}")
            continue

    summary["total"] = summary["employer_emails"] + summary["student_emails"]
    update_campaign_progress(campaign_id, "emails generated",
                             emails_generated=summary["total"])
    summary["status"] = "emails generated"
    return summary
