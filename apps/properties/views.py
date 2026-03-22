from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Property
from .serializers import PropertySerializer


class PropertyViewSet(viewsets.ModelViewSet):
    """Tenant-scoped properties (minimal model: label + tenant)."""

    permission_classes = [IsAuthenticated]
    serializer_class = PropertySerializer
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Property.objects.none()
        qs = Property.objects.select_related("tenant").order_by("-created_at")
        if getattr(user, "is_superuser", False):
            return qs
        tid = getattr(user, "tenant_id", None)
        if not tid:
            return Property.objects.none()
        return qs.filter(tenant_id=tid)

    def perform_create(self, serializer):
        tid = getattr(self.request.user, "tenant_id", None)
        serializer.save(tenant_id=tid)
