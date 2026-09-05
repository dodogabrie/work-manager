"""§11 and §17: capacity arithmetic and calendar occupation."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.domain.capacity import (
    CalendarEvent,
    CapacityCalendar,
    busy_minutes_by_day,
    merge_intervals,
)

ROME = ZoneInfo("Europe/Rome")
DAY = date(2026, 1, 5)


def dt(hour: int, minute: int = 0, day: int = 5) -> datetime:
    return datetime(2026, 1, day, hour, minute, tzinfo=ROME)


def test_merge_empty() -> None:
    assert merge_intervals([]) == []


def test_merge_disjoint_keeps_both_and_sorts() -> None:
    assert merge_intervals([(10, 12), (1, 3)]) == [(1, 3), (10, 12)]


def test_merge_overlapping() -> None:
    assert merge_intervals([(1, 5), (3, 8)]) == [(1, 8)]


def test_merge_adjacent() -> None:
    assert merge_intervals([(1, 3), (3, 6)]) == [(1, 6)]


def test_merge_contained() -> None:
    assert merge_intervals([(1, 10), (3, 4)]) == [(1, 10)]


def test_merge_identical() -> None:
    assert merge_intervals([(1, 5), (1, 5)]) == [(1, 5)]


def test_merge_drops_empty_intervals() -> None:
    assert merge_intervals([(5, 5), (1, 2)]) == [(1, 2)]


def test_merge_chain() -> None:
    assert merge_intervals([(1, 3), (2, 4), (4, 5), (9, 10)]) == [(1, 5), (9, 10)]


def test_busy_single_meeting() -> None:
    events = [CalendarEvent(dt(9), dt(11))]
    assert busy_minutes_by_day(events, ROME) == {DAY: 120}


def test_busy_overlapping_meetings_count_once() -> None:
    """§17.6: two overlapping meetings must not subtract the same minute twice."""
    events = [CalendarEvent(dt(9), dt(11)), CalendarEvent(dt(10), dt(12))]
    assert busy_minutes_by_day(events, ROME) == {DAY: 180}


def test_busy_declined_is_ignored() -> None:
    """§17.5: accepted and tentative occupy capacity, declined does not."""
    events = [
        CalendarEvent(dt(9), dt(10), "accepted"),
        CalendarEvent(dt(10), dt(11), "tentative"),
        CalendarEvent(dt(11), dt(15), "declined"),
    ]
    assert busy_minutes_by_day(events, ROME) == {DAY: 120}


def test_busy_across_midnight_is_split_per_day() -> None:
    events = [CalendarEvent(dt(23), dt(1, 0, day=6))]
    assert busy_minutes_by_day(events, ROME) == {DAY: 60, date(2026, 1, 6): 60}


def test_busy_naive_datetimes_are_read_in_the_given_timezone() -> None:
    events = [CalendarEvent(datetime(2026, 1, 5, 9), datetime(2026, 1, 5, 10))]
    assert busy_minutes_by_day(events, ROME) == {DAY: 60}


def test_busy_converts_other_timezones() -> None:
    utc = ZoneInfo("UTC")
    start = datetime(2026, 1, 5, 23, 30, tzinfo=utc)
    events = [CalendarEvent(start, start + timedelta(hours=1))]
    # 23:30 UTC is 00:30 local on the 6th.
    assert busy_minutes_by_day(events, ROME) == {date(2026, 1, 6): 60}


def test_available_subtracts_meetings_from_the_baseline() -> None:
    cal = CapacityCalendar({0: 480}, {}, {DAY: 120})
    assert cal.available(DAY) == 360


def test_exception_overrides_the_weekly_baseline() -> None:
    cal = CapacityCalendar({0: 480}, {DAY: 240}, {})
    assert cal.available(DAY) == 240


def test_available_never_goes_negative() -> None:
    cal = CapacityCalendar({0: 480}, {}, {DAY: 600})
    assert cal.available(DAY) == 0


def test_unknown_weekday_has_no_capacity() -> None:
    cal = CapacityCalendar({0: 480})
    assert cal.available(date(2026, 1, 10)) == 0  # Saturday


def test_iter_days_walks_forward() -> None:
    cal = CapacityCalendar({0: 480})
    days = cal.iter_days(DAY)
    assert [next(days) for _ in range(3)] == [DAY, date(2026, 1, 6), date(2026, 1, 7)]
