from datetime import datetime, timezone
from typing import Optional

def get_utc_now() -> datetime:
    """Get current time in UTC."""
    return datetime.now(timezone.utc)

def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is timezone-aware and set to UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

def parse_utc_timestamp(timestamp_str: str) -> datetime:
    """Parse an ISO 8601 string to a UTC timezone-aware datetime."""
    if not timestamp_str:
        return get_utc_now()
    if timestamp_str.endswith("Z"):
        timestamp_str = timestamp_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(timestamp_str)
    return ensure_utc(dt)
