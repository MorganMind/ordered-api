"""
Build GET /api/v1/auth/me/ JSON to match Ordered frontend (mapMeResponseFromApi / useTenant).

Contract:
- Top-level tenant_id and tenantId (same UUID string) when user has an org.
- tenant object with id (same UUID), name, slug, color, plan, status, settings,
  operator_admin_email (nullable string from DB for application-alerts recipient).
- membership: { "tenant_id": "<uuid>" } when resolved (for clients that read membership.tenant_id).
- organization_id and workspace_id duplicate tenant_id when set (alias names some clients expect).
- Top-level timezone mirrors tenant primary timezone for convenience.
- When user has no tenant: tenant_id, tenantId, tenant, membership, organization_id, workspace_id are null.
- Top-level avatar_url from Django users.User when the row resolves (null if none).

Tenant resolution order: JWT app_metadata / user_metadata (tenant_id or nested tenant),
then Django users.User (supabase_uid / email) if apps.users is installed,
then env AUTH_ME_FALLBACK_TENANT_ID (dev only).
"""

from __future__ import annotations

import os
from typing import Any

DEFAULT_FEATURES: dict[str, bool] = {
    "advanced_scheduling": False,
    "real_time_tracking": False,
    "custom_fields": False,
}

DEFAULT_COLOR = "#6366f1"


def _as_dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def tenant_seed_from_claims(claims: dict | None) -> dict[str, Any]:
    """Pull tenant hints from Supabase JWT (app_metadata / user_metadata)."""
    if not claims:
        return {"id": None}

    app = _as_dict(claims.get("app_metadata"))
    user_meta = _as_dict(claims.get("user_metadata"))

    for meta in (app, user_meta):
        nested = meta.get("tenant")
        if isinstance(nested, dict):
            tid = nested.get("id")
            if tid is not None:
                st = nested.get("settings")
                return {
                    "id": str(tid),
                    "slug": nested.get("slug"),
                    "name": nested.get("name"),
                    "color": nested.get("color"),
                    "plan": nested.get("plan"),
                    "status": nested.get("status"),
                    "settings": st if isinstance(st, dict) else {},
                }

    tenant_id = (
        app.get("tenant_id")
        or user_meta.get("tenant_id")
        or claims.get("tenant_id")
    )
    if tenant_id is not None:
        return {
            "id": str(tenant_id),
            "slug": app.get("tenant_slug") or user_meta.get("tenant_slug"),
            "name": app.get("tenant_name") or user_meta.get("tenant_name"),
            "color": app.get("tenant_color") or user_meta.get("tenant_color"),
            "plan": app.get("tenant_plan") or user_meta.get("tenant_plan"),
            "status": app.get("tenant_status") or user_meta.get("tenant_status"),
            "settings": {},
        }

    return {"id": None}


def _django_user_for_auth_me(request) -> Any:
    """Resolve ``apps.users.User`` from JWT sub / email when installed."""
    cache_attr = "_cached_django_user_me_v1"
    if hasattr(request, cache_attr):
        return getattr(request, cache_attr)
    try:
        from django.apps import apps

        if not apps.is_installed("users"):
            setattr(request, cache_attr, None)
            return None
        User = apps.get_model("users", "User")
    except LookupError:
        setattr(request, cache_attr, None)
        return None

    uid = getattr(request, "user_id", None)
    email = (getattr(request, "user_email", None) or "").strip()
    user = None
    if uid:
        user = User.objects.filter(supabase_uid=uid).first()
    if user is None and email:
        user = User.objects.filter(email__iexact=email).first()
    setattr(request, cache_attr, user)
    return user


def _tenant_seed_from_user_model(request) -> dict[str, Any] | None:
    """When JWT has no tenant hints, use Django ``users.User.tenant_id`` if installed."""
    user = _django_user_for_auth_me(request)
    if user is None:
        return None
    tid = getattr(user, "tenant_id", None)
    if not tid:
        return None
    return {"id": str(tid)}


def _tenant_seed_from_env() -> dict[str, Any] | None:
    """Local/dev escape hatch when auth.users metadata has no tenant_id yet."""
    tid = (os.getenv("AUTH_ME_FALLBACK_TENANT_ID") or "").strip()
    if not tid:
        return None
    return {"id": tid}


def merge_tenant_settings(
    *,
    db_settings: dict[str, Any],
    db_timezone: str,
    jwt_settings: dict[str, Any] | None,
) -> dict[str, Any]:
    s = dict(db_settings or {})
    j = dict(jwt_settings or {})

    features = {**DEFAULT_FEATURES, **(s.get("features") or {})}
    if isinstance(j.get("features"), dict):
        features = {**features, **j["features"]}

    timezone = (
        j.get("timezone")
        or s.get("timezone")
        or (db_timezone or "UTC")
    )
    currency = j.get("currency") or s.get("currency") or "USD"
    date_format = j.get("date_format") or s.get("date_format") or "MM/dd/yyyy"

    return {
        "timezone": timezone,
        "currency": currency,
        "date_format": date_format,
        "features": features,
    }


def enrich_tenant_for_auth_me(seed: dict[str, Any]) -> dict[str, Any] | None:
    """
    Full tenant block for /auth/me. Returns None if the user has no tenant id.
    Merges JWT seed with ``tenants.Tenant`` row when installed.
    """
    tid = seed.get("id")
    if tid is None or tid == "":
        return None

    name = seed.get("name")
    slug = seed.get("slug")
    color = seed.get("color")
    plan = seed.get("plan")
    status = seed.get("status")
    jwt_settings = seed.get("settings") if isinstance(seed.get("settings"), dict) else {}

    row = None
    try:
        from django.apps import apps

        if apps.is_installed("tenants"):
            from apps.tenants.models import Tenant

            row = Tenant.objects.filter(pk=tid).first()
    except Exception:
        row = None

    db_settings: dict[str, Any] = {}
    db_timezone = "UTC"
    if row:
        # DB is authoritative for workspace label + slug (PATCH /tenants/me/, admin, etc.).
        # JWT app_metadata often still carries the old tenant_name after a rename, which
        # previously made ``name = name or row.name`` freeze the UI on stale metadata.
        name = row.name
        slug = row.slug
        status = status or row.status
        db_settings = row.settings if isinstance(row.settings, dict) else {}
        db_timezone = row.timezone or "UTC"

    merged_settings = merge_tenant_settings(
        db_settings=db_settings,
        db_timezone=db_timezone,
        jwt_settings=jwt_settings,
    )

    color = color or db_settings.get("color") or DEFAULT_COLOR
    plan = plan or db_settings.get("plan")
    if not plan:
        plan = "trial" if (status or "").lower() == "trial" else "professional"
    status = status or "active"

    out_block = {
        "id": str(tid),
        "name": name or "",
        "slug": slug or "",
        "color": color,
        "plan": plan,
        "status": status,
        "settings": merged_settings,
    }
    if row:
        out_block["operator_admin_email"] = (row.operator_admin_email or "").strip() or None
        lu = getattr(row, "logo_url", None)
        out_block["logo_url"] = lu if lu else None
    else:
        out_block["operator_admin_email"] = None
        out_block["logo_url"] = None
    return out_block


def build_auth_me_response(request) -> dict[str, Any]:
    claims = getattr(request, "jwt_claims", None) or {}
    user_meta = _as_dict(claims.get("user_metadata"))
    app_meta = _as_dict(claims.get("app_metadata"))

    uid = getattr(request, "user_id", None)
    email = getattr(request, "user_email", None) or claims.get("email")
    # Prefer app_metadata.role so SQL/dashboard updates (admin/operator) beat user_metadata (client signup).
    role = (
        getattr(request, "user_role", None)
        or app_meta.get("role")
        or user_meta.get("role")
    )

    first_name = user_meta.get("first_name") or user_meta.get("given_name")
    last_name = user_meta.get("last_name") or user_meta.get("family_name")

    seed = tenant_seed_from_claims(claims)
    if not seed.get("id"):
        db_seed = _tenant_seed_from_user_model(request)
        if db_seed:
            seed = db_seed
    if not seed.get("id"):
        env_seed = _tenant_seed_from_env()
        if env_seed:
            seed = env_seed

    tenant_block = enrich_tenant_for_auth_me(seed)

    out: dict[str, Any] = {
        "id": uid,
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
        "role": role,
        "user_role": user_meta.get("role"),
        "app_role": app_meta.get("role"),
    }

    du = _django_user_for_auth_me(request)
    if du is not None:
        out["avatar_url"] = (getattr(du, "avatar_url", None) or "").strip() or None
    else:
        out["avatar_url"] = None

    if not tenant_block:
        out["tenant_id"] = None
        out["tenantId"] = None
        out["tenant"] = None
        out["membership"] = None
        out["organization_id"] = None
        out["workspace_id"] = None
        out["timezone"] = (
            user_meta.get("timezone")
            or app_meta.get("timezone")
            or "UTC"
        )
        return out

    tid = tenant_block["id"]
    out["tenant_id"] = tid
    out["tenantId"] = tid
    out["organization_id"] = tid
    out["workspace_id"] = tid
    out["tenant"] = tenant_block
    out["membership"] = {"tenant_id": tid}
    out["timezone"] = tenant_block["settings"]["timezone"]
    return out
