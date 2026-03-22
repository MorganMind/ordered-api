"""Minimal URLconf for Django tests (avoids optional app imports in root urls)."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("apps.jobs.urls")),
    path("api/v1/", include("apps.properties.urls")),
    path("api/v1/", include("apps.service_requests.urls")),
    path("api/v1/", include("apps.pricing.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/tenants/", include("apps.tenants.urls")),
]
