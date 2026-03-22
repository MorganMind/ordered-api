from rest_framework import serializers

from .models import Property


class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = ["id", "tenant", "label", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]
