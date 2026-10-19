"""
Candidate eligibility extraction and evaluation engine.
Extracts experience, graduation years, degree disciplines, and technical skills.
"""

from __future__ import annotations

import re
from typing import Any
from src.job_agent.models import (
    CandidateProfile,
    CareerTrack,
    EmploymentType,
    WorkMode,
)

# Common prompt injection patterns or untrusted instruction markers in scraped texts
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s*prompt", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
    re.compile(r"override\s+(all\s+)?rules", re.IGNORECASE),
]

# Patterns for experience requirements
# Matches e.g. "0-1 years", "1 to 2 yrs", "2+ years", "minimum 3 years", "at least 2 years"
_EXP_RANGE_PATTERN = re.compile(
    r"\b(?:(?:minimum|at\s+least|min\.?)\s*)?(\d+)(?:\s*(?:-|–|to)\s*(\d+))?\+?\s*(?:years?|yrs?)(?:\s*(?:of)?\s*(?:relevant|hands-on|industry|work|professional)?\s*experience)?\b",
    re.IGNORECASE
)

# Explicit fresher / entry level / intern indicators
_FRESHER_KEYWORDS = [
    "fresher", "freshers", "entry level", "entry-level", "graduate trainee",
    "intern", "internship", "0-1 years", "0 - 1 years", "0 to 1 years",
    "no experience required", "junior", "associate", "new grad", "campus hiring",
    "off campus", "trainee engineer", "get", "ase"
]

# Patterns for graduation batches (e.g. "2026 batch", "2026 passout", "batch of 2026", "2025/2026")
_BATCH_PATTERN = re.compile(
    r"\b(?:batch\s*(?:of)?\s*|passing\s*out\s*(?:in)?\s*|graduating\s*(?:in)?\s*|passout\s*(?:in)?\s*)?(202[4-8])\b",
    re.IGNORECASE
)

# Recognized engineering disciplines
_DEGREE_PATTERNS = {
    "B.Tech": re.compile(r"\b(b\.?tech|bachelor of technology)\b", re.IGNORECASE),
    "B.E.": re.compile(r"\b(b\.?e\.?|bachelor of engineering)\b", re.IGNORECASE),
    "M.Tech": re.compile(r"\b(m\.?tech|master of technology)\b", re.IGNORECASE),
    "MCA": re.compile(r"\b(mca|master of computer applications)\b", re.IGNORECASE),
    "Computer Science": re.compile(r"\b(computer science|cs|cse|information technology|it)\b", re.IGNORECASE),
    "Data Science / AI": re.compile(r"\b(data science|artificial intelligence|ai/ml)\b", re.IGNORECASE),
}

# Recognized technical skills
_SKILLS_KEYWORDS = {
    "Python": re.compile(r"\bpython\b", re.IGNORECASE),
    "Machine Learning": re.compile(r"\b(machine learning|ml)\b", re.IGNORECASE),
    "Deep Learning": re.compile(r"\b(deep learning|dl|neural networks)\b", re.IGNORECASE),
    "Generative AI": re.compile(r"\b(generative ai|genai|gen ai)\b", re.IGNORECASE),
    "LLM": re.compile(r"\b(llm|large language models?)\b", re.IGNORECASE),
    "RAG": re.compile(r"\b(rag|retrieval augmented generation)\b", re.IGNORECASE),
    "LangChain": re.compile(r"\b(langchain|langgraph|llamaindex)\b", re.IGNORECASE),
    "FastAPI": re.compile(r"\b(fastapi|flask|django)\b", re.IGNORECASE),
    "SQL": re.compile(r"\b(sql|postgresql|postgres|mysql|sqlite)\b", re.IGNORECASE),
    "Git": re.compile(r"\b(git|github|gitlab)\b", re.IGNORECASE),
    "DSA": re.compile(r"\b(data structures|algorithms|dsa|problem solving)\b", re.IGNORECASE),
    "PyTorch": re.compile(r"\b(pytorch|torch)\b", re.IGNORECASE),
    "TensorFlow": re.compile(r"\btensorflow\b", re.IGNORECASE),
}


def sanitize_job_text(text: str) -> str:
    """
    Sanitize untrusted text scraped from external job listings.
    Neutralizes attempts to embed prompt injections or dangerous terminal sequences.
    """
    if not text:
        return ""
    # Strip null bytes and control chars
    cleaned = "".join(ch for ch in text if ch >= " " or ch in "\n\r\t")
    # Defuse detected instruction overrides
    for pattern in _PROMPT_INJECTION_PATTERNS:
        cleaned = pattern.sub("[SAFETY_NEUTRALIZED]", cleaned)
    return cleaned.strip()


def extract_experience_requirements(text: str) -> tuple[float | None, float | None, str]:
    """
    Extract minimum and maximum years of experience from job text.
    Returns:
        (min_years, max_years, raw_match_string)
        min_years is None if experience is unknown/not explicitly specified.
    """
    clean = sanitize_job_text(text)
    
    # 1. First check for explicit fresher keywords
    has_fresher_keyword = any(kw in clean.lower() for kw in _FRESHER_KEYWORDS)

    # 2. Search for explicit numeric experience specifications
    matches = list(_EXP_RANGE_PATTERN.finditer(clean))
    
    if not matches:
        if has_fresher_keyword:
            return 0.0, 1.0, "Fresher / Entry level indicated"
        return None, None, "Unknown"

    # Find the most restrictive/relevant requirement mentioned
    min_exp_found: float | None = None
    max_exp_found: float | None = None
    best_match_text = "Unknown"

    for m in matches:
        low_str = m.group(1)
        high_str = m.group(2)
        match_str = m.group(0)

        low_val = float(low_str) if low_str else None
        high_val = float(high_str) if high_str else None

        # If low_val is 0 (e.g. "0-2 years", "0-1 years"), low experience is 0
        if low_val is not None:
            if min_exp_found is None or low_val < min_exp_found:
                min_exp_found = low_val
                max_exp_found = high_val if high_val is not None else low_val
                best_match_text = match_str

    if min_exp_found is None and has_fresher_keyword:
        return 0.0, 1.0, "Fresher / Entry level indicated"

    return min_exp_found, max_exp_found, best_match_text


def extract_graduation_batches(text: str) -> list[int]:
    """Extract mentioned graduation batches/years."""
    clean = sanitize_job_text(text)
    batches = set()
    for m in _BATCH_PATTERN.finditer(clean):
        try:
            year = int(m.group(1))
            if 2023 <= year <= 2028:
                batches.add(year)
        except (ValueError, IndexError):
            continue
    return sorted(list(batches))


def extract_degrees(text: str) -> list[str]:
    """Extract recognized engineering and technical degrees."""
    clean = sanitize_job_text(text)
    found = []
    for degree_name, pattern in _DEGREE_PATTERNS.items():
        if pattern.search(clean):
            found.append(degree_name)
    return found


def extract_matched_skills(text: str) -> list[str]:
    """Extract matching candidate technical skills from listing text."""
    clean = sanitize_job_text(text)
    matched = []
    for skill, pattern in _SKILLS_KEYWORDS.items():
        if pattern.search(clean):
            matched.append(skill)
    return matched


def detect_career_track(title: str, description: str = "") -> CareerTrack:
    """Classify the job into one of the designated career tracks."""
    combined = f"{title} {description}".lower()

    # Track A: AI / Machine Learning / Data Science
    ai_keywords = [
        "ai", "artificial intelligence", "machine learning", "ml", "deep learning",
        "generative ai", "genai", "llm", "rag", "data scientist", "nlp", "computer vision",
        "applied ai", "ai research"
    ]
    for kw in ai_keywords:
        # Match word boundary for short abbreviations like 'ai' or 'ml'
        if re.search(rf"\b{re.escape(kw)}\b", combined):
            return CareerTrack.AI_ML

    # Track B: Mass Hiring & IT Services Trainee Programs
    mass_hiring_keywords = [
        "graduate engineer trainee", "get", "associate software engineer", "ase",
        "graduate trainee", "trainee software engineer", "national qualifier test",
        "tcs nqt", "off-campus", "campus drive", "national hiring", "nextstep",
        "fresher hiring", "trainee"
    ]
    for kw in mass_hiring_keywords:
        if re.search(rf"\b{re.escape(kw)}\b", combined):
            return CareerTrack.MASS_HIRING

    # Track A2: Python Backend / Software Engineering
    backend_keywords = [
        "python", "backend", "software engineer", "software developer", "sde",
        "sde-1", "sde 1", "software engineer i", "junior developer", "api engineer"
    ]
    for kw in backend_keywords:
        if re.search(rf"\b{re.escape(kw)}\b", combined):
            return CareerTrack.SOFTWARE_BACKEND

    return CareerTrack.OTHER


def detect_work_mode(text: str) -> WorkMode:
    """Identify remote, hybrid, or on-site work arrangement."""
    lower = text.lower()
    if re.search(r"\bremote\b|\bwork from home\b|\bwfh\b", lower):
        return WorkMode.REMOTE
    if re.search(r"\bhybrid\b", lower):
        return WorkMode.HYBRID
    if re.search(r"\bon-site\b|\bonsite\b|\bin-office\b|\boffice-based\b", lower):
        return WorkMode.ON_SITE
    return WorkMode.UNKNOWN


def detect_employment_type(text: str) -> EmploymentType:
    """Identify full-time, internship, or trainee employment."""
    lower = text.lower()
    if re.search(r"\bintern\b|\binternship\b", lower):
        return EmploymentType.INTERNSHIP
    if re.search(r"\btrainee\b|\bget\b|\base\b", lower):
        return EmploymentType.TRAINEE
    if re.search(r"\bfull[- ]time\b|\bpermanent\b", lower):
        return EmploymentType.FULL_TIME
    if re.search(r"\bcontract\b", lower):
        return EmploymentType.CONTRACT
    return EmploymentType.UNKNOWN


def evaluate_fresher_eligibility(
    title: str,
    description: str,
    profile: CandidateProfile
) -> tuple[bool, str, float | None, list[int], list[str]]:
    """
    Evaluate candidate eligibility against strict fresher and experience rules.

    Returns:
        (is_eligible, reason_or_status, min_exp, batches, matched_skills)

    Rules:
        - If required minimum experience is strictly >= 2.0 years -> REJECT (REJECTED_EXPERIENCE).
        - If minimum experience <= 1.0 or 0 -> ELIGIBLE.
        - If minimum experience is unknown (None) -> ELIGIBLE_UNKNOWN (not rejected, treated as unknown).
        - Matched skills, batches, degrees extracted.
    """
    combined_text = f"{title}\n{description}"
    min_exp, max_exp, raw_exp_match = extract_experience_requirements(combined_text)
    batches = extract_graduation_batches(combined_text)
    skills = extract_matched_skills(combined_text)

    # 1. Mandatory Gate: Strict experience requirement check
    if min_exp is not None and min_exp >= 2.0:
        return (
            False,
            f"Explicitly requires {min_exp:.1f}+ years experience (matches: '{raw_exp_match}')",
            min_exp,
            batches,
            skills
        )

    # 2. Check if a conflicting past graduation batch is strictly mandated (e.g. only 2021/2022)
    if batches:
        has_allowed_batch = any(b in profile.allowed_batches for b in batches)
        # If specific batches are listed and NONE match candidate's allowed batches (e.g. strictly for 2022 batch)
        if not has_allowed_batch and all(b < min(profile.allowed_batches) for b in batches):
            return (
                False,
                f"Restricted to older graduation batches: {batches} (Candidate batch is {profile.graduation_batch})",
                min_exp,
                batches,
                skills
            )

    return (True, "Eligible", min_exp, batches, skills)
