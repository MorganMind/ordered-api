"""
Technician serializers for onboarding and profile management.
"""
import re

from django.utils import timezone
from rest_framework import serializers

from apps.jobs.models import Skill
from apps.technicians.models import (
    ApplicantType,
    ApplicationForm,
    ApplicationStatus,
    FormField,
    FormFieldType,
    OnboardingStatus,
    ServiceRegion,
    TechnicianApplication,
    TechnicianProfile,
    ONBOARDING_REQUIREMENTS,
)
from apps.technicians.validators import validate_answers_against_schema


class ServiceRegionSerializer(serializers.ModelSerializer):
    """Serializer for ServiceRegion."""

    class Meta:
        model = ServiceRegion
        fields = [
            "id",
            "key",
            "name",
            "short_name",
            "state",
            "is_active",
        ]
        read_only_fields = ["id", "key", "name", "short_name", "state"]


class SkillSummarySerializer(serializers.ModelSerializer):
    """Minimal skill serializer for technician profile."""

    pk = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = Skill
        fields = ["id", "pk", "key", "label", "category"]
        read_only_fields = fields


class TechnicianProfileReadSerializer(serializers.ModelSerializer):
    """
    Read-only serializer for technician profile with full onboarding context.

    Used for GET /api/v1/technicians/me/
    """

    # User fields (denormalized for convenience)
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    avatar_url = serializers.URLField(
        source="user.avatar_url", read_only=True, allow_null=True
    )

    # Relations
    skills = SkillSummarySerializer(source="user.skills", many=True, read_only=True)
    service_regions = ServiceRegionSerializer(many=True, read_only=True)

    # Onboarding progress
    onboarding_progress = serializers.SerializerMethodField()

    # Computed fields
    is_eligible = serializers.BooleanField(read_only=True)
    can_submit = serializers.BooleanField(read_only=True)

    class Meta:
        model = TechnicianProfile
        fields = [
            "id",
            # User info
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "avatar_url",
            # Profile info
            "onboarding_status",
            "is_eligible",
            "can_submit",
            "service_regions",
            "skills",
            "additional_data",
            "preferences",
            # Timestamps
            "submitted_at",
            "activated_at",
            "suspended_at",
            "created_at",
            "updated_at",
            # Review info (only suspension_reason visible to technician)
            "suspension_reason",
            # Progress
            "onboarding_progress",
        ]
        read_only_fields = fields

    def get_onboarding_progress(self, obj: TechnicianProfile) -> dict:
        return obj.get_onboarding_progress()


class TechnicianOnboardingUpdateSerializer(serializers.Serializer):
    """
    Serializer for updating onboarding fields.

    Used for PATCH /api/v1/technicians/me/

    Handles both User fields (first_name, last_name, phone) and
    TechnicianProfile relations (service_regions) plus User relations (skills).
    """

    # User fields
    first_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    last_name = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
    )
    phone = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
    )

    # Relations (pass list of IDs)
    # Skills use UUID primary keys (``jobs.Skill``); send UUID strings in JSON.
    skill_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
        help_text="List of skill UUIDs to set (matches GET /technicians/skills/ id/pk).",
    )
    service_region_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="List of service region IDs to set",
    )

    # Additional data (merged with existing)
    additional_data = serializers.JSONField(
        required=False,
        help_text="Additional onboarding data (merged with existing)",
    )

    # Preferences (merged with existing)
    preferences = serializers.JSONField(
        required=False,
        help_text="Technician preferences (merged with existing)",
    )

    def validate_skill_ids(self, value):
        """Validate that all skill IDs exist and are active."""
        if not value:
            return value

        existing = set(
            Skill.objects.filter(id__in=value, is_active=True).values_list(
                "id", flat=True
            )
        )
        invalid = set(value) - existing
        if invalid:
            raise serializers.ValidationError(
                f"Invalid or inactive skill IDs: {sorted(invalid)}"
            )
        return value

    def validate_service_region_ids(self, value):
        """Validate that all service region IDs exist and are active."""
        if not value:
            return value

        existing = set(
            ServiceRegion.objects.filter(id__in=value, is_active=True).values_list(
                "id", flat=True
            )
        )
        invalid = set(value) - existing
        if invalid:
            raise serializers.ValidationError(
                f"Invalid or inactive service region IDs: {sorted(invalid)}"
            )
        return value

    def update(self, profile: TechnicianProfile, validated_data):
        """
        Update user and profile with validated data.

        Returns the updated profile.
        """
        user = profile.user

        # Update User fields
        user_fields = ["first_name", "last_name", "phone"]
        user_changed = False
        for field in user_fields:
            if field in validated_data:
                setattr(user, field, validated_data[field])
                user_changed = True

        if user_changed:
            user.save(update_fields=[f for f in user_fields if f in validated_data] + ["updated_at"])

        # Update User skills
        if "skill_ids" in validated_data:
            skill_ids = validated_data["skill_ids"]
            user.skills.set(Skill.objects.filter(id__in=skill_ids, is_active=True))

        # Update Profile service regions
        if "service_region_ids" in validated_data:
            region_ids = validated_data["service_region_ids"]
            profile.service_regions.set(
                ServiceRegion.objects.filter(id__in=region_ids, is_active=True)
            )

        # Merge additional_data
        if "additional_data" in validated_data:
            profile.additional_data = {
                **profile.additional_data,
                **validated_data["additional_data"],
            }

        # Merge preferences
        if "preferences" in validated_data:
            profile.preferences = {
                **profile.preferences,
                **validated_data["preferences"],
            }

        profile.save()

        # Refresh to get updated M2M counts
        profile.refresh_from_db()
        user.refresh_from_db()

        return profile


class TechnicianSubmitSerializer(serializers.Serializer):
    """
    Serializer for submitting onboarding for review.

    Used for POST /api/v1/technicians/me/submit/
    """

    # No input fields — just validates that profile is ready

    def validate(self, attrs):
        profile = self.context.get("profile")
        if not profile:
            raise serializers.ValidationError("Profile context required")

        if profile.onboarding_status != OnboardingStatus.PENDING_ONBOARDING:
            raise serializers.ValidationError({
                "error": {
                    "code": "invalid_status",
                    "message": f"Cannot submit from status '{profile.onboarding_status}'. Must be 'pending_onboarding'.",
                }
            })

        missing = profile.get_missing_onboarding_fields()
        if missing:
            raise serializers.ValidationError({
                "error": {
                    "code": "onboarding_incomplete",
                    "message": "Cannot submit until all required fields are complete.",
                    "missing_fields": missing,
                }
            })

        return attrs


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing technicians (admin view).

    List rows are annotated on the queryset (`_list_email`, `_list_display_name`,
    `_skill_count`) so the list endpoint need not JOIN ``users_user``.
    """

    email = serializers.EmailField(source="_list_email", read_only=True, allow_null=True)
    full_name = serializers.CharField(
        source="_list_display_name", read_only=True, allow_blank=True
    )
    phone = serializers.CharField(
        source="_list_phone", read_only=True, allow_blank=True, allow_null=True
    )
    skill_count = serializers.IntegerField(source="_skill_count", read_only=True)
    region_count = serializers.IntegerField(source="_region_count", read_only=True)

    class Meta:
        model = TechnicianProfile
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "onboarding_status",
            "skill_count",
            "region_count",
            "submitted_at",
            "activated_at",
            "suspended_at",
            "created_at",
        ]
        read_only_fields = fields


class TechnicianAdminDetailSerializer(TechnicianProfileReadSerializer):
    """
    Full detail serializer for admin viewing a technician.

    Includes review_notes (not visible to technician).
    """

    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_status = serializers.CharField(source="user.status", read_only=True)
    review_notes = serializers.CharField(read_only=True)
    reviewed_by = serializers.UUIDField(
        source="reviewed_by_id", allow_null=True, read_only=True
    )
    reviewed_by_email = serializers.SerializerMethodField()

    class Meta(TechnicianProfileReadSerializer.Meta):
        fields = TechnicianProfileReadSerializer.Meta.fields + [
            "user_id",
            "user_status",
            "review_notes",
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_at",
        ]

    def get_reviewed_by_email(self, obj):
        from django.db import DatabaseError

        rid = getattr(obj, "reviewed_by_id", None)
        if rid is None:
            return None
        try:
            from apps.users.models import User

            return User.objects.filter(pk=rid).values_list("email", flat=True).first()
        except DatabaseError:
            return None


class TechnicianReviewActionSerializer(serializers.Serializer):
    """
    Serializer for admin review actions (approve, request_changes, suspend).
    """

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        help_text="Review notes (visible to admins, not technician)",
    )


class TechnicianSuspendSerializer(serializers.Serializer):
    """
    Serializer for suspending a technician.
    """

    reason = serializers.CharField(
        required=True,
        max_length=1000,
        help_text="Suspension reason (visible to technician)",
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=2000,
        help_text="Internal review notes (visible to admins only)",
    )


class OnboardingRequirementsSerializer(serializers.Serializer):
    """
    Serializer for listing onboarding requirements.

    GET /api/v1/technicians/onboarding-requirements/
    """

    requirements = serializers.SerializerMethodField()

    def get_requirements(self, obj) -> list[dict]:
        return [
            {
                "key": req["key"],
                "label": req["label"],
                "type": req["type"],
                "required": req.get("required", True),
            }
            for req in ONBOARDING_REQUIREMENTS
        ]


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION FORM SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════


class FormFieldSerializer(serializers.ModelSerializer):
    """Read/write serializer for a single form field (nested under application forms)."""

    id = serializers.UUIDField(required=False)

    class Meta:
        model = FormField
        fields = [
            "id",
            "field_key",
            "label",
            "description",
            "field_type",
            "required",
            "position",
            "options",
            "validations",
            "default_value",
            "placeholder",
            "visible",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate_field_key(self, value):
        if not value:
            raise serializers.ValidationError("field_key is required.")
        if not re.match(r"^[a-z][a-z0-9_]*$", value):
            raise serializers.ValidationError(
                "field_key must start with a lowercase letter and contain "
                "only lowercase letters, digits, and underscores."
            )
        return value

    def validate_options(self, value):
        if not value:
            return value
        if not isinstance(value, list):
            raise serializers.ValidationError("Options must be a list.")
        normalised = []
        for item in value:
            if isinstance(item, str):
                normalised.append({"label": item, "value": item})
            elif isinstance(item, dict):
                if "value" not in item:
                    raise serializers.ValidationError(
                        "Each option dict must have a 'value' key."
                    )
                if "label" not in item:
                    item = {**item, "label": item["value"]}
                normalised.append(item)
            else:
                raise serializers.ValidationError(
                    "Each option must be a string or a dict with 'label' and 'value'."
                )
        return normalised

    def validate(self, attrs):
        field_type = attrs.get(
            "field_type",
            getattr(self.instance, "field_type", FormFieldType.TEXT),
        )
        options = attrs.get("options", getattr(self.instance, "options", []))
        choice_types = {
            FormFieldType.SELECT,
            FormFieldType.MULTI_SELECT,
            FormFieldType.RADIO,
        }
        if field_type in choice_types and not options:
            raise serializers.ValidationError(
                {
                    "options": (
                        f"At least one option is required for field type "
                        f"'{field_type}'."
                    )
                }
            )
        return attrs


class FormFieldCompactSerializer(serializers.ModelSerializer):
    """Read-only compact representation for list views."""

    class Meta:
        model = FormField
        fields = [
            "id",
            "field_key",
            "label",
            "field_type",
            "required",
            "position",
            "visible",
        ]
        read_only_fields = [
            "id",
            "field_key",
            "label",
            "field_type",
            "required",
            "position",
            "visible",
        ]


class ApplicationFormListSerializer(serializers.ModelSerializer):
    """Compact representation for list views."""

    application_count = serializers.SerializerMethodField()
    is_accepting_submissions = serializers.BooleanField(read_only=True)
    field_count = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationForm
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "status",
            "is_accepting_submissions",
            "application_count",
            "field_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_accepting_submissions",
            "application_count",
            "field_count",
            "created_at",
            "updated_at",
        ]

    def get_application_count(self, obj) -> int:
        if hasattr(obj, "_application_count"):
            return obj._application_count
        from django.db import DatabaseError

        try:
            return TechnicianApplication.objects.filter(
                application_form_id=obj.pk
            ).count()
        except DatabaseError:
            return 0

    def get_field_count(self, obj) -> int:
        if hasattr(obj, "_field_count"):
            return obj._field_count
        return obj.fields.count()


class ApplicationFormDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer including nested fields (visible vs hidden)."""

    application_count = serializers.SerializerMethodField()
    is_accepting_submissions = serializers.BooleanField(read_only=True)
    status_counts = serializers.SerializerMethodField()
    fields_schema = serializers.SerializerMethodField()
    hidden_fields = serializers.SerializerMethodField()
    schema_version = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationForm
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "status",
            "settings",
            "is_accepting_submissions",
            "application_count",
            "status_counts",
            "fields_schema",
            "hidden_fields",
            "schema_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_accepting_submissions",
            "application_count",
            "status_counts",
            "fields_schema",
            "hidden_fields",
            "schema_version",
            "created_at",
            "updated_at",
        ]

    def get_application_count(self, obj) -> int:
        return obj.applications.count()

    def get_status_counts(self, obj) -> dict:
        from django.db.models import Count

        qs = obj.applications.values("status").annotate(count=Count("id"))
        return {row["status"]: row["count"] for row in qs}

    def get_schema_version(self, obj) -> int:
        return obj.schema_version_current

    def get_fields_schema(self, obj) -> list:
        visible = obj.fields.filter(visible=True).order_by("position", "created_at")
        return FormFieldSerializer(visible, many=True).data

    def get_hidden_fields(self, obj) -> list:
        hidden = obj.fields.filter(visible=False).order_by("position", "created_at")
        return FormFieldSerializer(hidden, many=True).data


class ApplicationFormCreateSerializer(serializers.ModelSerializer):
    """Create application form; optional ``fields_schema`` creates fields atomically."""

    fields_schema = FormFieldSerializer(many=True, required=False, default=list)

    class Meta:
        model = ApplicationForm
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "status",
            "settings",
            "fields_schema",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_slug(self, value):
        if not value:
            return value
        tenant_id = self.context.get("tenant_id")
        if tenant_id:
            exists = ApplicationForm.objects.filter(
                tenant_id=tenant_id, slug=value
            ).exists()
            if exists:
                raise serializers.ValidationError(
                    f"A form with slug '{value}' already exists for this tenant."
                )
        return value

    def validate_fields_schema(self, value):
        if not value:
            return value
        keys = [f.get("field_key") or "" for f in value]
        seen: set[str] = set()
        dupes: set[str] = set()
        for k in keys:
            if not k:
                continue
            if k in seen:
                dupes.add(k)
            seen.add(k)
        if dupes:
            raise serializers.ValidationError(
                f"Duplicate field_key(s): {', '.join(sorted(dupes))}"
            )
        return value

    def create(self, validated_data):
        fields_data = validated_data.pop("fields_schema", [])
        form = ApplicationForm.objects.create(**validated_data)

        for idx, field_data in enumerate(fields_data):
            field_data = {**field_data}
            field_data.pop("id", None)
            if "position" not in field_data:
                field_data["position"] = idx
            FormField.objects.create(form=form, **field_data)

        return form


class ApplicationFormUpdateSerializer(serializers.ModelSerializer):
    """
    Update application form. When ``fields_schema`` is sent, reconcile fields:
      - Rows with an existing ``id`` are updated in place.
      - Rows without ``id`` create new fields.
      - Existing rows whose ``id`` is absent from the payload are deleted if
        the form has no submissions, or soft-hidden (``visible=False``) if it does.

    With submissions, ``field_key`` renames are still blocked.
    """

    fields_schema = FormFieldSerializer(many=True, required=False)

    class Meta:
        model = ApplicationForm
        fields = [
            "title",
            "slug",
            "description",
            "status",
            "settings",
            "fields_schema",
        ]

    def validate_slug(self, value):
        if not value:
            return value
        tenant_id = self.context.get("tenant_id")
        if tenant_id and self.instance:
            exists = (
                ApplicationForm.objects.filter(tenant_id=tenant_id, slug=value)
                .exclude(pk=self.instance.pk)
                .exists()
            )
            if exists:
                raise serializers.ValidationError(
                    f"A form with slug '{value}' already exists for this tenant."
                )
        return value

    def validate_fields_schema(self, value):
        if value is None:
            return value
        keys = [f.get("field_key") or "" for f in value]
        seen: set[str] = set()
        dupes: set[str] = set()
        for k in keys:
            if not k:
                continue
            if k in seen:
                dupes.add(k)
            seen.add(k)
        if dupes:
            raise serializers.ValidationError(
                f"Duplicate field_key(s): {', '.join(sorted(dupes))}"
            )
        return value

    def _validate_field_key_stability(self, instance, fields_data):
        if not instance.applications.exists():
            return

        existing_fields = {
            str(f.id): f.field_key for f in instance.fields.all()
        }

        for field_data in fields_data:
            fid = field_data.get("id")
            if fid and str(fid) in existing_fields:
                old_key = existing_fields[str(fid)]
                new_key = field_data.get("field_key", old_key)
                if new_key != old_key:
                    raise serializers.ValidationError(
                        {
                            "fields_schema": (
                                f"Cannot rename field_key '{old_key}' → '{new_key}' "
                                f"on a form with existing submissions."
                            )
                        }
                    )

    def update(self, instance, validated_data):
        fields_data = validated_data.pop("fields_schema", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if fields_data is not None:
            self._validate_field_key_stability(instance, fields_data)
            self._reconcile_fields(instance, fields_data)

        return instance

    def _reconcile_fields(self, form, fields_data):
        has_submissions = form.applications.exists()
        existing_by_id = {str(f.id): f for f in form.fields.all()}
        incoming_ids: set[str] = set()

        for idx, raw in enumerate(fields_data):
            field_data = {**raw}
            fid = field_data.pop("id", None)

            if "position" not in field_data:
                field_data["position"] = idx

            if fid and str(fid) in existing_by_id:
                incoming_ids.add(str(fid))
                field_obj = existing_by_id[str(fid)]
                for attr, value in field_data.items():
                    setattr(field_obj, attr, value)
                field_obj.save()
            else:
                new_field = FormField.objects.create(form=form, **field_data)
                incoming_ids.add(str(new_field.id))

        to_remove_ids = set(existing_by_id.keys()) - incoming_ids
        if to_remove_ids:
            if has_submissions:
                FormField.objects.filter(id__in=to_remove_ids).update(
                    visible=False,
                    updated_at=timezone.now(),
                )
            else:
                FormField.objects.filter(id__in=to_remove_ids).delete()


class ApplicationFormPublicSerializer(serializers.ModelSerializer):
    """Public read-only form definition for rendering the applicant form."""

    fields_schema = serializers.SerializerMethodField()

    class Meta:
        model = ApplicationForm
        fields = [
            "id",
            "title",
            "description",
            "fields_schema",
        ]
        read_only_fields = ["id", "title", "description", "fields_schema"]

    def get_fields_schema(self, obj) -> list[dict]:
        return obj.get_field_schema()


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN APPLICATION SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianApplicationListSerializer(serializers.ModelSerializer):
    """Compact representation for list views."""

    display_name = serializers.CharField(read_only=True)
    application_form = serializers.UUIDField(
        source="application_form_id", allow_null=True, read_only=True
    )
    application_form_title = serializers.CharField(
        source="application_form.title", read_only=True, default=None
    )

    class Meta:
        model = TechnicianApplication
        fields = [
            "id",
            "application_form",
            "application_form_title",
            "applicant_type",
            "display_name",
            "first_name",
            "last_name",
            "company_name",
            "email",
            "phone",
            "status",
            "source",
            "submitted_at",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = fields


class TechnicianApplicationSerializer(serializers.ModelSerializer):
    """
    Full read/write serializer.

    Status is read-only here — transitions use POST `review`, `approve`,
    or `reject` so reviewer metadata and validation stay centralized.
    """

    display_name = serializers.CharField(read_only=True)
    is_terminal = serializers.BooleanField(read_only=True)
    is_converted = serializers.BooleanField(read_only=True)
    reviewed_by = serializers.UUIDField(
        source="reviewed_by_id", allow_null=True, read_only=True
    )
    reviewed_by_email = serializers.SerializerMethodField()
    converted_user = serializers.UUIDField(
        source="converted_user_id", allow_null=True, read_only=True
    )
    converted_by = serializers.UUIDField(
        source="converted_by_id", allow_null=True, read_only=True
    )
    converted_technician_profile = serializers.UUIDField(
        source="converted_technician_profile_id", allow_null=True, read_only=True
    )
    application_form_title = serializers.CharField(
        source="application_form.title", read_only=True, default=None
    )

    class Meta:
        model = TechnicianApplication
        fields = [
            "id",
            "application_form",
            "application_form_title",
            # classification
            "applicant_type",
            # identity / contact
            "first_name",
            "last_name",
            "company_name",
            "email",
            "phone",
            # structured application data
            "service_area",
            "availability",
            "experience",
            "capabilities",
            "answers",
            "schema_version",
            # lifecycle
            "status",
            "submitted_at",
            "status_changed_at",
            # review
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_at",
            "reviewer_notes",
            "rejection_reason",
            # conversion audit
            "converted_user",
            "converted_technician_profile",
            "converted_at",
            "converted_by",
            # provenance
            "source",
            "metadata",
            # derived
            "display_name",
            "is_terminal",
            "is_converted",
            # timestamps
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "status_changed_at",
            "reviewed_by",
            "reviewed_by_email",
            "reviewed_at",
            "converted_user",
            "converted_technician_profile",
            "converted_at",
            "converted_by",
            "display_name",
            "is_terminal",
            "is_converted",
            "application_form_title",
            "created_at",
            "updated_at",
        ]

    def get_reviewed_by_email(self, obj):
        from django.db import DatabaseError

        rid = getattr(obj, "reviewed_by_id", None)
        if rid is None:
            return None
        try:
            from apps.users.models import User

            return User.objects.filter(pk=rid).values_list("email", flat=True).first()
        except DatabaseError:
            return None

    def validate_application_form(self, value):
        if value is None:
            return value
        tenant_id = self.context.get("tenant_id")
        if tenant_id and value.tenant_id != tenant_id:
            raise serializers.ValidationError(
                "Application form does not belong to this tenant."
            )
        return value

    def validate(self, attrs):
        applicant_type = attrs.get(
            "applicant_type",
            getattr(self.instance, "applicant_type", ApplicantType.INDIVIDUAL),
        )
        if applicant_type == ApplicantType.COMPANY:
            company_name = attrs.get(
                "company_name", getattr(self.instance, "company_name", "")
            )
            if not company_name:
                raise serializers.ValidationError(
                    {"company_name": "Required when applicant_type is 'company'."}
                )

        form = attrs.get("application_form")
        if form is None and self.instance is not None:
            form = self.instance.application_form

        if form and hasattr(form, "get_field_schema"):
            field_schema = form.get_field_schema()
            if field_schema:
                if self.partial and "answers" not in attrs:
                    return attrs
                answers = attrs.get("answers")
                if answers is None and self.instance is not None:
                    answers = self.instance.answers or {}
                elif answers is None:
                    answers = {}
                errors = validate_answers_against_schema(field_schema, answers)
                if errors:
                    raise serializers.ValidationError({"answers": errors})

        return attrs


class TechnicianApplicationReviewSerializer(serializers.Serializer):
    """
    Payload for POST /admin/technician-applications/{id}/review/

    Enforces:
      - `status` is required
      - Cannot transition away from a terminal status
    """

    status = serializers.ChoiceField(choices=ApplicationStatus.choices)
    reviewer_notes = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, allow_null=True
    )

    def validate(self, attrs):
        application: TechnicianApplication = self.context["application"]

        if application.is_terminal:
            raise serializers.ValidationError(
                {
                    "status": (
                        f"Application is in terminal status '{application.status}' "
                        "and cannot be transitioned."
                    )
                }
            )

        new_status = attrs["status"]
        if (
            new_status == ApplicationStatus.REJECTED
            and not attrs.get("rejection_reason")
            and not application.rejection_reason
        ):
            # Soft nudge — not a hard requirement, but surface it.
            # Change to a hard error if your operators want it enforced.
            pass

        return attrs


class TechnicianApplicationApproveSerializer(serializers.Serializer):
    """
    Payload for POST /admin/technician-applications/{id}/approve/

    Minimal — just optional internal notes. Conversion options
    (link-to-existing-user, etc.) arrive in a later phase.
    """

    reviewer_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Internal note appended on approval. Optional.",
    )

    def validate(self, attrs):
        application: TechnicianApplication = self.context["application"]
        if application.is_terminal:
            raise serializers.ValidationError(
                f"Application is already '{application.status}' and cannot be approved."
            )
        return attrs


class TechnicianApplicationRejectSerializer(serializers.Serializer):
    """
    Payload for POST /admin/technician-applications/{id}/reject/

    `rejection_reason` is required — forces operators to capture *why*
    so future correlation against technician performance has context.
    """

    rejection_reason = serializers.CharField(
        required=True,
        allow_blank=False,
        help_text="Reason for rejection. Stored and potentially surfaced to the applicant.",
    )
    reviewer_notes = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Internal-only note. Optional.",
    )

    def validate(self, attrs):
        application: TechnicianApplication = self.context["application"]
        if application.is_terminal:
            raise serializers.ValidationError(
                f"Application is already '{application.status}' and cannot be rejected."
            )
        return attrs


class TechnicianApplicationConvertSerializer(serializers.Serializer):
    """
    Payload for POST /admin/technician-applications/{id}/convert/

    Modes:
      • create (default) — new Supabase + local user from the application email
      • link             — attach to an existing tenant user
    """

    existing_user_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Link to this existing user instead of creating a new one.",
    )
    create_supabase_account = serializers.BooleanField(
        default=True,
        help_text="Provision a Supabase auth user (ignored in link mode).",
    )
    activate_immediately = serializers.BooleanField(
        default=False,
        help_text="Skip onboarding and set profile status=active.",
    )
    reviewer_notes = serializers.CharField(
        required=False, allow_blank=True
    )

    def validate(self, attrs):
        application: TechnicianApplication = self.context["application"]
        if application.is_converted:
            raise serializers.ValidationError(
                "Application has already been converted."
            )
        if application.status in {
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }:
            raise serializers.ValidationError(
                f"Cannot convert a '{application.status}' application."
            )
        return attrs


class ConversionResultSerializer(serializers.Serializer):
    """Response envelope for the convert action."""

    application = TechnicianApplicationSerializer(read_only=True)
    user_id = serializers.UUIDField(read_only=True)
    profile_id = serializers.UUIDField(read_only=True)
    user_created = serializers.BooleanField(read_only=True)
    supabase_created = serializers.BooleanField(read_only=True)


class TechnicianApplicationPublicSubmitSerializer(serializers.ModelSerializer):
    """
    Public submission serializer — used by unauthenticated applicants.

    Only exposes fields an applicant should provide. Tenant and form are
    resolved from the URL or request context, not from user input.
    """

    class Meta:
        model = TechnicianApplication
        fields = [
            "applicant_type",
            "first_name",
            "last_name",
            "company_name",
            "email",
            "phone",
            "service_area",
            "availability",
            "experience",
            "capabilities",
            "answers",
        ]

    def validate_email(self, value):
        return value.lower().strip()

    def validate(self, attrs):
        applicant_type = attrs.get("applicant_type", ApplicantType.INDIVIDUAL)
        if applicant_type == ApplicantType.COMPANY:
            if not attrs.get("company_name"):
                raise serializers.ValidationError(
                    {"company_name": "Required when applying as a company/team."}
                )

        if not attrs.get("email"):
            raise serializers.ValidationError({"email": "Email is required."})
        if not attrs.get("first_name") and applicant_type == ApplicantType.INDIVIDUAL:
            raise serializers.ValidationError(
                {"first_name": "First name is required."}
            )

        form = self.context.get("application_form")
        answers = attrs.get("answers")
        if answers is None:
            answers = {}

        if form and hasattr(form, "get_field_schema"):
            field_schema = form.get_field_schema()
            if field_schema:
                errors = validate_answers_against_schema(field_schema, answers)
                if errors:
                    raise serializers.ValidationError({"answers": errors})

        return attrs
