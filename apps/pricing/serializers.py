from rest_framework import serializers

from .models import PriceSnapshot


class PriceSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = PriceSnapshot
        fields = [
            "id",
            "tenant",
            "service_request",
            "currency",
            "total_cents",
            "subtotal_cents",
            "line_items",
            "inputs_used",
            "pricing_engine_version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
