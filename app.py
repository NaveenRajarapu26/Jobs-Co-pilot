import os
from pathlib import Path
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash

from backend.extractors import load_resume_text, fetch_job_description_from_url
from backend.graph import build_job_graph

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

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

    return render_template(
        "result.html",
        result=result,
        job=state["job"],
        user=state["user"],
    )

if __name__ == "__main__":
    app.run(debug=True)
