# Technician app — self-service settings and profile

This document lists what a **technician** (`User.role === "technician"`) can **read and change** via the Ordered API, and how the mobile/web technician app should call it.

**Base URL:** `{API_ORIGIN}/api/v1` (e.g. `https://api.example.com/api/v1`).

**Auth:** `Authorization: Bearer <Supabase access_token>` on every request below.

---

## 1. Profile and “settings” the technician controls

The main surface is **`/technicians/me/`**. The backend stores data on the linked **`User`** and **`TechnicianProfile`**.

### Read current profile

```http
GET /api/v1/technicians/me/
```

Returns (among other fields): `email`, `first_name`, `last_name`, `full_name`, `phone`, `onboarding_status`, `is_eligible`, `can_submit`, `skills`, `service_regions`, `additional_data`, `preferences`, `suspension_reason`, `onboarding_progress`, timestamps.

- **`email`** is **read-only** here (comes from auth / `User`; changing it is an **account** concern—typically **Supabase Auth** or your identity flow, not this PATCH).
- **`onboarding_status`**, **`suspension_reason`**, review timestamps, etc. are **controlled by operators**; the app should **display** them, not offer edits except where PATCH allows.

### Update profile / preferences (PATCH)

```http
PATCH /api/v1/technicians/me/
Content-Type: application/json
```

**Allowed body fields** (all optional; send only what changed):

| JSON field | Type | What it updates |
|------------|------|------------------|
| `first_name` | string | `User.first_name` |
| `last_name` | string | `User.last_name` |
| `phone` | string | `User.phone` |
| `skill_ids` | array of UUID strings | **Replaces** the technician’s skills with this set (must exist and be **active**; IDs match `GET /technicians/skills/` → `id` / `pk`) |
| `service_region_ids` | array of integers | **Replaces** profile service regions with this set (must exist and be **active**; IDs match `GET /technicians/service-regions/` → `regions[].id`) |
| `additional_data` | object | **Merged** into existing `TechnicianProfile.additional_data` (shallow merge: top-level keys you send overwrite or add) |
| `preferences` | object | **Merged** into existing `TechnicianProfile.preferences` (same merge semantics) |

**Examples**

```json
{ "first_name": "Alex", "last_name": "Rivera", "phone": "+15551234567" }
```

```json
{
  "skill_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "service_region_ids": [1, 3]
}
```

```json
{
  "preferences": {
    "notifications_push": true,
    "availability_notes": "Prefer mornings"
  }
}
```

**Response:** **200** with the same shape as **GET** (full profile + `onboarding_progress`).

**Validation errors:** invalid skill UUIDs or inactive skills → **`skill_ids`** error; invalid region IDs → **`service_region_ids`** error. DRF may return `{ "skill_ids": ["..."] }`.

### Eligibility side effects (important for UX)

Required onboarding is defined in **`ONBOARDING_REQUIREMENTS`** (see `GET /technicians/onboarding-requirements/`). If a technician who was **`active`** or **`submitted`** removes or clears required data (e.g. empty `skill_ids` or `phone`):

- Status may be moved back to **`pending_onboarding`** (and `submitted_at` cleared if they were submitted).
- The app should **refresh** from GET after PATCH and show **`onboarding_progress.missing_fields`** until fixed.

---

## 2. Submit profile for operator review

When **`onboarding_status`** is **`pending_onboarding`**, required fields are complete, and the product flow allows it:

```http
POST /api/v1/technicians/me/submit/
Content-Type: application/json

{}
```

- **Body:** empty object is fine (no required fields).
- **Success:** **200** + full profile shape; status becomes **`submitted`** when the service accepts it.
- **Errors:** wrong status or incomplete onboarding → **400** with `error.code` such as `invalid_status` or `onboarding_incomplete` (see `TechnicianSubmitSerializer` / `TechnicianSubmitView`).

---

## 3. Reference data (for pickers before PATCH)

Use these **read-only** endpoints to build skill and region selectors (no auth role restriction beyond authenticated user in current code; still send Bearer token).

| GET | Purpose |
|-----|---------|
| `/api/v1/technicians/skills/` | `skills`, `grouped_by_category`, `categories` |
| `/api/v1/technicians/service-regions/` | `regions`, `grouped_by_state`, `states` |
| `/api/v1/technicians/onboarding-requirements/` | Static checklist metadata (`requirements[]` with `key`, `label`, `type`, `required`, …) |

---

## 4. Inbox: pin a thread (not profile JSON, but user-controlled)

Technicians can toggle whether a conversation is pinned:

```http
PATCH /api/v1/technicians/me/inbox/threads/{thread_id}/
Content-Type: application/json

{ "is_pinned": true }
```

**Response:** **200** with the thread object (same shape as list/detail). See **`docs/TECHNICIAN_INBOX_BACKEND.md`** for threads, messages, mark-read, and start-thread.

---

## 5. Jobs (work actions, not “settings”)

Technicians manage **work** via **`/jobs/`** (list, claim, start, complete, etc.). That is separate from profile settings. See **`docs/JOBS_API_FRONTEND.md`**.

---

## 6. Profile photo (all roles, shared API)

Avatar is on **`users.User`**, not the technician profile PATCH. Use **`GET` / `PATCH` `/api/v1/users/me/`** and **`POST` / `DELETE` `/api/v1/users/me/avatar/`** — same routes for clients and operators. See **`docs/USER_AVATAR_FRONTEND.md`**.

---

## 7. What technicians cannot change through this API

| Item | Notes |
|------|--------|
| **Email / password** | Use **Supabase Auth** (or your auth provider). `GET /api/v1/auth/me/` is **GET-only** for session/tenant context. |
| **Role, tenant** | Not exposed for self-service mutation on these routes. |
| **Onboarding status** (approve / suspend / reactivate) | Operator **`/api/v1/admin/technicians/...`** actions only. |
| **`review_notes`, admin-only fields** | Not in technician serializers. |

---

## 8. Suggested technician “Settings” screen flow

1. On screen open: **`GET /technicians/me/`** — populate form from `first_name`, `last_name`, `phone`, `skills`, `service_regions`, `preferences`, `additional_data`.
2. Load pickers: **`GET /technicians/skills/`** and **`GET /technicians/service-regions/`** (cache if needed).
3. On save: **`PATCH /technicians/me/`** with changed fields only; then replace local state with the response.
4. If `can_submit` is true and the user taps “Submit for review”: **`POST /technicians/me/submit/`**.
5. Link “Account / email” to your **Supabase** profile or password UI, not Django PATCH.
6. Optional: **`onboarding_progress`** drives a checklist UI alongside **`GET /technicians/onboarding-requirements/`**.

---

## Source of truth in code

| Piece | Location |
|-------|-----------|
| Routes | `apps/technicians/urls.py` |
| GET/PATCH me | `TechnicianMeView` in `apps/technicians/views.py` |
| PATCH fields | `TechnicianOnboardingUpdateSerializer` in `apps/technicians/serializers.py` |
| Submit | `TechnicianSubmitView`, `TechnicianSubmitSerializer` |
| Requirements registry | `ONBOARDING_REQUIREMENTS` in `apps/technicians/models.py` |

Broader operator vs technician API overview: **`docs/TECHNICIANS_API_FRONTEND.md`**.
