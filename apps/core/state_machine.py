from __future__ import annotations

from typing import Any


class _TechnicianOnboardingMachine:
    """Valid onboarding_status transitions for ``TechnicianProfile``."""

    ALLOWED = frozenset(
        {
            ("pending_onboarding", "submitted"),
            ("submitted", "active"),
            ("submitted", "pending_onboarding"),
            ("submitted", "suspended"),
            ("active", "suspended"),
            ("suspended", "active"),
        }
    )

    def validate_transition(
        self,
        *,
        from_state: Any,
        to_state: Any,
        entity_id: str | None = None,
    ) -> None:
        from rest_framework.exceptions import ValidationError

        def _norm(v: Any) -> str:
            if hasattr(v, "value"):
                return str(v.value)
            return str(v)

        f, t = _norm(from_state), _norm(to_state)
        if (f, t) in self.ALLOWED:
            return
        raise ValidationError(
            {
                "error": {
                    "code": "invalid_onboarding_transition",
                    "message": f"Cannot move technician onboarding from {f!r} to {t!r}.",
                    "from_state": f,
                    "to_state": t,
                    "entity_id": entity_id,
                }
            }
        )


_REGISTRY: dict[str, Any] = {
    "technician_onboarding": _TechnicianOnboardingMachine(),
}


def get_state_machine(name: str):
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise NotImplementedError(f"State machine {name!r} is not configured") from exc
