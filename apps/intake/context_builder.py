"""
Builds structured, repeatable context for AI intake conversations.

Assembles:
- Home memory (what we know)
- Onboarding progress (what we still need)
- Recent conversation context
- Pending proposals (to avoid repetition)
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json

from apps.intake.models import (
    IntakeSession,
    IntakeMessage,
    UpdateProposal,
    UpdateProposalStatus,
    MessageRole,
)
from apps.intake.onboarding_tracker import OnboardingTracker, OnboardingProgress
from apps.intake.onboarding_schema import (
    OnboardingCategory,
    FieldPriority,
    get_onboarding_schema,
)


@dataclass
class IntakeContext:
    """Complete context for an intake conversation turn."""
    session_id: str
    home_memory_summary: str
    onboarding_progress: OnboardingProgress
    pending_proposals_summary: str
    conversation_messages: List[Dict[str, str]]
    system_rules: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "home_memory_summary": self.home_memory_summary,
            "onboarding_progress": self.onboarding_progress.to_dict(),
            "pending_proposals_summary": self.pending_proposals_summary,
            "message_count": len(self.conversation_messages),
        }


class IntakeContextBuilder:
    """
    Builds structured context for intake AI calls.
    
    Designed to be repeatable - same inputs produce same context structure.
    """
    
    # How many recent messages to include
    DEFAULT_MESSAGE_LIMIT = 20
    
    def __init__(self, session: IntakeSession):
        self.session = session
        self.tracker = OnboardingTracker(session)
    
    def _get_recent_messages(self, limit: int = DEFAULT_MESSAGE_LIMIT) -> List[IntakeMessage]:
        """Get recent messages for conversation context."""
        messages = IntakeMessage.objects.filter(
            session=self.session
        ).order_by("-sequence_number")[:limit]
        
        return list(reversed(messages))
    
    def _format_messages_for_llm(
        self, 
        messages: List[IntakeMessage]
    ) -> List[Dict[str, str]]:
        """Format messages for LLM consumption."""
        formatted = []
        for msg in messages:
            formatted.append({
                "role": msg.role,
                "content": msg.content,
            })
        return formatted
    
    def _get_pending_proposals_summary(self) -> str:
        """
        Get summary of pending proposals to prevent repetition.
        
        Groups proposals by type for cleaner presentation.
        """
        proposals = UpdateProposal.objects.filter(
            session=self.session,
            status=UpdateProposalStatus.PENDING,
        ).order_by("created_at")
        
        if not proposals:
            return "No pending proposals."
        
        # Group by type
        by_type: Dict[str, List[str]] = {}
        for p in proposals:
            type_label = p.get_proposal_type_display()
            if type_label not in by_type:
                by_type[type_label] = []
            by_type[type_label].append(p.summary or str(p.proposed_data)[:100])
        
        lines = ["Pending proposed updates (already captured, don't repeat):"]
        for type_label, summaries in by_type.items():
            lines.append(f"\n{type_label}:")
            for s in summaries[:5]:  # Limit per type
                lines.append(f"  - {s}")
        
        return "\n".join(lines)
    
    def _get_system_rules(self) -> Dict[str, Any]:
        """
        Get system rules for the intake conversation.
        
        These define what the AI can/can't do and how to behave.
        """
        # Check session context for custom rules
        custom_rules = self.session.system_context.get("rules", {})
        
        default_rules = {
            "tone": "friendly and conversational",
            "response_length": "brief, 1-3 sentences per response",
            "questions_per_turn": "1-2 questions maximum",
            "can_do": [
                "Ask about the home and preferences",
                "Confirm understanding of what user said",
                "Propose updates based on user information",
                "Guide the conversation toward complete intake",
            ],
            "cannot_do": [
                "Make up information not provided by user",
                "Promise specific services or pricing",
                "Skip required information without user consent",
                "Ask more than 2 questions at once",
            ],
            "response_format": "JSON with assistant_reply and proposed_updates",
        }
        
        # Merge custom rules over defaults
        rules = {**default_rules, **custom_rules}
        return rules
    
    def _get_next_topic_guidance(self, progress: OnboardingProgress) -> str:
        """
        Generate guidance for what to ask about next.
        """
        if not progress.suggested_next_fields:
            if progress.required_completion >= 100:
                return "All required information collected. Ask if there's anything else they'd like to share about their home, or if they're ready to wrap up."
            return "Continue gathering any remaining details."
        
        topic = progress.suggested_next_topic or "general"
        fields = progress.suggested_next_fields
        
        # Map category to natural language
        topic_intros = {
            "property_basics": "basic property information",
            "access": "how technicians will access the property",
            "rooms": "the rooms in the home",
            "surfaces": "the types of surfaces and materials",
            "preferences": "cleaning product preferences",
            "priorities": "priority areas and concerns",
            "special_instructions": "any special instructions or notes",
        }
        
        topic_phrase = topic_intros.get(topic, topic.replace("_", " "))
        field_labels = [f.label for f in fields[:3]]
        
        guidance = f"Next, learn about {topic_phrase}."
        if field_labels:
            guidance += f" Specifically: {', '.join(field_labels)}."
        
        return guidance
    
    def build_context(self, message_limit: int = DEFAULT_MESSAGE_LIMIT) -> IntakeContext:
        """
        Build the complete context for an intake conversation turn.
        
        This is the main entry point - produces a structured, repeatable context.
        """
        # Get onboarding progress
        progress = self.tracker.calculate_progress()
        
        #  Get home memory summary
        home_memory = self.tracker.get_context_summary()
        
        # Get recent messages
        messages = self._get_recent_messages(message_limit)
        formatted_messages = self._format_messages_for_llm(messages)
        
        # Get pending proposals summary
        proposals_summary = self._get_pending_proposals_summary()
        
        # Get system rules
        rules = self._get_system_rules()
        
        return IntakeContext(
            session_id=str(self.session.id),
            home_memory_summary=home_memory,
            onboarding_progress=progress,
            pending_proposals_summary=proposals_summary,
            conversation_messages=formatted_messages,
            system_rules=rules,
        )
    
    def build_system_prompt(self, context: IntakeContext) -> str:
        """
        Build the system prompt from context.
        
        This is the repeatable prompt structure that produces consistent behavior.
        """
        progress = context.onboarding_progress
        next_guidance = self._get_next_topic_guidance(progress)
        
        prompt = f"""You are an intake assistant helping a homeowner set up their home profile for a cleaning service.

## YOUR ROLE
- Have a natural, friendly conversation to gather information about their home
- Keep responses brief (1-3 sentences) and conversational
- Ask 1-2 questions at a time, never overwhelm
- Acknowledge what the user shares before asking more

## CURRENT HOME PROFILE
{context.home_memory_summary}

## ONBOARDING STATUS
Overall completion: {progress.overall_completion:.0f}%
Required fields completion: {progress.required_completion:.0f}%

## NEXT STEPS
{next_guidance}

## ALREADY CAPTURED (don't repeat these)
{context.pending_proposals_summary}

## RULES
- Only record information the user explicitly provides
- Don't make assumptions or fill in gaps
- If unsure, ask for clarification
- Keep the conversation moving forward
- Be warm but efficient

## RESPONSE FORMAT
You MUST respond with valid JSON in exactly this format:
{{
    "assistant_reply": "Your conversational response here",
    "proposed_updates": [
        {{
            "type": "property_update|memory_create|room_create|preference_create",
            "target_type": "property|room|memory|preference",
            "target_id": null,
            "data": {{"field": "value"}},
            "summary": "Brief description of what this captures"
        }}
    ]
}}

IMPORTANT:
- assistant_reply: Your natural response to continue the conversation
- proposed_updates: Array of updates based ONLY on what user said (can be empty)
- Valid types: 
  * property_create, property_update (for Home/Property)
  * room_create, room_update (for Rooms)
  * memory_create, memory_update (for general notes)
  * preference_create, preference_update (for product preferences)
  * do_rule_create, do_rule_update (for explicit "do" rules)
  * dont_rule_create, dont_rule_update (for explicit "don't" rules)
  * photo_create, photo_update (for reference photos - ideal state or problem zones)
- For memory_create, include memory_type: "note", "do_rule", "dont_rule", "product_preference", "personal_sensitivity"
- For photo_create: Use when user shares photos. Include photo_type: "ideal_condition" or "problem_zone"
- For do_rule/dont_rule: Use explicit types when user clearly states rules (e.g., "always do X" or "never do Y")
"""
        
        return prompt
    
    def build_llm_messages(
        self, 
        context: IntakeContext,
        include_system: bool = True
    ) -> List[Dict[str, str]]:
        """
        Build the complete message array for LLM call.
        """
        messages = []
        
        if include_system:
            system_prompt = self.build_system_prompt(context)
            messages.append({"role": "system", "content": system_prompt})
        
        # Add conversation history
        messages.extend(context.conversation_messages)
        
        return messages
