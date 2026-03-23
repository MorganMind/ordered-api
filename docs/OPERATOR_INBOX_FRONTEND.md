# Operator inbox — backend API and **ordered-operator** (Next.js) integration

The operator workspace app lives beside this repo: **`../ordered-operator`**. It already uses Supabase JWT auth and `buildApiUrl()` / `apiRequest()` in `lib/api.ts` and `lib/api-client.ts`.

This document describes the **new** operator inbox endpoints (same database tables as the technician inbox) and exactly how to wire them in **ordered-operator**.

---

## Backend summary

- **Tables:** Reuses `TechnicianInboxThread`, `TechnicianInboxMessage`, `TechnicianInboxMessageReceipt` (see `apps/technicians/inbox_models.py`).
- **Scope:** Non–staff operators see threads where **`operator_contact`** is the logged-in user. **Django staff or superuser** sees **all** inbox threads in the tenant (for support / debugging).
- **Auth:** `Authorization: Bearer <supabase_access_token>` (same as jobs, applications, etc.).
- **Permission:** `IsOperatorInboxUser` — tenant operator (`is_tenant_operator`), staff, superuser, or `User.role` in `admin` / `"operator"` (`apps/technicians/operator_inbox_permissions.py`).

**Base path:** all routes below are under `NEXT_PUBLIC_API_URL` + `/v1`, e.g. `http://localhost:8000/api/v1` if your env is `http://localhost:8000/api`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/operator/inbox/threads/` | List threads (pinned first, then `last_activity_at`). |
| PATCH | `/operator/inbox/threads/{thread_id}/` | Update `is_pinned`. |
| GET | `/operator/inbox/threads/{thread_id}/messages/` | List messages (oldest first). |
| POST | `/operator/inbox/threads/{thread_id}/messages/` | Send reply (`{"body": "..."}`). |
| POST | `/operator/inbox/threads/{thread_id}/mark-read/` | Mark others’ messages read (204, no body). |
| GET | `/operator/inbox/technicians/` | Technicians on the tenant + optional `existing_thread_id` for **this** operator. |
| POST | `/operator/inbox/threads/start/` | Start or reuse direct thread with a technician + first message. |

---

## JSON shapes (match technician inbox)

Thread list / detail items use the **same field names** as `docs/TECHNICIAN_INBOX_BACKEND.md`, plus one extra id:

- **`technician_id`** (UUID string): the technician user id for navigation (e.g. `/technicians/{id}`).
- **`title`**, **`participant_name`**, **`participant_avatar_url`**: for the operator UI these are **derived from the technician** (not from stored thread title, which is optimized for the technician app).
- **`subtitle`**: `"Direct message"` for `operator_direct` without a job; otherwise often the **job title** if `job_id` is set.
- **`last_message`**, **`unread_count`**, **`thread_type`**, **`sender_type`**, etc.: same semantics as the technician doc.

**Start thread (operator):**

```http
POST /api/v1/operator/inbox/threads/start/
Content-Type: application/json

{"technician_id": "<uuid>", "body": "First message"}
```

Response: **201** if a new row was created, **200** if an existing `operator_direct` thread for this pair was reused. Body is a **thread** object (same shape as list items).

**Send message:**

```http
POST /api/v1/operator/inbox/threads/{thread_id}/messages/
Content-Type: application/json

{"body": "..."}
```

**Technicians directory (compose UI):**

```json
[
  {
    "id": "...",
    "first_name": "Alex",
    "last_name": "Tech",
    "full_name": "Alex Tech",
    "avatar_url": null,
    "has_existing_thread": true,
    "existing_thread_id": "550e8400-..."
  }
]
```

---

## Implementing in **ordered-operator**

### 1. Types (`types/index.ts` or a dedicated `types/inbox.ts`)

Mirror the technician doc types; add `technician_id` on thread types:

```ts
export type InboxThreadType = "operator_direct" | "client_job" | "system_alert";
export type InboxSenderType = "operator" | "client" | "system" | "technician";

export interface InboxMessage {
  id: string;
  thread_id: string;
  sender_name: string;
  sender_type: InboxSenderType;
  body: string;
  timestamp: string;
  is_read: boolean;
  job_id: string | null;
  job_title: string | null;
}

export interface OperatorInboxThread {
  id: string;
  title: string;
  subtitle: string;
  thread_type: InboxThreadType;
  participant_name: string;
  participant_avatar_url: string | null;
  technician_id: string;
  last_message: InboxMessage | null;
  unread_count: number;
  last_activity_at: string;
  job_id: string | null;
  job_title: string | null;
  is_pinned: boolean;
}

export interface TechnicianInboxRecipient {
  id: string;
  first_name: string;
  last_name: string;
  full_name: string;
  avatar_url: string | null;
  has_existing_thread: boolean;
  existing_thread_id: string | null;
}
```

### 2. API client (`lib/api-client.ts`)

Follow existing patterns: import `buildApiUrl` and `buildHeaders` from `./api` and use the same private `apiRequest<T>` as `JobsApiClient` (Bearer token, 401 sign-out).

Add a small class (constructor can accept `_tenantId` for consistency with other clients; **tenant is implied by the JWT**, so you do not need to pass tenant in the path):

```ts
import { buildApiUrl, buildHeaders } from "./api";

export class OperatorInboxApiClient {
  async listThreads(): Promise<OperatorInboxThread[]> {
    const url = buildApiUrl("/operator/inbox/threads/");
    return apiRequest<OperatorInboxThread[]>(url);
  }

  async patchThread(
    threadId: string,
    body: { is_pinned: boolean }
  ): Promise<OperatorInboxThread> {
    const url = buildApiUrl(`/operator/inbox/threads/${threadId}/`);
    return apiRequest<OperatorInboxThread>(url, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }

  async listMessages(threadId: string): Promise<InboxMessage[]> {
    const url = buildApiUrl(`/operator/inbox/threads/${threadId}/messages/`);
    return apiRequest<InboxMessage[]>(url);
  }

  async sendMessage(threadId: string, body: string): Promise<InboxMessage> {
    const url = buildApiUrl(`/operator/inbox/threads/${threadId}/messages/`);
    return apiRequest<InboxMessage>(url, {
      method: "POST",
      body: JSON.stringify({ body }),
    });
  }

  async markRead(threadId: string): Promise<void> {
    const url = buildApiUrl(`/operator/inbox/threads/${threadId}/mark-read/`);
    const res = await fetch(url, {
      method: "POST",
      headers: buildHeaders(),
    });
    // 204 empty body. On 401, mirror `apiRequest` in lib/api-client.ts (sign out + redirect).
    if (!res.ok) {
      throw new Error(`mark-read failed: ${res.status}`);
    }
  }

  async listTechnicianRecipients(): Promise<TechnicianInboxRecipient[]> {
    const url = buildApiUrl("/operator/inbox/technicians/");
    return apiRequest<TechnicianInboxRecipient[]>(url);
  }

  async startThread(
    technicianId: string,
    body: string
  ): Promise<OperatorInboxThread> {
    const url = buildApiUrl("/operator/inbox/threads/start/");
    return apiRequest<OperatorInboxThread>(url, {
      method: "POST",
      body: JSON.stringify({ technician_id: technicianId, body }),
    });
  }
}
```

For **`markRead`**, use `fetch` + `buildHeaders()` from `lib/api.ts` (see `ApplicationFormsApiClient.deleteField` in `lib/api-client.ts` for 401 handling), because the API returns **204** with no JSON.

### 3. UI flow (recommended)

1. **Inbox index:** `GET /operator/inbox/threads/` — show title (`technician`), subtitle, `unread_count`, `last_message.body`, `last_activity_at`.
2. **Open thread:** `GET .../messages/`, then `POST .../mark-read/` (same as technician app).
3. **Composer:** `POST .../messages/` with `{ body }`.
4. **New chat:** `GET /operator/inbox/technicians/` — if `has_existing_thread`, navigate to `existing_thread_id`; else `startThread(id, initialBody)`.

Optional: link from a thread row to **`/technicians/{technician_id}`** using the returned `technician_id`.

### 4. CORS and env

- Ensure **`NEXT_PUBLIC_API_URL`** matches the Django origin you use for other admin calls (see `ordered-operator/docs/DEV-SETUP.md` and `docs/backend/README-DJANGO-DRF-JWT.md`).
- Django must list the operator web origin in **`CORS_ALLOWED_ORIGINS`** (see `ordered-api/.env.example`). Production example: `https://operator.orderedhq.com` when the API is `https://api.orderedhq.com`. With `DEBUG=False`, omitting this yields a browser CORS error even if the API returns 200.

### 5. Errors

- **403:** User is not allowed as an operator inbox user (role / flags). Do **not** treat as session expiry (your `api-client` already avoids signing out on 403).
- **404:** Thread not in scope (wrong id or not `operator_contact` for this user).

---

## Related code in **ordered-api**

| Piece | Location |
|--------|-----------|
| Operator views | `apps/technicians/operator_inbox_views.py` |
| URL routes | `apps/technicians/urls.py` (`operator/inbox/...`) |
| Thread JSON (operator) | `OperatorInboxThreadSerializer` in `apps/technicians/inbox_serializers.py` |
| Shared unread logic | `apps/technicians/inbox_helpers.py` |
| Tests | `apps/technicians/tests/test_operator_inbox_views.py` |
| Technician reference | `docs/TECHNICIAN_INBOX_BACKEND.md` |

---

## Smoke check (curl)

Replace `TOKEN` and host with your values:

```bash
curl -sS -H "Authorization: Bearer TOKEN" \
  http://localhost:8000/api/v1/operator/inbox/threads/
```

You should receive a JSON array (possibly empty).
