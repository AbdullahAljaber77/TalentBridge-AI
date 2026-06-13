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

    emails = [
        email for email in emails
        if not any(bad in email.lower() for bad in ["example.com", "test.com"])
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

    return {
        "contact_name": None,
        "contact_email": email,
        "contact_title": "Talent / Careers Team",
        "contact_verified": False,
        "contact_source": "Web Search",
        "confidence_score": 0.65
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
        confidence = item.get("confidence") or 80

        if not email:
            continue

        title_lower = title.lower()
        is_hr = any(keyword in title_lower for keyword in HR_TITLE_KEYWORDS)

        if is_hr:
            hr_contacts.append({
                "contact_name": f"{first_name} {last_name}".strip() or None,
                "contact_email": email,
                "contact_title": title or "HR / Talent Contact",
                "contact_verified": True,
                "contact_source": "Hunter.io",
                "confidence_score": max(float(confidence) / 100, 0.85)
            })

    if hr_contacts:
        hr_contacts.sort(key=lambda x: x["confidence_score"], reverse=True)
        return hr_contacts[0]

    first = emails[0]
    email = first.get("value")

    if not email:
        return None

    return {
        "contact_name": f"{first.get('first_name') or ''} {first.get('last_name') or ''}".strip() or None,
        "contact_email": email,
        "contact_title": first.get("position") or "Company Contact",
        "contact_verified": True,
        "contact_source": "Hunter.io",
        "confidence_score": max(float(first.get("confidence") or 70) / 100, 0.7)
    }


def find_real_domain(company):
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

    cached = db.get_cached_contact(company_name)

    if cached:
        db.update_contact_last_used(cached["contact_id"])
        return {
            "company_name": company_name,
            "status": "cached_contact_used",
            "contact_email": cached["contact_email"],
            "source": "Cache"
        }

    web_contact = web_search_contact(company_name)

    if web_contact:
        saved = db.save_contact(
            company_name=company_name,
            contact_email=web_contact["contact_email"],
            contact_name=web_contact["contact_name"],
            contact_title=web_contact["contact_title"],
            contact_verified=web_contact["contact_verified"],
            contact_source=web_contact["contact_source"],
            confidence_score=web_contact["confidence_score"]
        )

        return {
            "company_name": company_name,
            "status": "web_search_contact_saved",
            "contact_email": web_contact["contact_email"],
            "source": "Web Search",
            "contact_id": saved["contact_id"] if saved else None
        }

    domain = find_real_domain(company)

    if not domain:
        return {
            "company_name": company_name,
            "status": "contact_needed_human_review",
            "contact_email": None,
            "source": None
        }

    hunter_contact = hunter_io_search(domain)

    if hunter_contact:
        saved = db.save_contact(
            company_name=company_name,
            contact_email=hunter_contact["contact_email"],
            contact_name=hunter_contact["contact_name"],
            contact_title=hunter_contact["contact_title"],
            contact_verified=hunter_contact["contact_verified"],
            contact_source=hunter_contact["contact_source"],
            confidence_score=hunter_contact["confidence_score"]
        )

        return {
            "company_name": company_name,
            "status": "hunter_contact_saved",
            "contact_email": hunter_contact["contact_email"],
            "source": "Hunter.io",
            "contact_id": saved["contact_id"] if saved else None
        }

    best_guess = build_best_guess_email(domain)

    saved = db.save_contact(
        company_name=company_name,
        contact_email=best_guess,
        contact_name=None,
        contact_title="HR / Recruitment Team",
        contact_verified=False,
        contact_source="Best Guess",
        confidence_score=0.2
    )

    return {
        "company_name": company_name,
        "status": "best_guess_saved_needs_verification",
        "contact_email": best_guess,
        "source": "Best Guess",
        "contact_id": saved["contact_id"] if saved else None
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