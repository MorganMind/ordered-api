from __future__ import annotations

from rest_framework import serializers

from apps.properties.models import Property

from .models import (
    VALID_STATUS_TRANSITIONS,
    ServiceRequest,
    ServiceRequestStatus,
)


class TimingPreferenceSerializer(serializers.Serializer):
    """
    Flexible scheduling preference — not a strict datetime.

    All fields are optional; an empty dict is valid (means "no preference").
    """

    DAYS = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    TIME_OF_DAY = ["morning", "afternoon", "evening", "flexible"]
    FLEXIBILITY = ["flexible", "semi_flexible", "fixed"]

    preferred_days = serializers.ListField(
        child=serializers.ChoiceField(choices=DAYS),
        required=False,
        default=list,
        allow_empty=True,
    )
    preferred_time_of_day = serializers.ChoiceField(
        choices=TIME_OF_DAY,
        required=False,
        default="flexible",
    )
    date_range_start = serializers.DateField(required=False, allow_null=True)
    date_range_end = serializers.DateField(required=False, allow_null=True)
    flexibility = serializers.ChoiceField(
        choices=FLEXIBILITY,
        required=False,
        default="flexible",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
    )

    def validate(self, data: dict) -> dict:
        start = data.get("date_range_start")
        end = data.get("date_range_end")
        if start and end and end < start:
            raise serializers.ValidationError(
                {"date_range_end": "Must be on or after date_range_start."}
            )
        return data


class MediaRefSerializer(serializers.Serializer):
    MEDIA_TYPES = ["image", "video", "document"]

    type = serializers.ChoiceField(choices=MEDIA_TYPES)
    storage_key = serializers.CharField(max_length=512)
    url = serializers.URLField(required=False, allow_blank=True)


class ServiceRequestSerializer(serializers.ModelSerializer):
    """
    Client-safe read representation.

    Does NOT include internal_operator_notes — use ServiceRequestOperatorSerializer
    for operator reads.
    """

    property = serializers.PrimaryKeyRelatedField(
        source="property_ref",
        read_only=True,
    )
    tenant = serializers.UUIDField(source="tenant_id", read_only=True)
    client = serializers.UUIDField(source="client_id", allow_null=True, read_only=True)
    latest_price_snapshot = serializers.UUIDField(
        source="latest_price_snapshot_id", allow_null=True, read_only=True
    )
    converted_job = serializers.UUIDField(
        source="converted_job_id", allow_null=True, read_only=True
    )

    class Meta:
        model = ServiceRequest
        fields = [
            "id",
            "tenant",
            "client",
            "property",
            "contact_name",
            "contact_phone",
            "contact_email",
            "address_raw",
            "address_normalized",
            "square_feet",
            "bedrooms",
            "bathrooms",
            "service_type",
            "timing_preference",
            "notes",
            "media_refs",
            "status",
            "source",
            "latest_price_snapshot",
            "converted_job",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ServiceRequestOperatorSerializer(ServiceRequestSerializer):
    class Meta(ServiceRequestSerializer.Meta):
        fields = ServiceRequestSerializer.Meta.fields + [
            "internal_operator_notes",
        ]
        read_only_fields = fields


class ServiceRequestCreateSerializer(serializers.ModelSerializer):
    """
    Intake / API submission.

    Excluded from client control: tenant, client, source, status,
    address_normalized, latest_price_snapshot, converted_job,
    internal_operator_notes.
    """

    timing_preference = TimingPreferenceSerializer(required=False, default=dict)
    media_refs = MediaRefSerializer(many=True, required=False, default=list)
    property = serializers.PrimaryKeyRelatedField(
        source="property_ref",
        queryset=Property.objects.all(),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = ServiceRequest
        fields = [
            "property",
            "contact_name",
            "contact_phone",
            "contact_email",
            "address_raw",
            "square_feet",
            "bedrooms",
            "bathrooms",
            "service_type",
            "timing_preference",
            "notes",
            "media_refs",
        ]

    def validate(self, data: dict) -> dict:
        if not data.get("contact_phone") and not data.get("contact_email"):
            raise serializers.ValidationError(
                "At least one of contact_phone or contact_email is required."
            )
        return data

    def create(self, validated_data):
        timing = validated_data.pop("timing_preference", None)
        media = validated_data.pop("media_refs", None)
        inst = super().create(validated_data)
        if timing is not None:
            inst.timing_preference = timing
        if media is not None:
            inst.media_refs = media
        if timing is not None or media is not None:
            inst.save(update_fields=["timing_preference", "media_refs", "updated_at"])
        return inst


class ServiceRequestClientUpdateSerializer(serializers.ModelSerializer):
    timing_preference = TimingPreferenceSerializer(required=False)
    media_refs = MediaRefSerializer(many=True, required=False)

    class Meta:
        model = ServiceRequest
        fields = [
            "contact_name",
            "contact_phone",
            "contact_email",
            "address_raw",
            "square_feet",
            "bedrooms",
            "bathrooms",
            "service_type",
            "timing_preference",
            "notes",
            "media_refs",
        ]

    def validate(self, data: dict) -> dict:
        instance = self.instance
        phone = data.get(
            "contact_phone", instance.contact_phone if instance else ""
        )
        email = data.get(
            "contact_email", instance.contact_email if instance else ""
        )
        if not phone and not email:
            raise serializers.ValidationError(
                "At least one of contact_phone or contact_email is required."
            )
        return data

    def update(self, instance, validated_data):
        timing = validated_data.pop("timing_preference", serializers.empty)
        media = validated_data.pop("media_refs", serializers.empty)
        inst = super().update(instance, validated_data)
        update_fields = []
        if timing is not serializers.empty:
            inst.timing_preference = timing
            update_fields.append("timing_preference")
        if media is not serializers.empty:
            inst.media_refs = media
            update_fields.append("media_refs")
        if update_fields:
            update_fields.append("updated_at")
            inst.save(update_fields=update_fields)
        return inst


class ServiceRequestOperatorUpdateSerializer(ServiceRequestClientUpdateSerializer):
    class Meta(ServiceRequestClientUpdateSerializer.Meta):
        fields = ServiceRequestClientUpdateSerializer.Meta.fields + [
            "address_normalized",
            "internal_operator_notes",
        ]


class ServiceRequestStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ServiceRequestStatus.choices)

    def validate_status(self, value: str) -> str:
        if self.instance is None:
            return value

        current = self.instance.status
        allowed = VALID_STATUS_TRANSITIONS.get(current, frozenset())

        if value not in allowed:
            terminal_msg = " This state is terminal." if not allowed else ""
            raise serializers.ValidationError(
                f"Cannot transition from '{current}' to '{value}'."
                f"{terminal_msg}"
                f" Allowed transitions: {sorted(allowed) or 'none'}."
            )
        return value
