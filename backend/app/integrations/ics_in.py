"""Lettura di un feed ICS in ingresso (§17, §18).

Sostituisce Microsoft Graph: niente OAuth, niente webhook, niente delta sync.
Si scarica l'URL ICS del calendario e se ne estraggono gli intervalli occupati.

Questo modulo fa SOLO parsing: non tocca il DB e non decide nulla sul piano.
La riduzione di capacità e la conseguente proposal sono responsabilità dei
servizi applicativi (§29).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events

from ..models.enums import CalendarEventStatus

#: Mappa gli stati iCalendar su quelli che ci interessano (§17.5).
#: Tutto ciò che non è esplicitamente declined occupa capacità: un meeting a cui
#: non si è ancora risposto va considerato impegnato, altrimenti il piano
#: promette capacità che non esiste.
_PARTSTAT_TO_STATUS = {
    "ACCEPTED": CalendarEventStatus.ACCEPTED,
    "TENTATIVE": CalendarEventStatus.TENTATIVE,
    "NEEDS-ACTION": CalendarEventStatus.TENTATIVE,
    "DECLINED": CalendarEventStatus.DECLINED,
}


@dataclass(frozen=True, slots=True)
class IcsEvent:
    uid: str
    recurrence_id: str | None
    summary: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    status: CalendarEventStatus
    cancelled: bool

    @property
    def occupies_capacity(self) -> bool:
        return not self.cancelled and self.status is not CalendarEventStatus.DECLINED


def _as_aware(value: date | datetime, tz: ZoneInfo) -> tuple[datetime, bool]:
    """Normalizza a datetime con timezone. Il bool dice se era un all-day."""
    if isinstance(value, datetime):
        return (value if value.tzinfo else value.replace(tzinfo=tz)), False
    # un VALUE=DATE è un evento all-day: lo ancoriamo alla mezzanotte locale
    return datetime.combine(value, time.min, tzinfo=tz), True


def _status_of(component: icalendar.Event) -> tuple[CalendarEventStatus, bool]:
    cancelled = str(component.get("STATUS", "")).upper() == "CANCELLED"

    attendees = component.get("ATTENDEE")
    if attendees is not None:
        # icalendar restituisce un singolo valore o una lista, a seconda del feed
        for attendee in attendees if isinstance(attendees, list) else [attendees]:
            partstat = str(getattr(attendee, "params", {}).get("PARTSTAT", "")).upper()
            if partstat in _PARTSTAT_TO_STATUS:
                return _PARTSTAT_TO_STATUS[partstat], cancelled

    # Un feed ICS personale spesso non riporta il PARTSTAT del proprietario:
    # in assenza di informazioni si assume che l'evento occupi la giornata.
    if str(component.get("TRANSP", "")).upper() == "TRANSPARENT":
        return CalendarEventStatus.DECLINED, cancelled
    return CalendarEventStatus.ACCEPTED, cancelled


def parse_ics(
    raw: str | bytes,
    window_start: date,
    window_end: date,
    tz: str = "Europe/Rome",
) -> list[IcsEvent]:
    """Espande il calendario nella finestra richiesta, ricorrenze incluse.

    La finestra è obbligatoria perché una regola di ricorrenza senza fine
    genererebbe eventi all'infinito.
    """
    zone = ZoneInfo(tz)
    calendar = icalendar.Calendar.from_ical(raw)
    occurrences = recurring_ical_events.of(calendar).between(window_start, window_end)

    events: list[IcsEvent] = []
    for component in occurrences:
        start_raw = component.get("DTSTART")
        end_raw = component.get("DTEND") or component.get("DUE")
        if start_raw is None:
            continue

        starts_at, start_all_day = _as_aware(start_raw.dt, zone)
        if end_raw is None:
            duration = component.get("DURATION")
            ends_at = starts_at + (duration.dt if duration else timedelta(hours=1))
            end_all_day = start_all_day
        else:
            ends_at, end_all_day = _as_aware(end_raw.dt, zone)

        if ends_at <= starts_at:
            continue

        status, cancelled = _status_of(component)
        recurrence = component.get("RECURRENCE-ID")
        events.append(
            IcsEvent(
                uid=str(component.get("UID", "")),
                recurrence_id=recurrence.dt.isoformat() if recurrence is not None else None,
                summary=str(component.get("SUMMARY")) if component.get("SUMMARY") else None,
                starts_at=starts_at.astimezone(UTC),
                ends_at=ends_at.astimezone(UTC),
                all_day=start_all_day and end_all_day,
                status=status,
                cancelled=cancelled,
            )
        )

    # Ordine stabile: gli eventi alimentano la capacità, che alimenta lo
    # scheduler, che deve essere deterministico (§32.2.7).
    events.sort(key=lambda e: (e.starts_at, e.ends_at, e.uid, e.recurrence_id or ""))
    return events
