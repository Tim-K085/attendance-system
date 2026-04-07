import pandas as pd
from ..extensions import db
from ..models import Student

REQUIRED_COLUMNS = ["系級", "學號", "姓名", "時段"]

def import_students_from_excel(file_storage):
    df = pd.read_excel(file_storage)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"缺少必要欄位：{', '.join(missing)}")

    imported_count = 0
    updated_count = 0

    for _, row in df.iterrows():
        department = str(row["系級"]).strip() if pd.notna(row["系級"]) else ""
        student_id = str(row["學號"]).strip() if pd.notna(row["學號"]) else ""
        raw_name = str(row["姓名"]).strip() if pd.notna(row["姓名"]) else ""
        section = str(row["時段"]).strip() if pd.notna(row["時段"]) else ""

        if not student_id or not raw_name or section not in ["週四", "週五"]:
            continue

        existing = Student.query.filter_by(student_id=student_id).first()

        if existing:
            existing.department = department
            existing.name = raw_name
            existing.raw_name = raw_name
            existing.section = section
            existing.is_active = True
            updated_count += 1
        else:
            student = Student(
                student_id=student_id,
                name=raw_name,
                raw_name=raw_name,
                department=department,
                section=section,
                is_active=True,
            )
            db.session.add(student)
            imported_count += 1

    db.session.commit()
    return imported_count, updated_count