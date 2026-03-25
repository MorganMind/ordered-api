# Service offerings and intake (frontend)

Tenant-scoped **service offerings** (custom bookable services) live under **`/api/v1/service-offerings/`**. Each offering can attach **ordered** rows from the global **Skill** catalog (`jobs.Skill`). **Service requests** can reference an offering via **`service_offering`**; the API still stores a legacy **`service_type`** enum on the row for reporting and pricing compatibility.

**Base URL:** `NEXT_PUBLIC_API_URL` + `/api/v1` (same as other app APIs).

**Auth:** `Authorization: Bearer <Supabase JWT>` (or session, per your app).

List responses are **plain JSON arrays** (no `results` wrapper) unless you add pagination globally later.

---

## Concepts

| Concept | Meaning |
|--------|---------|
| **Service offering** | One row per tenant: display name, slug, optional description, active flag, sort order, **reporting category**. |
| **Reporting category** | One of the fixed **`service_type`** enum values (see below). When a customer picks an offering, the API sets **`ServiceRequest.service_type`** to this value. |
| **Nested skills** | Offerings link to **catalog** skills by UUID. Order in **`skill_ids`** is the display / logic order. Only **active** skills are accepted. |
| **Intake** | Either send legacy **`service_type`** alone, or send **`service_offering`** (UUID). If both are sent with an offering, **`service_type`** must match the offering’s **`reporting_category`** or be omitted. |

### `reporting_category` / `service_type` values

Same enum everywhere (string values):

| Value | Label (human) |
|-------|----------------|
| `standard_cleaning` | Standard Cleaning |
| `deep_clean` | Deep Clean |
| `organizing` | Organizing |
| `move_in_out` | Move In / Move Out |
| `post_construction` | Post Construction |
| `other` | Other |

Custom offering **names** are free-form; **reporting_category** buckets them for filters and pricing inputs.

---

## Permissions

| Endpoint / method | Who |
|-------------------|-----|
| **`GET /api/v1/service-offerings/`**, **`GET .../{id}/`** | Any authenticated user with a **tenant** (`tenant_id` on user) — same as other tenant-member flows. |
| **`POST`**, **`PATCH`**, **`DELETE`** on offerings | **Workspace staff**: Django **`is_staff`** / **`is_superuser`**, or **`is_tenant_operator`**, or **`role`** in **`admin`** / **`operator`** (`IsTenantWorkspaceStaff`). |

If operator users only have a JWT claim and **not** the Django `User.role` / flags above, they may get **403** on write routes until the backend aligns permissions.

---

## List offerings

```http
GET /api/v1/service-offerings/
```

### Query parameters

| Param | Effect |
|-------|--------|
| `is_active` | `true` / `false` — filter by active flag. |
| `slug` | Exact slug match. |
| `ordering` | One of `sort_order`, `name`, `created_at`; prefix `-` for descending. Default: `sort_order`, then `name`. |

### Response: array of offerings

Each element:

| Field | Type | Notes |
|-------|------|--------|
| `id` | UUID | Primary key — use on intake as **`service_offering`**. |
| `tenant` | UUID | Tenant id. |
| `name` | string | Customer-facing label. |
| `slug` | string | Stable key per tenant (URL-safe). |
| `description` | string | May be empty. |
| `is_active` | boolean | Inactive offerings should be hidden in booking UI; API still rejects them on create if used (see intake). |
| `sort_order` | number | Display order (lower first). |
| `reporting_category` | string | Enum value above. |
| `skills` | array | Ordered nested skills (see below). |
| `created_at`, `updated_at` | ISO 8601 | |

#### Nested `skills[]` object

| Field | Type |
|-------|------|
| `id` | UUID (skill id) |
| `key` | string |
| `label` | string |
| `category` | string |
| `is_active` | boolean |
| `sort_order` | number (order within this offering) |

---

## Get one offering

```http
GET /api/v1/service-offerings/{id}/
```

Same shape as a list element.

**404** if the id is not in the user’s tenant (or user has no tenant).

---

## Create offering (workspace staff)

```http
POST /api/v1/service-offerings/
Content-Type: application/json
```

### Body

| Field | Required | Notes |
|-------|----------|--------|
| `name` | yes | |
| `slug` | yes | Unique **per tenant**. |
| `description` | no | Default empty. |
| `is_active` | no | Default `true`. |
| `sort_order` | no | Default `0`. |
| `reporting_category` | no | Default `other`. |
| `skill_ids` | no | Array of **UUID** strings; **order preserved**. Each id must be a unique **active** catalog skill. Omit or `[]` for no skills. |

### Response

**201** with the **full read** representation (same as GET), including generated **`id`** and nested **`skills`**.

### Errors

- **400** — validation (e.g. duplicate `slug`, invalid `skill_ids`).
- **403** — not workspace staff.

---

## Update offering (workspace staff)

```http
PATCH /api/v1/service-offerings/{id}/
Content-Type: application/json
```

Send only fields to change. **`skill_ids`**: if the key is present, the API **replaces** all skill links with the new ordered list. If you omit **`skill_ids`**, existing links are unchanged.

**200** with full read representation.

**PUT** is not registered; use **PATCH** (or the view’s **update** path, which delegates to partial update).

---

## Delete offering (workspace staff)

```http
DELETE /api/v1/service-offerings/{id}/
```

Typical **204** or **200** per DRF configuration. Existing **service requests** that pointed at this offering have **`service_offering`** cleared (**`SET_NULL`**); **`service_type`** on those rows is **unchanged**, so history and reporting stay consistent.

---

## Skill catalog (pick UUIDs for `skill_ids`)

Global skills are not tenant-specific. To populate a multi-select for **`skill_ids`**:

```http
GET /api/v1/technicians/skills/
```

Returns **`skills`** (flat list) and **`grouped_by_category`**. Each skill includes **`id`** (UUID) — use those values in **`skill_ids`**.

Requires **`IsAuthenticated`** only.

---

## Service requests (intake) — `service_offering`

Existing endpoint:

```http
POST /api/v1/service-requests/
```

### Create rules

1. Send **`service_offering`**: UUID of an offering in **the same tenant**, and **`is_active`** on the offering.
2. **Either** omit **`service_type`**, **or** set it equal to the offering’s **`reporting_category`**.
3. **Or** omit **`service_offering`** and send **`service_type`** only (legacy).

The server sets **`service_type`** from the offering’s **`reporting_category`** when **`service_offering`** is present.

### Read fields on service request

| Field | Notes |
|-------|--------|
| `service_type` | Enum string (always set). |
| `service_offering` | Nested brief offering + **`skills`**, or `null`. |
| `service_label` | Human label: offering **`name`** if linked, else the enum display label. |

Use **`service_label`** for headings and job titles in UI; use **`service_offering.id`** for editing or re-fetching the full offering.

### Patch (client / operator)

**`service_offering`** may be updated on PATCH subject to the same tenant and active rules. Setting **`service_offering`** to a non-null value forces **`service_type`** to that offering’s **`reporting_category`**. Setting it to **`null`** clears the link; **`service_type`** remains as stored.

---

## Suggested UI flows

1. **Operator settings — services**  
   List **`GET /service-offerings/`** (optionally `?is_active=true`). Create/edit with POST/PATCH; load skill choices from **`GET /technicians/skills/`**.

2. **Booking / intake form**  
   Load active offerings, sort client-side by **`sort_order`** then **`name`**. Submit **`service_offering`** as UUID. Show nested **`skills`** as chips or “what’s included” if needed.

3. **Service request detail**  
   Show **`service_label`**; expand **`service_offering`** when you need slug, reporting bucket, or skill list.

---

## Pricing note

Price snapshot **`inputs_used`** includes **`service_offering_id`** when the request had an offering at pricing time. The placeholder engine still keys off **`service_type`**; future engines can branch on **`service_offering_id`**.
