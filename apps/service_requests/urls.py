from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ServiceOfferingViewSet, ServiceRequestViewSet

router = DefaultRouter()
router.register(r"service-requests", ServiceRequestViewSet, basename="service-request")
router.register(
    r"service-offerings",
    ServiceOfferingViewSet,
    basename="service-offering",
)

urlpatterns = [
    path("", include(router.urls)),
]
