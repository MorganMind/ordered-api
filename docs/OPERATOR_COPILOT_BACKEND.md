# Operator Copilot Backend Contract

Base URL: `NEXT_PUBLIC_API_URL` + `/v1`

Auth: `Authorization: Bearer <access_token>`

Access: workspace operator/admin only (tenant-scoped).

---

## Endpoint

```http
POST /api/v1/operator/copilot/chat/
Content-Type: application/json
```

Request body:

```json
{
  "message": "what's at risk today?",
  "include_context": true,
  "dry_run": false,
  "tools": [
    {"type": "get_risk_summary"},
    {
      "type": "assign_technician",
      "input": {
        "job_id": "uuid",
        "technician_id": "uuid"
      }
    }
  ]
}
```

---

## Supported tools

- `get_risk_summary` (read)
  - Returns fresh operational context snapshot.
- `assign_technician` (write)
  - Input: `job_id`, `technician_id`
  - Assigns technician to a job; if job is `open`, status becomes `assigned`.
- `trigger_pricing` (write)
  - Input: `service_request_id`
  - Allowed when service request status is `new` or `reviewing`; creates price snapshot and sets status to `priced`.
- `approve_technician_application` (write)
  - Input: `application_id`, optional `reviewer_notes`
  - Approves a non-terminal technician application.

For write tools, `dry_run: true` validates and previews without mutating.

---

## Response shape

```json
{
  "assistant": {
    "message": "Processed 2 tool call(s): 2 succeeded, 0 failed. Use tool_results for details.",
    "message_type": "operational"
  },
  "context": {
    "snapshot": {
      "open_unassigned": 4,
      "assigned": 6,
      "in_progress": 3,
      "completed_today": 8,
      "at_risk_today": 2
    },
    "service_requests": {
      "new": 5,
      "reviewing": 2,
      "priced": 7
    },
    "technician_applications": {
      "new": 1,
      "reviewing": 2
    }
  },
  "tool_results": [
    {
      "ok": true,
      "type": "assign_technician",
      "data": {
        "job_id": "uuid",
        "status": "assigned",
        "technician_id": "uuid"
      }
    }
  ],
  "meta": {
    "dry_run": false,
    "tenant_id": "uuid",
    "generated_at": "2026-03-24T19:00:00Z"
  }
}
```

---

## Notes

- This endpoint is tool-based and deterministic: frontend should send explicit `tools[]` for writes.
- All reads/writes are tenant-filtered server-side.
- Write actions are event-logged for auditability.

