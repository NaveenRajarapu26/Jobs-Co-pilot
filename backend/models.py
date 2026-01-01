from datetime import datetime
from .db import db

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), default="pending", nullable=False)  # pending/approved/blocked
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    applications = db.relationship(
        "Application",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"   # optional
    )

class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)

    # job info
    job_title = db.Column(db.String(255), nullable=False)
    job_company = db.Column(db.String(255), nullable=False)
    job_location = db.Column(db.String(255), nullable=True)
    job_url = db.Column(db.Text, nullable=True)

    # raw inputs
    resume_filename = db.Column(db.String(255), nullable=True)
    resume_text = db.Column(db.Text, nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=True)

    # outputs
    fit_score = db.Column(db.Integer, nullable=True)
    fit_level = db.Column(db.String(50), nullable=True)
    fit_reasons = db.Column(db.Text, nullable=True)
    fit_gaps = db.Column(db.Text, nullable=True)

    job_parsed_markdown = db.Column(db.Text, nullable=True)
    tailored_resume_md = db.Column(db.Text, nullable=True)
    cover_letter = db.Column(db.Text, nullable=True)
    qna = db.Column(db.Text, nullable=True)
