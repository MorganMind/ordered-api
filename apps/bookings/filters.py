import django_filters

from .models import Booking


class BookingFilter(django_filters.FilterSet):
    client_name = django_filters.CharFilter(field_name="client_name", lookup_expr="icontains")
    start_date = django_filters.DateFilter(field_name="scheduled_date", lookup_expr="gte")
    end_date = django_filters.DateFilter(field_name="scheduled_date", lookup_expr="lte")

    class Meta:
        model = Booking
        fields = ["status"]
