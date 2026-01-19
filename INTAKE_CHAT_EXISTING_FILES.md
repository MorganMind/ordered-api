# Intake Chat - Existing Files and Schema

## 1. `apps/users/models.py`
```python
"""
Custom User model with role-based access and tenant association.
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    TECHNICIAN = "technician", "Technician"
    CLIENT = "client", "Client"


class UserStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    PENDING = "pending", "Pending Verification"
    SUSPENDED = "suspended", "Suspended"


class UserManager(BaseUserManager):
    """
    Custom user manager with tenant awareness.
    """
    
    def create_user(self, email, tenant, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        if not tenant:
            raise ValueError("Users must belong to a tenant")
        
        email = self.normalize_email(email)
        user = self.model(email=email, tenant=tenant, **extra_fields)
        
        if password:
            user.set_password(password)
        
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create a superuser - requires a tenant to be passed or created.
        """
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("status", UserStatus.ACTIVE)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        
        # For superuser creation via CLI, we need to handle tenant
        tenant = extra_fields.pop("tenant", None)
        if not tenant:
            from apps.tenants.models import Tenant
            tenant, _ = Tenant.objects.get_or_create(
                slug="system",
                defaults={"name": "System", "status": "active"}
            )
        
        return self.create_user(email, tenant, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for Ordered.
    
    - Every user belongs to exactly one tenant
    - Role determines access level (admin, technician, client)
    - Supports both password and token-based (Supabase) auth
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Tenant association - critical for multi-tenancy
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="users",
        db_index=True,
    )
    
    # Core fields
    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    
    #  Role and status
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=UserStatus.choices,
        default=UserStatus.PENDING,
        db_index=True,
    )
    
    # Supabase integration
    supabase_uid = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Supabase auth user ID"
    )
    
    # Django admin compatibility
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    
    # Profile data (JSONB for flexibility)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Technician skills (many-to-many)
    skills = models.ManyToManyField(
        "jobs.Skill",
        related_name="technicians",
        blank=True,
        help_text="Skills this technician has (only relevant for technicians)"
    )
    
    objects = UserManager()
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    class Meta:
        db_table = "users"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "role"]),
            models.Index(fields=["tenant", "status"]),
        ]
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    @property
    def is_technician(self):
        return self.role == UserRole.TECHNICIAN
    
    @property
    def is_client(self):
        return self.role == UserRole.CLIENT
```

---

## 2. `apps/properties/models.py`
```python
"""
Property models for managing property details, notes, preferences, and reference materials.
"""
from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.core.models import TenantAwareModel


class Property(TenantAwareModel):
    """
    Represents a physical property (home, office, etc.) where services are performed.
    
    Properties persist across technicians, services, time, and repeat visits.
    """
    # Basic property information
    address = models.TextField(
        help_text="Full property address"
    )
    address_line_1 = models.CharField(
        max_length=255,
        blank=True,
        help_text="Street address line 1"
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        help_text="City"
    )
    state = models.CharField(
        max_length=50,
        blank=True,
        help_text="State or province"
    )
    zip_code = models.CharField(
        max_length=20,
        blank=True,
        help_text="ZIP or postal code"
    )
    country = models.CharField(
        max_length=100,
        default="USA",
        help_text="Country"
    )
    
    # Property details (can be populated from RentCast lookup)
    property_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Property type (e.g., Single Family, Condo, Office)"
    )
    square_feet = models.IntegerField(
        null=True,
        blank=True,
        help_text="Square footage"
    )
    bedrooms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of bedrooms"
    )
    bathrooms = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        null=True,
        blank=True,
        help_text="Number of bathrooms"
    )
    year_built = models.IntegerField(
        null=True,
        blank=True,
        help_text="Year built"
    )
    lot_size_sqft = models.IntegerField(
        null=True,
        blank=True,
        help_text="Lot size in square feet"
    )
    
    # Client association (for MVP, using name/email; future: ForeignKey to Client model)
    client_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Primary client name"
    )
    client_email = models.EmailField(
        blank=True,
        help_text="Primary client email"
    )
    client_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Primary client phone"
    )
    # Future: client_id = ForeignKey to Client model
    
    # Additional metadata
    notes = models.TextField(
        blank=True,
        help_text="General property notes"
    )
    access_instructions = models.TextField(
        blank=True,
        help_text="Instructions for accessing the property (keys, codes, etc.)"
    )
    
    # Geographic coordinates (optional)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Latitude coordinate"
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Longitude coordinate"
    )
    
    class Meta:
        db_table = "properties"
        ordering = ["address"]
        indexes = [
            models.Index(fields=["tenant", "address"]),
            models.Index(fields=["tenant", "client_name"]),
            models.Index(fields=["tenant", "city", "state"]),
        ]
        verbose_name_plural = "Properties"
    
    def __str__(self):
        return f"{self.address} ({self.city}, {self.state})"


class PropertyMemoryType(models.TextChoices):
    """Types of property memories/notes."""
    NOTE = "note", "Note"
    PRODUCT_PREFERENCE = "product_preference", "Product Preference"
    PERSONAL_SENSITIVITY = "personal_sensitivity", "Personal Sensitivity"
    DO_RULE = "do_rule", "Do Rule"
    DONT_RULE = "dont_rule", "Don't Rule"


class PropertyMemoryLevel(models.TextChoices):
    """Levels at which memories can be attached."""
    PROPERTY = "property", "Property Level"
    ROOM = "room", "Room Level"
    SURFACE = "surface", "Surface Level"


class PropertyMemory(TenantAwareModel):
    """
    Flexible memory system for property-level notes, preferences, sensitivities, and rules.
    
    These memories persist across technicians, services, time, and repeat visits.
    The text content is designed to be fed to LLMs as part of system prompts.
    """
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="memories",
        db_index=True,
        help_text="Property this memory belongs to"
    )
    
    # Memory classification
    memory_type = models.CharField(
        max_length=50,
        choices=PropertyMemoryType.choices,
        db_index=True,
        help_text="Type of memory (note, preference, sensitivity, rule)"
    )
    level = models.CharField(
        max_length=20,
        choices=PropertyMemoryLevel.choices,
        default=PropertyMemoryLevel.PROPERTY,
        db_index=True,
        help_text="Level at which this memory applies (property, room, surface)"
    )
    
    # Content (key for LLM system prompts)
    label = models.CharField(
        max_length=255,
        help_text="Human-readable label for this memory"
    )
    content = models.TextField(
        help_text="Text content - this is what gets fed to LLM system prompts"
    )
    
    # Room/Surface context (optional, for room/surface-level memories)
    room_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Room name (e.g., 'Kitchen', 'Master Bedroom')"
    )
    surface_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Surface name (e.g., 'Granite Counter', 'Hardwood Floor')"
    )
    
    # Product preferences (for product_preference type)
    product_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Product name (for product preferences)"
    )
    use_product = models.BooleanField(
        default=True,
        help_text="True = use this product, False = do not use this product"
    )
    
    # Author tracking
    author = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="property_memories_created",
        help_text="User who created this memory"
    )
    
    # Additional metadata
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this memory is currently active"
    )
    priority = models.IntegerField(
        default=0,
        help_text="Priority level (higher = more important)"
    )
    
    class Meta:
        db_table = "property_memories"
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["property", "memory_type", "is_active"]),
            models.Index(fields=["property", "level", "is_active"]),
            models.Index(fields=["property", "room_name", "is_active"]),
            models.Index(fields=["property", "surface_name", "is_active"]),
            models.Index(fields=["tenant", "property", "memory_type"]),
        ]
        verbose_name_plural = "Property Memories"
    
    def __str__(self):
        level_str = f" - {self.room_name}" if self.room_name else ""
        surface_str = f" - {self.surface_name}" if self.surface_name else ""
        return f"{self.get_memory_type_display()}: {self.label}{level_str}{surface_str}"


class IdealConditionPhoto(TenantAwareModel):
    """
    Reference photos showing how things should look at a property.
    
    These photos persist across technicians, services, time, and repeat visits.
    Used as visual reference for maintaining ideal conditions.
    """
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="ideal_condition_photos",
        db_index=True,
        help_text="Property this photo belongs to"
    )
    
    # Photo location context
    room_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Room name (e.g., 'Kitchen', 'Master Bedroom')"
    )
    surface_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Surface name (e.g., 'Granite Counter', 'Hardwood Floor')"
    )
    location_description = models.TextField(
        blank=True,
        help_text="Detailed description of where this photo was taken"
    )
    
    # Photo storage (using Google Cloud Storage signed URLs)
    file_name = models.CharField(
        max_length=500,
        help_text="File name in storage"
    )
    file_url = models.URLField(
        max_length=1000,
        help_text="URL to access the photo (signed URL or public URL)"
    )
    thumbnail_url = models.URLField(
        max_length=1000,
        blank=True,
        help_text="Thumbnail URL (optional)"
    )
    
    # Metadata
    caption = models.TextField(
        blank=True,
        help_text="Caption describing what this photo shows"
    )
    taken_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this photo was taken"
    )
    uploaded_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ideal_condition_photos_uploaded",
        help_text="User who uploaded this photo"
    )
    
    # Organization
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this photo is currently active"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying photos"
    )
    
    class Meta:
        db_table = "ideal_condition_photos"
        ordering = ["display_order", "-created_at"]
        indexes = [
            models.Index(fields=["property", "room_name", "is_active"]),
            models.Index(fields=["property", "surface_name", "is_active"]),
            models.Index(fields=["tenant", "property", "is_active"]),
        ]
    
    def __str__(self):
        location = f" - {self.room_name}" if self.room_name else ""
        surface = f" - {self.surface_name}" if self.surface_name else ""
        return f"Photo: {self.property.address}{location}{surface}"
```

---

## 3. `apps/core/models.py`
```python
"""
Base models with automatic tenant filtering.
"""
import uuid
import hashlib
from django.db import models
from django.db.models import Manager
from django.utils import timezone
from datetime import timedelta


class TenantAwareManager(Manager):
    """
    Manager that automatically filters by tenant_id from request context.
    """
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Get tenant from thread-local storage (set by middleware)
        from apps.core.middleware import get_current_tenant_id
        tenant_id = get_current_tenant_id()
        
        if tenant_id is not None:
            queryset = queryset.filter(tenant_id=tenant_id)
        
        return queryset
    
    def all_tenants(self):
        """Bypass tenant filtering - use with caution."""
        return super().get_queryset()


class BaseModel(models.Model):
    """
    Abstract base model with UUID primary key and timestamps.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantAwareModel(BaseModel):
    """
    Abstract base model that belongs to a tenant.
    All queries are automatically filtered by tenant_id.
    """
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(class)s_set",
        db_index=True,
    )
    objects = TenantAwareManager()
    all_objects = Manager()  # Unfiltered access

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Auto-set tenant from context if not provided
        if not self.tenant_id:
            from apps.core.middleware import get_current_tenant_id
            tenant_id = get_current_tenant_id()
            if tenant_id:
                self.tenant_id = tenant_id
        super().save(*args, **kwargs)


def get_default_expiry():
    """Return default expiry time (24 hours from now)."""
    return timezone.now() + timedelta(hours=24)


class IdempotencyKey(models.Model):
    """
    Stores idempotency keys to prevent duplicate request processing.
    
    Keyed by tenant + idempotency_key to ensure tenant isolation.
    Stores request fingerprint to detect key reuse with different payloads.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    # Tenant association
    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="idempotency_keys",
        db_index=True,
    )
    
    # The idempotency key from the request header
    idempotency_key = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Client-provided idempotency key"
    )
    
    # Request fingerprint
    request_method = models.CharField(max_length=10)
    request_path = models.CharField(max_length=500)
    request_hash = models.CharField(
        max_length=64,
        help_text="SHA-256 hash of request body for fingerprinting"
    )
    
    # Cached response
    response_status = models.IntegerField()
    response_body = models.JSONField(default=dict)
    response_headers = models.JSONField(
        default=dict,
        help_text="Relevant response headers to replay"
    )
    
    # Lifecycle
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=get_default_expiry)
    
    # Processing state (for handling concurrent requests)
    is_processing = models.BooleanField(
        default=False,
        help_text="True while the original request is still being processed"
    )
    
    class Meta:
        db_table = "idempotency_keys"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "idempotency_key"],
                name="unique_tenant_idempotency_key"
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "idempotency_key"]),
            models.Index(fields=["expires_at"]),  # For cleanup queries
        ]
    
    def __str__(self):
        return f"{self.idempotency_key} ({self.request_method} {self.request_path})"
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @classmethod
    def compute_request_hash(cls, body: bytes) -> str:
        """Compute SHA-256 hash of request body."""
        return hashlib.sha256(body).hexdigest()


class PropertyLookupUsage(models.Model):
    """
    Tracks property lookup API calls per user per month.
    
    This is a temporary rate limiting mechanism (5 calls/month per user)
    until billing is implemented.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="property_lookup_usage",
        db_index=True,
        help_text="User who made the lookup request"
    )
    
    month = models.CharField(
        max_length=7,  # Format: YYYY-MM
        db_index=True,
        help_text="Month in YYYY-MM format"
    )
    
    count = models.IntegerField(
        default=0,
        help_text="Number of property lookups this month"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = "property_lookup_usage"
        unique_together = [["user", "month"]]
        indexes = [
            models.Index(fields=["user", "month"]),
            models.Index(fields=["month"]),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.month}: {self.count} lookups"
    
    @staticmethod
    def get_current_month() -> str:
        """Get current month in YYYY-MM format."""
        return timezone.now().strftime("%Y-%m")
    
    @staticmethod
    def get_or_create_usage(user) -> "PropertyLookupUsage":
        """Get or create usage record for current month."""
        month = PropertyLookupUsage.get_current_month()
        usage, created = PropertyLookupUsage.objects.get_or_create(
            user=user,
            month=month,
            defaults={"count": 0}
        )
        return usage
    
    @staticmethod
    def increment_usage(user) -> "PropertyLookupUsage":
        """Increment usage count for current month."""
        usage = PropertyLookupUsage.get_or_create_usage(user)
        usage.count += 1
        usage.save(update_fields=["count"])
        return usage
    
    @staticmethod
    def get_usage_count(user) -> int:
        """Get current month's usage count for user."""
        month = PropertyLookupUsage.get_current_month()
        try:
            usage = PropertyLookupUsage.objects.get(user=user, month=month)
            return usage.count
        except PropertyLookupUsage.DoesNotExist:
            return 0
    
    @staticmethod
    def can_make_request(user, limit: int = 5):
        """
        Check if user can make a property lookup request.
        
        Returns:
            (can_make_request, current_count, limit)
        """
        current_count = PropertyLookupUsage.get_usage_count(user)
        return current_count < limit, current_count, limit
```

---

## 4. `apps/tenants/models.py`
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
        validate_timezone(self.timezone)
```

---

## 5. `files/services/file_service.py`
```python
from common.google.google_storage_client import GoogleStorageClient
from uuid import uuid4
from datetime import datetime
from typing import Dict
from django.conf import settings
from common.logger.logger_service import get_logger
import os
import tempfile
from typing import Tuple

class FileService:
    @staticmethod
    async def generate_file_upload_url(
        file_name: str,
        content_type: str,
        folder: str = "system/uploads/files"
    ) -> Dict[str, str]:
        """Generate a signed URL for file upload"""
        # Generate a unique blob name
        extension = file_name.split('.')[-1] if '.' in file_name else ''
        blob_name = f"{folder}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid4()}"
        if extension:
            blob_name += f".{extension}"
        
        # Generate signed URL
        upload_url = await GoogleStorageClient.generate_upload_signed_url(
            bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET,
            blob_name=blob_name,
            content_type=content_type
        )
         
        return {
            "upload_url": upload_url,
            "blob_name": blob_name,
            "file_type": extension,
            "content_type": content_type
        }

    @staticmethod
    async def generate_image_upload_url(
        file_name: str,
        content_type: str,
        folder: str = "system/uploads/images"
    ) -> Dict[str, str]:
        """Generate a signed URL for image upload"""
        # Generate a unique blob name
        extension = file_name.split('.')[-1] if '.' in file_name else ''
        blob_name = f"{folder}/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid4()}"
        if extension:
            blob_name += f".{extension}"

        # Generate signed URL
        upload_url = await GoogleStorageClient.generate_upload_signed_url(
            bucket_name=settings.GOOGLE_CLOUD_STORAGE_BUCKET,
            blob_name=blob_name,
            content_type=content_type
        )

        return {
            "upload_url": upload_url,
            "blob_name": blob_name,
            "file_type": extension,
            "content_type": content_type
        }
    
    @staticmethod
    async def delete_file(file_path: str) -> None:
        """Delete a file from Google Cloud Storage"""
        try:
            storage_client = GoogleStorageClient.get_client()
            bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
            blob = bucket.blob(file_path)
            blob.delete()
        except Exception as e:
            # Log error but don't raise - this is a background task
            print(f"Error deleting file {file_path}: {str(e)}")

    @staticmethod
    async def generate_download_url(file_path: str, expiration: int = 3600) -> str:
        """Generate a signed URL for downloading a file"""
        storage_client = GoogleStorageClient.get_client()
        bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
        blob = bucket.blob(file_path)
        
        url = blob.generate_signed_url(
            version="v4",
            expiration=expiration,
            method="GET"
        )
        
        return url 
    
    @staticmethod
    async def download_file(blob_name: str) -> str:
        """
        Downloads a file from GCS to a temporary location
        Returns: Tuple[temp_file_path, content_type]
        """
        logger = get_logger()
        storage_client = GoogleStorageClient.get_client()
        bucket = storage_client.bucket(settings.GOOGLE_CLOUD_STORAGE_BUCKET)
        
        try:
            # Create temp directory if it doesn't exist
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, os.path.basename(blob_name))
            
            logger.info("Starting file download", extra={
                "blob_name": blob_name,
                "temp_path": temp_file_path
            })
            
            # Get blob  
            blob = bucket.blob(blob_name)
            
            # Download
            blob.download_to_filename(temp_file_path)
            
            logger.info("File download complete", extra={
                "blob_name": blob_name,
                "file_size": os.path.getsize(temp_file_path),
                "content_type": blob.content_type
            })
            
            return temp_file_path
            
        except Exception as e:
            logger.error("File download failed", extra={
                "blob_name": blob_name,
                "error": str(e),
                "error_type": type(e).__name__
            })
            raise
            
    @staticmethod
    async def cleanup_temp_file(file_path: str):
        """Remove temporary file after processing"""
        logger = get_logger()
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info("Temporary file cleaned up", extra={
                    "file_path": file_path
                })
        except Exception as e:
            logger.error("Failed to cleanup temp file", extra={
                "file_path": file_path,
                "error": str(e)
            })
```

---

## 6. `files/views/file_view.py`
```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from ..services.file_service import FileService
from common.supabase.supabase_client import get_current_user
import json

@csrf_exempt
@require_http_methods(["POST"])
async def generate_file_upload_url_view(request):
    """Generate a signed URL for file upload"""
    try:
        data = json.loads(request.body)
        file_name = data.get("file_name")
        content_type = data.get("content_type")

        if not file_name or not content_type:
            return JsonResponse({
                "error": "file_name and content_type are required"
            }, status=400)
        
        user = get_current_user()
        
        result = await FileService.generate_file_upload_url(
            file_name=file_name,
            content_type=content_type,
            folder=f"users/{user['id']}/uploads/files"
        )
        
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
async def generate_image_upload_url_view(request):
    """Generate a signed URL for image upload"""
    try:
        data = json.loads(request.body)
        file_name = data.get("file_name")
        content_type = data.get("content_type")

        if not file_name or not content_type:
            return JsonResponse({
                "error": "file_name and content_type are required"
            }, status=400)

        # Validate content type for images
        if not content_type.startswith('image/'):
            return JsonResponse({
                "error": "Content type must be an image format"
            }, status=400)
        
        user = get_current_user()
        
        result = await FileService.generate_image_upload_url(
            file_name=file_name,
            content_type=content_type,
            folder=f"users/{user['id']}/uploads/images"
        )
        
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)
```

---

## 7. `files/urls.py`
```python
from django.urls import path
from .views.file_view import generate_file_upload_url_view, generate_image_upload_url_view
from common.auth_routes import create_protected_urls

urlpatterns = [
    path("files/upload-url/", generate_file_upload_url_view, name="generate_file_upload_url"),
    path("files/images/upload-url/", generate_image_upload_url_view, name="generate_image_upload_url"),
]

# Wrap them with auth protection
urlpatterns = create_protected_urls(urlpatterns)
```

---

## 8. `llm/services/llm_service.py`
```python
from typing import AsyncGenerator, List, Dict, Any, Optional
from .llm_provider import LLMProvider, BaseLLMProvider
from common.logger.logger_service import get_logger

logger = get_logger()

class LLMService:
    _instance = None
    _providers: Dict[LLMProvider, BaseLLMProvider] = {}
    _default_provider = LLMProvider.OPENAI

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LLMService, cls).__new__(cls)
            # Initialize providers when first instance is created
            cls.configure_providers()
        return cls._instance

    @classmethod
    def configure_providers(cls) -> None:
        """Configure available LLM providers"""
        from .providers.openai_provider import OpenAIProvider
        from .providers.gte_small_provider import GteSmallProvider
        
        cls._providers = {
            LLMProvider.OPENAI: OpenAIProvider(),
            LLMProvider.GTE_SMALL: GteSmallProvider()
        }
        cls._default_provider = LLMProvider.OPENAI

    @classmethod
    async def chat_completion(
        cls,
        messages: List[Dict[str, str]],
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 2000,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:
        """
        Generic chat completion method that works with any provider
        """
        active_provider = cls._providers.get(provider or cls._default_provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")

        return await active_provider.create_chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            stream_options=stream_options
        )

    @classmethod
    async def create_embeddings(
        cls,
        texts: List[str],
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None,
        batch_size: int = 100  # OpenAI allows up to 2048 inputs per request
    ) -> List[Dict[str, Any]]:
        """
        Create embeddings for multiple texts efficiently in batches
        Returns list of embeddings with their usage stats
        """
        active_provider = cls._providers.get(provider or cls._default_provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")

        results = []
        total_usage = {"prompt_tokens": 0, "total_tokens": 0}

        # Process in batches to stay within API limits
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            print(f"embedding batch: {i} {batch_size}")
            try:
                response = await active_provider.create_embeddings(
                    texts=batch,
                    model=model
                )

                results.extend(response["embeddings"])

                # Accumulate token usage
                if "usage" in response:
                    total_usage["prompt_tokens"] += response["usage"]["prompt_tokens"]
                    total_usage["total_tokens"] += response["usage"]["total_tokens"]

            except Exception as e:
                logger.error(f"Error creating embeddings: {e}")
                raise e
        print(f"embedding batch END")
        return {
            "embeddings": results,
            "usage": total_usage
        }

    @classmethod
    async def create_embedding(
        cls,
        text: str,
        provider: Optional[LLMProvider] = None,
        model: Optional[str] = None
    ) -> List[float]:
        """
        Create embedding for a single text
        Returns the embedding vector
        """
        active_provider = cls._providers.get(provider or cls._default_provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")

        try:
            response = await active_provider.create_embeddings(
                texts=[text],  # Send as single-item list
                model=model
            )

            # Return just the embedding vector from the first (and only) result
            return response["embeddings"][0]

        except Exception as e:
            logger.error(
                "Error creating single embedding",
                extra={
                    "text_length": len(text),
                    "error": str(e)
                }
            )
            raise

    @classmethod
    async def count_tokens(
        cls,
        text: str,
        provider: LLMProvider = LLMProvider.OPENAI,
    ) -> int:
        """Count tokens using the specified provider's tokenizer"""
        active_provider = cls._providers.get(provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")
            
        return await active_provider.count_tokens(text)

    @classmethod
    async def count_tokens_batch(
        cls,
        texts: List[str],
        provider: LLMProvider = LLMProvider.OPENAI,
    ) -> List[int]:
        """Count tokens for multiple texts using the specified provider's tokenizer"""
        active_provider = cls._providers.get(provider)
        if not active_provider:
            raise ValueError(f"Provider {provider} not configured")
            
        return await active_provider.count_tokens_batch(texts)
```

---

## 9. `llm/services/providers/openai_provider.py`
```python
from typing import AsyncGenerator, List, Dict, Any, Optional
from openai import AsyncOpenAI
from ..llm_provider import BaseLLMProvider
import os
from openai.types.create_embedding_response import CreateEmbeddingResponse
import tiktoken
from common.logger.logger_service import get_logger

logger = get_logger()

class OpenAIProvider(BaseLLMProvider):
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.default_model = "gpt-4o-mini"
        self.default_embedding_model = "text-embedding-3-small"
        self._encodings = {}  # Cache for encoders

    def _get_encoding(self, model: str):
        """Get or create tiktoken encoding for a model"""
        if model not in self._encodings:
            self._encodings[model] = tiktoken.encoding_for_model(model)
        return self._encodings[model]

    async def count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken"""
        try:
            encoding = self._get_encoding(self.default_embedding_model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens with tiktoken: {e}")
            # Fallback: rough estimate
            return len(text.split()) * 1.3

    async def count_tokens_batch(self, texts: List[str]) -> List[int]:
        """Count tokens for multiple texts"""
        try:
            encoding = self._get_encoding(self.default_embedding_model)
            return [len(encoding.encode(text)) for text in texts]
        except Exception as e:
            logger.error(f"Error counting tokens batch with tiktoken: {e}")
            # Fallback: rough estimate
            return [len(text.split()) * 1.3 for text in texts]

    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:

        response = await self.client.chat.completions.create(
            model=model or self.default_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            stream_options=stream_options
        )

        if stream:
            async def response_generator():
                async for chunk in response:
                    yield chunk
            return response_generator()
        
        return {
            "content": response.choices[0].message.content,
            "usage": response.usage
        } 

    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create an embedding vector for text"""
        response = await self.client.embeddings.create(
            model=model or self.default_embedding_model,
            input=text
        )
        
        return {
            "embedding": response.data[0].embedding,
            "usage": response.usage
        } 

    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create embeddings for multiple texts in one API call
        
        Returns:
            Dict containing:
                embeddings: List of embedding vectors
                usage: Token usage statistics
        """
        response: CreateEmbeddingResponse = await self.client.embeddings.create(
            model=model or self.default_embedding_model,
            input=texts
        )
        
        return {
            "embeddings": [data.embedding for data in response.data],
            "usage": response.usage
        }
```

---

## 10. `llm/services/llm_provider.py`
```python
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional
from enum import Enum

class LLMProvider(Enum):
    OPENAI = "openai"
    GTE_SMALL = "gte-small"
    # Add more providers as needed
    # ANTHROPIC = "anthropic"
    # COHERE = "cohere"

class BaseLLMProvider(ABC):
    def __init__(self):
        self.default_model: Optional[str] = None
        self.default_embedding_model: Optional[str] = None

    @abstractmethod
    async def create_chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False,
        stream_options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None] | Dict[str, Any]:
        pass 
    
    @abstractmethod
    async def create_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        pass 

    @abstractmethod
    async def create_embedding(
        self,
        text: str,
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        pass 

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        pass

    @abstractmethod
    async def count_tokens_batch(self, texts: List[str]) -> List[int]:
        pass
```

---

## 11. `apps/users/authentication.py`
```python
"""
Supabase JWT authentication for Django REST Framework.

Supports both:
- New JWT signing keys (RS256/ES256) via JWKS endpoint
- Legacy JWT secret (HS256) for backward compatibility
"""
import jwt
import structlog
import urllib.request
import json
from functools import lru_cache
from django.conf import settings
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from .models import User

logger = structlog.get_logger(__name__)


class SupabaseAuthentication(authentication.BaseAuthentication):
    """
    Authentication class that validates Supabase JWT tokens.
    
    Supports both new JWT signing keys (RS256/ES256) and legacy JWT secret (HS256).
    Automatically tries JWKS first, then falls back to legacy secret for backward compatibility.
    
    Expected header: Authorization: Bearer <supabase_jwt_token>
    """
    
    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return None
        
        try:
            # Extract token from "Bearer <token>"
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != "bearer":
                return None
            
            token = parts[1]
            
            # Decode and verify JWT
            payload = self._decode_token(token)
            
            # Get or create user from Supabase claims
            user = self._get_user_from_payload(payload)
            
            if not user.is_active:
                raise AuthenticationFailed("User account is disabled.")
            
            if user.status == "suspended":
                raise AuthenticationFailed("User account is suspended.")
            
            return (user, token)
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed("Token has expired.")
        except jwt.InvalidTokenError as e:
            logger.warning("invalid_jwt_token", error=str(e))
            raise AuthenticationFailed("Invalid token.")
        except User.DoesNotExist:
            raise AuthenticationFailed("User not found.")
    
    def _decode_token(self, token):
        """
        Decode and verify Supabase JWT.
        
        Tries JWKS (RS256/ES256) first, then falls back to legacy JWT secret (HS256).
        """
        # First, try to decode the header to determine the algorithm
        try:
            unverified_header = jwt.get_unverified_header(token)
            algorithm = unverified_header.get("alg", "HS256")
        except Exception:
            algorithm = "HS256"
        
        # Try JWKS verification for asymmetric algorithms (RS256, ES256)
        if algorithm in ["RS256", "ES256"]:
            try:
                return self._decode_with_jwks(token)
            except Exception as e:
                logger.debug("jwks_verification_failed", error=str(e), algorithm=algorithm)
                # Fall through to legacy verification
        
        # Fall back to legacy JWT secret (HS256)
        if hasattr(settings, "SUPABASE_JWT_SECRET") and settings.SUPABASE_JWT_SECRET:
            try:
                return jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
            except Exception as e:
                logger.debug("legacy_verification_failed", error=str(e))
        
        # If both methods fail, raise an error
        raise jwt.InvalidTokenError("Token verification failed with both JWKS and legacy methods")
    
    @lru_cache(maxsize=1)
    def _get_jwks(self):
        """
        Fetch JWKS from Supabase endpoint.
        Cached to avoid repeated requests.
        """
        import ssl
        
        jwks_url = f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        try:
            # Create SSL context that doesn't verify certificates (for development)
            # In production, you should use proper certificate verification
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            with urllib.request.urlopen(jwks_url, timeout=5, context=ssl_context) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            logger.warning("failed_to_fetch_jwks", url=jwks_url, error=str(e))
            raise
    
    def _decode_with_jwks(self, token):
        """
        Decode JWT using JWKS (for RS256/ES256 algorithms).
        """
        from jwt.algorithms import RSAAlgorithm, ECAlgorithm
        
        # Get unverified header to find the key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        algorithm = unverified_header.get("alg", "RS256")
        
        if not kid:
            raise jwt.InvalidTokenError("Token header missing 'kid' (key ID)")
        
        # Fetch JWKS
        jwks = self._get_jwks()
        
        # Find the matching key
        key = None
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                key = jwk
                break
        
        if not key:
            raise jwt.InvalidTokenError(f"No matching key found for kid: {kid}")
        
        # Convert JWK to PEM format
        if algorithm == "RS256":
            public_key = RSAAlgorithm.from_jwk(key)
        elif algorithm == "ES256":
            public_key = ECAlgorithm.from_jwk(key)
        else:
            raise jwt.InvalidTokenError(f"Unsupported algorithm: {algorithm}")
        
        # Verify and decode the token
        return jwt.decode(
            token,
            public_key,
            algorithms=[algorithm],
            audience="authenticated",
            issuer=f"{settings.SUPABASE_URL}/auth/v1",
        )
    
    def _get_user_from_payload(self, payload):
        """
        Get user from JWT payload.
        Uses supabase_uid to find existing user.
        """
        supabase_uid = payload.get("sub")
        
        if not supabase_uid:
            raise AuthenticationFailed("Invalid token payload.")
        
        try:
            user = User.objects.select_related("tenant").get(
                supabase_uid=supabase_uid
            )
            return user
        except User.DoesNotExist:
            # User authenticated with Supabase but not in our database
            # This could happen if user signed up via Supabase directly
            logger.warning(
                "supabase_user_not_found",
                supabase_uid=supabase_uid,
                email=payload.get("email"),
            )
            raise AuthenticationFailed(
                "User not registered. Please complete registration."
            )
    
    def authenticate_header(self, request):
        return "Bearer"
```

---

## 12. `config/urls.py`
```python
from django.contrib import admin
from django.urls import path, include
# Import StatusView from views.py module
# Note: We have both views.py and views/ directory, so we import the module file directly
import importlib.util
import os

# Get the path to views.py
base_dir = os.path.dirname(os.path.dirname(__file__))
views_py = os.path.join(base_dir, 'apps', 'core', 'views.py')

# Load the module directly from file
spec = importlib.util.spec_from_file_location("core_views", views_py)
core_views = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_views)
StatusView = core_views.StatusView

from apps.users.views import ClientProfileView, ClientPropertyView

urlpatterns = [
    path("admin/", admin.site.urls),
        path("status", StatusView.as_view(), name="status"),
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/client/profile", ClientProfileView.as_view(), name="client-profile"),
    path("api/v1/client/property", ClientPropertyView.as_view(), name="client-property"),
    path("api/v1/tenants/", include("apps.tenants.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/", include("apps.jobs.urls")),
        path("api/v1/", include("apps.bookings.urls")),
        path("api/v1/", include("apps.core.urls.property_lookup")),  # Must come before properties.urls to avoid conflict
        path("api/v1/", include("apps.properties.urls")),
        path("api/v1/", include("apps.briefs.urls")),
        path("api/v1/", include("apps.core.urls.address_autocomplete")),
    path("api/v1/", include("files.urls")),
]
```

---

## 13. `config/settings/base.py` (Partial - INSTALLED_APPS section)
```python
LOCAL_APPS = [
    "apps.core",
    "apps.tenants",
    "apps.users",
    "apps.events",
    "apps.jobs",
    "apps.bookings",
    "apps.properties",
    "apps.briefs",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS
```
