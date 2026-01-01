import re

def extract_job_metadata(jd_text: str):
    """
    Very lightweight heuristic-based extraction.
    Safe fallback if LLM parsing fails.
    """
    text = jd_text.strip()

    title = None
    company = None
    location = None

    # --- Job Title ---
    title_patterns = [
        r"Job Title[:\-]\s*(.+)",
        r"Position[:\-]\s*(.+)",
        r"Role[:\-]\s*(.+)",
    ]
    for p in title_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            title = m.group(1).strip()
            break

    # --- Company ---
    company_patterns = [
        r"Company[:\-]\s*(.+)",
        r"About\s+([A-Z][A-Za-z0-9 &]+)",
    ]
    for p in company_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            company = m.group(1).strip()
            break

    # --- Location ---
    loc_patterns = [
        r"Location[:\-]\s*(.+)",
        r"based in\s+([A-Za-z ,]+)",
    ]
    for p in loc_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            location = m.group(1).strip()
            break

    return {
        "title": title,
        "company": company,
        "location": location,
    }
