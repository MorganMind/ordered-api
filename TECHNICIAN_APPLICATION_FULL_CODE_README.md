# Technician application system — full source (concatenated)

Generated for reference. Each section is one file.


---
## `apps/technicians/__init__.py`

```python
```

---
## `apps/technicians/apps.py`

```python
from django.apps import AppConfig


class TechniciansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.technicians"
    verbose_name = "Technicians"

    def ready(self):
        import apps.technicians.signals  # noqa: F401
```

---
## `apps/technicians/models.py`

```python
"""
Technician profile, onboarding state, and service regions.

The TechnicianProfile is the single source of truth for whether a technician
can participate in job operations. It tracks onboarding status through a
backend-enforced state machine and stores region preferences.

Onboarding states:
    pending_onboarding - profile created, required fields not yet submitted
    submitted          - technician filled required fields, awaiting admin review
    active             - approved by admin, can see/claim/execute jobs
    suspended          - blocked from all job operations by admin
"""
import uuid
from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from apps.users.models import User


class OnboardingStatus(models.TextChoices):
    PENDING_ONBOARDING = "pending_onboarding", "Pending Onboarding"
    SUBMITTED = "submitted", "Submitted for Review"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE REGION
# ═══════════════════════════════════════════════════════════════════════════════


class ServiceRegion(models.Model):
    """
    Geographic region where technicians can operate.

    Tenant-agnostic reference data (like Skill). Regions are shared across
    all tenants; use is_active to control availability.

    Designed for expansion — can add parent/child relationships, geo data,
    or tenant-specific overrides later.
    """

    key = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Stable identifier (e.g., 'nj_essex_county')",
    )
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name (e.g., 'Essex County, NJ')",
    )
    short_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Abbreviated name for UI (e.g., 'Essex County')",
    )
    state = models.CharField(
        max_length=50,
        db_index=True,
        help_text="State/province (e.g., 'NJ', 'New Jersey')",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this region is currently available for selection",
    )

    # ── Future expansion fields ──
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent region for hierarchical structures",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extensible metadata (geo bounds, zip codes, etc.)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "service_regions"
        ordering = ["state", "name"]
        indexes = [
            models.Index(fields=["state", "is_active"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


# ═══════════════════════════════════════════════════════════════════════════════
# ONBOARDING FIELD REQUIREMENTS
# ═══════════════════════════════════════════════════════════════════════════════


class OnboardingFieldType(models.TextChoices):
    """Types of onboarding requirements."""

    USER_FIELD = "user_field", "User Model Field"
    USER_RELATION = "user_relation", "User M2M Relation"
    PROFILE_RELATION = "profile_relation", "Profile M2M Relation"
    PROFILE_FIELD = "profile_field", "Profile Model Field"


# Registry of required onboarding fields.
# Each entry defines what's needed and how to check it.
# Add new requirements here without changing validation logic.
ONBOARDING_REQUIREMENTS: list[dict] = [
    {
        "key": "first_name",
        "label": "First name",
        "type": OnboardingFieldType.USER_FIELD,
        "field": "first_name",
        "required": True,
    },
    {
        "key": "last_name",
        "label": "Last name",
        "type": OnboardingFieldType.USER_FIELD,
        "field": "last_name",
        "required": True,
    },
    {
        "key": "phone",
        "label": "Phone number",
        "type": OnboardingFieldType.USER_FIELD,
        "field": "phone",
        "required": True,
    },
    {
        "key": "skills",
        "label": "At least one skill",
        "type": OnboardingFieldType.USER_RELATION,
        "field": "skills",
        "min_count": 1,
        "required": True,
    },
    {
        "key": "service_regions",
        "label": "At least one service region",
        "type": OnboardingFieldType.PROFILE_RELATION,
        "field": "service_regions",
        "min_count": 1,
        "required": True,
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN PROFILE
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianProfile(models.Model):
    """
    One-to-one extension of User for technician-specific data and onboarding state.

    Tenant scoping is achieved through the linked User's tenant FK.
    An explicit tenant FK is stored for query convenience and indexing.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        "users.User",
        on_delete=models.CASCADE,
        related_name="technician_profile",
    )

    # Denormalized for query convenience — always kept in sync with user.tenant
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="technician_profiles",
        db_index=True,
    )

    onboarding_status = models.CharField(
        max_length=30,
        choices=OnboardingStatus.choices,
        default=OnboardingStatus.PENDING_ONBOARDING,
        db_index=True,
    )

    # ── Service regions ──
    service_regions = models.ManyToManyField(
        ServiceRegion,
        related_name="technician_profiles",
        blank=True,
        help_text="Regions where this technician is willing to work",
    )

    # ── Lifecycle timestamps ──
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_technician_profiles",
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    # ── Admin notes ──
    review_notes = models.TextField(
        blank=True,
        help_text="Internal notes from the reviewer (visible to admins only)",
    )
    suspension_reason = models.TextField(
        blank=True,
        help_text="Reason for suspension (visible to the technician)",
    )

    # ── Extensible additional data ──
    # Use this for future onboarding fields without schema migrations.
    # Example: {"emergency_contact": {"name": "...", "phone": "..."}}
    additional_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Extensible storage for additional onboarding fields",
    )

    # ── Preferences ──
    # Store technician preferences that don't warrant their own columns yet
    preferences = models.JSONField(
        default=dict,
        blank=True,
        help_text="Technician preferences (notifications, availability, etc.)",
    )

    # ── Application provenance ──
    # Frozen copy of the application payload at the moment of conversion.
    # The source TechnicianApplication row may later be edited or deleted;
    # this snapshot preserves what the reviewer actually saw and approved.
    application_snapshot = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Immutable snapshot of the TechnicianApplication at conversion time. "
            "Used for outcome correlation and audit."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "technician_profiles"
        indexes = [
            models.Index(fields=["tenant", "onboarding_status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="unique_technician_profile_per_user",
            ),
        ]

    def __str__(self):
        return f"TechnicianProfile({self.user.email}, {self.onboarding_status})"

    # ── Onboarding field validation ──

    def get_missing_onboarding_fields(self) -> list[dict]:
        """
        Return a list of required onboarding fields that are incomplete.

        Checks all ONBOARDING_REQUIREMENTS against the User and Profile.

        Returns:
            [{"key": "phone", "label": "Phone number", "type": "user_field"}, ...]
        """
        missing = []

        for req in ONBOARDING_REQUIREMENTS:
            if not req.get("required", True):
                continue

            is_complete = False
            req_type = req["type"]
            field_name = req["field"]

            if req_type == OnboardingFieldType.USER_FIELD:
                value = getattr(self.user, field_name, None)
                is_complete = bool(value and str(value).strip())

            elif req_type == OnboardingFieldType.USER_RELATION:
                relation = getattr(self.user, field_name, None)
                if relation is not None:
                    # Filter for active items if the related model has is_active
                    try:
                        count = relation.filter(is_active=True).count()
                    except Exception:
                        count = relation.count()
                    min_count = req.get("min_count", 1)
                    is_complete = count >= min_count

            elif req_type == OnboardingFieldType.PROFILE_RELATION:
                relation = getattr(self, field_name, None)
                if relation is not None:
                    try:
                        count = relation.filter(is_active=True).count()
                    except Exception:
                        count = relation.count()
                    min_count = req.get("min_count", 1)
                    is_complete = count >= min_count

            elif req_type == OnboardingFieldType.PROFILE_FIELD:
                value = getattr(self, field_name, None)
                is_complete = bool(value and str(value).strip())

            if not is_complete:
                missing.append({
                    "key": req["key"],
                    "label": req["label"],
                    "type": req_type,
                })

        return missing

    @property
    def has_completed_required_fields(self) -> bool:
        return len(self.get_missing_onboarding_fields()) == 0

    @property
    def can_submit(self) -> bool:
        """True if technician has filled all required fields and is in pending state."""
        return (
            self.onboarding_status == OnboardingStatus.PENDING_ONBOARDING
            and self.has_completed_required_fields
        )

    @property
    def is_eligible(self) -> bool:
        """True if technician is approved and can participate in job operations."""
        return self.onboarding_status == OnboardingStatus.ACTIVE

    def get_onboarding_progress(self) -> dict:
        """
        Return onboarding progress summary for the frontend.

        Returns:
            {
                "status": "pending_onboarding",
                "is_eligible": False,
                "can_submit": False,
                "total_requirements": 5,
                "completed_requirements": 2,
                "missing_fields": [...],
                "completion_percentage": 40
            }
        """
        missing = self.get_missing_onboarding_fields()
        total = len([r for r in ONBOARDING_REQUIREMENTS if r.get("required", True)])
        completed = total - len(missing)

        return {
            "status": self.onboarding_status,
            "is_eligible": self.is_eligible,
            "can_submit": self.can_submit,
            "total_requirements": total,
            "completed_requirements": completed,
            "missing_fields": missing,
            "completion_percentage": int((completed / total) * 100) if total > 0 else 0,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════


class ApplicantType(models.TextChoices):
    """Whether the applicant is an individual or a company/team."""
    INDIVIDUAL = "individual", "Individual"
    COMPANY = "company", "Company / Team"


class ApplicationStatus(models.TextChoices):
    """Lifecycle status of a technician application."""
    NEW = "new", "New"
    REVIEWING = "reviewing", "Reviewing"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


# Terminal states cannot be transitioned away from (except via admin override).
APPLICATION_TERMINAL_STATUSES = {
    ApplicationStatus.APPROVED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
}


class TechnicianApplication(models.Model):
    """
    First-class record of a technician application, independent of any User.

    Applications are intentionally decoupled from the auth/User system so that:
      - Unauthenticated applicants can submit via a public intake form.
      - Rejected applications remain auditable without dangling user accounts.
      - Approval explicitly creates/links a User + TechnicianProfile (later phase).

    Schema design:
      - Core identity/contact fields are first-class columns for indexing,
        filtering, and dedup checks.
      - Everything else lives in structured JSONB fields (`service_area`,
        `availability`, `experience`, `capabilities`, `answers`) so operators
        can evolve their questionnaire without migrations.
      - `schema_version` tracks the shape of the `answers` payload over time.

    Tenant safety:
      - Explicit tenant FK with db_index. All queries MUST filter by tenant.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="technician_applications",
        db_index=True,
    )

    # ── Applicant classification ──
    applicant_type = models.CharField(
        max_length=20,
        choices=ApplicantType.choices,
        default=ApplicantType.INDIVIDUAL,
        db_index=True,
    )

    # ── Identity / contact (first-class for filtering & dedup) ──
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Populated when applicant_type=company",
    )
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=50, blank=True)

    # ── Structured but flexible application data ──
    # Each JSONB field has a soft schema documented below. Operators can extend
    # freely; the backend treats these as opaque beyond basic type checks.

    service_area = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Geographic coverage. Soft schema: "
            "{'counties': ['Essex', 'Hudson'], "
            "'service_region_keys': ['nj_essex_county'], "
            "'max_travel_miles': 25, 'notes': '...'}"
        ),
    )

    availability = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "When the applicant can work. Soft schema: "
            "{'days': ['mon','tue','wed'], "
            "'hours': {'start': '08:00', 'end': '18:00'}, "
            "'start_date': '2025-02-01', 'hours_per_week': 30, 'notes': '...'}"
        ),
    )

    experience = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Work history & qualifications. Soft schema: "
            "{'years_cleaning': 3, 'prior_employers': [...], "
            "'has_own_supplies': true, 'has_vehicle': true, "
            "'certifications': [...], 'references': [...]}"
        ),
    )

    capabilities = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Declared skills/service types. Soft schema: "
            "{'skill_keys': ['standard_clean','deep_clean'], "
            "'specialties': [...], 'team_size': 1, 'languages': [...]}"
        ),
    )

    answers = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Free-form Q&A payload for tenant-specific questions. "
            "Keyed by question slug. Shape governed by schema_version."
        ),
    )

    schema_version = models.PositiveIntegerField(
        default=1,
        help_text="Version of the questionnaire schema used to populate `answers`.",
    )

    # ── Lifecycle ──
    status = models.CharField(
        max_length=20,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.NEW,
        db_index=True,
    )

    submitted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the applicant submitted (may differ from created_at if drafts are supported).",
    )
    status_changed_at = models.DateTimeField(null=True, blank=True)

    # ── Review / operator annotations ──
    reviewed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_technician_applications",
        help_text="Operator who most recently reviewed this application.",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    reviewer_notes = models.TextField(
        blank=True,
        help_text="Internal operator notes. Never shown to the applicant.",
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Optional reason captured on rejection. May be shared with applicant.",
    )

    # ── Conversion audit trail (populated on approval in a later phase) ──
    converted_user = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_applications",
        help_text="User account created/linked when this application was approved.",
    )
    converted_technician_profile = models.ForeignKey(
        "technicians.TechnicianProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_applications",
        help_text="TechnicianProfile created/linked on approval.",
    )
    converted_at = models.DateTimeField(null=True, blank=True)
    converted_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="converted_technician_applications",
        help_text="Operator who executed the conversion.",
    )

    # ── Provenance / attribution ──
    source = models.CharField(
        max_length=50,
        blank=True,
        help_text="Where this application originated (e.g. 'public_form', 'operator_entry', 'referral').",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="System/provenance metadata (utm params, IP, user agent, referral codes, etc.).",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "technician_applications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "email"]),
            models.Index(fields=["tenant", "applicant_type", "status"]),
            models.Index(fields=["tenant", "-created_at"]),
        ]

    def __str__(self):
        label = self.display_name or self.email
        return f"TechnicianApplication({label}, {self.status})"

    # ── Derived helpers ──

    @property
    def display_name(self) -> str:
        """Human-friendly label for operator UIs."""
        if self.applicant_type == ApplicantType.COMPANY and self.company_name:
            return self.company_name
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.email

    @property
    def is_terminal(self) -> bool:
        return self.status in APPLICATION_TERMINAL_STATUSES

    @property
    def is_converted(self) -> bool:
        return self.converted_user_id is not None or self.converted_technician_profile_id is not None
```

---
## `apps/technicians/serializers.py`

```python
"""
Technician serializers for onboarding and profile management.
"""
from rest_framework import serializers

from apps.jobs.models import Skill
from apps.technicians.models import (
    ApplicantType,
    ApplicationStatus,
    OnboardingStatus,
    ServiceRegion,
    TechnicianApplication,
    TechnicianProfile,
    ONBOARDING_REQUIREMENTS,
)


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

    class Meta:
        model = Skill
        fields = ["id", "key", "label", "category"]
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
    skill_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="List of skill IDs to set",
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
    """

    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    phone = serializers.CharField(source="user.phone", read_only=True)
    skill_count = serializers.SerializerMethodField()
    region_count = serializers.SerializerMethodField()

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

    def get_skill_count(self, obj) -> int:
        return obj.user.skills.filter(is_active=True).count()

    def get_region_count(self, obj) -> int:
        return obj.service_regions.filter(is_active=True).count()


class TechnicianAdminDetailSerializer(TechnicianProfileReadSerializer):
    """
    Full detail serializer for admin viewing a technician.

    Includes review_notes (not visible to technician).
    """

    user_id = serializers.UUIDField(source="user.id", read_only=True)
    user_status = serializers.CharField(source="user.status", read_only=True)
    review_notes = serializers.CharField(read_only=True)
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True
    )

    class Meta(TechnicianProfileReadSerializer.Meta):
        fields = TechnicianProfileReadSerializer.Meta.fields + [
            "user_id",
            "user_status",
            "review_notes",
            "reviewed_by_email",
            "reviewed_at",
        ]


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
# TECHNICIAN APPLICATION SERIALIZERS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianApplicationListSerializer(serializers.ModelSerializer):
    """Compact representation for list views."""

    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = TechnicianApplication
        fields = [
            "id",
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
    reviewed_by_email = serializers.EmailField(
        source="reviewed_by.email", read_only=True, default=None
    )

    class Meta:
        model = TechnicianApplication
        fields = [
            "id",
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
            "created_at",
            "updated_at",
        ]

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

    Only exposes fields an applicant should provide. Tenant is resolved
    from the URL or request context, not from user input.
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

        return attrs
```

---
## `apps/technicians/services.py`

```python
"""
Technician onboarding service — state transitions and eligibility checks.

Also hosts technician application → User + TechnicianProfile conversion
(application snapshot, Supabase provisioning, audit events).

All onboarding state mutations go through this service. The state machine
in apps.core.state_machine enforces valid transitions; this service adds
business rules (required-field checks, timestamps, event logging).
"""
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import structlog
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.core.state_machine import get_state_machine
from apps.events.models import EntityType, EventType
from apps.events.services import event_service
from apps.jobs.models import Skill
from apps.technicians.models import (
    ApplicationStatus,
    OnboardingStatus,
    ServiceRegion,
    TechnicianApplication,
    TechnicianProfile,
    ONBOARDING_REQUIREMENTS,
)
from apps.users.models import User, UserRole, UserStatus
from apps.users.services.auth import SupabaseAuthService

logger = structlog.get_logger(__name__)

_machine = get_state_machine("technician_onboarding")


class TechnicianOnboardingService:
    """Service layer for technician onboarding operations."""

    # ── Eligibility check (used by permission class + service layer) ──

    @staticmethod
    def check_eligibility(user) -> TechnicianProfile:
        """
        Verify that a technician user is eligible to participate in jobs.

        Returns the profile if eligible.
        Raises TechnicianNotEligibleError if not.
        Does nothing for non-technician roles.
        """
        from apps.users.models import UserRole
        from apps.core.exceptions import TechnicianNotEligibleError

        if user.role != UserRole.TECHNICIAN:
            return None

        try:
            profile = user.technician_profile
        except TechnicianProfile.DoesNotExist:
            # Build missing fields from requirements
            missing_fields = [
                {"key": req["key"], "label": req["label"], "type": req["type"]}
                for req in ONBOARDING_REQUIREMENTS
                if req.get("required", True)
            ]
            raise TechnicianNotEligibleError(
                onboarding_status=OnboardingStatus.PENDING_ONBOARDING,
                missing_fields=missing_fields,
            )

        if not profile.is_eligible:
            raise TechnicianNotEligibleError(
                onboarding_status=profile.onboarding_status,
                missing_fields=profile.get_missing_onboarding_fields(),
                suspension_reason=(
                    profile.suspension_reason
                    if profile.onboarding_status == OnboardingStatus.SUSPENDED
                    else ""
                ),
            )

        return profile

    # ── State transitions ──

    @staticmethod
    def submit_for_review(profile: TechnicianProfile, actor=None) -> TechnicianProfile:
        """
        Technician submits their profile for admin review.

        Requires all ONBOARDING_REQUIREMENTS to be satisfied.
        """
        # Validate required fields are present
        missing = profile.get_missing_onboarding_fields()
        if missing:
            raise ValidationError({
                "error": {
                    "code": "onboarding_fields_incomplete",
                    "message": "Required onboarding fields are missing.",
                    "missing_fields": missing,
                }
            })

        # Validate state transition
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.SUBMITTED,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.SUBMITTED
            profile.submitted_at = timezone.now()
            profile.save(update_fields=[
                "onboarding_status", "submitted_at", "updated_at",
            ])

            logger.info(
                "technician_onboarding_submitted",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def approve(
        profile: TechnicianProfile,
        reviewer,
        notes: str = "",
    ) -> TechnicianProfile:
        """Admin approves a submitted technician profile."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.ACTIVE,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.ACTIVE
            profile.reviewed_at = timezone.now()
            profile.reviewed_by = reviewer
            profile.activated_at = timezone.now()
            profile.review_notes = notes
            # Clear any previous suspension
            profile.suspension_reason = ""
            profile.save(update_fields=[
                "onboarding_status",
                "reviewed_at",
                "reviewed_by",
                "activated_at",
                "review_notes",
                "suspension_reason",
                "updated_at",
            ])

            logger.info(
                "technician_onboarding_approved",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                reviewer_id=str(reviewer.id),
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def request_changes(
        profile: TechnicianProfile,
        reviewer,
        notes: str = "",
    ) -> TechnicianProfile:
        """Admin sends a submitted profile back for revisions."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.PENDING_ONBOARDING,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.PENDING_ONBOARDING
            profile.reviewed_at = timezone.now()
            profile.reviewed_by = reviewer
            profile.review_notes = notes
            # Clear submitted_at so they can re-submit
            profile.submitted_at = None
            profile.save(update_fields=[
                "onboarding_status",
                "reviewed_at",
                "reviewed_by",
                "review_notes",
                "submitted_at",
                "updated_at",
            ])

            logger.info(
                "technician_onboarding_changes_requested",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                reviewer_id=str(reviewer.id),
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def suspend(
        profile: TechnicianProfile,
        actor,
        reason: str = "",
    ) -> TechnicianProfile:
        """Admin suspends a technician — blocks all job operations."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.SUSPENDED,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.SUSPENDED
            profile.suspended_at = timezone.now()
            profile.suspension_reason = reason
            profile.save(update_fields=[
                "onboarding_status",
                "suspended_at",
                "suspension_reason",
                "updated_at",
            ])

            logger.info(
                "technician_suspended",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                actor_id=str(actor.id),
                reason=reason,
                tenant_id=str(profile.tenant_id),
            )

        return profile

    @staticmethod
    def reactivate(
        profile: TechnicianProfile,
        actor,
        notes: str = "",
    ) -> TechnicianProfile:
        """Admin reactivates a suspended technician."""
        _machine.validate_transition(
            from_state=profile.onboarding_status,
            to_state=OnboardingStatus.ACTIVE,
            entity_id=str(profile.id),
        )

        with transaction.atomic():
            profile.onboarding_status = OnboardingStatus.ACTIVE
            profile.activated_at = timezone.now()
            profile.suspension_reason = ""
            profile.review_notes = notes
            profile.save(update_fields=[
                "onboarding_status",
                "activated_at",
                "suspension_reason",
                "review_notes",
                "updated_at",
            ])

            logger.info(
                "technician_reactivated",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                actor_id=str(actor.id),
                tenant_id=str(profile.tenant_id),
            )

        return profile


# ═══════════════════════════════════════════════════════════════════════════════
# Technician application → technician conversion
# ═══════════════════════════════════════════════════════════════════════════════


class ApplicationConversionError(Exception):
    """Raised when an application cannot be converted."""

    def __init__(self, message: str, code: str = "conversion_failed"):
        self.code = code
        super().__init__(message)


@dataclass
class ConversionResult:
    application: TechnicianApplication
    user: User
    profile: TechnicianProfile
    user_created: bool
    supabase_created: bool


def build_application_snapshot(app: TechnicianApplication) -> dict:
    """
    Freeze the application into a plain dict for outcome correlation.

    Shape is intentionally flat + stable so downstream analytics can
    rely on key paths without chasing schema drift.
    """
    return {
        "application_id": str(app.id),
        "schema_version": app.schema_version,
        "snapshot_at": timezone.now().isoformat(),
        "applicant_type": app.applicant_type,
        "identity": {
            "first_name": app.first_name,
            "last_name": app.last_name,
            "company_name": app.company_name,
            "email": app.email,
            "phone": app.phone,
        },
        "service_area": app.service_area or {},
        "availability": app.availability or {},
        "experience": app.experience or {},
        "capabilities": app.capabilities or {},
        "answers": app.answers or {},
        "source": app.source,
        "submitted_at": app.submitted_at.isoformat() if app.submitted_at else None,
        "review": {
            "reviewer_notes": app.reviewer_notes,
            "rejection_reason": app.rejection_reason,
            "reviewed_by": str(app.reviewed_by_id) if app.reviewed_by_id else None,
            "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None,
        },
    }


class TechnicianApplicationConversionService:
    """
    Converts an approved TechnicianApplication into a User + TechnicianProfile.

    Supports two modes:
      • create  — provision a new Supabase user + local User (default)
      • link    — attach to an existing User in the same tenant
    """

    def __init__(self, *, actor: User, request=None):
        self.actor = actor
        self.request = request

    def convert(
        self,
        application: TechnicianApplication,
        *,
        existing_user_id: Optional[UUID] = None,
        create_supabase_account: bool = True,
        activate_immediately: bool = False,
        reviewer_notes: Optional[str] = None,
    ) -> ConversionResult:
        self._validate(application, existing_user_id)

        snapshot = build_application_snapshot(application)
        supabase_uid: Optional[str] = None
        supabase_created = False

        if existing_user_id is None and create_supabase_account:
            supabase_uid, supabase_created = self._provision_supabase(application)

        try:
            with transaction.atomic():
                if existing_user_id:
                    user, user_created = self._link_existing_user(
                        application, existing_user_id
                    )
                else:
                    user, user_created = self._create_user(
                        application, supabase_uid=supabase_uid
                    )

                profile = self._upsert_profile(
                    application, user, snapshot, activate_immediately
                )

                self._seed_skills_and_regions(application, user, profile)
                self._finalize_application(
                    application, user, profile, reviewer_notes
                )
                self._log_events(application, user, profile, user_created)

        except Exception:
            if supabase_created and supabase_uid:
                self._rollback_supabase(supabase_uid)
            raise

        logger.info(
            "technician_application_converted",
            application_id=str(application.id),
            tenant_id=str(application.tenant_id),
            user_id=str(user.id),
            profile_id=str(profile.id),
            user_created=user_created,
            supabase_created=supabase_created,
            actor_id=str(self.actor.id),
        )

        return ConversionResult(
            application=application,
            user=user,
            profile=profile,
            user_created=user_created,
            supabase_created=supabase_created,
        )

    def _validate(
        self, app: TechnicianApplication, existing_user_id: Optional[UUID]
    ) -> None:
        if app.is_converted:
            raise ApplicationConversionError(
                "Application has already been converted.",
                code="already_converted",
            )

        if app.status not in {
            ApplicationStatus.APPROVED,
            ApplicationStatus.REVIEWING,
            ApplicationStatus.NEW,
        }:
            raise ApplicationConversionError(
                f"Cannot convert an application with status '{app.status}'.",
                code="invalid_status",
            )

        if existing_user_id:
            return

        clash = (
            User.objects.filter(
                tenant_id=app.tenant_id, email__iexact=app.email
            )
            .exclude(role=UserRole.TECHNICIAN)
            .first()
        )
        if clash:
            raise ApplicationConversionError(
                f"A user with email {app.email} already exists in this tenant "
                "with a non-technician role. Use link mode instead.",
                code="email_conflict",
            )

    def _provision_supabase(
        self, app: TechnicianApplication
    ) -> tuple[Optional[str], bool]:
        try:
            auth = SupabaseAuthService()
            res = auth.create_user(app.email)
            uid = res.get("id")
            return (str(uid) if uid is not None else None), True
        except Exception as e:
            logger.warning(
                "supabase_provisioning_failed_during_conversion",
                application_id=str(app.id),
                email=app.email,
                error=str(e),
            )
            return None, False

    def _rollback_supabase(self, supabase_uid: str) -> None:
        try:
            SupabaseAuthService().delete_user(supabase_uid)
            logger.info("supabase_user_rolled_back", supabase_uid=supabase_uid)
        except Exception as e:
            logger.error(
                "supabase_rollback_failed",
                supabase_uid=supabase_uid,
                error=str(e),
            )

    def _create_user(
        self, app: TechnicianApplication, *, supabase_uid: Optional[str]
    ) -> tuple[User, bool]:
        existing = User.objects.filter(
            tenant_id=app.tenant_id,
            email__iexact=app.email,
            role=UserRole.TECHNICIAN,
        ).first()
        if existing:
            if supabase_uid and not existing.supabase_uid:
                existing.supabase_uid = supabase_uid
                existing.save(update_fields=["supabase_uid", "updated_at"])
            return existing, False

        user = User.objects.create(
            tenant_id=app.tenant_id,
            email=app.email,
            first_name=app.first_name,
            last_name=app.last_name,
            phone=app.phone,
            role=UserRole.TECHNICIAN,
            status=UserStatus.PENDING,
            supabase_uid=supabase_uid,
            metadata={
                "origin": "technician_application",
                "application_id": str(app.id),
                "company_name": app.company_name,
                "applicant_type": app.applicant_type,
            },
        )
        return user, True

    def _link_existing_user(
        self, app: TechnicianApplication, user_id: UUID
    ) -> tuple[User, bool]:
        try:
            user = User.objects.select_for_update().get(
                id=user_id, tenant_id=app.tenant_id
            )
        except User.DoesNotExist:
            raise ApplicationConversionError(
                "Target user not found in this tenant.", code="user_not_found"
            )

        if user.role != UserRole.TECHNICIAN:
            user.role = UserRole.TECHNICIAN
            user.save(update_fields=["role", "updated_at"])

        dirty = []
        for fld in ("first_name", "last_name", "phone"):
            if not getattr(user, fld) and getattr(app, fld):
                setattr(user, fld, getattr(app, fld))
                dirty.append(fld)
        if dirty:
            dirty.append("updated_at")
            user.save(update_fields=dirty)

        return user, False

    def _upsert_profile(
        self,
        app: TechnicianApplication,
        user: User,
        snapshot: dict,
        activate_immediately: bool,
    ) -> TechnicianProfile:
        profile, _ = TechnicianProfile.objects.get_or_create(
            user=user,
            defaults={"tenant_id": app.tenant_id},
        )

        profile.tenant_id = app.tenant_id
        profile.application_snapshot = snapshot

        profile.additional_data = {
            **(profile.additional_data or {}),
            "declared_availability": app.availability or {},
            "declared_experience": app.experience or {},
            "declared_service_area": app.service_area or {},
            "declared_capabilities": app.capabilities or {},
            "applicant_type": app.applicant_type,
            "company_name": app.company_name,
        }

        if activate_immediately:
            profile.onboarding_status = OnboardingStatus.ACTIVE
            profile.activated_at = timezone.now()
            profile.reviewed_by = self.actor
            profile.reviewed_at = timezone.now()

        profile.save()
        return profile

    def _seed_skills_and_regions(
        self,
        app: TechnicianApplication,
        user: User,
        profile: TechnicianProfile,
    ) -> None:
        skill_keys = (app.capabilities or {}).get("skill_keys") or []
        if skill_keys:
            skills = Skill.objects.filter(key__in=skill_keys, is_active=True)
            if skills.exists():
                user.skills.add(*skills)

        region_keys = (app.service_area or {}).get("service_region_keys") or []
        if region_keys:
            regions = ServiceRegion.objects.filter(
                key__in=region_keys, is_active=True
            )
            if regions.exists():
                profile.service_regions.add(*regions)

    def _finalize_application(
        self,
        app: TechnicianApplication,
        user: User,
        profile: TechnicianProfile,
        reviewer_notes: Optional[str],
    ) -> None:
        now = timezone.now()

        app.status = ApplicationStatus.APPROVED
        app.status_changed_at = now
        app.reviewed_by = self.actor
        app.reviewed_at = now
        app.converted_user = user
        app.converted_technician_profile = profile
        app.converted_at = now
        app.converted_by = self.actor

        if reviewer_notes:
            stamp = now.strftime("%Y-%m-%d %H:%M")
            entry = f"[{stamp} · {self.actor.email}] {reviewer_notes.strip()}"
            app.reviewer_notes = (
                f"{app.reviewer_notes}\n{entry}" if app.reviewer_notes else entry
            )

        app.save()

    def _log_events(
        self,
        app: TechnicianApplication,
        user: User,
        profile: TechnicianProfile,
        user_created: bool,
    ) -> None:
        common_payload = {
            "application_id": str(app.id),
            "user_id": str(user.id),
            "profile_id": str(profile.id),
            "user_created": user_created,
            "applicant_type": app.applicant_type,
            "email": app.email,
        }

        event_service.log_event(
            event_type=EventType.TECHNICIAN_APPLICATION_CONVERTED,
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=app.id,
            payload=common_payload,
            actor=self.actor,
            tenant_id=app.tenant_id,
            request=self.request,
        )

        event_service.log_event(
            event_type=EventType.TECHNICIAN_PROFILE_CREATED,
            entity_type=EntityType.TECHNICIAN,
            entity_id=profile.id,
            payload={
                **common_payload,
                "onboarding_status": profile.onboarding_status,
            },
            actor=self.actor,
            tenant_id=app.tenant_id,
            request=self.request,
        )

        if user_created:
            event_service.log_event(
                event_type=EventType.USER_CREATED,
                entity_type=EntityType.USER,
                entity_id=user.id,
                payload={
                    "origin": "technician_application_conversion",
                    "application_id": str(app.id),
                    "role": user.role,
                },
                actor=self.actor,
                tenant_id=app.tenant_id,
                request=self.request,
            )
```

---
## `apps/technicians/signals.py`

```python
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
```

---
## `apps/technicians/urls.py`

```python
"""
Technician URL routes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.technicians.views import (
    OnboardingRequirementsView,
    ServiceRegionListView,
    TechnicianAdminViewSet,
    TechnicianApplicationViewSet,
    TechnicianMeView,
    TechnicianSkillsListView,
    TechnicianSubmitView,
)

# Admin router
admin_router = DefaultRouter()
admin_router.register(
    r"technicians",
    TechnicianAdminViewSet,
    basename="admin-technician",
)
admin_router.register(
    r"technician-applications",
    TechnicianApplicationViewSet,
    basename="admin-technician-application",
)

urlpatterns = [
    # Technician self-service
    path("technicians/me/", TechnicianMeView.as_view(), name="technician-me"),
    path("technicians/me/submit/", TechnicianSubmitView.as_view(), name="technician-submit"),

    # Reference data
    path("technicians/service-regions/", ServiceRegionListView.as_view(), name="service-regions"),
    path("technicians/skills/", TechnicianSkillsListView.as_view(), name="technician-skills"),
    path("technicians/onboarding-requirements/", OnboardingRequirementsView.as_view(), name="onboarding-requirements"),

    # Admin routes
    path("admin/", include(admin_router.urls)),
]
```

---
## `apps/technicians/views.py`

```python
"""
Technician views for onboarding and profile management.
"""
from datetime import timedelta

import structlog
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.middleware import get_current_tenant_id
from apps.core.permissions import IsAdmin, IsTechnician
from apps.events.models import EntityType, EventType
from apps.events.services import event_service
from apps.jobs.models import Skill
from apps.jobs.serializers import SkillSerializer
from apps.tenants.models import Tenant, TenantStatus
from apps.users.models import UserRole
from apps.technicians.models import (
    ApplicationStatus,
    OnboardingStatus,
    ServiceRegion,
    TechnicianApplication,
    TechnicianProfile,
    ONBOARDING_REQUIREMENTS,
)
from apps.technicians.serializers import (
    ConversionResultSerializer,
    OnboardingRequirementsSerializer,
    ServiceRegionSerializer,
    TechnicianAdminDetailSerializer,
    TechnicianApplicationApproveSerializer,
    TechnicianApplicationConvertSerializer,
    TechnicianApplicationListSerializer,
    TechnicianApplicationRejectSerializer,
    TechnicianApplicationPublicSubmitSerializer,
    TechnicianApplicationReviewSerializer,
    TechnicianApplicationSerializer,
    TechnicianListSerializer,
    TechnicianOnboardingUpdateSerializer,
    TechnicianProfileReadSerializer,
    TechnicianReviewActionSerializer,
    TechnicianSubmitSerializer,
    TechnicianSuspendSerializer,
)
from apps.technicians.services import (
    ApplicationConversionError,
    TechnicianApplicationConversionService,
    TechnicianOnboardingService,
)

logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN SELF-SERVICE VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianMeView(APIView):
    """
    Self-service endpoint for the logged-in technician's profile.

    GET  /api/v1/technicians/me/ - Get profile with onboarding progress
    PATCH /api/v1/technicians/me/ - Update onboarding fields
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def get(self, request):
        """Get the current technician's profile."""
        if request.user.role != UserRole.TECHNICIAN:
            return Response(
                {"error": {"code": "not_technician", "message": "This endpoint is for technicians only."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.technician_profile
        except TechnicianProfile.DoesNotExist:
            return Response(
                {"error": {"code": "profile_not_found", "message": "Technician profile not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianProfileReadSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        """Update onboarding fields."""
        if request.user.role != UserRole.TECHNICIAN:
            return Response(
                {"error": {"code": "not_technician", "message": "This endpoint is for technicians only."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.technician_profile
        except TechnicianProfile.DoesNotExist:
            return Response(
                {"error": {"code": "profile_not_found", "message": "Technician profile not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianOnboardingUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Track previous completion state for cascading effects
        was_complete = profile.has_completed_required_fields
        previous_status = profile.onboarding_status

        # Perform the update
        profile = serializer.update(profile, serializer.validated_data)

        # Handle cascading effects: if an active technician removes required
        # fields, they go back to pending_onboarding
        is_complete = profile.has_completed_required_fields

        if previous_status == OnboardingStatus.ACTIVE and was_complete and not is_complete:
            # Active technician broke their eligibility
            profile.onboarding_status = OnboardingStatus.PENDING_ONBOARDING
            profile.save(update_fields=["onboarding_status", "updated_at"])

            logger.warning(
                "technician_eligibility_lost",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
                missing_fields=profile.get_missing_onboarding_fields(),
            )

        elif previous_status == OnboardingStatus.SUBMITTED and was_complete and not is_complete:
            # Submitted technician broke their completion — back to pending
            profile.onboarding_status = OnboardingStatus.PENDING_ONBOARDING
            profile.submitted_at = None
            profile.save(update_fields=["onboarding_status", "submitted_at", "updated_at"])

            logger.info(
                "technician_submission_reset",
                profile_id=str(profile.id),
                user_id=str(profile.user_id),
            )

        # Return updated profile
        response_serializer = TechnicianProfileReadSerializer(profile)
        return Response(response_serializer.data)


class TechnicianSubmitView(APIView):
    """
    Submit onboarding for admin review.

    POST /api/v1/technicians/me/submit/
    """

    permission_classes = [IsAuthenticated, IsTechnician]

    def post(self, request):
        if request.user.role != UserRole.TECHNICIAN:
            return Response(
                {"error": {"code": "not_technician", "message": "This endpoint is for technicians only."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            profile = request.user.technician_profile
        except TechnicianProfile.DoesNotExist:
            return Response(
                {"error": {"code": "profile_not_found", "message": "Technician profile not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianSubmitSerializer(
            data=request.data,
            context={"profile": profile},
        )
        serializer.is_valid(raise_exception=True)

        profile = TechnicianOnboardingService.submit_for_review(
            profile=profile,
            actor=request.user,
        )

        response_serializer = TechnicianProfileReadSerializer(profile)
        return Response(response_serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# REFERENCE DATA VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class ServiceRegionListView(APIView):
    """
    List available service regions.

    GET /api/v1/technicians/service-regions/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        regions = ServiceRegion.objects.filter(is_active=True).order_by("state", "name")
        serializer = ServiceRegionSerializer(regions, many=True)

        # Group by state for frontend convenience
        grouped = {}
        for region in serializer.data:
            state = region["state"]
            if state not in grouped:
                grouped[state] = []
            grouped[state].append(region)

        return Response({
            "regions": serializer.data,
            "grouped_by_state": grouped,
            "states": sorted(grouped.keys()),
        })


class TechnicianSkillsListView(APIView):
    """
    List available skills for technicians.

    GET /api/v1/technicians/skills/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        skills = Skill.objects.filter(is_active=True).order_by("category", "label")
        serializer = SkillSerializer(skills, many=True)

        # Group by category
        grouped = {}
        for skill in serializer.data:
            category = skill["category"]
            if category not in grouped:
                grouped[category] = []
            grouped[category].append(skill)

        return Response({
            "skills": serializer.data,
            "grouped_by_category": grouped,
            "categories": sorted(grouped.keys()),
        })


class OnboardingRequirementsView(APIView):
    """
    List onboarding requirements for the frontend.

    GET /api/v1/technicians/onboarding-requirements/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "requirements": [
                {
                    "key": req["key"],
                    "label": req["label"],
                    "type": req["type"],
                    "required": req.get("required", True),
                    "min_count": req.get("min_count"),
                }
                for req in ONBOARDING_REQUIREMENTS
            ]
        })


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN VIEWS
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianAdminViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin viewset for managing technicians.

    GET    /api/v1/admin/technicians/           - List technicians
    GET    /api/v1/admin/technicians/{id}/      - Get technician detail
    POST   /api/v1/admin/technicians/{id}/approve/  - Approve onboarding
    POST   /api/v1/admin/technicians/{id}/request-changes/  - Request changes
    POST   /api/v1/admin/technicians/{id}/suspend/  - Suspend technician
    POST   /api/v1/admin/technicians/{id}/reactivate/  - Reactivate suspended technician
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = TechnicianListSerializer

    def get_queryset(self):
        """Return technician profiles for the admin's tenant."""
        qs = TechnicianProfile.objects.filter(
            tenant_id=self.request.user.tenant_id
        ).select_related("user", "reviewed_by").prefetch_related(
            "service_regions",
            "user__skills",
        )

        # Filter by status
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(onboarding_status=status_filter)

        # Filter for pending review
        pending_review = self.request.query_params.get("pending_review")
        if pending_review and pending_review.lower() == "true":
            qs = qs.filter(onboarding_status=OnboardingStatus.SUBMITTED)

        return qs.order_by("-created_at")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TechnicianAdminDetailSerializer
        return TechnicianListSerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a technician's onboarding."""
        profile = self.get_object()

        serializer = TechnicianReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.approve(
                profile=profile,
                reviewer=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except Exception as e:
            logger.error(
                "technician_approval_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)

    @action(detail=True, methods=["post"], url_path="request-changes")
    def request_changes(self, request, pk=None):
        """Send a technician's profile back for revisions."""
        profile = self.get_object()

        serializer = TechnicianReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.request_changes(
                profile=profile,
                reviewer=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except Exception as e:
            logger.error(
                "technician_changes_request_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)

    @action(detail=True, methods=["post"])
    def suspend(self, request, pk=None):
        """Suspend a technician."""
        profile = self.get_object()

        serializer = TechnicianSuspendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.suspend(
                profile=profile,
                actor=request.user,
                reason=serializer.validated_data["reason"],
            )

            # Optionally store internal notes separately
            notes = serializer.validated_data.get("notes")
            if notes:
                profile.review_notes = notes
                profile.save(update_fields=["review_notes", "updated_at"])

        except Exception as e:
            logger.error(
                "technician_suspension_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)

    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        """Reactivate a suspended technician."""
        profile = self.get_object()

        serializer = TechnicianReviewActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            profile = TechnicianOnboardingService.reactivate(
                profile=profile,
                actor=request.user,
                notes=serializer.validated_data.get("notes", ""),
            )
        except Exception as e:
            logger.error(
                "technician_reactivation_failed",
                profile_id=str(profile.id),
                error=str(e),
            )
            raise

        response_serializer = TechnicianAdminDetailSerializer(profile)
        return Response(response_serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# TECHNICIAN APPLICATION VIEWSET (operator/admin)
# ═══════════════════════════════════════════════════════════════════════════════


class TechnicianApplicationViewSet(viewsets.ModelViewSet):
    """
    Operator-facing CRUD + review for technician applications.

    Routes (mounted under /api/v1/admin/):
        GET    technician-applications/              list (filter, search, order)
        POST   technician-applications/              create (operator manual entry)
        GET    technician-applications/{id}/         retrieve
        PATCH  technician-applications/{id}/         update (notes, applicant data)
        PUT    technician-applications/{id}/         replace
        DELETE technician-applications/{id}/         destroy
        POST   technician-applications/{id}/review/   generic status transition
        POST   technician-applications/{id}/approve/  approve (terminal)
        POST   technician-applications/{id}/reject/   reject (terminal, reason required)
        POST   technician-applications/{id}/convert/   User + TechnicianProfile

    Tenant safety:
        - Queryset is always filtered by the request's tenant.
        - Creates inject tenant_id from context (client cannot spoof).

    Permissions:
        - Admin-only. Applicant-facing submission endpoints (if any) live
          elsewhere and are out of scope for this phase.
    """

    permission_classes = [IsAuthenticated, IsAdmin]
    serializer_class = TechnicianApplicationSerializer

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "status": ["exact", "in"],
        "applicant_type": ["exact"],
        "source": ["exact"],
        "email": ["exact", "iexact"],
    }
    search_fields = [
        "first_name",
        "last_name",
        "company_name",
        "email",
        "phone",
    ]
    ordering_fields = [
        "created_at",
        "submitted_at",
        "status_changed_at",
        "reviewed_at",
    ]
    ordering = ["-created_at"]

    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            tenant_id = getattr(self.request.user, "tenant_id", None)
        if not tenant_id:
            return TechnicianApplication.objects.none()

        return TechnicianApplication.objects.filter(tenant_id=tenant_id).select_related(
            "reviewed_by",
            "converted_user",
            "converted_by",
            "converted_technician_profile",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return TechnicianApplicationListSerializer
        if self.action == "review":
            return TechnicianApplicationReviewSerializer
        if self.action == "approve":
            return TechnicianApplicationApproveSerializer
        if self.action == "reject":
            return TechnicianApplicationRejectSerializer
        if self.action == "convert":
            return TechnicianApplicationConvertSerializer
        return TechnicianApplicationSerializer

    def perform_create(self, serializer):
        tenant_id = get_current_tenant_id() or self.request.user.tenant_id
        now = timezone.now()

        serializer.save(
            tenant_id=tenant_id,
            source=serializer.validated_data.get("source") or "operator_entry",
            submitted_at=serializer.validated_data.get("submitted_at") or now,
        )

        logger.info(
            "technician_application_created",
            application_id=str(serializer.instance.id),
            tenant_id=str(tenant_id),
            created_by=str(self.request.user.id),
            source=serializer.instance.source,
        )

        event_service.log_event(
            event_type=EventType.TECHNICIAN_APPLICATION_CREATED,
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=serializer.instance.id,
            payload={
                "source": serializer.instance.source,
                "applicant_type": serializer.instance.applicant_type,
                "email": serializer.instance.email,
            },
            actor=self.request.user,
            tenant_id=tenant_id,
            request=self.request,
        )

    # ── Status transition helper ──

    def _apply_status_transition(
        self,
        application: TechnicianApplication,
        *,
        new_status: str,
        reviewer_notes: str | None = None,
        rejection_reason: str | None = None,
    ) -> TechnicianApplication:
        """
        Shared mutation path for review / approve / reject.

        - Stamps reviewer + timestamps.
        - Appends reviewer_notes (rather than overwriting) so history accrues.
        - Overwrites rejection_reason (single canonical reason).
        """
        now = timezone.now()
        old_status = application.status

        application.status = new_status
        application.status_changed_at = now
        application.reviewed_by = self.request.user
        application.reviewed_at = now

        update_fields = [
            "status",
            "status_changed_at",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]

        if reviewer_notes:
            stamp = now.strftime("%Y-%m-%d %H:%M")
            author = self.request.user.email
            entry = f"[{stamp} · {author}] {reviewer_notes.strip()}"
            application.reviewer_notes = (
                f"{application.reviewer_notes}\n{entry}"
                if application.reviewer_notes
                else entry
            )
            update_fields.append("reviewer_notes")

        if rejection_reason is not None:
            application.rejection_reason = rejection_reason
            update_fields.append("rejection_reason")

        application.save(update_fields=update_fields)

        event_type_map = {
            ApplicationStatus.APPROVED.value: EventType.TECHNICIAN_APPLICATION_APPROVED,
            ApplicationStatus.REJECTED.value: EventType.TECHNICIAN_APPLICATION_REJECTED,
        }
        status_key = (
            new_status
            if isinstance(new_status, str)
            else getattr(new_status, "value", str(new_status))
        )
        event_service.log_event(
            event_type=event_type_map.get(
                status_key, EventType.TECHNICIAN_APPLICATION_REVIEWED
            ),
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=application.id,
            payload={
                "old_status": old_status,
                "new_status": new_status,
                "reviewer_notes_added": bool(reviewer_notes),
                "rejection_reason": rejection_reason,
            },
            actor=self.request.user,
            tenant_id=application.tenant_id,
            request=self.request,
        )

        logger.info(
            "technician_application_status_changed",
            application_id=str(application.id),
            tenant_id=str(application.tenant_id),
            reviewer_id=str(self.request.user.id),
            old_status=old_status,
            new_status=new_status,
        )

        return application

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        """
        Generic status transition (e.g. move to `reviewing`, or `withdrawn`).

        Prefer /approve/ and /reject/ for terminal decisions — they carry
        dedicated validation. Use POST …/convert/ to provision accounts.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)

        application = self._apply_status_transition(
            application,
            new_status=serializer.validated_data["status"],
            reviewer_notes=serializer.validated_data.get("reviewer_notes"),
            rejection_reason=serializer.validated_data.get("rejection_reason"),
        )

        out = TechnicianApplicationSerializer(
            application, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="approve")
    def approve(self, request, pk=None):
        """
        POST /admin/technician-applications/{id}/approve/

        Body (all optional):
            { "reviewer_notes": "Looks solid, good references." }

        Transitions to `approved` and stamps reviewer metadata.
        Use POST …/convert/ to create or link a User + TechnicianProfile.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)

        application = self._apply_status_transition(
            application,
            new_status=ApplicationStatus.APPROVED,
            reviewer_notes=serializer.validated_data.get("reviewer_notes"),
        )

        out = TechnicianApplicationSerializer(
            application, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        """
        POST /admin/technician-applications/{id}/reject/

        Body:
            {
              "rejection_reason": "No availability in our service areas.",
              "reviewer_notes": "Revisit if we expand to Hudson."   // optional
            }

        `rejection_reason` is required.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)

        application = self._apply_status_transition(
            application,
            new_status=ApplicationStatus.REJECTED,
            reviewer_notes=serializer.validated_data.get("reviewer_notes"),
            rejection_reason=serializer.validated_data["rejection_reason"],
        )

        out = TechnicianApplicationSerializer(
            application, context=self.get_serializer_context()
        )
        return Response(out.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="convert")
    def convert(self, request, pk=None):
        """
        POST /admin/technician-applications/{id}/convert/

        Turns the application into a User + TechnicianProfile.

        Body (all optional):
          {
            "existing_user_id": "uuid",          // link mode
            "create_supabase_account": true,     // default true
            "activate_immediately": false,       // skip onboarding gate
            "reviewer_notes": "Converted after phone screen."
          }

        Returns the updated application plus the created/linked user & profile ids.
        """
        application = self.get_object()

        serializer = self.get_serializer(
            data=request.data,
            context={**self.get_serializer_context(), "application": application},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = TechnicianApplicationConversionService(
            actor=request.user, request=request
        )

        try:
            result = service.convert(
                application,
                existing_user_id=data.get("existing_user_id"),
                create_supabase_account=data.get("create_supabase_account", True),
                activate_immediately=data.get("activate_immediately", False),
                reviewer_notes=data.get("reviewer_notes"),
            )
        except ApplicationConversionError as e:
            return Response(
                {"error": {"code": e.code, "message": str(e)}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        out = ConversionResultSerializer(
            {
                "application": result.application,
                "user_id": result.user.id,
                "profile_id": result.profile.id,
                "user_created": result.user_created,
                "supabase_created": result.supabase_created,
            },
            context=self.get_serializer_context(),
        )
        return Response(out.data, status=status.HTTP_201_CREATED)


class TechnicianApplicationPublicSubmitView(APIView):
    """
    POST /api/v1/tenants/{tenant_id}/apply/

    Public (unauthenticated) endpoint for applicants to submit applications.
    Tenant is determined from the URL path.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, tenant_id):
        try:
            tenant = Tenant.objects.get(id=tenant_id, status=TenantStatus.ACTIVE)
        except Tenant.DoesNotExist:
            return Response(
                {"error": {"code": "tenant_not_found", "message": "Invalid tenant."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianApplicationPublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        recent_cutoff = now - timedelta(hours=24)
        duplicate = TechnicianApplication.objects.filter(
            tenant=tenant,
            email__iexact=serializer.validated_data["email"],
            created_at__gte=recent_cutoff,
        ).exists()

        if duplicate:
            return Response(
                {
                    "error": {
                        "code": "duplicate_application",
                        "message": (
                            "An application with this email was recently submitted. "
                            "Please wait before reapplying."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        application = serializer.save(
            tenant=tenant,
            status=ApplicationStatus.NEW,
            source="public_form",
            submitted_at=now,
            metadata={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": (request.META.get("HTTP_USER_AGENT", "") or "")[:500],
                "submitted_via": "public_api",
            },
        )

        logger.info(
            "technician_application_submitted",
            application_id=str(application.id),
            tenant_id=str(tenant.id),
            email=application.email,
            source="public_form",
        )

        return Response(
            {
                "success": True,
                "message": "Application submitted successfully. We'll be in touch soon.",
                "reference": str(application.id)[:8],
            },
            status=status.HTTP_201_CREATED,
        )
```

---
## `apps/technicians/management/__init__.py`

```python
```

---
## `apps/technicians/management/commands/__init__.py`

```python
```

---
## `apps/technicians/management/commands/seed_technician_data.py`

```python
"""
Management command to seed skills and service regions.

Usage:
    python manage.py seed_technician_data
    python manage.py seed_technician_data --skills-only
    python manage.py seed_technician_data --regions-only
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.jobs.models import Skill
from apps.technicians.models import ServiceRegion


# ═══════════════════════════════════════════════════════════════════════════════
# SKILLS DATA
# ═══════════════════════════════════════════════════════════════════════════════

SKILLS_DATA = [
    # General Cleaning
    {"key": "general.dusting", "label": "Dusting", "category": "General Cleaning"},
    {"key": "general.vacuuming", "label": "Vacuuming", "category": "General Cleaning"},
    {"key": "general.mopping", "label": "Mopping & Floor Care", "category": "General Cleaning"},
    {"key": "general.surface_cleaning", "label": "Surface Cleaning", "category": "General Cleaning"},
    {"key": "general.trash_removal", "label": "Trash Removal", "category": "General Cleaning"},

    # Deep Cleaning
    {"key": "deep.full_deep_clean", "label": "Full Deep Clean", "category": "Deep Cleaning"},
    {"key": "deep.move_in_out", "label": "Move In/Out Clean", "category": "Deep Cleaning"},
    {"key": "deep.spring_clean", "label": "Spring/Seasonal Clean", "category": "Deep Cleaning"},
    {"key": "deep.post_construction", "label": "Post-Construction Clean", "category": "Deep Cleaning"},
    {"key": "deep.post_event", "label": "Post-Event Clean", "category": "Deep Cleaning"},

    # Kitchen
    {"key": "kitchen.general", "label": "Kitchen General Clean", "category": "Kitchen"},
    {"key": "kitchen.oven", "label": "Oven Cleaning", "category": "Kitchen"},
    {"key": "kitchen.refrigerator", "label": "Refrigerator Cleaning", "category": "Kitchen"},
    {"key": "kitchen.dishwasher", "label": "Dishwasher Cleaning", "category": "Kitchen"},
    {"key": "kitchen.cabinets", "label": "Cabinet Interior Cleaning", "category": "Kitchen"},
    {"key": "kitchen.countertops", "label": "Countertop Deep Clean", "category": "Kitchen"},
    {"key": "kitchen.backsplash", "label": "Backsplash & Tile Cleaning", "category": "Kitchen"},

    # Bathroom
    {"key": "bathroom.general", "label": "Bathroom General Clean", "category": "Bathroom"},
    {"key": "bathroom.deep_clean", "label": "Bathroom Deep Clean", "category": "Bathroom"},
    {"key": "bathroom.grout", "label": "Grout Cleaning", "category": "Bathroom"},
    {"key": "bathroom.shower_detail", "label": "Shower/Tub Detail", "category": "Bathroom"},
    {"key": "bathroom.toilet_sanitize", "label": "Toilet Sanitization", "category": "Bathroom"},
    {"key": "bathroom.mirror_glass", "label": "Mirror & Glass Polish", "category": "Bathroom"},

    # Laundry & Linens
    {"key": "laundry.wash_fold", "label": "Wash & Fold", "category": "Laundry & Linens"},
    {"key": "laundry.ironing", "label": "Ironing", "category": "Laundry & Linens"},
    {"key": "laundry.linen_change", "label": "Bed Linen Change", "category": "Laundry & Linens"},
    {"key": "laundry.towel_refresh", "label": "Towel Refresh", "category": "Laundry & Linens"},

    # Organization
    {"key": "org.closet", "label": "Closet Organization", "category": "Organization"},
    {"key": "org.pantry", "label": "Pantry Organization", "category": "Organization"},
    {"key": "org.garage", "label": "Garage Organization", "category": "Organization"},
    {"key": "org.declutter", "label": "Decluttering", "category": "Organization"},
    {"key": "org.drawer", "label": "Drawer Organization", "category": "Organization"},
    {"key": "org.storage", "label": "Storage Space Organization", "category": "Organization"},
    {"key": "org.kids_room", "label": "Kids Room Organization", "category": "Organization"},
    {"key": "org.home_office", "label": "Home Office Organization", "category": "Organization"},

    # Windows & Glass
    {"key": "windows.interior", "label": "Interior Window Cleaning", "category": "Windows & Glass"},
    {"key": "windows.exterior_ground", "label": "Exterior Windows (Ground Level)", "category": "Windows & Glass"},
    {"key": "windows.tracks_sills", "label": "Window Tracks & Sills", "category": "Windows & Glass"},
    {"key": "windows.mirrors", "label": "Mirror Cleaning", "category": "Windows & Glass"},
    {"key": "windows.glass_doors", "label": "Glass Door Cleaning", "category": "Windows & Glass"},

    # Floors & Carpets
    {"key": "floors.hardwood", "label": "Hardwood Floor Care", "category": "Floors & Carpets"},
    {"key": "floors.tile_grout", "label": "Tile & Grout Cleaning", "category": "Floors & Carpets"},
    {"key": "floors.carpet_vacuum", "label": "Carpet Vacuuming", "category": "Floors & Carpets"},
    {"key": "floors.carpet_spot", "label": "Carpet Spot Cleaning", "category": "Floors & Carpets"},
    {"key": "floors.area_rugs", "label": "Area Rug Cleaning", "category": "Floors & Carpets"},

    # Specialty
    {"key": "specialty.pet_area", "label": "Pet Area Cleaning", "category": "Specialty"},
    {"key": "specialty.pet_hair", "label": "Pet Hair Removal", "category": "Specialty"},
    {"key": "specialty.allergen", "label": "Allergen Reduction Clean", "category": "Specialty"},
    {"key": "specialty.green_clean", "label": "Green/Eco Cleaning", "category": "Specialty"},
    {"key": "specialty.sanitization", "label": "Sanitization & Disinfection", "category": "Specialty"},
    {"key": "specialty.odor_removal", "label": "Odor Removal", "category": "Specialty"},

    # Appliances
    {"key": "appliance.microwave", "label": "Microwave Cleaning", "category": "Appliances"},
    {"key": "appliance.washer_dryer", "label": "Washer/Dryer Cleaning", "category": "Appliances"},
    {"key": "appliance.small_appliances", "label": "Small Appliance Cleaning", "category": "Appliances"},

    # Outdoor (Limited)
    {"key": "outdoor.patio", "label": "Patio/Deck Sweep", "category": "Outdoor"},
    {"key": "outdoor.furniture", "label": "Outdoor Furniture Wipe", "category": "Outdoor"},
    {"key": "outdoor.entryway", "label": "Entryway/Porch Clean", "category": "Outdoor"},
]


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE REGIONS DATA
# ═══════════════════════════════════════════════════════════════════════════════

SERVICE_REGIONS_DATA = [
    # New Jersey - Essex County
    {
        "key": "nj_essex_county",
        "name": "Essex County, NJ",
        "short_name": "Essex County",
        "state": "NJ",
        "metadata": {
            "type": "county",
            "state_full": "New Jersey",
            "notable_cities": ["Newark", "East Orange", "Orange", "Montclair", "Bloomfield", "Nutley", "West Orange", "Livingston", "Maplewood", "South Orange", "Millburn", "Caldwell"],
        },
    },
    # New Jersey - Morris County
    {
        "key": "nj_morris_county",
        "name": "Morris County, NJ",
        "short_name": "Morris County",
        "state": "NJ",
        "metadata": {
            "type": "county",
            "state_full": "New Jersey",
            "notable_cities": ["Morristown", "Parsippany", "Denville", "Randolph", "Roxbury", "Mount Olive", "Boonton", "Madison", "Chatham", "Dover", "Morris Plains", "Florham Park"],
        },
    },
]


class Command(BaseCommand):
    help = "Seed skills and service regions for technician onboarding"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skills-only",
            action="store_true",
            help="Only seed skills",
        )
        parser.add_argument(
            "--regions-only",
            action="store_true",
            help="Only seed service regions",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding (use with caution)",
        )

    def handle(self, *args, **options):
        skills_only = options.get("skills_only")
        regions_only = options.get("regions_only")
        clear = options.get("clear")

        # Default to both if neither specified
        seed_skills = not regions_only
        seed_regions = not skills_only

        with transaction.atomic():
            if clear:
                if seed_skills:
                    deleted_skills = Skill.objects.all().delete()
                    self.stdout.write(f"Cleared {deleted_skills[0]} existing skills")
                if seed_regions:
                    deleted_regions = ServiceRegion.objects.all().delete()
                    self.stdout.write(f"Cleared {deleted_regions[0]} existing service regions")

            if seed_skills:
                self._seed_skills()

            if seed_regions:
                self._seed_regions()

        self.stdout.write(self.style.SUCCESS("Seeding complete!"))

    def _seed_skills(self):
        created = 0
        updated = 0

        for skill_data in SKILLS_DATA:
            skill, was_created = Skill.objects.update_or_create(
                key=skill_data["key"],
                defaults={
                    "label": skill_data["label"],
                    "category": skill_data["category"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(f"Skills: {created} created, {updated} updated")

        # Print categories summary
        categories = Skill.objects.filter(is_active=True).values_list(
            "category", flat=True
        ).distinct()
        self.stdout.write(f"Categories: {', '.join(sorted(categories))}")

    def _seed_regions(self):
        created = 0
        updated = 0

        for region_data in SERVICE_REGIONS_DATA:
            region, was_created = ServiceRegion.objects.update_or_create(
                key=region_data["key"],
                defaults={
                    "name": region_data["name"],
                    "short_name": region_data.get("short_name", ""),
                    "state": region_data["state"],
                    "metadata": region_data.get("metadata", {}),
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(f"Service regions: {created} created, {updated} updated")

        # Print states summary
        states = ServiceRegion.objects.filter(is_active=True).values_list(
            "state", flat=True
        ).distinct()
        self.stdout.write(f"States: {', '.join(sorted(states))}")
```

---
## `apps/technicians/migrations/__init__.py`

```python
```

---
## `apps/technicians/migrations/0001_technician_application.py`

```python
# Generated by Django 5.0.14 on 2026-03-19 22:21

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0002_alter_tenant_timezone'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceRegion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(db_index=True, help_text="Stable identifier (e.g., 'nj_essex_county')", max_length=100, unique=True)),
                ('name', models.CharField(help_text="Human-readable name (e.g., 'Essex County, NJ')", max_length=255)),
                ('short_name', models.CharField(blank=True, help_text="Abbreviated name for UI (e.g., 'Essex County')", max_length=100)),
                ('state', models.CharField(db_index=True, help_text="State/province (e.g., 'NJ', 'New Jersey')", max_length=50)),
                ('is_active', models.BooleanField(db_index=True, default=True, help_text='Whether this region is currently available for selection')),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Extensible metadata (geo bounds, zip codes, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('parent', models.ForeignKey(blank=True, help_text='Parent region for hierarchical structures', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='children', to='technicians.serviceregion')),
            ],
            options={
                'db_table': 'service_regions',
                'ordering': ['state', 'name'],
            },
        ),
        migrations.CreateModel(
            name='TechnicianProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('onboarding_status', models.CharField(choices=[('pending_onboarding', 'Pending Onboarding'), ('submitted', 'Submitted for Review'), ('active', 'Active'), ('suspended', 'Suspended')], db_index=True, default='pending_onboarding', max_length=30)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('suspended_at', models.DateTimeField(blank=True, null=True)),
                ('review_notes', models.TextField(blank=True, help_text='Internal notes from the reviewer (visible to admins only)')),
                ('suspension_reason', models.TextField(blank=True, help_text='Reason for suspension (visible to the technician)')),
                ('additional_data', models.JSONField(blank=True, default=dict, help_text='Extensible storage for additional onboarding fields')),
                ('preferences', models.JSONField(blank=True, default=dict, help_text='Technician preferences (notifications, availability, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_technician_profiles', to=settings.AUTH_USER_MODEL)),
                ('service_regions', models.ManyToManyField(blank=True, help_text='Regions where this technician is willing to work', related_name='technician_profiles', to='technicians.serviceregion')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='technician_profiles', to='tenants.tenant')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='technician_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'technician_profiles',
            },
        ),
        migrations.CreateModel(
            name='TechnicianApplication',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('applicant_type', models.CharField(choices=[('individual', 'Individual'), ('company', 'Company / Team')], db_index=True, default='individual', max_length=20)),
                ('first_name', models.CharField(blank=True, max_length=100)),
                ('last_name', models.CharField(blank=True, max_length=100)),
                ('company_name', models.CharField(blank=True, help_text='Populated when applicant_type=company', max_length=255)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('service_area', models.JSONField(blank=True, default=dict, help_text="Geographic coverage. Soft schema: {'counties': ['Essex', 'Hudson'], 'service_region_keys': ['nj_essex_county'], 'max_travel_miles': 25, 'notes': '...'}")),
                ('availability', models.JSONField(blank=True, default=dict, help_text="When the applicant can work. Soft schema: {'days': ['mon','tue','wed'], 'hours': {'start': '08:00', 'end': '18:00'}, 'start_date': '2025-02-01', 'hours_per_week': 30, 'notes': '...'}")),
                ('experience', models.JSONField(blank=True, default=dict, help_text="Work history & qualifications. Soft schema: {'years_cleaning': 3, 'prior_employers': [...], 'has_own_supplies': true, 'has_vehicle': true, 'certifications': [...], 'references': [...]}")),
                ('capabilities', models.JSONField(blank=True, default=dict, help_text="Declared skills/service types. Soft schema: {'skill_keys': ['standard_clean','deep_clean'], 'specialties': [...], 'team_size': 1, 'languages': [...]}")),
                ('answers', models.JSONField(blank=True, default=dict, help_text='Free-form Q&A payload for tenant-specific questions. Keyed by question slug. Shape governed by schema_version.')),
                ('schema_version', models.PositiveIntegerField(default=1, help_text='Version of the questionnaire schema used to populate `answers`.')),
                ('status', models.CharField(choices=[('new', 'New'), ('reviewing', 'Reviewing'), ('approved', 'Approved'), ('rejected', 'Rejected'), ('withdrawn', 'Withdrawn')], db_index=True, default='new', max_length=20)),
                ('submitted_at', models.DateTimeField(blank=True, help_text='When the applicant submitted (may differ from created_at if drafts are supported).', null=True)),
                ('status_changed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('reviewer_notes', models.TextField(blank=True, help_text='Internal operator notes. Never shown to the applicant.')),
                ('rejection_reason', models.TextField(blank=True, help_text='Optional reason captured on rejection. May be shared with applicant.')),
                ('converted_at', models.DateTimeField(blank=True, null=True)),
                ('source', models.CharField(blank=True, help_text="Where this application originated (e.g. 'public_form', 'operator_entry', 'referral').", max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='System/provenance metadata (utm params, IP, user agent, referral codes, etc.).')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('converted_user', models.ForeignKey(blank=True, help_text='User account created/linked when this application was approved.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_applications', to=settings.AUTH_USER_MODEL)),
                ('reviewed_by', models.ForeignKey(blank=True, help_text='Operator who most recently reviewed this application.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_technician_applications', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='technician_applications', to='tenants.tenant')),
                ('converted_technician_profile', models.ForeignKey(blank=True, help_text='TechnicianProfile created/linked on approval.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='source_applications', to='technicians.technicianprofile')),
            ],
            options={
                'db_table': 'technician_applications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='serviceregion',
            index=models.Index(fields=['state', 'is_active'], name='service_reg_state_b2fd1d_idx'),
        ),
        migrations.AddIndex(
            model_name='serviceregion',
            index=models.Index(fields=['is_active'], name='service_reg_is_acti_15d40a_idx'),
        ),
        migrations.AddIndex(
            model_name='technicianprofile',
            index=models.Index(fields=['tenant', 'onboarding_status'], name='technician__tenant__729139_idx'),
        ),
        migrations.AddConstraint(
            model_name='technicianprofile',
            constraint=models.UniqueConstraint(fields=('user',), name='unique_technician_profile_per_user'),
        ),
        migrations.AddIndex(
            model_name='technicianapplication',
            index=models.Index(fields=['tenant', 'status', '-created_at'], name='technician__tenant__3e9fd3_idx'),
        ),
        migrations.AddIndex(
            model_name='technicianapplication',
            index=models.Index(fields=['tenant', 'email'], name='technician__tenant__8cd6d2_idx'),
        ),
        migrations.AddIndex(
            model_name='technicianapplication',
            index=models.Index(fields=['tenant', 'applicant_type', 'status'], name='technician__tenant__94c883_idx'),
        ),
        migrations.AddIndex(
            model_name='technicianapplication',
            index=models.Index(fields=['tenant', '-created_at'], name='technician__tenant__b9c7b8_idx'),
        ),
    ]
```

---
## `apps/technicians/migrations/0002_application_conversion_audit.py`

```python
# Generated by Django 5.0.14 on 2026-03-20 00:09

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('technicians', '0001_technician_application'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='technicianapplication',
            name='converted_by',
            field=models.ForeignKey(blank=True, help_text='Operator who executed the conversion.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='converted_technician_applications', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='technicianprofile',
            name='application_snapshot',
            field=models.JSONField(blank=True, default=dict, help_text='Immutable snapshot of the TechnicianApplication at conversion time. Used for outcome correlation and audit.'),
        ),
    ]
```

---
## `apps/tenants/__init__.py`

```python
```

---
## `apps/tenants/admin.py`

```python
from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "status", "email", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "slug", "email"]
    readonly_fields = ["id", "created_at", "updated_at"]
```

---
## `apps/tenants/apps.py`

```python
from django.apps import AppConfig


class TenantsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.tenants'
```

---
## `apps/tenants/models.py`

```python
"""
Tenant model - represents a business/operation using Ordered.
"""
from django.db import models
from django.core.exceptions import ValidationError
from apps.core.models import BaseModel
from zoneinfo import ZoneInfo


def validate_timezone(value):
    """Validate that the timezone is a valid IANA timezone."""
    try:
        ZoneInfo(value)
    except KeyError:
        raise ValidationError(f"'{value}' is not a valid timezone.")


class TenantStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    TRIAL = "trial", "Trial"


class Tenant(BaseModel):
    """
    A tenant represents a single business operation (e.g., a cleaning company).
    All data is isolated by tenant_id.
    """
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=100, unique=True)
    status = models.CharField(
        max_length=20,
        choices=TenantStatus.choices,
        default=TenantStatus.TRIAL,
        db_index=True,
    )
    
    # Contact info
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    # Settings (JSONB for flexibility)
    settings = models.JSONField(default=dict, blank=True)
    
    # Metadata
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        validators=[validate_timezone],
        help_text="IANA timezone (e.g., 'America/New_York', 'Europe/London')"
    )
    
    class Meta:
        db_table = "tenants"
        ordering = ["name"]
    
    def __str__(self):
        return self.name
    
    @property
    def is_active(self):
        return self.status in [TenantStatus.ACTIVE, TenantStatus.TRIAL]
    
    def clean(self):
        super().clean()
        # Validate timezone on clean
        validate_timezone(self.timezone)```

---
## `apps/tenants/serializers.py`

```python
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
```

---
## `apps/tenants/urls.py`

```python
"""
Tenant URL routes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.technicians.views import TechnicianApplicationPublicSubmitView

from .views import TenantViewSet

router = DefaultRouter()
router.register(r"", TenantViewSet, basename="tenant")

urlpatterns = [
    # Public technician application (unauthenticated; must be before router "")
    path(
        "<uuid:tenant_id>/apply/",
        TechnicianApplicationPublicSubmitView.as_view(),
        name="public-technician-apply",
    ),
    path("", include(router.urls)),
]
```

---
## `apps/tenants/views.py`

```python
"""
Tenant views - admin only.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from apps.core.permissions import IsAdmin
from .models import Tenant
from .serializers import TenantSerializer


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants.
    Admin only - typically only super admins would manage multiple tenants.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        """
        Admins can only see their own tenant.
        Super admin functionality can be added later.
        """
        user = self.request.user
        if user.is_authenticated and user.tenant_id:
            return Tenant.objects.filter(id=user.tenant_id)
        return Tenant.objects.none()
```

---
## `apps/tenants/migrations/__init__.py`

```python
# Migrations for tenants app

```

---
## `apps/tenants/migrations/0001_initial.py`

```python
# Generated manually - Django migration for tenants app

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Tenant',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('status', models.CharField(choices=[('active', 'Active'), ('suspended', 'Suspended'), ('trial', 'Trial')], db_index=True, default='trial', max_length=20)),
                ('email', models.EmailField(blank=True, max_length=254)),
                ('phone', models.CharField(blank=True, max_length=50)),
                ('settings', models.JSONField(blank=True, default=dict)),
                ('timezone', models.CharField(default='UTC', max_length=50)),
            ],
            options={
                'db_table': 'tenants',
                'ordering': ['name'],
            },
        ),
    ]

```

---
## `apps/tenants/migrations/0002_alter_tenant_timezone.py`

```python
# Generated by Django 5.0.14 on 2026-01-08 00:11

import apps.tenants.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tenant",
            name="timezone",
            field=models.CharField(
                default="UTC",
                help_text="IANA timezone (e.g., 'America/New_York', 'Europe/London')",
                max_length=50,
                validators=[apps.tenants.models.validate_timezone],
            ),
        ),
    ]
```

---
## `apps/events/__init__.py`

```python
```

---
## `apps/events/apps.py`

```python
from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.events'
```

---
## `apps/events/models.py`

```python
"""
Event audit log models for tracking domain-level actions.
"""
from django.db import models
from apps.core.models import BaseModel


class EventType(models.TextChoices):
    """Enumeration of all trackable event types."""
    # Booking events
    BOOKING_CREATED = "booking.created", "Booking Created"
    BOOKING_CONFIRMED = "booking.confirmed", "Booking Confirmed"
    BOOKING_CANCELLED = "booking.cancelled", "Booking Cancelled"
    BOOKING_COMPLETED = "booking.completed", "Booking Completed"
    BOOKING_FULFILLED = "booking.fulfilled", "Booking Fulfilled"
    BOOKING_RESCHEDULED = "booking.rescheduled", "Booking Rescheduled"
    BOOKING_JOB_GENERATED = "booking.job_generated", "Booking Job Generated"
    BOOKING_GENERATED_FROM_SERIES = "booking.generated_from_series", "Booking Generated From Series"
    BOOKING_RESCHEDULE_REQUESTED = "booking.reschedule_requested", "Booking Reschedule Requested"
    BOOKING_RESCHEDULE_CONFIRMED = "booking.reschedule_confirmed", "Booking Reschedule Confirmed"
    BOOKING_RESCHEDULE_REJECTED = "booking.reschedule_rejected", "Booking Reschedule Rejected"
    
    # Recurring Series events
    SERIES_PAUSED = "series.paused", "Series Paused"
    SERIES_RESUMED = "series.resumed", "Series Resumed"
    SERIES_ENDED = "series.ended", "Series Ended"
    SERIES_SKIP_NEXT = "series.skip_next", "Series Skip Next"
    SERIES_SKIP_CANCELLED = "series.skip_cancelled", "Series Skip Cancelled"
    SERIES_DATE_SKIPPED = "series.date_skipped", "Series Date Skipped"
    SERIES_OCCURRENCE_SKIPPED = "series.occurrence_skipped", "Series Occurrence Skipped"
    SERIES_OCCURRENCE_RESCHEDULED = "series.occurrence_rescheduled", "Series Occurrence Rescheduled"
    SERIES_EXCEPTION_REVERTED = "series.exception_reverted", "Series Exception Reverted"
    
    # Job events
    JOB_ASSIGNED = "job.assigned", "Job Assigned"
    JOB_CLAIMED = "job.claimed", "Job Claimed"
    JOB_RELEASED = "job.released", "Job Released"
    JOB_STARTED = "job.started", "Job Started"
    JOB_COMPLETED = "job.completed", "Job Completed"
    JOB_CANCELLED = "job.cancelled", "Job Cancelled"
    JOB_GENERATED_FROM_SERIES = "job.generated_from_series", "Job Generated From Series"
    
    # Technician events
    TECHNICIAN_ASSIGNED = "technician.assigned", "Technician Assigned"
    TECHNICIAN_UNASSIGNED = "technician.unassigned", "Technician Unassigned"
    TECHNICIAN_CHECKED_IN = "technician.checked_in", "Technician Checked In"
    TECHNICIAN_CHECKED_OUT = "technician.checked_out", "Technician Checked Out"
    TECHNICIAN_SKILLS_UPDATED = "technician.skills_updated", "Technician Skills Updated"

    # Technician application events
    TECHNICIAN_APPLICATION_CREATED = (
        "technician_application.created",
        "Technician Application Created",
    )
    TECHNICIAN_APPLICATION_REVIEWED = (
        "technician_application.reviewed",
        "Technician Application Reviewed",
    )
    TECHNICIAN_APPLICATION_APPROVED = (
        "technician_application.approved",
        "Technician Application Approved",
    )
    TECHNICIAN_APPLICATION_REJECTED = (
        "technician_application.rejected",
        "Technician Application Rejected",
    )
    TECHNICIAN_APPLICATION_CONVERTED = (
        "technician_application.converted",
        "Technician Application Converted",
    )

    # Technician lifecycle
    TECHNICIAN_PROFILE_CREATED = (
        "technician.profile_created",
        "Technician Profile Created",
    )

    # Memory events
    MEMORY_CREATED = "memory.created", "Memory Created"
    MEMORY_UPDATED = "memory.updated", "Memory Updated"
    MEMORY_DELETED = "memory.deleted", "Memory Deleted"
    
    # Brief events
    BRIEF_GENERATED = "brief.generated", "Brief Generated"
    
    # User events
    USER_CREATED = "user.created", "User Created"
    USER_UPDATED = "user.updated", "User Updated"
    USER_DEACTIVATED = "user.deactivated", "User Deactivated"
    USER_REACTIVATED = "user.reactivated", "User Reactivated"
    
    # Property events
    PROPERTY_CREATED = "property.created", "Property Created"
    PROPERTY_UPDATED = "property.updated", "Property Updated"
    PROPERTY_DELETED = "property.deleted", "Property Deleted"
    
    # Service events
    SERVICE_CREATED = "service.created", "Service Created"
    SERVICE_UPDATED = "service.updated", "Service Updated"
    SERVICE_DELETED = "service.deleted", "Service Deleted"


class EntityType(models.TextChoices):
    """Types of entities that can be tracked."""
    BOOKING = "booking", "Booking"
    JOB = "job", "Job"
    USER = "user", "User"
    PROPERTY = "property", "Property"
    SERVICE = "service", "Service"
    MEMORY = "memory", "Memory"
    TECHNICIAN = "technician", "Technician"
    TECHNICIAN_APPLICATION = "technician_application", "Technician Application"
    BRIEF = "brief", "Brief"
    RECURRING_SERIES = "recurring_series", "Recurring Series"


class Event(BaseModel):
    """
    Audit log entry for tracking all domain-level actions.
    
    This table serves as the source of truth for "what happened and when"
    for debugging, support, reconciliation, and analytics.
    """
    # Tenant association - all events are tenant-scoped
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="events",
        db_index=True,
    )
    
    # Actor - who performed the action (null for system-initiated events)
    actor = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events_created",
        help_text="User who performed the action"
    )
    
    # Event classification
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        db_index=True,
        help_text="Type of event that occurred"
    )
    
    # Entity reference
    entity_type = models.CharField(
        max_length=50,
        choices=EntityType.choices,
        db_index=True,
        help_text="Type of entity this event relates to"
    )
    entity_id = models.UUIDField(
        db_index=True,
        help_text="ID of the entity this event relates to"
    )
    
    # Event data
    payload = models.JSONField(
        default=dict,
        help_text="Event-specific data and context"
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request that triggered the event"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent of the request"
    )
    
    class Meta:
        db_table = "events"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "event_type", "-created_at"]),
            models.Index(fields=["tenant", "entity_type", "entity_id", "-created_at"]),
            models.Index(fields=["tenant", "actor", "-created_at"]),
            models.Index(fields=["tenant", "-created_at"]),
        ]
    
    def __str__(self):
        actor_str = self.actor.email if self.actor else "System"
        return f"{self.event_type} by {actor_str} at {self.created_at}"
```

---
## `apps/events/serializers.py`

```python
"""
Serializers for event models.
"""
from rest_framework import serializers
from .models import Event


class EventSerializer(serializers.ModelSerializer):
    """Serializer for Event model."""
    
    actor_email = serializers.EmailField(source='actor.email', read_only=True)
    actor_name = serializers.CharField(source='actor.full_name', read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id',
            'event_type',
            'entity_type',
            'entity_id',
            'actor',
            'actor_email',
            'actor_name',
            'payload',
            'ip_address',
            'created_at',
        ]
        read_only_fields = fields
```

---
## `apps/events/services.py`

```python
"""
Event logging service for creating audit log entries.
"""
import structlog
from typing import Optional, Dict, Any
from uuid import UUID
from apps.core.middleware import get_current_tenant_id, get_current_user
from .models import Event, EventType, EntityType

logger = structlog.get_logger(__name__)


class EventService:
    """Service for creating and querying audit log events."""
    
    @staticmethod
    def log_event(
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        payload: Optional[Dict[str, Any]] = None,
        actor: Optional['User'] = None,
        tenant_id: Optional[UUID] = None,
        request: Optional['HttpRequest'] = None
    ) -> Event:
        """
        Create an audit log entry.
        
        Args:
            event_type: Type of event (from EventType choices)
            entity_type: Type of entity (from EntityType choices)
            entity_id: ID of the entity
            payload: Additional event-specific data
            actor: User who performed the action (if not provided, tries to get from context)
            tenant_id: Tenant ID (if not provided, tries to get from context)
            request: HTTP request object for extracting metadata
            
        Returns:
            Created Event instance
        """
        # Get tenant from context if not provided
        if not tenant_id:
            tenant_id = get_current_tenant_id()
            if not tenant_id:
                raise ValueError("No tenant context available for event logging")
        
        # Get actor from context if not provided
        if not actor:
            actor = get_current_user()
        
        # Extract request metadata
        ip_address = None
        user_agent = ""
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create the event
        event = Event.objects.create(
            tenant_id=tenant_id,
            actor=actor,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(
            "event_logged",
            event_id=str(event.id),
            event_type=event_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            tenant_id=str(tenant_id),
            actor_id=str(actor.id) if actor else None
        )
        
        return event
    
    @staticmethod
    def get_entity_history(
        entity_type: str,
        entity_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> 'QuerySet[Event]':
        """
        Get all events for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            tenant_id: Tenant ID (if not provided, uses context)
            
        Returns:
            QuerySet of events for the entity
        """
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        
        return Event.objects.filter(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id
        ).select_related('actor').order_by('-created_at')


# Singleton instance
event_service = EventService()
```

---
## `apps/events/urls.py`

```python
"""
Event URL routes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet

router = DefaultRouter()
router.register(r"events", EventViewSet, basename="event")

urlpatterns = [
    path("", include(router.urls)),
]
```

---
## `apps/events/views.py`

```python
"""
Views for querying audit events.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.core.permissions import IsAdmin
from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for querying audit events.
    Admins only.
    """
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event_type', 'entity_type', 'entity_id', 'actor']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter events by current tenant."""
        return Event.objects.filter(
            tenant_id=self.request.user.tenant_id
        ).select_related('actor', 'tenant')
```

---
## `apps/events/migrations/__init__.py`

```python
```

---
## `apps/events/migrations/0001_initial.py`

```python
# Generated migration for events app
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Event',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('event_type', models.CharField(choices=[('booking.created', 'Booking Created'), ('booking.confirmed', 'Booking Confirmed'), ('booking.cancelled', 'Booking Cancelled'), ('booking.completed', 'Booking Completed'), ('booking.rescheduled', 'Booking Rescheduled'), ('job.assigned', 'Job Assigned'), ('job.started', 'Job Started'), ('job.completed', 'Job Completed'), ('job.cancelled', 'Job Cancelled'), ('technician.assigned', 'Technician Assigned'), ('technician.unassigned', 'Technician Unassigned'), ('technician.checked_in', 'Technician Checked In'), ('technician.checked_out', 'Technician Checked Out'), ('memory.created', 'Memory Created'), ('memory.updated', 'Memory Updated'), ('memory.deleted', 'Memory Deleted'), ('user.created', 'User Created'), ('user.updated', 'User Updated'), ('user.deactivated', 'User Deactivated'), ('user.reactivated', 'User Reactivated'), ('property.created', 'Property Created'), ('property.updated', 'Property Updated'), ('property.deleted', 'Property Deleted'), ('service.created', 'Service Created'), ('service.updated', 'Service Updated'), ('service.deleted', 'Service Deleted')], db_index=True, help_text='Type of event that occurred', max_length=50)),
                ('entity_type', models.CharField(choices=[('booking', 'Booking'), ('job', 'Job'), ('user', 'User'), ('property', 'Property'), ('service', 'Service'), ('memory', 'Memory'), ('technician', 'Technician')], db_index=True, help_text='Type of entity this event relates to', max_length=50)),
                ('entity_id', models.UUIDField(db_index=True, help_text='ID of the entity this event relates to')),
                ('payload', models.JSONField(default=dict, help_text='Event-specific data and context')),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of the request that triggered the event', null=True)),
                ('user_agent', models.TextField(blank=True, help_text='User agent of the request')),
                ('actor', models.ForeignKey(blank=True, help_text='User who performed the action', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events_created', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='events', to='tenants.tenant')),
            ],
            options={
                'db_table': 'events',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', 'event_type', '-created_at'], name='events_tenant_event_created_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', 'entity_type', 'entity_id', '-created_at'], name='events_tenant_entity_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', 'actor', '-created_at'], name='events_tenant_actor_idx'),
        ),
        migrations.AddIndex(
            model_name='event',
            index=models.Index(fields=['tenant', '-created_at'], name='events_tenant_created_idx'),
        ),
    ]
```

---
## `apps/events/migrations/0002_rename_events_tenant_event_created_idx_events_tenant__34f0a2_idx_and_more.py`

```python
# Generated by Django 5.0.14 on 2026-01-08 01:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0001_initial"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="event",
            new_name="events_tenant__34f0a2_idx",
            old_name="events_tenant_event_created_idx",
        ),
        migrations.RenameIndex(
            model_name="event",
            new_name="events_tenant__9fdd7a_idx",
            old_name="events_tenant_entity_idx",
        ),
        migrations.RenameIndex(
            model_name="event",
            new_name="events_tenant__bc7134_idx",
            old_name="events_tenant_actor_idx",
        ),
        migrations.RenameIndex(
            model_name="event",
            new_name="events_tenant__a3ecdb_idx",
            old_name="events_tenant_created_idx",
        ),
        migrations.AlterField(
            model_name="event",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("booking.created", "Booking Created"),
                    ("booking.confirmed", "Booking Confirmed"),
                    ("booking.cancelled", "Booking Cancelled"),
                    ("booking.completed", "Booking Completed"),
                    ("booking.fulfilled", "Booking Fulfilled"),
                    ("booking.rescheduled", "Booking Rescheduled"),
                    ("booking.job_generated", "Booking Job Generated"),
                    ("job.assigned", "Job Assigned"),
                    ("job.claimed", "Job Claimed"),
                    ("job.released", "Job Released"),
                    ("job.started", "Job Started"),
                    ("job.completed", "Job Completed"),
                    ("job.cancelled", "Job Cancelled"),
                    ("technician.assigned", "Technician Assigned"),
                    ("technician.unassigned", "Technician Unassigned"),
                    ("technician.checked_in", "Technician Checked In"),
                    ("technician.checked_out", "Technician Checked Out"),
                    ("technician.skills_updated", "Technician Skills Updated"),
                    ("memory.created", "Memory Created"),
                    ("memory.updated", "Memory Updated"),
                    ("memory.deleted", "Memory Deleted"),
                    ("user.created", "User Created"),
                    ("user.updated", "User Updated"),
                    ("user.deactivated", "User Deactivated"),
                    ("user.reactivated", "User Reactivated"),
                    ("property.created", "Property Created"),
                    ("property.updated", "Property Updated"),
                    ("property.deleted", "Property Deleted"),
                    ("service.created", "Service Created"),
                    ("service.updated", "Service Updated"),
                    ("service.deleted", "Service Deleted"),
                ],
                db_index=True,
                help_text="Type of event that occurred",
                max_length=50,
            ),
        ),
    ]
```

---
## `apps/events/migrations/0003_alter_event_entity_type_alter_event_event_type.py`

```python
# Generated by Django 5.0.14 on 2026-01-11 14:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "events",
            "0002_rename_events_tenant_event_created_idx_events_tenant__34f0a2_idx_and_more",
        ),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="entity_type",
            field=models.CharField(
                choices=[
                    ("booking", "Booking"),
                    ("job", "Job"),
                    ("user", "User"),
                    ("property", "Property"),
                    ("service", "Service"),
                    ("memory", "Memory"),
                    ("technician", "Technician"),
                    ("brief", "Brief"),
                ],
                db_index=True,
                help_text="Type of entity this event relates to",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("booking.created", "Booking Created"),
                    ("booking.confirmed", "Booking Confirmed"),
                    ("booking.cancelled", "Booking Cancelled"),
                    ("booking.completed", "Booking Completed"),
                    ("booking.fulfilled", "Booking Fulfilled"),
                    ("booking.rescheduled", "Booking Rescheduled"),
                    ("booking.job_generated", "Booking Job Generated"),
                    ("job.assigned", "Job Assigned"),
                    ("job.claimed", "Job Claimed"),
                    ("job.released", "Job Released"),
                    ("job.started", "Job Started"),
                    ("job.completed", "Job Completed"),
                    ("job.cancelled", "Job Cancelled"),
                    ("technician.assigned", "Technician Assigned"),
                    ("technician.unassigned", "Technician Unassigned"),
                    ("technician.checked_in", "Technician Checked In"),
                    ("technician.checked_out", "Technician Checked Out"),
                    ("technician.skills_updated", "Technician Skills Updated"),
                    ("memory.created", "Memory Created"),
                    ("memory.updated", "Memory Updated"),
                    ("memory.deleted", "Memory Deleted"),
                    ("brief.generated", "Brief Generated"),
                    ("user.created", "User Created"),
                    ("user.updated", "User Updated"),
                    ("user.deactivated", "User Deactivated"),
                    ("user.reactivated", "User Reactivated"),
                    ("property.created", "Property Created"),
                    ("property.updated", "Property Updated"),
                    ("property.deleted", "Property Deleted"),
                    ("service.created", "Service Created"),
                    ("service.updated", "Service Updated"),
                    ("service.deleted", "Service Deleted"),
                ],
                db_index=True,
                help_text="Type of event that occurred",
                max_length=50,
            ),
        ),
    ]
```

---
## `apps/events/migrations/0004_alter_event_entity_type_alter_event_event_type.py`

```python
# Generated by Django 5.0.14 on 2026-01-11 22:45

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0003_alter_event_entity_type_alter_event_event_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="event",
            name="entity_type",
            field=models.CharField(
                choices=[
                    ("booking", "Booking"),
                    ("job", "Job"),
                    ("user", "User"),
                    ("property", "Property"),
                    ("service", "Service"),
                    ("memory", "Memory"),
                    ("technician", "Technician"),
                    ("brief", "Brief"),
                    ("recurring_series", "Recurring Series"),
                ],
                db_index=True,
                help_text="Type of entity this event relates to",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="event",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("booking.created", "Booking Created"),
                    ("booking.confirmed", "Booking Confirmed"),
                    ("booking.cancelled", "Booking Cancelled"),
                    ("booking.completed", "Booking Completed"),
                    ("booking.fulfilled", "Booking Fulfilled"),
                    ("booking.rescheduled", "Booking Rescheduled"),
                    ("booking.job_generated", "Booking Job Generated"),
                    ("booking.generated_from_series", "Booking Generated From Series"),
                    ("booking.reschedule_requested", "Booking Reschedule Requested"),
                    ("booking.reschedule_confirmed", "Booking Reschedule Confirmed"),
                    ("booking.reschedule_rejected", "Booking Reschedule Rejected"),
                    ("series.paused", "Series Paused"),
                    ("series.resumed", "Series Resumed"),
                    ("series.ended", "Series Ended"),
                    ("series.skip_next", "Series Skip Next"),
                    ("series.skip_cancelled", "Series Skip Cancelled"),
                    ("series.date_skipped", "Series Date Skipped"),
                    ("series.occurrence_skipped", "Series Occurrence Skipped"),
                    ("series.occurrence_rescheduled", "Series Occurrence Rescheduled"),
                    ("series.exception_reverted", "Series Exception Reverted"),
                    ("job.assigned", "Job Assigned"),
                    ("job.claimed", "Job Claimed"),
                    ("job.released", "Job Released"),
                    ("job.started", "Job Started"),
                    ("job.completed", "Job Completed"),
                    ("job.cancelled", "Job Cancelled"),
                    ("job.generated_from_series", "Job Generated From Series"),
                    ("technician.assigned", "Technician Assigned"),
                    ("technician.unassigned", "Technician Unassigned"),
                    ("technician.checked_in", "Technician Checked In"),
                    ("technician.checked_out", "Technician Checked Out"),
                    ("technician.skills_updated", "Technician Skills Updated"),
                    ("memory.created", "Memory Created"),
                    ("memory.updated", "Memory Updated"),
                    ("memory.deleted", "Memory Deleted"),
                    ("brief.generated", "Brief Generated"),
                    ("user.created", "User Created"),
                    ("user.updated", "User Updated"),
                    ("user.deactivated", "User Deactivated"),
                    ("user.reactivated", "User Reactivated"),
                    ("property.created", "Property Created"),
                    ("property.updated", "Property Updated"),
                    ("property.deleted", "Property Deleted"),
                    ("service.created", "Service Created"),
                    ("service.updated", "Service Updated"),
                    ("service.deleted", "Service Deleted"),
                ],
                db_index=True,
                help_text="Type of event that occurred",
                max_length=50,
            ),
        ),
    ]
```

---
## `apps/events/migrations/0005_technician_application_events.py`

```python
# Generated by Django 5.0.14 on 2026-03-20 00:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0004_alter_event_entity_type_alter_event_event_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='entity_type',
            field=models.CharField(choices=[('booking', 'Booking'), ('job', 'Job'), ('user', 'User'), ('property', 'Property'), ('service', 'Service'), ('memory', 'Memory'), ('technician', 'Technician'), ('technician_application', 'Technician Application'), ('brief', 'Brief'), ('recurring_series', 'Recurring Series')], db_index=True, help_text='Type of entity this event relates to', max_length=50),
        ),
        migrations.AlterField(
            model_name='event',
            name='event_type',
            field=models.CharField(choices=[('booking.created', 'Booking Created'), ('booking.confirmed', 'Booking Confirmed'), ('booking.cancelled', 'Booking Cancelled'), ('booking.completed', 'Booking Completed'), ('booking.fulfilled', 'Booking Fulfilled'), ('booking.rescheduled', 'Booking Rescheduled'), ('booking.job_generated', 'Booking Job Generated'), ('booking.generated_from_series', 'Booking Generated From Series'), ('booking.reschedule_requested', 'Booking Reschedule Requested'), ('booking.reschedule_confirmed', 'Booking Reschedule Confirmed'), ('booking.reschedule_rejected', 'Booking Reschedule Rejected'), ('series.paused', 'Series Paused'), ('series.resumed', 'Series Resumed'), ('series.ended', 'Series Ended'), ('series.skip_next', 'Series Skip Next'), ('series.skip_cancelled', 'Series Skip Cancelled'), ('series.date_skipped', 'Series Date Skipped'), ('series.occurrence_skipped', 'Series Occurrence Skipped'), ('series.occurrence_rescheduled', 'Series Occurrence Rescheduled'), ('series.exception_reverted', 'Series Exception Reverted'), ('job.assigned', 'Job Assigned'), ('job.claimed', 'Job Claimed'), ('job.released', 'Job Released'), ('job.started', 'Job Started'), ('job.completed', 'Job Completed'), ('job.cancelled', 'Job Cancelled'), ('job.generated_from_series', 'Job Generated From Series'), ('technician.assigned', 'Technician Assigned'), ('technician.unassigned', 'Technician Unassigned'), ('technician.checked_in', 'Technician Checked In'), ('technician.checked_out', 'Technician Checked Out'), ('technician.skills_updated', 'Technician Skills Updated'), ('technician_application.created', 'Technician Application Created'), ('technician_application.reviewed', 'Technician Application Reviewed'), ('technician_application.approved', 'Technician Application Approved'), ('technician_application.rejected', 'Technician Application Rejected'), ('technician_application.converted', 'Technician Application Converted'), ('technician.profile_created', 'Technician Profile Created'), ('memory.created', 'Memory Created'), ('memory.updated', 'Memory Updated'), ('memory.deleted', 'Memory Deleted'), ('brief.generated', 'Brief Generated'), ('user.created', 'User Created'), ('user.updated', 'User Updated'), ('user.deactivated', 'User Deactivated'), ('user.reactivated', 'User Reactivated'), ('property.created', 'Property Created'), ('property.updated', 'Property Updated'), ('property.deleted', 'Property Deleted'), ('service.created', 'Service Created'), ('service.updated', 'Service Updated'), ('service.deleted', 'Service Deleted')], db_index=True, help_text='Type of event that occurred', max_length=50),
        ),
    ]
```
