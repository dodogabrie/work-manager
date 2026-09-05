"""Report PDF/PNG (§20, §21): dati -> HTML -> file, con metadati in tabella."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..models import Report
from .data import impact_context, planning_context
from .render import MEDIA_TYPES, Format, RendererUnavailableError, render_file, render_html

__all__ = [
    "MEDIA_TYPES",
    "Format",
    "RendererUnavailableError",
    "generate",
    "impact_context",
    "planning_context",
    "render_file",
    "render_html",
]


def generate(
    session: Session, context: dict[str, Any], fmt: Format, params: dict[str, Any]
) -> tuple[bytes, str]:
    """Rende il report e ne persiste i metadati (§20: i report sono tracciati).

    Il file resta su disco: un report è un allegato, non un contenuto effimero,
    e il record in tabella senza il file non servirebbe a nulla.
    """
    content = render_file(render_html(context), fmt)
    created_at = datetime.now(UTC)
    name = f"{context['kind']}-{created_at:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}.{fmt}"
    path = Path(settings.reports_dir) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    session.add(Report(
        kind=context["kind"], fmt=fmt, created_at=created_at,
        path=str(path), params=params,
    ))
    session.commit()
    return content, name
