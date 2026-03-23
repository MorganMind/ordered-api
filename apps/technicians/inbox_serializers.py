from rest_framework import serializers

from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
)


class TechnicianInboxMessageSerializer(serializers.ModelSerializer):
    """
    Serialises a single inbox message.

    The ``is_read`` field is computed per-request:
    - Messages sent by the requesting technician are always ``True``.
    - For all other messages, ``True`` only when a
      ``TechnicianInboxMessageReceipt`` exists for that reader.

    When the serializer is used inside
    ``TechnicianInboxThreadSerializer.get_last_message`` the same
    ``request`` context is forwarded so the read state is accurate.
    """

    thread_id = serializers.UUIDField(read_only=True)
    timestamp = serializers.DateTimeField(source="created_at", read_only=True)
    job_id = serializers.UUIDField(read_only=True, allow_null=True)
    job_title = serializers.SerializerMethodField()
    is_read = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianInboxMessage
        fields = [
            "id",
            "thread_id",
            "sender_name",
            "sender_type",
            "body",
            "timestamp",
            "is_read",
            "job_id",
            "job_title",
        ]
        read_only_fields = fields

    def get_job_title(self, obj: TechnicianInboxMessage):
        if obj.job_id:
            return obj.job.title if obj.job else None
        return None

    def get_is_read(self, obj: TechnicianInboxMessage):
        annotated = getattr(obj, "_is_read", None)
        if annotated is not None:
            return bool(annotated)

        request = self.context.get("request")
        reader = getattr(request, "user", None) if request else None
        if not reader or not reader.is_authenticated:
            return False

        if obj.sender_user_id and obj.sender_user_id == reader.id:
            return True

        return TechnicianInboxMessageReceipt.objects.filter(
            message=obj, reader=reader
        ).exists()


class TechnicianInboxThreadSerializer(serializers.ModelSerializer):
    """
    Serialises a thread summary for the inbox list.

    ``last_message`` and ``unread_count`` are computed per row. When
    the queryset has been annotated with ``_unread_count`` by the view
    we prefer that value to avoid N+1 queries.
    """

    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    last_activity_at = serializers.DateTimeField(read_only=True)
    job_id = serializers.UUIDField(read_only=True, allow_null=True)
    job_title = serializers.SerializerMethodField()

    class Meta:
        model = TechnicianInboxThread
        fields = [
            "id",
            "title",
            "subtitle",
            "thread_type",
            "participant_name",
            "participant_avatar_url",
            "last_message",
            "unread_count",
            "last_activity_at",
            "job_id",
            "job_title",
            "is_pinned",
        ]
        read_only_fields = fields

    def get_job_title(self, obj: TechnicianInboxThread):
        if obj.job_id:
            return obj.job.title if obj.job else None
        return None

    def get_last_message(self, obj: TechnicianInboxThread):
        prefetched = getattr(obj, "_prefetched_last_message", None)
        if prefetched is not None:
            if prefetched:
                return TechnicianInboxMessageSerializer(
                    prefetched, context=self.context
                ).data
            return None

        msg = (
            TechnicianInboxMessage.objects.filter(thread=obj)
            .select_related("job")
            .order_by("-created_at")
            .first()
        )
        if not msg:
            return None
        return TechnicianInboxMessageSerializer(
            msg, context=self.context
        ).data

    def get_unread_count(self, obj: TechnicianInboxThread):
        annotated = getattr(obj, "_unread_count", None)
        if annotated is not None:
            return int(annotated)

        request = self.context.get("request")
        reader = getattr(request, "user", None) if request else None
        if not reader or not reader.is_authenticated:
            return 0

        return (
            TechnicianInboxMessage.objects.filter(thread=obj)
            .exclude(sender_user=reader)
            .exclude(read_receipts__reader=reader)
            .count()
        )


class TechnicianInboxThreadPinSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechnicianInboxThread
        fields = ["is_pinned"]


class TechnicianInboxSendSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=10_000, trim_whitespace=True)


class TechnicianInboxStartThreadSerializer(serializers.Serializer):
    """Start a new ``operator_direct`` thread with an operator or admin."""

    operator_id = serializers.UUIDField()
    body = serializers.CharField(max_length=10_000, trim_whitespace=True)


class OperatorInboxStartThreadSerializer(serializers.Serializer):
    """Operator starts (or reuses) a direct thread with a technician."""

    technician_id = serializers.UUIDField()
    body = serializers.CharField(max_length=10_000, trim_whitespace=True)


class OperatorInboxThreadSerializer(TechnicianInboxThreadSerializer):
    """
    Same JSON keys as the technician thread serializer; ``title`` /
    ``participant_*`` describe the **technician** (counterparty for operators).

    ``technician_id`` comes from the model only — declaring it again duplicated
    ``source`` and could raise DRF's ``UniqueTogetherValidator`` assertion.
    """

    class Meta(TechnicianInboxThreadSerializer.Meta):
        fields = list(TechnicianInboxThreadSerializer.Meta.fields) + [
            "technician_id",
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        tech = instance.technician
        t_first = getattr(tech, "first_name", "") or ""
        t_last = getattr(tech, "last_name", "") or ""
        display = (
            f"{t_first} {t_last}".strip()
            or getattr(tech, "email", "")
            or "Technician"
        )
        data["technician_id"] = str(tech.id)
        data["title"] = display
        data["participant_name"] = display
        data["participant_avatar_url"] = getattr(tech, "avatar_url", None)
        if instance.job_id and instance.job:
            data["subtitle"] = getattr(instance.job, "title", "") or "Job"
        elif instance.thread_type == "operator_direct":
            data["subtitle"] = "Direct message"
        return data


class OperatorRecipientSerializer(serializers.Serializer):
    """Operator or admin on the tenant, available for a new conversation."""

    id = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    has_existing_thread = serializers.BooleanField(read_only=True, default=False)
    existing_thread_id = serializers.UUIDField(
        read_only=True, allow_null=True, default=None
    )

    def get_full_name(self, obj):
        first = getattr(obj, "first_name", "") or ""
        last = getattr(obj, "last_name", "") or ""
        full = f"{first} {last}".strip()
        return full or getattr(obj, "email", "Operator")

    def get_avatar_url(self, obj):
        return getattr(obj, "avatar_url", None)


class TechnicianRecipientSerializer(serializers.Serializer):
    """Technician on the tenant; optional existing ``operator_direct`` thread."""

    id = serializers.UUIDField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    has_existing_thread = serializers.BooleanField(read_only=True, default=False)
    existing_thread_id = serializers.UUIDField(
        read_only=True, allow_null=True, default=None
    )

    def get_full_name(self, obj):
        first = getattr(obj, "first_name", "") or ""
        last = getattr(obj, "last_name", "") or ""
        full = f"{first} {last}".strip()
        return full or getattr(obj, "email", "Technician")

    def get_avatar_url(self, obj):
        return getattr(obj, "avatar_url", None)
