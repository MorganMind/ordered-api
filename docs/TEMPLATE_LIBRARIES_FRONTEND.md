# Template libraries (services + forms)

This guide covers the new **template-first** flows:

- Service offering templates (tenant service catalog bootstrap)
- Application form templates (including cleaning questionnaire defaults)

Base URL: `NEXT_PUBLIC_API_URL` + `/api/v1`

---

## 1) Service offering templates

Use these when operators set up tenant services quickly.

### List service templates

```http
GET /api/v1/service-offerings/templates/
```

- Auth: tenant member (authenticated + `tenant_id`)
- Response:

```json
{
  "templates": [
    {
      "key": "cleaning_deep",
      "name": "Deep Cleaning",
      "description": "...",
      "reporting_category": "deep_clean",
      "suggested_skill_keys": ["deep_cleaning", "..."]
    }
  ]
}
```

### Create tenant offering from template

```http
POST /api/v1/service-offerings/from-template/
Content-Type: application/json
```

Body:

```json
{
  "template_key": "cleaning_deep",
  "name": "Deep Clean Plus",
  "slug": "deep-clean-plus"
}
```

Optional overrides: `description`, `is_active`, `sort_order`, `reporting_category`, `skill_keys`.

Response:

```json
{
  "template_key": "cleaning_deep",
  "service_offering": { "...full offering payload..." },
  "unresolved_skill_keys": []
}
```

If `unresolved_skill_keys` is non-empty, those skill keys were not found in the active skill catalog.

---

## 2) Application form template library

Template library is under admin forms routes.

### List form templates

```http
GET /api/v1/admin/application-forms/templates/
```

- Auth: admin/staff (`IsAdmin`)
- Response includes template metadata + default `fields_schema`.

### Create form from template

```http
POST /api/v1/admin/application-forms/from-template/
Content-Type: application/json
```

Body:

```json
{
  "template_key": "cleaning_technician_intake_v1",
  "title": "Cleaning Technician Application"
}
```

Optional: `slug`, `description`, `status`, `settings`, `fields_schema` (full override).

Response:

```json
{
  "template_key": "cleaning_technician_intake_v1",
  "form": { "...ApplicationForm detail payload..." }
}
```

### Start from scratch

Two ways are supported:

1. Existing create endpoint:

```http
POST /api/v1/admin/application-forms/
```

2. Explicit scratch helper:

```http
POST /api/v1/admin/application-forms/from-scratch/
```

Body example:

```json
{
  "title": "Custom Technician Form",
  "fields_schema": []
}
```

---

## Cleaning template fields included

Template key: `cleaning_technician_intake_v1`

**Built-in fields** on `POST /forms/{id}/apply/` (not in `fields_schema`): **name, email, phone**, and **applicant type** — do not duplicate those as custom questions.

Applicant-facing `fields_schema` in this template:

1. **County / area** (required, short text) — freeform, e.g. “Essex County, NJ”
2. **Availability** (required, multi-select) — weekdays, weekends, evenings, flexible
3. **Hours per week** (optional, number)
4. **Experience** (required, textarea)
5. **Work types** (required, multi-select) — standard, deep, organizing, move-in/out, other

Copy (titles, descriptions, placeholders) is written for **applicants**, not internal operators.

**Older forms** that still have **`full_name_phone`**, duplicate applicant-type questions, or a county **dropdown** placeholder: edit the form in the admin builder or recreate from this template.

---

## Frontend implementation checklist

- Build a **template picker** in:
  - Service settings (create offering)
  - Admin application forms (create form)
- Keep a **Start from scratch** CTA next to **Use template**.
- After template creation, open edit view immediately so operators can adjust labels or switch the county field to a curated dropdown if they prefer.
- For service templates, if `unresolved_skill_keys.length > 0`, show a warning with missing keys.
- For form templates, default status should stay `draft`; require explicit publish/activate.
