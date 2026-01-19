"""
Django admin configuration for intake sessions.
"""
from django.contrib import admin
from apps.intake.models import IntakeSession, IntakeMessage, UpdateProposal


class IntakeMessageInline(admin.TabularInline):
    model = IntakeMessage
    extra = 0
    readonly_fields = ["id", "role", "content", "sequence_number", "created_at"]
    ordering = ["sequence_number"]
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


class UpdateProposalInline(admin.TabularInline):
    model = UpdateProposal
    extra = 0
    readonly_fields = ["id", "proposal_type", "status", "summary", "created_at"]
    ordering = ["-created_at"]
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(IntakeSession)
class IntakeSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "client",
        "status",
        "message_count",
        "property",
        "created_at",
        "last_message_at",
    ]
    list_filter = ["status", "tenant", "created_at"]
    search_fields = ["client__email", "title", "property__address"]
    readonly_fields = ["id", "created_at", "updated_at", "message_count"]
    raw_id_fields = ["client", "property", "tenant"]
    inlines = [IntakeMessageInline, UpdateProposalInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "client", "property", "tenant"
        )


@admin.register(IntakeMessage)
class IntakeMessageAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session",
        "role",
        "sequence_number",
        "content_preview",
        "created_at",
    ]
    list_filter = ["role", "session__tenant", "created_at"]
    search_fields = ["content", "session__client__email"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["session", "tenant", "in_reply_to"]
    
    def content_preview(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    content_preview.short_description = "Content"


@admin.register(UpdateProposal)
class UpdateProposalAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "session",
        "proposal_type",
        "status",
        "summary",
        "created_at",
    ]
    list_filter = ["proposal_type", "status", "session__tenant", "created_at"]
    search_fields = ["summary", "session__client__email"]
    readonly_fields = [
        "id", "created_at", "updated_at", "content_hash",
        "proposed_data", "source_message"
    ]
    raw_id_fields = ["session", "tenant", "source_message", "reviewed_by"]
