from decimal import Decimal, InvalidOperation

from rest_framework import serializers

from .models import (
    BOOKING_ALLOWED_NEXT,
    BOOKING_TERMINAL,
    Booking,
    RecurringServiceSeries,
)


class BookingSerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(read_only=True)
    property = serializers.UUIDField(
        source="property_id",
        allow_null=True,
        required=False,
    )
    property_address = serializers.SerializerMethodField()
    allowed_transitions = serializers.SerializerMethodField()
    is_terminal = serializers.SerializerMethodField()
    jobs_count = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = [
            "id",
            "tenant_id",
            "title",
            "description",
            "client_name",
            "client_email",
            "client_phone",
            "scheduled_date",
            "scheduled_start_time",
            "scheduled_end_time",
            "address",
            "property",
            "property_address",
            "frequency",
            "status",
            "total_amount",
            "pricing_breakdown",
            "notes",
            "client_notes",
            "confirmed_at",
            "cancelled_at",
            "fulfilled_at",
            "allowed_transitions",
            "is_terminal",
            "jobs_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "status",
            "confirmed_at",
            "cancelled_at",
            "fulfilled_at",
            "property_address",
            "allowed_transitions",
            "is_terminal",
            "jobs_count",
            "created_at",
            "updated_at",
        ]

    def get_property_address(self, obj: Booking):
        p = getattr(obj, "property", None)
        if not p:
            return None
        return p.address or p.address_line_1 or None

    def get_allowed_transitions(self, obj: Booking):
        return list(BOOKING_ALLOWED_NEXT.get(obj.status, ()))

    def get_is_terminal(self, obj: Booking):
        return obj.status in BOOKING_TERMINAL

    def get_jobs_count(self, obj: Booking):
        if hasattr(obj, "jobs_count"):
            return obj.jobs_count
        return obj.jobs.count()

    def validate_property(self, value):
        if value is None:
            return value
        tid = self.context.get("tenant_id")
        if tid:
            from apps.properties.models import Property

            if not Property.objects.filter(pk=value, tenant_id=tid).exists():
                raise serializers.ValidationError(
                    "Property not found for this workspace."
                )
        return value

    def validate_total_amount(self, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                return Decimal(value)
            except (InvalidOperation, ValueError) as e:
                raise serializers.ValidationError("Invalid decimal.") from e
        return value

class BookingCreateSerializer(serializers.ModelSerializer):
    """POST body — status allowed on create per operator UI."""

    tenant_id = serializers.UUIDField(read_only=True)
    property = serializers.UUIDField(
        source="property_id",
        allow_null=True,
        required=False,
    )
    property_address = serializers.SerializerMethodField(read_only=True)
    allowed_transitions = serializers.SerializerMethodField(read_only=True)
    is_terminal = serializers.SerializerMethodField(read_only=True)
    jobs_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Booking
        fields = [
            "id",
            "tenant_id",
            "title",
            "description",
            "client_name",
            "client_email",
            "client_phone",
            "scheduled_date",
            "scheduled_start_time",
            "scheduled_end_time",
            "address",
            "property",
            "property_address",
            "frequency",
            "status",
            "total_amount",
            "pricing_breakdown",
            "notes",
            "client_notes",
            "confirmed_at",
            "cancelled_at",
            "fulfilled_at",
            "allowed_transitions",
            "is_terminal",
            "jobs_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "tenant_id",
            "confirmed_at",
            "cancelled_at",
            "fulfilled_at",
            "property_address",
            "allowed_transitions",
            "is_terminal",
            "jobs_count",
            "created_at",
            "updated_at",
        ]

    def get_property_address(self, obj: Booking):
        p = getattr(obj, "property", None)
        if not p:
            return None
        return p.address or p.address_line_1 or None

    def get_allowed_transitions(self, obj: Booking):
        return list(BOOKING_ALLOWED_NEXT.get(obj.status, ()))

    def get_is_terminal(self, obj: Booking):
        return obj.status in BOOKING_TERMINAL

    def get_jobs_count(self, obj: Booking):
        if obj.pk:
            return obj.jobs.count()
        return 0

    def validate_property(self, value):
        if value is None:
            return value
        tid = self.context.get("tenant_id")
        if tid:
            from apps.properties.models import Property

            if not Property.objects.filter(pk=value, tenant_id=tid).exists():
                raise serializers.ValidationError(
                    "Property not found for this workspace."
                )
        return value

    def validate_total_amount(self, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                return Decimal(value)
            except (InvalidOperation, ValueError) as e:
                raise serializers.ValidationError("Invalid decimal.") from e
        return value


class RecurringServiceSeriesSerializer(serializers.ModelSerializer):
    """List/detail shape for operator admin."""

    property = serializers.UUIDField(source="property_id", allow_null=True, read_only=True)

    class Meta:
        model = RecurringServiceSeries
        fields = [
            "id",
            "property",
            "title",
            "status",
            "schedule",
            "starts_at",
            "ends_at",
            "next_occurrence_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
