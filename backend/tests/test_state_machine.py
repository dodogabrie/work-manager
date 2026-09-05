"""La state machine dei task (§7, §32.5) è una tabella di dati: questi test
verificano che sia coerente, non che il codice la ricopi."""

from app.models.enums import (
    ALLOWED_TRANSITIONS,
    TRANSITIONS_REQUIRING_PROPOSAL,
    TaskStatus,
)


def test_every_status_has_an_entry():
    assert set(ALLOWED_TRANSITIONS) == set(TaskStatus)


def test_transitions_only_point_to_real_statuses():
    for source, targets in ALLOWED_TRANSITIONS.items():
        assert targets <= set(TaskStatus), source
        assert source not in targets, f"{source} non deve transire in se stesso"


def test_ready_and_delivered_do_not_require_a_proposal():
    """§11.5: READY è interno, non libera capacità e non sposta la delivery.
    Se una di queste transizioni finisse fra quelle che richiedono proposal,
    marcare un task come pronto ripianificherebbe la settimana."""
    assert (TaskStatus.IN_PROGRESS, TaskStatus.READY) not in TRANSITIONS_REQUIRING_PROPOSAL
    assert (TaskStatus.READY, TaskStatus.DELIVERED) not in TRANSITIONS_REQUIRING_PROPOSAL


def test_planning_a_task_requires_a_proposal():
    """§3.3: far entrare un task nella coda cambia il piano confermato."""
    assert (TaskStatus.INBOX, TaskStatus.PLANNED) in TRANSITIONS_REQUIRING_PROPOSAL


def test_proposal_transitions_are_all_allowed_transitions():
    for source, target in TRANSITIONS_REQUIRING_PROPOSAL:
        assert target in ALLOWED_TRANSITIONS[source], f"{source} -> {target} non è consentita"


def test_inbox_cannot_jump_straight_to_delivered():
    assert TaskStatus.DELIVERED not in ALLOWED_TRANSITIONS[TaskStatus.INBOX]


def test_delivered_can_be_reopened():
    """§32.5 prevede esplicitamente la riapertura di un task."""
    assert TaskStatus.IN_PROGRESS in ALLOWED_TRANSITIONS[TaskStatus.DELIVERED]
