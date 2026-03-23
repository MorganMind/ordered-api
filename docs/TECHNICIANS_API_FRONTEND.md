# Technicians API — frontend reference

Base path for all routes below: **`/api/v1/`** (unless noted).

Production URL shape: **`{API_ORIGIN}/api/v1/...`** (e.g. `https://api.example.com/api/v1/admin/technicians/`).

---

## Authentication & authorization

| Concern | Detail |
|--------|--------|
| **Auth** | `Authorization: Bearer <Supabase JWT>` (see `apps.users.authentication.SupabaseAuthentication`). Session auth also works for browser tooling. |
| **Admin technician routes** | `IsAuthenticated` + `IsAdmin`. Today `IsAdmin` is **`user.is_staff` or `user.is_superuser`** (`apps/core/permissions.py`). |
| **Self-service + reference data** | `IsAuthenticated` (any logged-in user unless you add role checks in the SPA). |
| **Tenancy** | Technician admin list/detail are scoped to **`request.user.tenant_id`**. The API does not accept a tenant override in the body for these routes; ensure the JWT user’s tenant matches the operator workspace. |

There is **no global DRF pagination** configured in `ordered_api/settings.py` for these viewsets; list endpoints typically return a **JSON array** of objects (unless you add pagination later).

---

## Operator UI: list & detail technicians

These are the primary endpoints to **display technicians** in an admin/operator app.

### List technicians

```http
GET /api/v1/admin/technicians/
```

**Query parameters**

| Param | Effect |
|-------|--------|
| `status` | Filter by `onboarding_status` (exact match). See enum below. |
| `pending_review=true` | Shortcut: only profiles in **`submitted`** (awaiting review). |

**Response:** array of **list row** objects.

| Field | Type | Notes |
|-------|------|--------|
| `id` | UUID | `TechnicianProfile` id |
| `email` | string \| null | From linked `User` |
| `full_name` | string | From user first + last name |
| `phone` | string \| null | From `User` |
| `onboarding_status` | string | See enum |
| `skill_count` | integer | Active skills on user |
| `region_count` | integer | Active service regions on profile |
| `submitted_at` | ISO 8601 \| null | |
| `activated_at` | ISO 8601 \| null | |
| `suspended_at` | ISO 8601 \| null | |
| `created_at` | ISO 8601 | |

### Detail technician (full card / drawer)

```http
GET /api/v1/admin/technicians/{profile_id}/
```

**Response:** extends the self-service profile shape with **admin-only** fields.

**Shared with technician “me” shape**

| Field | Type | Notes |
|-------|------|--------|
| `id` | UUID | Profile id |
| `email`, `first_name`, `last_name`, `full_name`, `phone` | string | From `User` |
| `onboarding_status` | string | |
| `is_eligible` | boolean | `active` and eligible for jobs |
| `can_submit` | boolean | Can submit onboarding for review |
| `service_regions` | array | `{ id, key, name, short_name, state, is_active }` |
| `skills` | array | `{ id, key, label, category }` |
| `additional_data` | object | JSON |
| `preferences` | object | JSON |
| `submitted_at`, `activated_at`, `suspended_at`, `created_at`, `updated_at` | ISO 8601 \| null | |
| `suspension_reason` | string | Shown to technician when suspended |
| `onboarding_progress` | object | See below |

**Admin-only additions**

| Field | Type | Notes |
|-------|------|--------|
| `user_id` | UUID | Auth user id |
| `user_status` | string | `User.status` (`pending`, `active`, `inactive`, …) |
| `review_notes` | string | Internal admin notes |
| `reviewed_by` | UUID \| null | Last reviewer user id |
| `reviewed_by_email` | string \| null | Resolved email |
| `reviewed_at` | ISO 8601 \| null | |

### `onboarding_progress` (detail)

Returned by `TechnicianProfile.get_onboarding_progress()`:

```json
{
  "status": "pending_onboarding",
  "is_eligible": false,
  "can_submit": false,
  "total_requirements": 5,
  "completed_requirements": 2,
  "missing_fields": [
    { "key": "phone", "label": "Phone number", "type": "user_field" }
  ],
  "completion_percentage": 40
}
```

### `onboarding_status` enum (`TechnicianProfile`)

| Value | Meaning |
|-------|---------|
| `pending_onboarding` | Not yet complete / not submitted |
| `submitted` | Waiting for operator review |
| `active` | Approved; can participate in job flows |
| `suspended` | Blocked by operator |

---

## Operator actions (mutations)

All **`POST`**, same auth as list. Body is JSON.

| Action | Path | Body |
|--------|------|------|
| Approve onboarding | `POST .../admin/technicians/{id}/approve/` | `{ "notes": "optional" }` |
| Request changes | `POST .../admin/technicians/{id}/request-changes/` | `{ "notes": "optional" }` |
| Suspend | `POST .../admin/technicians/{id}/suspend/` | `{ "reason": "required", "notes": "optional" }` |
| Reactivate | `POST .../admin/technicians/{id}/reactivate/` | `{ "notes": "optional" }` |

Successful responses return the **detail** technician object (same shape as `GET .../{id}/`).

---

## Reference data (pickers, onboarding UI)

Use these to build filters, region/skill selectors, or copy for onboarding checklists.

### Service regions

```http
GET /api/v1/technicians/service-regions/
```

**Response**

```json
{
  "regions": [
    { "id": 1, "key": "nj_essex_county", "name": "...", "short_name": "", "state": "NJ", "is_active": true }
  ],
  "grouped_by_state": { "NJ": [ /* same objects */ ] },
  "states": ["NJ", "..."]
}
```

### Skills (full job skill serializer)

```http
GET /api/v1/technicians/skills/
```

**Response**

```json
{
  "skills": [
    { "id": 1, "key": "standard_clean", "label": "...", "category": "...", "is_active": true }
  ],
  "grouped_by_category": { },
  "categories": ["..."]
}
```

### Onboarding requirements (static checklist metadata)

```http
GET /api/v1/technicians/onboarding-requirements/
```

**Response**

```json
{
  "requirements": [
    {
      "key": "first_name",
      "label": "First name",
      "type": "user_field",
      "required": true,
      "min_count": null
    }
  ]
}
```

`type` values include: `user_field`, `user_relation`, `profile_relation`, `profile_field` (see `ONBOARDING_REQUIREMENTS` in `apps/technicians/models.py`).

---

## Technician self-service (not operator list)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/technicians/me/` | Current user’s profile + progress |
| `PATCH` | `/api/v1/technicians/me/` | Update onboarding fields |
| `POST` | `/api/v1/technicians/me/submit/` | Submit for review |

These require an authenticated user with a **technician** role in your product model; the backend `IsTechnician` permission is currently a placeholder—confirm role checks in the SPA or tighten permissions on the API if needed.

---

## Related operator APIs (applications & forms)

If the UI links **applications** to **technicians** after conversion:

| Resource | Base path |
|----------|-----------|
| Technician applications | `/api/v1/admin/technician-applications/` |
| Application forms | `/api/v1/admin/application-forms/` |

See `README.md` (HTTP section) and `docs/APPLICATION_FORM_BUILDER_CODE.md` for application/form payloads.

---

## Error shape

Many endpoints return DRF validation errors as:

```json
{ "field_name": ["message"] }
```

or wrapped business errors:

```json
{ "error": { "code": "some_code", "message": "..." } }
```

Inspect `apps/technicians/views.py` for specific codes.

---

## Source of truth in code

| Area | Location |
|------|----------|
| URL routes | `apps/technicians/urls.py` |
| Admin list/detail & actions | `apps/technicians/views.py` → `TechnicianAdminViewSet` |
| Serializers | `apps/technicians/serializers.py` → `TechnicianListSerializer`, `TechnicianAdminDetailSerializer`, `TechnicianProfileReadSerializer` |
| Model fields & enums | `apps/technicians/models.py` → `TechnicianProfile`, `OnboardingStatus` |
