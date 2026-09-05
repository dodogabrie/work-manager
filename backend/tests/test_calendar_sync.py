"""Sync ICS in ingresso (§17, §39, §40).

Il rischio principale non è sbagliare il parsing — quello è già coperto da
test_ics_in — ma reagire troppo: compattare il piano quando si libera capacità.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.models import (
    ExternalCalendarEvent,
    PlanningProposal,
    PlanningSegment,
    ProposalKind,
    TaskStatus,
)
from app.services import calendar_sync, planning, proposals, tasks

from .conftest import MON

TUE = MON + timedelta(days=1)
WED = MON + timedelta(days=2)
THU = MON + timedelta(days=3)


# ---------------------------------------------------------------- fixture ICS

class FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        pass


def feed(*events: str):
    """http_get finto: nessuna rete, nessun mock globale."""
    body = "".join(events)
    ics = f"BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//test//\n{body}END:VCALENDAR\n"

    def http_get(url: str, **kwargs) -> FakeResponse:
        return FakeResponse(ics)

    return http_get


def meeting(uid: str, day: date, start_hour: int, end_hour: int) -> str:
    """Orari in UTC; Europe/Rome d'inverno è UTC+1, quindi +1h in locale."""
    stamp = day.strftime("%Y%m%d")
    return (
        f"BEGIN:VEVENT\nUID:{uid}\nSUMMARY:{uid}\n"
        f"DTSTART:{stamp}T{start_hour:02d}0000Z\nDTEND:{stamp}T{end_hour:02d}0000Z\n"
        "END:VEVENT\n"
    )


def connection(session):
    return calendar_sync.add_connection(session, "Outlook", "https://example.invalid/cal.ics")


def planned(session, minutes=960):
    """Un piano confermato: 960 min = lunedì pieno + martedì pieno."""
    task = tasks.quick_add(session, "A", planning_effort_minutes=minutes)
    proposal = tasks.change_status(session, task.id, TaskStatus.PLANNED, horizon_start=MON)
    proposals.approve(session, proposal.id)
    return task


def segments(session):
    return sorted(
        (s.day, s.task_id, s.minutes) for s in session.scalars(planning.select(PlanningSegment))
    )


def calendar_proposals(session):
    return list(
        session.scalars(
            planning.select(PlanningProposal).where(
                PlanningProposal.kind == ProposalKind.CALENDAR_CHANGE
            )
        )
    )


# ---------------------------------------------------------------- capacità persa

def test_new_meeting_making_the_plan_infeasible_proposes_a_shift(session):
    """§17.2 / §39: la capacità persa genera una proposal, non un piano nuovo."""
    planned(session)
    before = segments(session)

    result = calendar_sync.sync_connection(
        session, connection(session), MON, feed(meeting("m1", MON, 8, 12))
    )

    assert result.proposal is not None
    assert result.proposal.kind == ProposalKind.CALENDAR_CHANGE
    assert result.proposal.status == "pending"
    # §3.3: l'evento esiste subito, il piano no — finché non si approva.
    assert segments(session) == before
    assert result.proposal.simulation["segments"] != [
        planning.segment_json(s) for s in planning.current_plan(session).segments
    ]

    proposals.approve(session, result.proposal.id)
    assert segments(session) != before  # lo shift arriva solo ora


def test_meeting_that_still_fits_produces_no_proposal(session):
    """Capacità ridotta ma piano ancora materializzabile: niente da decidere."""
    planned(session)
    before = segments(session)

    result = calendar_sync.sync_connection(
        session, connection(session), MON, feed(meeting("m1", WED, 8, 10))
    )

    assert result.proposal is None
    assert segments(session) == before
    assert session.query(ExternalCalendarEvent).count() == 1


# ---------------------------------------------------------------- capacità recuperata

def test_cancelled_meeting_recovers_capacity_without_compacting(session):
    """§17.4 / §40 / R6: capacity recovered sì, auto compaction no.

    L'asimmetria è il punto: la stessa variazione, letta al contrario, non
    produce niente. Non manca del codice, è la regola.
    """
    planned(session)
    conn = connection(session)
    calendar_sync.sync_connection(session, conn, MON, feed(meeting("m1", WED, 8, 10)))
    before = segments(session)

    result = calendar_sync.sync_connection(session, conn, MON, feed())

    assert result.cancelled == 1
    assert session.scalars(planning.select(ExternalCalendarEvent)).one().cancelled is True
    assert result.proposal is None
    assert calendar_proposals(session) == []
    assert segments(session) == before  # nessun anticipo, nessuna compattazione


def test_meeting_moved_away_from_a_busy_day_does_not_propose(session):
    """§39: il lunedì recupera 2h e non succede nulla; il giovedì è libero."""
    planned(session)
    conn = connection(session)
    calendar_sync.sync_connection(session, conn, MON, feed(meeting("m1", MON, 8, 10)))
    proposals.approve(session, calendar_proposals(session)[0].id)
    before = segments(session)

    result = calendar_sync.sync_connection(session, conn, MON, feed(meeting("m1", THU, 8, 10)))

    assert result.proposal is None
    assert segments(session) == before


# ---------------------------------------------------------------- identità degli eventi

def test_moved_meeting_is_a_single_variation_not_a_delete_plus_create(session):
    """§17.3: stesso UID, stessa riga — si aggiornano gli estremi."""
    conn = connection(session)
    calendar_sync.sync_connection(session, conn, MON, feed(meeting("m1", MON, 8, 10)))
    original = session.scalars(planning.select(ExternalCalendarEvent)).one()
    original_id, original_start = original.id, original.starts_at

    calendar_sync.sync_connection(session, conn, MON, feed(meeting("m1", THU, 8, 10)))

    row = session.scalars(planning.select(ExternalCalendarEvent)).one()
    assert row.id == original_id
    assert row.cancelled is False
    assert row.starts_at != original_start
    assert row.starts_at.date() == THU


def test_two_identical_syncs_are_idempotent(session):
    """Nessun evento duplicato, nessuna seconda proposal."""
    planned(session)
    conn = connection(session)
    ics = feed(meeting("m1", MON, 8, 12))

    first = calendar_sync.sync_connection(session, conn, MON, ics)
    second = calendar_sync.sync_connection(session, conn, MON, ics)

    assert session.query(ExternalCalendarEvent).count() == 1
    assert second.upserted == 0 and second.cancelled == 0
    assert [p.id for p in calendar_proposals(session)] == [first.proposal.id]
    assert second.proposal.id == first.proposal.id


# ---------------------------------------------------------------- errori e sovrapposizioni

def test_unreachable_feed_records_the_error_and_leaves_the_plan_intact(session):
    planned(session)
    before = segments(session)
    conn = connection(session)

    def exploding(url: str, **kwargs):
        raise ConnectionError("name or service not known")

    result = calendar_sync.sync_connection(session, conn, MON, exploding)

    assert result.error and "ConnectionError" in conn.last_sync_error
    assert conn.last_synced_at is None
    assert result.proposal is None
    assert segments(session) == before
    assert session.query(ExternalCalendarEvent).count() == 0


def test_a_successful_sync_clears_a_previous_error(session):
    conn = connection(session)
    conn.last_sync_error = "boom"

    calendar_sync.sync_connection(session, conn, MON, feed(meeting("m1", WED, 8, 10)))

    assert conn.last_sync_error is None
    assert conn.last_synced_at is not None


def test_overlapping_meetings_subtract_their_union(session):
    """§17.6: due riunioni sovrapposte non sottraggono due volte lo stesso minuto."""
    conn = connection(session)
    calendar_sync.sync_connection(
        session, conn, MON, feed(meeting("m1", MON, 8, 12), meeting("m2", MON, 10, 14))
    )

    capacity = planning.build_capacity(session, MON, MON + timedelta(days=7))
    # unione 09:00-15:00 locali = 360 min, non 240 + 240
    assert capacity.available(MON) == 480 - 360
