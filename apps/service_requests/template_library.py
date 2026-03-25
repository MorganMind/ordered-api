from __future__ import annotations

from dataclasses import dataclass

from .models import ServiceType


@dataclass(frozen=True)
class ServiceOfferingTemplate:
    key: str
    name: str
    description: str
    reporting_category: str
    suggested_skill_keys: tuple[str, ...]


SERVICE_OFFERING_TEMPLATES: tuple[ServiceOfferingTemplate, ...] = (
    ServiceOfferingTemplate(
        key="cleaning_standard",
        name="Standard Home Cleaning",
        description=(
            "Regular home cleaning to keep things fresh — kitchens, baths, and "
            "main living areas."
        ),
        reporting_category=ServiceType.STANDARD_CLEANING,
        suggested_skill_keys=(
            "standard_cleaning",
            "bathroom_cleaning",
            "kitchen_cleaning",
            "dusting",
        ),
    ),
    ServiceOfferingTemplate(
        key="cleaning_deep",
        name="Deep Cleaning",
        description=(
            "A thorough clean for when your home needs extra attention — "
            "corners, buildup, and the easy-to-miss spots."
        ),
        reporting_category=ServiceType.DEEP_CLEAN,
        suggested_skill_keys=(
            "deep_cleaning",
            "bathroom_cleaning",
            "kitchen_cleaning",
            "appliance_detailing",
        ),
    ),
    ServiceOfferingTemplate(
        key="cleaning_move_in_out",
        name="Move-In / Move-Out Cleaning",
        description=(
            "Move-in or move-out cleaning so the place is ready for the next chapter."
        ),
        reporting_category=ServiceType.MOVE_IN_OUT,
        suggested_skill_keys=(
            "move_in_out_cleaning",
            "deep_cleaning",
            "inside_cabinets",
            "appliance_detailing",
        ),
    ),
    ServiceOfferingTemplate(
        key="organizing_reset",
        name="Home Organizing Reset",
        description=(
            "Help sorting and organizing closets, pantries, and busy spaces "
            "so they’re easier to keep up."
        ),
        reporting_category=ServiceType.ORGANIZING,
        suggested_skill_keys=(
            "organizing",
            "decluttering",
            "closet_organization",
        ),
    ),
)


def list_service_offering_templates() -> list[dict]:
    return [
        {
            "key": t.key,
            "name": t.name,
            "description": t.description,
            "reporting_category": t.reporting_category,
            "suggested_skill_keys": list(t.suggested_skill_keys),
        }
        for t in SERVICE_OFFERING_TEMPLATES
    ]


def get_service_offering_template(template_key: str) -> ServiceOfferingTemplate | None:
    for template in SERVICE_OFFERING_TEMPLATES:
        if template.key == template_key:
            return template
    return None
