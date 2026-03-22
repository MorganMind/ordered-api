from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookingViewSet, RecurringServiceSeriesViewSet

router = DefaultRouter()
router.register(
    r"recurring-series",
    RecurringServiceSeriesViewSet,
    basename="recurring-series",
)
router.register(
    r"bookings",
    BookingViewSet,
    basename="booking",
)

urlpatterns = [
    path("", include(router.urls)),
]
