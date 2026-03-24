from __future__ import annotations

from django.db import transaction

from apps.events.models import EntityType, EventType
from apps.events.services import record_event
from apps.jobs.models import Job, JobStatus
from apps.jobs.services.booking_link import ensure_booking_for_job
from apps.service_requests.models import ServiceRequest, ServiceRequestStatus


@transaction.atomic
def convert_service_request_to_job(
    sr: ServiceRequest,
    *,
    actor,
    title: str | None = None,
    request=None,
) -> Job:
    job = Job.objects.create(
        tenant_id=sr.tenant_id,
        title=title or f"{sr.service_type} — {sr.contact_name}",
        status=JobStatus.OPEN,
        service_request=sr,
        created_by=actor,
    )
    sr.converted_job = job
    sr.status = ServiceRequestStatus.CONVERTED
    sr.save(update_fields=["converted_job", "status", "updated_at"])
    booking = ensure_booking_for_job(job, actor=actor, request=request)
    record_event(
        tenant_id=sr.tenant_id,
        actor=actor,
        event_type=EventType.SERVICE_REQUEST_CONVERTED,
        entity_type=EntityType.SERVICE_REQUEST,
        entity_id=sr.id,
        payload={
            "job_id": str(job.id),
            "booking_id": str(booking.id),
        },
        request=request,
    )
    return job
