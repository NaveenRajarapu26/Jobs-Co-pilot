# Jobs-Co-Pilot 🚀

> Upload your resume, paste a job description — get a tailored resume, cover letter, ATS fit score, and interview prep in under 60 seconds.



---

## Why I Built This

Every time I applied for a job, I was doing the same tedious work — reading the JD, manually tweaking my resume, writing a cover letter from scratch, then trying to guess what they'd ask in the interview. I wanted one tool that does all of that automatically.

Jobs-Co-Pilot takes your resume and a job description, runs them through a pipeline of 4 AI agents, and hands back everything you need for that application — tailored resume, cover letter, fit score, and interview Q&A — in one shot.

---

## How It Works

You upload your resume (PDF, DOCX, or TXT) and either paste a job description or drop a job posting URL. The app scrapes the JD if needed, then kicks off a LangGraph multi-agent pipeline:

| Agent | What It Does |
|---|---|
| **JD Parser** | Pulls out the job title, company, location, and required skills from the JD |
| **ATS Fit Scorer** | Scores how well your resume matches the JD — gives you a fit level, what's matching, and what's missing |
| **Resume Tailor** | Rewrites your resume bullets to align with the JD keywords and requirements |
| **Cover Letter + Q&A Writer** | Writes a cover letter and interview Q&A using the tailored resume and JD as context |

Each agent builds on the previous one — the cover letter knows what changed in your resume, and the interview prep is grounded in the actual job description, not generic advice.

---

## Architecture
```
Resume (PDF/DOCX/TXT) + Job Description (text or URL)
              │
              ▼
   ┌──────────────────────┐
   │   LangGraph Pipeline  │
   │                      │
   │  [JD Parser]         │
   │       ↓              │
   │  [ATS Fit Scorer]    │
   │       ↓              │
   │  [Resume Tailor]     │
   │       ↓              │
   │  [Cover Letter+Q&A]  │
   └──────────────────────┘
              │
              ▼
   Flask → PostgreSQL (Render)
         → SQLite (local dev)
```

The pipeline is compiled once at startup and invoked per request. All 4 agents share a single state object — so every downstream agent has full context from the agents before it.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM chaining | LangChain |
| LLM inference | Groq API |
| Backend | Flask |
| Database | PostgreSQL (Render) / SQLite (local) |
| ORM + migrations | Flask-SQLAlchemy + Flask-Migrate |
| Resume parsing | pypdf + python-docx |
| JD scraping | trafilatura + BeautifulSoup4 |
| Auth | passlib[bcrypt] |
| Deployment | Render |

---

## Features

**Auth + admin system**
Built a full signup/login system with an admin approval gate — new users can't access the app until an admin approves them. There's an admin panel at `/admin/users` to approve, block, or delete accounts and see usage stats.

**Application history**
Every run gets saved to the database. You can go back to `/applications` and pull up any previous run — fit score, tailored resume, cover letter all stored. Each user only sees their own history.

**JD from a URL**
You don't have to copy-paste the job description. Drop the job posting URL and the app scrapes and extracts the JD text automatically using trafilatura.

**Works with any resume format**
PDF, DOCX, TXT, Markdown — all handled. If text extraction comes back empty, the app warns you instead of silently failing.

---

## Running Locally
```bash
git clone https://github.com/NaveenRajarapu26/Jobs-Co-pilot.git
cd Jobs-Co-pilot

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Add your keys to .env

flask db upgrade
python app.py
# Running at http://localhost:5000
```

---

## Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Your Groq API key |
| `FLASK_SECRET_KEY` | Flask session secret |
| `ADMIN_EMAIL` | Admin account email |
| `ADMIN_PASSWORD` | Admin account password |
| `DATABASE_URL` | Postgres URL on Render (falls back to SQLite locally) |
| `LANGCHAIN_API_KEY` | Optional — for LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | Set to `true` to enable tracing |

---

## Project Structure
```
Jobs-Co-pilot/
├── app.py                  # Routes, auth, DB setup
├── backend/
│   ├── graph.py            # LangGraph pipeline
│   ├── agents/             # The 4 agent nodes
│   ├── extractors.py       # Resume + JD extraction
│   ├── jd_parser.py        # Job metadata parsing
│   ├── models.py           # User + Application models
│   ├── db.py               # DB init
│   └── auth.py             # Auth logic + decorators
├── templates/              # Jinja2 templates
├── static/css/
├── migrations/
└── requirements.txt
```

---

## Things I Learned Building This

**LangGraph over a simple chain** — I started with a basic LangChain chain but hit a wall when agents needed to share state. LangGraph's graph structure made it easy to pass context between agents and add new nodes without breaking everything.

**Prompt regression is sneaky** — changing how one agent formats its output broke the next agent downstream. Lesson: test each agent in isolation before testing the full pipeline.

**trafilatura is great for job postings** — tried BeautifulSoup first but it pulled in too much noise. trafilatura handles messy career pages much better.

**SQLite → Postgres is painless with Flask-Migrate** — the only gotcha was SQLAlchemy needing `postgresql://` instead of `postgres://`. One line fix.

---


