"""
Auto-create TechnicianProfile when a User with role=TECHNICIAN is saved.

Handles both creation and role changes (e.g. client promoted to technician).
Uses get_or_create to be idempotent.
"""
import structlog
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.users.models import User, UserRole
from apps.technicians.models import TechnicianProfile, OnboardingStatus

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=User)
def ensure_technician_profile(sender, instance: User, created: bool, **kwargs):
    """Create a TechnicianProfile for any user with role=TECHNICIAN."""
    if instance.role != UserRole.TECHNICIAN:
        return

    profile, was_created = TechnicianProfile.objects.get_or_create(
        user=instance,
        defaults={
            "tenant": instance.tenant,
            "onboarding_status": OnboardingStatus.PENDING_ONBOARDING,
        },
    )

    if was_created:
        logger.info(
            "technician_profile_created",
            user_id=str(instance.id),
            tenant_id=str(instance.tenant_id),
        )
    elif profile.tenant_id != instance.tenant_id:
        # Keep tenant in sync if user somehow changed tenants
        profile.tenant = instance.tenant
        profile.save(update_fields=["tenant", "updated_at"])
