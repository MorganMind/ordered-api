"""
Tenant views - admin only.
"""
from rest_framework import viewsets, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsAdmin, IsTenantWorkspaceStaff
from apps.users.services.avatar import AVATAR_MULTIPART_FIELD_NAMES, pick_avatar_upload_file
from .models import Tenant
from .serializers import (
    TenantMePatchSerializer,
    TenantNotificationSettingsSerializer,
    TenantSerializer,
)
from .services.logo import (
    save_tenant_logo_to_default_storage,
    try_delete_stored_tenant_logo_if_local,
)


class TenantMeLogoView(APIView):
    """
    ``POST`` multipart upload → ``tenant_logos/`` → sets ``Tenant.logo_url``.
    ``DELETE`` clears ``logo_url`` and best-effort removes local media file.
    """

    permission_classes = [IsAuthenticated, IsTenantWorkspaceStaff]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload, _used_key = pick_avatar_upload_file(request)
        if not upload:
            keys = ", ".join(f"'{k}'" for k in AVATAR_MULTIPART_FIELD_NAMES)
            return Response(
                {
                    "detail": f"Missing multipart file field. Use one of: {keys}.",
                    "accepted_field_names": list(AVATAR_MULTIPART_FIELD_NAMES),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(
                {"detail": "No tenant on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(pk=tid).first()
        if not tenant:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        old = tenant.logo_url
        url = save_tenant_logo_to_default_storage(
            tenant,
            upload,
            content_type=getattr(upload, "content_type", None),
            request=request,
        )
        try_delete_stored_tenant_logo_if_local(old)
        tenant.logo_url = url
        tenant.save(update_fields=["logo_url", "updated_at"])
        return Response({"logo_url": tenant.logo_url}, status=status.HTTP_200_OK)

    def delete(self, request):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(
                {"detail": "No tenant on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(pk=tid).first()
        if not tenant:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        old = tenant.logo_url
        try_delete_stored_tenant_logo_if_local(old)
        tenant.logo_url = None
        tenant.save(update_fields=["logo_url", "updated_at"])
        return Response({"logo_url": None}, status=status.HTTP_200_OK)


class TenantMeView(APIView):
    """
    GET/PATCH ``/api/v1/tenants/me/``

    Read or update the authenticated user's workspace tenant (``name``, external ``logo_url``).
    """

    permission_classes = [IsAuthenticated, IsTenantWorkspaceStaff]

    def get(self, request):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(
                {"detail": "No tenant on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(pk=tid).first()
        if not tenant:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(TenantSerializer(tenant).data)

    def patch(self, request):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(
                {"detail": "No tenant on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(pk=tid).first()
        if not tenant:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ser = TenantMePatchSerializer(
            tenant,
            data=request.data,
            partial=True,
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(TenantSerializer(tenant).data)


class TenantNotificationSettingsView(APIView):
    """
    GET/PATCH ``/api/v1/tenants/me/notification-settings/``

    Read or update ``operator_admin_email`` for the authenticated user's tenant.
    """

    permission_classes = [IsAuthenticated, IsTenantWorkspaceStaff]

    def get(self, request):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(
                {"detail": "No tenant on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(pk=tid).first()
        if not tenant:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ser = TenantNotificationSettingsSerializer(tenant)
        return Response(ser.data)

    def patch(self, request):
        tid = getattr(request.user, "tenant_id", None)
        if not tid:
            return Response(
                {"detail": "No tenant on this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        tenant = Tenant.objects.filter(pk=tid).first()
        if not tenant:
            return Response(
                {"detail": "Tenant not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        ser = TenantNotificationSettingsSerializer(
            tenant,
            data=request.data,
            partial=True,
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class TenantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tenants.
    Admin only - typically only super admins would manage multiple tenants.
    """

    # Only UUIDs match the detail route so slugs like ``me`` never hit Postgres as a UUID (500).
    lookup_value_regex = (
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    )

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
