from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ServiceRequestViewSet

router = DefaultRouter()
router.register(r"service-requests", ServiceRequestViewSet, basename="service-request")

urlpatterns = [
    path("", include(router.urls)),
]
