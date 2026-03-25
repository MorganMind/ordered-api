"""
Ensure every job that enters scheduling / field execution has a linked ``Booking``.

Auto-creates a **draft** booking from ``ServiceRequest`` when the job has no booking.
"""
from __future__ import annotations

from datetime import date

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking, BookingFrequency, BookingStatus
from apps.events.models import EntityType, EventType
from apps.events.services import record_event


def _scheduled_date_from_service_request(sr) -> date:
    tp = sr.timing_preference or {}
    if not isinstance(tp, dict):
        return timezone.now().date()
    for key in ("date_range_start", "preferred_date", "date"):
        raw = tp.get(key)
        if raw and isinstance(raw, str):
            d = parse_date(raw[:10])
            if d:
                return d
    return timezone.now().date()


@transaction.atomic
def ensure_booking_for_job(job, *, actor, request=None):
    """
    If ``job.booking`` is set, return it.

    Otherwise require ``job.service_request`` and create a **draft** booking
    (scheduled date from SR timing preference or today), link it to the job, and log an event.

    Raises ``ValidationError`` if there is no booking and no service request.
    """
    if job.booking_id:
        return job.booking

    sr = getattr(job, "service_request", None)
    if sr is None and job.service_request_id:
        from apps.service_requests.models import ServiceRequest

        sr = (
            ServiceRequest.objects.select_related("service_offering")
            .filter(pk=job.service_request_id)
            .first()
        )
    if sr is None:
        raise ValidationError(
            {
                "detail": (
                    "This job has no linked booking. Link a booking or ensure the job "
                    "has a service request so a draft booking can be created automatically."
                )
            }
        )

    title = (job.title or f"{sr.service_display_label} — {sr.contact_name}")[:255]
    booking = Booking.objects.create(
        tenant_id=job.tenant_id,
        title=title,
        client_name=(sr.contact_name or "")[:255],
        client_email=sr.contact_email or "",
        client_phone=sr.contact_phone or "",
        scheduled_date=_scheduled_date_from_service_request(sr),
        address=sr.address_raw or "",
        property_id=sr.property_ref_id,
        status=BookingStatus.DRAFT,
        frequency=BookingFrequency.ONE_TIME,
    )
    job.booking = booking
    job.save(update_fields=["booking", "updated_at"])

    record_event(
        tenant_id=job.tenant_id,
        actor=actor,
        event_type=EventType.BOOKING_CREATED,
        entity_type=EntityType.BOOKING,
        entity_id=booking.id,
        payload={
            "source": "auto_from_service_request",
            "job_id": str(job.id),
            "service_request_id": str(sr.id),
        },
        request=request,
    )
    return booking
