"""
Discovery coordinator coordinating modular discovery sources.
"""

from __future__ import annotations

from typing import Any
from src.job_agent.logging_config import logger
from src.job_agent.models import RawJobPosting
from src.job_agent.settings import settings
from src.job_agent.sources.base import BaseDiscoverySource
from src.job_agent.sources.ats_sources import ATSDiscoverySource
from src.job_agent.sources.employer_sources import EmployerCareerDiscoverySource
from src.job_agent.sources.search_api import (
    GoogleCustomSearchSource,
    GeminiDiscoverySource,
    MockDiscoverySource,
)


class DiscoveryEngine:
    """Manages execution across registered source adapters."""

    def __init__(self, sources: list[BaseDiscoverySource] | None = None) -> None:
        if sources is not None:
            self.sources = sources
        else:
            self.sources = self._load_default_sources()

    def _load_default_sources(self) -> list[BaseDiscoverySource]:
        """Configure source adapters according to application settings."""
        active_sources: list[BaseDiscoverySource] = []

        if settings.search_provider == "mock":
            active_sources.append(MockDiscoverySource())
        elif settings.search_provider == "google_custom_search":
            active_sources.append(GoogleCustomSearchSource())
            active_sources.append(ATSDiscoverySource())
            active_sources.append(EmployerCareerDiscoverySource())
        elif settings.search_provider == "gemini":
            active_sources.append(GeminiDiscoverySource())
            active_sources.append(ATSDiscoverySource())
            active_sources.append(EmployerCareerDiscoverySource())
        else:
            # Default: ats_direct (combines verified public ATS feeds and official employer drives)
            active_sources.append(ATSDiscoverySource())
            active_sources.append(EmployerCareerDiscoverySource())

        return active_sources

    def run_discovery(self) -> tuple[list[RawJobPosting], dict[str, Any]]:
        """
        Query all enabled sources and return unique raw candidates with execution telemetry.
        """
        all_raw_candidates: list[RawJobPosting] = []
        source_telemetry: dict[str, Any] = {
            "sources_attempted": 0,
            "sources_succeeded": 0,
            "sources_failed": 0,
            "raw_counts_by_source": {},
            "errors": {}
        }

        for source in self.sources:
            source_name = getattr(source, "name", source.__class__.__name__)
            source_telemetry["sources_attempted"] += 1
            try:
                logger.info(f"Running discovery adapter: {source_name}")
                postings = source.discover_postings()
                all_raw_candidates.extend(postings)
                source_telemetry["sources_succeeded"] += 1
                source_telemetry["raw_counts_by_source"][source_name] = len(postings)
                logger.info(f"Adapter '{source_name}' discovered {len(postings)} candidates.")
            except Exception as exc:
                source_telemetry["sources_failed"] += 1
                source_telemetry["errors"][source_name] = str(exc)
                logger.error(f"Discovery adapter '{source_name}' failed: {exc}", exc_info=True)

        # Basic deduplication across sources by raw URL before passing to verification engine
        unique_by_url: dict[str, RawJobPosting] = {}
        for candidate in all_raw_candidates:
            clean_url = candidate.original_url.strip().lower()
            if clean_url not in unique_by_url:
                unique_by_url[clean_url] = candidate

        deduped_candidates = list(unique_by_url.values())
        logger.info(
            f"Discovery complete. Discovered {len(all_raw_candidates)} raw listings "
            f"({len(deduped_candidates)} unique URLs across {source_telemetry['sources_attempted']} sources)."
        )
        return deduped_candidates, source_telemetry
