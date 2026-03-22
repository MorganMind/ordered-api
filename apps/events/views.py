"""
Views for querying audit events.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from apps.core.permissions import IsAdmin
from .models import Event
from .serializers import EventSerializer


class EventViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only viewset for querying audit events.
    Admins only.
    """
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['event_type', 'entity_type', 'entity_id', 'actor']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter events by current tenant when user has tenant_id; superuser sees all."""
        user = self.request.user
        if not user.is_authenticated:
            return Event.objects.none()
        qs = Event.objects.select_related("tenant")
        if getattr(user, "is_superuser", False):
            return qs
        tid = getattr(user, "tenant_id", None)
        if tid:
            return qs.filter(tenant_id=tid)
        return Event.objects.none()
