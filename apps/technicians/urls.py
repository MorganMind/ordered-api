"""
Technician URL routes.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from apps.technicians.inbox_views import (
    TechnicianInboxMarkReadView,
    TechnicianInboxMessageListCreateView,
    TechnicianInboxOperatorRecipientsView,
    TechnicianInboxStartThreadView,
    TechnicianInboxThreadDetailView,
    TechnicianInboxThreadListView,
)
from apps.technicians.operator_inbox_views import (
    OperatorInboxMarkReadView,
    OperatorInboxMessageListCreateView,
    OperatorInboxStartThreadView,
    OperatorInboxTechnicianRecipientsView,
    OperatorInboxThreadDetailView,
    OperatorInboxThreadListView,
)
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
from apps.users.admin_views import ClientAdminViewSet

# Admin router
admin_router = DefaultRouter()
admin_router.register(
    r"clients",
    ClientAdminViewSet,
    basename="admin-client",
)
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
    path(
        "operator/inbox/threads/",
        OperatorInboxThreadListView.as_view(),
        name="operator-inbox-threads",
    ),
    path(
        "operator/inbox/threads/start/",
        OperatorInboxStartThreadView.as_view(),
        name="operator-inbox-start-thread",
    ),
    path(
        "operator/inbox/technicians/",
        OperatorInboxTechnicianRecipientsView.as_view(),
        name="operator-inbox-technicians",
    ),
    path(
        "operator/inbox/threads/<uuid:thread_id>/",
        OperatorInboxThreadDetailView.as_view(),
        name="operator-inbox-thread-detail",
    ),
    path(
        "operator/inbox/threads/<uuid:thread_id>/messages/",
        OperatorInboxMessageListCreateView.as_view(),
        name="operator-inbox-messages",
    ),
    path(
        "operator/inbox/threads/<uuid:thread_id>/mark-read/",
        OperatorInboxMarkReadView.as_view(),
        name="operator-inbox-mark-read",
    ),
    path(
        "technicians/me/inbox/threads/",
        TechnicianInboxThreadListView.as_view(),
        name="technician-inbox-threads",
    ),
    path(
        "technicians/me/inbox/threads/start/",
        TechnicianInboxStartThreadView.as_view(),
        name="technician-inbox-start-thread",
    ),
    path(
        "technicians/me/inbox/operators/",
        TechnicianInboxOperatorRecipientsView.as_view(),
        name="technician-inbox-operators",
    ),
    path(
        "technicians/me/inbox/threads/<uuid:thread_id>/",
        TechnicianInboxThreadDetailView.as_view(),
        name="technician-inbox-thread-detail",
    ),
    path(
        "technicians/me/inbox/threads/<uuid:thread_id>/messages/",
        TechnicianInboxMessageListCreateView.as_view(),
        name="technician-inbox-messages",
    ),
    path(
        "technicians/me/inbox/threads/<uuid:thread_id>/mark-read/",
        TechnicianInboxMarkReadView.as_view(),
        name="technician-inbox-mark-read",
    ),
    # Technician self-service
    path("technicians/me/", TechnicianMeView.as_view(), name="technician-me"),
    path("technicians/me/submit/", TechnicianSubmitView.as_view(), name="technician-submit"),

    # Reference data
    path("technicians/service-regions/", ServiceRegionListView.as_view(), name="service-regions"),
    path("technicians/skills/", TechnicianSkillsListView.as_view(), name="technician-skills"),
    path("technicians/onboarding-requirements/", OnboardingRequirementsView.as_view(), name="onboarding-requirements"),

    path(
        "forms/<str:form_ref>/apply/",
        ApplicationFormPublicSubmitView.as_view(),
        name="public-form-apply",
    ),

    # Admin routes
    path("admin/", include(admin_router.urls)),
]
