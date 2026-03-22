"""
Supabase Auth Admin (service role) for technician provisioning.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SupabaseAuthService:
    """Create/delete auth users via Supabase service role."""

    def _client(self):
        from supabase import create_client

        url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for admin auth"
            )
        return create_client(url, key)

    def create_user(self, email: str) -> dict[str, Any]:
        client = self._client()
        resp = client.auth.admin.create_user(
            {"email": email, "email_confirm": True}
        )
        uid = None
        if resp is not None:
            u = getattr(resp, "user", None)
            if u is not None and getattr(u, "id", None) is not None:
                uid = u.id
            elif isinstance(resp, dict):
                uid = resp.get("id")
        out = {"id": str(uid) if uid is not None else None}
        logger.info("supabase_auth_user_created", email=email, id=out.get("id"))
        return out

    def delete_user(self, supabase_uid: str) -> None:
        client = self._client()
        client.auth.admin.delete_user(supabase_uid)
        logger.info("supabase_auth_user_deleted", supabase_uid=supabase_uid)
