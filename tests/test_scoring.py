"""
Unit tests for the relevance scoring engine.
Validates weights, transparency, scoring breakdown, explanation generation,
and gating rules (failed jobs must score 0).
"""

import pytest
from src.job_agent.models import (
    CandidateProfile,
    CareerTrack,
    EmploymentType,
    VerificationStatus,
    VerifiedJob,
    WorkMode,
)
from src.job_agent.scoring import score_job
from src.job_agent.settings import ScoringWeights


@pytest.fixture
def sample_ai_job() -> VerifiedJob:
    return VerifiedJob(
        id="job_score_1",
        employer_name="TopAI Tech",
        title="Junior Generative AI Engineer",
        normalized_url="https://boards.greenhouse.io/topai/jobs/100",
        original_url="https://boards.greenhouse.io/topai/jobs/100",
        source_domain="boards.greenhouse.io",
        ats_provider="Greenhouse",
        career_track=CareerTrack.AI_ML,
        location="Bengaluru, India",
        work_mode=WorkMode.HYBRID,
        employment_type=EmploymentType.FULL_TIME,
        minimum_experience_years=0.0,
        graduation_eligibility=[2026],
        degree_eligibility=["B.Tech", "Computer Science"],
        publication_date="2026-10-19T08:00:00Z",
        matched_skills=["Python", "Generative AI", "RAG", "FastAPI"],
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        content_hash="abc123hash"
    )


def test_high_relevance_job_score(sample_ai_job):
    """A verified AI fresher job matching track, batch, and skills should score high (>= 85)."""
    score, breakdown, explanation = score_job(sample_ai_job)
    assert score >= 85
    assert score <= 100
    assert sum(breakdown.values()) == score
    assert "AI/ML" in explanation
    assert "2026" in explanation
    assert "Python" in explanation


def test_failed_verification_score_is_zero(sample_ai_job):
    """Mandatory Gate: A job that failed verification must score 0 regardless of skills or title."""
    sample_ai_job.verification_status = VerificationStatus.REJECTED_EXPERIENCE
    sample_ai_job.description_summary = "Requires 3+ years experience"
    score, breakdown, explanation = score_job(sample_ai_job)
    assert score == 0
    assert "Verification failed" in explanation


def test_custom_scoring_weights(sample_ai_job):
    """Scoring weights must be customizable via ScoringWeights."""
    custom_weights = ScoringWeights(
        fresher_eligibility=40,
        role_track_match=20,
        technical_skills=10,
        graduation_batch_degree=10,
        publication_recency=10,
        location_work_mode=5,
        source_evidence_quality=5
    )
    score, breakdown, _ = score_job(sample_ai_job, weights=custom_weights)
    assert score > 0
    assert breakdown["fresher_eligibility"] == 40
    assert sum(breakdown.values()) == score
