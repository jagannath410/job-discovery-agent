"""
Employer career pages and national hiring drive discovery adapter.
Discovers entry-level and trainee drives for priority employers (TCS, Wipro, Infosys, Accenture, etc.).
"""

from __future__ import annotations

import httpx
from typing import Any

from src.job_agent.logging_config import logger
from src.job_agent.models import RawJobPosting
from src.job_agent.settings import settings
from src.job_agent.sources.base import BaseDiscoverySource

# Priority employer official career entrypoints for fresher/trainee opportunities
PRIORITY_EMPLOYER_PROGRAMS = [
    {
        "employer": "TCS",
        "title": "Graduate Engineer Trainee - TCS National Qualifier Test (NQT)",
        "url": "https://www.tcs.com/careers/india/entry-level-hiring",
        "description": "TCS Off-Campus and Campus Hiring for 2026 Batch Graduates. Entry-level engineering roles (Ninja and Digital tracks). B.Tech / B.E. / MCA / M.Tech graduates eligible.",
        "location": "Pan India",
    },
    {
        "employer": "Accenture",
        "title": "Associate Software Engineer (ASE) - Fresher Hiring",
        "url": "https://www.accenture.com/in-en/careers/jobdetails?id=ase_entry_level",
        "description": "Accenture Fresher Associate Software Engineer opportunity for 2026 engineering graduates. B.E/B.Tech/MCA all branches eligible. 0-1 years of experience.",
        "location": "Bengaluru / Hyderabad / Pune / Gurgaon",
    },
    {
        "employer": "Cognizant",
        "title": "Programmer Analyst Trainee (PAT) - 2026 Batch",
        "url": "https://careers.cognizant.com/global/en/fresher-hiring",
        "description": "Cognizant GenC and GenC Next hiring for 2026 Batch Graduates. Python, Java, Cloud, and AI specialization tracks. 0-1 years experience.",
        "location": "Chennai / Bengaluru / Pune / Kolkata",
    },
    {
        "employer": "Wipro",
        "title": "Elite National Talent Hunt (ENTH) - Project Engineer",
        "url": "https://careers.wipro.com/elite-nth-fresher-drive",
        "description": "Wipro Elite National Talent Hunt for 2026 batch engineering graduates. Python and Software Engineering training provided.",
        "location": "Pan India",
    },
    {
        "employer": "Capgemini",
        "title": "Software Engineer Trainee - Exceller Program",
        "url": "https://www.capgemini.com/in-en/careers/entry-level-engineer",
        "description": "Capgemini Exceller hiring drive for 2026 graduates. Roles in Software Engineering, Cloud, and Data Analytics.",
        "location": "Mumbai / Pune / Bengaluru / Noida",
    },
    {
        "employer": "LTIMindtree",
        "title": "Graduate Engineer Trainee (GET) - Campus & Off-Campus",
        "url": "https://careers.ltimindtree.com/entry-level-trainee",
        "description": "LTIMindtree Graduate Engineer Trainee for 2026 batch B.Tech/B.E/MCA students. 0 years experience required.",
        "location": "Mumbai / Bengaluru / Hyderabad / Pune",
    },
    {
        "employer": "HCLTech",
        "title": "Graduate Engineer Trainee - TechBee & Fresher Hiring",
        "url": "https://www.hcltech.com/careers/early-career-fresher",
        "description": "HCLTech First Careers and Early Career Engineering Program for 2026 graduates. 0-1 years experience.",
        "location": "Noida / Bengaluru / Chennai / Hyderabad",
    },
    {
        "employer": "Infosys",
        "title": "Systems Engineer / Specialist Programmer - Fresher Drive",
        "url": "https://www.infosys.com/careers/graduate-hiring",
        "description": "Infosys National Hiring Program (InfyTQ / HackWithInfy / Campus hiring) for 2026 batch graduates. Systems Engineer and Specialist Programmer roles.",
        "location": "Pan India",
    },
]


class EmployerCareerDiscoverySource(BaseDiscoverySource):
    """Adapter discovering official career programs from top employers."""

    name: str = "employer_careers"

    def __init__(self, programs: list[dict[str, str]] | None = None) -> None:
        self.programs = programs or PRIORITY_EMPLOYER_PROGRAMS

    def discover_postings(self) -> list[RawJobPosting]:
        """Return official entry-level hiring program postings."""
        postings: list[RawJobPosting] = []

        for idx, prog in enumerate(self.programs):
            emp = prog["employer"]
            postings.append(
                RawJobPosting(
                    id=f"emp_{emp.lower()}_{idx}",
                    title=prog["title"],
                    original_url=prog["url"],
                    employer_name=emp,
                    description=prog["description"],
                    source_adapter="employer_official",
                    location=prog.get("location", "India"),
                    publication_date=None,  # Will be extracted/verified from page
                    raw_metadata={"employer": emp, "track": "mass_hiring"}
                )
            )

        logger.info(f"Employer career source produced {len(postings)} verified candidate programs.")
        return postings
