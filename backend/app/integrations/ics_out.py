"""Feed ICS in uscita (§17.7, §18).

È la metà "Work Planner -> calendario" della bidirezionalità: invece di
scrivere sul calendario altrui via API, si espone un feed sottoscrivibile che
Outlook e Google aggiornano da soli. Non serve esportare un file a ogni
modifica (§18).

Un evento per PlanningSegment, non per task: un task da 12h distribuito su due
giorni deve comparire nel calendario come due blocchi, altrimenti la
rappresentazione mentirebbe sull'allocazione.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from icalendar import Calendar, Event

#: Ora di inizio convenzionale della giornata nel feed. I PlanningSegment
#: allocano minuti su un giorno, non fasce orarie: il feed li rende sequenziali
#: a partire da qui, così il calendario resta leggibile.
DAY_START = time(9, 0)

_PRODID = "-//Work Planner//planning feed//IT"


@dataclass(frozen=True, slots=True)
class FeedSegment:
    task_id: str
    title: str
    day: date
    minutes: int
    project_name: str | None = None


def build_feed(
    segments: list[FeedSegment],
    tz: str = "Europe/Rome",
    calendar_name: str = "Work Planner",
) -> bytes:
    zone = ZoneInfo(tz)
    calendar = Calendar()
    calendar.add("prodid", _PRODID)
    calendar.add("version", "2.0")
    calendar.add("x-wr-calname", calendar_name)
    # Suggerisce ai client ogni quanto ricontrollare il feed.
    calendar.add("x-published-ttl", "PT30M")

    # I segmenti dello stesso giorno vengono impilati in sequenza dall'inizio
    # giornata. Ordine stabile per task_id a parità di giorno, così il feed non
    # cambia a ogni rigenerazione senza motivo.
    by_day: dict[date, list[FeedSegment]] = {}
    for segment in sorted(segments, key=lambda s: (s.day, s.task_id)):
        by_day.setdefault(segment.day, []).append(segment)

    for day, day_segments in sorted(by_day.items()):
        cursor = datetime.combine(day, DAY_START, tzinfo=zone)
        for segment in day_segments:
            end = cursor + timedelta(minutes=segment.minutes)
            event = Event()
            # UID stabile: lo stesso segmento deve aggiornarsi, non duplicarsi.
            event.add("uid", f"{segment.task_id}-{day.isoformat()}@work-planner")
            event.add("summary", _summary(segment))
            event.add("dtstart", cursor)
            event.add("dtend", end)
            event.add("transp", "TRANSPARENT")  # è pianificazione, non un impegno con altri
            calendar.add_component(event)
            cursor = end

    return calendar.to_ical()


def _summary(segment: FeedSegment) -> str:
    return f"{segment.project_name} · {segment.title}" if segment.project_name else segment.title
