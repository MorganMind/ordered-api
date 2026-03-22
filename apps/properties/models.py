from django.db import models

from apps.core.models import TenantAwareModel


class Property(TenantAwareModel):
    """Tenant-scoped property; extended for intake / service requests."""

    label = models.CharField(max_length=255, blank=True)

    address = models.CharField(max_length=512, blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=64, blank=True)
    zip_code = models.CharField(max_length=32, blank=True)
    country = models.CharField(max_length=64, blank=True, default="USA")

    property_type = models.CharField(max_length=120, blank=True)
    square_feet = models.PositiveIntegerField(null=True, blank=True)
    bedrooms = models.PositiveSmallIntegerField(null=True, blank=True)
    bathrooms = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    year_built = models.PositiveSmallIntegerField(null=True, blank=True)
    lot_size_sqft = models.PositiveIntegerField(null=True, blank=True)

    client_name = models.CharField(max_length=255, blank=True)
    client_email = models.EmailField(blank=True)
    client_phone = models.CharField(max_length=50, blank=True)

    access_instructions = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "properties"
        ordering = ["-created_at"]

    def __str__(self):
        return self.address or self.label or str(self.id)


class PropertyMemoryType(models.TextChoices):
    DO_RULE = "do_rule", "Do Rule"
    DONT_RULE = "dont_rule", "Don't Rule"
    PRODUCT_PREFERENCE = "product_preference", "Product Preference"
    PERSONAL_SENSITIVITY = "personal_sensitivity", "Personal Sensitivity"
    NOTE = "note", "Note"


class PropertyMemory(TenantAwareModel):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="memories",
        db_index=True,
    )
    memory_type = models.CharField(
        max_length=40,
        choices=PropertyMemoryType.choices,
        db_index=True,
    )
    level = models.CharField(max_length=32, default="property")
    room_name = models.CharField(max_length=255, blank=True)
    surface_name = models.CharField(max_length=255, blank=True)
    label = models.CharField(max_length=512, blank=True)
    content = models.TextField(blank=True)
    author = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_property_memories",
    )
    priority = models.IntegerField(default=0)
    product_name = models.CharField(max_length=255, blank=True)
    use_product = models.BooleanField(default=True)

    class Meta:
        db_table = "property_memories"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "property", "memory_type"]),
        ]

    def __str__(self):
        return self.label or str(self.id)


class IdealConditionPhoto(TenantAwareModel):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="ideal_condition_photos",
        db_index=True,
    )
    room_name = models.CharField(max_length=255, blank=True)
    surface_name = models.CharField(max_length=255, blank=True)
    location_description = models.TextField(blank=True)
    file_name = models.CharField(max_length=512, blank=True)
    file_url = models.URLField(max_length=2048, blank=True)
    thumbnail_url = models.URLField(max_length=2048, blank=True)
    caption = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_ideal_photos",
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        db_table = "ideal_condition_photos"
        ordering = ["created_at"]

    def __str__(self):
        return self.file_name or str(self.id)
