from __future__ import annotations

from rest_framework import serializers

from apps.jobs.models import Skill
from apps.properties.models import Property

from .models import (
    VALID_STATUS_TRANSITIONS,
    ServiceOffering,
    ServiceOfferingSkill,
    ServiceRequest,
    ServiceRequestStatus,
    ServiceType,
)


def _skills_payload_for_offering(obj: ServiceOffering) -> list[dict]:
    links = getattr(obj, "_prefetched_objects_cache", {}).get("offering_skills")
    if links is not None:
        ordered = sorted(
            links,
            key=lambda x: (x.sort_order, x.skill.label),
        )
    else:
        ordered = (
            ServiceOfferingSkill.objects.filter(service_offering=obj)
            .select_related("skill")
            .order_by("sort_order", "skill__label")
        )
    return [
        {
            "id": str(link.skill_id),
            "key": link.skill.key,
            "label": link.skill.label,
            "category": link.skill.category,
            "is_active": link.skill.is_active,
            "sort_order": link.sort_order,
        }
        for link in ordered
    ]


class ServiceOfferingSerializer(serializers.ModelSerializer):
    """Read representation with ordered nested skills."""

    tenant = serializers.UUIDField(source="tenant_id", read_only=True)
    skills = serializers.SerializerMethodField()

    class Meta:
        model = ServiceOffering
        fields = [
            "id",
            "tenant",
            "name",
            "slug",
            "description",
            "is_active",
            "sort_order",
            "reporting_category",
            "skills",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_skills(self, obj: ServiceOffering) -> list[dict]:
        return _skills_payload_for_offering(obj)


class ServiceOfferingWriteSerializer(serializers.ModelSerializer):
    """Operator create/update; ``skill_ids`` defines order."""

    skill_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        default=list,
    )

    class Meta:
        model = ServiceOffering
        fields = [
            "name",
            "slug",
            "description",
            "is_active",
            "sort_order",
            "reporting_category",
            "skill_ids",
        ]

    def validate(self, data: dict) -> dict:
        request = self.context.get("request")
        tid = getattr(request.user, "tenant_id", None) if request else None
        slug = data.get("slug")
        if slug and tid:
            qs = ServiceOffering.objects.filter(tenant_id=tid, slug=slug)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"slug": "An offering with this slug already exists in this workspace."}
                )
        return data

    def create(self, validated_data: dict) -> ServiceOffering:
        skill_ids = validated_data.pop("skill_ids", [])
        tenant_id = validated_data.pop("tenant_id")
        off = ServiceOffering.objects.create(tenant_id=tenant_id, **validated_data)
        self._set_skills(off, skill_ids)
        return off

    def update(self, instance: ServiceOffering, validated_data: dict) -> ServiceOffering:
        skill_ids = validated_data.pop("skill_ids", serializers.empty)
        inst = super().update(instance, validated_data)
        if skill_ids is not serializers.empty:
            self._set_skills(inst, skill_ids)
        return inst

    def _set_skills(self, offering: ServiceOffering, skill_ids: list) -> None:
        ServiceOfferingSkill.objects.filter(service_offering=offering).delete()
        if not skill_ids:
            return
        by_id = {
            str(s.id): s
            for s in Skill.objects.filter(id__in=skill_ids, is_active=True)
        }
        if len(by_id) != len(skill_ids):
            raise serializers.ValidationError(
                {
                    "skill_ids": (
                        "Each id must be a unique, active skill from the catalog."
                    )
                }
            )
        to_create = []
        for order, sid in enumerate(skill_ids):
            sk = by_id.get(str(sid))
            if sk is None:
                raise serializers.ValidationError(
                    {"skill_ids": f"Unknown or inactive skill id: {sid}"}
                )
            to_create.append(
                ServiceOfferingSkill(
                    service_offering=offering,
                    skill=sk,
                    sort_order=order,
                )
            )
        ServiceOfferingSkill.objects.bulk_create(to_create)


class ServiceOfferingBriefSerializer(serializers.ModelSerializer):
    skills = serializers.SerializerMethodField()

    class Meta:
        model = ServiceOffering
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "is_active",
            "sort_order",
            "reporting_category",
            "skills",
        ]
        read_only_fields = fields

    def get_skills(self, obj: ServiceOffering) -> list[dict]:
        return _skills_payload_for_offering(obj)


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


def _validate_offering_belongs_to_workspace(
    offering: ServiceOffering | None,
    request,
) -> None:
    if offering is None:
        return
    tid = getattr(request.user, "tenant_id", None) if request else None
    if not tid or offering.tenant_id != tid:
        raise serializers.ValidationError(
            "That service offering does not belong to your workspace."
        )
    if not offering.is_active:
        raise serializers.ValidationError("This service offering is not active.")


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
    service_offering = ServiceOfferingBriefSerializer(read_only=True, allow_null=True)
    service_label = serializers.CharField(
        source="service_display_label",
        read_only=True,
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
            "service_offering",
            "service_label",
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
    service_type = serializers.ChoiceField(
        choices=ServiceType.choices,
        required=False,
    )
    service_offering = serializers.PrimaryKeyRelatedField(
        queryset=ServiceOffering.objects.all(),
        required=False,
        allow_null=True,
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
            "service_offering",
            "timing_preference",
            "notes",
            "media_refs",
        ]

    def validate_service_offering(self, value: ServiceOffering | None) -> ServiceOffering | None:
        request = self.context.get("request")
        _validate_offering_belongs_to_workspace(value, request)
        return value

    def validate(self, data: dict) -> dict:
        if not data.get("contact_phone") and not data.get("contact_email"):
            raise serializers.ValidationError(
                "At least one of contact_phone or contact_email is required."
            )
        off = data.get("service_offering")
        st = data.get("service_type")
        if off is None and not st:
            raise serializers.ValidationError(
                {
                    "service_type": (
                        "Required when service_offering is omitted, "
                        "or send service_offering instead."
                    )
                }
            )
        if (
            off is not None
            and st is not None
            and st != off.reporting_category
        ):
            raise serializers.ValidationError(
                {
                    "service_type": (
                        "Must match reporting_category on the selected "
                        "service_offering, or omit service_type."
                    )
                }
            )
        return data

    def create(self, validated_data):
        off = validated_data.get("service_offering")
        if off is not None:
            validated_data["service_type"] = off.reporting_category
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
    service_type = serializers.ChoiceField(
        choices=ServiceType.choices,
        required=False,
    )
    service_offering = serializers.PrimaryKeyRelatedField(
        queryset=ServiceOffering.objects.all(),
        required=False,
        allow_null=True,
    )

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
            "service_offering",
            "timing_preference",
            "notes",
            "media_refs",
        ]

    def validate_service_offering(self, value: ServiceOffering | None) -> ServiceOffering | None:
        request = self.context.get("request")
        _validate_offering_belongs_to_workspace(value, request)
        return value

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
        off = data.get("service_offering", serializers.empty)
        st = data.get("service_type", serializers.empty)
        if off is not serializers.empty and off is not None:
            if st is not serializers.empty and st != off.reporting_category:
                raise serializers.ValidationError(
                    {
                        "service_type": (
                            "Must match reporting_category on the selected "
                            "service_offering, or omit service_type."
                        )
                    }
                )
        return data

    def update(self, instance, validated_data):
        timing = validated_data.pop("timing_preference", serializers.empty)
        media = validated_data.pop("media_refs", serializers.empty)
        off = validated_data.pop("service_offering", serializers.empty)
        if off is not serializers.empty:
            if off is None:
                validated_data["service_offering"] = None
            else:
                validated_data["service_offering"] = off
                validated_data["service_type"] = off.reporting_category
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
