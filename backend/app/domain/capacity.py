"""Capacity: weekly baseline, exceptions and external calendar occupation (§11, §17)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, tzinfo

# §17.5: accepted and tentative meetings occupy capacity, declined ones do not.
OCCUPYING_STATUSES = frozenset({"accepted", "tentative"})


@dataclass(frozen=True, slots=True)
class CalendarEvent:
    start: datetime
    end: datetime
    status: str = "accepted"


def merge_intervals[T](intervals: Sequence[tuple[T, T]]) -> list[tuple[T, T]]:
    """Union of overlapping or adjacent intervals.

    §17.6: two overlapping meetings must not subtract the same minute twice.
    """
    ordered = sorted((s, e) for s, e in intervals if s < e)
    merged: list[tuple[T, T]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1] = (merged[-1][0], end)
        else:
            merged.append((start, end))
    return merged


def busy_minutes_by_day(events: Iterable[CalendarEvent], tz: tzinfo) -> dict[date, int]:
    """Minutes occupied per local day, counting each minute once."""
    intervals: list[tuple[datetime, datetime]] = []
    for event in events:
        if event.status.lower() not in OCCUPYING_STATUSES:
            continue
        start = _to_tz(event.start, tz)
        end = _to_tz(event.end, tz)
        if start < end:
            intervals.append((start, end))

    busy: dict[date, int] = {}
    for start, end in merge_intervals(intervals):
        day = start.date()
        while day <= end.date():
            day_start = datetime.combine(day, time.min, tzinfo=tz)
            slice_start = max(start, day_start)
            slice_end = min(end, day_start + timedelta(days=1))
            minutes = int((slice_end - slice_start).total_seconds() // 60)
            if minutes > 0:
                busy[day] = busy.get(day, 0) + minutes
            day += timedelta(days=1)
    return busy


def _to_tz(value: datetime, tz: tzinfo) -> datetime:
    return value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)


@dataclass(frozen=True, slots=True)
class CapacityCalendar:
    """Schedulable minutes per day: baseline, overridden by exceptions, minus meetings."""

    weekly: dict[int, int]  # weekday 0=Monday .. 6=Sunday -> minutes
    exceptions: dict[date, int] = field(default_factory=dict)  # §11.3 holidays, leave
    busy: dict[date, int] = field(default_factory=dict)  # §11.4 meetings

    def available(self, day: date) -> int:
        base = self.exceptions.get(day, self.weekly.get(day.weekday(), 0))
        return max(0, base - self.busy.get(day, 0))

    def iter_days(self, start: date) -> Iterator[date]:
        day = start
        while True:
            yield day
            day += timedelta(days=1)
