import uuid

from django.conf import settings
from django.db import models

from apps.core.models import TenantAwareModel


class JobStatus(models.TextChoices):
    """Lifecycle for field execution; kept as strings for API compatibility."""

    OPEN = "open", "Open"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


class Skill(models.Model):
    """
    Tenant-agnostic catalog entry (technician capabilities, job matching).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=100, unique=True, db_index=True)
    label = models.CharField(max_length=255)
    category = models.CharField(max_length=100, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "skills"
        ordering = ["category", "label"]

    def __str__(self):
        return self.label


class Job(TenantAwareModel):
    title = models.CharField(max_length=255)
    status = models.CharField(
        max_length=32,
        default=JobStatus.OPEN,
        db_index=True,
    )
    booking = models.ForeignKey(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="jobs",
    )
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
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_jobs",
    )

    class Meta:
        db_table = "jobs"

    def __str__(self):
        return self.title
