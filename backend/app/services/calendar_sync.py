"""Sincronizzazione ICS in ingresso (§17, §18, §32.18).

Il calendario esterno è una fonte di occupazione della capacità, non di task
(§17.1). Questo service scarica il feed, riallinea la cache degli eventi e —
solo se serve — propone una ripianificazione. Non applica mai nulla al piano
(§3.3, §17.7).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..domain.scheduler import MAX_HORIZON_DAYS
from ..integrations.ics_in import IcsEvent, parse_ics
from ..models import (
    ExternalCalendarConnection,
    ExternalCalendarEvent,
    PlanningProposal,
    PlanningSegment,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
)
from . import planning, proposals

#: Finestra di sincronizzazione. Indietro di una settimana perché una riunione
#: appena passata può ancora spiegare un segmento congelato; in avanti quanto
#: basta a coprire un piano realistico.
PAST_DAYS = 7
FUTURE_DAYS = 90

HTTP_TIMEOUT = 20.0

#: Un `httpx.Response`-like: basta `.raise_for_status()` e `.text`.
HttpGet = Callable[..., httpx.Response]


class SyncResult:
    """Cosa è cambiato in un sync. Non è un'entità: serve al router e ai test."""

    __slots__ = ("connection", "upserted", "cancelled", "proposal", "error")

    def __init__(
        self,
        connection: ExternalCalendarConnection,
        upserted: int = 0,
        cancelled: int = 0,
        proposal: PlanningProposal | None = None,
        error: str | None = None,
    ) -> None:
        self.connection = connection
        self.upserted = upserted
        self.cancelled = cancelled
        self.proposal = proposal
        self.error = error


# ---------------------------------------------------------------- connessioni

def list_connections(session: Session) -> list[ExternalCalendarConnection]:
    return list(
        session.scalars(
            select(ExternalCalendarConnection)
            .where(ExternalCalendarConnection.deleted_at.is_(None))
            .order_by(ExternalCalendarConnection.created_at)
        )
    )


def get_connection(session: Session, connection_id) -> ExternalCalendarConnection:
    row = session.get(ExternalCalendarConnection, connection_id)
    if row is None or row.deleted_at is not None:
        raise LookupError(f"calendar connection {connection_id} not found")
    return row


def add_connection(
    session: Session, name: str, ics_url: str, enabled: bool = True
) -> ExternalCalendarConnection:
    if not ics_url.strip():
        raise ValueError("ics_url is required")
    row = ExternalCalendarConnection(
        name=name.strip(), ics_url=ics_url.strip(), enabled=enabled
    )
    session.add(row)
    session.commit()
    return row


def update_connection(
    session: Session,
    connection_id,
    name: str | None = None,
    ics_url: str | None = None,
    enabled: bool | None = None,
) -> ExternalCalendarConnection:
    row = get_connection(session, connection_id)
    if name is not None:
        row.name = name.strip()
    if ics_url is not None:
        row.ics_url = ics_url.strip()
    if enabled is not None:
        row.enabled = enabled
    session.commit()
    return row


def remove_connection(session: Session, connection_id) -> ExternalCalendarConnection:
    """§23.2: soft delete. Gli eventi già in cache restano, ma smettono di
    essere aggiornati; è l'utente a decidere se il piano va rifatto."""
    row = get_connection(session, connection_id)
    row.deleted_at = datetime.now(UTC)
    row.enabled = False
    session.commit()
    return row


# ---------------------------------------------------------------- sync

def sync_connection(
    session: Session,
    connection: ExternalCalendarConnection,
    today: date,
    http_get: HttpGet = httpx.get,
) -> SyncResult:
    """Scarica il feed, riallinea la cache, e propone se il piano non regge più.

    Un feed irraggiungibile o illeggibile non è un errore dell'applicazione: si
    registra su `last_sync_error` e il piano resta esattamente com'era.
    """
    try:
        response = http_get(connection.ics_url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        events = parse_ics(
            response.text,
            today - timedelta(days=PAST_DAYS),
            today + timedelta(days=FUTURE_DAYS),
            tz=settings.tz,
        )
    except Exception as exc:  # rete, HTTP, o ICS malformato: stessa conseguenza
        connection.last_sync_error = f"{type(exc).__name__}: {exc}"
        session.commit()
        return SyncResult(connection, error=connection.last_sync_error)

    upserted, cancelled = _apply_feed(session, connection, events)
    connection.last_synced_at = datetime.now(UTC)
    connection.last_sync_error = None
    session.flush()

    proposal = _propose_if_infeasible(session, today)
    session.commit()
    return SyncResult(connection, upserted, cancelled, proposal)


def sync_all(
    session: Session, today: date, http_get: HttpGet = httpx.get
) -> list[SyncResult]:
    return [
        sync_connection(session, connection, today, http_get)
        for connection in list_connections(session)
        if connection.enabled
    ]


def _apply_feed(
    session: Session,
    connection: ExternalCalendarConnection,
    events: list[IcsEvent],
) -> tuple[int, int]:
    """Upsert per (connection_id, uid, recurrence_id).

    §17.3: una riunione spostata conserva il suo UID, quindi qui è un UPDATE di
    start/end — una sola variazione, non una cancellazione più una creazione.
    """
    existing = {
        (row.uid, row.recurrence_id): row
        for row in session.scalars(
            select(ExternalCalendarEvent).where(
                ExternalCalendarEvent.connection_id == connection.id
            )
        )
    }
    seen: set[tuple[str, str | None]] = set()
    upserted = 0
    for event in events:
        key = (event.uid, _recurrence_key(event, events))
        seen.add(key)
        row = existing.get(key)
        if row is None:
            row = ExternalCalendarEvent(
                connection_id=connection.id, uid=key[0], recurrence_id=key[1]
            )
            session.add(row)
        if _fill(row, event):
            upserted += 1

    # Sparito dal feed = cancellato (§17.4). Si marca, non si elimina: la
    # history deve poter spiegare perché la capacità era ridotta.
    cancelled = 0
    for key, row in existing.items():
        if key not in seen and not row.cancelled:
            row.cancelled = True
            cancelled += 1
    session.flush()
    return upserted, cancelled


def _recurrence_key(event: IcsEvent, events: list[IcsEvent]) -> str | None:
    """Il RECURRENCE-ID distingue le occorrenze di una serie, non identifica un
    evento singolo: l'espansione ICS lo valorizza comunque, con il DTSTART.

    Tenerlo per un evento singolo significherebbe cambiargli identità appena
    viene spostato, cioè leggere uno spostamento come cancellazione + creazione:
    esattamente ciò che §17.3 vieta. Un UID con una sola occorrenza nella
    finestra è un evento singolo e la sua identità è il solo UID.
    """
    if sum(1 for other in events if other.uid == event.uid) > 1:
        return event.recurrence_id
    return None


def _fill(row: ExternalCalendarEvent, event: IcsEvent) -> bool:
    """Copia i campi dell'evento sulla riga. Ritorna True se qualcosa è cambiato:
    un sync ripetuto sullo stesso feed non deve risultare in una modifica."""
    values = {
        "summary": event.summary,
        "starts_at": event.starts_at,
        "ends_at": event.ends_at,
        "all_day": event.all_day,
        "status": event.status,
        "cancelled": event.cancelled,
    }
    changed = any(_differs(getattr(row, field), value) for field, value in values.items())
    for field, value in values.items():
        setattr(row, field, value)
    return changed


def _differs(current, new) -> bool:
    if isinstance(current, datetime) and isinstance(new, datetime):
        # SQLite rilegge i datetime naive: confronta sull'istante, non sul tzinfo.
        current = current.replace(tzinfo=UTC) if current.tzinfo is None else current
        return current != new
    return current != new


# ---------------------------------------------------------------- reazione al piano

def infeasible_days(session: Session, today: date) -> list[date]:
    """Giorni in cui il piano confermato chiede più minuti di quelli disponibili."""
    capacity = planning.build_capacity(
        session, today, today + timedelta(days=MAX_HORIZON_DAYS)
    )
    planned: dict[date, int] = {}
    for segment in session.scalars(
        select(PlanningSegment).where(PlanningSegment.day >= today)
    ):
        planned[segment.day] = planned.get(segment.day, 0) + segment.minutes
    return sorted(day for day, minutes in planned.items() if minutes > capacity.available(day))


def _pending_calendar_proposal(session: Session) -> PlanningProposal | None:
    return session.scalars(
        select(PlanningProposal).where(
            PlanningProposal.kind == ProposalKind.CALENDAR_CHANGE,
            PlanningProposal.status == ProposalStatus.PENDING,
        )
    ).first()


def _propose_if_infeasible(session: Session, today: date) -> PlanningProposal | None:
    """L'asimmetria di §39/§40 vive qui, ed è intenzionale.

    Il trigger è una sola cosa: il piano confermato non è più materializzabile,
    cioè un giorno ha più minuti pianificati di quelli rimasti. Solo una perdita
    di capacità può renderlo vero, e allora si propone lo shift in avanti a coda
    invariata (§39).

    Capacità *recuperata* — riunione cancellata o spostata altrove — non rende
    nulla infattibile, quindi non arriva qui e non produce nulla: niente
    compattazione, niente riordino, niente proposal di anticipo (§17.4, §40,
    R6). Il piano resta identico e la capacità libera resta visibile finché
    l'utente non chiede esplicitamente di riottimizzare. Non manca del codice:
    la sua assenza È la regola.
    """
    if not infeasible_days(session, today):
        return None
    # Idempotenza: due sync consecutivi sullo stesso feed non devono accumulare
    # proposal identiche. Quella pendente è già la risposta a questa capacità.
    pending = _pending_calendar_proposal(session)
    if pending is not None:
        # Ricalcolata, non duplicata: deve riflettere la capacità di adesso.
        return proposals.recalculate(session, pending.id, today)
    # Intent vuoto: nessun campo del task cambia, cambia solo la capacità già
    # scritta in cache. La simulazione ripianifica la coda invariata sulla nuova
    # capacità, che è esattamente lo shift in avanti di §39.
    return proposals.propose(
        session, ProposalKind.CALENDAR_CHANGE, ProposalOrigin.CALENDAR, {}, today
    )
