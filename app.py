import os
import json
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash

from backend.extractors import load_resume_text, fetch_job_description_from_url
from backend.graph import build_job_graph
from backend.db import init_db, db
from backend.models import Application

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# ✅ SET DB URI BEFORE init_db(app)
db_url = os.getenv("DATABASE_URL") or "sqlite:///local.db"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# ✅ NOW initialize SQLAlchemy + Migrate
init_db(app)


UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

compiled_graph = build_job_graph()

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/run", methods=["POST"])
def run_agent():
    # ----- User info -----
    name = request.form.get("name", "Candidate").strip()
    headline = request.form.get("headline", "").strip()
    location = request.form.get("location", "").strip()
    constraints = request.form.get("constraints", "").strip()

    skills_raw = request.form.get("skills", "").strip()
    key_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]

    # ----- Job info -----
    job_title = request.form.get("job_title", "").strip()
    job_company = request.form.get("job_company", "").strip()
    job_location = request.form.get("job_location", "").strip()
    job_url = request.form.get("job_url", "").strip()
    jd_text = request.form.get("job_description", "").strip()

    # ----- Questions -----
    questions_raw = request.form.get("questions", "").strip()
    questions = [q.strip() for q in questions_raw.splitlines() if q.strip()] if questions_raw else []

    # ----- Resume upload -----
    file = request.files.get("resume_file")
    if not file or file.filename.strip() == "":
        flash("Please upload a resume file (PDF/DOCX/TXT).", "danger")
        return redirect(url_for("index"))

    filename = secure_filename(file.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        flash("Unsupported file type. Use PDF/DOCX/TXT.", "danger")
        return redirect(url_for("index"))

    save_path = UPLOAD_DIR / filename
    file.save(save_path)

    try:
        resume_text = load_resume_text(str(save_path))
        if len(resume_text.strip()) < 50:
            flash("Resume text extraction looks empty. Try DOCX or a text-based PDF.", "warning")
    except Exception as e:
        flash(f"Failed to extract resume text: {e}", "danger")
        return redirect(url_for("index"))

    # ----- JD extraction -----
    if job_url and not jd_text:
        try:
            jd_text = fetch_job_description_from_url(job_url)
        except Exception as e:
            flash(f"Failed to fetch JD from URL. Paste JD text instead. Error: {e}", "warning")

    if not jd_text:
        flash("Please provide a Job Description URL or paste JD text.", "danger")
        return redirect(url_for("index"))

    # ----- Run graph -----
    state = {
        "user": {
            "name": name,
            "headline": headline,
            "location": location,
            "resume_text": resume_text,
            "key_skills": key_skills,
            "constraints": constraints,
        },
        "job": {
            "title": job_title,
            "company": job_company,
            "location": job_location,
            "description": jd_text,
            "source_url": job_url,
        },
        "questions": questions,
    }

    result = compiled_graph.invoke(state)

    




    #...
    fit = result.get("fit", {})
    app_row = Application(
        job_title=state["job"]["title"],
        job_company=state["job"]["company"],
        job_location=state["job"]["location"],
        job_url=state["job"]["source_url"],
        resume_filename=filename,
        resume_text=state["user"]["resume_text"],
        job_description=state["job"]["description"],
        questions="\n".join(state.get("questions", [])) if state.get("questions") else None,

        fit_score=fit.get("score"),
        fit_level=fit.get("level"),
        fit_reasons=json.dumps(fit.get("reasons", [])),
        fit_gaps=json.dumps(fit.get("gaps", [])),

        job_parsed_markdown=result.get("job_parsed_markdown"),
        tailored_resume_md=result.get("tailored_resume_md"),
        cover_letter=result.get("cover_letter"),
        qna=result.get("qna"),
    )

    from backend.db import db
    db.session.add(app_row)
    db.session.commit()


    return render_template(
        "result.html",
        result=result,
        job=state["job"],
        user=state["user"],
    )
from backend.models import Application

@app.route("/applications")
def applications():
    apps = Application.query.order_by(Application.created_at.desc()).limit(50).all()
    return render_template("applications.html", apps=apps)

@app.route("/applications/<int:app_id>")
def application_detail(app_id: int):
    row = Application.query.get_or_404(app_id)

    # shape it like result.html expects
    result = {
        "fit": {
            "score": row.fit_score,
            "level": row.fit_level,
            "reasons": json.loads(row.fit_reasons or "[]"),
            "gaps": json.loads(row.fit_gaps or "[]"),
        },
        "job_parsed_markdown": row.job_parsed_markdown,
        "tailored_resume_md": row.tailored_resume_md,
        "cover_letter": row.cover_letter,
        "qna": row.qna,
    }
    job = {
        "title": row.job_title,
        "company": row.job_company,
        "location": row.job_location,
        "source_url": row.job_url,
    }
    user = {}  # optional
    return render_template("result.html", result=result, job=job, user=user)


if __name__ == "__main__":
    app.run(debug=True)
