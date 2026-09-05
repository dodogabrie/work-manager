"""Enumerazioni di dominio persistite. I valori sono stringhe stabili: finiscono
negli snapshot JSON e nella history, quindi rinominarli romperebbe la storia."""

from enum import StrEnum


class TaskStatus(StrEnum):
    INBOX = "INBOX"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    DELIVERED = "DELIVERED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    ARCHIVED = "ARCHIVED"


#: §7 + §32.5. READY è interno: entrarci non tocca la pianificazione (§11.5).
ALLOWED_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.INBOX: frozenset({TaskStatus.PLANNED, TaskStatus.CANCELLED, TaskStatus.ARCHIVED}),
    TaskStatus.PLANNED: frozenset(
        {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.READY,
         TaskStatus.CANCELLED, TaskStatus.ARCHIVED, TaskStatus.INBOX}
    ),
    TaskStatus.IN_PROGRESS: frozenset(
        {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.PLANNED,
         TaskStatus.CANCELLED, TaskStatus.ARCHIVED}
    ),
    TaskStatus.READY: frozenset(
        {TaskStatus.DELIVERED, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.CANCELLED}
    ),
    TaskStatus.DELIVERED: frozenset({TaskStatus.IN_PROGRESS, TaskStatus.ARCHIVED}),
    TaskStatus.BLOCKED: frozenset(
        {TaskStatus.PLANNED, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED, TaskStatus.ARCHIVED}
    ),
    TaskStatus.CANCELLED: frozenset({TaskStatus.ARCHIVED, TaskStatus.INBOX}),
    TaskStatus.ARCHIVED: frozenset({TaskStatus.INBOX}),
}

#: Transizioni che cambiano la capacità pianificata e quindi passano da una
#: PlanningProposal (§3.3). READY e DELIVERED non ci sono, di proposito: §11.5
#: dice che marcare un task come pronto non tocca il piano.
#: Derivato da ALLOWED_TRANSITIONS, così non può contenere transizioni inesistenti.
def _requires_proposal(source: TaskStatus, target: TaskStatus) -> bool:
    if target in (TaskStatus.READY, TaskStatus.DELIVERED):
        return False
    # entrare nella coda, uscirne, o rientrarci: tutte cambiano la capacità allocata
    return target in (
        TaskStatus.PLANNED,
        TaskStatus.IN_PROGRESS,
        TaskStatus.CANCELLED,
        TaskStatus.BLOCKED,
        TaskStatus.ARCHIVED,
    )


TRANSITIONS_REQUIRING_PROPOSAL: frozenset[tuple[TaskStatus, TaskStatus]] = frozenset(
    (source, target)
    for source, targets in ALLOWED_TRANSITIONS.items()
    for target in targets
    if _requires_proposal(source, target)
)


class ProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    STALE = "stale"
    APPLIED = "applied"


class ProposalOrigin(StrEnum):
    UI = "UI"
    API = "API"          # Claude e altri client REST
    CALENDAR = "CALENDAR"
    SYSTEM = "SYSTEM"


class ProposalKind(StrEnum):
    TASK_PLANNED = "TASK_PLANNED"
    QUEUE_REORDER = "QUEUE_REORDER"
    EFFORT_CHANGE = "EFFORT_CHANGE"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_CANCELLED = "TASK_CANCELLED"
    CAPACITY_CHANGE = "CAPACITY_CHANGE"
    CALENDAR_CHANGE = "CALENDAR_CHANGE"
    UNDO = "UNDO"
    REDO = "REDO"


class CalendarEventStatus(StrEnum):
    """§17.5: accettato e provvisorio occupano capacità, rifiutato no."""

    ACCEPTED = "ACCEPTED"
    TENTATIVE = "TENTATIVE"
    DECLINED = "DECLINED"


class ExceptionKind(StrEnum):
    VACATION = "VACATION"
    LEAVE = "LEAVE"
    REDUCED = "REDUCED"
    EXTRA = "EXTRA"
