# Clients API — operator workspace (frontend)

Tenant **clients** are `users.User` rows with **`role: "client"`**. This API mirrors the **technicians admin** pattern: list + detail under **`/api/v1/admin/`**, tenant-scoped, no pagination wrapper (JSON array on list).

**Base:** `NEXT_PUBLIC_API_URL` + `/v1` (e.g. `https://api.example.com/api/v1`).

**Auth:** `Authorization: Bearer <Supabase JWT>`.

---

## Authentication and authorization

| Concern | Detail |
|--------|--------|
| **Who can call** | Same as **`GET /api/v1/admin/technicians/`**: `IsAuthenticated` + **`IsAdmin`**. Today `IsAdmin` means **`user.is_staff` or `user.is_superuser`** (`apps/core/permissions.py`). |
| **Tenancy** | List and detail are filtered to **`request.user.tenant_id`**. No tenant override in query/body. |

If your operator users are **not** Django staff but use **`role: "admin"`** / **`"operator"`** in JWT only, they will get **403** on these routes until you align permissions (e.g. extend `IsAdmin` or use `IsTenantWorkspaceStaff` on the viewset — product decision).

---

## List clients

```http
GET /api/v1/admin/clients/
```

### Query parameters

| Param | Effect |
|-------|--------|
| `search` | Search across `email`, `first_name`, `last_name`, `phone` (icontains). |
| `status` | Exact match on user **`status`**: `pending`, `active`, `inactive`. |
| `is_active` | Exact boolean (`true` / `false`). |
| `ordering` | One of `created_at`, `updated_at`, `email`, `last_name`, `first_name`; prefix `-` for descending. Default: **`-created_at`**. |

### Response

JSON **array** of list rows:

| Field | Type | Notes |
|-------|------|--------|
| `id` | UUID | User id — use for detail and deep links |
| `email` | string | |
| `first_name` | string | |
| `last_name` | string | |
| `full_name` | string | Derived; falls back to email |
| `phone` | string | |
| `avatar_url` | string \| null | |
| `status` | string | `pending` \| `active` \| `inactive` |
| `is_active` | boolean | Django auth flag |
| `service_request_count` | integer | Service requests with this user as **`client`** |
| `jobs_created_count` | integer | Jobs with **`created_by`** = this user |
| `created_at` | ISO 8601 | |

---

## Client detail

```http
GET /api/v1/admin/clients/{user_id}/
```

`user_id` is the **`users.User`** primary key (same as list `id`).

### Response

Everything in the list row, plus:

| Field | Type | Notes |
|-------|------|--------|
| `tenant_id` | UUID | Workspace tenant |
| `role` | string | Always `client` here |
| `supabase_uid` | string \| null | Auth link |
| `metadata` | object | JSON; may be empty |
| `updated_at` | ISO 8601 | |

**404** if the user is not a **client** in your tenant (including wrong tenant or wrong role).

---

## Frontend integration checklist

1. **Navigation**  
   Add a **Clients** item next to **Technicians** in the operator shell, pointing to e.g. `/operator/clients` (your route).

2. **List page**  
   - `GET /api/v1/admin/clients/`  
   - Optional search box → `?search=`  
   - Optional filters → `status`, `is_active`  
   - Table columns: name (`full_name`), email, phone, status, counts (`service_request_count`, `jobs_created_count`), created date.

3. **Detail drawer / page**  
   - `GET /api/v1/admin/clients/{id}/`  
   - Show profile + counts; link to **service requests** list with `?client={id}` if your SR list supports it (filter may need a separate backend param — not part of this doc).

4. **Errors**  
   - **403**: operator is not staff — show “insufficient permissions” or hide the section.  
   - **401**: refresh token / re-login.

5. **Types**  
   Mirror the field names above in TypeScript; treat UUIDs as strings.

---

## Related

- Technicians admin: `docs/TECHNICIANS_API_FRONTEND.md`  
- Current user profile (any role): `docs/USER_AVATAR_FRONTEND.md` (`GET /users/me/`)
