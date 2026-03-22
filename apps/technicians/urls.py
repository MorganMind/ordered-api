"""
Technician URL routes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.technicians.views import (
    ApplicationFormPublicSubmitView,
    ApplicationFormViewSet,
    OnboardingRequirementsView,
    ServiceRegionListView,
    TechnicianAdminViewSet,
    TechnicianApplicationViewSet,
    TechnicianMeView,
    TechnicianSkillsListView,
    TechnicianSubmitView,
)

# Admin router
admin_router = DefaultRouter()
admin_router.register(
    r"technicians",
    TechnicianAdminViewSet,
    basename="admin-technician",
)
admin_router.register(
    r"technician-applications",
    TechnicianApplicationViewSet,
    basename="admin-technician-application",
)
admin_router.register(
    r"application-forms",
    ApplicationFormViewSet,
    basename="admin-application-form",
)

urlpatterns = [
    # Technician self-service
    path("technicians/me/", TechnicianMeView.as_view(), name="technician-me"),
    path("technicians/me/submit/", TechnicianSubmitView.as_view(), name="technician-submit"),

    # Reference data
    path("technicians/service-regions/", ServiceRegionListView.as_view(), name="service-regions"),
    path("technicians/skills/", TechnicianSkillsListView.as_view(), name="technician-skills"),
    path("technicians/onboarding-requirements/", OnboardingRequirementsView.as_view(), name="onboarding-requirements"),

    path(
        "forms/<uuid:form_id>/apply/",
        ApplicationFormPublicSubmitView.as_view(),
        name="public-form-apply",
    ),

    # Admin routes
    path("admin/", include(admin_router.urls)),
]
