"""
Unit tests for deduplication, content hashing, and database transaction safety.
Covers required test cases:
11. Duplicate application URL
12. Same job found through multiple sources
18. Database failure & transaction rollback
"""

import sqlite3
import pytest
from pathlib import Path
from src.job_agent.database import Database
from src.job_agent.deduplication import compute_content_hash, compute_job_id
from src.job_agent.models import (
    CareerTrack,
    EmploymentType,
    VerificationStatus,
    VerifiedJob,
    WorkMode,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_file = tmp_path / "test_jobs.db"
    return Database(db_file)


@pytest.fixture
def mock_verified_job() -> VerifiedJob:
    url = "https://boards.greenhouse.io/browserstack/jobs/101"
    emp = "BrowserStack"
    return VerifiedJob(
        id=compute_job_id(emp, url),
        employer_name=emp,
        title="ML Engineer Intern",
        normalized_url=url,
        original_url=url,
        source_domain="boards.greenhouse.io",
        ats_provider="Greenhouse",
        career_track=CareerTrack.AI_ML,
        location="Bengaluru, India",
        work_mode=WorkMode.HYBRID,
        employment_type=EmploymentType.INTERNSHIP,
        minimum_experience_years=0.0,
        graduation_eligibility=[2026],
        matched_skills=["Python", "Machine Learning"],
        relevance_score=90,
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        content_hash=compute_content_hash("ML Engineer Intern", emp, "Description", "Bengaluru")
    )


def test_duplicate_application_url(temp_db, mock_verified_job):
    """Test Case 11: Inserting the same normalized application URL twice should update, not duplicate."""
    is_new_1, changed_1 = temp_db.save_job(mock_verified_job)
    assert is_new_1 is True
    assert changed_1 is False

    # Second save with exact same normalized URL
    is_new_2, changed_2 = temp_db.save_job(mock_verified_job)
    assert is_new_2 is False
    assert changed_2 is False

    # Verify only 1 entry in DB
    summary = temp_db.get_summary_stats()
    assert summary["total_jobs_stored"] == 1


def test_same_job_from_multiple_sources(temp_db, mock_verified_job):
    """Test Case 12: Same job discovered through multiple sources resolves to the same normalized URL & ID."""
    temp_db.save_job(mock_verified_job)

    # Secondary source discovers same position with minor tracking differences that normalize to identical URL
    alt_url = "https://boards.greenhouse.io/browserstack/jobs/101?utm_campaign=campus"
    from src.job_agent.verification import normalize_job_url
    norm_url, _ = normalize_job_url(alt_url)
    assert norm_url == mock_verified_job.normalized_url

    alt_job = mock_verified_job.model_copy()
    alt_job.normalized_url = norm_url
    alt_job.id = compute_job_id(alt_job.employer_name, norm_url)

    is_new, changed = temp_db.save_job(alt_job)
    assert is_new is False
    assert temp_db.get_summary_stats()["total_jobs_stored"] == 1


def test_database_failure_transaction_rollback(temp_db):
    """Test Case 18: Database failure rolls back transaction without corrupting data."""
    with pytest.raises(sqlite3.IntegrityError):
        with temp_db.get_connection() as conn:
            # Valid insertion
            conn.execute(
                "INSERT INTO schema_meta (version, applied_at) VALUES (99, '2026-10-19')"
            )
            # Intentionally duplicate primary key to trigger IntegrityError
            conn.execute(
                "INSERT INTO schema_meta (version, applied_at) VALUES (99, '2026-10-19')"
            )

    # Ensure rolled back
    with temp_db.get_connection() as conn:
        row = conn.execute("SELECT * FROM schema_meta WHERE version = 99").fetchone()
        assert row is None
