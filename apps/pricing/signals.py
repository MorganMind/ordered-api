from django.db.models.signals import post_delete
from django.dispatch import receiver

from apps.pricing.models import PriceSnapshot


@receiver(post_delete, sender=PriceSnapshot)
def clear_service_request_latest_price_snapshot(sender, instance: PriceSnapshot, **kwargs):
    """If the denormalized pointer aimed at this row, clear it when the snapshot is deleted."""
    if not instance.service_request_id:
        return
    from apps.service_requests.models import ServiceRequest

    ServiceRequest.objects.filter(
        pk=instance.service_request_id,
        latest_price_snapshot_id=instance.id,
    ).update(latest_price_snapshot=None)
