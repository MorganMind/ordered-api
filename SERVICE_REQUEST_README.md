# ServiceRequest — files and code

## `ordered_api/settings.py`

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "django_filters",
    "apps.core",
    "apps.tenants",
    "apps.events",
    "apps.pricing",
    "apps.service_requests",
    "apps.jobs",
    "apps.properties",
    "apps.intake",
    "apps.users",
    "apps.technicians",
]
```

## `ordered_api/urls.py`

```python
"""Root URL configuration for ordered-api."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api_auth.urls")),
    path("api/v1/", include("user.urls")),
    path("api/v1/", include("files.urls")),
    path("api/v1/", include("tag.urls")),
    path("api/v1/", include("transcription.urls")),
    path("api/v1/tenants/", include("apps.tenants.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/", include("apps.service_requests.urls")),
    path("api/v1/", include("apps.pricing.urls")),
]
```

## `apps/service_requests/__init__.py`

```python

```

## `apps/service_requests/apps.py`

```python
from django.apps import AppConfig


class ServiceRequestsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.service_requests"
    label = "service_requests"
    verbose_name = "Service requests"

    def ready(self):
        from . import signals  # noqa: F401
```

## `apps/service_requests/models.py`

```python
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import TenantAwareModel


class ServiceRequestStatus(models.TextChoices):
    NEW = "new", "New"
    REVIEWING = "reviewing", "Reviewing"
    PRICED = "priced", "Priced"
    CONVERTED = "converted", "Converted"
    CANCELLED = "cancelled", "Cancelled"
    ON_HOLD = "on_hold", "On Hold"


class ServiceRequestSource(models.TextChoices):
    FORM = "form", "Form"
    API = "api", "API"
    IMPORT = "import", "Import"


class ServiceRequest(TenantAwareModel):
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
        db_index=True,
    )
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
        db_index=True,
    )

    contact_name = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=64, blank=True)
    contact_email = models.EmailField(blank=True)

    address_raw = models.TextField()
    address_normalized = models.JSONField(null=True, blank=True)

    square_feet = models.PositiveIntegerField(null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    service_type = models.CharField(max_length=64, db_index=True)
    timing_preference = models.JSONField(
        default=dict,
        blank=True,
        help_text="Flexible window / preference payload, not strict scheduling",
    )
    notes = models.TextField(blank=True)
    media_refs = models.JSONField(
        default=list,
        blank=True,
        help_text="List of references, e.g. [{type, storage_key, url}] — no blobs",
    )

    status = models.CharField(
        max_length=20,
        choices=ServiceRequestStatus.choices,
        default=ServiceRequestStatus.NEW,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=ServiceRequestSource.choices,
        default=ServiceRequestSource.FORM,
        db_index=True,
    )

    latest_price_snapshot = models.ForeignKey(
        "pricing.PriceSnapshot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    converted_job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_service_requests",
    )

    internal_operator_notes = models.TextField(blank=True)

    class Meta:
        db_table = "service_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "service_type", "-created_at"]),
        ]

    def __str__(self):
        return f"ServiceRequest({self.id}) {self.status}"
```

## `apps/service_requests/serializers.py`

```python
from rest_framework import serializers

from .models import ServiceRequest, ServiceRequestStatus


class ServiceRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequest
        fields = [
            "id",
            "tenant",
            "client",
            "property",
            "contact_name",
            "contact_phone",
            "contact_email",
            "address_raw",
            "address_normalized",
            "square_feet",
            "bedrooms",
            "bathrooms",
            "service_type",
            "timing_preference",
            "notes",
            "media_refs",
            "status",
            "source",
            "latest_price_snapshot",
            "converted_job",
            "internal_operator_notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant",
            "latest_price_snapshot",
            "converted_job",
            "created_at",
            "updated_at",
        ]


class ServiceRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequest
        fields = [
            "property",
            "contact_name",
            "contact_phone",
            "contact_email",
            "address_raw",
            "square_feet",
            "bedrooms",
            "bathrooms",
            "service_type",
            "timing_preference",
            "notes",
            "media_refs",
            "source",
        ]


class ServiceRequestUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceRequest
        fields = [
            "contact_name",
            "contact_phone",
            "contact_email",
            "address_raw",
            "address_normalized",
            "square_feet",
            "bedrooms",
            "bathrooms",
            "service_type",
            "timing_preference",
            "notes",
            "media_refs",
            "internal_operator_notes",
        ]


class ServiceRequestStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ServiceRequestStatus.choices)
```

## `apps/service_requests/permissions.py`

```python
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsTenantMember(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and getattr(u, "tenant_id", None))


class IsTenantOperator(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
            return True
        return bool(getattr(u, "is_tenant_operator", False))


class ServiceRequestClientAccess(BasePermission):
    def has_object_permission(self, request, view, obj):
        if getattr(request.user, "is_staff", False) or getattr(
            request.user, "is_superuser", False
        ):
            return True
        if getattr(request.user, "is_tenant_operator", False):
            return obj.tenant_id == getattr(request.user, "tenant_id", None)
        if request.method in SAFE_METHODS and obj.client_id == request.user.id:
            return True
        return False
```

## `apps/service_requests/views.py`

```python
from django.db import transaction
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.events.services import record_event

from .models import ServiceRequest, ServiceRequestStatus
from .permissions import IsTenantMember, IsTenantOperator, ServiceRequestClientAccess
from .serializers import (
    ServiceRequestCreateSerializer,
    ServiceRequestSerializer,
    ServiceRequestStatusSerializer,
    ServiceRequestUpdateSerializer,
)
from apps.pricing.services import create_price_snapshot_from_service_request


class ServiceRequestViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsTenantMember, ServiceRequestClientAccess]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "service_type", "source", "client", "property"]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceRequestCreateSerializer
        if self.action == "partial_update":
            return ServiceRequestUpdateSerializer
        if self.action == "update_status":
            return ServiceRequestStatusSerializer
        return ServiceRequestSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ServiceRequest.objects.none()
        qs = ServiceRequest.objects.all()
        tid = getattr(user, "tenant_id", None)
        if getattr(user, "is_superuser", False):
            return qs
        if tid:
            qs = qs.filter(tenant_id=tid)
        else:
            return ServiceRequest.objects.none()
        if getattr(user, "is_tenant_operator", False) or getattr(
            user, "is_staff", False
        ):
            return qs
        return qs.filter(client_id=user.id)

    def perform_create(self, serializer):
        tid = getattr(self.request.user, "tenant_id", None)
        serializer.save(
            tenant_id=tid,
            client=self.request.user,
        )

    def partial_update(self, request, *args, **kwargs):
        self.permission_classes = [
            IsAuthenticated,
            IsTenantOperator,
            ServiceRequestClientAccess,
        ]
        return super().partial_update(request, *args, **kwargs)

    @action(
        detail=True,
        methods=["post"],
        url_path="status",
        permission_classes=[IsAuthenticated, IsTenantOperator],
    )
    def update_status(self, request, pk=None):
        sr = self.get_object()
        ser = ServiceRequestStatusSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        old = sr.status
        sr.status = ser.validated_data["status"]
        sr.save(update_fields=["status", "updated_at"])
        record_event(
            tenant_id=sr.tenant_id,
            actor=request.user,
            event_type="service_request.status_changed",
            entity_type="service_request",
            entity_id=sr.id,
            payload={"from": old, "to": sr.status},
            request=request,
        )
        return Response(ServiceRequestSerializer(sr).data, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=["post"],
        url_path="price",
        permission_classes=[IsAuthenticated, IsTenantOperator],
    )
    def price(self, request, pk=None):
        sr = self.get_object()
        with transaction.atomic():
            snap = create_price_snapshot_from_service_request(sr)
            sr.latest_price_snapshot = snap
            if sr.status == ServiceRequestStatus.NEW:
                sr.status = ServiceRequestStatus.PRICED
            sr.save(update_fields=["latest_price_snapshot", "status", "updated_at"])
        record_event(
            tenant_id=sr.tenant_id,
            actor=request.user,
            event_type="service_request.priced",
            entity_type="service_request",
            entity_id=sr.id,
            payload={"price_snapshot_id": str(snap.id)},
            request=request,
        )
        from apps.pricing.serializers import PriceSnapshotSerializer

        return Response(
            {
                "service_request": ServiceRequestSerializer(sr).data,
                "price_snapshot": PriceSnapshotSerializer(snap).data,
            },
            status=status.HTTP_201_CREATED,
        )
```

## `apps/service_requests/urls.py`

```python
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ServiceRequestViewSet

router = DefaultRouter()
router.register(r"service-requests", ServiceRequestViewSet, basename="service-request")

urlpatterns = [
    path("", include(router.urls)),
]
```

## `apps/service_requests/admin.py`

```python
from django.contrib import admin

from .models import ServiceRequest


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "status",
        "service_type",
        "contact_name",
        "created_at",
    )
    list_filter = ("status", "service_type", "source")
    search_fields = ("contact_name", "contact_email", "contact_phone", "address_raw")
```

## `apps/service_requests/signals.py`

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.events.services import record_event

from .models import ServiceRequest


@receiver(post_save, sender=ServiceRequest)
def service_request_audit(sender, instance: ServiceRequest, created, **kwargs):
    if not created:
        return
    record_event(
        tenant_id=instance.tenant_id,
        actor=None,
        event_type="service_request.created",
        entity_type="service_request",
        entity_id=instance.id,
        payload={"service_type": instance.service_type, "status": instance.status},
    )
```

## `apps/service_requests/services/__init__.py`

```python
from apps.pricing.services import create_price_snapshot_from_service_request

__all__ = ["create_price_snapshot_from_service_request"]
```

## `apps/pricing/__init__.py`

```python

```

## `apps/pricing/apps.py`

```python
from django.apps import AppConfig


class PricingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.pricing"
    label = "pricing"
```

## `apps/pricing/models.py`

```python
from django.db import models

from apps.core.models import TenantAwareModel


class PriceSnapshot(TenantAwareModel):
    service_request = models.ForeignKey(
        "service_requests.ServiceRequest",
        on_delete=models.CASCADE,
        related_name="price_snapshots",
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    total_cents = models.BigIntegerField()
    subtotal_cents = models.BigIntegerField(default=0)
    line_items = models.JSONField(default=list)
    inputs_used = models.JSONField(
        default=dict,
        help_text="Structured pricing inputs copied from ServiceRequest at quote time",
    )
    pricing_engine_version = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "price_snapshots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "service_request", "-created_at"]),
        ]
```

## `apps/pricing/services.py`

```python
from __future__ import annotations

from typing import Any, Dict

from django.db import transaction

from apps.pricing.models import PriceSnapshot

from apps.service_requests.models import ServiceRequest


def service_request_pricing_inputs(sr: ServiceRequest) -> Dict[str, Any]:
    return {
        "service_type": sr.service_type,
        "square_feet": sr.square_feet,
        "bedrooms": sr.bedrooms,
        "bathrooms": float(sr.bathrooms) if sr.bathrooms is not None else None,
        "address_raw": sr.address_raw,
        "timing_preference": sr.timing_preference,
        "notes": sr.notes,
        "property_id": str(sr.property_id) if sr.property_id else None,
    }


def _compute_line_items(inputs: Dict[str, Any]) -> tuple[list, int, int]:
    base = 9900
    sq = inputs.get("square_feet") or 0
    extra = min(50000, max(0, (sq - 1500) // 100 * 500))
    total = base + extra
    lines = [
        {"code": "base_visit", "label": "Base visit", "amount_cents": base},
        {"code": "sqft_adjustment", "label": "Size adjustment", "amount_cents": extra},
    ]
    return lines, total, total


@transaction.atomic
def create_price_snapshot_from_service_request(
    sr: ServiceRequest,
) -> PriceSnapshot:
    inputs = service_request_pricing_inputs(sr)
    lines, subtotal, total = _compute_line_items(inputs)
    return PriceSnapshot.objects.create(
        tenant_id=sr.tenant_id,
        service_request=sr,
        currency="USD",
        total_cents=total,
        subtotal_cents=subtotal,
        line_items=lines,
        inputs_used=inputs,
        pricing_engine_version="v1-placeholder",
    )
```

## `apps/pricing/serializers.py`

```python
from rest_framework import serializers

from .models import PriceSnapshot


class PriceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSnapshot
        fields = [
            "id",
            "tenant",
            "service_request",
            "currency",
            "total_cents",
            "subtotal_cents",
            "line_items",
            "inputs_used",
            "pricing_engine_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
```

## `apps/pricing/views.py`

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdmin

from .models import PriceSnapshot
from .serializers import PriceSnapshotSerializer


class PriceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PriceSnapshotSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return PriceSnapshot.objects.none()
        qs = PriceSnapshot.objects.all()
        if getattr(user, "is_superuser", False):
            return qs
        tid = getattr(user, "tenant_id", None)
        if tid:
            return qs.filter(tenant_id=tid)
        return PriceSnapshot.objects.none()
```

## `apps/pricing/urls.py`

```python
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PriceSnapshotViewSet

router = DefaultRouter()
router.register(r"price-snapshots", PriceSnapshotViewSet, basename="price-snapshot")

urlpatterns = [
    path("", include(router.urls)),
]
```

## `apps/jobs/models.py`

```python
import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TenantAwareModel


class Job(TenantAwareModel):
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="open", db_index=True)
    service_request = models.ForeignKey(
        "service_requests.ServiceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs_created",
    )

    class Meta:
        db_table = "jobs"
```

## `apps/jobs/services/conversion.py`

```python
from __future__ import annotations

from django.db import transaction

from apps.events.services import record_event
from apps.jobs.models import Job
from apps.service_requests.models import ServiceRequest, ServiceRequestStatus


@transaction.atomic
def convert_service_request_to_job(
    sr: ServiceRequest,
    *,
    actor,
    title: str | None = None,
) -> Job:
    job = Job.objects.create(
        tenant_id=sr.tenant_id,
        title=title or f"{sr.service_type} — {sr.contact_name}",
        service_request=sr,
        created_by=actor,
    )
    sr.converted_job = job
    sr.status = ServiceRequestStatus.CONVERTED
    sr.save(update_fields=["converted_job", "status", "updated_at"])
    record_event(
        tenant_id=sr.tenant_id,
        actor=actor,
        event_type="service_request.converted",
        entity_type="service_request",
        entity_id=sr.id,
        payload={"job_id": str(job.id)},
    )
    return job
```

## `apps/events/models.py`

```python
"""
Event audit log models for tracking domain-level actions.
"""
from django.conf import settings
from django.db import models

from apps.core.models import BaseModel


class EventType(models.TextChoices):
    """Enumeration of all trackable event types."""
    # Booking events
    BOOKING_CREATED = "booking.created", "Booking Created"
    BOOKING_CONFIRMED = "booking.confirmed", "Booking Confirmed"
    BOOKING_CANCELLED = "booking.cancelled", "Booking Cancelled"
    BOOKING_COMPLETED = "booking.completed", "Booking Completed"
    BOOKING_FULFILLED = "booking.fulfilled", "Booking Fulfilled"
    BOOKING_RESCHEDULED = "booking.rescheduled", "Booking Rescheduled"
    BOOKING_JOB_GENERATED = "booking.job_generated", "Booking Job Generated"
    BOOKING_GENERATED_FROM_SERIES = "booking.generated_from_series", "Booking Generated From Series"
    BOOKING_RESCHEDULE_REQUESTED = "booking.reschedule_requested", "Booking Reschedule Requested"
    BOOKING_RESCHEDULE_CONFIRMED = "booking.reschedule_confirmed", "Booking Reschedule Confirmed"
    BOOKING_RESCHEDULE_REJECTED = "booking.reschedule_rejected", "Booking Reschedule Rejected"

    # Recurring Series events
    SERIES_PAUSED = "series.paused", "Series Paused"
    SERIES_RESUMED = "series.resumed", "Series Resumed"
    SERIES_ENDED = "series.ended", "Series Ended"
    SERIES_SKIP_NEXT = "series.skip_next", "Series Skip Next"
    SERIES_SKIP_CANCELLED = "series.skip_cancelled", "Series Skip Cancelled"
    SERIES_DATE_SKIPPED = "series.date_skipped", "Series Date Skipped"
    SERIES_OCCURRENCE_SKIPPED = "series.occurrence_skipped", "Series Occurrence Skipped"
    SERIES_OCCURRENCE_RESCHEDULED = "series.occurrence_rescheduled", "Series Occurrence Rescheduled"
    SERIES_EXCEPTION_REVERTED = "series.exception_reverted", "Series Exception Reverted"

    # Job events
    JOB_ASSIGNED = "job.assigned", "Job Assigned"
    JOB_CLAIMED = "job.claimed", "Job Claimed"
    JOB_RELEASED = "job.released", "Job Released"
    JOB_STARTED = "job.started", "Job Started"
    JOB_COMPLETED = "job.completed", "Job Completed"
    JOB_CANCELLED = "job.cancelled", "Job Cancelled"
    JOB_GENERATED_FROM_SERIES = "job.generated_from_series", "Job Generated From Series"

    # Technician events
    TECHNICIAN_ASSIGNED = "technician.assigned", "Technician Assigned"
    TECHNICIAN_UNASSIGNED = "technician.unassigned", "Technician Unassigned"
    TECHNICIAN_CHECKED_IN = "technician.checked_in", "Technician Checked In"
    TECHNICIAN_CHECKED_OUT = "technician.checked_out", "Technician Checked Out"
    TECHNICIAN_SKILLS_UPDATED = "technician.skills_updated", "Technician Skills Updated"

    # Technician application events
    TECHNICIAN_APPLICATION_CREATED = (
        "technician_application.created",
        "Technician Application Created",
    )
    TECHNICIAN_APPLICATION_REVIEWED = (
        "technician_application.reviewed",
        "Technician Application Reviewed",
    )
    TECHNICIAN_APPLICATION_APPROVED = (
        "technician_application.approved",
        "Technician Application Approved",
    )
    TECHNICIAN_APPLICATION_REJECTED = (
        "technician_application.rejected",
        "Technician Application Rejected",
    )
    TECHNICIAN_APPLICATION_CONVERTED = (
        "technician_application.converted",
        "Technician Application Converted",
    )

    # Technician lifecycle
    TECHNICIAN_PROFILE_CREATED = (
        "technician.profile_created",
        "Technician Profile Created",
    )

    # Memory events
    MEMORY_CREATED = "memory.created", "Memory Created"
    MEMORY_UPDATED = "memory.updated", "Memory Updated"
    MEMORY_DELETED = "memory.deleted", "Memory Deleted"

    # Brief events
    BRIEF_GENERATED = "brief.generated", "Brief Generated"

    # User events
    USER_CREATED = "user.created", "User Created"
    USER_UPDATED = "user.updated", "User Updated"
    USER_DEACTIVATED = "user.deactivated", "User Deactivated"
    USER_REACTIVATED = "user.reactivated", "User Reactivated"

    # Property events
    PROPERTY_CREATED = "property.created", "Property Created"
    PROPERTY_UPDATED = "property.updated", "Property Updated"
    PROPERTY_DELETED = "property.deleted", "Property Deleted"

    # Service events
    SERVICE_CREATED = "service.created", "Service Created"
    SERVICE_UPDATED = "service.updated", "Service Updated"
    SERVICE_DELETED = "service.deleted", "Service Deleted"

    # Service request (demand intake)
    SERVICE_REQUEST_CREATED = "service_request.created", "Service Request Created"
    SERVICE_REQUEST_UPDATED = "service_request.updated", "Service Request Updated"
    SERVICE_REQUEST_STATUS_CHANGED = (
        "service_request.status_changed",
        "Service Request Status Changed",
    )
    SERVICE_REQUEST_PRICED = "service_request.priced", "Service Request Priced"
    SERVICE_REQUEST_CONVERTED = (
        "service_request.converted",
        "Service Request Converted To Job",
    )


class EntityType(models.TextChoices):
    """Types of entities that can be tracked."""
    BOOKING = "booking", "Booking"
    JOB = "job", "Job"
    USER = "user", "User"
    PROPERTY = "property", "Property"
    SERVICE = "service", "Service"
    MEMORY = "memory", "Memory"
    TECHNICIAN = "technician", "Technician"
    TECHNICIAN_APPLICATION = "technician_application", "Technician Application"
    BRIEF = "brief", "Brief"
    RECURRING_SERIES = "recurring_series", "Recurring Series"
    SERVICE_REQUEST = "service_request", "Service Request"


class Event(BaseModel):
    """
    Audit log entry for tracking all domain-level actions.

    This table serves as the source of truth for "what happened and when"
    for debugging, support, reconciliation, and analytics.
    """

    # Tenant association - all events are tenant-scoped
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="events",
        db_index=True,
    )

    # Actor - who performed the action (null for system-initiated events)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_created",
        help_text="User who performed the action",
    )

    # Event classification
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        db_index=True,
        help_text="Type of event that occurred",
    )

    # Entity reference
    entity_type = models.CharField(
        max_length=50,
        choices=EntityType.choices,
        db_index=True,
        help_text="Type of entity this event relates to",
    )
    entity_id = models.UUIDField(
        db_index=True,
        help_text="ID of the entity this event relates to",
    )

    # Event data
    payload = models.JSONField(
        default=dict,
        help_text="Event-specific data and context",
    )

    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request that triggered the event",
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent of the request that triggered the event",
    )

    class Meta:
        db_table = "events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "event_type", "-created_at"]),
            models.Index(fields=["tenant", "entity_type", "entity_id", "-created_at"]),
            models.Index(fields=["tenant", "actor", "-created_at"]),
            models.Index(fields=["tenant", "-created_at"]),
        ]

    def __str__(self):
        actor_str = self.actor.email if self.actor else "System"
        return f"{self.event_type} by {actor_str} at {self.created_at}"
```

## `apps/events/services.py`

```python
from typing import Optional

from django.http import HttpRequest

from .models import Event


def record_event(
    *,
    tenant_id,
    actor,
    event_type: str,
    entity_type: str,
    entity_id,
    payload: Optional[dict] = None,
    request: Optional[HttpRequest] = None,
) -> Event:
    ip = None
    ua = ""
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            ip = xff.split(",")[0].strip()
        else:
            ip = request.META.get("REMOTE_ADDR")
        ua = request.META.get("HTTP_USER_AGENT", "") or ""

    return Event.objects.create(
        tenant_id=tenant_id,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        ip_address=ip,
        user_agent=ua,
    )
```

## `apps/events/views.py`

```python
"""
Views for querying audit events.
"""
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdmin

from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for querying audit events.
    Admins only.
    """

    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["event_type", "entity_type", "entity_id", "actor"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter events by current tenant when user has tenant_id; superuser sees all."""
        user = self.request.user
        if not user.is_authenticated:
            return Event.objects.none()
        qs = Event.objects.select_related("actor", "tenant")
        if getattr(user, "is_superuser", False):
            return qs
        tid = getattr(user, "tenant_id", None)
        if tid:
            return qs.filter(tenant_id=tid)
        return Event.objects.none()
```

## `apps/users/models.py` (or equivalent user model module)

```python
# is_tenant_operator = models.BooleanField(default=False, db_index=True)
# tenant = models.ForeignKey("tenants.Tenant", null=True, on_delete=models.SET_NULL)
```

## Path index

`ordered_api/settings.py`  
`ordered_api/urls.py`  
`apps/service_requests/__init__.py`  
`apps/service_requests/apps.py`  
`apps/service_requests/models.py`  
`apps/service_requests/serializers.py`  
`apps/service_requests/views.py`  
`apps/service_requests/urls.py`  
`apps/service_requests/admin.py`  
`apps/service_requests/permissions.py`  
`apps/service_requests/signals.py`  
`apps/service_requests/services/__init__.py`  
`apps/pricing/__init__.py`  
`apps/pricing/apps.py`  
`apps/pricing/models.py`  
`apps/pricing/serializers.py`  
`apps/pricing/views.py`  
`apps/pricing/urls.py`  
`apps/pricing/services.py`  
`apps/jobs/models.py`  
`apps/jobs/services/conversion.py`  
`apps/events/models.py`  
`apps/events/services.py`  
`apps/events/views.py`  
`apps/users/models.py` (or equivalent)  
`apps/service_requests/migrations/0001_initial.py`  
`apps/pricing/migrations/0001_initial.py`  
`apps/jobs/migrations/0001_initial.py` (or additive migrations)  
`apps/events/migrations/0006_service_request_events.py`
