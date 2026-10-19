"""
End-to-end pipeline integration tests.
Covers required test cases:
15. Search provider timeout
19. Malformed search results
24. Persistence across two separate agent runs (deduplication & alert state retention)
"""

import httpx
import pytest
from pathlib import Path

from src.job_agent.database import Database
from src.job_agent.discovery import DiscoveryEngine
from src.job_agent.models import RawJobPosting, VerificationStatus, CareerTrack
from src.job_agent.notifications import TelegramNotifier
from src.job_agent.scoring import score_job
from src.job_agent.sources.base import BaseDiscoverySource
from src.job_agent.sources.search_api import GoogleCustomSearchSource, MockDiscoverySource
from src.job_agent.verification import JobVerifier


class TimeoutMockSource(BaseDiscoverySource):
    """Source that times out."""
    name: str = "timeout_source"

    def discover_postings(self) -> list[RawJobPosting]:
        raise httpx.TimeoutException("Search API connection timed out")


class MalformedResultsMockSource(BaseDiscoverySource):
    """Source that returns irregular or malformed items."""
    name: str = "malformed_source"

    def discover_postings(self) -> list[RawJobPosting]:
        return [
            RawJobPosting(
                id="malformed_1",
                title="",  # Empty title
                original_url="not-a-valid-url",
                employer_name="",
                source_adapter="malformed"
            ),
            RawJobPosting(
                id="malformed_2",
                title="Proper AI Intern",
                original_url="https://boards.greenhouse.io/good/jobs/1",
                employer_name="Good Co",
                description="0-1 years exp fresher AI role.",
                source_adapter="malformed"
            )
        ]


def test_search_provider_timeout_handled_gracefully():
    """Test Case 15: Search provider timeout does not crash the discovery engine."""
    engine = DiscoveryEngine(sources=[TimeoutMockSource()])
    candidates, telemetry = engine.run_discovery()
    assert len(candidates) == 0
    assert telemetry["sources_failed"] == 1
    assert "timeout_source" in telemetry["errors"]


def test_malformed_search_results_handled_safely(tmp_path: Path):
    """Test Case 19: Malformed search results are rejected without breaking the verification pipeline."""
    engine = DiscoveryEngine(sources=[MalformedResultsMockSource()])
    candidates, _ = engine.run_discovery()
    assert len(candidates) == 2

    verifier = JobVerifier()
    results = [verifier.verify_job_posting(c) for c in candidates]

    # First invalid URL must be rejected
    assert results[0].verification_status == VerificationStatus.REJECTED_DOMAIN


def test_persistence_across_two_separate_agent_runs(tmp_path: Path, respx_mock):
    """
    Test Case 24: Running the pipeline twice ensures that jobs alerted in Run 1
    are NOT re-alerted in Run 2.
    """
    db_file = tmp_path / "persistence_test.db"
    db = Database(db_file)

    # Mock Greenhouse page response
    gh_url = "https://boards.greenhouse.io/testcompany/jobs/888"
    respx_mock.get(gh_url).mock(
        return_value=httpx.Response(
            200,
            text="<html><body><h1>AI Intern</h1><p>2026 Batch, 0-1 years exp. Python and ML.</p></body></html>"
        )
    )

    verifier = JobVerifier()

    # --- RUN 1 ---
    raw_job = RawJobPosting(
        id="pers_job_1",
        title="AI Engineer Intern",
        original_url=gh_url,
        employer_name="TestCompany",
        description="Python & ML fresher role 2026.",
        source_adapter="mock"
    )

    verified = verifier.verify_job_posting(raw_job)
    score, breakdown, explanation = score_job(verified)
    verified.relevance_score = score
    verified.relevance_breakdown = breakdown
    verified.relevance_explanation = explanation

    is_new, _ = db.save_job(verified)
    assert is_new is True

    # Check unalerted jobs
    pending_alerts_run1 = db.get_unalerted_verified_jobs(min_score=60)
    assert len(pending_alerts_run1) == 1
    assert pending_alerts_run1[0].id == verified.id

    # Simulate sending alert and marking alerted in DB
    db.mark_job_alerted(verified.id, "2026-10-19T08:30:00Z")

    # --- RUN 2 (Next Day) ---
    # Same job is discovered again in Run 2
    raw_job_run2 = RawJobPosting(
        id="pers_job_1_repeat",
        title="AI Engineer Intern",
        original_url=gh_url,
        employer_name="TestCompany",
        description="Python & ML fresher role 2026.",
        source_adapter="mock"
    )

    verified_run2 = verifier.verify_job_posting(raw_job_run2)
    is_new_run2, changed_run2 = db.save_job(verified_run2)
    assert is_new_run2 is False  # Recognized as duplicate/existing
    assert changed_run2 is False

    # Check unalerted jobs in Run 2
    pending_alerts_run2 = db.get_unalerted_verified_jobs(min_score=60)
    # MUST BE ZERO because already alerted in Run 1!
    assert len(pending_alerts_run2) == 0
