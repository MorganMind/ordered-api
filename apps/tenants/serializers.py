"""
Tenant serializers.
"""
from rest_framework import serializers
from .models import Tenant


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
            "timezone",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class TenantMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal tenant info for nested representations.
    """
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug"]
