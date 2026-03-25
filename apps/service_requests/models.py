from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.core.models import BaseModel, TenantAwareModel


class ServiceRequestStatus(models.TextChoices):
    NEW = "new", "New"
    REVIEWING = "reviewing", "Reviewing"
    PRICED = "priced", "Priced"
    CONVERTED = "converted", "Converted"
    CANCELLED = "cancelled", "Cancelled"
    ON_HOLD = "on_hold", "On Hold"


TERMINAL_STATUSES = frozenset(
    {
        ServiceRequestStatus.CONVERTED,
        ServiceRequestStatus.CANCELLED,
    }
)

VALID_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    ServiceRequestStatus.NEW: frozenset(
        {
            ServiceRequestStatus.REVIEWING,
            ServiceRequestStatus.ON_HOLD,
            ServiceRequestStatus.CANCELLED,
        }
    ),
    ServiceRequestStatus.REVIEWING: frozenset(
        {
            ServiceRequestStatus.PRICED,
            ServiceRequestStatus.ON_HOLD,
            ServiceRequestStatus.CANCELLED,
        }
    ),
    ServiceRequestStatus.PRICED: frozenset(
        {
            ServiceRequestStatus.CONVERTED,
            ServiceRequestStatus.REVIEWING,
            ServiceRequestStatus.ON_HOLD,
            ServiceRequestStatus.CANCELLED,
        }
    ),
    ServiceRequestStatus.ON_HOLD: frozenset(
        {
            ServiceRequestStatus.REVIEWING,
            ServiceRequestStatus.CANCELLED,
        }
    ),
    ServiceRequestStatus.CONVERTED: frozenset(),
    ServiceRequestStatus.CANCELLED: frozenset(),
}


class ServiceType(models.TextChoices):
    STANDARD_CLEANING = "standard_cleaning", "Standard Cleaning"
    DEEP_CLEAN = "deep_clean", "Deep Clean"
    ORGANIZING = "organizing", "Organizing"
    MOVE_IN_OUT = "move_in_out", "Move In / Move Out"
    POST_CONSTRUCTION = "post_construction", "Post Construction"
    OTHER = "other", "Other"


class ServiceRequestSource(models.TextChoices):
    FORM = "form", "Form"
    API = "api", "API"
    IMPORT = "import", "Import"


class ServiceOffering(TenantAwareModel):
    """
    Tenant-defined service (offering) with optional links to the global Skill catalog.

    ``reporting_category`` is copied onto ``ServiceRequest.service_type`` for filters,
    analytics, and legacy pricing keys when a request is tied to this offering.
    """

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    reporting_category = models.CharField(
        max_length=64,
        choices=ServiceType.choices,
        default=ServiceType.OTHER,
        help_text=(
            "Stored on ServiceRequest.service_type when this offering is selected — "
            "keeps reporting aligned with the global ServiceType enum."
        ),
    )
    skills = models.ManyToManyField(
        "jobs.Skill",
        through="ServiceOfferingSkill",
        related_name="service_offerings",
        blank=True,
    )

    class Meta:
        db_table = "service_offerings"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="uniq_service_offering_tenant_slug",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "sort_order"]),
        ]

    def __str__(self) -> str:
        return self.name


class ServiceOfferingSkill(BaseModel):
    """Ordered attachment of a catalog Skill to a tenant ServiceOffering."""

    service_offering = models.ForeignKey(
        ServiceOffering,
        on_delete=models.CASCADE,
        related_name="offering_skills",
    )
    skill = models.ForeignKey(
        "jobs.Skill",
        on_delete=models.CASCADE,
        related_name="offering_skill_links",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "service_offering_skills"
        ordering = ["sort_order", "skill__label"]
        constraints = [
            models.UniqueConstraint(
                fields=["service_offering", "skill"],
                name="uniq_service_offering_skill",
            ),
        ]


class ServiceRequest(TenantAwareModel):
    """
    First-class intake object representing a customer request for service.

    Lifecycle
    ---------
    new → reviewing → priced → converted  (happy path)
                   ↘ on_hold ↗
    Any state → cancelled  (operator action)

    Ownership rules
    ---------------
    - tenant / client / source are set server-side at creation; never by the
      submitting client.
    - address_normalized is written by the normalization service or an operator,
      never by the intake form.
    - latest_price_snapshot is a denormalized pointer maintained exclusively by
      apps.pricing.services.
    - converted_job is a denormalized pointer maintained exclusively by
      apps.jobs.services.conversion.

    Note: the Property FK is stored as ``property_ref`` on the model so the name
    does not shadow Python's ``property`` builtin (which would break ``@property``
    methods). API payloads still use the field name ``property`` via serializers.
    """

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
        db_index=True,
    )
    property_ref = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
        db_index=True,
    )

    contact_name = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=64, blank=True)
    contact_email = models.EmailField(blank=True)

    address_raw = models.TextField(
        help_text="Verbatim address as submitted by the customer.",
    )
    address_normalized = models.JSONField(
        null=True,
        blank=True,
        help_text=(
            "Structured address after normalization. "
            "Shape: {street, city, state, zip, country, lat, lng, confidence}. "
            "Written by the normalization service or an operator only."
        ),
    )

    square_feet = models.PositiveIntegerField(null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )

    service_type = models.CharField(
        max_length=64,
        choices=ServiceType.choices,
        db_index=True,
    )
    service_offering = models.ForeignKey(
        ServiceOffering,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="service_requests",
        db_index=True,
    )
    timing_preference = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Flexible scheduling window. "
            "Shape: {preferred_days[], preferred_time_of_day, "
            "date_range_start, date_range_end, flexibility, notes}. "
            "Not strict scheduling — no datetime precision."
        ),
    )
    notes = models.TextField(blank=True)
    media_refs = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "References to attached media. No blobs stored here. "
            "Shape: [{type, storage_key, url?}]"
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=ServiceRequestStatus.choices,
        default=ServiceRequestStatus.NEW,
        db_index=True,
    )
    source = models.CharField(
        max_length=20,
        choices=ServiceRequestSource.choices,
        default=ServiceRequestSource.API,
        db_index=True,
    )

    latest_price_snapshot = models.ForeignKey(
        "pricing.PriceSnapshot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    converted_job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_service_requests",
    )

    internal_operator_notes = models.TextField(blank=True)

    class Meta:
        db_table = "service_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["tenant", "service_type", "-created_at"]),
            models.Index(fields=["tenant", "service_offering", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ServiceRequest({self.id}) [{self.status}] {self.contact_name}"

    def clean(self) -> None:
        if not self.contact_phone and not self.contact_email:
            raise ValidationError(
                "At least one of contact_phone or contact_email must be provided."
            )

    @property
    def service_display_label(self) -> str:
        off = getattr(self, "service_offering", None)
        if off is not None:
            return off.name
        return str(self.get_service_type_display())

    @property
    def is_converted(self) -> bool:
        return self.status == ServiceRequestStatus.CONVERTED

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES
