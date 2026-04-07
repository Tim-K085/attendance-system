from io import BytesIO
import pandas as pd

from ..extensions import db
from ..models import Student, CourseSession, Attendance


def build_attendance_excel():
    records = (
        db.session.query(Attendance, Student, CourseSession)
        .join(Student, Attendance.student_id_fk == Student.id)
        .join(CourseSession, Attendance.session_id == CourseSession.id)
        .order_by(Attendance.signed_at.asc())
        .all()
    )

    detail_rows = []
    for attendance, student, session in records:
        detail_rows.append({
            "課次ID": session.id,
            "日期": str(session.course_date),
            "時段": session.section,
            "開放時間": str(session.opens_at),
            "截止時間": str(session.closes_at),
            "學號": student.student_id,
            "姓名": student.name,
            "系級": student.department,
            "簽到時間": str(attendance.signed_at),
            "IP位址": attendance.ip_address,
            "狀態": attendance.status,
        })

    detail_df = pd.DataFrame(detail_rows)

    students = Student.query.order_by(Student.student_id.asc()).all()
    sessions = CourseSession.query.all()

    total_sessions_by_section = {}
    for s in sessions:
        total_sessions_by_section[s.section] = total_sessions_by_section.get(s.section, 0) + 1

    summary_rows = []
    for student in students:
        signed_count = (
            db.session.query(Attendance)
            .join(CourseSession, Attendance.session_id == CourseSession.id)
            .filter(
                Attendance.student_id_fk == student.id,
                CourseSession.section == student.section
            )
            .count()
        )

        total_sessions = total_sessions_by_section.get(student.section, 0)
        attendance_rate = 0
        if total_sessions > 0:
            attendance_rate = round(signed_count / total_sessions * 100, 2)

        summary_rows.append({
            "學號": student.student_id,
            "姓名": student.name,
            "系級": student.department,
            "時段": student.section,
            "已簽到次數": signed_count,
            "該時段總課次": total_sessions,
            "出席率(%)": attendance_rate,
        })

    summary_df = pd.DataFrame(summary_rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        detail_df.to_excel(writer, sheet_name="出席明細", index=False)
        summary_df.to_excel(writer, sheet_name="出席總表", index=False)

    output.seek(0)
    return output