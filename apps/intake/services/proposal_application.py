"""
Service for applying update proposals to canonical data models.

Phase 5: Enhanced with validation, audit trail, and partial acceptance.
Handles the workflow of approving and applying proposals that were
generated during intake sessions.
"""
from typing import List, Dict, Any, Optional, Tuple
from django.db import transaction
from django.utils import timezone
import structlog

from apps.intake.models import (
    UpdateProposal,
    UpdateProposalStatus,
    UpdateProposalType,
    IntakeSession,
    ProposalApplicationAuditLog,
)
from apps.properties.models import (
    Property,
    PropertyMemory,
    PropertyMemoryType,
    IdealConditionPhoto,
)
from apps.users.models import User

logger = structlog.get_logger(__name__)


class ProposalApplicationError(Exception):
    """Base exception for proposal application errors."""
    pass


class ProposalValidationError(ProposalApplicationError):
    """Raised when proposal validation fails."""
    pass


class ProposalApplicationService:
    """
    Service for applying update proposals to canonical models.
    
    Phase 5 enhancements:
    - Tenant and permission validation at application time
    - Parent relationship validation (e.g., room belongs to property)
    - Partial acceptance (apply valid, reject invalid)
    - Complete audit trail for all changes
    - Source tracking (which message/media triggered the proposal)
    """
    
    @staticmethod
    def _validate_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Tuple[bool, List[str]]:
        """
        Validate a proposal before application.
        
        Checks:
        - Tenant matches
        - User has permission
        - Parent relationships are valid
        - Required fields are present
        
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check tenant match
        if proposal.tenant != applied_by.tenant:
            errors.append(f"Proposal tenant {proposal.tenant_id} does not match user tenant {applied_by.tenant_id}")
        
        # Check session belongs to user
        session = proposal.session
        if session.client != applied_by:
            errors.append(f"Session {session.id} does not belong to user {applied_by.id}")
        
        # Check property belongs to tenant (if exists)
        if session.property:
            if session.property.tenant != applied_by.tenant:
                errors.append(f"Property {session.property.id} does not belong to tenant {applied_by.tenant_id}")
        
        # Type-specific validation
        if proposal.proposal_type in [
            UpdateProposalType.ROOM_CREATE,
            UpdateProposalType.ROOM_UPDATE,
            UpdateProposalType.MEMORY_CREATE,
            UpdateProposalType.MEMORY_UPDATE,
            UpdateProposalType.PREFERENCE_CREATE,
            UpdateProposalType.PREFERENCE_UPDATE,
            UpdateProposalType.DO_RULE_CREATE,
            UpdateProposalType.DO_RULE_UPDATE,
            UpdateProposalType.DONT_RULE_CREATE,
            UpdateProposalType.DONT_RULE_UPDATE,
            UpdateProposalType.PHOTO_CREATE,
            UpdateProposalType.PHOTO_UPDATE,
        ]:
            if not session.property:
                errors.append("Property required for this proposal type")
        
        # Validate parent relationships for updates
        if proposal.proposal_type in [
            UpdateProposalType.PROPERTY_UPDATE,
            UpdateProposalType.ROOM_UPDATE,
            UpdateProposalType.MEMORY_UPDATE,
            UpdateProposalType.PREFERENCE_UPDATE,
            UpdateProposalType.DO_RULE_UPDATE,
            UpdateProposalType.DONT_RULE_UPDATE,
            UpdateProposalType.PHOTO_UPDATE,
        ]:
            if not proposal.target_entity_id:
                errors.append("target_entity_id required for update proposals")
            else:
                # Validate entity exists and belongs to correct parent
                if proposal.proposal_type == UpdateProposalType.PROPERTY_UPDATE:
                    try:
                        prop = Property.objects.get(
                            id=proposal.target_entity_id,
                            tenant=applied_by.tenant,
                        )
                        if session.property and prop.id != session.property.id:
                            errors.append(f"Property {proposal.target_entity_id} does not match session property")
                    except Property.DoesNotExist:
                        errors.append(f"Property {proposal.target_entity_id} not found")
                
                elif proposal.proposal_type in [
                    UpdateProposalType.ROOM_UPDATE,
                    UpdateProposalType.MEMORY_UPDATE,
                    UpdateProposalType.PREFERENCE_UPDATE,
                    UpdateProposalType.DO_RULE_UPDATE,
                    UpdateProposalType.DONT_RULE_UPDATE,
                ]:
                    if not session.property:
                        errors.append("Property required for memory update")
                    else:
                        try:
                            memory = PropertyMemory.objects.get(
                                id=proposal.target_entity_id,
                                tenant=applied_by.tenant,
                            )
                            if memory.property_id != session.property.id:
                                errors.append(f"Memory {proposal.target_entity_id} does not belong to session property")
                        except PropertyMemory.DoesNotExist:
                            errors.append(f"Memory {proposal.target_entity_id} not found")
                
                elif proposal.proposal_type == UpdateProposalType.PHOTO_UPDATE:
                    if not session.property:
                        errors.append("Property required for photo update")
                    else:
                        try:
                            photo = IdealConditionPhoto.objects.get(
                                id=proposal.target_entity_id,
                                tenant=applied_by.tenant,
                            )
                            if photo.property_id != session.property.id:
                                errors.append(f"Photo {proposal.target_entity_id} does not belong to session property")
                        except IdealConditionPhoto.DoesNotExist:
                            errors.append(f"Photo {proposal.target_entity_id} not found")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def _create_audit_log(
        proposal: UpdateProposal,
        applied_by: User,
        result: str,
        affected_entity_type: Optional[str] = None,
        affected_entity_id: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        validation_errors: Optional[List[str]] = None,
        request=None,
    ) -> ProposalApplicationAuditLog:
        """
        Create an audit log entry for a proposal application.
        
        This provides a complete audit trail for "why does this home have this rule?"
        """
        # Extract source message info
        source_message = proposal.source_message
        source_message_id = source_message.id if source_message else None
        source_media = source_message.media_attachments if source_message else []
        
        # Extract request metadata
        ip_address = None
        user_agent = ""
        request_id = ""
        if request:
            ip_address = getattr(request, 'META', {}).get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            request_id = getattr(request, 'id', '')
        
        audit_log = ProposalApplicationAuditLog.objects.create(
            tenant=proposal.tenant,
            proposal=proposal,
            result=result,
            affected_entity_type=affected_entity_type or "",
            affected_entity_id=affected_entity_id,
            applied_by=applied_by,
            source_message_id=source_message_id,
            source_media_attachments=source_media,
            previous_state=previous_state,
            new_state=new_state,
            error_code=error_code or "",
            error_message=error_message or "",
            validation_passed=len(validation_errors or []) == 0,
            validation_errors=validation_errors or [],
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
        )
        
        logger.info(
            "proposal_audit_log_created",
            audit_log_id=str(audit_log.id),
            proposal_id=str(proposal.id),
            result=result,
            applied_by=str(applied_by.id),
        )
        
        return audit_log
    
    @staticmethod
    def _capture_previous_state(
        proposal: UpdateProposal,
    ) -> Optional[Dict[str, Any]]:
        """Capture the previous state of an entity before update."""
        if not proposal.target_entity_id:
            return None
        
        try:
            if proposal.proposal_type == UpdateProposalType.PROPERTY_UPDATE:
                prop = Property.objects.get(id=proposal.target_entity_id)
                return {
                    "address": prop.address,
                    "property_type": prop.property_type,
                    "bedrooms": prop.bedrooms,
                    "bathrooms": prop.bathrooms,
                    "square_feet": prop.square_feet,
                    "access_instructions": prop.access_instructions,
                }
            elif proposal.proposal_type in [
                UpdateProposalType.ROOM_UPDATE,
                UpdateProposalType.MEMORY_UPDATE,
                UpdateProposalType.PREFERENCE_UPDATE,
                UpdateProposalType.DO_RULE_UPDATE,
                UpdateProposalType.DONT_RULE_UPDATE,
            ]:
                memory = PropertyMemory.objects.get(id=proposal.target_entity_id)
                return {
                    "content": memory.content,
                    "label": memory.label,
                    "room_name": memory.room_name,
                    "level": memory.level,
                }
            elif proposal.proposal_type == UpdateProposalType.PHOTO_UPDATE:
                photo = IdealConditionPhoto.objects.get(id=proposal.target_entity_id)
                return {
                    "caption": photo.caption,
                    "room_name": photo.room_name,
                    "location_description": photo.location_description,
                }
        except Exception as e:
            logger.warning(
                "failed_to_capture_previous_state",
                proposal_id=str(proposal.id),
                error=str(e),
            )
        
        return None
    
    @staticmethod
    @transaction.atomic
    def apply_proposal(
        proposal: UpdateProposal,
        applied_by: User,
        request=None,
    ) -> Dict[str, Any]:
        """
        Apply a single proposal to the canonical data model.
        
        Phase 5: Enhanced with validation and audit trail.
        IDEMPOTENT: If proposal is already applied, returns success without duplicate changes.
        
        Args:
            proposal: The UpdateProposal to apply
            applied_by: User who is applying the proposal
            request: Optional HTTP request for audit metadata
            
        Returns:
            Dict with 'success', 'entity_type', 'entity_id', and 'message'
            
        Raises:
            ProposalApplicationError: If application fails
            ValidationError: If validation fails
        """
        # IDEMPOTENCY: If already applied, return success without duplicate changes
        if proposal.status == UpdateProposalStatus.APPLIED:
            # Check if there's an existing successful audit log
            existing_log = ProposalApplicationAuditLog.objects.filter(
                proposal=proposal,
                action="applied",
            ).first()
            
            if existing_log:
                logger.info(
                    "proposal_already_applied",
                    proposal_id=str(proposal.id),
                    entity_id=str(existing_log.entity_id) if existing_log.entity_id else None,
                )
                return {
                    "success": True,
                    "entity_type": existing_log.entity_type or "",
                    "entity_id": str(existing_log.entity_id) if existing_log.entity_id else None,
                    "message": "Proposal was already applied (idempotent operation)",
                    "idempotent": True,
                }
        
        if proposal.status != UpdateProposalStatus.PENDING:
            raise ProposalApplicationError(
                f"Cannot apply proposal {proposal.id} with status {proposal.status}"
            )
        
        # Validate proposal
        is_valid, validation_errors = ProposalApplicationService._validate_proposal(
            proposal, applied_by
        )
        
        if not is_valid:
            # Create audit log for validation failure
            ProposalApplicationService._create_audit_log(
                proposal=proposal,
                applied_by=applied_by,
                result="failed",
                error_code="validation_failed",
                error_message="; ".join(validation_errors),
                validation_errors=validation_errors,
                request=request,
            )
            raise ProposalValidationError(f"Validation failed: {'; '.join(validation_errors)}")
        
        # Capture previous state for updates
        previous_state = ProposalApplicationService._capture_previous_state(proposal)
        
        try:
            result = None
            
            if proposal.proposal_type in [
                UpdateProposalType.PROPERTY_CREATE,
                UpdateProposalType.PROPERTY_UPDATE,
            ]:
                result = ProposalApplicationService._apply_property_proposal(
                    proposal, applied_by
                )
            elif proposal.proposal_type in [
                UpdateProposalType.ROOM_CREATE,
                UpdateProposalType.ROOM_UPDATE,
            ]:
                result = ProposalApplicationService._apply_room_proposal(
                    proposal, applied_by
                )
            elif proposal.proposal_type in [
                UpdateProposalType.MEMORY_CREATE,
                UpdateProposalType.MEMORY_UPDATE,
            ]:
                result = ProposalApplicationService._apply_memory_proposal(
                    proposal, applied_by
                )
            elif proposal.proposal_type in [
                UpdateProposalType.PREFERENCE_CREATE,
                UpdateProposalType.PREFERENCE_UPDATE,
            ]:
                result = ProposalApplicationService._apply_preference_proposal(
                    proposal, applied_by
                )
            elif proposal.proposal_type in [
                UpdateProposalType.DO_RULE_CREATE,
                UpdateProposalType.DO_RULE_UPDATE,
            ]:
                result = ProposalApplicationService._apply_do_rule_proposal(
                    proposal, applied_by
                )
            elif proposal.proposal_type in [
                UpdateProposalType.DONT_RULE_CREATE,
                UpdateProposalType.DONT_RULE_UPDATE,
            ]:
                result = ProposalApplicationService._apply_dont_rule_proposal(
                    proposal, applied_by
                )
            elif proposal.proposal_type in [
                UpdateProposalType.PHOTO_CREATE,
                UpdateProposalType.PHOTO_UPDATE,
            ]:
                result = ProposalApplicationService._apply_photo_proposal(
                    proposal, applied_by
                )
            else:
                raise ProposalApplicationError(
                    f"Unknown proposal type: {proposal.proposal_type}"
                )
            
            # Capture new state
            new_state = result.get("new_state") or proposal.proposed_data
            
            # Mark proposal as applied
            proposal.status = UpdateProposalStatus.APPLIED
            proposal.reviewed_at = timezone.now()
            proposal.reviewed_by = applied_by
            proposal.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"])
            
            # Update target_entity_id if it was a create
            if result.get("entity_id") and not proposal.target_entity_id:
                proposal.target_entity_id = result["entity_id"]
                proposal.save(update_fields=["target_entity_id"])
            
            # Create audit log for successful application
            ProposalApplicationService._create_audit_log(
                proposal=proposal,
                applied_by=applied_by,
                result="applied",
                affected_entity_type=result.get("entity_type"),
                affected_entity_id=str(result.get("entity_id")) if result.get("entity_id") else None,
                previous_state=previous_state,
                new_state=new_state,
                request=request,
            )
            
            logger.info(
                "proposal_applied",
                proposal_id=str(proposal.id),
                proposal_type=proposal.proposal_type,
                entity_type=result.get("entity_type"),
                entity_id=str(result.get("entity_id")),
                applied_by=str(applied_by.id),
            )
            
            return {
                "success": True,
                "entity_type": result.get("entity_type"),
                "entity_id": str(result.get("entity_id")),
                "message": result.get("message", "Proposal applied successfully"),
            }
            
        except Exception as e:
            # Create audit log for application failure
            ProposalApplicationService._create_audit_log(
                proposal=proposal,
                applied_by=applied_by,
                result="failed",
                previous_state=previous_state,
                error_code="application_failed",
                error_message=str(e),
                request=request,
            )
            
            logger.error(
                "proposal_application_failed",
                proposal_id=str(proposal.id),
                proposal_type=proposal.proposal_type,
                error=str(e),
                exc_info=True,
            )
            raise ProposalApplicationError(f"Failed to apply proposal: {str(e)}")
    
    @staticmethod
    @transaction.atomic
    def apply_multiple_proposals(
        proposals: List[UpdateProposal],
        applied_by: User,
        request=None,
    ) -> Dict[str, Any]:
        """
        Apply multiple proposals with partial acceptance.
        
        Phase 5: Applies valid proposals, rejects invalid ones.
        Does not fail the entire operation if some proposals are invalid.
        
        Returns:
            Dict with 'successful', 'failed', and 'total' counts
        """
        results = {
            "successful": [],
            "failed": [],
            "total": len(proposals),
        }
        
        for proposal in proposals:
            try:
                result = ProposalApplicationService.apply_proposal(
                    proposal, applied_by, request=request
                )
                results["successful"].append({
                    "proposal_id": str(proposal.id),
                    **result,
                })
            except ProposalValidationError as e:
                # Validation errors are logged but don't fail the batch
                results["failed"].append({
                    "proposal_id": str(proposal.id),
                    "error": str(e),
                    "error_type": "validation",
                })
            except ProposalApplicationError as e:
                # Application errors are logged but don't fail the batch
                results["failed"].append({
                    "proposal_id": str(proposal.id),
                    "error": str(e),
                    "error_type": "application",
                })
            except Exception as e:
                # Unexpected errors
                logger.error(
                    "unexpected_error_in_batch_apply",
                    proposal_id=str(proposal.id),
                    error=str(e),
                    exc_info=True,
                )
                results["failed"].append({
                    "proposal_id": str(proposal.id),
                    "error": str(e),
                    "error_type": "unexpected",
                })
        
        logger.info(
            "multiple_proposals_applied",
            total=results["total"],
            successful=len(results["successful"]),
            failed=len(results["failed"]),
            applied_by=str(applied_by.id),
        )
        
        return results
    
    @staticmethod
    def reject_proposal(
        proposal: UpdateProposal,
        rejected_by: User,
        reason: Optional[str] = None,
        request=None,
    ) -> UpdateProposal:
        """
        Mark a proposal as rejected.
        
        Phase 5: Creates audit log for rejection.
        """
        if proposal.status != UpdateProposalStatus.PENDING:
            raise ProposalApplicationError(
                f"Cannot reject proposal {proposal.id} with status {proposal.status}"
            )
        
        proposal.status = UpdateProposalStatus.REJECTED
        proposal.reviewed_at = timezone.now()
        proposal.reviewed_by = rejected_by
        if reason:
            proposal.summary = f"{proposal.summary} [REJECTED: {reason}]"
        proposal.save(update_fields=["status", "reviewed_at", "reviewed_by", "summary", "updated_at"])
        
        # Create audit log for rejection
        ProposalApplicationService._create_audit_log(
            proposal=proposal,
            applied_by=rejected_by,
            result="rejected",
            error_message=reason or "Rejected by user",
            request=request,
        )
        
        logger.info(
            "proposal_rejected",
            proposal_id=str(proposal.id),
            rejected_by=str(rejected_by.id),
            reason=reason,
        )
        
        return proposal
    
    # Keep all the existing _apply_* methods unchanged
    @staticmethod
    def _apply_property_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a property create/update proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        # Get or create property
        if proposal.proposal_type == UpdateProposalType.PROPERTY_CREATE:
            # Create new property
            property_obj = Property.objects.create(
                tenant=session.tenant,
                address=data.get("address", ""),
                address_line_1=data.get("address_line_1", ""),
                city=data.get("city", ""),
                state=data.get("state", ""),
                zip_code=data.get("zip_code", ""),
                country=data.get("country", "USA"),
                property_type=data.get("property_type", ""),
                square_feet=data.get("square_feet"),
                bedrooms=data.get("num_bedrooms") or data.get("bedrooms"),
                bathrooms=data.get("num_bathrooms") or data.get("bathrooms"),
                year_built=data.get("year_built"),
                lot_size_sqft=data.get("lot_size_sqft"),
                client_name=data.get("client_name", ""),
                client_email=data.get("client_email", ""),
                client_phone=data.get("client_phone", ""),
                access_instructions=data.get("access_details", "") or data.get("access_instructions", ""),
                notes=data.get("notes", ""),
            )
        else:
            # Update existing property
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for property update")
            
            property_obj = Property.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            # Update fields from data
            for field in ["address", "address_line_1", "city", "state", "zip_code", 
                         "country", "property_type", "square_feet", "year_built",
                         "lot_size_sqft", "client_name", "client_email", "client_phone",
                         "access_instructions", "notes"]:
                if field in data:
                    setattr(property_obj, field, data[field])
            
            # Handle bedroom/bathroom fields (can be num_bedrooms or bedrooms)
            if "num_bedrooms" in data or "bedrooms" in data:
                property_obj.bedrooms = data.get("num_bedrooms") or data.get("bedrooms")
            if "num_bathrooms" in data or "bathrooms" in data:
                property_obj.bathrooms = data.get("num_bathrooms") or data.get("bathrooms")
            
            # Handle access_details -> access_instructions
            if "access_details" in data:
                property_obj.access_instructions = data["access_details"]
            
            property_obj.save()
        
        # Link session to property if not already linked
        # RULE: One session = one home (MVP)
        # Lock property linkage when first set
        if not session.property:
            if session.property_locked:
                raise ProposalApplicationError(
                    f"Cannot link property to session {session.id}: "
                    "property linkage is locked (one session = one home)"
                )
            session.set_property(property_obj)  # This locks it automatically
        elif session.property != property_obj:
            # Property mismatch - this shouldn't happen if locked
            if session.property_locked:
                raise ProposalApplicationError(
                    f"Cannot change property for session {session.id}: "
                    "property linkage is locked (one session = one home)"
                )
        
        return {
            "entity_type": "property",
            "entity_id": property_obj.id,
            "message": f"Property {'created' if proposal.proposal_type == UpdateProposalType.PROPERTY_CREATE else 'updated'}",
            "new_state": {
                "address": property_obj.address,
                "property_type": property_obj.property_type,
                "bedrooms": property_obj.bedrooms,
                "bathrooms": property_obj.bathrooms,
            },
        }
    
    @staticmethod
    def _apply_room_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a room create/update proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        if not session.property:
            raise ProposalApplicationError("Property required for room proposals")
        
        room_name = data.get("room_name") or data.get("name", "")
        if not room_name:
            raise ProposalApplicationError("room_name is required")
        
        if proposal.proposal_type == UpdateProposalType.ROOM_CREATE:
            memory = PropertyMemory.objects.create(
                tenant=session.tenant,
                property=session.property,
                memory_type=PropertyMemoryType.NOTE,
                level="room",
                room_name=room_name,
                label=f"Room: {room_name}",
                content=data.get("description", "") or data.get("content", ""),
                author=applied_by,
            )
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Room '{room_name}' noted",
                "new_state": {
                    "room_name": memory.room_name,
                    "content": memory.content,
                },
            }
        else:
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for room update")
            
            memory = PropertyMemory.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            if "description" in data or "content" in data:
                memory.content = data.get("description") or data.get("content", memory.content)
            if "room_name" in data:
                memory.room_name = data["room_name"]
            
            memory.save()
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Room '{room_name}' updated",
                "new_state": {
                    "room_name": memory.room_name,
                    "content": memory.content,
                },
            }
    
    @staticmethod
    def _apply_memory_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a memory/note create/update proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        if not session.property:
            raise ProposalApplicationError("Property required for memory proposals")
        
        memory_type_str = data.get("memory_type", "note")
        try:
            memory_type = PropertyMemoryType(memory_type_str)
        except ValueError:
            memory_type = PropertyMemoryType.NOTE
        
        if proposal.proposal_type == UpdateProposalType.MEMORY_CREATE:
            memory = PropertyMemory.objects.create(
                tenant=session.tenant,
                property=session.property,
                memory_type=memory_type,
                level=data.get("level", "property"),
                room_name=data.get("room_name", ""),
                surface_name=data.get("surface_name", ""),
                label=data.get("label", "") or data.get("summary", ""),
                content=data.get("content", ""),
                author=applied_by,
                priority=data.get("priority", 0),
            )
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Memory '{memory.label}' created",
                "new_state": {
                    "label": memory.label,
                    "content": memory.content,
                    "memory_type": memory.memory_type,
                },
            }
        else:
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for memory update")
            
            memory = PropertyMemory.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            if "content" in data:
                memory.content = data["content"]
            if "label" in data:
                memory.label = data["label"]
            if "priority" in data:
                memory.priority = data["priority"]
            if "room_name" in data:
                memory.room_name = data["room_name"]
            if "surface_name" in data:
                memory.surface_name = data["surface_name"]
            
            memory.save()
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Memory '{memory.label}' updated",
                "new_state": {
                    "label": memory.label,
                    "content": memory.content,
                },
            }
    
    @staticmethod
    def _apply_preference_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a product preference proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        if not session.property:
            raise ProposalApplicationError("Property required for preference proposals")
        
        product_name = data.get("product_name", "")
        use_product = data.get("use_product", True)
        
        if not product_name:
            raise ProposalApplicationError("product_name is required for preference")
        
        if proposal.proposal_type == UpdateProposalType.PREFERENCE_CREATE:
            memory = PropertyMemory.objects.create(
                tenant=session.tenant,
                property=session.property,
                memory_type=PropertyMemoryType.PRODUCT_PREFERENCE,
                level=data.get("level", "property"),
                room_name=data.get("room_name", ""),
                product_name=product_name,
                use_product=use_product,
                label=f"Product: {product_name}",
                content=data.get("content", "") or f"{'Use' if use_product else 'Avoid'} {product_name}",
                author=applied_by,
            )
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Preference for '{product_name}' created",
                "new_state": {
                    "product_name": memory.product_name,
                    "use_product": memory.use_product,
                },
            }
        else:
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for preference update")
            
            memory = PropertyMemory.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            if "product_name" in data:
                memory.product_name = data["product_name"]
            if "use_product" in data:
                memory.use_product = data["use_product"]
            if "content" in data:
                memory.content = data["content"]
            
            memory.save()
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Preference for '{product_name}' updated",
                "new_state": {
                    "product_name": memory.product_name,
                    "use_product": memory.use_product,
                },
            }
    
    @staticmethod
    def _apply_do_rule_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a do rule proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        if not session.property:
            raise ProposalApplicationError("Property required for do rule proposals")
        
        content = data.get("content", "") or data.get("rule", "")
        if not content:
            raise ProposalApplicationError("content is required for do rule")
        
        if proposal.proposal_type == UpdateProposalType.DO_RULE_CREATE:
            memory = PropertyMemory.objects.create(
                tenant=session.tenant,
                property=session.property,
                memory_type=PropertyMemoryType.DO_RULE,
                level=data.get("level", "property"),
                room_name=data.get("room_name", ""),
                surface_name=data.get("surface_name", ""),
                label=data.get("label", "") or "Do Rule",
                content=content,
                author=applied_by,
                priority=data.get("priority", 0),
            )
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Do rule created",
                "new_state": {
                    "content": memory.content,
                    "label": memory.label,
                },
            }
        else:
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for do rule update")
            
            memory = PropertyMemory.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            if "content" in data:
                memory.content = data["content"]
            if "label" in data:
                memory.label = data["label"]
            
            memory.save()
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Do rule updated",
                "new_state": {
                    "content": memory.content,
                    "label": memory.label,
                },
            }
    
    @staticmethod
    def _apply_dont_rule_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a don't rule proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        if not session.property:
            raise ProposalApplicationError("Property required for don't rule proposals")
        
        content = data.get("content", "") or data.get("rule", "")
        if not content:
            raise ProposalApplicationError("content is required for don't rule")
        
        if proposal.proposal_type == UpdateProposalType.DONT_RULE_CREATE:
            memory = PropertyMemory.objects.create(
                tenant=session.tenant,
                property=session.property,
                memory_type=PropertyMemoryType.DONT_RULE,
                level=data.get("level", "property"),
                room_name=data.get("room_name", ""),
                surface_name=data.get("surface_name", ""),
                label=data.get("label", "") or "Don't Rule",
                content=content,
                author=applied_by,
                priority=data.get("priority", 0),
            )
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Don't rule created",
                "new_state": {
                    "content": memory.content,
                    "label": memory.label,
                },
            }
        else:
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for don't rule update")
            
            memory = PropertyMemory.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            if "content" in data:
                memory.content = data["content"]
            if "label" in data:
                memory.label = data["label"]
            
            memory.save()
            
            return {
                "entity_type": "memory",
                "entity_id": memory.id,
                "message": f"Don't rule updated",
                "new_state": {
                    "content": memory.content,
                    "label": memory.label,
                },
            }
    
    @staticmethod
    def _apply_photo_proposal(
        proposal: UpdateProposal,
        applied_by: User,
    ) -> Dict[str, Any]:
        """Apply a reference photo proposal."""
        data = proposal.proposed_data
        session = proposal.session
        
        if not session.property:
            raise ProposalApplicationError("Property required for photo proposals")
        
        # Get media attachment from source message
        source_message = proposal.source_message
        media_attachments = source_message.media_attachments if source_message else []
        
        if not media_attachments:
            raise ProposalApplicationError("No media attachments found in source message")
        
        # Use the first attachment
        attachment = media_attachments[0]
        blob_name = attachment.get("blob_name", "")
        file_name = attachment.get("file_name", "")
        
        if not blob_name:
            raise ProposalApplicationError("blob_name is required for photo proposal")
        
        # Generate file URL using FileService
        from files.services.file_service import FileService
        from asgiref.sync import async_to_sync
        
        # Generate download URL (signed URL for GCS)
        file_url = data.get("file_url")
        if not file_url:
            # Generate signed URL (async function called from sync context)
            file_url = async_to_sync(FileService.generate_download_url)(
                blob_name, 
                expiration=31536000  # 1 year expiration
            )
        
        thumbnail_url = data.get("thumbnail_url", "")
        
        photo_type = data.get("photo_type", "ideal_condition")  # ideal_condition or problem_zone
        
        if proposal.proposal_type == UpdateProposalType.PHOTO_CREATE:
            photo = IdealConditionPhoto.objects.create(
                tenant=session.tenant,
                property=session.property,
                room_name=data.get("room_name", ""),
                surface_name=data.get("surface_name", ""),
                location_description=data.get("location_description", ""),
                file_name=file_name or blob_name,
                file_url=file_url,
                thumbnail_url=thumbnail_url,
                caption=data.get("caption", "") or proposal.summary,
                uploaded_by=applied_by,
                is_active=True,
            )
            
            return {
                "entity_type": "photo",
                "entity_id": photo.id,
                "message": f"Reference photo created ({photo_type})",
                "new_state": {
                    "file_name": photo.file_name,
                    "room_name": photo.room_name,
                    "caption": photo.caption,
                },
            }
        else:
            if not proposal.target_entity_id:
                raise ProposalApplicationError("target_entity_id required for photo update")
            
            photo = IdealConditionPhoto.objects.get(
                id=proposal.target_entity_id,
                tenant=session.tenant,
            )
            
            if "caption" in data:
                photo.caption = data["caption"]
            if "room_name" in data:
                photo.room_name = data["room_name"]
            if "surface_name" in data:
                photo.surface_name = data["surface_name"]
            if "location_description" in data:
                photo.location_description = data["location_description"]
            
            photo.save()
            
            return {
                "entity_type": "photo",
                "entity_id": photo.id,
                "message": f"Reference photo updated",
                "new_state": {
                    "caption": photo.caption,
                    "room_name": photo.room_name,
                },
            }
