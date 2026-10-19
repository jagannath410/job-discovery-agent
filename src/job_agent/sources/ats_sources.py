"""
Direct ATS API and public job board source adapter.
Queries official, public job board feeds from Greenhouse, Lever, and Ashby.
"""

from __future__ import annotations

import httpx
from typing import Any

from src.job_agent.logging_config import logger
from src.job_agent.models import RawJobPosting
from src.job_agent.settings import settings
from src.job_agent.sources.base import BaseDiscoverySource

# Selected tech companies and AI organizations that provide public ATS job feeds
DEFAULT_GREENHOUSE_BOARDS = [
    {"employer": "BrowserStack", "board": "browserstack"},
    {"employer": "Postman", "board": "postman"},
    {"employer": "Razorpay", "board": "razorpay"},
]

DEFAULT_LEVER_BOARDS = [
    {"employer": "CRED", "company": "cred"},
]

DEFAULT_ASHBY_BOARDS = [
    {"employer": "Sierra", "board": "sierra"},
]


class ATSDiscoverySource(BaseDiscoverySource):
    """Adapter querying public ATS APIs (Greenhouse, Lever, Ashby)."""

    name: str = "ats_direct"

    def __init__(
        self,
        greenhouse_boards: list[dict[str, str]] | None = None,
        lever_boards: list[dict[str, str]] | None = None,
        client: httpx.Client | None = None
    ) -> None:
        self.greenhouse_boards = greenhouse_boards or DEFAULT_GREENHOUSE_BOARDS
        self.lever_boards = lever_boards or DEFAULT_LEVER_BOARDS
        self.client = client or httpx.Client(
            timeout=settings.http_timeout_seconds,
            headers={
                "User-Agent": "JobDiscoveryAgent/1.0",
                "Accept": "application/json"
            }
        )

    def discover_postings(self) -> list[RawJobPosting]:
        """Fetch active job postings from trusted ATS public board endpoints."""
        all_postings: list[RawJobPosting] = []

        # 1. Fetch Greenhouse boards
        for item in self.greenhouse_boards:
            emp = item["employer"]
            board = item["board"]
            url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"
            try:
                resp = self.client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    jobs = data.get("jobs", [])
                    for job in jobs:
                        title = job.get("title", "")
                        job_url = job.get("absolute_url")
                        job_id = str(job.get("id"))
                        content = job.get("content", "")
                        loc = job.get("location", {}).get("name") if isinstance(job.get("location"), dict) else None
                        updated_at = job.get("updated_at")

                        if job_url and title:
                            all_postings.append(
                                RawJobPosting(
                                    id=f"gh_{board}_{job_id}",
                                    title=title,
                                    original_url=job_url,
                                    employer_name=emp,
                                    description=content,
                                    source_adapter="greenhouse_api",
                                    location=loc,
                                    publication_date=updated_at,
                                    raw_metadata={"board": board, "ats": "Greenhouse"}
                                )
                            )
                else:
                    logger.debug(f"Greenhouse board {board} returned status {resp.status_code}")
            except Exception as exc:
                logger.warning(f"Error querying Greenhouse board '{board}': {exc}")

        # 2. Fetch Lever boards
        for item in self.lever_boards:
            emp = item["employer"]
            company = item["company"]
            url = f"https://api.lever.co/v0/postings/{company}?mode=json"
            try:
                resp = self.client.get(url)
                if resp.status_code == 200:
                    postings = resp.json()
                    if isinstance(postings, list):
                        for post in postings:
                            title = post.get("text", "")
                            job_url = post.get("hostedUrl")
                            job_id = str(post.get("id"))
                            desc = post.get("descriptionPlain") or post.get("description", "")
                            categories = post.get("categories", {})
                            loc = categories.get("location")
                            created_at = post.get("createdAt")

                            if job_url and title:
                                all_postings.append(
                                    RawJobPosting(
                                        id=f"lever_{company}_{job_id}",
                                        title=title,
                                        original_url=job_url,
                                        employer_name=emp,
                                        description=desc,
                                        source_adapter="lever_api",
                                        location=loc,
                                        publication_date=str(created_at) if created_at else None,
                                        raw_metadata={"company": company, "ats": "Lever"}
                                    )
                                )
                else:
                    logger.debug(f"Lever board {company} returned status {resp.status_code}")
            except Exception as exc:
                logger.warning(f"Error querying Lever board '{company}': {exc}")

        logger.info(f"ATS direct discovery collected {len(all_postings)} raw postings.")
        return all_postings
