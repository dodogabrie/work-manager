"""Entità persistite (§24).

Nota di lettura: i PlanningSegment sono derivati — sono il risultato materializzato
dello scheduler, riscritti a ogni applicazione di proposal. La fonte di verità
dell'ordine è Task.queue_position; la fonte di verità della storia è
PlanningSnapshot + Action.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin
from .enums import (
    CalendarEventStatus, ExceptionKind, ProposalKind, ProposalOrigin, ProposalStatus, TaskStatus,
)

#: JSONB su Postgres, JSON altrove: i test girano su SQLite in memoria senza Docker.
JsonDoc = JSON().with_variant(JSONB, "postgresql")


class User(Base, TimestampMixin):
    """Owner singolo (§5.1). Password argon2, mai in chiaro."""

    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))


class Project(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    color: Mapped[str] = mapped_column(String(7), default="#6b7280")  # §19: colore del progetto
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    tasks: Mapped[list[Task]] = relationship(back_populates="project")


class Task(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[TaskStatus] = mapped_column(String(20), default=TaskStatus.INBOX)

    #: Effort usato dallo scheduler (§15.3). Sempre in minuti (§11.1).
    planning_effort_minutes: Mapped[int] = mapped_column(Integer, default=0)
    #: Stima proposta da Claude, in attesa di conferma (§15.1). Non usata dallo scheduler.
    proposed_effort_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    proposed_effort_min_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    proposed_effort_max_minutes: Mapped[int | None] = mapped_column(Integer, default=None)
    estimate_confidence: Mapped[str | None] = mapped_column(String(20), default=None)
    estimate_rationale: Mapped[str | None] = mapped_column(Text, default=None)

    target_delivery_date: Mapped[date | None] = mapped_column(Date, default=None)  # soft, §10
    fixed_delivery_date: Mapped[date | None] = mapped_column(Date, default=None)   # hard, §10

    #: §8: la posizione in coda È la priorità. Frazionaria perché il drag & drop
    #: è l'operazione più frequente: inserire fra due vicini è una sola UPDATE
    #: (la media dei due valori) invece di rinumerare l'intera coda.
    queue_position: Mapped[Decimal | None] = mapped_column(Numeric(20, 10), default=None)

    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    internal_notes: Mapped[str | None] = mapped_column(Text, default=None)  # owner-only, §27

    project: Mapped[Project | None] = relationship(back_populates="tasks")
    segments: Mapped[list[PlanningSegment]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_tasks_queue", "queue_position"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_deleted_at", "deleted_at"),
    )


class PlanningSegment(Base):
    """Allocazione di una porzione di effort su un giorno (§6.4).

    Derivato dallo scheduler, non modificabile a mano: un resize grafico è una
    modifica dell'effort e passa da proposal (§14.3).
    """

    __tablename__ = "planning_segments"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer)
    #: §32.2.8: un segmento locked consuma capacità e non viene mosso da una
    #: ri-simulazione; il resto della coda ci scorre intorno.
    locked: Mapped[bool] = mapped_column(Boolean, default=False)

    task: Mapped[Task] = relationship(back_populates="segments")

    __table_args__ = (Index("ix_segments_day", "day"), Index("ix_segments_task", "task_id"))


class WeeklyCapacity(Base, TimestampMixin):
    """Capacità standard settimanale (§11.2). Una riga per giorno della settimana."""

    __tablename__ = "weekly_capacity"
    weekday: Mapped[int] = mapped_column(Integer, primary_key=True)  # 0=lunedì
    minutes: Mapped[int] = mapped_column(Integer, default=480)


class CapacityException(Base, TimestampMixin, SoftDeleteMixin):
    """Ferie, permessi, giornate ridotte (§11.3). Non sono task."""

    __tablename__ = "capacity_exceptions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    day: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer)  # capacità totale del giorno, non un delta
    kind: Mapped[ExceptionKind] = mapped_column(String(20), default=ExceptionKind.LEAVE)
    note: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (UniqueConstraint("day", name="uq_capacity_exception_day"),)


class ExternalCalendarConnection(Base, TimestampMixin, SoftDeleteMixin):
    """Feed ICS in ingresso (§17, §18). Nessun OAuth: solo un URL sottoscritto."""

    __tablename__ = "external_calendar_connections"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    ics_url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_sync_error: Mapped[str | None] = mapped_column(Text, default=None)


class ExternalCalendarEvent(Base, TimestampMixin):
    """Cache degli eventi esterni rilevanti (§24). Riducono la capacità, non sono task (§17.1)."""

    __tablename__ = "external_calendar_events"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("external_calendar_connections.id", ondelete="CASCADE")
    )
    uid: Mapped[str] = mapped_column(String(500))          # UID iCalendar
    recurrence_id: Mapped[str | None] = mapped_column(String(100), default=None)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[CalendarEventStatus] = mapped_column(
        String(20), default=CalendarEventStatus.ACCEPTED
    )
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        UniqueConstraint("connection_id", "uid", "recurrence_id", name="uq_calendar_event"),
        Index("ix_calendar_events_span", "starts_at", "ends_at"),
    )


class PlanState(Base):
    """Riga singleton che porta la versione corrente del piano (§26).

    È l'ancora del controllo di concorrenza: l'approvazione di una proposal fa
    SELECT ... FOR UPDATE su questa riga, poi confronta base_plan_version.
    """

    __tablename__ = "plan_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class PlanningSnapshot(Base):
    """Copia immutabile e COMPLETA del piano (§22), non un diff."""

    __tablename__ = "planning_snapshots"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_version: Mapped[int] = mapped_column(Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JsonDoc)
    note: Mapped[str | None] = mapped_column(Text, default=None)

    __table_args__ = (Index("ix_snapshots_version", "plan_version"),)


class PlanningProposal(Base, TimestampMixin):
    """Modifica proposta e non ancora applicata (§12)."""

    __tablename__ = "planning_proposals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[ProposalKind] = mapped_column(String(30))
    origin: Mapped[ProposalOrigin] = mapped_column(String(20))
    originator: Mapped[str | None] = mapped_column(String(200), default=None)
    status: Mapped[ProposalStatus] = mapped_column(String(20), default=ProposalStatus.PENDING)

    #: §12.1: se il piano cambia nel frattempo la proposal diventa STALE.
    base_plan_version: Mapped[int] = mapped_column(Integer)

    intent: Mapped[dict] = mapped_column(JsonDoc)        # il cambiamento richiesto
    simulation: Mapped[dict] = mapped_column(JsonDoc)    # changes/warnings/conflicts/reasons (§44)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    __table_args__ = (Index("ix_proposals_status", "status"),)


class Action(Base):
    """Audit log e base per undo/redo (§23.1)."""

    __tablename__ = "actions"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    action_type: Mapped[str] = mapped_column(String(50))
    origin: Mapped[ProposalOrigin] = mapped_column(String(20))
    actor: Mapped[str | None] = mapped_column(String(200), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entities: Mapped[dict] = mapped_column(JsonDoc, default=dict)
    before: Mapped[dict | None] = mapped_column(JsonDoc, default=None)
    after: Mapped[dict | None] = mapped_column(JsonDoc, default=None)
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("planning_snapshots.id"), default=None
    )
    reversible: Mapped[bool] = mapped_column(Boolean, default=True)
    #: §23.3: l'undo non cancella l'azione originale, ne crea una che la referenzia.
    inverse_of_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("actions.id"), default=None)
    undone: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_actions_created", "created_at"),)


class ManagerShareLink(Base, TimestampMixin):
    """Link read-only revocabile (§5.2). Il token è salvato solo hashato."""

    __tablename__ = "manager_share_links"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(200))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    #: distingue il link della Manager View dal feed ICS in uscita (§18)
    kind: Mapped[str] = mapped_column(String(20), default="manager")


class ApiToken(Base, TimestampMixin):
    """Token per Claude e altri client REST (§5.3). Salvato hashato, mostrato una volta."""

    __tablename__ = "api_tokens"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(String(200))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    scopes: Mapped[list] = mapped_column(JsonDoc, default=list)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)


class Report(Base):
    """Metadati dei report generati (§20, §21)."""

    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(20))  # planning | impact
    fmt: Mapped[str] = mapped_column(String(10))   # pdf | png
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    path: Mapped[str] = mapped_column(Text)
    params: Mapped[dict] = mapped_column(JsonDoc, default=dict)
