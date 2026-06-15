"""
Agent 02 — Targeting Agent
Matches students to jobs using keyword overlap, experience/location
filters, and semantic similarity (FAISS).

Parameters (all tunable):
    campaign_id       : which campaign to process
    min_match_score   : minimum overall score to save a match (default 0.2)
    experience_strict : True = exact level match, False = allow one level down (default True)
"""
from sentence_transformers import SentenceTransformer

from rag.student_embeddings import load_student_index, EMBED_MODEL
from shared.db import get_job_analyses, get_all_students, get_job_posting, save_job_match, update_campaign_status

# Load once at module level — not inside the function
embed_model = SentenceTransformer(EMBED_MODEL)


# ─────────────────────────────────────────────
# Keyword matching
# ─────────────────────────────────────────────

def keyword_match(job_skills: list[str], student_skills: list[str]) -> tuple[float, list[str]]:
    job_set     = {s.lower().strip() for s in job_skills}
    student_set = {s.lower().strip() for s in student_skills}

    matched_lower = job_set & student_set
    score = len(matched_lower) / max(len(job_set), 1)

    matched_original = [s for s in student_skills if s.lower().strip() in matched_lower]

    return round(score, 4), matched_original


# ─────────────────────────────────────────────
# Experience filter
# ─────────────────────────────────────────────

EXPERIENCE_MAP = {
    "Junior": ["No experience yet", "Less than 1 year", "1-2 years"],
    "Mid":    ["3-5 years"],
    "Senior": ["5+ years"],
}

def experience_compatible(job_level: str, student_years: str, strict: bool = True) -> bool:
    if job_level not in EXPERIENCE_MAP:
        return True  # "Not specified" → everyone passes

    if strict:
        return student_years in EXPERIENCE_MAP[job_level]

    # Lenient: allow one level down
    allowed = EXPERIENCE_MAP[job_level].copy()
    if job_level == "Mid":
        allowed += EXPERIENCE_MAP["Junior"]
    if job_level == "Senior":
        allowed += EXPERIENCE_MAP["Mid"]

    return student_years in allowed


# ─────────────────────────────────────────────
# Location filter
# ─────────────────────────────────────────────

OPEN_LOCATION_TOKENS = {"Anywhere in KSA", "Open to relocation", "Remote only"}

def location_compatible(job_location: str, student_preferred: list[str]) -> bool:
    if any(token in student_preferred for token in OPEN_LOCATION_TOKENS):
        return True

    return job_location in student_preferred


# ─────────────────────────────────────────────
# Semantic matching (FAISS)
# ─────────────────────────────────────────────

def semantic_match(job_description: str, faiss_index, faiss_metadata, embed_model) -> dict:
    job_vector = embed_model.encode([job_description])

    distances, indices = faiss_index.search(job_vector, faiss_index.ntotal)

    scores = {}
    for dist, idx in zip(distances[0], indices[0]):
        student_id = faiss_metadata[idx]["student_id"]
        scores[student_id] = round(1 / (1 + float(dist)), 4)

    return scores


# ─────────────────────────────────────────────
# Combined score
# ─────────────────────────────────────────────

def combined_score(keyword_score: float, semantic_score: float) -> float:
    return round((keyword_score * 0.3) + (semantic_score * 0.7), 4)


# ─────────────────────────────────────────────
# Main agent
# ─────────────────────────────────────────────

def run_targeting_agent(
    campaign_id: int,
    min_match_score: float = 0.2,
    experience_strict: bool = True,
    top_k: int = 5,
):
    job_analyses = get_job_analyses(campaign_id)
    students = get_all_students()
    faiss_index, faiss_metadata = load_student_index()

    update_campaign_status(campaign_id, "matching students")
    print(f"Settings: min_match_score={min_match_score}, experience_strict={experience_strict}, top_k={top_k}")

    total_matches = 0

    for job_analysis in job_analyses:
        job_posting = get_job_posting(job_analysis.job_id)
        print(f"\nProcessing: {job_posting.job_title} at {job_posting.company_name}")

        semantic_scores = semantic_match(
            job_posting.description_text, faiss_index, faiss_metadata, embed_model
        )

        # Collect all passing matches for this job
        candidates = []
        for student in students:
            kw_score, matched_skills = keyword_match(job_analysis.extracted_skills, student.skills)

            if not experience_compatible(job_analysis.experience_level, student.experience_years, strict=experience_strict):
                continue
            if not location_compatible(job_posting.location, student.preferred_location):
                continue

            sem_score = semantic_scores.get(student.student_id, 0.0)
            overall = combined_score(kw_score, sem_score)

            if overall < min_match_score:
                continue

            candidates.append({
                "student_id"    : student.student_id,
                "kw_score"      : kw_score,
                "sem_score"     : sem_score,
                "overall"       : overall,
                "matched_skills": matched_skills,
            })

        # Sort by overall score descending, keep top_k only
        candidates = sorted(candidates, key=lambda x: x["overall"], reverse=True)[:top_k]

        # Save top_k matches to Neon
        for c in candidates:
            save_job_match(
                campaign_id=campaign_id,
                job_id=job_analysis.job_id,
                student_id=c["student_id"],
                keyword_match_score=c["kw_score"],
                semantic_match_score=c["sem_score"],
                overall_match_score=c["overall"],
                matched_skills=c["matched_skills"],
            )
            total_matches += 1

        print(f"  -> {len(candidates)} matches saved")

    update_campaign_status(campaign_id, "students matched")
    
    print(f"\nDone. Total matches saved: {total_matches}")
    return {
        "status"        : "complete",
        "campaign_id"   : campaign_id,
        "total_matches" : total_matches,
    }


if __name__ == "__main__":
    run_targeting_agent(
        campaign_id=1,
        min_match_score=0.2,
        experience_strict=False,
        top_k=5,
    )