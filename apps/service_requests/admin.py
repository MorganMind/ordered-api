from django.contrib import admin

from .models import ServiceOffering, ServiceOfferingSkill, ServiceRequest


class ServiceOfferingSkillInline(admin.TabularInline):
    model = ServiceOfferingSkill
    extra = 0
    raw_id_fields = ("skill",)


@admin.register(ServiceOffering)
class ServiceOfferingAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "tenant",
        "is_active",
        "sort_order",
        "reporting_category",
        "created_at",
    )
    list_filter = ("is_active", "tenant", "reporting_category")
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ServiceOfferingSkillInline]


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "status",
        "service_type",
        "contact_name",
        "contact_email",
        "source",
        "created_at",
    )
    list_filter = ("status", "service_type", "source", "tenant")
    search_fields = (
        "contact_name",
        "contact_email",
        "contact_phone",
        "address_raw",
    )
    readonly_fields = (
        "id",
        "tenant",
        "client",
        "source",
        "latest_price_snapshot",
        "converted_job",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    "id",
                    "tenant",
                    "client",
                    "status",
                    "source",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Contact",
            {"fields": ("contact_name", "contact_phone", "contact_email")},
        ),
        (
            "Address",
            {"fields": ("address_raw", "address_normalized")},
        ),
        (
            "Home Attributes",
            {"fields": ("property_ref", "square_feet", "bedrooms", "bathrooms")},
        ),
        (
            "Service Details",
            {
                "fields": (
                    "service_type",
                    "service_offering",
                    "timing_preference",
                    "notes",
                    "media_refs",
                )
            },
        ),
        (
            "Operator",
            {
                "fields": ("internal_operator_notes",),
                "classes": ("collapse",),
            },
        ),
        (
            "Linked Objects",
            {
                "fields": ("latest_price_snapshot", "converted_job"),
                "classes": ("collapse",),
            },
        ),
    )
