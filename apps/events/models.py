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
        help_text="Type of event that occurred"
    )
    
    # Entity reference
    entity_type = models.CharField(
        max_length=50,
        choices=EntityType.choices,
        db_index=True,
        help_text="Type of entity this event relates to"
    )
    entity_id = models.UUIDField(
        db_index=True,
        help_text="ID of the entity this event relates to"
    )
    
    # Event data
    payload = models.JSONField(
        default=dict,
        help_text="Event-specific data and context"
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request that triggered the event"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent of the request"
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
