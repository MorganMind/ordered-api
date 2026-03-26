"""
Tenant serializers.
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from .models import Tenant, validate_public_logo_url


class TenantSerializer(serializers.ModelSerializer):
    """
    Serializer for tenant details.
    """
    is_active = serializers.ReadOnlyField()
    
    class Meta:
        model = Tenant
        fields = [
            "id",
            "name",
            "slug",
            "status",
            "email",
            "phone",
            "operator_admin_email",
            "logo_url",
            "timezone",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class TenantNotificationSettingsSerializer(serializers.ModelSerializer):
    """Operator-editable notification address for the workspace tenant."""

    class Meta:
        model = Tenant
        fields = ["operator_admin_email"]


class TenantMePatchSerializer(serializers.ModelSerializer):
    """Workspace staff may PATCH their tenant via ``/tenants/me/`` (name, external ``logo_url``)."""

    class Meta:
        model = Tenant
        fields = ["name", "logo_url"]
        extra_kwargs = {
            "name": {"required": False},
            "logo_url": {"allow_null": True, "required": False, "allow_blank": True},
        }

    def validate_logo_url(self, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        try:
            validate_public_logo_url(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc))
        return value


class TenantMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal tenant info for nested representations.
    """
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]
