"""
Workspace logo upload validation and storage for ``tenants.Tenant``.

Mirrors ``apps.users.services.avatar`` paths and constraints; stored under ``tenant_logos/``.
"""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from apps.users.services.avatar import (
    pick_avatar_upload_file,
    resolve_avatar_content_type,
    validate_avatar_upload,
)

_EXT_BY_CT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def save_tenant_logo_to_default_storage(tenant, file_obj, *, content_type: str | None, request) -> str:
    """Save to default storage; return absolute URL for ``Tenant.logo_url``."""
    raw = file_obj.read()
    filename = getattr(file_obj, "name", None)
    ct = resolve_avatar_content_type(
        content_type,
        filename=filename,
        file_head=raw[:64],
    )
    validate_avatar_upload(size=len(raw), content_type=ct)
    ext = _EXT_BY_CT.get(ct, ".bin")
    name = f"tenant_logos/{tenant.id}/{uuid.uuid4().hex}{ext}"
    path = default_storage.save(name, ContentFile(raw))
    rel_url = default_storage.url(path)
    if rel_url.startswith("http://") or rel_url.startswith("https://"):
        return rel_url
    return request.build_absolute_uri(rel_url)


def try_delete_stored_tenant_logo_if_local(old_url: str | None) -> None:
    """Best-effort delete when URL points at this app’s ``tenant_logos/`` media."""
    if not old_url:
        return
    media_url = (getattr(settings, "MEDIA_URL", None) or "").strip()
    if not media_url:
        return
    path = urlparse(old_url).path
    base = media_url.rstrip("/")
    if not path.startswith(base + "/"):
        return
    rel = path[len(base) + 1 :]
    if not rel.startswith("tenant_logos/"):
        return
    try:
        if default_storage.exists(rel):
            default_storage.delete(rel)
    except Exception:
        pass


__all__ = [
    "pick_avatar_upload_file",
    "save_tenant_logo_to_default_storage",
    "try_delete_stored_tenant_logo_if_local",
]
