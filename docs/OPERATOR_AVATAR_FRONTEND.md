# Operator app avatar integration (`ordered-operator`)

This is the operator-focused wiring guide for avatar/profile photo updates.

The backend intentionally uses a **shared user API** (`users.User`) so operator, technician, and client apps do not duplicate avatar endpoints.

**Base URL:** `NEXT_PUBLIC_API_URL` + `/v1`  
**Auth:** `Authorization: Bearer <supabase_access_token>`

---

## Endpoints operators should use

| Method | Path | Use |
|--------|------|-----|
| `GET` | `/users/me/` | Load current operator profile + `avatar_url` |
| `PATCH` | `/users/me/` | Save profile text fields and/or external `avatar_url` |
| `POST` | `/users/me/avatar/` | Upload avatar file to backend storage |
| `DELETE` | `/users/me/avatar/` | Remove avatar |
| `GET` | `/auth/me/` | Optional bootstrap source (now also includes `avatar_url`) |

---

## Recommended operator UI flow

1. On app/session bootstrap, call `GET /auth/me/` (if you already do this) or `GET /users/me/`.
2. In account/profile settings UI, use `GET /users/me/` as the source of truth.
3. For image picker upload, call `POST /users/me/avatar/` with multipart field `file`.
4. On success, immediately update local user store with returned `avatar_url` (or refetch `/users/me/`).
5. For “remove photo,” call `DELETE /users/me/avatar/` and clear local avatar state.

---

## Request examples (Next.js / browser)

### 1) Read profile

```ts
const res = await fetch(`${API}/users/me/`, {
  headers: { Authorization: `Bearer ${token}` },
});
const me = await res.json(); // includes avatar_url
```

### 2) Upload chosen file

```ts
const form = new FormData();
form.append("file", selectedFile, selectedFile.name); // preferred field name

const res = await fetch(`${API}/users/me/avatar/`, {
  method: "POST",
  headers: { Authorization: `Bearer ${token}` },
  body: form,
});

if (!res.ok) throw new Error(await res.text());
const data = await res.json(); // { avatar_url: "..." }
```

### 3) Save external URL instead of uploading (optional)

```ts
const res = await fetch(`${API}/users/me/`, {
  method: "PATCH",
  headers: {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    avatar_url: "https://<your-cdn>/avatars/operator-123.png",
  }),
});
```

### 4) Remove avatar

```ts
await fetch(`${API}/users/me/avatar/`, {
  method: "DELETE",
  headers: { Authorization: `Bearer ${token}` },
});
```

---

## Multipart notes (important)

- Preferred multipart field: **`file`**
- Also accepted for compatibility: `avatar`, `image`, `photo`
- Allowed image types: `image/jpeg`, `image/png`, `image/webp`, `image/gif`
- Max size: `5 MiB`
- If a mobile/web client sends `application/octet-stream`, backend infers image type from extension/header when possible.

If upload fails with missing field, backend returns:

```json
{
  "detail": "Missing multipart file field. Use one of: 'file', 'avatar', 'image', 'photo'.",
  "accepted_field_names": ["file", "avatar", "image", "photo"]
}
```

---

## Shared contract reference

For the full cross-app contract, see `docs/USER_AVATAR_FRONTEND.md`.
