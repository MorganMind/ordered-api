# Jobs API — backend contract and frontend integration

Base URL: `NEXT_PUBLIC_API_URL` + `/v1` (e.g. `http://localhost:8000/api/v1`). Same Supabase JWT as other authenticated routes: `Authorization: Bearer <access_token>`.

Run migrations after deploy so `jobs.assigned_to` exists (`0006_job_assigned_to`).

---

## Summary

| Area | What to call |
|------|----------------|
| **List / detail / filter** | `GET /jobs/`, `GET /jobs/{id}/`, `GET /jobs/today/` |
| **Detail: next actions (UI)** | `GET /jobs/{id}/transitions/` (same idea as bookings) |
| **Operator: create job** | `POST /jobs/` (workspace staff only) |
| **Operator: edit job** | `PATCH /jobs/{id}/` (workspace staff only) |
| **Technician: lifecycle** | `POST /jobs/{id}/claim/`, `release/`, `start/`, `complete/` |
| **Create job from booking** | `POST /bookings/{id}/generate_job/` (existing; now emits an audit event) |
| **Create job from service request** | `POST /service-requests/{id}/convert-to-job/` |

---

## Job detail: transitions (avoid 404 on detail screen)

```http
GET /api/v1/jobs/{job_id}/transitions/
```

Same **shape** as **`GET /api/v1/bookings/{id}/transitions/`**:

```json
{
  "allowed_transitions": ["assigned", "cancelled"],
  "transitions": [
    {
      "name": "claim",
      "target": "assigned",
      "description": "Claim this job (technician) — POST …/claim/"
    },
    {
      "name": "assign",
      "target": "assigned",
      "description": "Assign a technician (operator) — PATCH job with assigned_to / status"
    },
    {
      "name": "cancel",
      "target": "cancelled",
      "description": "Cancel job — PATCH status to cancelled (workspace staff)"
    }
  ]
}
```

Use **`name`** / **`target`** to decide which buttons to show; enforce **permissions** in the client (technician vs operator). Terminal states (`completed`, `cancelled`) return empty **`allowed_transitions`** and **`transitions`**.

---

## Job status values

Use these string literals in UI and when PATCHing `status`:

| Value | Meaning |
|--------|---------|
| `open` | Unassigned (or released); available on the technician “board” if `assigned_to` is null |
| `assigned` | Someone is assigned; work not started |
| `in_progress` | Assigned tech has started |
| `completed` | Done |
| `cancelled` | Cancelled |

---

## JSON shape (`GET` / `PATCH` response)

Typical job object:

```json
{
  "id": "uuid",
  "tenant": "uuid",
  "title": "string",
  "status": "open",
  "assigned_to": null,
  "assigned_to_name": null,
  "booking_id": null,
  "booking_title": null,
  "scheduled_date": null,
  "scheduled_start_time": null,
  "scheduled_end_time": null,
  "address": "",
  "customer_name": "",
  "customer_phone": "",
  "customer_email": "",
  "service_request": null,
  "created_by": null,
  "created_at": "...",
  "updated_at": "..."
}
```

- **`booking_*`, `scheduled_*`, `address`, `customer_*`**: populated from the linked **booking** (`booking_id`). A **draft booking** is **auto-created** from the **service request** when a job is created or converted without an explicit `booking`, and before **assign / claim / start** when a booking is still missing but a `service_request` exists.
- **`service_request`**: UUID of the source service request when applicable.
- **`assigned_to`**: UUID of the technician user, or `null`.

List responses are a **JSON array** (no pagination wrapper on `/jobs/`).

Optional query param on `GET /jobs/`: **`?status=open`** (and other statuses).

---

## Permissions (who can do what)

- **Workspace staff** (`IsTenantWorkspaceStaff`): Django staff/superuser, `is_tenant_operator`, or `User.role` in `admin` / `"operator"`. Full job list for the tenant; **`PATCH /jobs/{id}/`**; **`POST .../convert-to-job/`**.
- **Technician** (`role === "technician"`): sees jobs **assigned to them** plus **open, unassigned** jobs in the tenant (claim board). May call **`claim` / `release` / `start` / `complete`** only if onboarding is **eligible** (active technician profile); otherwise **400** with `onboarding_status` / `missing_fields`. **`claim`** / **`start`** require a resolvable **booking** (existing or auto-created from **`service_request`**); jobs with neither link return **400**.
- **Client**: sees jobs they **created** or that are tied to their **service request**.

---

## Operator / workspace: create job

```http
POST /api/v1/jobs/
Content-Type: application/json

{
  "title": "Required",
  "status": "open",
  "booking": "<booking_uuid>",
  "service_request": "<service_request_uuid>",
  "assigned_to": "<technician_user_uuid>"
}
```

- **`title`**: required.
- **`status`**: optional; defaults to `open`. If **`assigned_to`** is set and you omit **`status`**, the API sets **`assigned`** (same idea as PATCH).
- **`booking`** or **`service_request`**: **at least one is required** (tenant-scoped UUIDs). If only **`service_request`** is set, the API creates a **draft** `Booking` from the SR (scheduled date from SR timing preference or **today**) and links it to the job.
- **`assigned_to`**: optional; must be a **technician** user in the tenant. Assigning triggers the same booking rule as PATCH (auto-create from SR when needed).

Response **201** with the full job object (same shape as `GET`).

---

## Operator / workspace: update job

```http
PATCH /api/v1/jobs/{job_id}/
Content-Type: application/json

{
  "title": "Optional new title",
  "status": "cancelled",
  "assigned_to": "<technician_user_uuid>"
}
```

- Assignee must be a user with **`role: "technician"`** in the same tenant.
- If you set **`assigned_to`** and omit **`status`**, the API sets **`status` to `assigned`** when the job was `open`. Clearing **`assigned_to`** (`null`) while the job was **`assigned`** sets **`status`** back to **`open`** if you did not send an explicit **`status`**.
- Before assigning or moving to **`assigned`** / **`in_progress`**, the job must have (or obtain via **`service_request`**) a linked **booking**; otherwise **400**.

---

## Technician actions

All are **`POST`** with an empty JSON body `{}` unless noted.

| Action | Path | Rules |
|--------|------|--------|
| Claim | `/api/v1/jobs/{id}/claim/` | Job must be `open` and `assigned_to` null; **booking** auto-created from **`service_request`** if needed |
| Release | `/api/v1/jobs/{id}/release/` | You must be assignee; job must be `assigned` (not started) |
| Start | `/api/v1/jobs/{id}/start/` | You must be assignee; status must be `assigned`; ensures **booking** exists (auto-create from SR if needed) |
| Complete | `/api/v1/jobs/{id}/complete/` | You must be assignee; status must be `in_progress` |

Success: **200** with the full job object (same shape as `GET`).

---

## Today’s jobs

```http
GET /api/v1/jobs/today/
```

Returns jobs in the **current user’s visible set** whose **`created_at`** date equals **today** in the server timezone. Prefer booking schedule fields in the UI when `booking_id` is set; this endpoint is intentionally simple until a dedicated “scheduled for” field exists on `Job`.

---

## Create jobs (existing + new)

**From a booking** (operator admin in this codebase):

```http
POST /api/v1/bookings/{booking_id}/generate_job/
```

**From a priced service request** (workspace staff):

```http
POST /api/v1/service-requests/{service_request_id}/convert-to-job/
Content-Type: application/json

{}
```

Optional body: `{ "title": "Override job title" }`.

- Service request must be in status **`priced`** and not already converted.
- On success: **201** + job body with **`booking_id`** set (draft booking from SR); service request becomes **`converted`** and exposes **`converted_job`** on service-request payloads as before.

---

## Frontend checklist

1. **Types**: model the job fields above; treat UUIDs as strings.
2. **Operator app**: list with `?status=` tabs; detail drawer; `PATCH` for assign/cancel; link to **convert-to-job** from priced service request detail.
3. **Technician app**: two logical lists — “Available” (`open` + `assigned_to == null`) and “Mine” (`assigned_to == me`), or a single list with sections; wire **claim → start → complete**; handle **400** eligibility errors on those actions.
4. **Error handling**: **409** on convert when not priced or already converted; **404** on technician actions for jobs outside tenant or invisible queryset.

---

## Related docs

- Service requests / pricing: `SERVICE_REQUEST_README.md`, `docs/OPERATOR_INBOX_FRONTEND.md`
- Technician inbox (threads may reference `job_id` / `job_title`): `docs/TECHNICIAN_INBOX_BACKEND.md`
