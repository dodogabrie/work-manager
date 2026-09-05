"""Progetti (§25, §32.4.6). Router sottile: parse -> service -> DTO."""

from __future__ import annotations

import uuid

from fastapi import APIRouter

from ..schemas import ProjectIn, ProjectPatchIn, ProjectView
from ..services import projects as service
from .deps import Caller, DbSession

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[ProjectView])
def list_projects(session: DbSession, principal: Caller, include_archived: bool = False):
    return service.list_projects(session, include_archived)


@router.post("", response_model=ProjectView, status_code=201)
def create_project(payload: ProjectIn, session: DbSession, principal: Caller):
    return service.create(session, payload.name, payload.color)


@router.get("/{project_id}", response_model=ProjectView)
def get_project(project_id: uuid.UUID, session: DbSession, principal: Caller):
    return service.get(session, project_id)


@router.patch("/{project_id}", response_model=ProjectView)
def patch_project(
    project_id: uuid.UUID, payload: ProjectPatchIn, session: DbSession, principal: Caller
):
    return service.update(session, project_id, **payload.model_dump(exclude_unset=True))


@router.delete("/{project_id}", response_model=ProjectView)
def delete_project(project_id: uuid.UUID, session: DbSession, principal: Caller):
    return service.soft_delete(session, project_id)
