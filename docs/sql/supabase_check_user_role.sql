-- Run in Supabase → SQL Editor (project database).
-- JWT "role" is often `authenticated` / `anon`; app roles (operator, technician, etc.)
-- usually live in raw_app_meta_data / raw_user_meta_data.

-- By email
SELECT
  id,
  email,
  email_confirmed_at,
  banned_until,
  raw_app_meta_data   AS app_metadata,
  raw_user_meta_data  AS user_metadata,
  -- Common locations for app role (adjust keys to match your hook):
  raw_app_meta_data->>'role'       AS app_role,
  raw_user_meta_data->>'role'      AS user_role,
  raw_app_meta_data->>'tenant_id'  AS tenant_id_from_app
FROM auth.users
WHERE lower(email) = lower('ops@example.com');

-- By user UUID (matches JWT `sub`)
SELECT
  id,
  email,
  raw_app_meta_data,
  raw_user_meta_data
FROM auth.users
WHERE id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'::uuid;

-- Quick JSON pretty (optional)
SELECT jsonb_pretty(raw_app_meta_data) AS app_meta,
       jsonb_pretty(raw_user_meta_data) AS user_meta
FROM auth.users
WHERE lower(email) = lower('ops@example.com');
