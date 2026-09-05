"""Pure data structures of the planning domain (§24, §32.2).

No infrastructure: these are plain frozen dataclasses so the scheduler can be
imported and tested without a database, a web framework or a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


class TaskStatus(str, Enum):
    INBOX = "INBOX"
    PLANNED = "PLANNED"
    IN_PROGRESS = "IN_PROGRESS"
    READY = "READY"
    DELIVERED = "DELIVERED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class ReasonType(str, Enum):
    CAPACITY_REDUCED = "CAPACITY_REDUCED"
    TARGET_MISSED = "TARGET_MISSED"
    FIXED_DATE_CONFLICT = "FIXED_DATE_CONFLICT"
    USER_REORDER = "USER_REORDER"
    CALENDAR_EVENT = "CALENDAR_EVENT"
    EFFORT_INCREASE = "EFFORT_INCREASE"
    TASK_COMPLETED = "TASK_COMPLETED"
    QUEUE_COMPACTION = "QUEUE_COMPACTION"
    UNSCHEDULABLE = "UNSCHEDULABLE"


@dataclass(frozen=True, slots=True)
class QueueItem:
    """A task as seen by the scheduler.

    `effort_minutes` is the effort still to be placed: minutes already frozen in
    locked segments are not part of it.
    """

    task_id: str
    title: str
    effort_minutes: int
    queue_position: Decimal
    created_at: datetime
    target_date: date | None = None
    fixed_date: date | None = None
    status: TaskStatus = TaskStatus.PLANNED
    project_id: str | None = None


@dataclass(frozen=True, slots=True)
class PlanningSegment:
    task_id: str
    date: date
    minutes: int
    locked: bool = False


@dataclass(frozen=True, slots=True)
class PlanningReason:
    type: ReasonType
    severity: str  # "info" | "warning" | "conflict"
    message: str
    task_id: str | None = None
    related_task_id: str | None = None
    date: date | None = None
    minutes: int | None = None


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    segments: tuple[PlanningSegment, ...]
    delivery_dates: dict[str, date]
    reasons: tuple[PlanningReason, ...] = field(default_factory=tuple)

    @property
    def warnings(self) -> tuple[PlanningReason, ...]:
        return tuple(r for r in self.reasons if r.severity == "warning")

    @property
    def conflicts(self) -> tuple[PlanningReason, ...]:
        return tuple(r for r in self.reasons if r.severity == "conflict")

    @property
    def has_conflicts(self) -> bool:
        return any(r.severity == "conflict" for r in self.reasons)
