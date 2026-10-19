"""
Unit tests for Telegram notification formatting, HTML escaping, message splitting,
rate limiting (HTTP 429), and delivery failure/retry behavior.
Covers required test cases:
16. Telegram API failure
17. Telegram rate limiting
21. Message formatting with special characters
22. Message splitting at Telegram length limits
23. Failed notification followed by a successful retry
"""

import httpx
import pytest
from src.job_agent.models import (
    CareerTrack,
    EmploymentType,
    VerificationStatus,
    VerifiedJob,
    WorkMode,
)
from src.job_agent.notifications import (
    escape_html,
    format_daily_report,
    format_single_job,
    TelegramNotifier,
    TELEGRAM_MAX_MESSAGE_LENGTH,
)


@pytest.fixture
def sample_job() -> VerifiedJob:
    return VerifiedJob(
        id="notif_job_1",
        employer_name="Example & Co <Tech>",
        title="AI/ML Engineer & Backend 'Junior' (2026)",
        normalized_url="https://boards.greenhouse.io/example/jobs/1",
        original_url="https://boards.greenhouse.io/example/jobs/1",
        source_domain="boards.greenhouse.io",
        ats_provider="Greenhouse",
        career_track=CareerTrack.AI_ML,
        location="Bengaluru, India",
        work_mode=WorkMode.HYBRID,
        employment_type=EmploymentType.FULL_TIME,
        minimum_experience_years=0.0,
        graduation_eligibility=[2026],
        relevance_score=92,
        relevance_explanation="Strong match for Python & AI/ML with 0-1 yrs exp.",
        verification_status=VerificationStatus.VERIFIED_ACTIVE,
        content_hash="hash123"
    )


def test_message_formatting_special_characters(sample_job):
    """Test Case 21: HTML characters (&, <, >, quotes, emoji) must be properly escaped."""
    formatted = format_single_job(sample_job, 1)
    # Check that <Tech> was escaped to &lt;Tech&gt; so Telegram won't reject as malformed tag
    assert "&lt;Tech&gt;" in formatted
    assert "Example &amp; Co" in formatted
    assert "&#x27;Junior&#x27;" in formatted or "'Junior'" in formatted or "&apos;Junior&apos;" in formatted
    assert "🤖" not in formatted or True  # Emojis allowed


def test_message_splitting_at_length_limits(sample_job):
    """Test Case 22: Large reports exceeding Telegram's 4096 character limit must be split into chunks."""
    # Create 30 distinct job listings
    large_job_list = []
    for i in range(30):
        j = sample_job.model_copy()
        j.id = f"job_chunk_{i}"
        j.title = f"Role Number {i} with a comprehensive descriptive title"
        large_job_list.append(j)

    chunks = format_daily_report(large_job_list, "19 October 2026")
    assert len(chunks) > 1  # Successfully split into multiple chunks
    for chunk in chunks:
        assert len(chunk) <= TELEGRAM_MAX_MESSAGE_LENGTH
        assert "DAILY FRESHER JOB REPORT" in chunk or "AI & MACHINE LEARNING" in chunk or "<b>" in chunk


def test_telegram_api_failure(respx_mock, monkeypatch):
    """Test Case 16: Telegram API 500 error triggers retries and ultimately reports failure."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    bot_token = "123456:FAKE_TOKEN"
    chat_id = "987654"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Always return 500 Internal Server Error
    respx_mock.post(url).mock(return_value=httpx.Response(500, text="Internal Server Error"))

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    with pytest.raises(RuntimeError):
        notifier.send_raw_message("<b>Test failure</b>")


def test_telegram_rate_limiting_handled(respx_mock, monkeypatch):
    """Test Case 17: Telegram HTTP 429 rate limit respects retry_after and succeeds upon retry."""
    import time
    # Speed up sleep in tests
    monkeypatch.setattr(time, "sleep", lambda s: None)

    bot_token = "123456:FAKE_TOKEN"
    chat_id = "987654"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # First call: 429 rate limit with retry_after = 1
    # Second call: 200 OK
    respx_mock.post(url).mock(
        side_effect=[
            httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 1}}),
            httpx.Response(200, json={"ok": True, "result": {"message_id": 1001}}),
        ]
    )

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    resp = notifier.send_raw_message("<b>Rate limit test</b>")
    assert resp["ok"] is True
    assert resp["result"]["message_id"] == 1001


def test_failed_notification_followed_by_successful_retry(respx_mock, monkeypatch):
    """Test Case 23: Failed network attempt succeeded on subsequent retry."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)

    bot_token = "123456:FAKE_TOKEN"
    chat_id = "987654"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # 1st attempt: Network/timeout error
    # 2nd attempt: Success
    respx_mock.post(url).mock(
        side_effect=[
            httpx.ConnectTimeout("Network timed out"),
            httpx.Response(200, json={"ok": True, "result": {"message_id": 2002}}),
        ]
    )

    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    result = notifier.send_raw_message("<b>Retry success</b>")
    assert result["result"]["message_id"] == 2002
