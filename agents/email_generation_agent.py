from shared.llm import call_llm_with_data, build_system_prompt

JUNK_URL_VALUES = {"", "-", "n/a", "na", "none", "null", "not found",
                   "not available", "tbd", "pending"}

LENGTH_GUIDANCE = {
    "Short":  "about 60-100 words",
    "Medium": "about 110-170 words",
    "Long":   "about 180-260 words",
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
        "- End with the exact call_to_action provided.\n"
        "- Close with a brief professional sign-off (e.g. 'Best regards').\n"
        "- Use only facts present in the data. Never output placeholders like [Name] or [Company].\n"
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
    """Join matches->students, one entry per student at their best-scoring role."""
    by_id = {s["student_id"]: s for s in students}
    roster, seen = [], set()
    for m in matches:                       # matches arrive ordered by score desc
        sid = m["student_id"]
        if sid in seen:
            continue
        seen.add(sid)
        s = by_id.get(sid, {})
        skills = m.get("matched_skills") or s.get("skills") or []   # fall back to student's skills
        roster.append({
            "name": s.get("full_name", "A candidate"),
            "field": s.get("field"),
            "experience": s.get("experience_years"),
            "matched_role": m.get("job_title"),
            "matched_skills": skills,
        })
    return roster


def generate_employer_email(campaign_id: int, company_name: str, strategy: dict,
                            research: dict, contact: dict,
                            matches: list[dict], students: list[dict]) -> dict | None:
    """
    One employer-outreach email pitching the matched cohort to the HR contact.
    Returns a ready-to-save email record, or None if there is no real contact.
    """
    if not contact:
        return None

    roster = _build_employer_roster(matches, students)

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
        "candidate_count":    len(roster),
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
        "recipient_email":  contact.get("contact_email"),
        "recipient_name":   contact.get("contact_name"),
        "contact_id":       contact.get("contact_id"),
        "student_id":       None,
        "contact_verified": contact.get("contact_verified", False),
        "subject":          (result.get("subject") or "").strip(),
        "body":             (result.get("body") or "").strip(),
    }

    check = validate_email(email)
    if not check["valid"]:          # one regeneration with the errors fed back
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