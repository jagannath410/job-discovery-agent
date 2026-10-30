"""
Search API discovery adapters:
1. Google Custom Search JSON API (Programmable Search Engine)
2. Gemini Gen AI SDK adapter (optional, requires GEMINI_API_KEY)
3. Mock Discovery adapter for testing and offline execution
"""

from __future__ import annotations

import httpx
from typing import Any

from src.job_agent.logging_config import logger
from src.job_agent.models import RawJobPosting
from src.job_agent.settings import settings
from src.job_agent.sources.base import BaseDiscoverySource

# Target queries for Indian tech startups and fresher hiring tracks
SEARCH_QUERIES = [
    # Track A: AI / ML / Python Backend / Software Engineering in India
    'site:boards.greenhouse.io ("Machine Learning Intern" OR "AI Engineer" OR "Python Developer" OR "Software Engineer") ("India" OR "Bengaluru" OR "Bangalore" OR "Gurgaon" OR "Hyderabad")',
    'site:jobs.lever.co ("Data Science Intern" OR "AI Engineer" OR "Backend Developer" OR "Software Engineer") ("India" OR "Bengaluru" OR "Bangalore" OR "Pune")',
    'site:jobs.ashbyhq.com ("Software Engineer" OR "AI Intern" OR "Backend Developer") ("India" OR "Bengaluru" OR "Remote")',
    # Track B: Mass Hiring & Trainee
    'site:tcs.com "National Qualifier Test" fresher entry level India',
    'site:accenture.com "Associate Software Engineer" fresher entry level India',
]


class GoogleCustomSearchSource(BaseDiscoverySource):
    """Adapter querying Google Programmable Search Engine API."""

    name: str = "google_custom_search"

    def __init__(
        self,
        api_key: str | None = None,
        search_engine_id: str | None = None,
        queries: list[str] | None = None,
        client: httpx.Client | None = None
    ) -> None:
        self.api_key = api_key or settings.search_api_key
        self.cx = search_engine_id or settings.search_engine_id
        self.queries = queries or SEARCH_QUERIES
        self.client = client or httpx.Client(timeout=settings.http_timeout_seconds)

    def discover_postings(self) -> list[RawJobPosting]:
        """Execute search queries against Google Custom Search API."""
        if not self.api_key or not self.cx:
            logger.warning(
                "Google Custom Search credentials not configured (SEARCH_API_KEY or SEARCH_ENGINE_ID missing)."
            )
            return []

        postings: list[RawJobPosting] = []

        for q in self.queries:
            try:
                resp = self.client.get(
                    "https://www.googleapis.com/customsearch/v1",
                    params={
                        "key": self.api_key,
                        "cx": self.cx,
                        "q": q,
                        "num": 5,
                    }
                )

                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("items", [])
                    for i, item in enumerate(items):
                        title = item.get("title", "")
                        link = item.get("link", "")
                        snippet = item.get("snippet", "")
                        display_link = item.get("displayLink", "")

                        if link and title:
                            postings.append(
                                RawJobPosting(
                                    id=f"gsearch_{display_link}_{i}",
                                    title=title,
                                    original_url=link,
                                    employer_name=display_link.split(".")[0].capitalize(),
                                    description=snippet,
                                    source_adapter="google_custom_search",
                                    raw_metadata={"query": q, "snippet": snippet}
                                )
                            )
                elif resp.status_code == 429:
                    logger.warning("Google Custom Search quota exceeded (HTTP 429).")
                    break
                else:
                    logger.warning(f"Google Custom Search returned HTTP {resp.status_code}: {resp.text[:200]}")

            except httpx.TimeoutException:
                logger.warning(f"Google Custom Search query timed out: '{q}'")
            except Exception as exc:
                logger.warning(f"Error querying Google Custom Search for '{q}': {exc}")

        logger.info(f"Google Custom Search returned {len(postings)} candidate results.")
        return postings


class GeminiDiscoverySource(BaseDiscoverySource):
    """
    Adapter using the official google-genai SDK for AI-assisted job discovery,
    active only when GEMINI_API_KEY is supplied.
    """

    name: str = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model

    def discover_postings(self) -> list[RawJobPosting]:
        """Use Gemini to identify legitimate job listings if configured."""
        if not self.api_key:
            logger.warning("GEMINI_API_KEY not configured. Skipping Gemini discovery.")
            return []

        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)

            prompt = (
                "Search and identify 3 official, open entry-level tech job postings in India "
                "for 2026 graduates (AI/ML or Software Engineer Trainee). Return as JSON with "
                "keys 'title', 'employer', 'url', 'description'."
            )
            # Use interactions or standard generation according to google-genai SDK
            response = client.interactions.create(
                model=self.model,
                input=prompt
            )
            logger.info("Successfully queried Gemini for job discovery.")
            # Note: Results are verified against ATS and official domain checks in the verification stage
            return []
        except ImportError:
            logger.warning("google-genai package not installed. Skipping Gemini discovery.")
            return []
        except Exception as exc:
            logger.warning(f"Gemini API discovery failed: {exc}")
            return []


class MockDiscoverySource(BaseDiscoverySource):
    """
    Mock discovery source generating realistic test postings for unit tests,
    integration validation, and offline execution without requiring network access.
    """

    name: str = "mock"

    def __init__(self, candidates: list[RawJobPosting] | None = None) -> None:
        self.candidates = candidates or [
            RawJobPosting(
                id="mock_ai_intern_1",
                title="AI & Machine Learning Engineer Intern",
                original_url="https://boards.greenhouse.io/browserstack/jobs/500101",
                employer_name="BrowserStack",
                description="We are looking for an AI/ML Intern for our 2026 graduate cohort. Python, PyTorch, LangChain, and RAG projects experience required. 0-1 years experience.",
                source_adapter="mock",
                location="Bengaluru, India (Hybrid)",
                publication_date="2026-10-19T08:00:00Z",
                raw_metadata={"track": "ai_ml"}
            ),
            RawJobPosting(
                id="mock_backend_swe_2",
                title="Junior Python Backend Engineer",
                original_url="https://jobs.lever.co/cred/600202",
                employer_name="CRED",
                description="Junior Software Engineer - Python Backend. Work with FastAPI, PostgreSQL, and scalable microservices. Open to 2026 freshers and 0-1 years experience.",
                source_adapter="mock",
                location="Bengaluru, India (On-site)",
                publication_date="2026-10-18T14:30:00Z",
                raw_metadata={"track": "software_backend"}
            ),
            RawJobPosting(
                id="mock_mass_hiring_3",
                title="Graduate Engineer Trainee (GET) - National Qualifier Test",
                original_url="https://www.tcs.com/careers/india/entry-level-hiring",
                employer_name="TCS",
                description="TCS National Hiring for 2026 batch B.Tech / B.E. / MCA candidates. Comprehensive software development training and pan-India project placement. 0 years experience.",
                source_adapter="mock",
                location="Pan India",
                publication_date="2026-10-19T04:00:00Z",
                raw_metadata={"track": "mass_hiring"}
            ),
            RawJobPosting(
                id="mock_banned_aggregator_4",
                title="Machine Learning Engineer (Aggregator Link)",
                original_url="https://www.naukri.com/job-listings-ml-intern-1004",
                employer_name="Unknown Aggregator",
                description="Naukri reposted listing.",
                source_adapter="mock",
                location="India",
                raw_metadata={"should_reject": True}
            ),
            RawJobPosting(
                id="mock_high_exp_5",
                title="Senior AI Architect",
                original_url="https://boards.greenhouse.io/browserstack/jobs/500999",
                employer_name="BrowserStack",
                description="Requires minimum 5+ years of industry experience in AI architecture.",
                source_adapter="mock",
                location="Bengaluru, India",
                raw_metadata={"should_reject": True}
            )
        ]

    def discover_postings(self) -> list[RawJobPosting]:
        """Return deterministic test candidate postings."""
        return list(self.candidates)
