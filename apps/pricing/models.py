from django.db import models

from apps.core.models import TenantAwareModel


class PriceSnapshot(TenantAwareModel):
    """
    PriceSnapshot.service_request owns the FK history; ServiceRequest.latest_price_snapshot
    is a denormalized pointer to the most recent row. Only pricing helpers should set
    latest_price_snapshot, and it must always reference a snapshot with service_request=this SR.
    """

    service_request = models.ForeignKey(
        "service_requests.ServiceRequest",
        on_delete=models.CASCADE,
        related_name="price_snapshots",
        null=True,
        blank=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    total_cents = models.BigIntegerField()
    subtotal_cents = models.BigIntegerField(default=0)
    line_items = models.JSONField(default=list)
    inputs_used = models.JSONField(
        default=dict,
        help_text="Structured pricing inputs copied from ServiceRequest at quote time",
    )
    pricing_engine_version = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "price_snapshots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "service_request", "-created_at"]),
        ]
