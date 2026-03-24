"""
Admin/operator API for tenant clients (users with role ``client``).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdmin
from apps.users.admin_serializers import (
    ClientAdminDetailSerializer,
    ClientListSerializer,
)
from apps.users.models import UserRole

User = get_user_model()


class ClientAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and retrieve client users for the operator workspace.

    GET    /api/v1/admin/clients/
    GET    /api/v1/admin/clients/{user_id}/

    Same auth model as ``/api/v1/admin/technicians/``: ``IsAuthenticated`` + ``IsAdmin``
    (Django staff/superuser). Scoped to ``request.user.tenant_id``.
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["status", "is_active"]
    search_fields = ["email", "first_name", "last_name", "phone"]
    ordering_fields = ["created_at", "updated_at", "email", "last_name", "first_name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        tid = getattr(self.request.user, "tenant_id", None)
        if not tid:
            return User.objects.none()
        return (
            User.objects.filter(tenant_id=tid, role=UserRole.CLIENT)
            .annotate(
                _service_request_count=Count("service_requests", distinct=True),
                _jobs_created_count=Count("jobs_created", distinct=True),
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ClientAdminDetailSerializer
        return ClientListSerializer
