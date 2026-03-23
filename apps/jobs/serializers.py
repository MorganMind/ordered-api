from rest_framework import serializers

from .models import Job, Skill


class SkillSerializer(serializers.ModelSerializer):
    """
    Skills use UUID primary keys. Expose ``pk`` (alias of ``id``) so clients
    that expect a ``pk`` field match DRF conventions; values are UUID strings,
    not integers.
    """

    pk = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = Skill
        fields = ["id", "pk", "key", "label", "category", "is_active"]
        read_only_fields = fields


class JobSerializer(serializers.ModelSerializer):
    """FKs as raw UUIDs so job queries need not JOIN ``users_user``."""

    tenant = serializers.UUIDField(source="tenant_id", read_only=True)
    service_request = serializers.UUIDField(
        source="service_request_id", read_only=True, allow_null=True
    )
    created_by = serializers.UUIDField(
        source="created_by_id", read_only=True, allow_null=True
    )
    booking_id = serializers.UUIDField(
        source="booking_id", read_only=True, allow_null=True
    )
    booking_title = serializers.SerializerMethodField()
    scheduled_date = serializers.SerializerMethodField()
    scheduled_start_time = serializers.SerializerMethodField()
    scheduled_end_time = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "tenant",
            "title",
            "status",
            "booking_id",
            "booking_title",
            "scheduled_date",
            "scheduled_start_time",
            "scheduled_end_time",
            "address",
            "customer_name",
            "customer_phone",
            "customer_email",
            "service_request",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_booking_title(self, obj: Job):
        return obj.booking.title if obj.booking_id else None

    def get_scheduled_date(self, obj: Job):
        return obj.booking.scheduled_date if obj.booking_id else None

    def get_scheduled_start_time(self, obj: Job):
        if not obj.booking_id:
            return None
        t = obj.booking.scheduled_start_time
        return t.isoformat() if t else None

    def get_scheduled_end_time(self, obj: Job):
        if not obj.booking_id:
            return None
        t = obj.booking.scheduled_end_time
        return t.isoformat() if t else None

    def get_address(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.address or ""

    def get_customer_name(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.client_name or ""

    def get_customer_phone(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.client_phone or ""

    def get_customer_email(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.client_email or ""
