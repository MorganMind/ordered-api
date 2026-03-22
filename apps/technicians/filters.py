"""
django-filter FilterSets for technician admin APIs.

``application_form`` avoids ModelChoiceFilter (unknown PK used to yield 400).

Invalid values (e.g. the literal string ``"undefined"`` from a bad client
route param) are treated as "no applications match" — HTTP 200 with an
empty page — instead of 400.
"""

import uuid

from django_filters import rest_framework as filters

from .models import TechnicianApplication


class TechnicianApplicationFilter(filters.FilterSet):
    application_form = filters.CharFilter(method="filter_application_form")
    application_form__isnull = filters.BooleanFilter(
        field_name="application_form",
        lookup_expr="isnull",
    )

    class Meta:
        model = TechnicianApplication
        fields = {
            "status": ["exact", "in"],
            "applicant_type": ["exact"],
            "source": ["exact"],
            "email": ["exact", "iexact"],
        }

    def filter_application_form(self, queryset, name, value):
        if value is None:
            return queryset
        s = str(value).strip()
        if not s:
            return queryset
        try:
            uid = uuid.UUID(s)
        except (ValueError, TypeError, AttributeError):
            return queryset.none()
        return queryset.filter(application_form_id=uid)
