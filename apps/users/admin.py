from django.contrib import admin

from apps.users.models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    ordering = ("email",)
    list_display = ("email", "tenant", "role", "status", "is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name", "supabase_uid")
    list_filter = ("role", "status", "is_staff", "is_active")
    filter_horizontal = ("groups", "user_permissions", "skills")
    readonly_fields = ("created_at", "updated_at", "last_login", "password")
