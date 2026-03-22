# Your tables vs Django migrations

## Tables you listed

| Table | Source in this repo |
|-------|---------------------|
| `user_data`, `user_settings`, `user_analytics`, `tag`, `tagging` | **`migrations.sql`** (top) — raw SQL for Supabase/Postgres |
| `plans`, `memberships`, `entitlements`, `ledger_entries`, `webhook_events` | **`migrations.sql`** (billing / Stripe section) |

These are **not** created by `python manage.py migrate`. They come from applying **`migrations.sql`** (or equivalent Supabase migrations) to Postgres.

If those tables exist, that SQL has already been applied. There is nothing for Django to “catch up” for those tables unless you later add matching Django models + migrations.

---

## Django migrations in *this* repo

Apps that **have** `migrations/*.py`:

| App | Tables (from models `db_table` / defaults) |
|-----|---------------------------------------------|
| `apps.tenants` | `tenants` |
| `apps.events` | `events` |
| `apps.technicians` | `service_regions`, `technician_profiles`, `application_forms`, `technician_applications` |
| `apps.intake` | `intake_sessions`, `intake_messages`, `intake_update_proposals`, etc. |

**`apps.intake`**: the `migrations/` folder has **no numbered `0001_*.py` in git** (only `__init__.py`). There is a stray `__pycache__/0001_initial.*.pyc` — treat intake as **missing migration sources**; run `makemigrations` once `apps.intake` and its dependencies are correctly installed.

Intake models reference **`users.User`**, but **`apps/users/` is not present** in this tree. You cannot run intake migrations until that app (or swapped FK targets) exists.

---

## Why `showmigrations` only shows `admin`, `auth`, …

`ordered_api/settings.py` now includes **`apps.core`**, **`apps.tenants`**, **`apps.events`** (plus DRF). **`apps.technicians`** / **`apps.intake`** are not installed until **`apps.users`** (and related) exist — see **`docs/SUPABASE_YOU_MUST_DO.md`**.

With the default settings, **`manage.py migrate` will never create `tenants`, `events`, technician tables, etc.**

---

## Commands that answer “which migrations are not run?”

### 1) After you fix `INSTALLED_APPS` (add the real Ordered apps)

```bash
./venv/bin/python manage.py showmigrations
./venv/bin/python migrate --plan
```

`[ ]` = not applied; `[X]` = applied.

### 2) On Postgres: what Django thinks it applied

```sql
SELECT app, name, applied
FROM django_migrations
ORDER BY applied;
```

Compare `app` + `name` to files under `*/migrations/0*.py`.

### 3) Supabase billing tables (not in `django_migrations`)

If `plans` / `memberships` / etc. are missing, re-run or diff against **`migrations.sql`**, not Django.

---

## Summary

1. **Your JSON list** matches **Supabase SQL** (`migrations.sql`), **not** pending Django migrations.
2. **Django app migrations** for tenants / events / technicians / intake are **untracked by default** because those apps are **not** in `INSTALLED_APPS`.
3. **Intake** needs **migration files** + a **`users`** (or equivalent) app before `migrate` can succeed.
