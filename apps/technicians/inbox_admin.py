from django.contrib import admin

from apps.technicians.inbox_models import (
    TechnicianInboxMessage,
    TechnicianInboxMessageReceipt,
    TechnicianInboxThread,
)


class TechnicianInboxMessageInline(admin.TabularInline):
    model = TechnicianInboxMessage
    extra = 0
    readonly_fields = (
        "id",
        "sender_type",
        "sender_user",
        "sender_name",
        "body",
        "job",
        "created_at",
    )
    ordering = ("created_at",)

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TechnicianInboxThread)
class TechnicianInboxThreadAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "thread_type",
        "technician",
        "participant_name",
        "is_pinned",
        "last_activity_at",
        "tenant",
    )
    list_filter = (
        "thread_type",
        "is_pinned",
        "tenant",
    )
    search_fields = (
        "title",
        "participant_name",
        "technician__email",
        "technician__first_name",
        "technician__last_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = (
        "technician",
        "job",
        "operator_contact",
        "client_contact",
        "tenant",
    )
    inlines = [TechnicianInboxMessageInline]
    ordering = ("-last_activity_at",)


@admin.register(TechnicianInboxMessage)
class TechnicianInboxMessageAdmin(admin.ModelAdmin):
    list_display = (
        "short_body",
        "sender_type",
        "sender_name",
        "thread",
        "created_at",
        "tenant",
    )
    list_filter = (
        "sender_type",
        "tenant",
    )
    search_fields = (
        "body",
        "sender_name",
        "thread__title",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    raw_id_fields = ("thread", "sender_user", "job", "tenant")
    ordering = ("-created_at",)

    @admin.display(description="Body")
    def short_body(self, obj):
        if len(obj.body) > 80:
            return obj.body[:80] + "…"
        return obj.body


@admin.register(TechnicianInboxMessageReceipt)
class TechnicianInboxMessageReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "reader",
        "read_at",
        "tenant",
    )
    list_filter = ("tenant",)
    search_fields = (
        "reader__email",
        "message__body",
    )
    readonly_fields = ("id", "read_at", "created_at", "updated_at")
    raw_id_fields = ("message", "reader", "tenant")
    ordering = ("-read_at",)
