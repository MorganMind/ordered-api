from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.users.models import UserRole

from .models import Job, JobStatus, Skill

User = get_user_model()


class SkillSerializer(serializers.ModelSerializer):
    """
    Skills use UUID primary keys. Expose ``pk`` (alias of ``id``) so clients
    that expect a ``pk`` field match DRF conventions; values are UUID strings,
    not integers.
    """

    pk = serializers.UUIDField(source="id", read_only=True)

    class Meta:
        model = Skill
        fields = ["id", "pk", "key", "label", "category", "is_active"]
        read_only_fields = fields


class JobSerializer(serializers.ModelSerializer):
    """FKs as raw UUIDs so job queries need not JOIN ``users_user``."""

    tenant = serializers.UUIDField(source="tenant_id", read_only=True)
    service_request = serializers.UUIDField(
        source="service_request_id", read_only=True, allow_null=True
    )
    created_by = serializers.UUIDField(
        source="created_by_id", read_only=True, allow_null=True
    )
    assigned_to = serializers.UUIDField(
        source="assigned_to_id", read_only=True, allow_null=True
    )
    assigned_to_name = serializers.SerializerMethodField()
    booking_id = serializers.UUIDField(read_only=True, allow_null=True)
    booking_title = serializers.SerializerMethodField()
    scheduled_date = serializers.SerializerMethodField()
    scheduled_start_time = serializers.SerializerMethodField()
    scheduled_end_time = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "tenant",
            "title",
            "status",
            "assigned_to",
            "assigned_to_name",
            "booking_id",
            "booking_title",
            "scheduled_date",
            "scheduled_start_time",
            "scheduled_end_time",
            "address",
            "customer_name",
            "customer_phone",
            "customer_email",
            "service_request",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_assigned_to_name(self, obj: Job):
        if not obj.assigned_to_id:
            return None
        u = obj.assigned_to
        return u.full_name if u else None

    def get_booking_title(self, obj: Job):
        return obj.booking.title if obj.booking_id else None

    def get_scheduled_date(self, obj: Job):
        return obj.booking.scheduled_date if obj.booking_id else None

    def get_scheduled_start_time(self, obj: Job):
        if not obj.booking_id:
            return None
        t = obj.booking.scheduled_start_time
        return t.isoformat() if t else None

    def get_scheduled_end_time(self, obj: Job):
        if not obj.booking_id:
            return None
        t = obj.booking.scheduled_end_time
        return t.isoformat() if t else None

    def get_address(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.address or ""

    def get_customer_name(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.client_name or ""

    def get_customer_phone(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.client_phone or ""

    def get_customer_email(self, obj: Job):
        if not obj.booking_id:
            return ""
        return obj.booking.client_email or ""


_ALLOWED_JOB_STATUS = frozenset(c.value for c in JobStatus)


class JobCreateSerializer(serializers.ModelSerializer):
    """
    Workspace staff: create a job in the current tenant.

    ``booking`` / ``service_request`` must belong to the same tenant (enforced via queryset).
    A **draft booking** is auto-created from ``service_request`` when no ``booking`` is sent.
    """

    class Meta:
        model = Job
        fields = ["title", "status", "booking", "service_request", "assigned_to"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tid = self.context.get("tenant_id")
        from apps.bookings.models import Booking
        from apps.service_requests.models import ServiceRequest

        booking_qs = Booking.objects.none()
        sr_qs = ServiceRequest.objects.none()
        user_qs = User.objects.none()
        if tid:
            booking_qs = Booking.objects.filter(tenant_id=tid)
            sr_qs = ServiceRequest.objects.filter(tenant_id=tid)
            user_qs = User.objects.filter(tenant_id=tid)
        self.fields["booking"].queryset = booking_qs
        self.fields["service_request"].queryset = sr_qs
        self.fields["assigned_to"].queryset = user_qs

    def validate_status(self, value: str):
        if value not in _ALLOWED_JOB_STATUS:
            raise serializers.ValidationError(
                f"Invalid status. Allowed: {sorted(_ALLOWED_JOB_STATUS)}."
            )
        return value

    def validate_assigned_to(self, user):
        if user is not None and getattr(user, "role", None) != UserRole.TECHNICIAN:
            raise serializers.ValidationError("Assignee must be a technician.")
        return user

    def validate(self, attrs):
        if attrs.get("booking") or attrs.get("service_request"):
            return attrs
        raise serializers.ValidationError(
            {
                "detail": (
                    "Provide ``booking`` or ``service_request``. "
                    "If only ``service_request`` is set, a draft booking is created automatically."
                )
            }
        )

    def create(self, validated_data):
        if validated_data.get("assigned_to") and validated_data.get(
            "status", JobStatus.OPEN
        ) == JobStatus.OPEN:
            validated_data["status"] = JobStatus.ASSIGNED
        job = super().create(validated_data)
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None
        if not job.booking_id:
            from apps.jobs.services.booking_link import ensure_booking_for_job

            ensure_booking_for_job(job, actor=actor, request=request)
            job.refresh_from_db(fields=["booking_id"])
        return job


class JobOperatorUpdateSerializer(serializers.ModelSerializer):
    """Workspace operators may edit title, status, and assignee."""

    class Meta:
        model = Job
        fields = ["title", "status", "assigned_to"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tid = self.context.get("tenant_id")
        qs = User.objects.none()
        if tid:
            qs = User.objects.filter(tenant_id=tid)
        self.fields["assigned_to"] = serializers.PrimaryKeyRelatedField(
            queryset=qs,
            required=False,
            allow_null=True,
        )

    def validate_status(self, value: str):
        if value not in _ALLOWED_JOB_STATUS:
            raise serializers.ValidationError(
                f"Invalid status. Allowed: {sorted(_ALLOWED_JOB_STATUS)}."
            )
        return value

    def validate_assigned_to(self, user):
        if user is not None and getattr(user, "role", None) != UserRole.TECHNICIAN:
            raise serializers.ValidationError("Assignee must be a technician.")
        return user

    def update(self, instance, validated_data):
        request = self.context.get("request")
        actor = getattr(request, "user", None) if request else None
        assign_in_payload = "assigned_to" in validated_data
        new_assignee = validated_data.get("assigned_to") if assign_in_payload else None
        new_status = validated_data.get("status", serializers.empty)
        needs_booking = (
            (assign_in_payload and new_assignee is not None)
            or (
                new_status is not serializers.empty
                and new_status in (JobStatus.ASSIGNED, JobStatus.IN_PROGRESS)
            )
        )
        if not instance.booking_id and needs_booking:
            from apps.jobs.services.booking_link import ensure_booking_for_job

            ensure_booking_for_job(instance, actor=actor, request=request)
            instance.refresh_from_db(fields=["booking_id"])

        if "assigned_to" in validated_data:
            assignee = validated_data["assigned_to"]
            if assignee is not None and "status" not in validated_data:
                if instance.status == JobStatus.OPEN:
                    validated_data["status"] = JobStatus.ASSIGNED
            if assignee is None and "status" not in validated_data:
                if instance.status == JobStatus.ASSIGNED and instance.assigned_to_id:
                    validated_data["status"] = JobStatus.OPEN
        return super().update(instance, validated_data)
