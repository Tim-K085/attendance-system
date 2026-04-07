from datetime import datetime

from flask import Blueprint, request, render_template_string
from .extensions import db
from .models import CourseSession, Student, Attendance

checkin_bp = Blueprint("checkin", __name__)

CHECKIN_HTML = """
<!doctype html>
<html>
<head><meta charset="utf-8"><title>學生簽到</title></head>
<body>
    <h1>學生簽到</h1>
    <p>課次 ID：{{ session.id }}</p>
    <p>時段：{{ session.section }}</p>
    <p>開放時間：{{ session.opens_at }}</p>
    <p>截止時間：{{ session.closes_at }}</p>

    <form method="post">
        <label>學號：</label>
        <input type="text" name="student_id" required><br><br>
        <label>姓名：</label>
        <input type="text" name="name" required><br><br>
        <button type="submit">送出簽到</button>
    </form>

    {% if message %}
    <p style="color:blue;">{{ message }}</p>
    {% endif %}
</body>
</html>
"""

@checkin_bp.route("/checkin/<int:session_id>", methods=["GET", "POST"])
def checkin(session_id):
    session = CourseSession.query.get_or_404(session_id)
    token = request.args.get("token", "")

    if token != session.qr_token:
        return "無效簽到連結", 403

    now = datetime.now()

    if now < session.opens_at:
        return "尚未開放簽到", 403

    if now > session.closes_at:
        return "簽到已截止", 403

    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        name = request.form.get("name", "").strip()

        student = Student.query.filter_by(student_id=student_id, is_active=True).first()

        if not student:
            return render_template_string(
                CHECKIN_HTML,
                session=session,
                message="學號不存在"
            )

        if student.name != name:
            return render_template_string(
                CHECKIN_HTML,
                session=session,
                message="學號或姓名不符"
            )

        if student.section != session.section:
            return render_template_string(
                CHECKIN_HTML,
                session=session,
                message="不屬於本時段，無法簽到"
            )

        existing_attendance = Attendance.query.filter_by(
            session_id=session.id,
            student_id_fk=student.id
        ).first()

        if existing_attendance:
            return render_template_string(
                CHECKIN_HTML,
                session=session,
                message="本次課程已簽到，請勿重複送出"
            )

        attendance = Attendance(
            session_id=session.id,
            student_id_fk=student.id,
            signed_at=now,
            ip_address=request.remote_addr,
            user_agent=request.headers.get("User-Agent", "")[:500],
            status="present",
        )
        db.session.add(attendance)
        db.session.commit()

        return render_template_string(
            CHECKIN_HTML,
            session=session,
            message=f"點名成功：{student.name}（{student.student_id}）"
        )

    return render_template_string(
        CHECKIN_HTML,
        session=session,
        message=None
    )