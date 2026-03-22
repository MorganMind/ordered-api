from __future__ import annotations

from typing import Any, Dict

from django.db import transaction

from apps.pricing.models import PriceSnapshot
from apps.service_requests.models import ServiceRequest


def service_request_pricing_inputs(sr: ServiceRequest) -> Dict[str, Any]:
    return {
        "service_type": sr.service_type,
        "square_feet": sr.square_feet,
        "bedrooms": sr.bedrooms,
        "bathrooms": float(sr.bathrooms) if sr.bathrooms is not None else None,
        "address_raw": sr.address_raw,
        "timing_preference": sr.timing_preference,
        "notes": sr.notes,
        "property_id": str(sr.property_ref_id) if sr.property_ref_id else None,
    }


def _compute_line_items(inputs: Dict[str, Any]) -> tuple[list, int, int]:
    base = 9900
    sq = inputs.get("square_feet") or 0
    extra = min(50000, max(0, (sq - 1500) // 100 * 500))
    total = base + extra
    lines = [
        {"code": "base_visit", "label": "Base visit", "amount_cents": base},
        {"code": "sqft_adjustment", "label": "Size adjustment", "amount_cents": extra},
    ]
    return lines, total, total


@transaction.atomic
def create_price_snapshot_from_service_request(sr: ServiceRequest) -> PriceSnapshot:
    inputs = service_request_pricing_inputs(sr)
    lines, subtotal, total = _compute_line_items(inputs)
    snap = PriceSnapshot.objects.create(
        tenant_id=sr.tenant_id,
        service_request=sr,
        currency="USD",
        total_cents=total,
        subtotal_cents=subtotal,
        line_items=lines,
        inputs_used=inputs,
        pricing_engine_version="v1-placeholder",
    )
    sr.latest_price_snapshot = snap
    sr.save(update_fields=["latest_price_snapshot", "updated_at"])
    return snap
