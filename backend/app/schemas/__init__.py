"""DTO di output, uno per superficie applicativa (§5, §27).

§27 è esplicito: la Manager View non deve serializzare il modello Task. Qui i
campi sono elencati uno per uno, così un campo nuovo sul modello non finisce
per sbaglio in una vista pubblica: va aggiunto a mano dove serve.

    TaskInternalView  owner   -> tutto
    TaskClaudeView    API     -> tutto tranne le note private
    TaskManagerView   share   -> progetto, titolo, effort, periodo, delivery, stato pubblico
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..models import PlanningSegment, Task, TaskStatus

ORM = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- task

class _TaskShared(BaseModel):
    """Campi visibili a owner e API. Le note private NON sono qui (§27)."""

    model_config = ORM

    id: uuid.UUID
    title: str
    description: str | None = None
    project_id: uuid.UUID | None = None
    status: TaskStatus
    planning_effort_minutes: int
    proposed_effort_minutes: int | None = None
    proposed_effort_min_minutes: int | None = None
    proposed_effort_max_minutes: int | None = None
    estimate_confidence: str | None = None
    estimate_rationale: str | None = None
    target_delivery_date: date | None = None
    fixed_delivery_date: date | None = None
    queue_position: Decimal | None = None
    ready_at: datetime | None = None
    delivered_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class TaskClaudeView(_TaskShared):
    """§5.3 / §27: come l'internal, senza le note interne — sono private."""


class TaskInternalView(_TaskShared):
    """§5.1: l'owner vede tutto."""

    internal_notes: str | None = None


#: §5.2: il manager non deve vedere lo stato READY interno. READY viene mappato
#: su IN_PROGRESS: dal suo punto di vista il lavoro è in corso finché non è
#: consegnato (§3.2 — pronto internamente e consegnato sono cose diverse).
PUBLIC_STATUS: dict[TaskStatus, str] = {
    TaskStatus.INBOX: "PLANNED",
    TaskStatus.PLANNED: "PLANNED",
    TaskStatus.IN_PROGRESS: "IN_PROGRESS",
    TaskStatus.READY: "IN_PROGRESS",
    TaskStatus.DELIVERED: "DELIVERED",
    TaskStatus.BLOCKED: "BLOCKED",
    TaskStatus.CANCELLED: "CANCELLED",
    TaskStatus.ARCHIVED: "ARCHIVED",
}


class TaskManagerView(BaseModel):
    """§5.2: progetto, titolo, effort pianificato, periodo, delivery, stato pubblico.

    Nessun campo interno: niente note, niente ready_at, niente stima proposta,
    niente id di integrazione.
    """

    id: uuid.UUID
    title: str
    project: str | None = None
    project_color: str | None = None
    planned_effort_minutes: int
    allocation_start: date | None = None
    allocation_end: date | None = None
    delivery_date: date | None = None
    status: str

    @classmethod
    def of(cls, task: Task, segments: list[PlanningSegment]) -> TaskManagerView:
        days = sorted(s.day for s in segments)
        return cls(
            id=task.id,
            title=task.title,
            project=task.project.name if task.project else None,
            project_color=task.project.color if task.project else None,
            planned_effort_minutes=task.planning_effort_minutes,
            allocation_start=days[0] if days else None,
            allocation_end=days[-1] if days else None,
            delivery_date=days[-1] if days else None,
            status=PUBLIC_STATUS[TaskStatus(task.status)],
        )


# ---------------------------------------------------------------- input

class QuickAddIn(BaseModel):
    """§6.2: unico campo obbligatorio, il titolo."""

    title: str
    project_id: uuid.UUID | None = None
    description: str | None = None
    planning_effort_minutes: int = Field(default=0, ge=0)
    target_delivery_date: date | None = None
    fixed_delivery_date: date | None = None
    internal_notes: str | None = None


class TaskPatchIn(BaseModel):
    """Solo i campi che non toccano il piano. L'effort passa da /effort/change (§15.3)."""

    title: str | None = None
    description: str | None = None
    project_id: uuid.UUID | None = None
    target_delivery_date: date | None = None
    fixed_delivery_date: date | None = None
    internal_notes: str | None = None
    planning_effort_minutes: int | None = Field(default=None, ge=0)


class EffortProposalIn(BaseModel):
    """§15.1: la stima di Claude non è ancora l'effort pianificato."""

    minutes: int = Field(ge=0)
    min_minutes: int | None = Field(default=None, ge=0)
    max_minutes: int | None = Field(default=None, ge=0)
    confidence: str | None = None
    rationale: str | None = None


class EffortChangeIn(BaseModel):
    minutes: int = Field(ge=0)


class StatusChangeIn(BaseModel):
    status: TaskStatus


class MoveIn(BaseModel):
    """§14: il drag & drop esprime dove il task finisce fra due vicini."""

    before_id: uuid.UUID | None = None
    after_id: uuid.UUID | None = None


class CompleteIn(BaseModel):
    actual_minutes: int | None = Field(default=None, ge=0)


class LoginIn(BaseModel):
    password: str


class SimulateIn(BaseModel):
    """Intent nella forma normalizzata di services.proposals."""

    tasks: dict[str, dict[str, Any]] = Field(default_factory=dict)
    capacity: dict[str, int | None] = Field(default_factory=dict)
    completed: dict[str, int | None] = Field(default_factory=dict)


class CapacityExceptionIn(BaseModel):
    day: date
    minutes: int = Field(ge=0)
    kind: str = "LEAVE"
    note: str | None = None


class CapacityExceptionPatchIn(BaseModel):
    minutes: int = Field(ge=0)
    kind: str | None = None
    note: str | None = None


HEX_COLOR = r"^#[0-9a-fA-F]{6}$"


class ProjectIn(BaseModel):
    name: str
    color: str | None = Field(default=None, pattern=HEX_COLOR)


class ProjectPatchIn(BaseModel):
    name: str | None = None
    color: str | None = Field(default=None, pattern=HEX_COLOR)
    archived: bool | None = None


class ShareLinkIn(BaseModel):
    label: str
    kind: Literal["manager", "ics"] = "manager"
    expires_at: datetime | None = None


class ApiTokenIn(BaseModel):
    label: str
    scopes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- piano

class ProjectView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    name: str
    color: str
    archived: bool


class PlanningSegmentView(BaseModel):
    model_config = ORM

    task_id: uuid.UUID
    day: date
    minutes: int
    locked: bool


class DayCapacityView(BaseModel):
    day: date
    available_minutes: int
    planned_minutes: int


class SimulationView(BaseModel):
    """§44: la forma che una proposal deve esporre."""

    segments: list[dict[str, Any]] = Field(default_factory=list)
    delivery_dates: dict[str, str] = Field(default_factory=dict)
    changes: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    reasons: list[dict[str, Any]] = Field(default_factory=list)


class ProposalView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    kind: str
    origin: str
    originator: str | None = None
    status: str
    base_plan_version: int
    intent: dict[str, Any]
    simulation: SimulationView
    created_at: datetime
    resolved_at: datetime | None = None


class TaskOrProposal(BaseModel):
    """Un'operazione che tocca il piano restituisce una proposal, non un task (§3.3)."""

    task: TaskInternalView | None = None
    proposal: ProposalView | None = None


class CalendarConnectionIn(BaseModel):
    """§32.18: un feed ICS è solo un URL sottoscritto, nessun OAuth."""

    name: str
    ics_url: str
    enabled: bool = True


class CalendarConnectionPatchIn(BaseModel):
    name: str | None = None
    ics_url: str | None = None
    enabled: bool | None = None


class CalendarConnectionView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    name: str
    ics_url: str
    enabled: bool
    last_synced_at: datetime | None = None
    last_sync_error: str | None = None
    created_at: datetime


class SyncResultView(BaseModel):
    """Esito di un sync: cosa è cambiato nel calendario e se ha prodotto una proposal."""

    connection: CalendarConnectionView
    events_upserted: int = 0
    events_cancelled: int = 0
    proposal: ProposalView | None = None


class PlanningView(BaseModel):
    plan_version: int
    tasks: list[TaskInternalView | TaskClaudeView]
    segments: list[PlanningSegmentView]
    days: list[DayCapacityView]


class PlanningContextView(BaseModel):
    """§16.1: contesto compatto per un LLM. Poche liste, nessun campo ridondante."""

    today: date
    plan_version: int
    projects: list[ProjectView]
    inbox: list[TaskClaudeView]
    queue: list[TaskClaudeView]
    segments: list[PlanningSegmentView]
    capacity: list[DayCapacityView]
    pending_proposals: list[ProposalView]
    constraints: list[str]


class CapacityView(BaseModel):
    weekly_minutes: dict[int, int]
    exceptions: list[CapacityExceptionView]
    days: list[DayCapacityView]


class CapacityExceptionView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    day: date
    minutes: int
    kind: str
    note: str | None = None


class ExceptionOrProposal(BaseModel):
    exception: CapacityExceptionView | None = None
    proposal: ProposalView | None = None


class SnapshotView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    plan_version: int
    created_at: datetime
    note: str | None = None


class SnapshotDetailView(SnapshotView):
    payload: dict[str, Any]


class ActionView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    action_type: str
    origin: str
    actor: str | None = None
    created_at: datetime
    entities: dict[str, Any]
    reversible: bool
    undone: bool
    inverse_of_id: uuid.UUID | None = None
    snapshot_id: uuid.UUID | None = None


class UndoView(BaseModel):
    """§23.4: l'undo può riuscire, richiedere una proposal, o essere impossibile."""

    status: Literal["applied", "proposal", "conflict", "impossible"]
    message: str = ""
    action: ActionView | None = None
    proposal: ProposalView | None = None


class ShareLinkView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    label: str
    kind: str
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    last_accessed_at: datetime | None = None
    created_at: datetime


class ShareLinkCreatedView(ShareLinkView):
    """Il token in chiaro compare qui e mai più: in DB c'è solo l'hash (§28)."""

    token: str
    url: str


class ApiTokenView(BaseModel):
    model_config = ORM

    id: uuid.UUID
    label: str
    scopes: list[str]
    revoked_at: datetime | None = None
    last_used_at: datetime | None = None
    created_at: datetime


class ApiTokenCreatedView(ApiTokenView):
    token: str


class SessionView(BaseModel):
    subject: str


CapacityView.model_rebuild()
