from datetime import datetime, timedelta
from functools import wraps
from io import BytesIO
import base64
import os
import secrets

import qrcode
from flask import (
    Blueprint,
    request,
    redirect,
    url_for,
    render_template_string,
    send_file,
    session,
)

from .extensions import db
from .models import CourseSession, Student, Attendance
from .services.import_students import import_students_from_excel
from .services.export_service import build_attendance_excel

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "123456")


def login_required(view_func):
    @wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return view_func(*args, **kwargs)

    return wrapped_view


def generate_qr_base64(data: str) -> str:
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


LOGIN_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>管理員登入</title>
</head>
<body>
    <h1>管理員登入</h1>

    <form method="post">
        <label>密碼：</label>
        <input type="password" name="password" required>
        <button type="submit">登入</button>
    </form>

    {% if message %}
    <p style="color:red;">{{ message }}</p>
    {% endif %}
</body>
</html>
"""

DASHBOARD_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>管理後台</title>
</head>
<body>
    <h1>管理後台</h1>

    <p><a href="{{ url_for('admin.create_session') }}">建立新課次</a></p>
    <p><a href="{{ url_for('admin.upload_students') }}">匯入學生名單</a></p>
    <p><a href="{{ url_for('admin.attendance_records') }}">查看出席紀錄</a></p>
    <p><a href="{{ url_for('admin.export_attendance') }}">匯出 Excel 總表</a></p>
    <p><a href="{{ url_for('admin.clear_test_data') }}" onclick="return confirm('確定要清除所有測試課次與簽到紀錄嗎？學生名單會保留。');">清除測試資料</a></p>
    <p><a href="{{ url_for('admin.logout') }}">登出</a></p> 

    <h2>學生統計</h2>
    <p>目前學生總數：{{ student_count }}</p>
    <p>目前簽到總筆數：{{ attendance_count }}</p>

    <h2>目前課次</h2>
    <ul>
    {% for s in sessions %}
        <li>
            ID={{ s.id }} | {{ s.section }} | {{ s.course_date }}
            | 開始：{{ s.opens_at }}
            | 結束：{{ s.closes_at }}
            | <a href="{{ url_for('admin.session_qr', session_id=s.id) }}">顯示 QR code</a>
            | <a href="{{ url_for('checkin.checkin', session_id=s.id, token=s.qr_token) }}" target="_blank">學生簽到頁</a>
        </li>
    {% endfor %}
    </ul>
</body>
</html>
"""

CREATE_SESSION_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>建立課次</title>
</head>
<body>
    <h1>建立課次</h1>

    <form method="post">
        <label>時段：</label>
        <select name="section">
            <option value="週四">週四</option>
            <option value="週五">週五</option>
        </select>
        <button type="submit">建立 5 分鐘簽到課次</button>
    </form>

    {% if message %}
    <p style="color:green;">{{ message }}</p>
    {% endif %}

    <p><a href="{{ url_for('admin.dashboard') }}">回後台</a></p>
</body>
</html>
"""

UPLOAD_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>匯入學生名單</title>
</head>
<body>
    <h1>匯入學生名單</h1>

    <p>Excel 必須包含欄位：系級、學號、姓名、時段</p>

    <form method="post" enctype="multipart/form-data">
        <input type="file" name="student_file" accept=".xlsx,.xls" required>
        <button type="submit">上傳並匯入</button>
    </form>

    {% if message %}
    <p style="color:blue;">{{ message }}</p>
    {% endif %}

    <p><a href="{{ url_for('admin.dashboard') }}">回後台</a></p>
</body>
</html>
"""

ATTENDANCE_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>出席紀錄</title>
</head>
<body>
    <h1>出席紀錄</h1>

    <table border="1" cellpadding="6" cellspacing="0">
        <tr>
            <th>課次ID</th>
            <th>日期</th>
            <th>時段</th>
            <th>學號</th>
            <th>姓名</th>
            <th>系級</th>
            <th>簽到時間</th>
            <th>IP位址</th>
            <th>狀態</th>
        </tr>
        {% for row in rows %}
        <tr>
            <td>{{ row.session_id }}</td>
            <td>{{ row.course_date }}</td>
            <td>{{ row.section }}</td>
            <td>{{ row.student_id }}</td>
            <td>{{ row.name }}</td>
            <td>{{ row.department }}</td>
            <td>{{ row.signed_at }}</td>
            <td>{{ row.ip_address }}</td>
            <td>{{ row.status }}</td>
        </tr>
        {% endfor %}
    </table>

    <p><a href="{{ url_for('admin.dashboard') }}">回後台</a></p>
</body>
</html>
"""

QR_PAGE_HTML = """
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>課次 QR Code</title>
</head>
<body>
    <h1>課次 QR Code</h1>

    <p>課次 ID：{{ session.id }}</p>
    <p>時段：{{ session.section }}</p>
    <p>日期：{{ session.course_date }}</p>
    <p>開始：{{ session.opens_at }}</p>
    <p>截止：{{ session.closes_at }}</p>

    <p>請讓學生掃描下方 QR code 進行簽到：</p>

    <img src="data:image/png;base64,{{ qr_base64 }}" alt="QR Code" style="max-width: 360px;">

    <p>學生簽到網址：</p>
    <p><a href="{{ checkin_url }}" target="_blank">{{ checkin_url }}</a></p>

    <p><a href="{{ url_for('admin.dashboard') }}">回後台</a></p>
</body>
</html>
"""


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "").strip()
        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin.dashboard"))
        return render_template_string(LOGIN_HTML, message="密碼錯誤")

    return render_template_string(LOGIN_HTML, message=None)


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@login_required
def dashboard():
    sessions = CourseSession.query.order_by(CourseSession.id.desc()).all()
    student_count = Student.query.count()
    attendance_count = Attendance.query.count()

    return render_template_string(
        DASHBOARD_HTML,
        sessions=sessions,
        student_count=student_count,
        attendance_count=attendance_count,
    )


@admin_bp.route("/create-session", methods=["GET", "POST"])
@login_required
def create_session():
    if request.method == "POST":
        section = request.form.get("section", "").strip()

        now = datetime.now()
        session_obj = CourseSession(
            section=section,
            course_date=now.date(),
            opens_at=now,
            closes_at=now + timedelta(minutes=5),
            qr_token=secrets.token_urlsafe(24),
        )
        db.session.add(session_obj)
        db.session.commit()

        return redirect(url_for("admin.session_qr", session_id=session_obj.id))

    return render_template_string(
        CREATE_SESSION_HTML,
        message=None,
    )


@admin_bp.route("/session/<int:session_id>/qr")
@login_required
def session_qr(session_id):
    session_obj = CourseSession.query.get_or_404(session_id)

    checkin_url = url_for(
        "checkin.checkin",
        session_id=session_obj.id,
        token=session_obj.qr_token,
        _external=True,
    )

    qr_base64 = generate_qr_base64(checkin_url)

    return render_template_string(
        QR_PAGE_HTML,
        session=session_obj,
        checkin_url=checkin_url,
        qr_base64=qr_base64,
    )


@admin_bp.route("/upload-students", methods=["GET", "POST"])
@login_required
def upload_students():
    if request.method == "POST":
        file = request.files.get("student_file")
        if not file:
            return render_template_string(UPLOAD_HTML, message="請選擇 Excel 檔案")

        try:
            imported_count, updated_count = import_students_from_excel(file)
            msg = f"匯入完成：新增 {imported_count} 筆，更新 {updated_count} 筆"
            return render_template_string(UPLOAD_HTML, message=msg)
        except Exception as e:
            return render_template_string(UPLOAD_HTML, message=f"匯入失敗：{e}")

    return render_template_string(UPLOAD_HTML, message=None)


@admin_bp.route("/attendance")
@login_required
def attendance_records():
    records = (
        db.session.query(Attendance, Student, CourseSession)
        .join(Student, Attendance.student_id_fk == Student.id)
        .join(CourseSession, Attendance.session_id == CourseSession.id)
        .order_by(Attendance.signed_at.desc())
        .all()
    )

    rows = []
    for attendance, student, session_obj in records:
        rows.append({
            "session_id": session_obj.id,
            "course_date": session_obj.course_date,
            "section": session_obj.section,
            "student_id": student.student_id,
            "name": student.name,
            "department": student.department,
            "signed_at": attendance.signed_at,
            "ip_address": attendance.ip_address,
            "status": attendance.status,
        })

    return render_template_string(ATTENDANCE_HTML, rows=rows)


@admin_bp.route("/export-attendance")
@login_required
def export_attendance():
    output = build_attendance_excel()
    return send_file(
        output,
        as_attachment=True,
        download_name="attendance_report.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
@admin_bp.route("/clear-test-data")
@login_required
def clear_test_data():
    Attendance.query.delete()
    CourseSession.query.delete()
    db.session.commit()
    return redirect(url_for("admin.dashboard"))