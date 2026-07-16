"""Shared safeguards for content that may enter durable memory."""

from __future__ import annotations

import re


SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(AKIA|AGPA|AIDA|AROA|ASCA|ASIA)[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN .{0,20}PRIVATE KEY-----"),
    re.compile(r"[Bb]earer\s+[A-Za-z0-9\-._~+/]{20,}={0,3}"),
    re.compile(r"AccountKey=[A-Za-z0-9+/]{20,}={0,2}"),
)


def check_content_for_secrets(content: str) -> None:
    """Reject values that match known credential formats before persistence."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(content):
            raise ValueError(
                "content appears to contain a secret or credential. "
                "Secrets must not be stored as memories."
            )
