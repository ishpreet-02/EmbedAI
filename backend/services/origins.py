"""
Origin whitelist helpers for widget embed security.
"""

import re
from urllib.parse import urlparse

ORIGIN_PATTERN = re.compile(
    r"^https?://"
    r"(localhost(?::\d+)?|[\w.-]+(?:\.[\w.-]+)*)(?::\d+)?$"
    r"$",
    re.IGNORECASE,
)


def normalize_origin(origin: str) -> str:
    """Normalize to scheme://host[:port] without trailing slash."""
    return origin.strip().rstrip("/")


def extract_request_origin(
    origin_header: str | None,
    referer: str | None,
) -> str | None:
    if origin_header:
        return normalize_origin(origin_header)
    if referer:
        parsed = urlparse(referer.strip())
        if parsed.scheme and parsed.netloc:
            return normalize_origin(f"{parsed.scheme}://{parsed.netloc}")
    return None


def validate_origin_format(origin: str) -> bool:
    normalized = normalize_origin(origin)
    parsed = urlparse(normalized)
    if not parsed.scheme or not parsed.netloc:
        return False
    if parsed.path not in ("", "/"):
        return False
    return bool(ORIGIN_PATTERN.match(normalized))


def origin_from_url(url: str) -> str | None:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    return normalize_origin(f"{parsed.scheme}://{parsed.netloc}")


def is_origin_allowed(
    request_origin: str | None,
    allowed_origins: list[str] | None,
) -> bool:
    """
    Empty allowed_origins means allow all (backward compatible).
    When a whitelist is configured, the request origin must match.
    """
    allowed = allowed_origins or []
    if not allowed:
        return True
    if not request_origin:
        return False
    normalized_request = normalize_origin(request_origin)
    normalized_allowed = {normalize_origin(o) for o in allowed}
    return normalized_request in normalized_allowed


def default_allowed_origins(website_url: str, frontend_url: str) -> list[str]:
    """Seed whitelist with the business site and dashboard for testing."""
    origins: list[str] = []
    site = origin_from_url(website_url)
    if site:
        origins.append(site)
    dashboard = origin_from_url(frontend_url)
    if dashboard and dashboard not in origins:
        origins.append(dashboard)
    return origins
