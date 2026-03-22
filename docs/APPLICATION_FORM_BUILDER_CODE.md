`ordered_api/urls.py`

```python
    path("api/v1/", include("apps.technicians.urls")),
```

`GET /api/v1/admin/application-forms/`  
`POST /api/v1/admin/application-forms/`  
`GET /api/v1/admin/application-forms/{id}/`  
`PATCH /api/v1/admin/application-forms/{id}/`  
`PUT /api/v1/admin/application-forms/{id}/`  
`DELETE /api/v1/admin/application-forms/{id}/`  

`GET /api/v1/admin/technician-applications/`  
`POST /api/v1/admin/technician-applications/`  
`GET /api/v1/admin/technician-applications/{id}/`  
`PATCH /api/v1/admin/technician-applications/{id}/`  
`PUT /api/v1/admin/technician-applications/{id}/`  
`DELETE /api/v1/admin/technician-applications/{id}/`  
`POST /api/v1/admin/technician-applications/{id}/review/`  
`POST /api/v1/admin/technician-applications/{id}/approve/`  
`POST /api/v1/admin/technician-applications/{id}/reject/`  
`POST /api/v1/admin/technician-applications/{id}/convert/`  

`POST /api/v1/forms/{form_id}/apply/`  

`application_forms`

- `id` UUID PK  
- `tenant_id` FK → `tenants_tenant`  
- `title` varchar 255  
- `slug` varchar 150 blank  
- `description` text blank  
- `status` varchar 20 (`draft` | `active` | `archived`)  
- `settings` JSONB default `{}`  
- `created_at`, `updated_at`  
- index `(tenant, status, -created_at)`  
- index `(tenant, slug)`  
- constraint `unique_application_form_slug_per_tenant` on `(tenant, slug)` where `slug` non-empty  

`technician_applications` (subset)

- `application_form_id` FK → `application_forms` null `SET NULL` `related_name=applications`  
- `answers` JSONB  
- `schema_version` positive integer default 1  
- `service_area`, `availability`, `experience`, `capabilities` JSONB  
- index `(application_form, status, -created_at)`  

`apps/technicians/migrations/0003_application_form.py`

```python
# Generated manually for ApplicationForm + TechnicianApplication.application_form

import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0002_alter_tenant_timezone"),
        ("technicians", "0002_application_conversion_audit"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApplicationForm",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="Internal/display title (e.g. 'Summer 2025 Hiring Drive')",
                        max_length=255,
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        blank=True,
                        help_text="URL-friendly identifier. Auto-generated if blank.",
                        max_length=150,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Optional description shown to applicants or used internally.",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("draft", "Draft"),
                            ("active", "Active"),
                            ("archived", "Archived"),
                        ],
                        db_index=True,
                        default="draft",
                        max_length=20,
                    ),
                ),
                (
                    "settings",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text=(
                            "Form-level settings. Reserved keys: "
                            "{'duplicate_check_hours': 24, 'confirmation_message': '...', "
                            "'redirect_url': '...'}"
                        ),
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="application_forms",
                        to="tenants.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "application_forms",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="applicationform",
            index=models.Index(
                fields=["tenant", "status", "-created_at"],
                name="application_tenant_i_7a8b2c_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="applicationform",
            index=models.Index(
                fields=["tenant", "slug"],
                name="application_tenant_i_9d0e1f_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="applicationform",
            constraint=models.UniqueConstraint(
                condition=models.Q(slug__gt=""),
                fields=("tenant", "slug"),
                name="unique_application_form_slug_per_tenant",
            ),
        ),
        migrations.AddField(
            model_name="technicianapplication",
            name="application_form",
            field=models.ForeignKey(
                blank=True,
                help_text="The form definition this application was submitted against.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="applications",
                to="technicians.applicationform",
            ),
        ),
        migrations.AddIndex(
            model_name="technicianapplication",
            index=models.Index(
                fields=["application_form", "status", "-created_at"],
                name="technician_applicatio_af_idx",
            ),
        ),
    ]
```

`apps/technicians/models.py`

```python
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
```

```python
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
```

`apps/technicians/urls.py`

```python
"""
Technician URL routes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.technicians.views import (
    ApplicationFormPublicSubmitView,
    ApplicationFormViewSet,
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
admin_router.register(
    r"application-forms",
    ApplicationFormViewSet,
    basename="admin-application-form",
)

urlpatterns = [
    # Technician self-service
    path("technicians/me/", TechnicianMeView.as_view(), name="technician-me"),
    path("technicians/me/submit/", TechnicianSubmitView.as_view(), name="technician-submit"),

    # Reference data
    path("technicians/service-regions/", ServiceRegionListView.as_view(), name="service-regions"),
    path("technicians/skills/", TechnicianSkillsListView.as_view(), name="technician-skills"),
    path("technicians/onboarding-requirements/", OnboardingRequirementsView.as_view(), name="onboarding-requirements"),

    path(
        "forms/<uuid:form_id>/apply/",
        ApplicationFormPublicSubmitView.as_view(),
        name="public-form-apply",
    ),

    # Admin routes
    path("admin/", include(admin_router.urls)),
]
```

`apps/technicians/serializers.py`

```python
class ApplicationFormListSerializer(serializers.ModelSerializer):
    """Compact representation for list views."""

    application_count = serializers.SerializerMethodField()
    is_accepting_submissions = serializers.BooleanField(read_only=True)

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_accepting_submissions",
            "application_count",
            "created_at",
            "updated_at",
        ]

    def get_application_count(self, obj) -> int:
        if hasattr(obj, "_application_count"):
            return obj._application_count
        # Avoid annotate/subquery SQL (fragile on some Postgres schemas); COUNT
        # by FK does not JOIN users_user.
        from django.db import DatabaseError

        try:
            return TechnicianApplication.objects.filter(
                application_form_id=obj.pk
            ).count()
        except DatabaseError:
            return 0


class ApplicationFormDetailSerializer(serializers.ModelSerializer):
    """Full detail serializer for a single application form."""

    application_count = serializers.SerializerMethodField()
    is_accepting_submissions = serializers.BooleanField(read_only=True)
    status_counts = serializers.SerializerMethodField()

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
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_accepting_submissions",
            "application_count",
            "status_counts",
            "created_at",
            "updated_at",
        ]

    def get_application_count(self, obj) -> int:
        return obj.applications.count()

    def get_status_counts(self, obj) -> dict:
        from django.db.models import Count

        qs = obj.applications.values("status").annotate(count=Count("id"))
        return {row["status"]: row["count"] for row in qs}


class ApplicationFormCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new application form."""

    class Meta:
        model = ApplicationForm
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "status",
            "settings",
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


class ApplicationFormUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating an existing application form."""

    class Meta:
        model = ApplicationForm
        fields = [
            "title",
            "slug",
            "description",
            "status",
            "settings",
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
```

```python
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
        return attrs


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

        return attrs
```

`apps/technicians/views.py`

```python
class ApplicationFormViewSet(viewsets.ModelViewSet):
    """
    Operator-facing CRUD for application form definitions.

    Routes (mounted under /api/v1/admin/):
        GET/POST   application-forms/
        GET/PATCH/PUT/DELETE application-forms/{id}/
    """

    permission_classes = [IsAuthenticated, IsAdmin]

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = {
        "status": ["exact", "in"],
    }
    search_fields = ["title", "slug", "description"]
    ordering_fields = ["created_at", "updated_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        tenant_id = get_current_tenant_id()
        if not tenant_id:
            tenant_id = getattr(self.request.user, "tenant_id", None)
        if not tenant_id:
            return ApplicationForm.objects.none()

        return ApplicationForm.objects.filter(tenant_id=tenant_id)

    def get_serializer_class(self):
        if self.action == "list":
            return ApplicationFormListSerializer
        if self.action == "create":
            return ApplicationFormCreateSerializer
        if self.action in ("update", "partial_update"):
            return ApplicationFormUpdateSerializer
        return ApplicationFormDetailSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tenant_id"] = (
            get_current_tenant_id()
            or getattr(self.request.user, "tenant_id", None)
        )
        return ctx

    def perform_create(self, serializer):
        tenant_id = get_current_tenant_id() or self.request.user.tenant_id

        slug = serializer.validated_data.get("slug")
        if not slug:
            base_slug = slugify(serializer.validated_data["title"])[:140]
            slug = base_slug
            counter = 1
            while ApplicationForm.objects.filter(
                tenant_id=tenant_id, slug=slug
            ).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

        serializer.save(tenant_id=tenant_id, slug=slug)

        logger.info(
            "application_form_created",
            form_id=str(serializer.instance.id),
            tenant_id=str(tenant_id),
            title=serializer.instance.title,
            created_by=str(self.request.user.id),
        )

    def perform_destroy(self, instance):
        if instance.status != ApplicationFormStatus.DRAFT:
            raise ValidationError(
                {
                    "error": {
                        "code": "cannot_delete",
                        "message": (
                            f"Cannot delete a form with status '{instance.status}'. "
                            "Set status to 'archived' instead."
                        ),
                    }
                }
            )

        if instance.applications.exists():
            raise ValidationError(
                {
                    "error": {
                        "code": "has_applications",
                        "message": (
                            "Cannot delete a form that has applications. "
                            "Archive it instead."
                        ),
                    }
                }
            )

        logger.info(
            "application_form_deleted",
            form_id=str(instance.id),
            tenant_id=str(instance.tenant_id),
            title=instance.title,
            deleted_by=str(self.request.user.id),
        )
        instance.delete()
```

```python
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
    filterset_class = TechnicianApplicationFilter
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
            "converted_technician_profile",
            "application_form",
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["tenant_id"] = (
            get_current_tenant_id()
            or getattr(self.request.user, "tenant_id", None)
        )
        return ctx

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
            form_id=(
                str(serializer.instance.application_form_id)
                if serializer.instance.application_form_id
                else None
            ),
        )

        event_service.log_event(
            event_type=EventType.TECHNICIAN_APPLICATION_CREATED,
            entity_type=EntityType.TECHNICIAN_APPLICATION,
            entity_id=serializer.instance.id,
            payload={
                "source": serializer.instance.source,
                "applicant_type": serializer.instance.applicant_type,
                "email": serializer.instance.email,
                "application_form_id": (
                    str(serializer.instance.application_form_id)
                    if serializer.instance.application_form_id
                    else None
                ),
            },
            actor=self.request.user,
            tenant_id=tenant_id,
            request=self.request,
        )
```

```python
class ApplicationFormPublicSubmitView(APIView):
    """
    POST /api/v1/forms/{form_id}/apply/

    Public apply against a specific ApplicationForm; tenant comes from the form.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, form_id):
        try:
            form = ApplicationForm.objects.select_related("tenant").get(id=form_id)
        except ApplicationForm.DoesNotExist:
            return Response(
                {
                    "error": {
                        "code": "form_not_found",
                        "message": "Application form not found.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if not form.is_accepting_submissions:
            return Response(
                {
                    "error": {
                        "code": "form_not_active",
                        "message": (
                            "This application form is not currently accepting "
                            "submissions."
                        ),
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        tenant = form.tenant
        if not tenant.is_active:
            return Response(
                {
                    "error": {
                        "code": "tenant_inactive",
                        "message": "This organization is not currently active.",
                    }
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TechnicianApplicationPublicSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now = timezone.now()
        raw_dup_hours = (form.settings or {}).get("duplicate_check_hours", 24)
        try:
            duplicate_check_hours = int(raw_dup_hours)
        except (TypeError, ValueError):
            duplicate_check_hours = 24
        if duplicate_check_hours < 0:
            duplicate_check_hours = 24
        recent_cutoff = now - timedelta(hours=duplicate_check_hours)

        duplicate = TechnicianApplication.objects.filter(
            tenant=tenant,
            application_form=form,
            email__iexact=serializer.validated_data["email"],
            created_at__gte=recent_cutoff,
        ).exists()

        if duplicate:
            return Response(
                {
                    "error": {
                        "code": "duplicate_application",
                        "message": (
                            "An application with this email was recently submitted "
                            "to this form. Please wait before reapplying."
                        ),
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

        application = serializer.save(
            tenant=tenant,
            application_form=form,
            status=ApplicationStatus.NEW,
            source="public_form",
            submitted_at=now,
            metadata={
                "ip_address": request.META.get("REMOTE_ADDR"),
                "user_agent": (request.META.get("HTTP_USER_AGENT", "") or "")[:500],
                "submitted_via": "public_api",
                "form_id": str(form.id),
                "form_title": form.title,
            },
        )

        logger.info(
            "technician_application_submitted",
            application_id=str(application.id),
            tenant_id=str(tenant.id),
            form_id=str(form.id),
            email=application.email,
            source="public_form",
        )

        confirmation_message = (form.settings or {}).get(
            "confirmation_message",
            "Application submitted successfully. We'll be in touch soon.",
        )

        return Response(
            {
                "success": True,
                "message": confirmation_message,
                "reference": str(application.id)[:8],
            },
            status=status.HTTP_201_CREATED,
        )
```

`apps/technicians/filters.py`

```python
"""
django-filter FilterSets for technician admin APIs.

``application_form`` avoids ModelChoiceFilter (unknown PK used to yield 400).

Invalid values (e.g. the literal string ``"undefined"`` from a bad client
route param) are treated as "no applications match" — HTTP 200 with an
empty page — instead of 400.
"""

import uuid

from django_filters import rest_framework as filters

from .models import TechnicianApplication


class TechnicianApplicationFilter(filters.FilterSet):
    application_form = filters.CharFilter(method="filter_application_form")
    application_form__isnull = filters.BooleanFilter(
        field_name="application_form",
        lookup_expr="isnull",
    )

    class Meta:
        model = TechnicianApplication
        fields = {
            "status": ["exact", "in"],
            "applicant_type": ["exact"],
            "source": ["exact"],
            "email": ["exact", "iexact"],
        }

    def filter_application_form(self, queryset, name, value):
        if value is None:
            return queryset
        s = str(value).strip()
        if not s:
            return queryset
        try:
            uid = uuid.UUID(s)
        except (ValueError, TypeError, AttributeError):
            return queryset.none()
        return queryset.filter(application_form_id=uid)
```

`apps/technicians/services.py`

```python
def build_application_snapshot(app: TechnicianApplication) -> dict:
    """
    Freeze the application into a plain dict for outcome correlation.

    Shape is intentionally flat + stable so downstream analytics can
    rely on key paths without chasing schema drift.
    """
    return {
        "application_id": str(app.id),
        "application_form_id": (
            str(app.application_form_id) if app.application_form_id else None
        ),
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
```

`apps/core/middleware.py` (`get_current_tenant_id`)

`apps/core/permissions.py` (`IsAdmin`)

`apps/events/models.py` (`EventType` technician_application.*, `EntityType.TECHNICIAN_APPLICATION`)

`apps/technicians/migrations/0004_rename_application_tenant_i_7a8b2c_idx_application_tenant__d68dde_idx_and_more.py`

`apps/technicians/migrations/0002_application_conversion_audit.py`

`apps/technicians/migrations/0001_technician_application.py`
