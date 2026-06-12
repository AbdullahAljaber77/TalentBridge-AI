from shared.db import get_all_students
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "all-MiniLM-L6-v2"

def student_to_text(student):
    skills_str = ", ".join(student.skills) if student.skills else "No skills listed"
    location_str = ", ".join(student.preferred_location) if student.preferred_location else student.location

    text = (
        f"Field: {student.field_of_study}\n"
        f"Experience: {student.experience_years}\n"
        f"Skills: {skills_str}\n"
        f"Preferred Location: {location_str}\n"
        f"Summary: {student.summary or 'No summary provided'}"
    )
    return text

def build_student_index():
    students = get_all_students()
    print(f"Loaded {len(students)} students")

    valid_students = [s for s in students if s.skills or s.summary]
    skipped = len(students) - len(valid_students)
    if skipped > 0:
        print(f"Skipped {skipped} students with no skills and no summary")

    incomplete = [s for s in valid_students if s.skills and not s.summary]
    if incomplete:
        print(f"WARNING: {len(incomplete)} students have skills but no summary.")
        print("Run rag/enrich_student_summaries.py before building the index for best results.")

    # ── Stage 3: build text for ALL students, then embed all at once ──
    texts = [student_to_text(s) for s in valid_students]

    print(f"\nLoading embedding model...")
    model = SentenceTransformer(EMBED_MODEL)

    print(f"Embedding {len(texts)} students...")
    vectors = model.encode(texts, show_progress_bar=True)
    print(f"\nAll vectors shape: {vectors.shape}")

    return valid_students, vectors