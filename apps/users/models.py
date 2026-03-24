import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

from apps.core.models import BaseModel


class UserRole(models.TextChoices):
    CLIENT = "client", "Client"
    TECHNICIAN = "technician", "Technician"
    ADMIN = "admin", "Admin"


class UserStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", UserRole.ADMIN)
        extra_fields.setdefault("status", UserStatus.ACTIVE)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, BaseModel):
    """
    Tenant-scoped identity aligned with Supabase Auth (supabase_uid).
    Not the same table as auth.users; links via supabase_uid / email.
    """

    email = models.EmailField(unique=True, db_index=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="users",
        db_index=True,
    )

    role = models.CharField(
        max_length=32,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        db_index=True,
    )
    status = models.CharField(
        max_length=32,
        choices=UserStatus.choices,
        default=UserStatus.ACTIVE,
        db_index=True,
    )

    supabase_uid = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
    )
    metadata = models.JSONField(default=dict, blank=True)

    avatar_url = models.URLField(
        max_length=2048,
        blank=True,
        null=True,
        help_text="Public or app-served URL for profile photo (all roles).",
    )

    skills = models.ManyToManyField(
        "jobs.Skill",
        blank=True,
        related_name="users",
    )

    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "users_user"
        ordering = ["-created_at"]

    @property
    def full_name(self) -> str:
        parts = f"{self.first_name} {self.last_name}".strip()
        return parts or self.email

    def __str__(self):
        return self.email
