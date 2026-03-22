"""
Serializers for event models.
"""
import uuid

from django.db import DatabaseError
from rest_framework import serializers

from .models import Event


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model."""

    actor = serializers.SerializerMethodField()
    actor_email = serializers.SerializerMethodField()
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "event_type",
            "entity_type",
            "entity_id",
            "actor",
            "actor_email",
            "actor_name",
            "payload",
            "ip_address",
            "created_at",
        ]
        read_only_fields = fields

    def get_actor(self, obj):
        """
        Expose actor as a UUID string when the stored FK matches users_user.
        Legacy schemas may use integer actor_id (e.g. auth_user); those cannot
        be represented as a user UUID and are returned as null.
        """
        aid = getattr(obj, "actor_id", None)
        if aid is None:
            return None
        if isinstance(aid, int):
            return None
        if isinstance(aid, uuid.UUID):
            return str(aid)
        try:
            return str(uuid.UUID(str(aid)))
        except (ValueError, TypeError, AttributeError):
            return None

    def _actor_user(self, obj):
        aid = getattr(obj, "actor_id", None)
        if aid is None:
            return None
        if isinstance(aid, int):
            return None
        if not isinstance(aid, uuid.UUID):
            try:
                aid = uuid.UUID(str(aid))
            except (ValueError, TypeError, AttributeError):
                return None
        try:
            from apps.users.models import User

            return User.objects.filter(pk=aid).only("email", "first_name", "last_name").first()
        except DatabaseError:
            return None

    def get_actor_email(self, obj):
        u = self._actor_user(obj)
        return u.email if u else None

    def get_actor_name(self, obj):
        u = self._actor_user(obj)
        return u.full_name if u else None
