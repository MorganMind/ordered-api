# Organization (workspace) logo — frontend spec

The **organization** is the Django **`tenants.Tenant`** row for the signed-in user’s workspace. The logo is stored as a public URL: **`logo_url`** (same pattern as **`users.User.avatar_url`**).

**Base:** `NEXT_PUBLIC_API_URL` + `/v1` (e.g. `http://localhost:8000/api/v1`).

**Auth:** `Authorization: Bearer <Supabase access_token>`.

**Who can change it:** workspace operators/admins only — same permission as `GET/PATCH /tenants/me/` (`IsTenantWorkspaceStaff`).

Run migrations after deploy: `tenants.0004_tenant_logo_url`.

---

## Where the frontend reads `logo_url`

| Source | Field | Notes |
|--------|--------|--------|
| **`GET /auth/me/`** | `tenant.logo_url` | Prefer this on app bootstrap if you already call `/auth/me/` — DB-backed when the tenant row resolves. |
| **`GET /tenants/me/`** | `logo_url` | Full tenant payload for settings / workspace screen. |

Both return **`null`** when no logo is set.

Example `tenant` block from `/auth/me/` (subset):

```json
{
  "tenant_id": "<uuid>",
  "tenant": {
    "id": "<uuid>",
    "name": "Acme Cleaning",
    "slug": "acme-cleaning",
    "logo_url": "https://api.example.com/media/tenant_logos/<uuid>/....png",
    "color": "#6366f1",
    "plan": "professional",
    "status": "active",
    "settings": { "timezone": "America/New_York", "currency": "USD", "date_format": "MM/dd/yyyy", "features": {} },
    "operator_admin_email": "ops@example.com"
  }
}
```

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/tenants/me/` | Full tenant including `logo_url` |
| `PATCH` | `/tenants/me/` | Update `name` and/or `logo_url` (external URL only) |
| `POST` | `/tenants/me/logo/` | **Multipart** image upload → stored on API media → `logo_url` updated |
| `DELETE` | `/tenants/me/logo/` | Clear `logo_url` (and delete file if stored under this API’s media) |

---

## `GET /tenants/me/` — response shape (relevant fields)

```json
{
  "id": "<uuid>",
  "name": "Acme Cleaning",
  "slug": "acme-cleaning",
  "status": "active",
  "email": "",
  "phone": "",
  "operator_admin_email": "ops@example.com",
  "logo_url": "https://...",
  "timezone": "America/New_York",
  "is_active": true,
  "created_at": "...",
  "updated_at": "..."
}
```

- **`slug`**, **`id`**, **`created_at`**, **`updated_at`**: read-only.
- **`logo_url`**: string URL or `null`.

---

## `PATCH /tenants/me/` — set external logo URL

Use when the image lives on **Supabase Storage**, **S3**, or another CDN; you only persist the **public HTTPS URL** in Django.

```http
PATCH /api/v1/tenants/me/
Content-Type: application/json

{
  "name": "Acme Cleaning",
  "logo_url": "https://xyz.supabase.co/storage/v1/object/public/org-logos/acme.png"
}
```

Clear logo (without deleting a file — for uploads use `DELETE /tenants/me/logo/`):

```json
{ "logo_url": null }
```

---

## `POST /tenants/me/logo/` — upload through this API

**Multipart** form. The backend uses the **first** of these part names it finds (same as user avatar for client reuse):

| Part name | Notes |
|-----------|--------|
| **`file`** | **Preferred** |
| `avatar` | Legacy mobile / shared client code |
| `image` | Common alternate |
| `photo` | Common alternate |

**Constraints** (same as user avatar):

- **Types:** `image/jpeg`, `image/png`, `image/webp`, `image/gif`
- **Max size:** 5 MiB

**Response:** `200 OK`

```json
{ "logo_url": "https://your-api.example.com/media/tenant_logos/<tenant_uuid>/<uuid>.png" }
```

---

## `DELETE /tenants/me/logo/`

Clears **`logo_url`** on the tenant and **best-effort** deletes the object if it was stored under this API’s **`tenant_logos/`** media prefix (external URLs are only cleared in DB).

**Response:** `200 OK`

```json
{ "logo_url": null }
```

---

## UI guidelines

- Treat **`logo_url`** like **`avatar_url`**: optional; show **tenant `name` initial** or a **generic building** icon when `null`.
- Use **`object-fit: contain`** in headers and **`max-height`** (e.g. 32–40px nav, larger on settings) so wide logos do not break layout.
- After **upload**, refresh local workspace state from **`GET /tenants/me/`** or rely on **`POST`** response `logo_url` and patch client cache.
- **`GET /auth/me/`** may be cached in the client; after changing the logo, **refetch `/auth/me/`** or update **`tenant.logo_url`** in client state so the shell header updates.

---

## Related

- User avatars: `docs/USER_AVATAR_FRONTEND.md`
- Operator workspace tenant name: `PATCH /tenants/me/` (existing)
