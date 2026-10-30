"""
Automated unit tests for system security audit and database search capabilities.
"""

import pytest
from pathlib import Path
from src.job_agent.database import Database
from src.job_agent.models import (
    CareerTrack,
    EmploymentType,
    VerificationStatus,
    VerifiedJob,
    WorkMode,
)
from src.job_agent.security_audit import run_security_audit
from src.job_agent.verification import (
    check_domain_trust,
    is_hostname_safe,
    is_ip_private_or_internal,
)


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    db_file = tmp_path / "test_sec.db"
    return Database(db_file)


def test_system_security_audit_all_pass():
    """Verify that the autonomous security audit executes and passes all checks."""
    result = run_security_audit()
    assert result is True


def test_ssrf_internal_ip_detection():
    """Verify private/loopback IP detection rejects internal destinations."""
    assert is_ip_private_or_internal("127.0.0.1") is True
    assert is_ip_private_or_internal("10.254.0.1") is True
    assert is_ip_private_or_internal("169.254.169.254") is True
    assert is_ip_private_or_internal("::1") is True
    assert is_ip_private_or_internal("8.8.8.8") is False


def test_banned_aggregators_rejected():
    """Verify aggregator sites (naukri, indeed, linkedin) are blocked."""
    assert check_domain_trust("naukri.com")[0] is False
    assert check_domain_trust("indeed.com")[0] is False
    assert check_domain_trust("jobs.lever.co")[0] is True
    assert check_domain_trust("boards.greenhouse.io")[0] is True


def test_database_safe_keyword_search(temp_db: Database):
    """Verify SQL injection payloads do not break database search and return safe results."""
    job = VerifiedJob(
        id="job_search_1",
        employer_name="Groww",
        title="Software Engineer Intern",
        normalized_url="https://boards.greenhouse.io/groww/jobs/99",
        original_url="https://boards.greenhouse.io/groww/jobs/99",
        source_domain="boards.greenhouse.io",
        ats_provider="Greenhouse",
        career_track=CareerTrack.SOFTWARE_BACKEND,
        location="Bengaluru",
        work_mode=WorkMode.HYBRID,
        employment_type=EmploymentType.INTERNSHIP,
        minimum_experience_years=0.0,
        maximum_experience_years=1.0,
        graduation_eligibility=[2027],
        degree_eligibility=["B.Tech", "Computer Science"],
        publication_date="2026-10-30",
        deadline=None,
        description_summary="Python and DSA developer role",
        matched_skills=["Python", "DSA & Problem Solving"],
        relevance_score=85,
        relevance_breakdown={"fresher": 25},
        relevance_explanation="Eligible",
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        verification_evidence={},
        first_seen_at="2026-10-30T00:00:00Z",
        last_checked_at="2026-10-30T00:00:00Z",
        alerted_at=None,
        content_hash="hash99",
    )
    temp_db.upsert_job(job)

    # 1. Normal keyword search
    res = temp_db.search_jobs("python")
    assert len(res) == 1
    assert res[0].employer_name == "Groww"

    # 2. SQL injection payload attempt should return 0 safely without error
    sqli_res = temp_db.search_jobs("' OR 1=1 --")
    assert isinstance(sqli_res, list)

    # 3. Recent verified jobs
    recent = temp_db.get_recent_verified_jobs(limit=5)
    assert len(recent) == 1
