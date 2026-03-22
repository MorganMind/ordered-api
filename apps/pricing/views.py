from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsAdmin

from .models import PriceSnapshot
from .serializers import PriceSnapshotSerializer


class PriceSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PriceSnapshotSerializer
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return PriceSnapshot.objects.none()
        qs = PriceSnapshot.objects.all()
        if getattr(user, "is_superuser", False):
            return qs
        tid = getattr(user, "tenant_id", None)
        if tid:
            return qs.filter(tenant_id=tid)
        return PriceSnapshot.objects.none()
