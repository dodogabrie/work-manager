"""Parsing ICS (§17). Il rischio vero qui è sottrarre capacità che non è
davvero occupata, o non sottrarne una che lo è."""

from datetime import date

from app.integrations.ics_in import parse_ics
from app.models.enums import CalendarEventStatus


def _cal(*events: str) -> str:
    body = "\n".join(events)
    return f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//\n{body}\nEND:VCALENDAR"


def _ev(**kw: str) -> str:
    lines = "\n".join(f"{k.replace('_', '-')}:{v}" for k, v in kw.items())
    return f"BEGIN:VEVENT\n{lines}\nEND:VEVENT"


WEEK = (date(2026, 9, 7), date(2026, 9, 14))


def test_simple_meeting():
    ics = _cal(_ev(UID="a", DTSTART="20260907T090000Z", DTEND="20260907T110000Z", SUMMARY="Standup"))
    (event,) = parse_ics(ics, *WEEK)
    assert event.uid == "a"
    assert (event.ends_at - event.starts_at).total_seconds() == 7200
    assert event.occupies_capacity


def test_declined_meeting_does_not_occupy_capacity():
    """§17.5: rifiutata -> non occupa capacità."""
    ics = _cal(
        "BEGIN:VEVENT\nUID:b\nDTSTART:20260907T090000Z\nDTEND:20260907T100000Z\n"
        "ATTENDEE;PARTSTAT=DECLINED:mailto:me@example.com\nEND:VEVENT"
    )
    (event,) = parse_ics(ics, *WEEK)
    assert event.status is CalendarEventStatus.DECLINED
    assert not event.occupies_capacity


def test_tentative_meeting_occupies_capacity():
    """§17.5: provvisoria -> occupa capacità."""
    ics = _cal(
        "BEGIN:VEVENT\nUID:c\nDTSTART:20260907T090000Z\nDTEND:20260907T100000Z\n"
        "ATTENDEE;PARTSTAT=TENTATIVE:mailto:me@example.com\nEND:VEVENT"
    )
    (event,) = parse_ics(ics, *WEEK)
    assert event.status is CalendarEventStatus.TENTATIVE
    assert event.occupies_capacity


def test_unanswered_invite_still_occupies_capacity():
    """Non rispondere a un invito non libera la giornata."""
    ics = _cal(
        "BEGIN:VEVENT\nUID:d\nDTSTART:20260907T090000Z\nDTEND:20260907T100000Z\n"
        "ATTENDEE;PARTSTAT=NEEDS-ACTION:mailto:me@example.com\nEND:VEVENT"
    )
    (event,) = parse_ics(ics, *WEEK)
    assert event.occupies_capacity


def test_transparent_event_does_not_occupy_capacity():
    ics = _cal(_ev(UID="e", DTSTART="20260907T090000Z", DTEND="20260907T100000Z", TRANSP="TRANSPARENT"))
    (event,) = parse_ics(ics, *WEEK)
    assert not event.occupies_capacity


def test_cancelled_event_does_not_occupy_capacity():
    ics = _cal(_ev(UID="f", DTSTART="20260907T090000Z", DTEND="20260907T100000Z", STATUS="CANCELLED"))
    (event,) = parse_ics(ics, *WEEK)
    assert event.cancelled
    assert not event.occupies_capacity


def test_recurring_meeting_is_expanded():
    ics = _cal(
        _ev(UID="g", DTSTART="20260907T090000Z", DTEND="20260907T093000Z", RRULE="FREQ=DAILY;COUNT=5")
    )
    assert len(parse_ics(ics, *WEEK)) == 5


def test_event_without_dtend_uses_duration():
    ics = _cal(_ev(UID="h", DTSTART="20260907T090000Z", DURATION="PT90M"))
    (event,) = parse_ics(ics, *WEEK)
    assert (event.ends_at - event.starts_at).total_seconds() == 5400


def test_zero_length_event_is_dropped():
    ics = _cal(_ev(UID="i", DTSTART="20260907T090000Z", DTEND="20260907T090000Z"))
    assert parse_ics(ics, *WEEK) == []


def test_all_day_event_is_flagged():
    ics = _cal("BEGIN:VEVENT\nUID:j\nDTSTART;VALUE=DATE:20260908\nDTEND;VALUE=DATE:20260909\nEND:VEVENT")
    (event,) = parse_ics(ics, *WEEK)
    assert event.all_day


def test_output_order_is_deterministic():
    """La capacità alimenta lo scheduler, che deve essere deterministico (§32.2.7)."""
    ics = _cal(
        _ev(UID="z", DTSTART="20260909T140000Z", DTEND="20260909T150000Z"),
        _ev(UID="a", DTSTART="20260907T090000Z", DTEND="20260907T100000Z"),
    )
    assert [e.uid for e in parse_ics(ics, *WEEK)] == ["a", "z"]
