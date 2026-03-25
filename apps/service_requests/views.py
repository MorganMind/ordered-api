from __future__ import annotations

from django.db import transaction
from django.db.models import Prefetch
from django.utils.text import slugify
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.core.permissions import IsTenantWorkspaceStaff
from apps.events.models import EntityType, EventType
from apps.events.services import record_event
from apps.jobs.models import Job, Skill
from apps.jobs.serializers import JobSerializer
from apps.jobs.services.conversion import convert_service_request_to_job
from apps.pricing.serializers import PriceSnapshotSerializer
from apps.pricing.services import create_price_snapshot_from_service_request
from apps.users.models import UserRole

from .models import (
    ServiceOffering,
    ServiceOfferingSkill,
    ServiceRequest,
    ServiceRequestSource,
    ServiceRequestStatus,
)
from .template_library import (
    get_service_offering_template,
    list_service_offering_templates,
)
from .permissions import (
    IsTenantMember,
    IsTenantOperator,
    ServiceRequestObjectPermission,
)
from .serializers import (
    ServiceOfferingSerializer,
    ServiceOfferingWriteSerializer,
    ServiceRequestClientUpdateSerializer,
    ServiceRequestCreateSerializer,
    ServiceRequestOperatorSerializer,
    ServiceRequestOperatorUpdateSerializer,
    ServiceRequestSerializer,
    ServiceRequestStatusSerializer,
)

PRICEABLE_STATUSES = frozenset(
    {
        ServiceRequestStatus.NEW,
        ServiceRequestStatus.REVIEWING,
    }
)


class ServiceRequestViewSet(viewsets.ModelViewSet):
    """
    Tenant-scoped service requests.

    Permission matrix (see ``get_permissions`` — do not mutate
    ``permission_classes`` on the instance).
    """

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = [
        "status",
        "service_type",
        "service_offering",
        "source",
        "client",
        "property_ref",
    ]
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_permissions(self):
        if self.action in ("update_status", "price"):
            return [IsAuthenticated(), IsTenantOperator()]

        if self.action == "partial_update":
            return [
                IsAuthenticated(),
                IsTenantOperator(),
                ServiceRequestObjectPermission(),
            ]

        if self.action == "convert_to_job":
            return [IsAuthenticated(), IsTenantWorkspaceStaff()]

        return [
            IsAuthenticated(),
            IsTenantMember(),
            ServiceRequestObjectPermission(),
        ]

    def _caller_is_operator(self) -> bool:
        u = self.request.user
        if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
            return True
        if getattr(u, "is_tenant_operator", False):
            return True
        role = getattr(u, "role", None)
        return role in (UserRole.ADMIN, "operator")

    def get_serializer_class(self):
        if self.action == "create":
            return ServiceRequestCreateSerializer
        if self.action == "partial_update":
            return (
                ServiceRequestOperatorUpdateSerializer
                if self._caller_is_operator()
                else ServiceRequestClientUpdateSerializer
            )
        if self.action == "update_status":
            return ServiceRequestStatusSerializer
        return (
            ServiceRequestOperatorSerializer
            if self._caller_is_operator()
            else ServiceRequestSerializer
        )

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ServiceRequest.objects.none()

        qs = ServiceRequest.objects.select_related(
            "tenant",
            "property_ref",
            "latest_price_snapshot",
            "converted_job",
            "service_offering",
        ).prefetch_related(
            Prefetch(
                "service_offering__offering_skills",
                queryset=ServiceOfferingSkill.objects.select_related("skill").order_by(
                    "sort_order",
                    "skill__label",
                ),
            ),
        )

        if getattr(user, "is_superuser", False):
            return qs

        tid = getattr(user, "tenant_id", None)
        if not tid:
            return ServiceRequest.objects.none()

        qs = qs.filter(tenant_id=tid)

        if self._caller_is_operator():
            return qs

        return qs.filter(client_id=user.id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_cls = (
            ServiceRequestOperatorSerializer
            if self._caller_is_operator()
            else ServiceRequestSerializer
        )
        read = read_cls(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read.data)
        return Response(read.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        read_cls = (
            ServiceRequestOperatorSerializer
            if self._caller_is_operator()
            else ServiceRequestSerializer
        )
        read = read_cls(instance, context=self.get_serializer_context())
        return Response(read.data)

    def perform_create(self, serializer: ServiceRequestCreateSerializer) -> None:
        serializer.save(
            tenant_id=getattr(self.request.user, "tenant_id", None),
            client=self.request.user,
            source=ServiceRequestSource.API,
        )

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk: str | None = None) -> Response:
        sr: ServiceRequest = self.get_object()
        ser = ServiceRequestStatusSerializer(sr, data=request.data)
        ser.is_valid(raise_exception=True)

        old_status = sr.status
        sr.status = ser.validated_data["status"]
        sr.save(update_fields=["status", "updated_at"])

        record_event(
            tenant_id=sr.tenant_id,
            actor=request.user,
            event_type=EventType.SERVICE_REQUEST_STATUS_CHANGED,
            entity_type=EntityType.SERVICE_REQUEST,
            entity_id=sr.id,
            payload={"from": old_status, "to": sr.status},
            request=request,
        )

        read_cls = (
            ServiceRequestOperatorSerializer
            if self._caller_is_operator()
            else ServiceRequestSerializer
        )
        return Response(
            read_cls(sr, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="price")
    def price(self, request, pk: str | None = None) -> Response:
        sr: ServiceRequest = self.get_object()

        if sr.status not in PRICEABLE_STATUSES:
            return Response(
                {
                    "detail": (
                        f"Cannot price a ServiceRequest in '{sr.status}' status. "
                        f"Must be one of: {sorted(PRICEABLE_STATUSES)}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            snap = create_price_snapshot_from_service_request(sr)
            sr.status = ServiceRequestStatus.PRICED
            sr.save(update_fields=["status", "updated_at"])

        record_event(
            tenant_id=sr.tenant_id,
            actor=request.user,
            event_type=EventType.SERVICE_REQUEST_PRICED,
            entity_type=EntityType.SERVICE_REQUEST,
            entity_id=sr.id,
            payload={"price_snapshot_id": str(snap.id)},
            request=request,
        )

        sr.refresh_from_db(
            fields=["status", "latest_price_snapshot_id", "updated_at"]
        )

        return Response(
            {
                "service_request": ServiceRequestOperatorSerializer(
                    sr, context=self.get_serializer_context()
                ).data,
                "price_snapshot": PriceSnapshotSerializer(
                    snap, context=self.get_serializer_context()
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="convert-to-job")
    def convert_to_job(self, request, pk: str | None = None) -> Response:
        sr: ServiceRequest = self.get_object()
        if sr.converted_job_id:
            return Response(
                {"detail": "This service request has already been converted to a job."},
                status=status.HTTP_409_CONFLICT,
            )
        if sr.status != ServiceRequestStatus.PRICED:
            return Response(
                {
                    "detail": (
                        "Only priced service requests can be converted to a job. "
                        f"Current status: {sr.status}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        title = request.data.get("title")
        if title is not None and not isinstance(title, str):
            return Response(
                {"detail": "Field 'title' must be a string when provided."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        job = convert_service_request_to_job(
            sr,
            actor=request.user,
            title=title.strip() if isinstance(title, str) and title.strip() else None,
            request=request,
        )
        job = Job.objects.select_related(
            "tenant",
            "service_request",
            "booking",
            "booking__property",
            "assigned_to",
        ).get(pk=job.pk)
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)


class ServiceOfferingViewSet(viewsets.ModelViewSet):
    """
    Tenant-scoped catalog of bookable services (offerings) with nested skills.

    Members may list/retrieve; operators may create, update, and delete.
    """

    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["is_active", "slug"]
    ordering_fields = ["sort_order", "name", "created_at"]
    ordering = ["sort_order", "name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_permissions(self):
        if self.action in ("list", "retrieve", "templates"):
            return [IsAuthenticated(), IsTenantMember()]
        return [IsAuthenticated(), IsTenantWorkspaceStaff()]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ServiceOfferingWriteSerializer
        return ServiceOfferingSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return ServiceOffering.objects.none()
        base = ServiceOffering.objects.select_related("tenant").prefetch_related(
            Prefetch(
                "offering_skills",
                queryset=ServiceOfferingSkill.objects.select_related("skill").order_by(
                    "sort_order",
                    "skill__label",
                ),
            ),
        )
        if getattr(user, "is_superuser", False):
            return base
        tid = getattr(user, "tenant_id", None)
        if not tid:
            return ServiceOffering.objects.none()
        return base.filter(tenant_id=tid)

    def perform_create(self, serializer) -> None:
        serializer.save(tenant_id=self.request.user.tenant_id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read = ServiceOfferingSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        )
        headers = self.get_success_headers(read.data)
        return Response(read.data, status=status.HTTP_201_CREATED, headers=headers)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        fresh = self.get_queryset().get(pk=instance.pk)
        read = ServiceOfferingSerializer(
            fresh,
            context=self.get_serializer_context(),
        )
        return Response(read.data)

    def update(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    @action(detail=False, methods=["get"], url_path="templates")
    def templates(self, request):
        return Response({"templates": list_service_offering_templates()})

    @action(detail=False, methods=["post"], url_path="from-template")
    def from_template(self, request):
        template_key = str(request.data.get("template_key") or "").strip()
        template = get_service_offering_template(template_key)
        if template is None:
            return Response(
                {"detail": f"Unknown template_key '{template_key}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {
            "name": request.data.get("name") or template.name,
            "slug": request.data.get("slug")
            or slugify(request.data.get("name") or template.name)[:80],
            "description": request.data.get("description") or template.description,
            "is_active": request.data.get("is_active", True),
            "sort_order": request.data.get("sort_order", 0),
            "reporting_category": (
                request.data.get("reporting_category") or template.reporting_category
            ),
        }
        skill_keys = request.data.get("skill_keys") or list(template.suggested_skill_keys)
        skills = list(Skill.objects.filter(key__in=skill_keys, is_active=True))
        by_key = {s.key: s for s in skills}
        skill_ids = [str(by_key[k].id) for k in skill_keys if k in by_key]
        missing_keys = [k for k in skill_keys if k not in by_key]

        serializer = ServiceOfferingWriteSerializer(
            data={**payload, "skill_ids": skill_ids},
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        fresh = self.get_queryset().get(pk=serializer.instance.pk)
        read = ServiceOfferingSerializer(fresh, context=self.get_serializer_context())
        return Response(
            {
                "service_offering": read.data,
                "template_key": template.key,
                "unresolved_skill_keys": missing_keys,
            },
            status=status.HTTP_201_CREATED,
        )
