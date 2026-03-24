# Technician application emails — frontend notes

When someone submits a **public** application (`POST /api/v1/forms/{formId}/apply/` or legacy `POST /api/v1/tenants/{tenantId}/apply/`), the API sends:

1. **Applicant** — HTML + plain text to the email they entered.
2. **Operator** — HTML + plain text to the tenant’s **`operator_admin_email`**, if that field is set.

Email delivery uses Django’s configured backend (e.g. **Resend** when `RESEND_API_KEY` is set). Failures are logged; the HTTP response stays **201**.

---

## Read the current operator inbox address

**`GET /api/v1/auth/me`**

Under `tenant`, the API now includes:

- **`operator_admin_email`**: string or `null` (empty in DB is returned as `null` for convenience in JSON).

Your existing `mapMeResponseFromApi` / tenant types should add an optional field, e.g. `operatorAdminEmail`.

---

## Update the operator admin email (operator app)

**`GET /api/v1/tenants/me/notification-settings/`**  
**`PATCH /api/v1/tenants/me/notification-settings/`**

- **Auth:** Bearer JWT (same as the rest of the operator API).
- **Permission:** workspace staff — same idea as operator inbox (`is_tenant_operator`, Django staff, or `role` `admin` / `"operator"`).

**PATCH body (JSON):**

```json
{ "operator_admin_email": "dispatch@yourcompany.com" }
```

Use `""` or omit to clear (serializer accepts blank).

**Response:** `{ "operator_admin_email": "..." }`

**Base URL:** Remember the API prefix is **`/api/v1`** (e.g. `https://api.orderedhq.com/api/v1/tenants/me/notification-settings/`).

---

## UI suggestions

- Settings page: label e.g. “Application notification email”, help text that this address receives a copy when **public** applications are submitted.
- After save, optionally refresh **`/auth/me`** if other screens read `tenant.operator_admin_email` from there.

---

## Super-admins / Django

- **`TenantViewSet`** (`IsAdmin`) includes **`operator_admin_email`** in the full tenant serializer for staff who manage tenants via **`/api/v1/tenants/{id}/`**.
- Django **admin** → Tenants: **`operator_admin_email`** is editable in the list/search surface.

---

## Backend reference

- Model: `apps.tenants.models.Tenant.operator_admin_email`
- Emails: `apps/technicians/application_emails.py`, templates under `apps/technicians/templates/technicians/email/`
- `/auth/me`: `api_auth/me_response.py` (`enrich_tenant_for_auth_me`)
