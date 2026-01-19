"""
API views for intake sessions.
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from asgiref.sync import async_to_sync

from apps.users.authentication import SupabaseAuthentication
from apps.users.models import UserRole
from apps.intake.models import (
    IntakeSession, 
    IntakeSessionStatus,
    IntakeMessageUsage,
    IntakeMessage,
    MessageRole,
)
from apps.intake.services import (
    IntakeSessionService,
    IntakeMessageService,
    IntakeChatService,
    UpdateProposalService,
)
from apps.intake.services.proposal_application import (
    ProposalApplicationService,
    ProposalApplicationError,
    ProposalValidationError,
)
from apps.intake.services.intake_output import IntakeOutputService
from apps.intake.fact_requirements import (
    get_missing_facts_summary,
    get_next_question_hint,
)
from apps.intake.serializers import (
    IntakeSessionSerializer,
    IntakeSessionDetailSerializer,
    CreateSessionRequestSerializer,
    SendMessageRequestSerializer,
    IntakeMessageSerializer,
    UpdateProposalSerializer,
    OnboardingProgressSerializer,
    ApplyProposalRequestSerializer,
    ApplyMultipleProposalsRequestSerializer,
    RejectProposalRequestSerializer,
    ApplyProposalsResponseSerializer,
)
import structlog

logger = structlog.get_logger(__name__)


class IntakeSessionListCreateView(APIView):
    """
    List and create intake sessions.
    
    GET: List sessions for the authenticated client
    POST: Create a new intake session
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """List sessions for the authenticated client."""
        user = request.user
        
        # Only clients can access intake sessions
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get query params
        status_filter = request.query_params.get("status")
        limit = min(int(request.query_params.get("limit", 20)), 100)
        offset = int(request.query_params.get("offset", 0))
        
        sessions, total = IntakeSessionService.list_sessions(
            client=user,
            status=status_filter,
            limit=limit,
            offset=offset,
        )
        
        serializer = IntakeSessionSerializer(sessions, many=True)
        
        return Response({
            "sessions": serializer.data,
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    
    def post(self, request):
        """Create a new intake session."""
        user = request.user
        
        # Only clients can create intake sessions
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can create intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CreateSessionRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        session = IntakeSessionService.create_session(
            client=user,
            property_id=str(serializer.validated_data.get("property_id")) if serializer.validated_data.get("property_id") else None,
            title=serializer.validated_data.get("title", ""),
        )
        
        # Auto-generate greeting if requested (default: True)
        greeting_message = None
        if serializer.validated_data.get("auto_greet", True):
            greeting_message = async_to_sync(IntakeChatService.generate_greeting)(session)
        
        # Get onboarding progress
        progress = IntakeSessionService.get_onboarding_progress(session)
        
        response_data = IntakeSessionSerializer(session).data
        response_data["onboarding_progress"] = progress.to_dict()
        
        if greeting_message:
            response_data["greeting_message"] = IntakeMessageSerializer(greeting_message).data
        
        return Response(response_data, status=status.HTTP_201_CREATED)


class IntakeSessionDetailView(APIView):
    """
    Retrieve a single intake session with its messages.
    
    GET: Get session details including messages and pending proposals
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get session details."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all messages
        messages = IntakeMessageService.get_all_messages(session)
        
        # Get pending proposals
        pending_proposals = UpdateProposalService.get_pending_proposals(session)
        
        # Get onboarding progress
        progress = IntakeSessionService.get_onboarding_progress(session)
        
        # Build response
        session_data = IntakeSessionSerializer(session).data
        session_data["messages"] = IntakeMessageSerializer(messages, many=True).data
        session_data["pending_proposals"] = UpdateProposalSerializer(
            pending_proposals, many=True
        ).data
        session_data["onboarding_progress"] = progress.to_dict()
        
        return Response(session_data)


class IntakeSessionStatusView(APIView):
    """
    Update session status.
    
    PATCH: Update the session status (pause, complete, abandon)
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, session_id):
        """Update session status."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can update intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        new_status = request.data.get("status")
        
        if not new_status:
            return Response(
                {"error": "status field is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate status
        try:
            IntakeSessionStatus(new_status)
        except ValueError:
            return Response(
                {"error": f"Invalid status. Must be one of: {[s.value for s in IntakeSessionStatus]}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session = IntakeSessionService.update_session_status(session, new_status)
        
        return Response(IntakeSessionSerializer(session).data)


class IntakeMessageSendView(APIView):
    """
    Send a message in an intake session.
    
    POST: Send a user message and receive AI response
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id):
        """
        Send a user message.
        
        Flow:
        1. Validate request
        2. Create user message record (persisted BEFORE AI runs)
        3. Process with AI
        4. Return both user message, assistant reply, and any proposals
        """
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can send messages"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check session is active
        if session.status != IntakeSessionStatus.ACTIVE:
            return Response(
                {"error": f"Session is {session.status}, cannot send messages"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check rate limit (100 messages per day per user)
        can_make_request, current_count, limit = IntakeMessageUsage.can_make_request(
            user, 
            limit=100
        )
        if not can_make_request:
            return Response(
                {
                    "error": "Rate limit exceeded",
                    "message": f"You have reached the daily limit of {limit} messages. Please try again tomorrow.",
                    "current_count": current_count,
                    "limit": limit,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Validate request
        serializer = SendMessageRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        content = serializer.validated_data["content"]
        media_attachments = serializer.validated_data.get("media_attachments", [])
        
        # Step 1: Create user message FIRST (before AI processing)
        user_message = IntakeMessageService.create_user_message(
            session=session,
            content=content,
            media_attachments=media_attachments,
        )
        
        logger.info(
            "user_message_persisted",
            session_id=str(session.id),
            message_id=str(user_message.id),
        )
        
        # Step 2: Process with fact-based AI
        try:
            # Increment usage counter (only after successful message creation)
            IntakeMessageUsage.increment_usage(user)
            
            # Use the fact-based processing
            assistant_message, new_proposals, fact_status = async_to_sync(
                IntakeChatService.process_user_message_with_facts
            )(
                session=session,
                user_message=user_message,
            )
        except Exception as e:
            logger.error(
                "ai_processing_failed",
                session_id=str(session.id),
                user_message_id=str(user_message.id),
                error=str(e),
                exc_info=True
            )
            # Return partial response - user message was saved
            return Response({
                "user_message": IntakeMessageSerializer(user_message).data,
                "assistant_message": None,
                "new_proposals": [],
                "fact_status": None,
                "error": "AI processing failed, please try again",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Step 3: Return complete response with fact status
        return Response({
            "user_message": IntakeMessageSerializer(user_message).data,
            "assistant_message": IntakeMessageSerializer(assistant_message).data,
            "new_proposals": UpdateProposalSerializer(new_proposals, many=True).data,
            "fact_status": fact_status.to_dict(),
            "ready_to_proceed": fact_status.ready_to_proceed,
        })


class IntakeMessageRetryView(APIView):
    """
    Retry generating assistant response for a user message.
    
    POST: Retry AI processing for a user message that failed or needs regeneration.
    
    IDEMPOTENT: Can be called multiple times without duplicating proposals.
    Uses content_hash deduplication to prevent duplicate proposals.
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id, message_id):
        """Retry AI processing for a user message."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can retry messages"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get the user message
        try:
            user_message = IntakeMessage.objects.get(
                id=message_id,
                session=session,
                role=MessageRole.USER,
            )
        except IntakeMessage.DoesNotExist:
            return Response(
                {"error": "User message not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if there's already an assistant response
        existing_assistant = IntakeMessage.objects.filter(
            session=session,
            in_reply_to=user_message,
            role=MessageRole.ASSISTANT,
        ).first()
        
        # Process with fact-based AI
        try:
            assistant_message, new_proposals, fact_status = async_to_sync(
                IntakeChatService.process_user_message_with_facts
            )(
                session=session,
                user_message=user_message,
            )
            
            # If there was an existing assistant message, mark it as superseded
            if existing_assistant and existing_assistant.id != assistant_message.id:
                logger.info(
                    "assistant_message_regenerated",
                    session_id=str(session.id),
                    user_message_id=str(user_message.id),
                    old_assistant_id=str(existing_assistant.id),
                    new_assistant_id=str(assistant_message.id),
                )
            
        except Exception as e:
            logger.error(
                "retry_ai_processing_failed",
                session_id=str(session.id),
                user_message_id=str(user_message.id),
                error=str(e),
                exc_info=True
            )
            return Response({
                "error": "AI processing failed",
                "message": str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response({
            "user_message": IntakeMessageSerializer(user_message).data,
            "assistant_message": IntakeMessageSerializer(assistant_message).data,
            "new_proposals": UpdateProposalSerializer(new_proposals, many=True).data,
            "fact_status": fact_status.to_dict(),
            "ready_to_proceed": fact_status.ready_to_proceed,
            "regenerated": existing_assistant is not None,
        })


class IntakeSessionMessagesView(APIView):
    """
    Get messages for a session (paginated).
    
    GET: Get messages with optional pagination
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get session messages."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get pagination params
        limit = min(int(request.query_params.get("limit", 50)), 100)
        before_sequence = request.query_params.get("before_sequence")
        
        queryset = session.messages.all().order_by("-sequence_number")
        
        if before_sequence:
            queryset = queryset.filter(sequence_number__lt=int(before_sequence))
        
        messages = list(queryset[:limit])
        messages.reverse()  # Return in chronological order
        
        return Response({
            "messages": IntakeMessageSerializer(messages, many=True).data,
            "has_more": len(messages) == limit,
        })


class IntakeSessionProposalsView(APIView):
    """
    Get pending proposals for a session.
    
    GET: Get all pending update proposals
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get pending proposals."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        from apps.intake.services import UpdateProposalService
        proposals = UpdateProposalService.get_pending_proposals(session)
        
        return Response({
            "proposals": UpdateProposalSerializer(proposals, many=True).data,
        })


class IntakeSessionProgressView(APIView):
    """Get onboarding progress for a session."""
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get onboarding progress."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        progress = IntakeSessionService.get_onboarding_progress(session)
        
        return Response({
            "progress": progress.to_dict(),
        })


class ProposalApplyView(APIView):
    """
    Apply a single proposal to canonical data.
    
    POST: Apply a proposal (creates/updates Property, Memory, Photo, etc.)
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id, proposal_id):
        """Apply a proposal."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can apply proposals"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            proposal = UpdateProposal.objects.get(
                id=proposal_id,
                session=session,
            )
        except UpdateProposal.DoesNotExist:
            return Response(
                {"error": "Proposal not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            result = ProposalApplicationService.apply_proposal(
                proposal=proposal,
                applied_by=user,
                request=request,
            )
            
            return Response(result, status=status.HTTP_200_OK)
            
        except (ProposalApplicationError, ProposalValidationError) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                "proposal_apply_failed",
                proposal_id=str(proposal_id),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {"error": "Failed to apply proposal"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProposalApplyMultipleView(APIView):
    """
    Apply multiple proposals in a single transaction.
    
    POST: Apply multiple proposals at once
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id):
        """Apply multiple proposals."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can apply proposals"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ApplyMultipleProposalsRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        proposal_ids = serializer.validated_data["proposal_ids"]
        
        # Get proposals
        proposals = UpdateProposal.objects.filter(
            id__in=proposal_ids,
            session=session,
            status=UpdateProposalStatus.PENDING,
        )
        
        if proposals.count() != len(proposal_ids):
            return Response(
                {"error": "Some proposals not found or not pending"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            results = ProposalApplicationService.apply_multiple_proposals(
                proposals=list(proposals),
                applied_by=user,
                request=request,
            )
            
            serializer = ApplyProposalsResponseSerializer(results)
            return Response(serializer.data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(
                "proposals_apply_multiple_failed",
                session_id=str(session_id),
                proposal_count=len(proposal_ids),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {"error": "Failed to apply proposals"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ProposalRejectView(APIView):
    """
    Reject a proposal.
    
    POST: Reject a proposal (mark as rejected, don't apply)
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request, session_id, proposal_id):
        """Reject a proposal."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can reject proposals"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            proposal = UpdateProposal.objects.get(
                id=proposal_id,
                session=session,
            )
        except UpdateProposal.DoesNotExist:
            return Response(
                {"error": "Proposal not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = RejectProposalRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            proposal = ProposalApplicationService.reject_proposal(
                proposal=proposal,
                rejected_by=user,
                reason=serializer.validated_data.get("reason"),
                request=request,
            )
            
            return Response(
                UpdateProposalSerializer(proposal).data,
                status=status.HTTP_200_OK
            )
            
        except (ProposalApplicationError, ProposalValidationError) as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(
                "proposal_reject_failed",
                proposal_id=str(proposal_id),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {"error": "Failed to reject proposal"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class IntakeSessionFactStatusView(APIView):
    """
    Check fact-based onboarding status.
    
    GET: Get current fact status for a session
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get current fact status for a session."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check facts (use cache for GET requests)
        fact_status = IntakeSessionService.check_onboarding_facts(
            session,
            use_cache=True,
        )
        
        return Response({
            "fact_status": fact_status.to_dict(),
            "ready_to_proceed": fact_status.ready_to_proceed,
            "missing_summary": get_missing_facts_summary(fact_status),
            "next_question_hint": get_next_question_hint(fact_status),
        })


class IntakeSessionOutputView(APIView):
    """
    Get structured intake output for downstream systems.
    
    Phase 8: Provides clean output for pricing engines and booking workflows.
    
    GET: Get structured intake output (property data, preferences, rules, etc.)
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """Get structured intake output."""
        user = request.user
        
        if user.role != UserRole.CLIENT:
            return Response(
                {"error": "Only clients can access intake sessions"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        session = IntakeSessionService.get_session(session_id, user)
        
        if not session:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate structured output
        output = IntakeOutputService.generate_output(session)
        
        return Response(output.to_dict(), status=status.HTTP_200_OK)


class IntakeSessionOutcomeView(APIView):
    """
    Get the current intake outcome for a session.
    
    Returns only applied/stored data - no pending proposals or chat text.
    This endpoint is designed for consumption by:
    - Pricing system
    - Booking system
    - Operator review
    - Client UI
    
    GET: Get complete intake outcome
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, session_id):
        """
        Get intake outcome.
        
        Returns a single payload containing:
        - Linked property ID (if exists)
        - Current property details (address, type, size, etc.)
        - List of known rooms
        - Stored standards/constraints (do/don'ts, preferences, notes)
        - Readiness status (ready to proceed or what's missing)
        """
        user = request.user
        
        # Allow both clients and admins/operators to access
        if user.role not in [UserRole.CLIENT, UserRole.ADMIN]:
            # For technicians or other roles, check if they have access
            # For now, restrict to client and admin
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get session
        try:
            if user.role == UserRole.CLIENT:
                # Clients can only access their own sessions
                session = IntakeSession.objects.select_related("property").get(
                    id=session_id,
                    client=user,
                    tenant=user.tenant,
                )
            else:
                # Admins can access any session in their tenant
                session = IntakeSession.objects.select_related("property").get(
                    id=session_id,
                    tenant=user.tenant,
                )
        except IntakeSession.DoesNotExist:
            return Response(
                {"error": "Session not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build outcome
        outcome = IntakeSessionService.get_intake_outcome(session)
        
        # Serialize and return
        return Response(outcome.to_dict())


class IntakeOutcomeByPropertyView(APIView):
    """
    Get intake outcome by property ID.
    
    Finds the most recent completed intake session for a property
    and returns its outcome. Useful when you have a property ID
    but not a session ID.
    
    GET: Get intake outcome for a property
    """
    authentication_classes = [SupabaseAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request, property_id):
        """Get intake outcome for a property."""
        user = request.user
        
        if user.role not in [UserRole.CLIENT, UserRole.ADMIN]:
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Find the most recent intake session for this property
        try:
            queryset = IntakeSession.objects.filter(
                property_id=property_id,
                tenant=user.tenant,
            ).select_related("property").order_by("-updated_at")
            
            if user.role == UserRole.CLIENT:
                queryset = queryset.filter(client=user)
            
            session = queryset.first()
            
            if not session:
                return Response(
                    {"error": "No intake session found for this property"},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except Exception as e:
            logger.error(
                "property_outcome_lookup_failed",
                property_id=str(property_id),
                error=str(e),
                exc_info=True,
            )
            return Response(
                {"error": "Invalid property ID"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build outcome
        outcome = IntakeSessionService.get_intake_outcome(session)
        
        return Response(outcome.to_dict())
