from django.db import models

from apps.core.models import TenantAwareModel


class BookingStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    CANCELLED = "cancelled", "Cancelled"
    FULFILLED = "fulfilled", "Fulfilled"


class BookingFrequency(models.TextChoices):
    ONE_TIME = "one_time", "One-time"
    WEEKLY = "weekly", "Weekly"
    BIWEEKLY = "biweekly", "Bi-weekly"
    MONTHLY = "monthly", "Monthly"


# Targets for operator UI (allowed_transitions).
BOOKING_ALLOWED_NEXT: dict[str, tuple[str, ...]] = {
    BookingStatus.DRAFT: (BookingStatus.PENDING, BookingStatus.CONFIRMED, BookingStatus.CANCELLED),
    BookingStatus.PENDING: (BookingStatus.CONFIRMED, BookingStatus.CANCELLED),
    BookingStatus.CONFIRMED: (BookingStatus.FULFILLED, BookingStatus.CANCELLED),
    BookingStatus.CANCELLED: (),
    BookingStatus.FULFILLED: (),
}

BOOKING_TERMINAL = frozenset({BookingStatus.CANCELLED, BookingStatus.FULFILLED})


class Booking(TenantAwareModel):
    """
    Tenant-scoped scheduled service visit (operator bookings UI).
    """

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    client_name = models.CharField(max_length=255, blank=True)
    client_email = models.EmailField(blank=True)
    client_phone = models.CharField(max_length=64, blank=True)

    scheduled_date = models.DateField(db_index=True)
    scheduled_start_time = models.TimeField(null=True, blank=True)
    scheduled_end_time = models.TimeField(null=True, blank=True)

    address = models.TextField(blank=True)
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )

    frequency = models.CharField(
        max_length=20,
        choices=BookingFrequency.choices,
        default=BookingFrequency.ONE_TIME,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.DRAFT,
        db_index=True,
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    pricing_breakdown = models.JSONField(default=dict, blank=True)

    notes = models.TextField(blank=True)
    client_notes = models.TextField(blank=True)

    confirmed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    recurring_service_series = models.ForeignKey(
        "bookings.RecurringServiceSeries",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bookings",
    )

    class Meta:
        db_table = "bookings"
        ordering = ["-scheduled_date", "-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-scheduled_date"]),
            models.Index(fields=["tenant", "client_name"]),
        ]

    def __str__(self) -> str:
        return self.title


class RecurringSeriesStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    ENDED = "ended", "Ended"


class RecurringServiceSeries(TenantAwareModel):
    """
    Tenant-scoped recurring visit schedule (bookings generated from this series).
    """

    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="recurring_series",
    )
    title = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=32,
        choices=RecurringSeriesStatus.choices,
        default=RecurringSeriesStatus.ACTIVE,
        db_index=True,
    )
    schedule = models.JSONField(
        default=dict,
        blank=True,
        help_text="Recurrence definition (e.g. RRULE payload or app-specific keys).",
    )
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    next_occurrence_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recurring_service_series"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.title or str(self.id)
