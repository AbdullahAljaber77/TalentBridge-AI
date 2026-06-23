import json
import textwrap
from pathlib import Path
from typing import Dict, Any, List

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from shared import db

try:
    from shared.llm import call_llm
except Exception:
    call_llm = None


REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def safe_int(value) -> int:
    return int(value or 0)


def calculate_response_rate(total_replies: int, total_emails_sent: int) -> float:
    if total_emails_sent <= 0:
        return 0.0
    return round((total_replies / total_emails_sent) * 100, 2)


def get_unique_companies_targeted(campaign_id: int) -> int:
    query = """
        SELECT COUNT(DISTINCT jp.company_name) AS total
        FROM job_matches jm
        JOIN job_postings jp ON jm.job_id = jp.job_id
        WHERE jm.campaign_id = %s
    """
    row = db.fetchone(query, (campaign_id,))
    return safe_int(row["total"]) if row else 0


def build_live_dashboard_data(campaign_id: int) -> Dict[str, Any]:
    campaign = db.get_campaign_report_summary(campaign_id)
    emails = db.get_reporting_email_stats(campaign_id)
    replies = db.get_reporting_reply_stats(campaign_id)
    meetings = db.get_reporting_meeting_stats(campaign_id)
    followups = db.get_reporting_followup_stats(campaign_id)

    emails_sent = safe_int(emails.get("sent") if emails else 0)
    total_replies = safe_int(replies.get("total_replies") if replies else 0)

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.get("campaign_name") if campaign else None,
        "campaign_status": campaign.get("status") if campaign else None,
        "emails": emails,
        "replies": replies,
        "meetings": meetings,
        "followups": followups,
        "response_rate": calculate_response_rate(total_replies, emails_sent),
        "pending_actions": {
            "emails_awaiting_approval": safe_int(emails.get("pending_approval") if emails else 0),
            "undecided_replies": safe_int(replies.get("undecided") if replies else 0),
            "pending_followups": safe_int(followups.get("pending") if followups else 0)
        }
    }


def build_recommendations_prompt(report_data: Dict[str, Any]) -> str:
    return f"""
You are a campaign analytics expert analyzing an employer outreach campaign.

Generate 5 clear, actionable recommendations for the next campaign.
Focus on what worked, what did not, and what to improve.

Campaign Data:
{json.dumps(report_data, ensure_ascii=False, default=str)}

Return valid JSON only:
{{
  "recommendations": [
    "recommendation 1",
    "recommendation 2",
    "recommendation 3",
    "recommendation 4",
    "recommendation 5"
  ]
}}
"""


def parse_json_response(text: str):
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return None


def generate_fallback_recommendations(report_data: Dict[str, Any]) -> List[str]:
    response_rate = report_data.get("response_rate", 0)
    emails_sent = report_data.get("emails", {}).get("sent", 0) if report_data.get("emails") else 0
    interested = report_data.get("replies", {}).get("interested", 0) if report_data.get("replies") else 0

    recommendations = []

    if emails_sent == 0:
        recommendations.append("No emails were sent. Complete the approval and sending workflow before evaluating campaign performance.")
    elif response_rate < 10:
        recommendations.append("Response rate is low. Improve subject lines and personalize openers using stronger company research.")
    else:
        recommendations.append("Response rate is acceptable. Continue using the strongest company research and matching signals in outreach.")

    if interested == 0:
        recommendations.append("No interested replies were recorded. Review targeting quality and ensure matched students are clearly relevant to each company.")
    else:
        recommendations.append("Interested replies were recorded. Prioritize scheduling quickly to convert interest into meetings.")

    recommendations.extend([
        "Use the highest scoring job matches as the main email angle.",
        "Review unverified contacts before sending to reduce bounce risk.",
        "Track which company types respond best and adjust future targeting accordingly."
    ])

    return recommendations[:5]


def generate_recommendations(report_data: Dict[str, Any]) -> List[str]:
    if call_llm:
        try:
            prompt = build_recommendations_prompt(report_data)
            response = call_llm(prompt)
            parsed = parse_json_response(response)

            if parsed and isinstance(parsed.get("recommendations"), list):
                return parsed["recommendations"][:5]
        except Exception:
            pass

    return generate_fallback_recommendations(report_data)


def export_pdf_report(report_data: Dict[str, Any], recommendations: List[str]) -> str:
    campaign_id = report_data["campaign_id"]
    pdf_path = REPORTS_DIR / f"campaign_report_{campaign_id}.pdf"

    c = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4

    def title(text, y):
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, text)

    def line(text, y, size=11):
        c.setFont("Helvetica", size)
        c.drawString(50, y, str(text))

    y = height - 60

    title("TalentBridge AI — Campaign Report", y)
    y -= 40

    line(f"Campaign ID: {campaign_id}", y)
    y -= 20
    line(f"Campaign Name: {report_data.get('campaign_name')}", y)
    y -= 20
    line(f"Status: {report_data.get('campaign_status')}", y)
    y -= 30

    title("Summary Metrics", y)
    y -= 35

    emails = report_data.get("emails") or {}
    replies = report_data.get("replies") or {}
    meetings = report_data.get("meetings") or {}

    metrics = [
        f"Emails Sent: {emails.get('sent', 0)}",
        f"Total Replies: {replies.get('total_replies', 0)}",
        f"Response Rate: {report_data.get('response_rate', 0)}%",
        f"Interested Replies: {replies.get('interested', 0)}",
        f"Undecided Replies: {replies.get('undecided', 0)}",
        f"Not Interested Replies: {replies.get('not_interested', 0)}",
        f"Meetings Confirmed: {meetings.get('confirmed', 0)}",
    ]

    for m in metrics:
        line(m, y)
        y -= 18

    y -= 20
    title("Top Keywords", y)
    y -= 30

    for item in report_data.get("top_keywords", []):
        line(f"- {item.get('keyword')} | Matches: {item.get('matched_jobs')} | Avg Score: {item.get('avg_match_score')}", y)
        y -= 18

    y -= 20
    title("Recommendations", y)
    y -= 30

    # Wrap long recommendation text so it never runs off the page edge.
    # ~95 chars fits the A4 content width at 10pt Helvetica with a 50px margin.
    WRAP_WIDTH = 95
    for idx, rec in enumerate(recommendations, 1):
        wrapped = textwrap.wrap(f"{idx}. {rec}", width=WRAP_WIDTH) or [f"{idx}."]
        for wrap_idx, text_line in enumerate(wrapped):
            if y < 80:
                c.showPage()
                y = height - 60
            # Indent continuation lines so they align under the first line's text.
            indent = "" if wrap_idx == 0 else "   "
            line(indent + text_line, y, 10)
            y -= 16
        y -= 8  # small gap between recommendations

    c.save()
    return str(pdf_path)


def generate_full_report(campaign_id: int) -> Dict[str, Any]:
    campaign = db.get_campaign_report_summary(campaign_id)

    if not campaign:
        return {
            "status": "not_found",
            "campaign_id": campaign_id
        }

    dashboard = build_live_dashboard_data(campaign_id)

    top_keywords = db.get_top_performing_keywords(campaign_id)
    top_companies = db.get_top_responding_companies(campaign_id)
    student_success = db.get_student_match_success(campaign_id)

    companies_targeted = get_unique_companies_targeted(campaign_id)

    report_data = {
        **dashboard,
        "top_keywords": top_keywords,
        "top_companies": top_companies,
        "student_success": student_success,
        "companies_targeted": companies_targeted
    }

    recommendations = generate_recommendations(report_data)
    pdf_path = export_pdf_report(report_data, recommendations)

    emails = dashboard.get("emails") or {}
    replies = dashboard.get("replies") or {}
    meetings = dashboard.get("meetings") or {}

    top_keyword_names = [x.get("keyword") for x in top_keywords if x.get("keyword")]
    top_company_names = [x.get("company_name") for x in top_companies if x.get("company_name")]

    saved = db.save_campaign_report(
        campaign_id=campaign_id,
        report_type="Full Report",
        total_jobs_processed=safe_int(campaign.get("jobs_processed")),
        total_companies_targeted=companies_targeted,
        total_emails_sent=safe_int(emails.get("sent")),
        total_replies=safe_int(replies.get("total_replies")),
        response_rate=dashboard.get("response_rate", 0.0),
        interested_count=safe_int(replies.get("interested")),
        neutral_count=safe_int(replies.get("undecided")),
        negative_count=safe_int(replies.get("not_interested")),
        meetings_booked=safe_int(meetings.get("confirmed")),
        top_performing_keywords=top_keyword_names,
        top_responding_companies=top_company_names,
        recommendations="\n".join(recommendations)
    )

    return {
        "status": "complete",
        "campaign_id": campaign_id,
        "report_id": saved.get("report_id") if saved else None,
        "pdf_path": pdf_path,
        "dashboard": dashboard,
        "top_keywords": top_keywords,
        "top_companies": top_companies,
        "student_success": student_success,
        "recommendations": recommendations
    }


def reporting_agent(campaign_id: int, mode: str = "dashboard") -> Dict[str, Any]:
    mode = mode.lower().strip()

    if mode == "dashboard":
        return {
            "status": "complete",
            "mode": "dashboard",
            "data": build_live_dashboard_data(campaign_id)
        }

    if mode in ["full", "report", "full_report"]:
        return generate_full_report(campaign_id)

    return {
        "status": "invalid_mode",
        "allowed_modes": ["dashboard", "full_report"]
    }


if __name__ == "__main__":
    output = reporting_agent(campaign_id=2, mode="dashboard")
    print(json.dumps(output, indent=2, default=str))