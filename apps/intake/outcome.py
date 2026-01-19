"""
Intake outcome data structures and builders.

Provides a clean, structured view of intake results for consumption by
pricing, booking, operator review, and client UI.

CRITICAL BOUNDARY: Proposals vs Applied Memory
==============================================
This module enforces a strict boundary:

- PROPOSALS are NEVER treated as truth by downstream systems
- ONLY APPLIED canonical memory counts (Property, PropertyMemory models)
- This prevents half-applied intake from leaking into pricing or jobs

All data in IntakeOutcome comes from:
- Property model (applied property data)
- PropertyMemory model (applied memory/notes/rules/preferences)
- IdealConditionPhoto model (applied reference photos)

This module does NOT read:
- UpdateProposal records (pending proposals)
- IntakeMessage records (chat transcripts)
- Any unapplied data

This ensures that pricing, booking, and job systems only see
data that has been explicitly applied and validated.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from django.utils import timezone

from apps.properties.models import Property, PropertyMemory, PropertyMemoryType
from apps.intake.models import IntakeSession
from apps.intake.fact_requirements import (
    OnboardingFactChecker,
    OnboardingFactStatus,
)


class ReadinessStatus(str, Enum):
    """Overall readiness to proceed with quoting/booking."""
    READY = "ready"
    NOT_READY = "not_ready"
    INCOMPLETE = "incomplete"  # Has property but missing critical facts


@dataclass
class PropertyDetails:
    """Core property details."""
    id: str
    address: str
    address_line_1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    property_type: Optional[str] = None
    square_feet: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[float] = None
    num_floors: Optional[int] = None
    year_built: Optional[int] = None
    access_instructions: Optional[str] = None
    parking_instructions: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "address": self.address,
            "address_line_1": self.address_line_1,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "property_type": self.property_type,
            "square_feet": self.square_feet,
            "bedrooms": self.bedrooms,
            "bathrooms": float(self.bathrooms) if self.bathrooms else None,
            "num_floors": self.num_floors,
            "year_built": self.year_built,
            "access_instructions": self.access_instructions,
            "parking_instructions": self.parking_instructions,
        }


@dataclass
class RoomInfo:
    """Information about a room."""
    name: str
    display_name: str
    notes: List[str] = field(default_factory=list)
    surfaces: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "notes": self.notes,
            "surfaces": self.surfaces,
        }


@dataclass
class StandardRule:
    """A do or don't rule."""
    id: str
    rule_type: str  # "do" or "dont"
    content: str
    room_name: Optional[str] = None
    surface_name: Optional[str] = None
    priority: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "rule_type": self.rule_type,
            "content": self.content,
            "room_name": self.room_name,
            "surface_name": self.surface_name,
            "priority": self.priority,
        }


@dataclass
class ProductPreference:
    """A product preference."""
    id: str
    product_name: str
    use_product: bool  # True = use, False = avoid
    notes: Optional[str] = None
    room_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "product_name": self.product_name,
            "use_product": self.use_product,
            "notes": self.notes,
            "room_name": self.room_name,
        }


@dataclass
class Sensitivity:
    """A personal sensitivity or allergy."""
    id: str
    content: str
    severity: Optional[str] = None  # "mild", "moderate", "severe"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "severity": self.severity,
        }


@dataclass
class GeneralNote:
    """A general note about the property."""
    id: str
    content: str
    room_name: Optional[str] = None
    surface_name: Optional[str] = None
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "room_name": self.room_name,
            "surface_name": self.surface_name,
            "label": self.label,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Standards:
    """All standards and constraints for the property."""
    do_rules: List[StandardRule] = field(default_factory=list)
    dont_rules: List[StandardRule] = field(default_factory=list)
    product_preferences: List[ProductPreference] = field(default_factory=list)
    sensitivities: List[Sensitivity] = field(default_factory=list)
    general_notes: List[GeneralNote] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "do_rules": [r.to_dict() for r in self.do_rules],
            "dont_rules": [r.to_dict() for r in self.dont_rules],
            "product_preferences": [p.to_dict() for p in self.product_preferences],
            "sensitivities": [s.to_dict() for s in self.sensitivities],
            "general_notes": [n.to_dict() for n in self.general_notes],
            "summary": {
                "total_rules": len(self.do_rules) + len(self.dont_rules),
                "total_product_preferences": len(self.product_preferences),
                "total_sensitivities": len(self.sensitivities),
                "total_notes": len(self.general_notes),
            }
        }


@dataclass
class MissingInfo:
    """Information about what's still missing."""
    categories: List[str]
    details: Dict[str, List[str]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "categories": self.categories,
            "details": self.details,
        }


@dataclass
class ReadinessInfo:
    """Readiness status and details."""
    status: ReadinessStatus
    is_ready: bool
    completion_percentage: float
    missing: Optional[MissingInfo] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "status": self.status.value,
            "is_ready": self.is_ready,
            "completion_percentage": round(self.completion_percentage, 1),
        }
        if self.missing:
            result["missing"] = self.missing.to_dict()
        return result


@dataclass
class IntakeOutcome:
    """
    Complete intake outcome for an intake session.
    
    Contains only applied/stored data - no pending proposals or chat text.
    Ready for consumption by pricing, booking, operator review, and client UI.
    """
    # Session info
    session_id: str
    session_status: str
    session_created_at: datetime
    session_updated_at: datetime
    
    # Property link
    property_id: Optional[str]
    has_property: bool
    
    # Core data (only if property exists)
    property_details: Optional[PropertyDetails]
    rooms: List[RoomInfo]
    standards: Standards
    
    # Readiness
    readiness: ReadinessInfo
    
    # Metadata
    generated_at: datetime = field(default_factory=timezone.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session": {
                "id": self.session_id,
                "status": self.session_status,
                "created_at": self.session_created_at.isoformat(),
                "updated_at": self.session_updated_at.isoformat(),
            },
            "property_id": self.property_id,
            "has_property": self.has_property,
            "property": self.property_details.to_dict() if self.property_details else None,
            "rooms": [r.to_dict() for r in self.rooms],
            "standards": self.standards.to_dict(),
            "readiness": self.readiness.to_dict(),
            "generated_at": self.generated_at.isoformat(),
        }


class IntakeOutcomeBuilder:
    """
    Builds an IntakeOutcome from stored data.
    
    Only reads from applied/stored records:
    - Property model
    - PropertyMemory records
    
    Does NOT read:
    - Chat messages
    - Pending proposals
    """
    
    def __init__(self, session: IntakeSession):
        self.session = session
        self.property = session.property
        self._memories: Optional[List[PropertyMemory]] = None
    
    @property
    def memories(self) -> List[PropertyMemory]:
        """Lazy load property memories."""
        if self._memories is None:
            if self.property:
                self._memories = list(
                    PropertyMemory.objects.filter(
                        property=self.property,
                        is_active=True
                    ).order_by("-priority", "-created_at")
                )
            else:
                self._memories = []
        return self._memories
    
    def _build_property_details(self) -> Optional[PropertyDetails]:
        """Build property details from Property model."""
        if not self.property:
            return None
        
        p = self.property
        return PropertyDetails(
            id=str(p.id),
            address=p.address,
            address_line_1=p.address_line_1 or None,
            city=p.city or None,
            state=p.state or None,
            zip_code=p.zip_code or None,
            property_type=p.property_type or None,
            square_feet=p.square_feet,
            bedrooms=p.bedrooms,
            bathrooms=float(p.bathrooms) if p.bathrooms else None,
            num_floors=None,  # Add to Property model if needed
            year_built=p.year_built,
            access_instructions=p.access_instructions or None,
            parking_instructions=None,  # Add to Property model if needed
        )
    
    def _build_rooms(self) -> List[RoomInfo]:
        """Build room list from PropertyMemory records."""
        if not self.property:
            return []
        
        # Collect unique rooms from memories
        rooms_dict: Dict[str, RoomInfo] = {}
        
        for mem in self.memories:
            if not mem.room_name:
                continue
            
            room_key = mem.room_name.lower().strip()
            
            if room_key not in rooms_dict:
                # Create display name with proper capitalization
                display_name = mem.room_name.strip().title()
                rooms_dict[room_key] = RoomInfo(
                    name=room_key,
                    display_name=display_name,
                    notes=[],
                    surfaces=[],
                )
            
            room = rooms_dict[room_key]
            
            # Add surface if specified
            if mem.surface_name and mem.surface_name not in room.surfaces:
                room.surfaces.append(mem.surface_name)
            
            # Add note content if it's a note type
            if mem.memory_type == PropertyMemoryType.NOTE:
                note_preview = mem.content[:200] if len(mem.content) > 200 else mem.content
                if note_preview not in room.notes:
                    room.notes.append(note_preview)
        
        # Sort rooms alphabetically
        return sorted(rooms_dict.values(), key=lambda r: r.display_name)
    
    def _build_standards(self) -> Standards:
        """Build standards from PropertyMemory records."""
        do_rules = []
        dont_rules = []
        product_preferences = []
        sensitivities = []
        general_notes = []
        
        for mem in self.memories:
            mem_id = str(mem.id)
            
            if mem.memory_type == PropertyMemoryType.DO_RULE:
                do_rules.append(StandardRule(
                    id=mem_id,
                    rule_type="do",
                    content=mem.content,
                    room_name=mem.room_name or None,
                    surface_name=mem.surface_name or None,
                    priority=mem.priority,
                ))
            
            elif mem.memory_type == PropertyMemoryType.DONT_RULE:
                dont_rules.append(StandardRule(
                    id=mem_id,
                    rule_type="dont",
                    content=mem.content,
                    room_name=mem.room_name or None,
                    surface_name=mem.surface_name or None,
                    priority=mem.priority,
                ))
            
            elif mem.memory_type == PropertyMemoryType.PRODUCT_PREFERENCE:
                product_preferences.append(ProductPreference(
                    id=mem_id,
                    product_name=mem.product_name or mem.label or "Unknown",
                    use_product=mem.use_product,
                    notes=mem.content if mem.content != mem.product_name else None,
                    room_name=mem.room_name or None,
                ))
            
            elif mem.memory_type == PropertyMemoryType.PERSONAL_SENSITIVITY:
                sensitivities.append(Sensitivity(
                    id=mem_id,
                    content=mem.content,
                    severity=None,  # Could parse from content or add field
                ))
            
            elif mem.memory_type == PropertyMemoryType.NOTE:
                # Only include property-level notes here (room notes are in rooms)
                if not mem.room_name:
                    general_notes.append(GeneralNote(
                        id=mem_id,
                        content=mem.content,
                        room_name=None,
                        surface_name=mem.surface_name or None,
                        label=mem.label or None,
                        created_at=mem.created_at,
                    ))
        
        return Standards(
            do_rules=do_rules,
            dont_rules=dont_rules,
            product_preferences=product_preferences,
            sensitivities=sensitivities,
            general_notes=general_notes,
        )
    
    def _build_readiness(self) -> ReadinessInfo:
        """Build readiness status from fact checking."""
        # Use the fact checker to determine readiness
        checker = OnboardingFactChecker(property_obj=self.property)
        fact_status = checker.check_all_facts()
        
        # Determine status
        if fact_status.ready_to_proceed:
            status = ReadinessStatus.READY
            missing_info = None
        elif self.property:
            status = ReadinessStatus.INCOMPLETE
            missing_info = self._build_missing_info(fact_status)
        else:
            status = ReadinessStatus.NOT_READY
            missing_info = self._build_missing_info(fact_status)
        
        return ReadinessInfo(
            status=status,
            is_ready=fact_status.ready_to_proceed,
            completion_percentage=fact_status.completion_percentage,
            missing=missing_info,
        )
    
    def _build_missing_info(self, fact_status: OnboardingFactStatus) -> MissingInfo:
        """Build missing info from fact status."""
        # Group missing facts by category
        categories = set()
        details: Dict[str, List[str]] = {}
        
        for fact in fact_status.missing_critical_facts:
            cat_name = fact.category.value
            categories.add(cat_name)
            
            if cat_name not in details:
                details[cat_name] = []
            details[cat_name].append(fact.description)
        
        return MissingInfo(
            categories=sorted(list(categories)),
            details=details,
        )
    
    def build(self) -> IntakeOutcome:
        """Build the complete intake outcome."""
        return IntakeOutcome(
            session_id=str(self.session.id),
            session_status=self.session.status,
            session_created_at=self.session.created_at,
            session_updated_at=self.session.updated_at,
            property_id=str(self.property.id) if self.property else None,
            has_property=self.property is not None,
            property_details=self._build_property_details(),
            rooms=self._build_rooms(),
            standards=self._build_standards(),
            readiness=self._build_readiness(),
        )
