# Operator Dashboard Backend Contract

Base URL: `NEXT_PUBLIC_API_URL` + `/v1`

Auth: `Authorization: Bearer <access_token>`

Audience: workspace operators/admins only.

---

## Endpoint

```http
GET /api/v1/operator/dashboard/
```

Optional query params:

- `limit` (default `7`, min `1`, max `20`) for list sizes
- `soon_hours` (default `4`, min `1`, max `24`) for soon/at-risk windows
- `stale_unassigned_hours` (default `4`, min `1`, max `72`)
- `stalled_hours` (default `2`, min `1`, max `72`)

---

## Response shape

```json
{
  "generated_at": "2026-03-24T18:22:00Z",
  "snapshot": {
    "open_jobs_unassigned": {
      "count": 12,
      "job_filter": {"status": "open", "assigned_to__isnull": true}
    },
    "assigned_jobs": {
      "count": 9,
      "job_filter": {"status": "assigned"}
    },
    "in_progress_jobs": {
      "count": 6,
      "job_filter": {"status": "in_progress"}
    },
    "overdue_or_at_risk_jobs": {
      "count": 4,
      "job_filter": {
        "status__in": ["open", "assigned", "in_progress"],
        "schedule_state": "overdue_or_starting_soon",
        "soon_hours": 4
      }
    },
    "completed_today": {
      "count": 15,
      "job_filter": {"status": "completed", "updated_at__date": "2026-03-24"}
    }
  },
  "today_action_data": {
    "jobs_needing_assignment_soon": {
      "sort": "scheduled_date_asc_then_start_time_asc",
      "items": []
    },
    "jobs_currently_in_progress": {
      "sort": "oldest_status_update_first",
      "items": []
    },
    "recently_completed_jobs": {
      "sort": "recently_completed_first",
      "items": []
    }
  },
  "attention_items": [
    {
      "type": "starting_soon_without_technician",
      "severity": "critical",
      "reference": {"job_id": "uuid"},
      "message": "Job 'Kitchen deep clean' starts soon but has no technician assigned.",
      "action": {"type": "assign_technician", "job_id": "uuid"}
    }
  ],
  "cross_system_summary": {
    "new_service_requests": {
      "count": 8,
      "filter": {"status": "new"}
    },
    "pending_price_reviews": {
      "count": 5,
      "filter": {"status": "reviewing"}
    },
    "technician_applications_pending": {
      "count": 3,
      "filter": {"status__in": ["new", "reviewing"]}
    },
    "unread_inbox_threads": {
      "count": 2,
      "filter": {"has_unread": true}
    }
  },
  "quick_actions": {
    "create_service_request": {"method": "POST", "path": "/api/v1/service-requests/"},
    "create_job": {"method": "POST", "path": "/api/v1/jobs/"},
    "assign_technician": {"method": "PATCH", "path": "/api/v1/jobs/{job_id}/"},
    "approve_technician": {"method": "POST", "path": "/api/v1/admin/technician-applications/{application_id}/approve/"},
    "trigger_pricing": {"method": "POST", "path": "/api/v1/service-requests/{service_request_id}/price/"}
  }
}
```

---

## Item payload (`today_action_data.*.items[]`)

Each item is intentionally minimal:

- `job_id`
- `title`
- `status`
- `scheduled_date`
- `scheduled_start_time`
- `scheduled_end_time`
- `technician` (`id`, `name`) or `null`
- `location.address`
- `service_request_id`
- `updated_at`

---

## Notes

- All values are tenant scoped and computed server-side.
- Frontend should treat `job_filter` / `filter` objects as deep-link hints.
- This endpoint is an operational summary, not a full dataset replacement.

