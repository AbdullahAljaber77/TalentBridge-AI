from shared.db import get_all_students

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

    # Skip students with no skills AND no summary — nothing to embed
    valid_students = [s for s in students if s.skills or s.summary]
    skipped = len(students) - len(valid_students)
    if skipped > 0:
        print(f"Skipped {skipped} students with no skills and no summary")

    # Warn if anyone is missing a summary but has skills — run enrich_student_summaries.py first
    incomplete = [s for s in valid_students if s.skills and not s.summary]
    if incomplete:
        print(f"WARNING: {len(incomplete)} students have skills but no summary.")
        print("Run rag/enrich_student_summaries.py before building the index for best results.")

    sample_text = student_to_text(valid_students[0])
    print("\n--- Sample text for student 0 ---")
    print(sample_text)

    return valid_students