from django.contrib import admin

from .models import PriceSnapshot


@admin.register(PriceSnapshot)
class PriceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "service_request", "total_cents", "created_at")
