from __future__ import annotations

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from apps.core.exceptions import TechnicianNotEligibleError
from apps.core.middleware import get_current_tenant_id
from apps.core.permissions import IsTechnician, IsTenantWorkspaceStaff
from apps.events.models import EntityType, EventType
from apps.events.services import record_event
from apps.technicians.services import TechnicianOnboardingService
from apps.users.models import UserRole

from .models import Job, JobStatus
from .serializers import JobCreateSerializer, JobOperatorUpdateSerializer, JobSerializer
from .services.booking_link import ensure_booking_for_job
from .transitions import transitions_payload_for_status


def _is_workspace_operator(user) -> bool:
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    if getattr(user, "is_tenant_operator", False):
        return True
    role = getattr(user, "role", None)
    return role in (UserRole.ADMIN, "operator")


class JobViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Tenant-scoped jobs.

    - **Operators** (workspace staff): ``POST /jobs/`` to create, list, PATCH updates.
    - **Technicians**: list jobs assigned to them plus **open** jobs with no assignee
      (claim board); POST actions ``claim``, ``release``, ``start``, ``complete``.
    - **Clients**: jobs they created or that stem from their service request.

    ``GET /jobs/today/`` filters by ``created_at`` date (same calendar day as the server).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = JobSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]
    http_method_names = ["get", "patch", "head", "options", "post"]

    def get_permissions(self):
        if self.action in ("create", "partial_update"):
            return [IsAuthenticated(), IsTenantWorkspaceStaff()]
        if self.action in ("claim", "release", "start", "complete"):
            return [IsAuthenticated(), IsTechnician()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == "create":
            return JobCreateSerializer
        if self.action == "partial_update":
            return JobOperatorUpdateSerializer
        return JobSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tenant_id"] = get_current_tenant_id() or getattr(
            self.request.user, "tenant_id", None
        )
        return ctx

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Job.objects.none()

        qs = Job.objects.select_related(
            "tenant",
            "service_request",
            "booking",
            "booking__property",
            "assigned_to",
        ).order_by("-created_at")

        if getattr(user, "is_superuser", False):
            return qs

        tid = getattr(user, "tenant_id", None)
        if not tid:
            return Job.objects.none()

        qs = qs.filter(tenant_id=tid)

        if _is_workspace_operator(user):
            return qs

        if getattr(user, "role", None) == UserRole.TECHNICIAN:
            return qs.filter(
                Q(assigned_to_id=user.id)
                | (
                    Q(status=JobStatus.OPEN)
                    & Q(assigned_to__isnull=True)
                )
            )

        return qs.filter(
            Q(created_by_id=user.id) | Q(service_request__client_id=user.id)
        )

    def perform_create(self, serializer):
        tid = get_current_tenant_id() or getattr(
            self.request.user, "tenant_id", None
        )
        serializer.save(tenant_id=tid, created_by=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        instance = self.get_queryset().get(pk=instance.pk)
        out = JobSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(out.data)
        return Response(out.data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=["get"], url_path="today")
    def today(self, request):
        day = timezone.now().date()
        qs = self.get_queryset().filter(created_at__date=day)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"], url_path="transitions")
    def transitions(self, request, pk=None):
        """
        Next valid statuses and UI hints (same shape as ``GET …/bookings/{id}/transitions/``).
        """
        job = self.get_object()
        return Response(transitions_payload_for_status(job.status))

    def _eligible_technician_profile(self, request):
        try:
            return TechnicianOnboardingService.check_eligibility(request.user)
        except TechnicianNotEligibleError as e:
            raise ValidationError(
                {
                    "detail": "Technician is not eligible for job actions.",
                    "onboarding_status": getattr(
                        e, "onboarding_status", None
                    ),
                    "missing_fields": getattr(e, "missing_fields", []),
                }
            ) from e

    def _job_for_technician_action(self, request, pk):
        self._eligible_technician_profile(request)
        try:
            job = Job.objects.select_related(
                "tenant", "booking", "booking__property", "assigned_to"
            ).get(pk=pk)
        except Job.DoesNotExist as e:
            raise NotFound() from e
        if job.tenant_id != getattr(request.user, "tenant_id", None):
            raise NotFound()
        return job

    @action(detail=True, methods=["post"], url_path="claim")
    def claim(self, request, pk=None):
        job = self._job_for_technician_action(request, pk)
        if job.status != JobStatus.OPEN or job.assigned_to_id is not None:
            raise ValidationError(
                {"detail": "Only open, unassigned jobs can be claimed."}
            )
        ensure_booking_for_job(job, actor=request.user, request=request)
        job.refresh_from_db(fields=["booking_id"])
        job.assigned_to = request.user
        job.status = JobStatus.ASSIGNED
        job.save(update_fields=["assigned_to", "status", "updated_at"])
        record_event(
            tenant_id=job.tenant_id,
            actor=request.user,
            event_type=EventType.JOB_CLAIMED,
            entity_type=EntityType.JOB,
            entity_id=job.id,
            payload={"technician_id": str(request.user.id)},
            request=request,
        )
        job = self.get_queryset().get(pk=job.pk)
        return Response(JobSerializer(job).data)

    @action(detail=True, methods=["post"], url_path="release")
    def release(self, request, pk=None):
        job = self._job_for_technician_action(request, pk)
        if job.assigned_to_id != request.user.id:
            raise ValidationError({"detail": "You are not assigned to this job."})
        if job.status != JobStatus.ASSIGNED:
            raise ValidationError(
                {"detail": "Only assigned jobs that have not been started can be released."}
            )
        job.assigned_to = None
        job.status = JobStatus.OPEN
        job.save(update_fields=["assigned_to", "status", "updated_at"])
        record_event(
            tenant_id=job.tenant_id,
            actor=request.user,
            event_type=EventType.JOB_RELEASED,
            entity_type=EntityType.JOB,
            entity_id=job.id,
            payload={},
            request=request,
        )
        job = self.get_queryset().get(pk=job.pk)
        return Response(JobSerializer(job).data)

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, pk=None):
        job = self._job_for_technician_action(request, pk)
        if job.assigned_to_id != request.user.id:
            raise ValidationError({"detail": "You are not assigned to this job."})
        if job.status != JobStatus.ASSIGNED:
            raise ValidationError(
                {"detail": "Job must be in assigned status to start."}
            )
        ensure_booking_for_job(job, actor=request.user, request=request)
        job.refresh_from_db(fields=["booking_id"])
        job.status = JobStatus.IN_PROGRESS
        job.save(update_fields=["status", "updated_at"])
        record_event(
            tenant_id=job.tenant_id,
            actor=request.user,
            event_type=EventType.JOB_STARTED,
            entity_type=EntityType.JOB,
            entity_id=job.id,
            payload={},
            request=request,
        )
        job = self.get_queryset().get(pk=job.pk)
        return Response(JobSerializer(job).data)

    @action(detail=True, methods=["post"], url_path="complete")
    def complete(self, request, pk=None):
        job = self._job_for_technician_action(request, pk)
        if job.assigned_to_id != request.user.id:
            raise ValidationError({"detail": "You are not assigned to this job."})
        if job.status != JobStatus.IN_PROGRESS:
            raise ValidationError(
                {"detail": "Job must be in progress to complete."}
            )
        job.status = JobStatus.COMPLETED
        job.save(update_fields=["status", "updated_at"])
        record_event(
            tenant_id=job.tenant_id,
            actor=request.user,
            event_type=EventType.JOB_COMPLETED,
            entity_type=EntityType.JOB,
            entity_id=job.id,
            payload={},
            request=request,
        )
        job = self.get_queryset().get(pk=job.pk)
        return Response(JobSerializer(job).data)
