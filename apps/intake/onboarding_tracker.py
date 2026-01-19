"""
Tracks onboarding progress for an intake session.

Determines what information has been collected, what's missing,
and what to ask about next.
"""
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from apps.intake.onboarding_schema import (
    OnboardingField,
    OnboardingCategory,
    FieldPriority,
    PropertyTypeSchema,
    get_onboarding_schema,
    get_flat_field_list,
    ROOM_TEMPLATES,
)
from apps.intake.models import IntakeSession, UpdateProposal, UpdateProposalStatus


class FieldStatus(str, Enum):
    """Status of a field in onboarding."""
    NOT_STARTED = "not_started"
    PARTIAL = "partial"  # Some info but needs more detail
    COMPLETE = "complete"
    SKIPPED = "skipped"  # User explicitly skipped


@dataclass
class FieldProgress:
    """Progress status for a single field."""
    field: OnboardingField
    status: FieldStatus
    collected_value: Any = None
    source: str = ""  # "property", "proposal", "memory"
    confidence: float = 1.0  # How confident we are in the value
    notes: str = ""


@dataclass
class CategoryProgress:
    """Progress for a category of fields."""
    category: OnboardingCategory
    total_fields: int
    required_complete: int
    required_total: int
    important_complete: int
    important_total: int
    fields: List[FieldProgress]
    
    @property
    def completion_percentage(self) -> float:
        """Calculate completion percentage (required + important)."""
        total = self.required_total + self.important_total
        complete = self.required_complete + self.important_complete
        return (complete / total * 100) if total > 0 else 100.0
    
    @property
    def required_complete_pct(self) -> float:
        """Percentage of required fields complete."""
        return (self.required_complete / self.required_total * 100) if self.required_total > 0 else 100.0


@dataclass
class OnboardingProgress:
    """Overall onboarding progress."""
    property_type: str
    categories: Dict[str, CategoryProgress]
    overall_completion: float
    required_completion: float
    missing_required: List[OnboardingField]
    missing_important: List[OnboardingField]
    suggested_next_topic: Optional[str] = None
    suggested_next_fields: List[OnboardingField] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "property_type": self.property_type,
            "overall_completion": round(self.overall_completion, 1),
            "required_completion": round(self.required_completion, 1),
            "categories": {
                cat: {
                    "completion": round(prog.completion_percentage, 1),
                    "required_complete": prog.required_complete,
                    "required_total": prog.required_total,
                    "important_complete": prog.important_complete,
                    "important_total": prog.important_total,
                }
                for cat, prog in self.categories.items()
            },
            "missing_required": [f.key for f in self.missing_required],
            "missing_important": [f.key for f in self.missing_important],
            "suggested_next_topic": self.suggested_next_topic,
            "suggested_next_fields": [f.key for f in self.suggested_next_fields],
        }


class OnboardingTracker:
    """
    Tracks and calculates onboarding progress for a session.
    
    Pulls data from:
    - Property model (if linked)
    - PropertyMemory records
    - Pending UpdateProposals from the session
    - Session context/metadata
    """
    
    def __init__(self, session: IntakeSession):
        self.session = session
        self.property = session.property
        self._collected_data: Dict[str, Any] = {}
        self._field_sources: Dict[str, str] = {}
        
    def _extract_property_data(self) -> Dict[str, Any]:
        """Extract known data from the Property model."""
        data = {}
        
        if not self.property:
            return data
        
        prop = self.property
        
        # Map property fields to onboarding keys
        if prop.address:
            data["address"] = prop.address
        if prop.property_type:
            data["property_type"] = prop.property_type
        if prop.square_feet:
            data["square_feet"] = prop.square_feet
        if prop.bedrooms:
            data["num_bedrooms"] = prop.bedrooms
        if prop.bathrooms:
            data["num_bathrooms"] = prop.bathrooms
        if prop.access_instructions:
            data["access_details"] = prop.access_instructions
            
        # Mark sources
        for key in data:
            self._field_sources[key] = "property"
            
        return data
    
    def _extract_memory_data(self) -> Dict[str, Any]:
        """Extract known data from PropertyMemory records."""
        from apps.properties.models import PropertyMemory, PropertyMemoryType
        
        data = {}
        
        if not self.property:
            return data
        
        memories = PropertyMemory.objects.filter(
            property=self.property,
            is_active=True,
        ).order_by("-priority", "-created_at")
        
        # Categorize memories by type
        do_rules = []
        dont_rules = []
        products_use = []
        products_avoid = []
        rooms = set()
        notes = []
        
        for mem in memories:
            if mem.memory_type == PropertyMemoryType.DO_RULE:
                do_rules.append(mem.content)
            elif mem.memory_type == PropertyMemoryType.DONT_RULE:
                dont_rules.append(mem.content)
            elif mem.memory_type == PropertyMemoryType.PRODUCT_PREFERENCE:
                if mem.use_product:
                    products_use.append(mem.product_name or mem.content)
                else:
                    products_avoid.append(mem.product_name or mem.content)
            elif mem.memory_type == PropertyMemoryType.NOTE:
                notes.append(mem.content)
            
            # Track rooms mentioned
            if mem.room_name:
                rooms.add(mem.room_name.lower())
        
        if do_rules:
            data["do_rules"] = do_rules
        if dont_rules:
            data["dont_rules"] = dont_rules
        if products_use:
            data["products_to_use"] = products_use
        if products_avoid:
            data["products_to_avoid"] = products_avoid
        if rooms:
            data["room_list"] = list(rooms)
            
        # Mark sources
        for key in data:
            self._field_sources[key] = "memory"
            
        return data
    
    def _extract_proposal_data(self) -> Dict[str, Any]:
        """Extract data from pending UpdateProposals."""
        from apps.intake.models import UpdateProposalStatus, UpdateProposalType
        
        data = {}
        
        proposals = UpdateProposal.objects.filter(
            session=self.session,
            status=UpdateProposalStatus.PENDING,
        ).order_by("created_at")
        
        rooms_from_proposals = set()
        do_rules = []
        dont_rules = []
        products_use = []
        products_avoid = []
        
        for proposal in proposals:
            proposed = proposal.proposed_data or {}
            
            # Property updates
            if proposal.proposal_type in [
                UpdateProposalType.PROPERTY_CREATE, 
                UpdateProposalType.PROPERTY_UPDATE
            ]:
                for key in ["address", "property_type", "square_feet", "num_bedrooms", 
                           "num_bathrooms", "num_floors", "access_method", "access_details",
                           "parking_instructions", "gate_code", "alarm_info"]:
                    if key in proposed and proposed[key]:
                        data[key] = proposed[key]
            
            # Room creates
            if proposal.proposal_type == UpdateProposalType.ROOM_CREATE:
                room_name = proposed.get("room_name") or proposed.get("name")
                if room_name:
                    rooms_from_proposals.add(room_name.lower())
            
            # Memory/preference creates
            if proposal.proposal_type in [
                UpdateProposalType.MEMORY_CREATE,
                UpdateProposalType.PREFERENCE_CREATE
            ]:
                mem_type = proposed.get("memory_type") or proposed.get("type")
                content = proposed.get("content") or proposed.get("value")
                
                if mem_type == "do_rule" and content:
                    do_rules.append(content)
                elif mem_type == "dont_rule" and content:
                    dont_rules.append(content)
                elif mem_type == "product_preference":
                    product = proposed.get("product_name") or content
                    if proposed.get("use_product", True):
                        products_use.append(product)
                    else:
                        products_avoid.append(product)
                        
                # Check for pet info
                if "pet" in str(content).lower() or mem_type == "pet":
                    data["pets"] = content
                    
                # Check for allergy info
                if "allerg" in str(content).lower() or mem_type == "allergy":
                    data["allergies"] = content
            
            # Explicit do/don't rule proposals
            if proposal.proposal_type in [
                UpdateProposalType.DO_RULE_CREATE,
                UpdateProposalType.DO_RULE_UPDATE
            ]:
                content = proposed.get("content") or proposed.get("rule", "")
                if content:
                    do_rules.append(content)
            
            if proposal.proposal_type in [
                UpdateProposalType.DONT_RULE_CREATE,
                UpdateProposalType.DONT_RULE_UPDATE
            ]:
                content = proposed.get("content") or proposed.get("rule", "")
                if content:
                    dont_rules.append(content)
            
            # Photo proposals (extract room/surface context if available)
            if proposal.proposal_type in [
                UpdateProposalType.PHOTO_CREATE,
                UpdateProposalType.PHOTO_UPDATE
            ]:
                # Photos might indicate room context
                room_name = proposed.get("room_name", "")
                if room_name and room_name not in rooms_from_proposals:
                    rooms_from_proposals.add(room_name.lower())
        
        # Merge lists
        if rooms_from_proposals:
            existing_rooms = set(data.get("room_list", []))
            data["room_list"] = list(existing_rooms | rooms_from_proposals)
        if do_rules:
            existing = data.get("do_rules", [])
            data["do_rules"] = existing + do_rules
        if dont_rules:
            existing = data.get("dont_rules", [])
            data["dont_rules"] = existing + dont_rules
        if products_use:
            existing = data.get("products_to_use", [])
            data["products_to_use"] = existing + products_use
        if products_avoid:
            existing = data.get("products_to_avoid", [])
            data["products_to_avoid"] = existing + products_avoid
            
        # Mark sources
        for key in data:
            if key not in self._field_sources:
                self._field_sources[key] = "proposal"
                
        return data
    
    def _extract_session_context(self) -> Dict[str, Any]:
        """Extract any data stored in session context."""
        data = {}
        context = self.session.system_context or {}
        
        # Check for collected_data in context
        if "collected_data" in context:
            data.update(context["collected_data"])
            for key in context["collected_data"]:
                if key not in self._field_sources:
                    self._field_sources[key] = "session"
                    
        return data
    
    def collect_all_data(self) -> Dict[str, Any]:
        """
        Collect all known data from all sources.
        
        Order matters - later sources can override earlier ones:
        1. Session context (lowest priority)
        2. Proposals
        3. Memory
        4. Property model (highest priority - confirmed data)
        """
        self._collected_data = {}
        self._field_sources = {}
        
        # Collect in priority order (lowest first)
        self._collected_data.update(self._extract_session_context())
        self._collected_data.update(self._extract_proposal_data())
        self._collected_data.update(self._extract_memory_data())
        self._collected_data.update(self._extract_property_data())
        
        return self._collected_data
    
    def _get_field_status(
        self, 
        field: OnboardingField, 
        collected: Dict[str, Any]
    ) -> Tuple[FieldStatus, Any]:
        """Determine the status of a single field."""
        value = collected.get(field.key)
        
        if value is None:
            return FieldStatus.NOT_STARTED, None
        
        # For list types, check if we have meaningful content
        if field.data_type == "list":
            if isinstance(value, list) and len(value) > 0:
                return FieldStatus.COMPLETE, value
            return FieldStatus.NOT_STARTED, None
        
        # For text, check for non-empty
        if field.data_type == "text":
            if value and str(value).strip():
                return FieldStatus.COMPLETE, value
            return FieldStatus.NOT_STARTED, None
        
        # For numbers, check for valid value
        if field.data_type == "number":
            if value is not None and value != "":
                return FieldStatus.COMPLETE, value
            return FieldStatus.NOT_STARTED, None
        
        # For boolean
        if field.data_type == "boolean":
            if value is not None:
                return FieldStatus.COMPLETE, value
            return FieldStatus.NOT_STARTED, None
        
        # For enum
        if field.data_type == "enum":
            if value and str(value).strip():
                return FieldStatus.COMPLETE, value
            return FieldStatus.NOT_STARTED, None
        
        # Default: if we have any value, consider it complete
        if value:
            return FieldStatus.COMPLETE, value
        return FieldStatus.NOT_STARTED, None
    
    def calculate_progress(self) -> OnboardingProgress:
        """
        Calculate the full onboarding progress.
        
        Returns detailed progress information including:
        - Per-category completion
        - Missing required/important fields
        - Suggested next topic to discuss
        """
        collected = self.collect_all_data()
        
        # Determine property type (default to single_family)
        property_type = collected.get("property_type", "single_family")
        if property_type not in [e.value for e in PropertyTypeSchema]:
            property_type = PropertyTypeSchema.SINGLE_FAMILY.value
        
        schema = get_onboarding_schema(property_type)
        
        categories: Dict[str, CategoryProgress] = {}
        all_missing_required: List[OnboardingField] = []
        all_missing_important: List[OnboardingField] = []
        total_required = 0
        total_required_complete = 0
        total_important = 0
        total_important_complete = 0
        
        for category_name, fields in schema.items():
            field_progress_list = []
            cat_required = 0
            cat_required_complete = 0
            cat_important = 0
            cat_important_complete = 0
            
            for f in fields:
                status, value = self._get_field_status(f, collected)
                source = self._field_sources.get(f.key, "")
                
                field_progress_list.append(FieldProgress(
                    field=f,
                    status=status,
                    collected_value=value,
                    source=source,
                ))
                
                if f.priority == FieldPriority.REQUIRED:
                    cat_required += 1
                    total_required += 1
                    if status == FieldStatus.COMPLETE:
                        cat_required_complete += 1
                        total_required_complete += 1
                    else:
                        all_missing_required.append(f)
                        
                elif f.priority == FieldPriority.IMPORTANT:
                    cat_important += 1
                    total_important += 1
                    if status == FieldStatus.COMPLETE:
                        cat_important_complete += 1
                        total_important_complete += 1
                    else:
                        all_missing_important.append(f)
            
            categories[category_name] = CategoryProgress(
                category=OnboardingCategory(category_name),
                total_fields=len(fields),
                required_complete=cat_required_complete,
                required_total=cat_required,
                important_complete=cat_important_complete,
                important_total=cat_important,
                fields=field_progress_list,
            )
        
        # Calculate overall percentages
        total_target = total_required + total_important
        total_complete = total_required_complete + total_important_complete
        overall_completion = (total_complete / total_target * 100) if total_target > 0 else 100.0
        required_completion = (total_required_complete / total_required * 100) if total_required > 0 else 100.0
        
        # Determine suggested next topic
        suggested_topic, suggested_fields = self._suggest_next_topic(
            categories, 
            all_missing_required, 
            all_missing_important
        )
        
        return OnboardingProgress(
            property_type=property_type,
            categories=categories,
            overall_completion=overall_completion,
            required_completion=required_completion,
            missing_required=all_missing_required,
            missing_important=all_missing_important,
            suggested_next_topic=suggested_topic,
            suggested_next_fields=suggested_fields,
        )
    
    def _suggest_next_topic(
        self,
        categories: Dict[str, CategoryProgress],
        missing_required: List[OnboardingField],
        missing_important: List[OnboardingField],
    ) -> Tuple[Optional[str], List[OnboardingField]]:
        """
        Determine the best next topic to discuss.
        
        Priority:
        1. Required fields, in category order
        2. Important fields, in category order
        """
        # Category priority order
        category_order = [
            OnboardingCategory.PROPERTY_BASICS.value,
            OnboardingCategory.ACCESS.value,
            OnboardingCategory.ROOMS.value,
            OnboardingCategory.SURFACES.value,
            OnboardingCategory.PREFERENCES.value,
            OnboardingCategory.PRIORITIES.value,
            OnboardingCategory.SPECIAL_INSTRUCTIONS.value,
        ]
        
        # First pass: find categories with missing required fields
        for cat_name in category_order:
            if cat_name not in categories:
                continue
            cat = categories[cat_name]
            if cat.required_complete < cat.required_total:
                # Get the missing required fields for this category
                missing = [
                    fp.field for fp in cat.fields
                    if fp.status != FieldStatus.COMPLETE 
                    and fp.field.priority == FieldPriority.REQUIRED
                ]
                if missing:
                    return cat_name, missing[:3]  # Return up to 3 fields
        
        # Second pass: find categories with missing important fields
        for cat_name in category_order:
            if cat_name not in categories:
                continue
            cat = categories[cat_name]
            if cat.important_complete < cat.important_total:
                missing = [
                    fp.field for fp in cat.fields
                    if fp.status != FieldStatus.COMPLETE 
                    and fp.field.priority == FieldPriority.IMPORTANT
                ]
                if missing:
                    return cat_name, missing[:3]
        
        # All required and important fields complete
        return None, []
    
    def get_context_summary(self) -> str:
        """
        Generate a text summary of what's known for AI context.
        
        This is the structured, repeatable view of the home memory.
        """
        collected = self.collect_all_data()
        progress = self.calculate_progress()
        
        lines = []
        lines.append(f"=== HOME INFORMATION ({progress.overall_completion:.0f}% complete) ===")
        lines.append("")
        
        # Property basics
        lines.append("PROPERTY BASICS:")
        if collected.get("address"):
            lines.append(f"  Address: {collected['address']}")
        if collected.get("property_type"):
            lines.append(f"  Type: {collected['property_type']}")
        if collected.get("square_feet"):
            lines.append(f"  Size: {collected['square_feet']} sq ft")
        if collected.get("num_bedrooms"):
            lines.append(f"  Bedrooms: {collected['num_bedrooms']}")
        if collected.get("num_bathrooms"):
            lines.append(f"  Bathrooms: {collected['num_bathrooms']}")
        if collected.get("num_floors"):
            lines.append(f"  Floors: {collected['num_floors']}")
        
        # Rooms
        if collected.get("room_list"):
            lines.append("")
            lines.append("ROOMS:")
            for room in collected["room_list"]:
                lines.append(f"  - {room}")
        
        if collected.get("rooms_to_skip"):
            lines.append("")
            lines.append("ROOMS TO SKIP:")
            for room in collected["rooms_to_skip"]:
                lines.append(f"  - {room}")
        
        # Surfaces
        if collected.get("floor_types") or collected.get("countertop_types"):
            lines.append("")
            lines.append("SURFACES:")
            if collected.get("floor_types"):
                lines.append(f"  Floors: {', '.join(collected['floor_types'])}")
            if collected.get("countertop_types"):
                lines.append(f"  Counters: {', '.join(collected['countertop_types'])}")
        
        # Access
        if collected.get("access_method") or collected.get("access_details"):
            lines.append("")
            lines.append("ACCESS:")
            if collected.get("access_method"):
                lines.append(f"  Method: {collected['access_method']}")
            if collected.get("access_details"):
                lines.append(f"  Details: {collected['access_details']}")
            if collected.get("parking_instructions"):
                lines.append(f"  Parking: {collected['parking_instructions']}")
            if collected.get("gate_code"):
                lines.append(f"  Gate: {collected['gate_code']}")
            if collected.get("alarm_info"):
                lines.append(f"  Alarm: {collected['alarm_info']}")
        
        # Preferences
        if collected.get("products_to_use") or collected.get("products_to_avoid"):
            lines.append("")
            lines.append("PRODUCT PREFERENCES:")
            if collected.get("products_to_use"):
                lines.append(f"  Use: {', '.join(collected['products_to_use'])}")
            if collected.get("products_to_avoid"):
                lines.append(f"  Avoid: {', '.join(collected['products_to_avoid'])}")
        
        # Rules
        if collected.get("do_rules") or collected.get("dont_rules"):
            lines.append("")
            lines.append("RULES:")
            if collected.get("do_rules"):
                lines.append("  DO:")
                for rule in collected["do_rules"]:
                    lines.append(f"    - {rule}")
            if collected.get("dont_rules"):
                lines.append("  DON'T:")
                for rule in collected["dont_rules"]:
                    lines.append(f"    - {rule}")
        
        # Special instructions
        special = []
        if collected.get("pets"):
            special.append(f"  Pets: {collected['pets']}")
        if collected.get("allergies"):
            special.append(f"  Allergies: {collected['allergies']}")
        if collected.get("fragile_items"):
            special.append(f"  Fragile items: {collected['fragile_items']}")
        if collected.get("high_priority_areas"):
            areas = collected["high_priority_areas"]
            if isinstance(areas, list):
                special.append(f"  Priority areas: {', '.join(areas)}")
            else:
                special.append(f"  Priority areas: {areas}")
        
        if special:
            lines.append("")
            lines.append("SPECIAL NOTES:")
            lines.extend(special)
        
        # What's missing
        if progress.missing_required:
            lines.append("")
            lines.append("STILL NEEDED (Required):")
            for f in progress.missing_required[:5]:
                lines.append(f"  - {f.label}")
        
        if progress.missing_important and len(progress.missing_required) < 3:
            lines.append("")
            lines.append("STILL NEEDED (Important):")
            for f in progress.missing_important[:5]:
                lines.append(f"  - {f.label}")
        
        return "\n".join(lines)
