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
# APPLICATION FORM
# ═══════════════════════════════════════════════════════════════════════════════


class ApplicationFormStatus(models.TextChoices):
    """Lifecycle status of an application form."""

    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ApplicationForm(models.Model):
    """
    A tenant-scoped application form definition.

    Each tenant can create multiple forms (e.g. "Summer 2025 Hiring",
    "Experienced Cleaners Only", "Company/Team Application").

    For now every form uses the same built-in field set (the columns on
    TechnicianApplication). In a future phase, a `fields` JSONB column
    will allow per-form field customization.

    Public submissions target a specific form via its ID, which resolves
    the owning tenant automatically.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="application_forms",
        db_index=True,
    )

    title = models.CharField(
        max_length=255,
        help_text="Internal/display title (e.g. 'Summer 2025 Hiring Drive')",
    )
    slug = models.SlugField(
        max_length=150,
        blank=True,
        help_text="URL-friendly identifier. Auto-generated if blank.",
    )
    description = models.TextField(
        blank=True,
        help_text="Optional description shown to applicants or used internally.",
    )

    status = models.CharField(
        max_length=20,
        choices=ApplicationFormStatus.choices,
        default=ApplicationFormStatus.DRAFT,
        db_index=True,
    )

    settings = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Form-level settings. Reserved keys: "
            "{'duplicate_check_hours': 24, 'confirmation_message': '...', "
            "'redirect_url': '...'}"
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "application_forms"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "slug"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                condition=models.Q(slug__gt=""),
                name="unique_application_form_slug_per_tenant",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_accepting_submissions(self) -> bool:
        return self.status == ApplicationFormStatus.ACTIVE


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

    application_form = models.ForeignKey(
        ApplicationForm,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applications",
        help_text="The form definition this application was submitted against.",
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
            models.Index(fields=["application_form", "status", "-created_at"]),
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
