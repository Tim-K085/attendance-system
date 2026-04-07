from datetime import datetime
from .extensions import db

class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    raw_name = db.Column(db.String(200))
    department = db.Column(db.String(200))
    section = db.Column(db.String(20), nullable=False)   # 週四 / 週五
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CourseSession(db.Model):
    __tablename__ = "course_sessions"

    id = db.Column(db.Integer, primary_key=True)
    section = db.Column(db.String(20), nullable=False)
    course_date = db.Column(db.Date, nullable=False)
    opens_at = db.Column(db.DateTime, nullable=False)
    closes_at = db.Column(db.DateTime, nullable=False)
    qr_token = db.Column(db.String(200), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    __tablename__ = "attendances"

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("course_sessions.id"), nullable=False)
    student_id_fk = db.Column(db.Integer, db.ForeignKey("students.id"), nullable=False)
    signed_at = db.Column(db.DateTime, nullable=False)
    ip_address = db.Column(db.String(100))
    user_agent = db.Column(db.String(500))
    status = db.Column(db.String(50), default="present")

    __table_args__ = (
        db.UniqueConstraint("session_id", "student_id_fk", name="uq_session_student"),
    )