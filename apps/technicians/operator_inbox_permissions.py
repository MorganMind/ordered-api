"""
Permissions for operator (workspace) inbox — broader than ``IsTenantOperator``
when Django users use ``role=admin`` without ``is_tenant_operator``.
"""

from rest_framework.permissions import BasePermission

from apps.service_requests.permissions import IsTenantOperator
from apps.users.models import UserRole


class IsOperatorInboxUser(BasePermission):
    """
    Allows tenant operators, staff, superusers, or users whose ``role`` is
    admin / ``\"operator\"`` (same idea as ``MESSAGABLE_STAFF_ROLES`` in inbox).
    """

    def has_permission(self, request, view):
        if IsTenantOperator().has_permission(request, view):
            return True
        u = request.user
        if not u or not u.is_authenticated:
            return False
        role = getattr(u, "role", None)
        return role in (UserRole.ADMIN, "operator")
