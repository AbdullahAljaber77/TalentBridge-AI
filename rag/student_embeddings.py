from shared.db import get_all_students

def build_student_index():
    students = get_all_students()
    print(f"Loaded {len(students)} students")
    return students