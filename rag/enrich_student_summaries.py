from shared.db import get_all_students, update_student_summary
from shared.llm import call_llm

def enrich_summaries():
    students = get_all_students()
    missing = [s for s in students if not s.summary]

    print(f"{len(missing)} students need a summary")

    for student in missing:
        prompt = (
            f"Write a 1-2 sentence professional summary for this candidate. "
            f"Output ONLY the summary text itself — no headers, no markdown, no labels.\n\n"
            f"Field: {student.field_of_study}\n"
            f"Experience: {student.experience_years}\n"
            f"Skills: {', '.join(student.skills)}\n"
            f"Status: {student.status}"
        )

        summary = call_llm(prompt)
        update_student_summary(student.student_id, summary)
        print(f"  {student.full_name}: {summary[:60]}...")

    print("Done.")