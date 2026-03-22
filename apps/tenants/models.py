"""
Tenant model - represents a business/operation using Ordered.
"""
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
    
    # Settings (JSONB for flexibility)
    settings = models.JSONField(default=dict, blank=True)
    
    # Metadata
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        validators=[validate_timezone],
        help_text="IANA timezone (e.g., 'America/New_York', 'Europe/London')"
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