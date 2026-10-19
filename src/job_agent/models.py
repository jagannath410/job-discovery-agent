"""
Data models and typed structures for the Daily Fresher Job Discovery Agent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl


class VerificationStatus(str, Enum):
    """Job verification status codes."""
    VERIFIED_ACTIVE = "VERIFIED_ACTIVE"
    UNCONFIRMED = "UNCONFIRMED"
    EXPIRED = "EXPIRED"
    REJECTED_DOMAIN = "REJECTED_DOMAIN"
    REJECTED_EXPERIENCE = "REJECTED_EXPERIENCE"
    REJECTED_PROFILE = "REJECTED_PROFILE"
    DUPLICATE = "DUPLICATE"


class CareerTrack(str, Enum):
    """Job categorization tracks."""
    AI_ML = "AI_ML"
    SOFTWARE_BACKEND = "SOFTWARE_BACKEND"
    MASS_HIRING = "MASS_HIRING"
    OTHER = "OTHER"


class WorkMode(str, Enum):
    """Work arrangement mode."""
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ON_SITE = "ON_SITE"
    UNKNOWN = "UNKNOWN"


class EmploymentType(str, Enum):
    """Employment nature."""
    FULL_TIME = "FULL_TIME"
    INTERNSHIP = "INTERNSHIP"
    TRAINEE = "TRAINEE"
    CONTRACT = "CONTRACT"
    UNKNOWN = "UNKNOWN"


class CandidateProfile(BaseModel):
    """Configuration representing candidate preferences, skills, and eligibility."""
    graduation_disciplines: list[str] = Field(
        default_factory=lambda: [
            "B.Tech", "B.E.", "Computer Science", "Information Technology",
            "Artificial Intelligence", "Data Science", "MCA"
        ]
    )
    graduation_batch: int = 2026
    allowed_batches: list[int] = Field(default_factory=lambda: [2025, 2026, 2027])
    max_experience_years: float = 1.0  # Max acceptable. If explicit requirement is >= 2.0, reject.
    primary_country: str = "India"
    allowed_countries: list[str] = Field(default_factory=lambda: ["India", "Remote"])
    target_tracks: list[CareerTrack] = Field(
        default_factory=lambda: [CareerTrack.AI_ML, CareerTrack.SOFTWARE_BACKEND, CareerTrack.MASS_HIRING]
    )
    technical_skills: list[str] = Field(
        default_factory=lambda: [
            "Python", "Machine Learning", "Deep Learning", "Generative AI",
            "RAG", "LangChain", "FastAPI", "SQL", "Git", "DSA"
        ]
    )
    priority_employers: list[str] = Field(
        default_factory=lambda: [
            "TCS", "Wipro", "Cognizant", "Infosys", "Accenture",
            "Capgemini", "LTIMindtree", "HCLTech"
        ]
    )


class RawJobPosting(BaseModel):
    """Raw candidate job discovery from a search adapter before deep verification."""
    id: str
    title: str
    original_url: str
    employer_name: str
    description: str = ""
    source_adapter: str
    location: str | None = None
    publication_date: str | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class VerifiedJob(BaseModel):
    """Fully validated, scored, and normalized job opportunity."""
    id: str
    employer_name: str
    title: str
    normalized_url: str
    original_url: str
    source_domain: str
    ats_provider: str | None = None
    career_track: CareerTrack = CareerTrack.OTHER
    location: str = "Unknown"
    work_mode: WorkMode = WorkMode.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    minimum_experience_years: float | None = None  # None indicates unknown / not specified
    maximum_experience_years: float | None = None
    graduation_eligibility: list[int] = Field(default_factory=list)
    degree_eligibility: list[str] = Field(default_factory=list)
    publication_date: str | None = None
    deadline: str | None = None
    description_summary: str = ""
    matched_skills: list[str] = Field(default_factory=list)
    relevance_score: int = 0  # 0 to 100
    relevance_breakdown: dict[str, int] = Field(default_factory=dict)
    relevance_explanation: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNCONFIRMED
    verification_evidence: dict[str, Any] = Field(default_factory=dict)
    first_seen_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    alerted_at: str | None = None
    content_hash: str = ""


class RunStats(BaseModel):
    """Summary statistics for an agent execution run."""
    id: str
    started_at: str
    completed_at: str | None = None
    run_status: str = "RUNNING"
    sources_attempted: int = 0
    candidates_discovered: int = 0
    candidates_verified: int = 0
    candidates_rejected: int = 0
    new_jobs: int = 0
    duplicates: int = 0
    alerts_sent: int = 0
    alerts_failed: int = 0
    error_summary: str | None = None
    details_by_source: dict[str, Any] = Field(default_factory=dict)


class NotificationRecord(BaseModel):
    """Record of a notification sent via Telegram."""
    id: str
    job_id: str
    chat_id_hash_or_reference: str
    sent_at: str
    telegram_message_id: str | None = None
    delivery_status: str = "PENDING"
    retry_count: int = 0
