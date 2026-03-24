"""
Tenant URL routes.

Note: Public technician application lived here with TechnicianApplicationPublicSubmitView;
restore that route when `apps.technicians` and `apps.users` are installed.
"""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TenantMeLogoView, TenantMeView, TenantNotificationSettingsView, TenantViewSet

router = DefaultRouter()
router.register(r"", TenantViewSet, basename="tenant")

urlpatterns = [
    path(
        "me/notification-settings/",
        TenantNotificationSettingsView.as_view(),
        name="tenant-notification-settings",
    ),
    path(
        "me/logo/",
        TenantMeLogoView.as_view(),
        name="tenant-me-logo",
    ),
    path(
        "me/",
        TenantMeView.as_view(),
        name="tenant-me",
    ),
    path("", include(router.urls)),
]
