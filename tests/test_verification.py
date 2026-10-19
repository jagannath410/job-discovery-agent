"""
Unit tests for URL normalization, domain trust, spoofing defense, SSRF guards,
redirect safety, and job activity verification.
Covers required test cases:
1. Valid official ATS URL
2. Valid employer-owned career URL
3. Banned aggregator URL
4. Spoofed domain (employer.com.attacker.invalid)
5. Redirect to a banned domain
6. Redirect to a private or internal IP (SSRF)
7. Expired job
"""

import httpx
import pytest
from src.job_agent.models import RawJobPosting, VerificationStatus
from src.job_agent.verification import (
    check_domain_trust,
    is_hostname_safe,
    is_ip_private_or_internal,
    normalize_job_url,
    JobVerifier,
)


def test_valid_official_ats_url():
    """Test Case 1: Valid official ATS URL (Ashby, Greenhouse, Lever, Workday)."""
    urls = [
        "https://boards.greenhouse.io/browserstack/jobs/12345?utm_source=slack",
        "https://jobs.lever.co/cred/abcdef-1234?ref=email",
        "https://jobs.ashbyhq.com/sierra/7890",
    ]
    for raw in urls:
        norm, err = normalize_job_url(raw)
        assert err is None
        assert norm is not None
        assert "utm_source" not in norm
        assert "ref=" not in norm
        assert norm.startswith("https://")

        # Check domain trust
        from urllib.parse import urlsplit
        host = urlsplit(norm).hostname
        is_allowed, cat, provider, reason = check_domain_trust(host)
        assert is_allowed is True
        assert cat == "TRUSTED_ATS"
        assert provider in ("Greenhouse", "Lever", "Ashby")


def test_valid_employer_owned_career_url():
    """Test Case 2: Valid employer-owned career URL (TCS, Wipro, Infosys, etc.)."""
    urls = [
        "https://www.tcs.com/careers/india/entry-level",
        "https://careers.wipro.com/opportunities/fresher-2026",
        "https://www.infosys.com/careers/graduate-hiring.html?trk=web",
        "https://www.accenture.com/in-en/careers/jobdetails?id=123",
    ]
    for raw in urls:
        norm, err = normalize_job_url(raw)
        assert err is None
        assert norm is not None
        assert "trk=" not in norm

        from urllib.parse import urlsplit
        host = urlsplit(norm).hostname
        is_allowed, cat, employer, reason = check_domain_trust(host)
        assert is_allowed is True
        assert cat == "OFFICIAL_EMPLOYER"


def test_banned_aggregator_url():
    """Test Case 3: Banned aggregator URLs must be strictly rejected."""
    banned_urls = [
        "https://www.linkedin.com/jobs/view/123456",
        "https://in.indeed.com/viewjob?jk=abcdef",
        "https://www.naukri.com/job-listings-ai-intern-123",
        "https://unstop.com/internships/machine-learning-engineer",
        "https://internshala.com/internship/detail/python-intern-123",
        "https://subdomain.freshersworld.com/jobs/trainee",
        "https://prepinsta.com/tcs-nqt-hiring",
        "https://www.glassdoor.com/job-listing/123",
        "https://hirist.com/j/python-dev-123",
    ]
    for raw in banned_urls:
        norm, _ = normalize_job_url(raw)
        from urllib.parse import urlsplit
        host = urlsplit(norm or raw).hostname
        is_allowed, cat, _, reason = check_domain_trust(host)
        assert is_allowed is False
        assert cat == "BANNED_AGGREGATOR"
        assert "banned" in reason.lower()


def test_spoofed_domain_rejection():
    """Test Case 4: Spoofed domains (e.g. employer.com.attacker.invalid) must be rejected."""
    spoofed_urls = [
        "https://tcs.com.attacker.invalid/careers",
        "https://wipro.com.phishing.org/apply",
        "https://boards.greenhouse.io.evilcorp.com/jobs/123",
        "https://accenture.com.fakejobs.in/entry-level",
    ]
    for raw in spoofed_urls:
        norm, _ = normalize_job_url(raw)
        from urllib.parse import urlsplit
        host = urlsplit(norm or raw).hostname
        is_allowed, cat, _, _ = check_domain_trust(host)
        # Suffix must not trick exact or subdomain check
        assert is_allowed is False
        assert cat == "UNVERIFIED_DOMAIN"


def test_redirect_to_banned_domain(respx_mock):
    """Test Case 5: Redirect to a banned domain (e.g. from bit.ly/landing to naukri) must be detected and rejected."""
    start_url = "https://boards.greenhouse.io/company/jobs/100"
    banned_target = "https://www.naukri.com/job-listings-redirected"

    respx_mock.get(start_url).mock(
        return_value=httpx.Response(302, headers={"Location": banned_target})
    )

    verifier = JobVerifier()
    raw = RawJobPosting(
        id="test_redirect_banned",
        title="ML Intern",
        original_url=start_url,
        employer_name="Company",
        source_adapter="test"
    )
    result = verifier.verify_job_posting(raw)
    assert result.verification_status == VerificationStatus.REJECTED_DOMAIN
    assert "banned" in str(result.verification_evidence["rejection_reasons"]).lower()


def test_redirect_to_private_internal_ip_ssrf(respx_mock):
    """Test Case 6: Redirect or direct URL to private/internal IP (SSRF) must be blocked."""
    assert is_ip_private_or_internal("127.0.0.1") is True
    assert is_ip_private_or_internal("10.0.0.5") is True
    assert is_ip_private_or_internal("192.168.1.1") is True
    assert is_ip_private_or_internal("172.16.0.1") is True
    assert is_ip_private_or_internal("169.254.169.254") is True
    assert is_ip_private_or_internal("::1") is True
    assert is_ip_private_or_internal("8.8.8.8") is False

    assert is_hostname_safe("localhost") is False
    assert is_hostname_safe("127.0.0.1") is False
    assert is_hostname_safe("server.local") is False
    assert is_hostname_safe("metadata.internal") is False

    # Test SSRF redirect
    start_url = "https://boards.greenhouse.io/company/jobs/ssrf"
    internal_target = "http://169.254.169.254/latest/meta-data/"

    respx_mock.get(start_url).mock(
        return_value=httpx.Response(302, headers={"Location": internal_target})
    )

    verifier = JobVerifier()
    raw = RawJobPosting(
        id="test_ssrf",
        title="Software Intern",
        original_url=start_url,
        employer_name="Company",
        source_adapter="test"
    )
    result = verifier.verify_job_posting(raw)
    assert result.verification_status == VerificationStatus.REJECTED_DOMAIN


def test_expired_job_detection(respx_mock):
    """Test Case 7: Expired or closed jobs must be marked EXPIRED."""
    job_url = "https://boards.greenhouse.io/company/jobs/expired_1"

    # HTML explicitly containing closed job text
    html_closed = """
    <html>
        <body>
            <h1>Data Science Intern</h1>
            <div class="message">This position is no longer available. Applications are now closed.</div>
        </body>
    </html>
    """
    respx_mock.get(job_url).mock(
        return_value=httpx.Response(200, text=html_closed)
    )

    verifier = JobVerifier()
    raw = RawJobPosting(
        id="test_expired",
        title="Data Science Intern",
        original_url=job_url,
        employer_name="Company",
        source_adapter="test"
    )
    result = verifier.verify_job_posting(raw)
    assert result.verification_status == VerificationStatus.EXPIRED

    # Also test HTTP 404 / 410
    job_404_url = "https://boards.greenhouse.io/company/jobs/404"
    respx_mock.get(job_404_url).mock(
        return_value=httpx.Response(404, text="Not Found")
    )
    raw_404 = RawJobPosting(
        id="test_404",
        title="AI Engineer",
        original_url=job_404_url,
        employer_name="Company",
        source_adapter="test"
    )
    result_404 = verifier.verify_job_posting(raw_404)
    assert result_404.verification_status == VerificationStatus.EXPIRED
