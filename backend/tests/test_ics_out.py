"""Feed ICS in uscita (§18). Il feed è sottoscritto da client esterni: un UID
instabile creerebbe duplicati a ogni refresh invece di aggiornare gli eventi."""

from datetime import date

import icalendar

from app.integrations.ics_out import FeedSegment, build_feed


def _events(raw: bytes) -> list[icalendar.Event]:
    return list(icalendar.Calendar.from_ical(raw).walk("VEVENT"))


def test_one_event_per_segment():
    """Un task multi-giorno deve comparire come più blocchi (§6.4)."""
    feed = build_feed([
        FeedSegment("t1", "RAW API", date(2026, 9, 7), 480),
        FeedSegment("t1", "RAW API", date(2026, 9, 8), 240),
    ])
    assert len(_events(feed)) == 2


def test_uid_is_stable_across_rebuilds():
    segments = [FeedSegment("t1", "RAW API", date(2026, 9, 7), 480)]
    first = [str(e["UID"]) for e in _events(build_feed(segments))]
    second = [str(e["UID"]) for e in _events(build_feed(segments))]
    assert first == second


def test_uid_differs_per_day():
    feed = build_feed([
        FeedSegment("t1", "RAW API", date(2026, 9, 7), 480),
        FeedSegment("t1", "RAW API", date(2026, 9, 8), 240),
    ])
    uids = {str(e["UID"]) for e in _events(feed)}
    assert len(uids) == 2


def test_segments_of_a_day_do_not_overlap():
    feed = build_feed([
        FeedSegment("a", "A", date(2026, 9, 7), 300),
        FeedSegment("b", "B", date(2026, 9, 7), 180),
    ])
    events = sorted(_events(feed), key=lambda e: e["DTSTART"].dt)
    assert events[0]["DTEND"].dt == events[1]["DTSTART"].dt


def test_duration_matches_planned_minutes():
    feed = build_feed([FeedSegment("a", "A", date(2026, 9, 7), 150)])
    (event,) = _events(feed)
    assert (event["DTEND"].dt - event["DTSTART"].dt).total_seconds() == 150 * 60


def test_project_prefixes_the_summary():
    feed = build_feed([FeedSegment("a", "Fix import", date(2026, 9, 7), 60, "MAG")])
    (event,) = _events(feed)
    assert str(event["SUMMARY"]) == "MAG · Fix import"


def test_empty_plan_is_still_a_valid_calendar():
    calendar = icalendar.Calendar.from_ical(build_feed([]))
    assert calendar.walk("VEVENT") == []
