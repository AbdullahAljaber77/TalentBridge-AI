import faiss
import json
from pathlib import Path
from shared.db import get_all_students
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "all-MiniLM-L6-v2"
INDEX_DIR  = Path("faiss_index")
INDEX_FILE = INDEX_DIR / "student_index.faiss"
IDS_FILE   = INDEX_DIR / "student_ids.json"

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

    # ── Stage 4: save FAISS index + ID mapping ──────────────────────
    INDEX_DIR.mkdir(exist_ok=True)

    dim = vectors.shape[1]  # 384
    index = faiss.IndexFlatL2(dim)
    index.add(vectors)

    faiss.write_index(index, str(INDEX_FILE))
    print(f"\nSaved FAISS index to {INDEX_FILE}")

    metadata = [{"student_id": s.student_id, "full_name": s.full_name} for s in valid_students]
    with open(IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved student ID mapping to {IDS_FILE}")

    return valid_students, vectors

def load_student_index():
    index = faiss.read_index(str(INDEX_FILE))

    with open(IDS_FILE, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    print(f"Loaded FAISS index with {index.ntotal} vectors")
    return index, metadata