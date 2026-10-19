"""
Source adapters package exports.
"""

from src.job_agent.sources.base import BaseDiscoverySource
from src.job_agent.sources.ats_sources import ATSDiscoverySource
from src.job_agent.sources.employer_sources import EmployerCareerDiscoverySource
from src.job_agent.sources.search_api import (
    GoogleCustomSearchSource,
    GeminiDiscoverySource,
    MockDiscoverySource,
)

__all__ = [
    "BaseDiscoverySource",
    "ATSDiscoverySource",
    "EmployerCareerDiscoverySource",
    "GoogleCustomSearchSource",
    "GeminiDiscoverySource",
    "MockDiscoverySource",
]
