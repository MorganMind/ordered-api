from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsTenantMember(BasePermission):
    """
    Allows access to any authenticated user who belongs to a tenant.

    Minimum bar for any service-request endpoint; does not distinguish operators
    from regular clients.
    """

    def has_permission(self, request, view) -> bool:
        u = request.user
        return bool(
            u and u.is_authenticated and getattr(u, "tenant_id", None)
        )


class IsTenantOperator(BasePermission):
    """
    Tenant operators, staff, and superusers.

    Operator means ``is_tenant_operator=True`` on the user profile.
    """

    def has_permission(self, request, view) -> bool:
        u = request.user
        if not u or not u.is_authenticated:
            return False
        if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
            return True
        return bool(getattr(u, "is_tenant_operator", False))


class ServiceRequestObjectPermission(BasePermission):
    """
    Object-level rules for ServiceRequest.

    - Staff / superuser: full access.
    - Tenant operator: any request in their tenant.
    - Client: read-only for their own requests in their tenant (same tenant_id
      and client_id match).
    """

    def has_object_permission(self, request, view, obj) -> bool:
        u = request.user

        if getattr(u, "is_staff", False) or getattr(u, "is_superuser", False):
            return True

        if getattr(u, "is_tenant_operator", False):
            return obj.tenant_id == getattr(u, "tenant_id", None)

        if request.method in SAFE_METHODS:
            return (
                obj.client_id == u.id
                and obj.tenant_id == getattr(u, "tenant_id", None)
            )

        return False
