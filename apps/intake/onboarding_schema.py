"""
Onboarding schema definitions for different property types.

Defines what information needs to be collected during intake,
organized by property type and category.
"""
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


class PropertyTypeSchema(str, Enum):
    """Supported property types for onboarding."""
    SINGLE_FAMILY = "single_family"
    CONDO = "condo"
    APARTMENT = "apartment"
    TOWNHOUSE = "townhouse"
    OFFICE = "office"
    OTHER = "other"


class OnboardingCategory(str, Enum):
    """Categories of information to collect."""
    PROPERTY_BASICS = "property_basics"
    ROOMS = "rooms"
    SURFACES = "surfaces"
    PREFERENCES = "preferences"
    ACCESS = "access"
    PRIORITIES = "priorities"
    SPECIAL_INSTRUCTIONS = "special_instructions"


class FieldPriority(str, Enum):
    """Priority level for onboarding fields."""
    REQUIRED = "required"  # Must have before completing onboarding
    IMPORTANT = "important"  # Should ask about, but can proceed without
    OPTIONAL = "optional"  # Nice to have, ask if conversation flows there


@dataclass
class OnboardingField:
    """Definition of a single field to collect."""
    key: str
    label: str
    description: str
    priority: FieldPriority
    category: OnboardingCategory
    data_type: str = "text"  # text, number, boolean, list, enum
    enum_options: Optional[List[str]] = None
    example_values: Optional[List[str]] = None
    follow_up_questions: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "priority": self.priority.value,
            "category": self.category.value,
            "data_type": self.data_type,
            "enum_options": self.enum_options,
            "example_values": self.example_values,
        }


@dataclass
class RoomTemplate:
    """Template for a room type with expected surfaces."""
    room_type: str
    typical_surfaces: List[str]
    common_notes: List[str]


# Standard room templates
ROOM_TEMPLATES: Dict[str, RoomTemplate] = {
    "kitchen": RoomTemplate(
        room_type="kitchen",
        typical_surfaces=["countertops", "stovetop", "sink", "floors", "cabinets", "appliances"],
        common_notes=["cleaning frequency", "product preferences", "areas to avoid"]
    ),
    "bathroom": RoomTemplate(
        room_type="bathroom",
        typical_surfaces=["toilet", "shower/tub", "sink", "mirrors", "floors", "counters"],
        common_notes=["products to use/avoid", "special fixtures"]
    ),
    "bedroom": RoomTemplate(
        room_type="bedroom",
        typical_surfaces=["floors", "furniture", "windows"],
        common_notes=["bed making preferences", "closet access", "personal items"]
    ),
    "living_room": RoomTemplate(
        room_type="living_room",
        typical_surfaces=["floors", "furniture", "windows", "electronics"],
        common_notes=["furniture care", "electronics handling"]
    ),
    "dining_room": RoomTemplate(
        room_type="dining_room",
        typical_surfaces=["floors", "table", "chairs", "windows"],
        common_notes=["table surface type", "chair care"]
    ),
    "office": RoomTemplate(
        room_type="office",
        typical_surfaces=["desk", "floors", "electronics", "shelves"],
        common_notes=["paper handling", "electronics", "do not disturb items"]
    ),
    "laundry": RoomTemplate(
        room_type="laundry",
        typical_surfaces=["floors", "appliances", "counters"],
        common_notes=["appliance care", "product storage"]
    ),
    "garage": RoomTemplate(
        room_type="garage",
        typical_surfaces=["floors"],
        common_notes=["scope of cleaning", "vehicle presence"]
    ),
    "outdoor": RoomTemplate(
        room_type="outdoor",
        typical_surfaces=["patio", "furniture", "grill"],
        common_notes=["scope", "seasonal items"]
    ),
}


def get_onboarding_schema(property_type: str) -> Dict[str, List[OnboardingField]]:
    """
    Get the onboarding schema for a property type.
    
    Returns fields organized by category.
    """
    # Base schema applies to all property types
    base_schema = {
        OnboardingCategory.PROPERTY_BASICS.value: [
            OnboardingField(
                key="address",
                label="Property Address",
                description="Full address of the property",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.PROPERTY_BASICS,
            ),
            OnboardingField(
                key="property_type",
                label="Property Type",
                description="Type of property (house, condo, apartment, etc.)",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.PROPERTY_BASICS,
                data_type="enum",
                enum_options=["single_family", "condo", "apartment", "townhouse", "office", "other"],
            ),
            OnboardingField(
                key="square_feet",
                label="Square Footage",
                description="Approximate size of the home",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.PROPERTY_BASICS,
                data_type="number",
                example_values=["1200", "2500", "3500"],
            ),
            OnboardingField(
                key="num_bedrooms",
                label="Number of Bedrooms",
                description="How many bedrooms",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.PROPERTY_BASICS,
                data_type="number",
            ),
            OnboardingField(
                key="num_bathrooms",
                label="Number of Bathrooms",
                description="How many bathrooms (can be partial like 2.5)",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.PROPERTY_BASICS,
                data_type="number",
            ),
            OnboardingField(
                key="num_floors",
                label="Number of Floors/Levels",
                description="How many floors or levels in the home",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.PROPERTY_BASICS,
                data_type="number",
            ),
        ],
        OnboardingCategory.ROOMS.value: [
            OnboardingField(
                key="room_list",
                label="Rooms to Service",
                description="List of rooms that should be cleaned/serviced",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.ROOMS,
                data_type="list",
                example_values=["kitchen", "living room", "master bedroom", "master bath"],
            ),
            OnboardingField(
                key="rooms_to_skip",
                label="Rooms to Skip",
                description="Any rooms that should not be entered or cleaned",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.ROOMS,
                data_type="list",
            ),
        ],
        OnboardingCategory.SURFACES.value: [
            OnboardingField(
                key="floor_types",
                label="Floor Types",
                description="Types of flooring in the home",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SURFACES,
                data_type="list",
                example_values=["hardwood", "tile", "carpet", "laminate", "vinyl"],
            ),
            OnboardingField(
                key="countertop_types",
                label="Countertop Types",
                description="Types of countertop surfaces",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SURFACES,
                data_type="list",
                example_values=["granite", "quartz", "marble", "laminate", "butcher block"],
            ),
            OnboardingField(
                key="special_surfaces",
                label="Special Surfaces",
                description="Any surfaces requiring special care",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SURFACES,
            ),
        ],
        OnboardingCategory.PREFERENCES.value: [
            OnboardingField(
                key="products_to_use",
                label="Preferred Products",
                description="Specific cleaning products the client wants used",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.PREFERENCES,
                data_type="list",
            ),
            OnboardingField(
                key="products_to_avoid",
                label="Products to Avoid",
                description="Products that should NOT be used",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.PREFERENCES,
                data_type="list",
            ),
            OnboardingField(
                key="scent_preferences",
                label="Scent Preferences",
                description="Preferences about scents (unscented, specific scents, etc.)",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.PREFERENCES,
            ),
            OnboardingField(
                key="eco_friendly",
                label="Eco-Friendly Products",
                description="Whether to use eco-friendly/green products",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.PREFERENCES,
                data_type="boolean",
            ),
        ],
        OnboardingCategory.ACCESS.value: [
            OnboardingField(
                key="access_method",
                label="Access Method",
                description="How technicians will access the property",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.ACCESS,
                data_type="enum",
                enum_options=["lockbox", "door_code", "hidden_key", "meet_in_person", "doorman", "other"],
            ),
            OnboardingField(
                key="access_details",
                label="Access Details",
                description="Specific access instructions (codes, lockbox location, etc.)",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.ACCESS,
            ),
            OnboardingField(
                key="parking_instructions",
                label="Parking Instructions",
                description="Where technicians should park",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.ACCESS,
            ),
            OnboardingField(
                key="gate_code",
                label="Gate Code",
                description="Code for community/building gate if applicable",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.ACCESS,
            ),
            OnboardingField(
                key="alarm_info",
                label="Alarm Information",
                description="Alarm code and instructions",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.ACCESS,
            ),
        ],
        OnboardingCategory.PRIORITIES.value: [
            OnboardingField(
                key="high_priority_areas",
                label="High Priority Areas",
                description="Areas that are most important to the client",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.PRIORITIES,
                data_type="list",
            ),
            OnboardingField(
                key="pain_points",
                label="Pain Points",
                description="Specific issues or areas that have been problems",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.PRIORITIES,
                data_type="list",
            ),
        ],
        OnboardingCategory.SPECIAL_INSTRUCTIONS.value: [
            OnboardingField(
                key="pets",
                label="Pets",
                description="Information about pets in the home",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
                follow_up_questions=["type", "name", "temperament", "containment during service"],
            ),
            OnboardingField(
                key="allergies",
                label="Allergies/Sensitivities",
                description="Any allergies or chemical sensitivities",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
            ),
            OnboardingField(
                key="do_rules",
                label="Do's",
                description="Specific things technicians should always do",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
                data_type="list",
            ),
            OnboardingField(
                key="dont_rules",
                label="Don'ts",
                description="Specific things technicians should never do",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
                data_type="list",
            ),
            OnboardingField(
                key="fragile_items",
                label="Fragile/Valuable Items",
                description="Items requiring special care or to avoid",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
            ),
            OnboardingField(
                key="people_home",
                label="People Home During Service",
                description="Whether anyone will be home during service",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
            ),
        ],
    }
    
    # Property-type-specific additions
    if property_type in [PropertyTypeSchema.CONDO.value, PropertyTypeSchema.APARTMENT.value]:
        base_schema[OnboardingCategory.ACCESS.value].extend([
            OnboardingField(
                key="building_name",
                label="Building Name",
                description="Name of the building/complex",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.ACCESS,
            ),
            OnboardingField(
                key="unit_number",
                label="Unit Number",
                description="Apartment/condo unit number",
                priority=FieldPriority.REQUIRED,
                category=OnboardingCategory.ACCESS,
            ),
            OnboardingField(
                key="concierge_info",
                label="Concierge/Doorman Info",
                description="Information about building staff",
                priority=FieldPriority.OPTIONAL,
                category=OnboardingCategory.ACCESS,
            ),
        ])
    
    if property_type == PropertyTypeSchema.OFFICE.value:
        base_schema[OnboardingCategory.SPECIAL_INSTRUCTIONS.value].extend([
            OnboardingField(
                key="after_hours_access",
                label="After Hours Access",
                description="Instructions for after-hours access",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
            ),
            OnboardingField(
                key="restricted_areas",
                label="Restricted Areas",
                description="Areas that are off-limits",
                priority=FieldPriority.IMPORTANT,
                category=OnboardingCategory.SPECIAL_INSTRUCTIONS,
                data_type="list",
            ),
        ])
    
    return base_schema


def get_flat_field_list(property_type: str) -> List[OnboardingField]:
    """Get all fields as a flat list for a property type."""
    schema = get_onboarding_schema(property_type)
    fields = []
    for category_fields in schema.values():
        fields.extend(category_fields)
    return fields


def get_required_fields(property_type: str) -> List[OnboardingField]:
    """Get only required fields for a property type."""
    return [
        f for f in get_flat_field_list(property_type) 
        if f.priority == FieldPriority.REQUIRED
    ]


def get_important_fields(property_type: str) -> List[OnboardingField]:
    """Get required + important fields for a property type."""
    return [
        f for f in get_flat_field_list(property_type) 
        if f.priority in [FieldPriority.REQUIRED, FieldPriority.IMPORTANT]
    ]
