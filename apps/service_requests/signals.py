from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.events.models import EntityType, EventType
from apps.events.services import record_event

from .models import ServiceRequest


@receiver(post_save, sender=ServiceRequest)
def service_request_created_audit(
    sender,
    instance: ServiceRequest,
    created: bool,
    **kwargs,
) -> None:
    """
    Single source of creation audit events — do not duplicate in perform_create.
    """
    if not created:
        return

    record_event(
        tenant_id=instance.tenant_id,
        actor=None,
        event_type=EventType.SERVICE_REQUEST_CREATED,
        entity_type=EntityType.SERVICE_REQUEST,
        entity_id=instance.id,
        payload={
            "service_type": instance.service_type,
            "status": instance.status,
            "source": instance.source,
        },
    )
