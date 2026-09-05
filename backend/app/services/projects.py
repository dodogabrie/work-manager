"""Progetti (§19, §32.4.6).

Un progetto è solo un raggruppamento con un colore: non entra nello scheduler,
quindi nessuna operazione qui passa da una PlanningProposal.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Project

#: §19: il colore serve alla vista calendario; grigio neutro se non specificato.
DEFAULT_COLOR = "#6b7280"


def create(session: Session, name: str, color: str | None = None) -> Project:
    if not name or not name.strip():
        raise ValueError("name is required")
    project = Project(name=name.strip(), color=color or DEFAULT_COLOR)
    session.add(project)
    session.commit()
    return project


def list_projects(session: Session, include_archived: bool = False) -> list[Project]:
    stmt = select(Project).where(Project.deleted_at.is_(None))
    if not include_archived:
        stmt = stmt.where(Project.archived.is_(False))
    return list(session.scalars(stmt.order_by(Project.name)))


def get(session: Session, project_id: uuid.UUID) -> Project:
    """Un progetto soft-deleted resta leggibile: i task che lo referenziano
    devono poter ancora mostrare nome e colore (§23.2)."""
    project = session.get(Project, project_id)
    if project is None:
        raise LookupError(f"project {project_id} not found")
    return project


def update(
    session: Session,
    project_id: uuid.UUID,
    name: str | None = None,
    color: str | None = None,
    archived: bool | None = None,
) -> Project:
    project = get(session, project_id)
    if name is not None:
        if not name.strip():
            raise ValueError("name is required")
        project.name = name.strip()
    if color is not None:
        project.color = color
    if archived is not None:
        project.archived = archived
    session.commit()
    return project


def soft_delete(session: Session, project_id: uuid.UUID) -> Project:
    """§23.2: soft delete. I task collegati restano, con il loro project_id:
    cancellare un progetto non deve cancellare o slegare del lavoro pianificato."""
    project = get(session, project_id)
    project.deleted_at = datetime.now(UTC)
    session.commit()
    return project
