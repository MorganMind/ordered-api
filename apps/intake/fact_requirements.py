"""
Defines the facts that must exist in stored memory for onboarding completion.

These facts must be present in the actual data models (Property, PropertyMemory, etc.),
not just in chat history or proposals.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from apps.properties.models import Property, PropertyMemory, PropertyMemoryType


class FactStatus(str, Enum):
    """Status of a required fact."""
    MISSING = "missing"
    PARTIAL = "partial"
    COMPLETE = "complete"


class FactCategory(str, Enum):
    """Categories of required facts."""
    PROPERTY = "property"
    ROOMS = "rooms"
    STANDARDS = "standards"
    SERVICE = "service"
    ACCESS = "access"


@dataclass
class RequiredFact:
    """Definition of a single required fact."""
    key: str
    category: FactCategory
    description: str
    check_function: str  # Name of the function to check this fact
    is_critical: bool = True  # Must have for completion
    minimum_value: Optional[Any] = None
    prompt_hints: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "category": self.category.value,
            "description": self.description,
            "is_critical": self.is_critical,
            "prompt_hints": self.prompt_hints,
        }


@dataclass
class FactCheckResult:
    """Result of checking a single fact."""
    fact: RequiredFact
    status: FactStatus
    current_value: Optional[Any] = None
    missing_detail: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        return self.status == FactStatus.COMPLETE
    
    @property
    def is_missing(self) -> bool:
        return self.status == FactStatus.MISSING


@dataclass
class OnboardingFactStatus:
    """Complete status of all onboarding facts."""
    property_exists: bool
    all_critical_facts_complete: bool
    fact_results: List[FactCheckResult]
    missing_critical_facts: List[RequiredFact]
    missing_optional_facts: List[RequiredFact]
    completion_percentage: float
    ready_to_proceed: bool
    next_fact_to_collect: Optional[RequiredFact] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "property_exists": self.property_exists,
            "all_critical_facts_complete": self.all_critical_facts_complete,
            "ready_to_proceed": self.ready_to_proceed,
            "completion_percentage": round(self.completion_percentage, 1),
            "missing_critical": [f.key for f in self.missing_critical_facts],
            "missing_optional": [f.key for f in self.missing_optional_facts],
            "next_to_collect": self.next_fact_to_collect.key if self.next_fact_to_collect else None,
            "by_category": self._group_by_category(),
        }
    
    def _group_by_category(self) -> Dict[str, Dict[str, str]]:
        """Group fact results by category."""
        by_cat = {}
        for result in self.fact_results:
            cat = result.fact.category.value
            if cat not in by_cat:
                by_cat[cat] = {}
            by_cat[cat][result.fact.key] = result.status.value
        return by_cat


# Define the required facts for onboarding completion
REQUIRED_FACTS = [
    # PROPERTY FACTS
    RequiredFact(
        key="property_exists",
        category=FactCategory.PROPERTY,
        description="A property object must exist",
        check_function="check_property_exists",
        is_critical=True,
        prompt_hints=["What's the address of your property?"],
    ),
    RequiredFact(
        key="property_type",
        category=FactCategory.PROPERTY,
        description="Property type must be specified",
        check_function="check_property_type",
        is_critical=True,
        prompt_hints=["Is this a house, apartment, condo, or office?"],
    ),
    RequiredFact(
        key="property_size",
        category=FactCategory.PROPERTY,
        description="Basic size info (bedrooms and bathrooms)",
        check_function="check_property_size",
        is_critical=True,
        prompt_hints=["How many bedrooms and bathrooms?"],
    ),
    
    # ROOMS FACTS
    RequiredFact(
        key="rooms_identified",
        category=FactCategory.ROOMS,
        description="Main rooms to be serviced identified",
        check_function="check_rooms_identified",
        is_critical=True,
        minimum_value=2,  # At least 2 rooms
        prompt_hints=["Which rooms need cleaning?", "What are the main rooms in your home?"],
    ),
    RequiredFact(
        key="priority_areas",
        category=FactCategory.ROOMS,
        description="Priority areas or rooms identified",
        check_function="check_priority_areas",
        is_critical=False,
        prompt_hints=["Which areas are most important to you?"],
    ),
    
    # STANDARDS/RULES FACTS
    RequiredFact(
        key="standards_discussed",
        category=FactCategory.STANDARDS,
        description="Standards, rules, or preferences discussed",
        check_function="check_standards_discussed",
        is_critical=True,
        prompt_hints=[
            "Any specific products you prefer or want to avoid?",
            "Any special instructions for our team?",
            "Anything we should or shouldn't do?"
        ],
    ),
    RequiredFact(
        key="product_preferences",
        category=FactCategory.STANDARDS,
        description="Product preferences (if any)",
        check_function="check_product_preferences",
        is_critical=False,
        prompt_hints=["Any cleaning products you prefer?"],
    ),
    
    # SERVICE FACTS
    RequiredFact(
        key="service_type",
        category=FactCategory.SERVICE,
        description="Type of service needed",
        check_function="check_service_type",
        is_critical=True,
        prompt_hints=["What kind of cleaning service are you looking for?", "Regular cleaning or deep clean?"],
    ),
    RequiredFact(
        key="service_frequency",
        category=FactCategory.SERVICE,
        description="Service frequency preference",
        check_function="check_service_frequency",
        is_critical=False,
        prompt_hints=["How often would you like service?", "Weekly, bi-weekly, or monthly?"],
    ),
    
    # ACCESS FACTS
    RequiredFact(
        key="access_method",
        category=FactCategory.ACCESS,
        description="How to access the property",
        check_function="check_access_method",
        is_critical=True,
        prompt_hints=["How will our team access your home?", "Will you be home or provide a key/code?"],
    ),
]


class OnboardingFactChecker:
    """
    Checks if required facts exist in stored memory (not chat text).
    
    Evaluates actual stored data:
    - Property model fields
    - PropertyMemory records
    - Applied proposals (not pending ones)
    """
    
    def __init__(self, property_obj: Optional[Property] = None):
        self.property = property_obj
        self._memories_cache: Optional[List[PropertyMemory]] = None
    
    @property
    def memories(self) -> List[PropertyMemory]:
        """Lazy load and cache property memories."""
        if self._memories_cache is None:
            if self.property:
                self._memories_cache = list(
                    PropertyMemory.objects.filter(
                        property=self.property,
                        is_active=True
                    )
                )
            else:
                self._memories_cache = []
        return self._memories_cache
    
    def check_property_exists(self, fact: RequiredFact) -> FactCheckResult:
        """Check if a property object exists."""
        if self.property:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=str(self.property.id),
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="No property linked to session",
        )
    
    def check_property_type(self, fact: RequiredFact) -> FactCheckResult:
        """Check if property type is specified."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        if self.property.property_type:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=self.property.property_type,
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="Property type not specified",
        )
    
    def check_property_size(self, fact: RequiredFact) -> FactCheckResult:
        """Check if basic size info exists (bedrooms and bathrooms)."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        has_bedrooms = self.property.bedrooms is not None and self.property.bedrooms > 0
        has_bathrooms = self.property.bathrooms is not None and self.property.bathrooms > 0
        
        if has_bedrooms and has_bathrooms:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=f"{self.property.bedrooms} bed, {self.property.bathrooms} bath",
            )
        elif has_bedrooms or has_bathrooms:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.PARTIAL,
                current_value=f"Bed: {self.property.bedrooms}, Bath: {self.property.bathrooms}",
                missing_detail="Missing bedroom or bathroom count",
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="No size information",
        )
    
    def check_rooms_identified(self, fact: RequiredFact) -> FactCheckResult:
        """Check if rooms have been identified."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        # Check for room-level memories
        room_names = set()
        for mem in self.memories:
            if mem.room_name:
                room_names.add(mem.room_name.lower())
        
        # Also check for general room list in notes
        for mem in self.memories:
            if mem.memory_type == PropertyMemoryType.NOTE:
                content_lower = mem.content.lower()
                # Look for room mentions
                common_rooms = ["kitchen", "bathroom", "bedroom", "living room", 
                               "dining room", "office", "laundry"]
                for room in common_rooms:
                    if room in content_lower:
                        room_names.add(room)
        
        room_count = len(room_names)
        min_required = fact.minimum_value or 2
        
        if room_count >= min_required:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=list(room_names),
            )
        elif room_count > 0:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.PARTIAL,
                current_value=list(room_names),
                missing_detail=f"Only {room_count} rooms identified, need at least {min_required}",
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="No rooms identified",
        )
    
    def check_priority_areas(self, fact: RequiredFact) -> FactCheckResult:
        """Check if priority areas have been identified."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        # Look for priority mentions in memories
        priorities = []
        for mem in self.memories:
            content_lower = mem.content.lower()
            if any(word in content_lower for word in ["priority", "important", "focus", "main concern"]):
                priorities.append(mem.content[:100])
        
        if priorities:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=priorities,
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="No priority areas specified",
        )
    
    def check_standards_discussed(self, fact: RequiredFact) -> FactCheckResult:
        """Check if any standards, rules, or preferences have been discussed."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        # Check for DO/DON'T rules, preferences, or sensitivities
        relevant_memories = [
            mem for mem in self.memories
            if mem.memory_type in [
                PropertyMemoryType.DO_RULE,
                PropertyMemoryType.DONT_RULE,
                PropertyMemoryType.PRODUCT_PREFERENCE,
                PropertyMemoryType.PERSONAL_SENSITIVITY,
            ]
        ]
        
        # Also check if they explicitly said "no special instructions"
        no_special = any(
            "no special" in mem.content.lower() or 
            "nothing special" in mem.content.lower()
            for mem in self.memories
        )
        
        if relevant_memories or no_special:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=len(relevant_memories),
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="No standards or rules discussed",
        )
    
    def check_product_preferences(self, fact: RequiredFact) -> FactCheckResult:
        """Check for product preferences."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        product_prefs = [
            mem for mem in self.memories
            if mem.memory_type == PropertyMemoryType.PRODUCT_PREFERENCE
        ]
        
        if product_prefs:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=[p.content[:50] for p in product_prefs],
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
        )
    
    def check_service_type(self, fact: RequiredFact) -> FactCheckResult:
        """Check if service type has been identified."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        # Look for service type mentions in notes
        service_keywords = {
            "regular": ["regular", "standard", "routine", "maintenance"],
            "deep": ["deep clean", "thorough", "detailed", "move-in", "move-out"],
            "specific": ["specific", "particular", "focus on"],
        }
        
        identified_service = None
        for mem in self.memories:
            content_lower = mem.content.lower()
            for service_type, keywords in service_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    identified_service = service_type
                    break
        
        if identified_service:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=identified_service,
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="Service type not specified",
        )
    
    def check_service_frequency(self, fact: RequiredFact) -> FactCheckResult:
        """Check if service frequency has been identified."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        # Look for frequency mentions
        frequency_keywords = {
            "weekly": ["weekly", "every week", "once a week"],
            "biweekly": ["biweekly", "bi-weekly", "every two weeks", "twice a month"],
            "monthly": ["monthly", "every month", "once a month"],
            "one-time": ["one time", "once", "single", "just this once"],
        }
        
        identified_frequency = None
        for mem in self.memories:
            content_lower = mem.content.lower()
            for freq_type, keywords in frequency_keywords.items():
                if any(kw in content_lower for kw in keywords):
                    identified_frequency = freq_type
                    break
        
        if identified_frequency:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=identified_frequency,
            )
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
        )
    
    def check_access_method(self, fact: RequiredFact) -> FactCheckResult:
        """Check if access method has been specified."""
        if not self.property:
            return FactCheckResult(fact=fact, status=FactStatus.MISSING)
        
        # Check property access_instructions
        if self.property.access_instructions:
            return FactCheckResult(
                fact=fact,
                status=FactStatus.COMPLETE,
                current_value=self.property.access_instructions[:100],
            )
        
        # Look in memories for access info
        access_keywords = ["key", "code", "lockbox", "doorman", "buzzer", "home", "access", "entry"]
        for mem in self.memories:
            if any(kw in mem.content.lower() for kw in access_keywords):
                return FactCheckResult(
                    fact=fact,
                    status=FactStatus.COMPLETE,
                    current_value=mem.content[:100],
                )
        
        return FactCheckResult(
            fact=fact,
            status=FactStatus.MISSING,
            missing_detail="No access method specified",
        )
    
    def check_all_facts(self) -> OnboardingFactStatus:
        """
        Check all required facts and determine overall status.
        
        Returns comprehensive status including what's missing and what to collect next.
        """
        results = []
        missing_critical = []
        missing_optional = []
        
        for fact in REQUIRED_FACTS:
            # Get the check function by name
            check_func = getattr(self, fact.check_function, None)
            if not check_func:
                # Fallback if function doesn't exist
                result = FactCheckResult(
                    fact=fact,
                    status=FactStatus.MISSING,
                    missing_detail="Check function not implemented",
                )
            else:
                result = check_func(fact)
            
            results.append(result)
            
            if not result.is_complete:
                if fact.is_critical:
                    missing_critical.append(fact)
                else:
                    missing_optional.append(fact)
        
        # Calculate completion
        total_critical = sum(1 for f in REQUIRED_FACTS if f.is_critical)
        complete_critical = sum(
            1 for r in results 
            if r.fact.is_critical and r.is_complete
        )
        
        total_facts = len(REQUIRED_FACTS)
        complete_facts = sum(1 for r in results if r.is_complete)
        
        # Determine if ready to proceed
        all_critical_complete = len(missing_critical) == 0
        ready = all_critical_complete and self.property is not None
        
        # Determine next fact to collect (prioritize critical)
        next_fact = None
        if missing_critical:
            # Order by category priority
            category_order = [
                FactCategory.PROPERTY,
                FactCategory.SERVICE,
                FactCategory.ROOMS,
                FactCategory.ACCESS,
                FactCategory.STANDARDS,
            ]
            for cat in category_order:
                for fact in missing_critical:
                    if fact.category == cat:
                        next_fact = fact
                        break
                if next_fact:
                    break
        elif missing_optional:
            next_fact = missing_optional[0]
        
        return OnboardingFactStatus(
            property_exists=self.property is not None,
            all_critical_facts_complete=all_critical_complete,
            fact_results=results,
            missing_critical_facts=missing_critical,
            missing_optional_facts=missing_optional,
            completion_percentage=(complete_facts / total_facts * 100) if total_facts > 0 else 100.0,
            ready_to_proceed=ready,
            next_fact_to_collect=next_fact,
        )


def get_missing_facts_summary(fact_status: OnboardingFactStatus) -> str:
    """
    Generate a human-readable summary of missing facts for AI context.
    """
    if fact_status.ready_to_proceed:
        return "All required information has been collected. Ready to proceed with service setup."
    
    lines = []
    
    if not fact_status.property_exists:
        lines.append("- Need to create property record with address")
    
    # Group missing facts by category
    by_category: Dict[str, List[str]] = {}
    for fact in fact_status.missing_critical_facts:
        cat = fact.category.value.replace("_", " ").title()
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(fact.description)
    
    for cat, items in by_category.items():
        lines.append(f"\n{cat}:")
        for item in items:
            lines.append(f"  - {item}")
    
    if lines:
        return "Still need to collect:\n" + "\n".join(lines)
    return "All required information collected."


def get_next_question_hint(fact_status: OnboardingFactStatus) -> Optional[str]:
    """
    Get a hint for the next question to ask based on missing facts.
    """
    if fact_status.ready_to_proceed:
        return "Ask if there's anything else they'd like to share about their home."
    
    if fact_status.next_fact_to_collect:
        fact = fact_status.next_fact_to_collect
        if fact.prompt_hints:
            return fact.prompt_hints[0]
    
    return None
