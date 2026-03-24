# User avatar & profile — shared API (all apps / roles)

One **`users.User`** row backs **clients**, **technicians**, and **operators**. Avatar and basic name fields live on that model so **operator, technician, and client apps** all use the **same endpoints** — no per-role duplicate APIs.

**Base:** `NEXT_PUBLIC_API_URL` + `/v1` (e.g. `http://localhost:8000/api/v1`).

**Auth:** `Authorization: Bearer <Supabase access_token>`.

---

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/users/me/` | Full profile including `avatar_url` |
| `PATCH` | `/users/me/` | Update `first_name`, `last_name`, `phone`, and/or `avatar_url` |
| `POST` | `/users/me/avatar/` | **Multipart** image upload → stored on server → `avatar_url` updated |
| `DELETE` | `/users/me/avatar/` | Clear `avatar_url` (and delete file if it was stored under this API’s media) |

Also, **`GET /auth/me/`** includes top-level **`avatar_url`** (from Django `User` when resolved), so lightweight bootstraps can read it without calling `/users/me/`.

---

## `GET /users/me/` response (shape)

```json
{
  "id": "<uuid>",
  "email": "user@example.com",
  "first_name": "Alex",
  "last_name": "Rivera",
  "full_name": "Alex Rivera",
  "phone": "",
  "avatar_url": "https://..." ,
  "role": "client",
  "tenant_id": "<uuid>"
}
```

- **`role`**: `client` | `technician` | `admin` (and your app may treat `admin` as operator workspace).
- **`email`**, **`tenant_id`**, **`role`**: read-only in `PATCH`.
- **`avatar_url`**: `null` if unset.

Technicians also see **`avatar_url`** on **`GET /technicians/me/`** (same underlying `User`).

---

## `PATCH /users/me/` — set text fields or external avatar URL

Use when the image was uploaded elsewhere (e.g. **Supabase Storage**) and you only want to save the **public URL** in Django.

```http
PATCH /api/v1/users/me/
Content-Type: application/json

{
  "first_name": "Alex",
  "last_name": "Rivera",
  "phone": "+15551234567",
  "avatar_url": "https://xyz.supabase.co/storage/v1/object/public/avatars/..."
}
```

To remove an external URL:

```json
{ "avatar_url": null }
```

---

## `POST /users/me/avatar/` — upload through this API

**Multipart** form. The backend accepts the file under the **first** of these part names it finds (use **`file`** in new code — matches DRF conventions and the example below):

| Part name | Notes |
|-----------|--------|
| **`file`** | **Preferred** (documented default) |
| `avatar` | e.g. Flutter/Dio apps that use `ApiService._userAvatarMultipartField = 'avatar'` |
| `image` | Common alternate |
| `photo` | Common alternate |

If the file is missing, the API returns **400** with **`accepted_field_names`**: `["file", "avatar", "image", "photo"]` so clients can align.

Allowed types: **`image/jpeg`**, **`image/png`**, **`image/webp`**, **`image/gif`**. Max size **5 MiB**.

If the client sends **`application/octet-stream`** (common on mobile), the API still accepts the upload when the **filename extension** (`.jpg`, `.png`, `.gif`, `.webp`) or **file header** matches a supported image.

**Example (web)**

```ts
const form = new FormData();
form.append("file", fileFromInput, fileFromInput.name);

await fetch(`${API}/users/me/avatar/`, {
  method: "POST",
  headers: { Authorization: `Bearer ${accessToken}` },
  body: form,
});
```

**Response 200**

```json
{ "avatar_url": "http://localhost:8000/media/avatars/..." }
```

In **development**, `DEBUG=True` serves `/media/...` from Django. In **production**, serve **`MEDIA_ROOT`** (or switch default storage to S3/GCS and return public URLs) — configure your reverse proxy or storage backend accordingly.

---

## `DELETE /users/me/avatar/`

Clears `avatar_url`. If the previous URL pointed at a file under this app’s **local media** avatars path, the file is deleted best-effort; external URLs are only cleared in the database.

---

## UI flow recommendations

1. **Settings / profile screen:** `GET /users/me/` once; bind `avatar_url` to `<img src>` when non-null.
2. **After any update:** use the JSON body returned by `PATCH` or `POST …/avatar/` as source of truth (or refetch `GET /users/me/`).
3. **Optional:** after changing profile, call **`GET /auth/me/`** if other hooks depend on it — or rely on `/users/me/` only.
4. **Technician onboarding** can keep using **`PATCH /technicians/me/`** for skills/regions; **avatar** should still go through **`/users/me/`** so all roles stay consistent.

---

## Backend code map

| Piece | Location |
|-------|-----------|
| Model field | `apps.users.models.User.avatar_url` |
| GET/PATCH me | `apps.users.views.UserMeView` |
| Upload/delete | `apps.users.views.UserMeAvatarUploadView` |
| Shared upload logic | `apps.users.services.avatar` |
| Routes | `apps.users.urls` → `ordered_api/urls.py` |
| `auth/me` field | `api_auth.me_response.build_auth_me_response` |
