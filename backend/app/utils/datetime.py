"""UTC timezone datetime helpers for CliniXAI backend."""

from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures a datetime is timezone-aware in UTC.
    
    If dt is naive, it is assumed to be UTC and assigned UTC timezone.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_iso_utc(dt: Optional[datetime] = None) -> str:
    """Formats a datetime as an ISO 8601 UTC string ending in 'Z'.
    
    If dt is None, uses current UTC time.
    """
    if dt is None:
        dt = utc_now()
    elif dt.tzinfo is None:
        # Assume naive datetime is in UTC
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    
    return dt.isoformat()


def parse_iso_utc(iso_string: str) -> datetime:
    """Parses an ISO 8601 string into a timezone-aware UTC datetime."""
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
