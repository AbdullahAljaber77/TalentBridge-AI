"""
Agent 01 — Job Analysis Agent
TalentBridge AI — RCP #7
 
First agent in the pipeline. Reads job postings for a campaign, sends each
description to the LLM, extracts structured data, and saves it to the
job_analysis table. Output feeds the Targeting Agent (Agent 02).
 
Flow:
  load campaign -> filter jobs -> batch -> LLM extract -> save -> update progress
"""
 
import time
 
from shared import db
from shared.llm import call_llm_with_data, build_system_prompt, DEFAULT_MODEL
 
# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
 
BATCH_SIZE            = 50      # jobs per batch
BATCH_DELAY_SECONDS   = 2       # pause between batches (avoid rate limits)
MAX_DESCRIPTION_CHARS = 3000    # truncate very long descriptions
 
REQUIRED_FIELDS = [
    "extracted_skills",
    "experience_level",
    "job_type",
    "key_responsibilities",
    "qualifications_summary",
]
 
# System prompt is built once and reused for every job.
SYSTEM_PROMPT = build_system_prompt(
    role="job description analyst",
    instructions=(
        "Extract structured information from job postings. "
        "Always respond with valid JSON only — no markdown, no explanation."
    ),
)
 
# Extraction rules sent with every job (kept out of the data dict).
INSTRUCTION = (
    "Analyze this job posting and extract the required fields. "
    "Return JSON with exactly these keys: extracted_skills (list), "
    "experience_level, job_type, key_responsibilities (list), "
    "qualifications_summary.\n"
    "Rules:\n"
    "- extracted_skills: all technical and soft skills mentioned\n"
    "- experience_level: Junior (0-2y) | Mid (3-5y) | Senior (6+y) | Not specified\n"
    "- job_type: Full-time | Part-time | Remote | Hybrid | Not specified\n"
    "- key_responsibilities: maximum 5 most important\n"
    "- qualifications_summary: one sentence"
)
 
 
# ─────────────────────────────────────────────
# LLM extraction
# ─────────────────────────────────────────────
 
def analyze_job(job):
    """Send one job to the LLM and return a validated dict, or None on failure.
    call_llm_with_data already strips fences, retries, and checks required_keys
    (raising ValueError if it cannot produce them) — so we just catch and skip."""
    description = (job.description_text or "")[:MAX_DESCRIPTION_CHARS]
 
    try:
        return call_llm_with_data(
            instruction=INSTRUCTION,
            data={
                "job_title":   job.job_title,
                "company":     job.company_name,
                "description": description,
            },
            system=SYSTEM_PROMPT,
            required_keys=REQUIRED_FIELDS,
        )
    except Exception as e:
        print(f"   ✗ LLM failed on job {job.job_id}: {e}")
        return None
 
 
# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────
 
def run(campaign_id: int, limit: int = None) -> dict:
    # STEP 1 — Load campaign config
    campaign = db.get_campaign(campaign_id)
    if not campaign:
        print(f"Campaign {campaign_id} not found.")
        return {"status": "failed", "reason": "campaign not found"}
 
    keywords  = campaign["selected_keywords"]
    date_from = campaign["date_range_start"]
 
    # STEP 2 — Filter jobs (skips already-analysed jobs, so restart is safe).
    # Pass limit=5 for a cheap first test run; leave None for a full run.
    jobs = db.get_jobs_for_campaign(keywords, date_from, campaign_id, limit=limit)
    total = len(jobs)
    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
 
    print(f"Campaign {campaign_id}: {total} jobs to analyze "
          f"in {total_batches} batches.")
 
    db.start_campaign(campaign_id, total_jobs_found=total,
                      total_batches=total_batches)
 
    if total == 0:
        db.complete_campaign(campaign_id)
        return {"status": "complete", "campaign_id": campaign_id,
                "processed": 0, "failed": 0}
 
    processed = 0
    failed    = 0
 
    # STEP 3 — Process in batches
    for batch_index in range(total_batches):
        batch = jobs[batch_index * BATCH_SIZE:(batch_index + 1) * BATCH_SIZE]
        db.update_current_batch(campaign_id, batch_index + 1)
        print(f" Batch {batch_index + 1}/{total_batches} ({len(batch)} jobs)")
 
        for job in batch:
            analysis = analyze_job(job)
 
            if analysis is None:
                db.increment_jobs_failed(campaign_id)
                failed += 1
                continue
 
            db.save_job_analysis(
                campaign_id            = campaign_id,
                job_id                 = job.job_id,
                extracted_skills       = analysis["extracted_skills"],
                experience_level       = analysis["experience_level"],
                job_type               = analysis["job_type"],
                key_responsibilities   = analysis["key_responsibilities"],
                qualifications_summary = analysis["qualifications_summary"],
                llm_model_used         = DEFAULT_MODEL,
            )
            db.increment_jobs_processed(campaign_id)
            processed += 1
 
        # Delay between batches (not after the last one)
        if batch_index < total_batches - 1:
            time.sleep(BATCH_DELAY_SECONDS)
 
    # STEP 4 — Mark campaign complete, signal next agent
    db.complete_campaign(campaign_id)
    print(f"Done. processed={processed} failed={failed}")
 
    return {
        "status": "complete",
        "campaign_id": campaign_id,
        "processed": processed,
        "failed": failed,
    }

if __name__ == "__main__":
    run(campaign_id=1)