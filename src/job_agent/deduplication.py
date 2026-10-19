"""
Deduplication logic and content hash verification for job listings.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.job_agent.database import Database
    from src.job_agent.models import VerifiedJob


def normalize_text_for_hash(text: str) -> str:
    """Normalize text by collapsing whitespace and lowercasing."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip().lower()


def compute_job_id(employer: str, normalized_url: str) -> str:
    """
    Generate a deterministic, stable unique ID for a job listing
    based on employer name and normalized URL.
    """
    key = f"{normalize_text_for_hash(employer)}:{normalized_url.strip().lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def compute_content_hash(
    title: str,
    employer: str,
    description: str,
    location: str,
    experience_str: str = ""
) -> str:
    """
    Generate SHA-256 digest of key listing content to detect material updates
    such as changed requirements or updated job titles.
    """
    elements = [
        normalize_text_for_hash(title),
        normalize_text_for_hash(employer),
        normalize_text_for_hash(location),
        normalize_text_for_hash(experience_str),
        normalize_text_for_hash(description[:1000]),  # Primary summary chunk
    ]
    payload = "|".join(elements)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def check_existing_url(normalized_url: str, db: Database) -> bool:
    """Check if a normalized URL has already been recorded in the database."""
    return db.get_job_by_url(normalized_url) is not None
