"""
DRF permission classes used by tenants/events viewsets.

Uses Django's auth User (AUTH_USER_MODEL). Extend when you add tenant_id on a custom user.
"""

from rest_framework.permissions import BasePermission

from apps.users.models import UserRole


class IsAdmin(BasePermission):
    """Staff/superuser — adjust when you add a dedicated admin role."""

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and (getattr(u, "is_staff", False) or getattr(u, "is_superuser", False))
        )


class IsTechnician(BasePermission):
    """Logged-in user whose Django ``User.role`` is technician."""

    def has_permission(self, request, view):
        u = request.user
        return bool(
            u
            and u.is_authenticated
            and getattr(u, "role", None) == UserRole.TECHNICIAN
        )


class IsTenantWorkspaceStaff(BasePermission):
    """
    Workspace operators: Django staff/superuser, ``is_tenant_operator``, or
    ``role`` admin / ``\"operator\"`` (aligned with operator inbox / service requests).
    """

    def has_permission(self, request, view):
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
            return True
        if getattr(u, "is_tenant_operator", False):
            return True
        role = getattr(u, "role", None)
        return role in (UserRole.ADMIN, "operator")
