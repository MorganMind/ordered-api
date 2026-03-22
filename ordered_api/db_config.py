"""
Django DATABASES: prefer Supabase Postgres (same DB as migrations.sql + auth).

Set either:
  - DATABASE_URL=postgresql://postgres.[ref]:PASSWORD@aws-0-....pooler.supabase.com:6543/postgres?sslmode=require
    (copy from Supabase Dashboard → Project Settings → Database → URI; use pooler for Cloud Run / many short-lived connections)

Or discrete vars (if you prefer not to put the full URL in .env):
  - SUPABASE_DB_HOST, SUPABASE_DB_PASSWORD
  - optional: SUPABASE_DB_USER (default postgres), SUPABASE_DB_NAME (default postgres),
              SUPABASE_DB_PORT (default 5432)

If nothing is set and DEBUG=True, falls back to SQLite for local experiments.
If nothing is set and DEBUG=False, raises ImproperlyConfigured.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured


def _build_url_from_supabase_env() -> str:
    host = os.getenv("SUPABASE_DB_HOST", "").strip()
    password = os.getenv("SUPABASE_DB_PASSWORD", "").strip()
    if not host or not password:
        return ""

    user = os.getenv("SUPABASE_DB_USER", "postgres").strip()
    name = os.getenv("SUPABASE_DB_NAME", "postgres").strip()
    port = os.getenv("SUPABASE_DB_PORT", "5432").strip()

    from urllib.parse import quote_plus

    return (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}"
        f"@{host}:{port}/{name}?sslmode=require"
    )


def _parse_postgres_url(url: str) -> dict:
    parsed = urlparse(url)
    if parsed.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured(
            f"DATABASE_URL must use postgres:// or postgresql:// (got {parsed.scheme!r})"
        )

    db_name = (parsed.path or "").lstrip("/") or "postgres"
    user = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    host = parsed.hostname or ""
    if not host:
        raise ImproperlyConfigured("DATABASE_URL is missing host")

    port = parsed.port or 5432
    qs = parse_qs(parsed.query)
    sslmode = (qs.get("sslmode") or ["require"])[0]

    conn_max_age = os.getenv("DATABASE_CONN_MAX_AGE", "600")
    try:
        conn_max_age_int = int(conn_max_age)
    except ValueError:
        conn_max_age_int = 600

    return {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": db_name,
            "USER": user,
            "PASSWORD": password,
            "HOST": host,
            "PORT": str(port),
            "CONN_MAX_AGE": conn_max_age_int,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "sslmode": sslmode,
                "connect_timeout": int(os.getenv("DATABASE_CONNECT_TIMEOUT", "15")),
            },
        }
    }


def get_django_databases(base_dir: Path, *, debug: bool) -> dict:
    database_url = (os.getenv("DATABASE_URL") or "").strip()
    if not database_url:
        database_url = _build_url_from_supabase_env()

    if database_url:
        return _parse_postgres_url(database_url)

    if not debug:
        raise ImproperlyConfigured(
            "Production requires Supabase Postgres: set DATABASE_URL or "
            "SUPABASE_DB_HOST + SUPABASE_DB_PASSWORD (see ordered_api/db_config.py)."
        )

    return {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": base_dir / "db.sqlite3",
        }
    }
