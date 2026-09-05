"""§26: due superfici (UI, Claude, sync calendario) agiscono contemporaneamente.

Il controllo è `proposal.base_plan_version == plan_state.version`, verificato
dopo il lock di riga su PlanState: chi arriva secondo trova la proposal STALE.
"""

from __future__ import annotations

import pytest

from app.models import PlanningSegment, PlanningSnapshot, ProposalStatus, TaskStatus
from app.services import planning, proposals, tasks

from .conftest import MON


def test_double_approval_of_the_same_proposal_one_wins_one_is_stale(sessions):
    with sessions() as setup:
        task = tasks.quick_add(setup, "A", planning_effort_minutes=480)
        proposal_id = tasks.change_status(
            setup, task.id, TaskStatus.PLANNED, horizon_start=MON
        ).id
        setup.commit()

    # Le due sessioni leggono la stessa proposal PENDING sulla stessa versione,
    # poi provano ad applicarla: è la corsa reale fra UI e Claude.
    with sessions() as winner, sessions() as loser:
        loaded = loser.get(proposals.PlanningProposal, proposal_id)  # va tenuto vivo:
        assert loaded.status == ProposalStatus.PENDING  # l'identity map è debole

        snapshot = proposals.approve(winner, proposal_id)
        assert snapshot.plan_version == 1

        with pytest.raises(proposals.StaleProposalError):
            proposals.approve(loser, proposal_id)

    with sessions() as check:
        assert check.get(type(snapshot), snapshot.id) is not None
        assert planning.plan_version(check) == 1
        assert check.query(PlanningSnapshot).count() == 1
        assert check.query(PlanningSegment).count() == 1
        proposal = check.get(proposals.PlanningProposal, proposal_id)
        assert proposal.status == ProposalStatus.STALE


def test_proposal_computed_on_v1_is_stale_once_the_plan_reaches_v2(sessions):
    with sessions() as setup:
        first = tasks.quick_add(setup, "A", planning_effort_minutes=480)
        proposals.approve(
            setup,
            tasks.change_status(setup, first.id, TaskStatus.PLANNED, horizon_start=MON).id,
        )
        assert planning.plan_version(setup) == 1

        second = tasks.quick_add(setup, "B", planning_effort_minutes=480)
        stale = tasks.change_status(setup, second.id, TaskStatus.PLANNED, horizon_start=MON)
        assert stale.base_plan_version == 1

        third = tasks.quick_add(setup, "C", planning_effort_minutes=480)
        proposals.approve(
            setup,
            tasks.change_status(setup, third.id, TaskStatus.PLANNED, horizon_start=MON).id,
        )
        assert planning.plan_version(setup) == 2
        stale_id = stale.id
        setup.commit()

    with sessions() as approver:
        with pytest.raises(proposals.StaleProposalError):
            proposals.approve(approver, stale_id)
        assert approver.get(proposals.PlanningProposal, stale_id).status == ProposalStatus.STALE
        assert planning.plan_version(approver) == 2


def test_a_stale_proposal_is_approvable_again_after_recalculation(sessions):
    with sessions() as setup:
        first = tasks.quick_add(setup, "A", planning_effort_minutes=480)
        stale = tasks.change_status(setup, first.id, TaskStatus.PLANNED, horizon_start=MON)
        second = tasks.quick_add(setup, "B", planning_effort_minutes=480)
        proposals.approve(
            setup,
            tasks.change_status(setup, second.id, TaskStatus.PLANNED, horizon_start=MON).id,
        )
        stale_id = stale.id
        setup.commit()

    with sessions() as session:
        with pytest.raises(proposals.StaleProposalError):
            proposals.approve(session, stale_id)

        recalculated = proposals.recalculate(session, stale_id, MON)
        assert recalculated.status == ProposalStatus.PENDING
        assert recalculated.base_plan_version == 1

        proposals.approve(session, stale_id)
        assert planning.plan_version(session) == 2
        # A entra in coda dietro B (R3): due giorni consecutivi, ordine invariato.
        assert [s.minutes for s in session.query(PlanningSegment).order_by("day")] == [480, 480]
