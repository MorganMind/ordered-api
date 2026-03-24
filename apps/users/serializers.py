from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserMeSerializer(serializers.ModelSerializer):
    """
    Current user profile for all roles (operator, technician, client).

    Use ``GET`` / ``PATCH`` ``/api/v1/users/me/``.
    """

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "avatar_url",
            "role",
            "tenant_id",
        ]
        read_only_fields = ["id", "email", "role", "tenant_id", "full_name"]
        extra_kwargs = {
            "avatar_url": {"allow_null": True, "required": False, "allow_blank": True},
        }

    def validate_avatar_url(self, value):
        if value is None:
            return None
        s = (value or "").strip()
        return s or None
