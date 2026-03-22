from __future__ import annotations

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.events.models import EntityType, EventType
from apps.events.services import record_event
from apps.pricing.serializers import PriceSnapshotSerializer
from apps.pricing.services import create_price_snapshot_from_service_request

from .models import ServiceRequest, ServiceRequestSource, ServiceRequestStatus
from .permissions import (
    IsTenantMember,
    IsTenantOperator,
    ServiceRequestObjectPermission,
)
from .serializers import (
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
    filterset_fields = ["status", "service_type", "source", "client", "property_ref"]
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

        return [
            IsAuthenticated(),
            IsTenantMember(),
            ServiceRequestObjectPermission(),
        ]

    def _caller_is_operator(self) -> bool:
        u = self.request.user
        return bool(
            getattr(u, "is_staff", False)
            or getattr(u, "is_superuser", False)
            or getattr(u, "is_tenant_operator", False)
        )

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
