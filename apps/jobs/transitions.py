"""
Job status transitions for ``GET /jobs/{id}/transitions/``.

Response shape matches bookings: ``allowed_transitions`` + ``transitions``
(``name``, ``target``, ``description``).
"""
from __future__ import annotations

from .models import JobStatus

JOB_ALLOWED_NEXT: dict[str, frozenset[str]] = {
    JobStatus.OPEN: frozenset({JobStatus.ASSIGNED, JobStatus.CANCELLED}),
    JobStatus.ASSIGNED: frozenset(
        {JobStatus.IN_PROGRESS, JobStatus.OPEN, JobStatus.CANCELLED}
    ),
    JobStatus.IN_PROGRESS: frozenset({JobStatus.COMPLETED, JobStatus.CANCELLED}),
    JobStatus.COMPLETED: frozenset(),
    JobStatus.CANCELLED: frozenset(),
}


def transitions_payload_for_status(current: str) -> dict:
    allowed_set = JOB_ALLOWED_NEXT.get(current, frozenset())
    allowed_list = sorted(allowed_set)

    if current == JobStatus.OPEN:
        candidates = [
            {
                "name": "claim",
                "target": JobStatus.ASSIGNED,
                "description": "Claim this job (technician) — POST …/claim/",
            },
            {
                "name": "assign",
                "target": JobStatus.ASSIGNED,
                "description": "Assign a technician (operator) — PATCH job with assigned_to / status",
            },
            {
                "name": "cancel",
                "target": JobStatus.CANCELLED,
                "description": "Cancel job — PATCH status to cancelled (workspace staff)",
            },
        ]
    elif current == JobStatus.ASSIGNED:
        candidates = [
            {
                "name": "start",
                "target": JobStatus.IN_PROGRESS,
                "description": "Start work — POST …/start/ (assigned technician)",
            },
            {
                "name": "release",
                "target": JobStatus.OPEN,
                "description": "Release claim — POST …/release/ (assigned technician)",
            },
            {
                "name": "cancel",
                "target": JobStatus.CANCELLED,
                "description": "Cancel job — PATCH status to cancelled (workspace staff)",
            },
        ]
    elif current == JobStatus.IN_PROGRESS:
        candidates = [
            {
                "name": "complete",
                "target": JobStatus.COMPLETED,
                "description": "Mark completed — POST …/complete/ (assigned technician)",
            },
            {
                "name": "cancel",
                "target": JobStatus.CANCELLED,
                "description": "Cancel job — PATCH status to cancelled (workspace staff)",
            },
        ]
    else:
        candidates = []

    transitions = [t for t in candidates if t["target"] in allowed_set]
    return {
        "allowed_transitions": allowed_list,
        "transitions": transitions,
    }
