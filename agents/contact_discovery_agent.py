import re
import requests
from typing import Optional
from urllib.parse import urlparse

from shared.config import TAVILY_API_KEY, HUNTER_IO_API_KEY
from shared import db


HR_TITLE_KEYWORDS = [
    "hr", "human resources", "talent", "recruiter",
    "recruiting", "recruitment", "hiring", "people",
    "culture", "workforce", "staffing", "acquisition"
]

JOB_BOARD_DOMAINS = [
    "indeed.com", "sa.indeed.com", "linkedin.com",
    "bayt.com", "naukrigulf.com", "gulftalent.com"
]


def extract_domain(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    value = value.strip()

    if not value.startswith(("http://", "https://")):
        value = "https://" + value

    parsed = urlparse(value)
    domain = parsed.netloc.lower().replace("www.", "")

    if not domain:
        return None

    if any(blocked in domain for blocked in JOB_BOARD_DOMAINS):
        return None

    return domain


def is_valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def tavily_search(query: str):
    if not TAVILY_API_KEY:
        return []

    try:
        response = requests.post(
            "https://api.tavily.com/search",
            json={
                "api_key": TAVILY_API_KEY,
                "query": query,
                "search_depth": "basic",
                "max_results": 5
            },
            timeout=20
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except Exception:
        return []


def extract_email_from_text(text: str) -> Optional[str]:
    pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(pattern, text)

    if not emails:
        return None

    BAD_EMAIL_DOMAINS = [
    # Generic placeholders
    "example.com", "test.com", "email.com", "domain.com",
    "yourcompany.com", "company.com", "mail.com", "sample.com",
    
    # Common in Arabic/Saudi web content
    "example.sa", "test.sa", "domain.sa",
    
    # Technical/dev placeholders
    "localhost", "tempmail.com", "mailinator.com", "guerrillamail.com",
    "yopmail.com", "throwaway.email", "fakeinbox.com",
    
    # Image/media files mistaken for emails (regex edge case)
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    
    # Common in job board scraped content
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "notifications@", "automated@", "system@",
    ]

    emails = [
        email for email in emails
        if not any(bad in email.lower() for bad in BAD_EMAIL_DOMAINS)
    ]

    if not emails:
        return None

    def score(email):
        email = email.lower()
        score_value = 0

        if email.startswith(("hr@", "careers@", "recruitment@", "talent@")):
            score_value += 10

        for keyword in HR_TITLE_KEYWORDS:
            if keyword in email:
                score_value += 3

        return score_value

    emails.sort(key=score, reverse=True)
    return emails[0]


def web_search_contact(company_name: str):
    queries = [
        f"{company_name} HR manager Saudi Arabia email",
        f"{company_name} talent acquisition contact",
        f"{company_name} careers email",
        f"{company_name} recruitment email"
    ]

    all_results_text = ""

    for query in queries:
        results = tavily_search(query)

        for item in results:
            all_results_text += " "
            all_results_text += item.get("title", "")
            all_results_text += " "
            all_results_text += item.get("content", "")
            all_results_text += " "
            all_results_text += item.get("url", "")

    email = extract_email_from_text(all_results_text)

    if not email:
        return None

    email_prefix = email.split("@")[0].lower()

    title_map = {
        "hr"         : "HR Team",
        "careers"    : "Careers Team",
        "talent"     : "Talent Acquisition Team",
        "recruitment": "Recruitment Team",
        "hiring"     : "Hiring Team",
        "people"     : "People & Culture Team",
    }
    contact_title = title_map.get(email_prefix, "General Contact")

    if email.lower().startswith(("hr@", "careers@", "talent@", "recruitment@")):
        confidence_score = 0.70
    elif any(kw in email.lower() for kw in HR_TITLE_KEYWORDS):
        confidence_score = 0.60
    else:
        confidence_score = 0.45

    return {
        "contact_name"    : None,
        "contact_email"   : email,
        "contact_title"   : contact_title,
        "contact_verified": False,
        "contact_source"  : "Web Search",
        "confidence_score": confidence_score,
    }


def hunter_io_search(domain: str):
    if not HUNTER_IO_API_KEY:
        return None

    try:
        response = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "domain": domain,
                "api_key": HUNTER_IO_API_KEY,
                "limit": 10
            },
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
    except Exception:
        print(f"   [Hunter.io] failed for {domain}: {e}")
        return None

    emails = data.get("data", {}).get("emails", [])

    if not emails:
        return None

    hr_contacts = []

    for item in emails:
        email = item.get("value")
        title = item.get("position") or ""
        first_name = item.get("first_name") or ""
        last_name = item.get("last_name") or ""
        confidence = item.get("confidence") if item.get("confidence") is not None else 50

        if not email:
            continue

        title_lower = title.lower()
        is_hr = any(keyword in title_lower for keyword in HR_TITLE_KEYWORDS)

        verified = item.get("type") == "personal"

        if is_hr:
            hr_contacts.append({
                "contact_name": f"{first_name} {last_name}".strip() or None,
                "contact_email": email,
                "contact_title": title or "HR / Talent Contact",
                "contact_verified": verified,
                "contact_source": "Hunter.io",
                "confidence_score": round(float(confidence) / 100, 2)
            })

    if hr_contacts:
        hr_contacts.sort(key=lambda x: x["confidence_score"], reverse=True)
        return hr_contacts[0]

    first = emails[0]
    email = first.get("value")

    if not email:
        return None

    raw_confidence = first.get("confidence") if first.get("confidence") is not None else 50

    return {
        "contact_name"    : f"{first.get('first_name') or ''} {first.get('last_name') or ''}".strip() or None,
        "contact_email"   : email,
        "contact_title"   : first.get("position") or "Non-HR Contact — Verify Before Sending",
        "contact_verified": first.get("type") == "personal",
        "contact_source"  : "Hunter.io",
        "confidence_score": round(float(raw_confidence) / 100, 2)
    }


def find_real_domain(company):
    # NOTE: For this dataset all domain/url columns point to sa.indeed.com
    # (scraped from Indeed Saudi Arabia) — extract_domain() will block all
    # of them as job board domains. The loop below runs but always falls
    # through to the Tavily search. Kept for correctness in case future
    # datasets have real company domains.
    possible_values = [
        company.get("domain"),
        company.get("company_link"),
        company.get("url"),
        company.get("input_discovery_input_domain")
    ]

    for value in possible_values:
        domain = extract_domain(value)
        if domain:
            return domain

    results = tavily_search(f"{company.get('company_name')} official website Saudi Arabia")

    for item in results:
        domain = extract_domain(item.get("url"))
        if domain:
            return domain

    return None


def build_best_guess_email(domain: str) -> str:
    return f"hr@{domain}"


def process_company(campaign_id: int, company: dict):
    company_name = company["company_name"]

    # Step 1 — Check cache
    cached = db.get_cached_contact(company_name)
    if cached:
        db.update_contact_last_used(cached["contact_id"])
        return {
            "company_name" : company_name,
            "status"       : "cached_contact_used",
            "contact_email": cached["contact_email"],
            "source"       : "Cache"
        }

    # Step 2 — Find real domain first
    domain = find_real_domain(company)

    # Step 3 — Hunter.io (highest quality — try before web search)
    if domain:
        hunter_contact = hunter_io_search(domain)
        if hunter_contact:
            saved = db.save_contact(
                company_name   = company_name,
                contact_email  = hunter_contact["contact_email"],
                contact_name   = hunter_contact["contact_name"],
                contact_title  = hunter_contact["contact_title"],
                contact_verified = hunter_contact["contact_verified"],
                contact_source = hunter_contact["contact_source"],
                confidence_score = hunter_contact["confidence_score"]
            )
            return {
                "company_name" : company_name,
                "status"       : "hunter_contact_saved",
                "contact_email": hunter_contact["contact_email"],
                "source"       : "Hunter.io",
                "contact_id"   : saved["contact_id"] if saved else None
            }

    # Step 4 — Web search (fallback)
    web_contact = web_search_contact(company_name)
    if web_contact:
        saved = db.save_contact(
            company_name   = company_name,
            contact_email  = web_contact["contact_email"],
            contact_name   = web_contact["contact_name"],
            contact_title  = web_contact["contact_title"],
            contact_verified = web_contact["contact_verified"],
            contact_source = web_contact["contact_source"],
            confidence_score = web_contact["confidence_score"]
        )
        return {
            "company_name" : company_name,
            "status"       : "web_search_contact_saved",
            "contact_email": web_contact["contact_email"],
            "source"       : "Web Search",
            "contact_id"   : saved["contact_id"] if saved else None
        }

    # Step 5 — Best guess (domain found but no contact)
    if domain:
        best_guess = build_best_guess_email(domain)
        saved = db.save_contact(
            company_name   = company_name,
            contact_email  = best_guess,
            contact_name   = None,
            contact_title  = "HR / Recruitment Team",
            contact_verified = False,
            contact_source = "Best Guess",
            confidence_score = 0.2
        )
        db.flag_contact_needed(company_name, campaign_id)
        return {
            "company_name" : company_name,
            "status"       : "best_guess_saved_needs_verification",
            "contact_email": best_guess,
            "source"       : "Best Guess",
            "contact_id"   : saved["contact_id"] if saved else None
        }

    # Step 6 — Nothing found — flag for human review
    db.flag_contact_needed(company_name, campaign_id)
    return {
        "company_name" : company_name,
        "status"       : "contact_needed_human_review",
        "contact_email": None,
        "source"       : None
    }


def contact_discovery_agent(campaign_id: int):
    db.update_campaign_status(campaign_id, "discovering contacts")

    companies = db.get_company_targets_for_contact_discovery(campaign_id)
    results = []

    for company in companies:
        result = process_company(campaign_id, company)
        results.append(result)
        db.touch_campaign(campaign_id)

    db.update_campaign_status(campaign_id, "contacts_discovered")

    return {
        "status": "complete",
        "campaign_id": campaign_id,
        "companies_processed": len(companies),
        "results": results
    }


if __name__ == "__main__":
    output = contact_discovery_agent(campaign_id=1)
    print(output)