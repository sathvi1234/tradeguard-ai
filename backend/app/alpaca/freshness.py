"""Market-data freshness helpers. Thresholds live in config, not call sites."""

from datetime import datetime, timezone
from typing import Optional

from app.config import settings
from app.models.market_data import FreshnessStatus


def parse_alpaca_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def evaluate_freshness(
    timestamp: Optional[datetime],
    *,
    max_age_seconds: Optional[int] = None,
    now: Optional[datetime] = None,
) -> FreshnessStatus:
    if timestamp is None:
        return FreshnessStatus.DATA_UNAVAILABLE
    current = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age = (current - timestamp).total_seconds()
    if age < 0:
        age = 0
    limit = max_age_seconds if max_age_seconds is not None else settings.quote_max_age_seconds
    if age > limit:
        return FreshnessStatus.STALE
    return FreshnessStatus.FRESH
