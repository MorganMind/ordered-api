"""
Tenant model - represents a business/operation using Ordered.
"""
import ipaddress
from urllib.parse import urlparse

from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from zoneinfo import ZoneInfo


def validate_timezone(value):
    """Validate that the timezone is a valid IANA timezone."""
    try:
        ZoneInfo(value)
    except KeyError:
        raise ValidationError(f"'{value}' is not a valid timezone.")


def validate_public_logo_url(value):
    """
    Reject localhost/private-network URLs for tenant logo storage.
    """
    if not value:
        return
    parsed = urlparse(value)
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return
    if host in {"localhost", "127.0.0.1", "::1"}:
        raise ValidationError(
            "Logo URL must be publicly reachable; localhost URLs are not allowed."
        )
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    ):
        raise ValidationError(
            "Logo URL must be publicly reachable; private network addresses are not allowed."
        )


class TenantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    TRIAL = "trial", "Trial"


class Tenant(BaseModel):
    """
    A tenant represents a single business operation (e.g., a cleaning company).
    All data is isolated by tenant_id.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.TRIAL,
        db_index=True,
    )
    
    # Contact info
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    operator_admin_email = models.EmailField(
        blank=True,
        default="",
        help_text=(
            "Receives a notification when someone submits a technician application "
            "(public form). Leave blank to skip operator copy."
        ),
    )
    
    # Settings (JSONB for flexibility)
    settings = models.JSONField(default=dict, blank=True)
    
    # Metadata
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        validators=[validate_timezone],
        help_text="IANA timezone (e.g., 'America/New_York', 'Europe/London')"
    )
    logo_url = models.URLField(
        max_length=2048,
        null=True,
        blank=True,
        help_text="Public URL for workspace/organization logo (upload via API or external CDN).",
    )
    
    class Meta:
        db_table = "tenants"
        ordering = ["name"]
    
    def __str__(self):
        return self.name
    
    @property
    def is_active(self):
        return self.status in [TenantStatus.ACTIVE, TenantStatus.TRIAL]
    
    def clean(self):
        super().clean()
        # Validate timezone on clean
        validate_timezone(self.timezone)
        validate_public_logo_url(self.logo_url)