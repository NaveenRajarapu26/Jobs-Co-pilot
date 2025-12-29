from datetime import datetime
from .db import db

class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # job info
    job_title = db.Column(db.String(255), nullable=False)
    job_company = db.Column(db.String(255), nullable=False)
    job_location = db.Column(db.String(255), nullable=True)
    job_url = db.Column(db.Text, nullable=True)

    # raw inputs (store for reproducibility)
    resume_filename = db.Column(db.String(255), nullable=True)
    resume_text = db.Column(db.Text, nullable=False)
    job_description = db.Column(db.Text, nullable=False)
    questions = db.Column(db.Text, nullable=True)  # store as newline string

    # outputs
    fit_score = db.Column(db.Integer, nullable=True)
    fit_level = db.Column(db.String(50), nullable=True)
    fit_reasons = db.Column(db.Text, nullable=True)  # store as JSON string
    fit_gaps = db.Column(db.Text, nullable=True)     # store as JSON string

    job_parsed_markdown = db.Column(db.Text, nullable=True)
    tailored_resume_md = db.Column(db.Text, nullable=True)
    cover_letter = db.Column(db.Text, nullable=True)
    qna = db.Column(db.Text, nullable=True)
