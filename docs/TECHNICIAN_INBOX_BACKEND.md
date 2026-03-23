# Technician inbox — backend reference

Base path: `/api/v1/` (see `ordered_api/urls.py`).

---

## Endpoints

```http
GET /api/v1/technicians/me/inbox/threads/
Authorization: Bearer <token>
```

```http
GET /api/v1/technicians/me/inbox/threads/{thread_id}/messages/
Authorization: Bearer <token>
```

```http
POST /api/v1/technicians/me/inbox/threads/{thread_id}/messages/
Authorization: Bearer <token>
Content-Type: application/json

{"body": "string"}
```

```http
POST /api/v1/technicians/me/inbox/threads/{thread_id}/mark-read/
Authorization: Bearer <token>
```

```http
PATCH /api/v1/technicians/me/inbox/threads/{thread_id}/
Authorization: Bearer <token>
Content-Type: application/json

{"is_pinned": true}
```

---

## Response shapes (Flutter `fromJson`)

Thread list item:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Dispatch Team",
  "subtitle": "Operator messages",
  "thread_type": "operator_direct",
  "participant_name": "Sarah",
  "participant_avatar_url": "https://example.com/a.png",
  "last_message": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
    "sender_name": "Sarah",
    "sender_type": "operator",
    "body": "Hey, just wanted to confirm…",
    "timestamp": "2025-03-22T15:04:05.123456Z",
    "is_read": false,
    "job_id": null,
    "job_title": null
  },
  "unread_count": 2,
  "last_activity_at": "2025-03-22T15:04:05.123456Z",
  "job_id": null,
  "job_title": null,
  "is_pinned": true
}
```

`thread_type`: `operator_direct` | `client_job` | `system_alert`

Message:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440010",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "sender_name": "You",
  "sender_type": "technician",
  "body": "Got it.",
  "timestamp": "2025-03-22T14:00:00.000000Z",
  "is_read": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440020",
  "job_title": "AC Repair — 742 Evergreen Terrace"
}
```

`sender_type`: `operator` | `client` | `system` | `technician`

---

## New module: `apps/technicians/inbox_models.py`

```python
from django.conf import settings
from django.db import models

from apps.core.models import TenantAwareModel


class TechnicianInboxThreadType(models.TextChoices):
    OPERATOR_DIRECT = "operator_direct", "Operator direct"
    CLIENT_JOB = "client_job", "Client job"
    SYSTEM_ALERT = "system_alert", "System alert"


class TechnicianInboxSenderType(models.TextChoices):
    OPERATOR = "operator", "Operator"
    CLIENT = "client", "Client"
    SYSTEM = "system", "System"
    TECHNICIAN = "technician", "Technician"


class TechnicianInboxThread(TenantAwareModel):
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_threads",
        db_index=True,
    )
    thread_type = models.CharField(
        max_length=32,
        choices=TechnicianInboxThreadType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=512, blank=True, default="")
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technician_inbox_threads",
    )
    participant_name = models.CharField(max_length=255, blank=True, default="")
    participant_avatar_url = models.URLField(blank=True, null=True, max_length=2048)
    is_pinned = models.BooleanField(default=False, db_index=True)
    last_activity_at = models.DateTimeField(db_index=True)
    operator_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_inbox_threads",
    )
    client_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_inbox_threads",
    )

    class Meta:
        db_table = "technician_inbox_threads"
        indexes = [
            models.Index(fields=["tenant", "technician", "-last_activity_at"]),
            models.Index(fields=["technician", "thread_type"]),
        ]


class TechnicianInboxMessage(TenantAwareModel):
    thread = models.ForeignKey(
        TechnicianInboxThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_type = models.CharField(
        max_length=32,
        choices=TechnicianInboxSenderType.choices,
        db_index=True,
    )
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbox_messages_sent",
    )
    sender_name = models.CharField(max_length=255)
    body = models.TextField()
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technician_inbox_messages",
    )

    class Meta:
        db_table = "technician_inbox_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]


class TechnicianInboxMessageReceipt(TenantAwareModel):
    message = models.ForeignKey(
        TechnicianInboxMessage,
        on_delete=models.CASCADE,
        related_name="read_receipts",
    )
    reader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_read_receipts",
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "technician_inbox_message_receipts"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "reader"],
                name="uniq_inbox_msg_reader",
            ),
        ]
```

Run `makemigrations` / `migrate` after adding models.

---

## New module: `apps/technicians/inbox_serializers.py`

```python
from rest_framework import serializers

from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
)


class TechnicianInboxMessageSerializer(serializers.ModelSerializer):
    thread_id = serializers.UUIDField(read_only=True)
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    job_id = serializers.UUIDField(read_only=True, allow_null=True)
    job_title = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianInboxMessage
        fields = [
            "id",
            "thread_id",
            "sender_name",
            "sender_type",
            "body",
            "timestamp",
            "is_read",
            "job_id",
            "job_title",
        ]
        read_only_fields = fields

    def get_job_title(self, obj):
        if obj.job_id:
            return obj.job.title
        return None

    def get_is_read(self, obj):
        request = self.context.get("request")
        tech = getattr(request, "user", None) if request else None
        if not tech or not tech.is_authenticated:
            return False
        if obj.sender_type == "technician" and obj.sender_user_id == tech.id:
            return True
        return TechnicianInboxMessageReceipt.objects.filter(
            message=obj, reader=tech
        ).exists()


class TechnicianInboxThreadSerializer(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_activity_at = serializers.DateTimeField(read_only=True)
    job_id = serializers.UUIDField(read_only=True, allow_null=True)
    job_title = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianInboxThread
        fields = [
            "id",
            "title",
            "subtitle",
            "thread_type",
            "participant_name",
            "participant_avatar_url",
            "last_message",
            "unread_count",
            "last_activity_at",
            "job_id",
            "job_title",
            "is_pinned",
        ]
        read_only_fields = fields

    def get_job_title(self, obj):
        if obj.job_id:
            return obj.job.title
        return None

    def get_last_message(self, obj):
        m = (
            TechnicianInboxMessage.objects.filter(thread=obj)
            .order_by("-created_at")
            .first()
        )
        if not m:
            return None
        return TechnicianInboxMessageSerializer(
            m, context=self.context
        ).data

    def get_unread_count(self, obj):
        request = self.context.get("request")
        tech = getattr(request, "user", None) if request else None
        if not tech or not tech.is_authenticated:
            return 0
        qs = TechnicianInboxMessage.objects.filter(thread=obj).exclude(
            sender_type="technician", sender_user=tech
        )
        return qs.exclude(read_receipts__reader=tech).count()


class TechnicianInboxThreadPinSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianInboxThread
        fields = ["is_pinned"]


class TechnicianInboxSendSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=10000, trim_whitespace=True)
```

---

## New module: `apps/technicians/inbox_views.py`

```python
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsTechnician
from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
    TechnicianInboxThreadType,
)
from apps.technicians.inbox_serializers import (
    TechnicianInboxMessageSerializer,
    TechnicianInboxSendSerializer,
    TechnicianInboxThreadPinSerializer,
    TechnicianInboxThreadSerializer,
)


class TechnicianInboxThreadListView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def get(self, request):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response([])
        qs = (
            TechnicianInboxThread.objects.filter(
                tenant_id=tid, technician=request.user
            )
            .select_related("job")
            .order_by("-is_pinned", "-last_activity_at")
        )
        ser = TechnicianInboxThreadSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(ser.data)


class TechnicianInboxThreadDetailView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def get_thread(self, request, thread_id):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return None
        return TechnicianInboxThread.objects.filter(
            id=thread_id, tenant_id=tid, technician=request.user
        ).first()

    def patch(self, request, thread_id):
        thread = self.get_thread(request, thread_id)
        if not thread:
            return Response(status=status.HTTP_404_NOT_FOUND)
        ser = TechnicianInboxThreadPinSerializer(
            thread, data=request.data, partial=True
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        out = TechnicianInboxThreadSerializer(
            thread, context={"request": request}
        )
        return Response(out.data)


class TechnicianInboxMessageListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def get_thread(self, request, thread_id):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return None
        return TechnicianInboxThread.objects.filter(
            id=thread_id, tenant_id=tid, technician=request.user
        ).first()

    def get(self, request, thread_id):
        thread = self.get_thread(request, thread_id)
        if not thread:
            return Response(status=status.HTTP_404_NOT_FOUND)
        qs = (
            TechnicianInboxMessage.objects.filter(thread=thread)
            .select_related("job")
            .order_by("created_at")
        )
        ser = TechnicianInboxMessageSerializer(
            qs, many=True, context={"request": request}
        )
        return Response(ser.data)

    def post(self, request, thread_id):
        thread = self.get_thread(request, thread_id)
        if not thread:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if thread.thread_type == TechnicianInboxThreadType.SYSTEM_ALERT:
            return Response(
                {"detail": "Replies not supported for system threads."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ser = TechnicianInboxSendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        body = ser.validated_data["body"].strip()
        msg = TechnicianInboxMessage.objects.create(
            tenant_id=thread.tenant_id,
            thread=thread,
            sender_type="technician",
            sender_user=request.user,
            sender_name="You",
            body=body,
            job_id=thread.job_id,
        )
        thread.last_activity_at = timezone.now()
        thread.save(update_fields=["last_activity_at", "updated_at"])
        out = TechnicianInboxMessageSerializer(
            msg, context={"request": request}
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class TechnicianInboxMarkReadView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]

    def post(self, request, thread_id):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(status=status.HTTP_404_NOT_FOUND)
        thread = TechnicianInboxThread.objects.filter(
            id=thread_id, tenant_id=tid, technician=request.user
        ).first()
        if not thread:
            return Response(status=status.HTTP_404_NOT_FOUND)
        msgs = TechnicianInboxMessage.objects.filter(thread=thread).exclude(
            sender_type="technician", sender_user=request.user
        )
        for m in msgs:
            TechnicianInboxMessageReceipt.objects.get_or_create(
                message=m,
                reader=request.user,
                defaults={"tenant_id": thread.tenant_id},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## Edit: `apps/technicians/urls.py`

Add imports:

```python
from apps.technicians.inbox_views import (
    TechnicianInboxMarkReadView,
    TechnicianInboxMessageListCreateView,
    TechnicianInboxThreadDetailView,
    TechnicianInboxThreadListView,
)
```

Add routes **before** `technicians/me/` (more specific paths first):

```python
    path(
        "technicians/me/inbox/threads/",
        TechnicianInboxThreadListView.as_view(),
        name="technician-inbox-threads",
    ),
    path(
        "technicians/me/inbox/threads/<uuid:thread_id>/",
        TechnicianInboxThreadDetailView.as_view(),
        name="technician-inbox-thread-detail",
    ),
    path(
        "technicians/me/inbox/threads/<uuid:thread_id>/messages/",
        TechnicianInboxMessageListCreateView.as_view(),
        name="technician-inbox-messages",
    ),
    path(
        "technicians/me/inbox/threads/<uuid:thread_id>/mark-read/",
        TechnicianInboxMarkReadView.as_view(),
        name="technician-inbox-mark-read",
    ),
```

---

## Reference: `ordered_api/urls.py`

```python
    path("api/v1/", include("apps.technicians.urls")),
```

---

## Reference: `apps/core/permissions.py`

```python
class IsTechnician(BasePermission):
    """Logged-in user whose Django ``User.role`` is technician."""

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u
            and u.is_authenticated
            and getattr(u, "role", None) == UserRole.TECHNICIAN
        )
```

---

## Reference: `apps/technicians/views.py` (existing technician self-service pattern)

```python
class TechnicianMeView(APIView):
    permission_classes = [IsAuthenticated, IsTechnician]
```

---

## Reference: `apps/jobs/models.py` (`job_id` / `job_title` on threads and messages)

```python
class Job(TenantAwareModel):
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="open", db_index=True)
```

---

## Reference: `apps/jobs/views.py` (technician job visibility)

Technicians are not included in the current `JobViewSet.get_queryset()` filter; extend with assignment or `TechnicianProfile` linkage when wiring `JobDetailScreen` for assigned work.

```python
        return qs.filter(
            Q(created_by_id=user.id) | Q(service_request__client_id=user.id)
        )
```

---

## Reference: `ordered_api/settings.py`

```python
INSTALLED_APPS = [
    # ...
    "apps.technicians",
]

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.users.authentication.SupabaseAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
}
```

---

## Flutter wiring targets (client)

`lib/models/inbox_message.dart` — `fromJson` keys: `id`, `thread_id`, `sender_name`, `sender_type`, `body`, `timestamp`, `is_read`, `job_id`, `job_title`.

`lib/models/inbox_thread.dart` — `fromJson` keys: `id`, `title`, `subtitle`, `thread_type`, `participant_name`, `participant_avatar_url`, `last_message`, `unread_count`, `last_activity_at`, `job_id`, `job_title`, `is_pinned`.

`lib/widgets/conversation_composer.dart` — POST `{"body": "<text>"}` to messages URL.

`lib/screens/inbox_screen.dart` — `GET` threads; refresh repeats same request.

`lib/screens/conversation_screen.dart` — `GET` messages; menu “Mark as Read” → `POST mark-read/`.

`lib/screens/main_tab_screen.dart` — badge: sum `unread_count` from threads response.

---

## Optional: Django admin

```python
from django.contrib import admin
from apps.technicians.inbox_models import TechnicianInboxMessage, TechnicianInboxThread

admin.site.register(TechnicianInboxThread)
admin.site.register(TechnicianInboxMessage)
```
