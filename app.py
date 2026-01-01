import os
import json
from pathlib import Path

from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, url_for, flash, session

from backend.extractors import load_resume_text, fetch_job_description_from_url
from backend.graph import build_job_graph
from backend.db import init_db, db
from backend.models import Application, User
from backend.auth import (
    login_required,
    admin_required,
    approved_required,   # ✅ NEW
    create_user,
    authenticate,
    ensure_admin_seed,
)

from backend.jd_parser import extract_job_metadata

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret")

# ---- Database config (SQLite locally, Postgres on Render) ----
db_url = os.getenv("DATABASE_URL") or "sqlite:///local.db"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

init_db(app)

# Seed admin user from env vars (ADMIN_EMAIL / ADMIN_PASSWORD)
if not os.getenv("FLASK_SKIP_SEED"):
    with app.app_context():
        ensure_admin_seed()

# ---- Uploads ----
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}

# ---- Build graph once ----
compiled_graph = build_job_graph()


# ----------------------------
# Small helper: keep session in sync
# ----------------------------
def sync_session_user():
    uid = session.get("user_id")
    if not uid:
        return None

    u = User.query.get(uid)
    if not u:
        session.clear()
        return None

    # keep session fresh
    session["user_email"] = u.email
    session["is_admin"] = bool(u.is_admin)
    session["user_status"] = u.status   # ✅ ADD THIS LINE

    return u



# ----------------------------
# Auth routes
# ----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    try:
        create_user(email, password)
        flash("Account created. Waiting for admin approval.", "success")
        return redirect(url_for("login"))
    except Exception as e:
        flash(str(e), "danger")
        return redirect(url_for("signup"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    result = authenticate(email, password)

    if result == "NOT_APPROVED":
        flash("Your account is not approved yet. Please wait for admin approval.", "warning")
        return redirect(url_for("login"))

    if not result:
        flash("Invalid credentials.", "danger")
        return redirect(url_for("login"))

    # ✅ store everything needed for UX badge + admin routing
    session["user_id"] = result.id
    session["user_email"] = result.email
    session["is_admin"] = bool(result.is_admin)
    session["user_status"] = result.status 
    #session["status"] = result.status

    flash("Logged in successfully.", "success")
    next_url = request.args.get("next")
    return redirect(next_url or url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))


# ----------------------------
# Admin routes
# ----------------------------


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    sync_session_user()

    users = User.query.order_by(User.created_at.desc()).all()

    # Dashboard stats
    stats = {
        "total_users": User.query.count(),
        "pending_users": User.query.filter_by(status="pending").count(),
        "total_apps": Application.query.count(),
    }

    return render_template("admin_users.html", users=users, stats=stats)



@app.route("/admin/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_user(user_id: int):
    sync_session_user()

    u = User.query.get_or_404(user_id)
    u.status = "approved"
    db.session.commit()
    flash(f"Approved {u.email}", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/block", methods=["POST"])
@login_required
@admin_required
def block_user(user_id: int):
    sync_session_user()

    u = User.query.get_or_404(user_id)
    if u.is_admin:
        flash("Cannot block an admin account.", "warning")
        return redirect(url_for("admin_users"))

    u.status = "blocked"
    db.session.commit()
    flash(f"Blocked {u.email}", "warning")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id: int):
    sync_session_user()

    u = User.query.get_or_404(user_id)
    if u.is_admin:
        flash("Cannot delete an admin account.", "warning")
        return redirect(url_for("admin_users"))

    # delete applications first (safer if FK constraints exist)
    Application.query.filter_by(user_id=u.id).delete()
    db.session.delete(u)
    db.session.commit()

    flash(f"Deleted user {u.email}", "success")
    return redirect(url_for("admin_users"))


# ----------------------------
# App routes
# ----------------------------

@app.route("/", methods=["GET"])
def root():
    # If user already logged in → go to app
    if session.get("user_id"):
        return redirect(url_for("index"))  # /app

    # Otherwise show landing page
    return redirect(url_for("home"))


@app.route("/app", methods=["GET"])
@login_required
def index():
    u = sync_session_user()
    return render_template("index.html", user=u)



@app.route("/run", methods=["POST"])
@login_required
@approved_required   # ✅ NEW: blocks pending/blocked users
def run_agent():
    sync_session_user()

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

    

    # 🔍 Auto-extract from JD if missing
    parsed = extract_job_metadata(jd_text)

    job_title = job_title or parsed.get("title") or "Unknown Role"
    job_company = job_company or parsed.get("company") or "Unknown Company"
    job_location = job_location or parsed.get("location")


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

    # ----- Save to DB -----
    fit = result.get("fit", {})
    user_id = session["user_id"]

    app_row = Application(
        user_id=user_id,
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

    db.session.add(app_row)
    db.session.commit()

    return render_template("result.html", result=result, job=state["job"], user=state["user"])


@app.route("/applications")
@login_required
def applications():
    sync_session_user()

    apps = (
        Application.query.filter_by(user_id=session["user_id"])
        .order_by(Application.created_at.desc())
        .limit(50)
        .all()
    )
    return render_template("applications.html", apps=apps)


@app.route("/applications/<int:app_id>")
@login_required
def application_detail(app_id: int):
    sync_session_user()

    row = Application.query.get_or_404(app_id)

    # Only owner or admin can view
    if (row.user_id != session["user_id"]) and (not session.get("is_admin")):
        flash("You do not have access to this application.", "danger")
        return redirect(url_for("applications"))

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

    return render_template("result.html", result=result, job=job, user={})

@app.route("/home")
def home():
    # Public landing page (no login required)
    return render_template("home.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "GET":
        return render_template("contact.html")

    # simple form handling (email to console/log for now)
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()

    if not name or not email or not message:
        flash("Please fill all fields.", "warning")
        return redirect(url_for("contact"))

    # Later you can email this / store in DB
    app.logger.info(f"[CONTACT] {name} <{email}>: {message}")

    flash("Thanks! We got your message and will get back soon.", "success")
    return redirect(url_for("contact"))


if __name__ == "__main__":
    app.run(debug=True)
