"""
Intake session services for managing chat sessions and AI interactions.

Enhanced with structured onboarding tracking and context assembly.
"""
import json
from typing import Optional, List, Dict, Any, Tuple
from django.db import transaction
from django.utils import timezone
from django.db.models import F

from apps.intake.models import (
    IntakeSession,
    IntakeSessionStatus,
    IntakeMessage,
    MessageRole,
    UpdateProposal,
    UpdateProposalStatus,
    UpdateProposalType,
)
from apps.intake.context_builder import IntakeContextBuilder, IntakeContext
from apps.intake.onboarding_tracker import OnboardingTracker, OnboardingProgress
from apps.intake.fact_requirements import (
    OnboardingFactChecker,
    OnboardingFactStatus,
    get_missing_facts_summary,
    get_next_question_hint,
)
from apps.properties.models import Property, PropertyMemory
from apps.users.models import User
from llm.services.llm_service import LLMService
from datetime import timedelta
import structlog

logger = structlog.get_logger(__name__)


class IntakeSessionService:
    """Service for managing intake sessions."""
    
    @staticmethod
    @transaction.atomic
    def create_session(
        client: User,
        property_id: Optional[str] = None,
        title: Optional[str] = None,
        system_context: Optional[Dict[str, Any]] = None,
    ) -> IntakeSession:
        """
        Create a new intake session for a client.
        
        Args:
            client: The client user
            property_id: Optional property UUID to associate with
            title: Optional title for the session
            system_context: Optional system rules/context
            
        Returns:
            The created IntakeSession
        """
        property_obj = None
        if property_id:
            try:
                property_obj = Property.objects.get(
                    id=property_id,
                    tenant=client.tenant
                )
            except Property.DoesNotExist:
                logger.warning(
                    "property_not_found_for_intake",
                    property_id=property_id,
                    client_id=str(client.id)
                )
        
        # Initialize system context with onboarding state
        ctx = system_context or {}
        if "collected_data" not in ctx:
            ctx["collected_data"] = {}
        if "onboarding_started_at" not in ctx:
            ctx["onboarding_started_at"] = timezone.now().isoformat()
        
        session = IntakeSession.objects.create(
            tenant=client.tenant,
            client=client,
            property=property_obj,
            title=title or "",
            status=IntakeSessionStatus.ACTIVE,
            system_context=ctx,
            property_locked=bool(property_obj),  # Lock if property provided
        )
        
        logger.info(
            "intake_session_created",
            session_id=str(session.id),
            client_id=str(client.id),
            property_id=str(property_obj.id) if property_obj else None,
            property_locked=bool(property_obj)
        )
        
        return session
    
    @staticmethod
    def get_session(session_id: str, client: User) -> Optional[IntakeSession]:
        """
        Get a session by ID, ensuring it belongs to the client.
        
        Args:
            session_id: The session UUID
            client: The client user (for authorization)
            
        Returns:
            The IntakeSession or None if not found/unauthorized
        """
        try:
            return IntakeSession.objects.select_related("property").get(
                id=session_id,
                client=client,
                tenant=client.tenant,
            )
        except IntakeSession.DoesNotExist:
            return None
    
    @staticmethod
    def list_sessions(
        client: User,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Tuple[List[IntakeSession], int]:
        """
        List sessions for a client.
        
        Args:
            client: The client user
            status: Optional status filter
            limit: Max results to return
            offset: Pagination offset
            
        Returns:
            Tuple of (sessions list, total count)
        """
        queryset = IntakeSession.objects.filter(
            client=client,
            tenant=client.tenant,
        ).select_related("property")
        
        if status:
            queryset = queryset.filter(status=status)
        
        total = queryset.count()
        sessions = list(queryset[offset:offset + limit])
        
        return sessions, total
    
    @staticmethod
    @transaction.atomic
    def update_session_status(
        session: IntakeSession,
        status: str,
    ) -> IntakeSession:
        """Update session status."""
        session.status = status
        session.save(update_fields=["status", "updated_at"])
        return session
    
    @staticmethod
    def get_onboarding_progress(session: IntakeSession) -> OnboardingProgress:
        """Get the current onboarding progress for a session."""
        tracker = OnboardingTracker(session)
        return tracker.calculate_progress()
    
    @staticmethod
    def check_onboarding_facts(
        session: IntakeSession,
        use_cache: bool = True,
        cache_duration_minutes: int = 5,
    ) -> OnboardingFactStatus:
        """
        Check if all required onboarding facts exist in stored memory.
        
        Args:
            session: The intake session
            use_cache: Whether to use cached results if recent
            cache_duration_minutes: How long to cache results
            
        Returns:
            OnboardingFactStatus with complete fact checking results
        """
        # Check cache if enabled
        if use_cache and session.fact_check_cache_updated_at:
            cache_age = timezone.now() - session.fact_check_cache_updated_at
            if cache_age < timedelta(minutes=cache_duration_minutes):
                # Return cached results
                cached = session.fact_check_cache
                if cached and "ready_to_proceed" in cached:
                    # Reconstruct from cache (simplified version)
                    return OnboardingFactStatus(
                        property_exists=cached.get("property_exists", False),
                        all_critical_facts_complete=cached.get("all_critical_facts_complete", False),
                        fact_results=[],  # Skip detailed results in cache
                        missing_critical_facts=[],
                        missing_optional_facts=[],
                        completion_percentage=cached.get("completion_percentage", 0),
                        ready_to_proceed=cached.get("ready_to_proceed", False),
                        next_fact_to_collect=None,
                    )
        
        # Perform fresh fact checking
        checker = OnboardingFactChecker(property_obj=session.property)
        fact_status = checker.check_all_facts()
        
        # Update cache
        session.fact_check_cache = fact_status.to_dict()
        session.fact_check_cache_updated_at = timezone.now()
        session.save(update_fields=["fact_check_cache", "fact_check_cache_updated_at"])
        
        # Update onboarding_complete if needed
        if fact_status.ready_to_proceed and not session.onboarding_complete:
            session.onboarding_complete = True
            session.onboarding_completed_at = timezone.now()
            session.save(update_fields=["onboarding_complete", "onboarding_completed_at"])
            
            logger.info(
                "onboarding_marked_complete",
                session_id=str(session.id),
                property_id=str(session.property.id) if session.property else None,
            )
        
        return fact_status
    
    @staticmethod
    @transaction.atomic
    def apply_proposal_and_recheck(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> OnboardingFactStatus:
        """
        Apply a proposal and recheck facts.
        
        This is a placeholder for the actual proposal application logic.
        After applying, it rechecks facts to update completion status.
        """
        # TODO: Implement actual proposal application logic
        # This would create/update Property, PropertyMemory, etc.
        
        proposal.status = UpdateProposalStatus.APPLIED
        proposal.reviewed_by = applied_by
        proposal.reviewed_at = timezone.now()
        proposal.save()
        
        # Recheck facts after applying
        return IntakeSessionService.check_onboarding_facts(
            proposal.session,
            use_cache=False,  # Force fresh check
        )
    
    @staticmethod
    def get_intake_outcome(session: IntakeSession) -> 'IntakeOutcome':
        """
        Get the current intake outcome for a session.
        
        Returns only applied/stored data - no pending proposals or chat text.
        Ready for consumption by pricing, booking, operator review, and client UI.
        
        Args:
            session: The intake session
            
        Returns:
            IntakeOutcome containing all stored data and readiness status
        """
        from apps.intake.outcome import IntakeOutcomeBuilder
        
        builder = IntakeOutcomeBuilder(session)
        return builder.build()


class IntakeMessageService:
    """Service for managing intake messages."""
    
    @staticmethod
    def _get_next_sequence_number(session: IntakeSession) -> int:
        """Get the next sequence number for a message in this session."""
        last_message = IntakeMessage.objects.filter(
            session=session
        ).order_by("-sequence_number").first()
        
        return (last_message.sequence_number + 1) if last_message else 1
    
    @staticmethod
    @transaction.atomic
    def create_user_message(
        session: IntakeSession,
        content: str,
        media_attachments: Optional[List[Dict[str, str]]] = None,
    ) -> IntakeMessage:
        """
        Create a user message in the session.
        
        This is called BEFORE any AI processing - the user message
        is persisted first for reliability.
        
        Args:
            session: The intake session
            content: Text content of the message
            media_attachments: Optional list of media references
                [{blob_name, content_type, file_name}]
                
        Returns:
            The created IntakeMessage
        """
        sequence_number = IntakeMessageService._get_next_sequence_number(session)
        
        message = IntakeMessage.objects.create(
            tenant=session.tenant,
            session=session,
            role=MessageRole.USER,
            content=content,
            media_attachments=media_attachments or [],
            sequence_number=sequence_number,
            metadata={},
        )
        
        # Update session counters
        IntakeSession.objects.filter(id=session.id).update(
            message_count=F("message_count") + 1,
            last_message_at=timezone.now(),
            updated_at=timezone.now(),
        )
        
        logger.info(
            "user_message_created",
            session_id=str(session.id),
            message_id=str(message.id),
            sequence=sequence_number,
            has_media=bool(media_attachments),
        )
        
        return message
    
    @staticmethod
    @transaction.atomic
    def create_assistant_message(
        session: IntakeSession,
        content: str,
        in_reply_to: IntakeMessage,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IntakeMessage:
        """
        Create an assistant message in the session.
        
        Args:
            session: The intake session
            content: Text content of the message
            in_reply_to: The user message this responds to
            metadata: Optional metadata (model used, tokens, etc.)
            
        Returns:
            The created IntakeMessage
        """
        sequence_number = IntakeMessageService._get_next_sequence_number(session)
        
        message = IntakeMessage.objects.create(
            tenant=session.tenant,
            session=session,
            role=MessageRole.ASSISTANT,
            content=content,
            in_reply_to=in_reply_to,
            media_attachments=[],
            sequence_number=sequence_number,
            metadata=metadata or {},
        )
        
        # Update session counters
        IntakeSession.objects.filter(id=session.id).update(
            message_count=F("message_count") + 1,
            last_message_at=timezone.now(),
            updated_at=timezone.now(),
        )
        
        logger.info(
            "assistant_message_created",
            session_id=str(session.id),
            message_id=str(message.id),
            sequence=sequence_number,
            in_reply_to=str(in_reply_to.id),
        )
        
        return message
    
    @staticmethod
    def get_recent_messages(
        session: IntakeSession,
        limit: int = 20,
    ) -> List[IntakeMessage]:
        """
        Get the most recent messages from a session.
        
        Args:
            session: The intake session
            limit: Max number of messages to return
            
        Returns:
            List of messages, oldest first (for context building)
        """
        messages = IntakeMessage.objects.filter(
            session=session
        ).order_by("-sequence_number")[:limit]
        
        # Reverse to get chronological order
        return list(reversed(messages))
    
    @staticmethod
    @transaction.atomic
    def create_system_message(
        session: IntakeSession,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> IntakeMessage:
        """Create a system message (for internal notes/state)."""
        sequence_number = IntakeMessageService._get_next_sequence_number(session)
        
        message = IntakeMessage.objects.create(
            tenant=session.tenant,
            session=session,
            role=MessageRole.SYSTEM,
            content=content,
            media_attachments=[],
            sequence_number=sequence_number,
            metadata=metadata or {},
        )
        
        return message
    
    @staticmethod
    def get_all_messages(session: IntakeSession) -> List[IntakeMessage]:
        """Get all messages for a session in order."""
        return list(
            IntakeMessage.objects.filter(session=session)
            .order_by("sequence_number")
        )


class UpdateProposalService:
    """Service for managing update proposals."""
    
    @staticmethod
    @transaction.atomic
    def create_proposals(
        session: IntakeSession,
        source_message: IntakeMessage,
        proposals_data: List[Dict[str, Any]],
    ) -> List[UpdateProposal]:
        """
        Create update proposals from AI response.
        
        Args:
            session: The intake session
            source_message: The assistant message that generated these
            proposals_data: List of proposal dicts from AI
            
        Returns:
            List of created UpdateProposal objects
        """
        created_proposals = []
        
        for proposal_data in proposals_data:
            proposal_type = proposal_data.get("type", "")
            target_type = proposal_data.get("target_type", "")
            target_id = proposal_data.get("target_id")
            data = proposal_data.get("data", {})
            summary = proposal_data.get("summary", "")
            
            # Validate proposal type
            valid_types = [t.value for t in UpdateProposalType]
            if proposal_type not in valid_types:
                logger.warning(
                    "invalid_proposal_type",
                    proposal_type=proposal_type,
                    valid_types=valid_types,
                    session_id=str(session.id)
                )
                continue
            
            # Skip empty proposals
            if not data:
                continue
            
            # Compute content hash for deduplication
            content_hash = UpdateProposal.compute_content_hash(data)
            
            # Check for duplicate pending proposals
            existing = UpdateProposal.objects.filter(
                session=session,
                content_hash=content_hash,
                status=UpdateProposalStatus.PENDING,
            ).exists()
            
            if existing:
                logger.info(
                    "duplicate_proposal_skipped",
                    content_hash=content_hash[:16],
                    session_id=str(session.id)
                )
                continue
            
            proposal = UpdateProposal.objects.create(
                tenant=session.tenant,
                session=session,
                source_message=source_message,
                proposal_type=proposal_type,
                status=UpdateProposalStatus.PENDING,
                target_entity_id=target_id,
                target_entity_type=target_type,
                proposed_data=data,
                content_hash=content_hash,
                summary=summary,
            )
            
            created_proposals.append(proposal)
            
            logger.info(
                "update_proposal_created",
                proposal_id=str(proposal.id),
                proposal_type=proposal_type,
                summary=summary[:50] if summary else "",
                session_id=str(session.id),
            )
        
        return created_proposals
    
    @staticmethod
    def get_pending_proposals(session: IntakeSession) -> List[UpdateProposal]:
        """Get all pending proposals for a session."""
        return list(
            UpdateProposal.objects.filter(
                session=session,
                status=UpdateProposalStatus.PENDING,
            ).order_by("created_at")
        )
    
    @staticmethod
    def get_proposals_by_message(message: IntakeMessage) -> List[UpdateProposal]:
        """Get proposals generated by a specific message."""
        return list(
            UpdateProposal.objects.filter(
                source_message=message,
            ).order_by("created_at")
        )


class IntakeChatService:
    """Service for orchestrating intake chat interactions."""
    
    # How many messages to include as context
    CONTEXT_MESSAGE_LIMIT = 20
    
    @staticmethod
    def _parse_ai_response(response_content: str) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parse the AI response JSON.
        
        Handles various edge cases and malformed responses.
        """
        # Try to extract JSON from the response
        content = response_content.strip()
        
        # Handle markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            parsed = json.loads(content)
            assistant_reply = parsed.get("assistant_reply", "")
            proposed_updates = parsed.get("proposed_updates", [])
            
            if not assistant_reply:
                logger.warning(
                    "ai_response_missing_reply",
                    response=response_content[:200]
                )
                # Try to use the whole response as reply if parsing partially worked
                if isinstance(parsed, dict):
                    assistant_reply = "I'd be happy to help. Could you tell me more?"
            
            # Ensure proposed_updates is a list
            if not isinstance(proposed_updates, list):
                proposed_updates = []
            
            return assistant_reply, proposed_updates
            
        except json.JSONDecodeError as e:
            logger.error(
                "ai_response_parse_error",
                error=str(e),
                response=response_content[:500]
            )
            # Return the raw response as the reply if parsing fails
            # Clean up any partial JSON
            if "{" in response_content:
                # Try to extract just text before JSON
                text_part = response_content.split("{")[0].strip()
                if text_part:
                    return text_part, []
            return response_content, []
    
    @staticmethod
    async def process_user_message(
        session: IntakeSession,
        user_message: IntakeMessage,
    ) -> Tuple[IntakeMessage, List[UpdateProposal], OnboardingProgress]:
        """
        Process a user message and generate AI response.
        
        This is called AFTER the user message is already persisted.
        
        Returns:
            Tuple of (assistant message, list of created proposals, updated progress)
        """
        # Build context using the context builder
        context_builder = IntakeContextBuilder(session)
        context = context_builder.build_context(
            message_limit=IntakeChatService.CONTEXT_MESSAGE_LIMIT
        )
        
        # Build LLM messages
        llm_messages = context_builder.build_llm_messages(context)
        
        logger.info(
            "calling_llm_for_intake",
            session_id=str(session.id),
            message_count=len(llm_messages),
            user_message_id=str(user_message.id),
            onboarding_completion=context.onboarding_progress.overall_completion,
        )
        
        # Call the LLM
        try:
            response = await LLMService.chat_completion(
                messages=llm_messages,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=800,  # Keep responses concise
                stream=False,
            )
            
            response_content = response.get("content", "")
            usage = response.get("usage", {})
            
            logger.info(
                "llm_response_received",
                session_id=str(session.id),
                response_length=len(response_content),
                tokens_used=usage.get("total_tokens") if usage else None,
            )
            
        except Exception as e:
            logger.error(
                "llm_call_failed",
                session_id=str(session.id),
                error=str(e),
                exc_info=True
            )
            # Create a fallback response
            response_content = json.dumps({
                "assistant_reply": "I'm sorry, I had a brief hiccup. Could you repeat that?",
                "proposed_updates": []
            })
            usage = {}
        
        # Parse the response
        assistant_reply, proposed_updates = IntakeChatService._parse_ai_response(
            response_content
        )
        
        # Create assistant message
        assistant_message = IntakeMessageService.create_assistant_message(
            session=session,
            content=assistant_reply,
            in_reply_to=user_message,
            metadata={
                "model": "gpt-4o-mini",
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens") if usage else None,
                    "completion_tokens": usage.get("completion_tokens") if usage else None,
                    "total_tokens": usage.get("total_tokens") if usage else None,
                } if usage else {},
                "raw_response_length": len(response_content),
                "context_snapshot": context.to_dict(),
            },
        )
        
        # Create update proposals (if any)
        created_proposals = []
        if proposed_updates:
            created_proposals = UpdateProposalService.create_proposals(
                session=session,
                source_message=assistant_message,
                proposals_data=proposed_updates,
            )
        
        # Recalculate progress after proposals
        updated_progress = context_builder.tracker.calculate_progress()
        
        return assistant_message, created_proposals, updated_progress
    
    @staticmethod
    def _build_fact_based_context(
        session: IntakeSession,
        fact_status: OnboardingFactStatus,
    ) -> str:
        """
        Build AI context focused on missing facts.
        
        This guides the AI to focus only on closing gaps in required facts.
        """
        if fact_status.ready_to_proceed:
            return """
All required information has been collected! The home profile is ready.

Now just check if there's anything else the user wants to share:
- Any special concerns or requests?
- Any questions about the service?
- Anything we haven't covered that's important to them?

If they have nothing else to add, you can let them know the profile is complete.
"""
        
        missing_summary = get_missing_facts_summary(fact_status)
        next_hint = get_next_question_hint(fact_status)
        
        context = f"""
## ONBOARDING STATUS
Completion: {fact_status.completion_percentage:.0f}%
Property Exists: {'Yes' if fact_status.property_exists else 'No - Need address to create property'}

## WHAT'S STILL NEEDED
{missing_summary}

## NEXT QUESTION TO ASK
{next_hint or "Continue gathering the missing information listed above."}

## IMPORTANT
- Focus ONLY on collecting the missing required information
- Don't re-ask about things already collected
- Keep questions brief and natural
- One topic at a time
"""
        return context
    
    @staticmethod
    async def process_user_message_with_facts(
        session: IntakeSession,
        user_message: IntakeMessage,
    ) -> Tuple[IntakeMessage, List[UpdateProposal], OnboardingFactStatus]:
        """
        Enhanced message processing that uses fact-based tracking.
        
        This version:
        1. Checks what facts exist in stored memory
        2. Focuses AI only on missing facts
        3. Returns fact status with response
        """
        # Check current fact status
        fact_status = IntakeSessionService.check_onboarding_facts(session)
        
        # Build fact-focused context
        fact_context = IntakeChatService._build_fact_based_context(
            session, fact_status
        )
        
        # Build regular context
        context_builder = IntakeContextBuilder(session)
        context = context_builder.build_context(
            message_limit=IntakeChatService.CONTEXT_MESSAGE_LIMIT
        )
        
        # Modify system prompt to include fact focus
        system_prompt = f"""You are an intake assistant helping complete a home profile for a cleaning service.

## FACT-BASED GUIDANCE
{fact_context}

## YOUR ROLE
- Focus on collecting missing required information
- Keep responses brief and conversational
- Ask about ONE topic at a time
- Don't repeat questions about information already stored
- When all required facts are collected, ask if there's anything else

## CURRENT HOME PROFILE
{context.home_memory_summary}

## ALREADY CAPTURED (don't ask about these again)
{context.pending_proposals_summary}

## RESPONSE FORMAT
You MUST respond with valid JSON:
{{
    "assistant_reply": "Your conversational response",
    "proposed_updates": [
        {{
            "type": "property_create|property_update|memory_create|preference_create",
            "target_type": "property|memory|preference",
            "target_id": null,
            "data": {{"field": "value"}},
            "summary": "What this captures"
        }}
    ]
}}

CRITICAL RULES:
- If the user provides an address and no property exists, create one with type "property_create"
- If discussing rooms, create memories with memory_type "note" and room_name filled
- If discussing service preferences, note them as memory_type "note" with content
- If discussing access, update property with access_instructions
- If user says "no special instructions" or similar, still record it as a memory
"""
        
        # Build messages with modified system prompt
        llm_messages = [
            {"role": "system", "content": system_prompt}
        ] + context.conversation_messages
        
        logger.info(
            "calling_llm_with_fact_focus",
            session_id=str(session.id),
            fact_completion=fact_status.completion_percentage,
            ready_to_proceed=fact_status.ready_to_proceed,
            missing_critical=len(fact_status.missing_critical_facts),
        )
        
        # Call the LLM
        try:
            response = await LLMService.chat_completion(
                messages=llm_messages,
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=800,
                stream=False,
            )
            
            response_content = response.get("content", "")
            usage = response.get("usage", {})
            
        except Exception as e:
            logger.error(
                "llm_call_failed",
                session_id=str(session.id),
                error=str(e),
            )
            response_content = json.dumps({
                "assistant_reply": "I'm sorry, I had a brief hiccup. Could you repeat that?",
                "proposed_updates": []
            })
            usage = {}
        
        # Parse response
        assistant_reply, proposed_updates = IntakeChatService._parse_ai_response(
            response_content
        )
        
        # If onboarding is complete and this is the wrap-up, adjust the message
        if fact_status.ready_to_proceed and "complete" in assistant_reply.lower():
            # Mark session as ready for next phase
            if session.status == IntakeSessionStatus.ACTIVE:
                session.status = IntakeSessionStatus.COMPLETED
                session.save(update_fields=["status", "updated_at"])
        
        # Create assistant message
        assistant_message = IntakeMessageService.create_assistant_message(
            session=session,
            content=assistant_reply,
            in_reply_to=user_message,
            metadata={
                "model": "gpt-4o-mini",
                "usage": usage if usage else {},
                "fact_status_snapshot": fact_status.to_dict(),
            },
        )
        
        # Create proposals
        created_proposals = []
        if proposed_updates:
            created_proposals = UpdateProposalService.create_proposals(
                session=session,
                source_message=assistant_message,
                proposals_data=proposed_updates,
            )
        
        # Recheck facts after proposals (they're not applied yet, but cache is expired)
        updated_fact_status = IntakeSessionService.check_onboarding_facts(
            session,
            use_cache=False,
        )
        
        return assistant_message, created_proposals, updated_fact_status
    
    @staticmethod
    async def generate_greeting(session: IntakeSession) -> IntakeMessage:
        """
        Generate an initial greeting message for a new session.
        
        This creates the first assistant message to start the conversation.
        """
        # Build context to understand what we already know
        context_builder = IntakeContextBuilder(session)
        progress = context_builder.tracker.calculate_progress()
        
        # Determine appropriate greeting based on existing data
        if progress.overall_completion > 50:
            greeting = "Welcome back! I see we've already gathered quite a bit about your home. Let's pick up where we left off."
        elif session.property:
            greeting = f"Hi! I see you're setting up your profile for {session.property.address}. I'll help gather some details to make sure our team takes great care of your home. First, could you tell me a bit about the layout - how many bedrooms and bathrooms?"
        else:
            greeting = "Hi! I'm here to help set up your home profile. This helps our team know exactly how to take care of your space. Let's start simple - what's the address of the property?"
        
        # Create as system-generated assistant message
        message = IntakeMessage.objects.create(
            tenant=session.tenant,
            session=session,
            role=MessageRole.ASSISTANT,
            content=greeting,
            media_attachments=[],
            sequence_number=1,
            metadata={
                "type": "greeting",
                "auto_generated": True,
                "onboarding_completion_at_start": progress.overall_completion,
            },
        )
        
        # Update session counters
        IntakeSession.objects.filter(id=session.id).update(
            message_count=1,
            last_message_at=timezone.now(),
            updated_at=timezone.now(),
        )
        
        return message
