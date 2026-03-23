from django.conf import settings
from django.db import models

from apps.core.models import TenantAwareModel


class TechnicianInboxThreadType(models.TextChoices):
    OPERATOR_DIRECT = "operator_direct", "Operator direct"
    CLIENT_JOB = "client_job", "Client job"
    SYSTEM_ALERT = "system_alert", "System alert"


class TechnicianInboxSenderType(models.TextChoices):
    OPERATOR = "operator", "Operator"
    CLIENT = "client", "Client"
    SYSTEM = "system", "System"
    TECHNICIAN = "technician", "Technician"


class TechnicianInboxThread(TenantAwareModel):
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_threads",
        db_index=True,
    )
    thread_type = models.CharField(
        max_length=32,
        choices=TechnicianInboxThreadType.choices,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=512, blank=True, default="")
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technician_inbox_threads",
    )
    participant_name = models.CharField(max_length=255, blank=True, default="")
    participant_avatar_url = models.URLField(
        blank=True, null=True, max_length=2048
    )
    is_pinned = models.BooleanField(default=False, db_index=True)
    last_activity_at = models.DateTimeField(db_index=True)
    operator_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_inbox_threads",
    )
    client_contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_inbox_threads",
    )

    class Meta:
        db_table = "technician_inbox_threads"
        indexes = [
            models.Index(
                fields=["tenant", "technician", "-last_activity_at"]
            ),
            models.Index(fields=["technician", "thread_type"]),
        ]
        ordering = ["-is_pinned", "-last_activity_at"]

    def __str__(self):
        return f"{self.title} ({self.thread_type}) — {self.technician}"


class TechnicianInboxMessage(TenantAwareModel):
    thread = models.ForeignKey(
        TechnicianInboxThread,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender_type = models.CharField(
        max_length=32,
        choices=TechnicianInboxSenderType.choices,
        db_index=True,
    )
    sender_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbox_messages_sent",
    )
    sender_name = models.CharField(max_length=255)
    body = models.TextField()
    job = models.ForeignKey(
        "jobs.Job",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technician_inbox_messages",
    )

    class Meta:
        db_table = "technician_inbox_messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["thread", "created_at"]),
        ]

    def __str__(self):
        return f"[{self.sender_type}] {self.sender_name}: {self.body[:50]}"


class TechnicianInboxMessageReceipt(TenantAwareModel):
    message = models.ForeignKey(
        TechnicianInboxMessage,
        on_delete=models.CASCADE,
        related_name="read_receipts",
    )
    reader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="inbox_read_receipts",
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "technician_inbox_message_receipts"
        constraints = [
            models.UniqueConstraint(
                fields=["message", "reader"],
                name="uniq_inbox_msg_reader",
            ),
        ]

    def __str__(self):
        return f"{self.reader} read {self.message_id} at {self.read_at}"
