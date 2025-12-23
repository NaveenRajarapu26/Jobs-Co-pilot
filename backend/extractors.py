from pathlib import Path
import requests
import trafilatura
from pypdf import PdfReader
import docx

def extract_text_from_pdf(path: str) -> str:
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()

def extract_text_from_docx(path: str) -> str:
    d = docx.Document(path)
    return "\n".join(p.text for p in d.paragraphs).strip()

def extract_text_from_txt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore").strip()

def load_resume_text(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    if ext == ".docx":
        return extract_text_from_docx(file_path)
    if ext in [".txt", ".md"]:
        return extract_text_from_txt(file_path)
    raise ValueError(f"Unsupported resume file type: {ext}. Use PDF/DOCX/TXT")

def fetch_job_description_from_url(url: str, timeout: int = 20) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()

    extracted = trafilatura.extract(r.text, include_comments=False, include_tables=False)
    if extracted and len(extracted.strip()) > 200:
        return extracted.strip()

    # fallback: return html if extraction fails
    return r.text
