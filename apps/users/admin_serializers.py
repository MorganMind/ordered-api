"""
Operator/admin serializers for tenant-scoped client (customer) users.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class ClientListSerializer(serializers.ModelSerializer):
    """
    List row for ``GET /api/v1/admin/clients/``.

    Expects queryset annotated with ``_service_request_count`` and ``_jobs_created_count``.
    """

    full_name = serializers.CharField(read_only=True)
    service_request_count = serializers.IntegerField(
        source="_service_request_count", read_only=True
    )
    jobs_created_count = serializers.IntegerField(
        source="_jobs_created_count", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "avatar_url",
            "status",
            "is_active",
            "service_request_count",
            "jobs_created_count",
            "created_at",
        ]
        read_only_fields = fields


class ClientAdminDetailSerializer(serializers.ModelSerializer):
    """Full read model for ``GET /api/v1/admin/clients/{id}/``."""

    full_name = serializers.CharField(read_only=True)
    tenant_id = serializers.UUIDField(read_only=True)
    service_request_count = serializers.IntegerField(
        source="_service_request_count", read_only=True
    )
    jobs_created_count = serializers.IntegerField(
        source="_jobs_created_count", read_only=True
    )

    class Meta:
        model = User
        fields = [
            "id",
            "tenant_id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "avatar_url",
            "role",
            "status",
            "is_active",
            "supabase_uid",
            "metadata",
            "service_request_count",
            "jobs_created_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
