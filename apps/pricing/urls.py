from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PriceSnapshotViewSet

router = DefaultRouter()
router.register(r"price-snapshots", PriceSnapshotViewSet, basename="price-snapshot")

urlpatterns = [
    path("", include(router.urls)),
]
