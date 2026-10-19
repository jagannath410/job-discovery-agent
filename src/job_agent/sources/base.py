"""
Base abstract class for job discovery source adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from src.job_agent.models import RawJobPosting


class BaseDiscoverySource(ABC):
    """Abstract interface for all job discovery sources."""

    name: str = "base_source"

    @abstractmethod
    def discover_postings(self) -> list[RawJobPosting]:
        """
        Query the source and return a list of raw job postings for verification.
        Should handle exceptions gracefully and return an empty list or partial list.
        """
        pass
