# Django + Supabase Postgres (single database)

Django’s **`DATABASES`** now points at **Supabase PostgreSQL** when you set **`DATABASE_URL`** (or **`SUPABASE_DB_HOST`** + **`SUPABASE_DB_PASSWORD`**).

That is the **same database** where you ran **`migrations.sql`** (`user_data`, `plans`, `tenants` after you `migrate`, etc.).

## Setup

1. **Supabase Dashboard** → **Project Settings** → **Database**  
2. Copy **Connection string** → **URI** (use **Transaction pooler** / port **6543** for Cloud Run and many short-lived connections).  
3. Put it in **`.env`** as **`DATABASE_URL=...`** (see **`.env.example`**).

## Commands

```bash
pip install -r requirements.txt
export DEBUG=True SECRET_KEY=dev   # or use .env
python manage.py migrate
python manage.py runserver
```

With **`DEBUG=False`**, Django **requires** `DATABASE_URL` or Supabase DB env vars (no SQLite).

## Notes

- **RLS**: Django connects with the DB user from the URI (often `postgres` or pooler role). Server-side RLS still applies to PostgREST; Django uses a direct Postgres session (bypasses PostgREST). Use a restricted DB user if you need stricter DB-level policy for Django.
- **`psycopg`** (v3) is required; it is listed in **`requirements.txt`**.
