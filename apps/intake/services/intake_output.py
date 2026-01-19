"""
Service for generating structured intake outputs.

Phase 8: Forward compatibility with quoting and bookings.

Provides structured outputs from intake sessions that can be consumed
by pricing engines and booking workflows without coupling chat to those systems.

CRITICAL BOUNDARY: Proposals vs Applied Memory
==============================================
This service enforces a strict boundary:

- PROPOSALS are NEVER treated as truth by downstream systems
- ONLY APPLIED canonical memory counts (Property, PropertyMemory models)
- This prevents half-applied intake from leaking into pricing or jobs

All data in IntakeOutput comes from:
- Property model (applied property data)
- PropertyMemory model (applied memory/notes/rules/preferences)
- IdealConditionPhoto model (applied reference photos)

This service does NOT read:
- UpdateProposal records (pending proposals)
- IntakeMessage records (chat transcripts)
- Any unapplied data

This ensures that pricing, booking, and job systems only see
data that has been explicitly applied and validated.
"""
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from apps.intake.models import IntakeSession
from apps.properties.models import Property, PropertyMemory, PropertyMemoryType


@dataclass
class IntakeOutput:
    """
    Structured output from an intake session.
    
    This provides a clean interface for downstream systems (pricing, booking)
    to consume intake data without coupling to chat implementation.
    """
    # Session info
    session_id: str
    property_id: Optional[str] = None
    onboarding_complete: bool = False
    
    # Home basics
    address: Optional[str] = None
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: str = "USA"
    
    # Property characteristics (for pricing)
    property_type: Optional[str] = None
    square_feet: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    year_built: Optional[int] = None
    lot_size_sqft: Optional[int] = None
    
    # Service preferences (for booking)
    service_type_preference: Optional[str] = None  # "regular", "deep", "specific"
    service_frequency_preference: Optional[str] = None  # "weekly", "biweekly", "monthly", "one-time"
    
    # Scope signals
    rooms_identified: List[str] = field(default_factory=list)
    priority_areas: List[str] = field(default_factory=list)
    
    # Rules and preferences
    do_rules: List[Dict[str, Any]] = field(default_factory=list)
    dont_rules: List[Dict[str, Any]] = field(default_factory=list)
    product_preferences: List[Dict[str, Any]] = field(default_factory=list)
    sensitivities: List[Dict[str, Any]] = field(default_factory=list)
    
    # Access information
    access_instructions: Optional[str] = None
    
    # Notes and general memories
    general_notes: List[Dict[str, Any]] = field(default_factory=list)
    
    # Reference photos
    reference_photos: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "session_id": self.session_id,
            "property_id": self.property_id,
            "onboarding_complete": self.onboarding_complete,
            "home_basics": {
                "address": self.address,
                "address_line_1": self.address_line_1,
                "city": self.city,
                "state": self.state,
                "zip_code": self.zip_code,
                "country": self.country,
            },
            "property_characteristics": {
                "property_type": self.property_type,
                "square_feet": self.square_feet,
                "bedrooms": self.bedrooms,
                "bathrooms": self.bathrooms,
                "year_built": self.year_built,
                "lot_size_sqft": self.lot_size_sqft,
            },
            "service_preferences": {
                "service_type": self.service_type_preference,
                "frequency": self.service_frequency_preference,
            },
            "scope_signals": {
                "rooms_identified": self.rooms_identified,
                "priority_areas": self.priority_areas,
            },
            "rules_and_preferences": {
                "do_rules": self.do_rules,
                "dont_rules": self.dont_rules,
                "product_preferences": self.product_preferences,
                "sensitivities": self.sensitivities,
            },
            "access": {
                "instructions": self.access_instructions,
            },
            "general_notes": self.general_notes,
            "reference_photos": self.reference_photos,
        }


class IntakeOutputService:
    """
    Service for generating structured intake outputs.
    
    Extracts data from Property and PropertyMemory models to create
    a clean, structured output that pricing and booking systems can consume.
    """
    
    @staticmethod
    def generate_output(session: IntakeSession) -> IntakeOutput:
        """
        Generate structured output from an intake session.
        
        Args:
            session: The intake session
            
        Returns:
            IntakeOutput with all structured data
        """
        output = IntakeOutput(
            session_id=str(session.id),
            property_id=str(session.property.id) if session.property else None,
            onboarding_complete=session.onboarding_complete,
        )
        
        if not session.property:
            return output
        
        property_obj = session.property
        
        # Extract home basics
        output.address = property_obj.address
        output.address_line_1 = property_obj.address_line_1
        output.city = property_obj.city
        output.state = property_obj.state
        output.zip_code = property_obj.zip_code
        output.country = property_obj.country or "USA"
        
        # Extract property characteristics
        output.property_type = property_obj.property_type
        output.square_feet = property_obj.square_feet
        output.bedrooms = property_obj.bedrooms
        output.bathrooms = float(property_obj.bathrooms) if property_obj.bathrooms else None
        output.year_built = property_obj.year_built
        output.lot_size_sqft = property_obj.lot_size_sqft
        
        # Extract access information
        output.access_instructions = property_obj.access_instructions
        
        # Load all memories for the property
        memories = PropertyMemory.objects.filter(
            property=property_obj,
            is_active=True,
        ).order_by("created_at")
        
        # Extract service preferences from memories
        for memory in memories:
            content_lower = memory.content.lower() if memory.content else ""
            
            # Service type detection
            if not output.service_type_preference:
                if any(kw in content_lower for kw in ["deep clean", "thorough", "detailed", "move-in", "move-out"]):
                    output.service_type_preference = "deep"
                elif any(kw in content_lower for kw in ["regular", "standard", "routine", "maintenance"]):
                    output.service_type_preference = "regular"
                elif any(kw in content_lower for kw in ["specific", "particular", "focus on"]):
                    output.service_type_preference = "specific"
            
            # Service frequency detection
            if not output.service_frequency_preference:
                if any(kw in content_lower for kw in ["weekly", "every week", "once a week"]):
                    output.service_frequency_preference = "weekly"
                elif any(kw in content_lower for kw in ["biweekly", "bi-weekly", "every two weeks", "twice a month"]):
                    output.service_frequency_preference = "biweekly"
                elif any(kw in content_lower for kw in ["monthly", "every month", "once a month"]):
                    output.service_frequency_preference = "monthly"
                elif any(kw in content_lower for kw in ["one time", "once", "single", "just this once"]):
                    output.service_frequency_preference = "one-time"
        
        # Extract rules and preferences by type
        for memory in memories:
            if memory.memory_type == PropertyMemoryType.DO_RULE:
                output.do_rules.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "label": memory.label,
                    "level": memory.level,
                    "room_name": memory.room_name,
                    "surface_name": memory.surface_name,
                    "priority": memory.priority,
                })
            elif memory.memory_type == PropertyMemoryType.DONT_RULE:
                output.dont_rules.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "label": memory.label,
                    "level": memory.level,
                    "room_name": memory.room_name,
                    "surface_name": memory.surface_name,
                    "priority": memory.priority,
                })
            elif memory.memory_type == PropertyMemoryType.PRODUCT_PREFERENCE:
                output.product_preferences.append({
                    "id": str(memory.id),
                    "product_name": memory.product_name,
                    "use_product": memory.use_product,
                    "content": memory.content,
                    "level": memory.level,
                    "room_name": memory.room_name,
                })
            elif memory.memory_type == PropertyMemoryType.PERSONAL_SENSITIVITY:
                output.sensitivities.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "label": memory.label,
                    "level": memory.level,
                    "room_name": memory.room_name,
                })
            elif memory.memory_type == PropertyMemoryType.NOTE:
                # Extract room names
                if memory.room_name and memory.room_name not in output.rooms_identified:
                    output.rooms_identified.append(memory.room_name)
                
                # Check for priority mentions
                if any(word in (memory.content or "").lower() for word in ["priority", "important", "focus", "main concern"]):
                    output.priority_areas.append({
                        "room": memory.room_name or "property",
                        "note": memory.content[:200],
                    })
                
                # General notes
                output.general_notes.append({
                    "id": str(memory.id),
                    "content": memory.content,
                    "label": memory.label,
                    "room_name": memory.room_name,
                    "level": memory.level,
                })
        
        # Extract reference photos
        from apps.properties.models import IdealConditionPhoto
        photos = IdealConditionPhoto.objects.filter(
            property=property_obj,
            is_active=True,
        ).order_by("created_at")
        
        for photo in photos:
            output.reference_photos.append({
                "id": str(photo.id),
                "file_name": photo.file_name,
                "file_url": photo.file_url,
                "thumbnail_url": photo.thumbnail_url,
                "room_name": photo.room_name,
                "surface_name": photo.surface_name,
                "location_description": photo.location_description,
                "caption": photo.caption,
            })
        
        return output
