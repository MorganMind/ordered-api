# Only you can do (secrets + your Supabase project)

The codebase is wired for **one Postgres** (Supabase) via `DATABASE_URL` / `ordered_api/db_config.py`, and Django now installs **`apps.core`**, **`apps.tenants`**, **`apps.events`** with migrations.

## 1. Put real credentials in `.env` (never commit)

- **`DATABASE_URL`** — Supabase → **Project Settings → Database → Connection string (URI)**.  
  Prefer **Transaction pooler** (port **6543**) for Cloud Run.
- **`SUPABASE_URL`**, **`SUPABASE_ANON_KEY`**, **`SUPABASE_SERVICE_ROLE_KEY`**, **`SUPABASE_JWT_SECRET`** (or JWKS path already handled in code) — for the Supabase client + `/api/v1/auth/me/`.
- **`SECRET_KEY`** — Django secret.

Copy from **`.env.example`** and fill values.

## 2. Run migrations against Supabase (on your machine)

With `.env` loaded so `DATABASE_URL` points at Supabase:

```bash
pip install -r requirements.txt
python manage.py migrate
```

Use a DB role that can **CREATE TABLE** (direct connection or pooler role Supabase documents for migrations).

## 3. Cloud Run / production

In **GCP Console** (or Secret Manager + service env), set the same vars as `.env` — **`DATABASE_URL`**, **`SECRET_KEY`**, Supabase keys.  
Redeploy after **`cloudbuild.yaml`** image name change (`ordered-api`).

## 4. Workspace tenant on `/api/v1/auth/me/` (operator + client apps)

The API fills `tenant_id`, `tenantId`, `tenant.id`, and `membership.tenant_id` from the **Supabase access token** first (`app_metadata` / `user_metadata`). If those are empty, it can fall back to Django `users.User` (when `apps.users` exists) or **`AUTH_ME_FALLBACK_TENANT_ID`** in `.env` (dev only).

Put the workspace on the auth user so **new JWTs** include it (then sign out / sign in):

```sql
-- Replace TENANT_UUID with ``tenants.id`` (Django table ``public.tenants``).
UPDATE auth.users
SET
  raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
    || jsonb_build_object('tenant_id', 'TENANT_UUID'::text),
  updated_at = now()
WHERE lower(email) = lower('you@example.com');
```

Optional nested shape (also supported by the API):

```sql
UPDATE auth.users
SET
  raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
    || jsonb_build_object(
      'tenant',
      jsonb_build_object('id', 'TENANT_UUID'::text, 'name', 'My Org', 'slug', 'my-org')
    ),
  updated_at = now()
WHERE lower(email) = lower('you@example.com');
```

## 5. Optional next features (not done here)

- **`apps.technicians`** + **`apps.users`** — imports `apps.users.models` and `TechniciansConfig.ready()` signals; add when those packages exist, then restore **public apply** route in `apps/tenants/urls.py`.
- **`apps.intake`** — needs migrations + `users.User` / `properties.Property` or model refactors.
- **Custom user** with **`tenant_id`** — if you want tenant-scoped API without `is_superuser`, extend **`AUTH_USER_MODEL`** and migrate; `/auth/me` will pick up tenant from that user when JWT has no tenant.
