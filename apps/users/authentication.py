"""
DRF authentication: Supabase JWT Bearer → ``apps.users.User``.
"""

import jwt
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from common.decorators import _decode_supabase_jwt


class SupabaseAuthentication(BaseAuthentication):
    """Validate Supabase access token and resolve the Django ``User`` row."""

    def authenticate(self, request):
        header = request.headers.get("Authorization")
        if not header or not header.startswith("Bearer "):
            return None

        raw = header.split(" ", 1)[1].strip()
        if not raw:
            return None

        try:
            claims = _decode_supabase_jwt(raw)
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationFailed("Token has expired") from exc
        except (jwt.InvalidTokenError, Exception) as exc:
            raise AuthenticationFailed(f"Invalid token: {exc}") from exc

        request.jwt_claims = claims
        request.user_id = claims.get("sub")
        request.user_email = (claims.get("email") or "").strip()

        User = get_user_model()
        uid = request.user_id
        email = request.user_email
        user = None
        if uid:
            user = User.objects.filter(supabase_uid=uid).first()
        if user is None and email:
            user = User.objects.filter(email__iexact=email).first()
        if user is None:
            raise AuthenticationFailed("User is not provisioned in this workspace")
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled")

        return (user, None)
