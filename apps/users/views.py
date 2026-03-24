from __future__ import annotations

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import UserMeSerializer
from .services.avatar import (
    AVATAR_MULTIPART_FIELD_NAMES,
    pick_avatar_upload_file,
    save_avatar_to_default_storage,
    try_delete_stored_avatar_if_local,
)


class UserMeView(APIView):
    """
    Single profile surface for **every** authenticated workspace user.

    ``GET`` / ``PATCH`` ``/api/v1/users/me/`` — same code path for client, technician, and operator.
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get(self, request):
        return Response(UserMeSerializer(request.user).data)

    def patch(self, request):
        ser = UserMeSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(UserMeSerializer(request.user).data)


class UserMeAvatarUploadView(APIView):
    """
    Multipart image upload → default storage → updates ``User.avatar_url``.

    ``POST`` ``/api/v1/users/me/avatar/`` — multipart file under ``file`` (preferred) or
    ``avatar`` / ``image`` / ``photo`` (common mobile clients).
    ``DELETE`` ``/api/v1/users/me/avatar/`` — clears ``avatar_url`` (and tries to delete local file).
    """

    permission_classes = [IsAuthenticated]
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
        user = request.user
        old = user.avatar_url
        url = save_avatar_to_default_storage(
            user,
            upload,
            content_type=getattr(upload, "content_type", None),
            request=request,
        )
        try_delete_stored_avatar_if_local(old)
        user.avatar_url = url
        user.save(update_fields=["avatar_url", "updated_at"])
        return Response(
            {"avatar_url": user.avatar_url},
            status=status.HTTP_200_OK,
        )

    def delete(self, request):
        user = request.user
        old = user.avatar_url
        try_delete_stored_avatar_if_local(old)
        user.avatar_url = None
        user.save(update_fields=["avatar_url", "updated_at"])
        return Response(
            {"avatar_url": None},
            status=status.HTTP_200_OK,
        )
