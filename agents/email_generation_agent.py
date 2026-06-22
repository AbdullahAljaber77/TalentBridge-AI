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
        "- Early on (first or second sentence), briefly identify the sender as "
        "reaching out on behalf of WeCloudData, the leading data science and AI "
        "academy whose blended-learning courses have helped thousands of learners "
        "and many enterprises advance their data journeys. Introduce this naturally "
        "and concisely — a brief mention, not a full marketing paragraph.\n"
        "- If contact_name is provided, address them by name (e.g. 'Dear Mr. Greenhalgh'); "
        "if it is null, use 'Dear Hiring Team'.\n"
        "- Describe the matched graduates as a GROUP, not individuals: how many "
        "matched (use candidate_count), the roles or areas they fit, and the main "
        "skill areas across the cohort. Do NOT name individual candidates or give "
        "per-person profiles. This first email opens a conversation, not a pitch of "
        "specific people.\n"
        "- Match the requested tone and the length_guidance.\n"
        "- Close by inviting the reader to take the action described in "
        "call_to_action, phrased naturally as part of a sentence (e.g. 'Would you "
        "be open to a 15-minute introductory call?'). Convey that exact action, but "
        "do NOT paste the call_to_action text verbatim as a standalone line or label.\n"
        "- Close with 'Best regards,' on its own line, followed by the sender "
        "identity line 'The WeCloudData Team'.\n"
        "- Speak about the cohort's experience and skills in general terms. Do not "
        "claim one experience range fits everyone; describe the range broadly or omit "
        "specifics.\n"
        "- A person may match multiple roles, so matched_candidates can list them more "
        "than once. Use candidate_count (distinct people) for any headline number, and "
        "never imply there are more people than candidate_count.\n"
        "- Use only facts present in the data. Never output placeholders like [Name] or [Company].\n"
        "- Write in plain text only. Do not use markdown formatting such as ** for "
        "bold, # headings, or backticks. Do not use em-dashes (—); use commas, "
        "periods, or parentheses instead.\n"
        "Return JSON with exactly two keys: 'subject' and 'body'."
    ),
)

STUDENT_SYSTEM = build_system_prompt(
    role="career advisor writing to a bootcamp graduate",
    instructions=(
        "Write a warm, encouraging email notifying a graduate that our matching system "
        "has identified them as a potential candidate for one or more job openings. "
        "Keep it personal and motivating, not corporate.\n"
        "Rules:\n"
        "- Greet the student by first name (e.g. 'Hi Ahmed,').\n"
        "- Make clear this is a PRELIMINARY, automated match from our system, not a "
        "final decision, interview invitation, or job offer. The company has not "
        "selected them; our system flagged them as a potential fit. Say this kindly so "
        "it stays encouraging.\n"
        "- List every role in 'matches'. For each: company name, role title, location "
        "if present, and the application link if present. If a match's application_link "
        "is null, tell them to search that company's careers page instead of inventing "
        "a link.\n"
        "- Mention a role's company_rating ONLY if provided and not null.\n"
        "- Briefly say why they're a good fit overall, referencing 2-3 of their skills "
        "and their field. Be genuine, not flattering.\n"
        "- Reference WeCloudData naturally as the academy they trained with. Do not "
        "introduce it as unfamiliar; they are already a graduate.\n"
        "- Keep it concise and skimmable. With several roles, present them as a short list.\n"
        "- Close warmly with 'Best regards,' on its own line, followed by "
        "'The WeCloudData Team'.\n"
        "- Use only facts present in the data. Never output placeholders like [Name].\n"
        "- Write in plain text only. Do not use markdown formatting such as ** for "
        "bold, # headings, or backticks. Do not use em-dashes (—); use commas, "
        "periods, or parentheses instead.\n"
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

def generate_student_digest_email(campaign_id: int, student: dict, items: list[dict]) -> dict:
    """One notification per student, covering every role they matched in this campaign."""
    fn = (student.get("full_name") or "").strip()
    first = fn.split()[0] if fn else "there"
    companies = sorted({it["company_name"] for it in items})
    company_label = companies[0] if len(companies) == 1 else f"{len(companies)} companies"

    data = {
        "student_first_name": first,
        "student_field": student.get("field"),
        "student_skills": student.get("skills"),
        "match_count": len(items),
        "matches": items,
    }
    instruction = "Write one notification email to this graduate summarizing all the roles our system matched them to."
    result = call_llm_with_data(instruction=instruction, data=data,
                                system=STUDENT_SYSTEM, required_keys=["subject", "body"])

    email = {
        "campaign_id": campaign_id,
        "email_type": "Student Notification",
        "company_name": company_label,
        "recipient_email": student.get("email"),
        "recipient_name": student.get("full_name"),
        "contact_id": None,
        "student_id": student.get("student_id"),
        "contact_verified": True,
        "subject": (result.get("subject") or "").strip(),
        "body": (result.get("body") or "").strip(),
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
    student_items: dict[int, list[dict]] = {}
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

            employer = generate_employer_email(
                campaign_id, company, strategy, research, contact,
                matches, list(students_by_id.values()),
            )
            save_email(employer)
            summary["employer_emails"] += 1

            for m in matches:
                if m["student_id"] not in students_by_id:
                    summary["errors"].append(f"{company}: no profile for student {m['student_id']}")
                    continue
                job = get_job_posting(m["job_id"])
                link = resolve_application_link(job) if job else {"link": None, "source": "Not Available"}
                student_items.setdefault(m["student_id"], []).append({
                    "company_name":       company,
                    "job_title":          m.get("job_title") or (job.job_title if job else None),
                    "job_location":       (job.location if job else None),
                    "company_rating":     float(job.company_rating) if (job and job.company_rating is not None) else None,
                    "application_link":   link["link"],
                    "application_source": link["source"],
                    "matched_skills":     m.get("matched_skills") or [],
                })

        except Exception as e:
            summary["errors"].append(f"{company}: {type(e).__name__}: {e}")
            continue

    # one digest email per student, across all their matches
    all_students = get_students_by_ids(list(student_items.keys()))
    profiles = {s["student_id"]: s for s in all_students}
    for sid, items in student_items.items():
        student = profiles.get(sid)
        if not student:
            summary["errors"].append(f"student {sid}: no profile")
            continue
        try:
            save_email(generate_student_digest_email(campaign_id, student, items))
            summary["student_emails"] += 1
        except Exception as e:
            summary["errors"].append(f"student {sid}: {type(e).__name__}: {e}")

    summary["total"] = summary["employer_emails"] + summary["student_emails"]
    update_campaign_progress(campaign_id, "emails generated", emails_generated=summary["total"])
    summary["status"] = "emails generated"
    return summary
