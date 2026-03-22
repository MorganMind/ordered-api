"""Root URL configuration for ordered-api.

Mounted under ``/api/v1/`` (plus ``/admin/``).

Not mounted yet (no ``urls.py`` in tree): ``apps.briefs``.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("api_auth.urls")),
    path("api/v1/", include("user.urls")),
    path("api/v1/", include("files.urls")),
    path("api/v1/", include("tag.urls")),
    path("api/v1/", include("transcription.urls")),
    path("api/v1/", include("invite.urls")),
    path("api/v1/", include("tasks.urls")),
    path("api/v1/tenants/", include("apps.tenants.urls")),
    path("api/v1/", include("apps.properties.urls")),
    path("api/v1/", include("apps.events.urls")),
    path("api/v1/", include("apps.jobs.urls")),
    path("api/v1/", include("apps.bookings.urls")),
    path("api/v1/", include("apps.service_requests.urls")),
    path("api/v1/", include("apps.pricing.urls")),
    path("api/v1/", include("apps.intake.urls")),
    path("api/v1/", include("apps.technicians.urls")),
]
