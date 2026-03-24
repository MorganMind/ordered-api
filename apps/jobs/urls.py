from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .operator_copilot_views import OperatorCopilotChatView
from .operator_dashboard_views import OperatorDashboardView
from .views import JobViewSet

router = DefaultRouter()
router.register(r"jobs", JobViewSet, basename="job")

urlpatterns = [
    path("operator/dashboard/", OperatorDashboardView.as_view(), name="operator-dashboard"),
    path("operator/copilot/chat/", OperatorCopilotChatView.as_view(), name="operator-copilot-chat"),
    path("", include(router.urls)),
]
