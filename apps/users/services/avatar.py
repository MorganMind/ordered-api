"""
Shared avatar upload validation and storage for ``users.User``.

Used by ``/api/v1/users/me/avatar/`` for any authenticated role (client, technician, operator).
"""
from __future__ import annotations

import uuid
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework.exceptions import ValidationError

ALLOWED_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)
MAX_AVATAR_BYTES = 5 * 1024 * 1024  # 5 MiB

# Multipart part names accepted on POST /users/me/avatar/ (canonical first).
AVATAR_MULTIPART_FIELD_NAMES: tuple[str, ...] = (
    "file",
    "avatar",
    "image",
    "photo",
)


def pick_avatar_upload_file(request):
    """Return ``(uploaded_file, field_name)`` or ``(None, None)``."""
    for key in AVATAR_MULTIPART_FIELD_NAMES:
        f = request.FILES.get(key)
        if f:
            return f, key
    return None, None

_EXT_BY_CT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Mobile pickers often send ``application/octet-stream``; infer real type from name / bytes.
_GENERIC_BINARY_TYPES = frozenset(
    {
        "application/octet-stream",
        "binary/octet-stream",
        "application/x-binary",
    }
)


def _content_type_from_filename(filename: str | None) -> str | None:
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
    }.get(ext)


def _content_type_from_magic(head: bytes) -> str | None:
    if len(head) < 12:
        return None
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def resolve_avatar_content_type(
    reported: str | None,
    *,
    filename: str | None,
    file_head: bytes,
) -> str:
    """
    Return a value in ``ALLOWED_CONTENT_TYPES``.

    Accepts generic ``application/octet-stream`` when filename or magic bytes identify an image.
    """
    ct = (reported or "").split(";")[0].strip().lower()
    if ct in ALLOWED_CONTENT_TYPES:
        return ct
    if not ct or ct in _GENERIC_BINARY_TYPES:
        guessed = _content_type_from_filename(filename)
        if guessed:
            return guessed
        guessed = _content_type_from_magic(file_head)
        if guessed:
            return guessed
    return ct


def validate_avatar_upload(*, size: int, content_type: str | None) -> None:
    if size <= 0:
        raise ValidationError({"file": ["Empty file."]})
    if size > MAX_AVATAR_BYTES:
        raise ValidationError(
            {"file": [f"Image too large (max {MAX_AVATAR_BYTES // (1024 * 1024)} MiB)."]}
        )
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in ALLOWED_CONTENT_TYPES:
        raise ValidationError(
            {
                "file": [
                    f"Unsupported type {content_type!r}. "
                    f"Allowed: {sorted(ALLOWED_CONTENT_TYPES)}."
                ]
            }
        )


def save_avatar_to_default_storage(user, file_obj, *, content_type: str | None, request) -> str:
    """
    Save ``file_obj`` to default storage and return an **absolute** URL to embed in clients.

    ``user.avatar_url`` should be set to this return value by the caller.
    """
    raw = file_obj.read()
    filename = getattr(file_obj, "name", None)
    ct = resolve_avatar_content_type(
        content_type,
        filename=filename,
        file_head=raw[:64],
    )
    validate_avatar_upload(size=len(raw), content_type=ct)
    ext = _EXT_BY_CT.get(ct, ".bin")
    tid = getattr(user, "tenant_id", None) or "no-tenant"
    name = f"avatars/{tid}/{user.id}/{uuid.uuid4().hex}{ext}"
    path = default_storage.save(name, ContentFile(raw))
    rel_url = default_storage.url(path)
    if rel_url.startswith("http://") or rel_url.startswith("https://"):
        return rel_url
    return request.build_absolute_uri(rel_url)


def try_delete_stored_avatar_if_local(old_url: str | None) -> None:
    """
    Best-effort delete when ``old_url`` points at this app's default storage (MEDIA) avatars.
    Skips Supabase or other external URLs.
    """
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
    if not rel.startswith("avatars/"):
        return
    try:
        if default_storage.exists(rel):
            default_storage.delete(rel)
    except Exception:
        pass
