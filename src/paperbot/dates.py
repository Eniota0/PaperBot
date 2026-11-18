"""UTC date logic: target date, catch-up ranges, new-channel baseline."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta


def target_date(now: datetime, delay_days: int) -> date:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    return now.astimezone(UTC).date() - timedelta(days=delay_days)


def catchup_dates(last_posted: date | None, target: date, max_days: int) -> list[date]:
    if last_posted is None:
        return [target]
    days = (target - last_posted).days
    if days <= 0:
        return []
    dates = [last_posted + timedelta(days=i) for i in range(1, days + 1)]
    return dates[-max_days:]


def new_channel_baseline(now: datetime, schedule: time, delay_days: int) -> date:
    t = target_date(now, delay_days)
    now_utc = now.astimezone(UTC).time().replace(tzinfo=None)
    return t if now_utc >= schedule.replace(tzinfo=None) else t - timedelta(days=1)


def pending_dates(floor: date | None, posted: set[date], target: date, max_days: int) -> list[date]:
    """Dates still to post: the last `max_days` dates up to target, from `floor` on, not yet posted.

    A date that failed earlier is retried while it stays inside the window (spec 7.10).
    """
    if floor is None:
        return [] if target in posted else [target]
    window = [target - timedelta(days=i) for i in range(max_days - 1, -1, -1)]
    return [d for d in window if d >= floor and d not in posted]
