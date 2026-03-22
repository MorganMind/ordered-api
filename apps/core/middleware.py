"""
Request context for tenant / user (optional).

Wire into MIDDLEWARE when you have auth that sets tenant on the user.
Until then, helpers return None so services degrade gracefully.
"""

from __future__ import annotations

from typing import Any


def get_current_tenant_id() -> Any:
    return None


def get_current_user() -> Any:
    return None
