from typing import Dict, Any, List
import json
from langgraph.graph import StateGraph, END
from .llm import get_llm

llm = get_llm()

def parse_job_node(state: Dict[str, Any]) -> Dict[str, Any]:
    job = state["job"]
    prompt = f"""
You are a hiring expert.

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}

DESCRIPTION:
\"\"\"{job['description']}\"\"\"

TASKS:
1. Summarize the role in 3–5 bullet points.
2. List MUST-HAVE skills.
3. List NICE-TO-HAVE skills.
4. Infer seniority level (Intern/Entry/Junior/Mid/Senior).
5. List top 10 ATS keywords.

Respond in markdown.
"""
    state["job_parsed_markdown"] = llm.invoke(prompt).content
    return state

def score_fit_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user = state["user"]
    job = state["job"]
    prompt = f"""
You are a recruiter and career coach.

CANDIDATE:
Name: {user['name']}
Headline: {user['headline']}
Location: {user['location']}
Key skills: {", ".join(user['key_skills'])}
Constraints: {user['constraints']}

RESUME:
\"\"\"{user['resume_text']}\"\"\"

JOB:
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}

DESCRIPTION:
\"\"\"{job['description']}\"\"\"

TASK:
Return JSON only:

{{
  "score": 0-100,
  "level": "Strong Fit" | "Moderate Fit" | "Weak Fit",
  "reasons": ["...", "..."],
  "gaps": ["...", "..."]
}}
"""
    text = llm.invoke(prompt).content
    start, end = text.find("{"), text.rfind("}")
    json_str = text[start:end+1] if start != -1 and end != -1 else text

    try:
        fit = json.loads(json_str)
    except json.JSONDecodeError:
        fit = {"score": 60, "level": "Unknown", "reasons": [text], "gaps": []}

    state["fit"] = fit
    return state

def resume_tailor_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user = state["user"]
    job = state["job"]
    prompt = f"""
You are a resume optimization assistant.

CANDIDATE RESUME:
\"\"\"{user['resume_text']}\"\"\"

JOB:
{job['title']} at {job['company']} in {job['location']}

DESCRIPTION:
\"\"\"{job['description']}\"\"\"

TASK:
1. Select 6–10 most relevant experiences/projects/achievements.
2. Rewrite into strong bullets with action verbs and metrics if possible.
3. Use job keywords but DO NOT lie or invent tools/roles.
4. Group under 2–3 mini headings.
5. Provide a one-line suggested headline tailored to this job.

Output markdown with headings.
"""
    state["tailored_resume_md"] = llm.invoke(prompt).content
    return state

def cover_letter_node(state: Dict[str, Any]) -> Dict[str, Any]:
    user = state["user"]
    job = state["job"]
    fit = state["fit"]
    prompt = f"""
You are an expert cover letter writer.

CANDIDATE:
Name: {user['name']}
Headline: {user['headline']}
Location: {user['location']}
Constraints: {user['constraints']}

RESUME:
\"\"\"{user['resume_text']}\"\"\"

JOB:
{job['title']} at {job['company']} in {job['location']}

DESCRIPTION:
\"\"\"{job['description']}\"\"\"

FIT:
Score: {fit.get("score")}
Level: {fit.get("level")}
Reasons: {fit.get("reasons")}
Gaps: {fit.get("gaps")}

TASK:
Write a tailored cover letter (350–450 words):
- Mention role & company early
- Connect 2–3 specific experiences to the job
- Be specific, professional, not fluffy
- Do NOT invent experience

Output ONLY the letter text.
"""
    state["cover_letter"] = llm.invoke(prompt).content
    return state

def qna_node(state: Dict[str, Any]) -> Dict[str, Any]:
    questions: List[str] = state.get("questions", [])
    if not questions:
        return state

    user = state["user"]
    job = state["job"]
    q_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))

    prompt = f"""
You help candidates answer job application questions.

CANDIDATE:
Name: {user['name']}
Headline: {user['headline']}
Location: {user['location']}
Key skills: {", ".join(user['key_skills'])}
Constraints: {user['constraints']}

RESUME:
\"\"\"{user['resume_text']}\"\"\"

JOB:
{job['title']} at {job['company']} ({job['location']})

DESCRIPTION:
\"\"\"{job['description']}\"\"\"

QUESTIONS:
{q_text}

TASK:
Answer each question in 3–6 sentences with numbered answers.
"""
    state["qna"] = llm.invoke(prompt).content
    return state

def build_job_graph():
    graph = StateGraph(dict)
    graph.add_node("parse_job", parse_job_node)
    graph.add_node("score_fit", score_fit_node)
    graph.add_node("resume_tailor", resume_tailor_node)
    graph.add_node("cover_letter", cover_letter_node)
    graph.add_node("qna", qna_node)

    graph.set_entry_point("parse_job")
    graph.add_edge("parse_job", "score_fit")
    graph.add_edge("score_fit", "resume_tailor")
    graph.add_edge("resume_tailor", "cover_letter")
    graph.add_edge("cover_letter", "qna")
    graph.add_edge("qna", END)
    return graph.compile()
