from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Job
from .serializers import JobSerializer


class JobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Tenant-scoped jobs. Read-only until write flows are defined.

    ``/jobs/today/`` returns jobs whose ``created_at`` falls on the current
    calendar date (server/TZ-aware ``timezone.now()``). When Job gains a
    scheduled/start field, prefer that for this action instead.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = JobSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Job.objects.none()

        qs = Job.objects.select_related(
            "tenant",
            "service_request",
            "booking",
            "booking__property",
        ).order_by("-created_at")

        if getattr(user, "is_superuser", False):
            return qs

        tid = getattr(user, "tenant_id", None)
        if not tid:
            return Job.objects.none()

        qs = qs.filter(tenant_id=tid)

        if getattr(user, "is_tenant_operator", False) or getattr(
            user, "is_staff", False
        ):
            return qs

        return qs.filter(
            Q(created_by_id=user.id) | Q(service_request__client_id=user.id)
        )

    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        day = timezone.now().date()
        qs = self.get_queryset().filter(created_at__date=day)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
