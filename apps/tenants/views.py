"""
Tenant views - admin only.
"""
from rest_framework import viewsets, status
from rest_framework.response import Response
from apps.core.permissions import IsAdmin
from .models import Tenant
from .serializers import TenantSerializer


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants.
    Admin only - typically only super admins would manage multiple tenants.
    """
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        """
        Filter by optional user.tenant_id when present; superusers see all.
        """
        user = self.request.user
        if not user.is_authenticated:
            return Tenant.objects.none()
        if getattr(user, "is_superuser", False):
            return Tenant.objects.all()
        tid = getattr(user, "tenant_id", None)
        if tid:
            return Tenant.objects.filter(id=tid)
        return Tenant.objects.none()
