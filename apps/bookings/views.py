from django.db.models import Count
from django.utils import timezone
from rest_framework import filters, pagination, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from apps.core.middleware import get_current_tenant_id
from apps.core.permissions import IsAdmin
from apps.events.models import EntityType, EventType
from apps.events.services import record_event
from apps.jobs.models import Job, JobStatus
from apps.jobs.serializers import JobSerializer

from .filters import BookingFilter
from .models import BOOKING_ALLOWED_NEXT, Booking, BookingStatus, RecurringServiceSeries
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    RecurringServiceSeriesSerializer,
)


class OperatorPagination(pagination.PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class RecurringServiceSeriesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Operator admin: list recurring visit series for the current tenant.

    Mounted at ``/api/v1/recurring-series/``.
    """

    serializer_class = RecurringServiceSeriesSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = OperatorPagination
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["status", "property"]
    ordering_fields = ["created_at", "next_occurrence_at", "status", "starts_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return RecurringServiceSeries.objects.none()
        qs = RecurringServiceSeries.objects.select_related("tenant", "property")
        if getattr(user, "is_superuser", False):
            return qs
        tid = getattr(user, "tenant_id", None)
        if tid:
            return qs.filter(tenant_id=tid)
        return RecurringServiceSeries.objects.none()


class BookingViewSet(viewsets.ModelViewSet):
    """
    Operator bookings: CRUD, status actions, job generation.

    Mounted at ``/api/v1/bookings/``.
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = OperatorPagination
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_class = BookingFilter
    search_fields = ["title", "client_name", "client_email", "address"]
    ordering_fields = ["scheduled_date", "created_at", "status", "title"]
    ordering = ["-scheduled_date", "-created_at"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Booking.objects.none()

        tid = get_current_tenant_id() or getattr(user, "tenant_id", None)
        qs = (
            Booking.objects.select_related("property", "tenant")
            .annotate(jobs_count=Count("jobs"))
            .order_by("-scheduled_date", "-created_at")
        )
        if getattr(user, "is_superuser", False):
            return qs
        if tid:
            return qs.filter(tenant_id=tid)
        return Booking.objects.none()

    def get_serializer_class(self):
        if self.action == "create":
            return BookingCreateSerializer
        return BookingSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tenant_id"] = get_current_tenant_id() or getattr(
            self.request.user, "tenant_id", None
        )
        return ctx

    def perform_create(self, serializer):
        tid = get_current_tenant_id() or self.request.user.tenant_id
        serializer.save(tenant_id=tid)

    @action(detail=True, methods=["get"], url_path="transitions")
    def transitions(self, request, pk=None):
        booking = self.get_object()
        allowed = list(BOOKING_ALLOWED_NEXT.get(booking.status, ()))
        meta = {
            "confirm": {
                "name": "confirm",
                "target": BookingStatus.CONFIRMED,
                "description": "Confirm booking",
            },
            "cancel": {
                "name": "cancel",
                "target": BookingStatus.CANCELLED,
                "description": "Cancel booking",
            },
            "fulfill": {
                "name": "fulfill",
                "target": BookingStatus.FULFILLED,
                "description": "Mark fulfilled",
            },
        }
        transitions = [meta[k] for k in meta if meta[k]["target"] in allowed]
        return Response(
            {
                "allowed_transitions": allowed,
                "transitions": transitions,
            }
        )

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        booking = self.get_object()
        if booking.status not in (BookingStatus.DRAFT, BookingStatus.PENDING):
            raise ValidationError(
                {"detail": "Only draft or pending bookings can be confirmed."}
            )
        booking.status = BookingStatus.CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.save(update_fields=["status", "confirmed_at", "updated_at"])
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status in (BookingStatus.CANCELLED, BookingStatus.FULFILLED):
            raise ValidationError({"detail": "Booking is already terminal."})
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.save(update_fields=["status", "cancelled_at", "updated_at"])
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"], url_path="fulfill")
    def fulfill(self, request, pk=None):
        booking = self.get_object()
        if booking.status != BookingStatus.CONFIRMED:
            raise ValidationError({"detail": "Only confirmed bookings can be fulfilled."})
        booking.status = BookingStatus.FULFILLED
        booking.fulfilled_at = timezone.now()
        booking.save(update_fields=["status", "fulfilled_at", "updated_at"])
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=["post"], url_path="generate_job")
    def generate_job(self, request, pk=None):
        booking = self.get_object()
        job = Job.objects.create(
            tenant_id=booking.tenant_id,
            title=booking.title,
            booking=booking,
            status=JobStatus.OPEN,
        )
        record_event(
            tenant_id=booking.tenant_id,
            actor=request.user,
            event_type=EventType.BOOKING_JOB_GENERATED,
            entity_type=EntityType.BOOKING,
            entity_id=booking.id,
            payload={"job_id": str(job.id)},
            request=request,
        )
        job = Job.objects.select_related(
            "booking", "booking__property", "assigned_to"
        ).get(pk=job.pk)
        return Response(JobSerializer(job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="jobs")
    def jobs(self, request, pk=None):
        booking = self.get_object()
        qs = (
            Job.objects.filter(booking=booking)
            .select_related("booking", "booking__property", "tenant", "assigned_to")
            .order_by("-created_at")
        )
        paginator = OperatorPagination()
        page = paginator.paginate_queryset(qs, request)
        serializer = JobSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
