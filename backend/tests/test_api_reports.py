"""Report PDF/PNG (§20, §21, §27).

Due cose contano qui e nessuna richiede un browser:
  - l'HTML del report contiene quello che §20/§21 chiedono;
  - non contiene niente di owner-only, controllato sul testo grezzo come in
    test_api_privacy.py.

La conversione in PDF/PNG è l'unica parte che dipende da Playwright ed è
isolata in `render_file`: qui viene sostituita.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select

from app import reports
from app.models import PlanningProposal, Report
from app.reports.render import RendererUnavailableError

from .conftest import API_MON

#: Come in test_api_privacy.py: campi che non devono uscire dall'owner app (§27).
OWNER_ONLY_FIELDS = (
    "internal_notes",
    "ready_at",
    "queue_position",
    "estimate_rationale",
    "proposed_effort_minutes",
    "token_hash",
    "READY",
)

SECRETS = {
    "internal_notes": "non deve finire in un report",
    "description": "dettaglio tecnico interno",
    "estimate_rationale": "stima interna, non condivisibile",
}


@pytest.fixture
def planned(owner):
    """Un task pianificato e approvato, con tutti i campi interni valorizzati."""
    project = owner.post("/api/projects", json={"name": "MAG", "color": "#2f6f4f"}).json()
    task = owner.post("/api/inbox/quick-add", json={
        "title": "Fix MAG import",
        "project_id": project["id"],
        "planning_effort_minutes": 600,
        **SECRETS,
    }).json()
    owner.post(f"/api/tasks/{task['id']}/effort/propose", json={
        "minutes": 600, "min_minutes": 480, "max_minutes": 720,
        "confidence": "low", "rationale": SECRETS["estimate_rationale"],
    })
    proposal = owner.post(
        f"/api/tasks/{task['id']}/status", json={"status": "PLANNED"}
    ).json()["proposal"]
    owner.post(f"/api/proposals/{proposal['id']}/approve")
    owner.post(f"/api/tasks/{task['id']}/status", json={"status": "IN_PROGRESS"})
    # §5.2: READY è interno. Se trapelasse, trapelerebbe da qui.
    owner.post(f"/api/tasks/{task['id']}/status", json={"status": "READY"})
    return task


@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    """I test non devono dipendere dal browser: la conversione è sostituita.
    I file finiscono in una directory temporanea, non nel repo."""
    from app.config import settings

    monkeypatch.setattr(settings, "reports_dir", str(tmp_path))
    monkeypatch.setattr(
        reports, "render_file",
        lambda html, fmt: b"%PDF-fake" if fmt == "pdf" else b"\x89PNG-fake",
    )
    return tmp_path


# ---------------------------------------------------------------- HTML, senza browser

def test_planning_report_html_shows_what_section_20_requires(session, client, planned):
    context = reports.planning_context(
        session, API_MON, API_MON + timedelta(days=13),
        notes="Consegna prevista a fine mese.",
    )
    html = reports.render_html(context)

    assert "Fix MAG import" in html
    assert "MAG" in html
    assert "10h" in html                      # 600 minuti di effort pianificato (§20)
    assert "Consegna prevista" in html
    assert "Timeline" in html
    assert "Capacità" in html
    assert "Consegna prevista a fine mese." in html  # note pubbliche (§20)


def test_planning_report_html_never_contains_owner_only_data(session, client, planned):
    context = reports.planning_context(session, API_MON, API_MON)
    html = reports.render_html(context)

    for field in OWNER_ONLY_FIELDS:
        assert field not in html, f"{field} è owner-only (§27)"
    for secret in SECRETS.values():
        assert secret not in html


def test_impact_report_html_shows_before_request_after_and_effects(session, client, planned):
    # Una seconda attività davanti alla prima: la coda si sposta (§21).
    urgent = client.post("/api/inbox/quick-add", json={
        "title": "Urgenza cliente", "planning_effort_minutes": 480,
    }).json()
    proposal_id = client.post(
        f"/api/tasks/{urgent['id']}/status", json={"status": "PLANNED"}
    ).json()["proposal"]["id"]
    proposal = session.get(PlanningProposal, uuid.UUID(proposal_id))

    html = reports.render_html(reports.impact_context(session, proposal))

    assert "La richiesta" in html
    assert "Nuova attività da pianificare" in html
    assert "Effetti" in html
    assert "Urgenza cliente" in html
    for field in OWNER_ONLY_FIELDS:
        assert field not in html, f"{field} è owner-only (§27)"


def test_impact_report_html_never_contains_owner_only_data(session, client, planned):
    proposal = session.scalars(select(PlanningProposal)).first()

    html = reports.render_html(reports.impact_context(session, proposal))

    for secret in SECRETS.values():
        assert secret not in html


# ---------------------------------------------------------------- endpoint

def test_reports_require_authentication(client):
    """§25: i report sono superficie owner, non pubblica."""
    assert client.post("/api/reports/planning", json={}).status_code == 401
    assert client.post(
        "/api/reports/impact", json={"proposal_id": "00000000-0000-0000-0000-000000000000"}
    ).status_code == 401


def test_planning_report_returns_the_file_and_stores_its_metadata(
    owner, session, planned, fake_render
):
    response = owner.post("/api/reports/planning", json={"format": "png"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == b"\x89PNG-fake"
    row = session.scalars(select(Report)).one()
    assert (row.kind, row.fmt) == ("planning", "png")
    assert row.path.endswith(".png")
    assert (fake_render / row.path.rsplit("/", 1)[-1]).read_bytes() == response.content


def test_impact_report_needs_an_existing_proposal(owner, fake_render):
    response = owner.post(
        "/api/reports/impact",
        json={"proposal_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404


def test_a_missing_browser_answers_503_not_a_crash(owner, planned, monkeypatch):
    """§20: Playwright è opzionale a runtime."""
    def boom(html: str, fmt: str) -> bytes:
        raise RendererUnavailableError("browser non installato")

    monkeypatch.setattr(reports, "render_file", boom)

    response = owner.post("/api/reports/planning", json={})

    assert response.status_code == 503
    assert "non disponibile" in response.json()["detail"]


def test_an_invalid_interval_is_rejected(owner):
    response = owner.post(
        "/api/reports/planning",
        json={"start": "2026-02-10", "end": "2026-02-01"},
    )
    assert response.status_code == 422
