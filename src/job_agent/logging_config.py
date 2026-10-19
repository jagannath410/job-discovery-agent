"""
Logging configuration with sensitive data redaction for security.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import Any

# Regex patterns to catch bot tokens and API keys in log lines
_TOKEN_PATTERN = re.compile(r"bot\d+:[A-Za-z0-9_-]{30,}")
_AUTH_HEADER_PATTERN = re.compile(r"(Bearer\s+)[A-Za-z0-9_-]{16,}", re.IGNORECASE)
_API_KEY_PATTERN = re.compile(r"((?:key|api_key|token)=\s*)[A-Za-z0-9_-]{16,}", re.IGNORECASE)


class RedactingFormatter(logging.Formatter):
    """Custom logging formatter that scrubs bot tokens, API keys, and sensitive tokens."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = _TOKEN_PATTERN.sub("bot[REDACTED_TELEGRAM_TOKEN]", original)
        redacted = _AUTH_HEADER_PATTERN.sub(r"\1[REDACTED_AUTH_TOKEN]", redacted)
        redacted = _API_KEY_PATTERN.sub(r"\1[REDACTED_API_KEY]", redacted)
        return redacted


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Initialize and configure root application logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger("job_agent")
    root_logger.setLevel(level)

    # Avoid adding duplicate handlers if setup_logging is called multiple times
    if not root_logger.handlers:
        if sys.platform.startswith("win"):
            try:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = RedactingFormatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

    return root_logger


logger = setup_logging()
