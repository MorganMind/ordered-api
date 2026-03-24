from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "slug",
        "status",
        "email",
        "operator_admin_email",
        "created_at",
    ]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "slug", "email", "operator_admin_email"]
    readonly_fields = ["id", "created_at", "updated_at"]
