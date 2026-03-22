"""
Event logging service for creating audit log entries.
"""
import logging
from typing import Any, Dict, Optional
from uuid import UUID

from django.http import HttpRequest

from apps.core.middleware import get_current_tenant_id, get_current_user

from .models import Event

logger = logging.getLogger(__name__)


def record_event(
    *,
    tenant_id: UUID,
    actor,
    event_type: str,
    entity_type: str,
    entity_id: UUID,
    payload: Optional[Dict[str, Any]] = None,
    request: Optional[HttpRequest] = None,
) -> Event:
    """
    Persist an audit event. Pass actor=None for system-initiated events (no request user).

    Contract: creation is logged from the ServiceRequest post_save signal only; status and
    pricing changes are logged from the view layer. Do not duplicate creation events in perform_create.
    """
    ip_address = None
    user_agent = ""
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        if xff:
            ip_address = xff.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")
        user_agent = request.META.get("HTTP_USER_AGENT", "") or ""

    resolved_actor = None
    if actor is not None and getattr(actor, "is_authenticated", False):
        resolved_actor = actor

    return Event.objects.create(
        tenant_id=tenant_id,
        actor=resolved_actor,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )


class EventService:
    """Service for creating and querying audit log events."""
    
    @staticmethod
    def log_event(
        event_type: str,
        entity_type: str,
        entity_id: UUID,
        payload: Optional[Dict[str, Any]] = None,
        actor: Optional['User'] = None,
        tenant_id: Optional[UUID] = None,
        request: Optional['HttpRequest'] = None
    ) -> Event:
        """
        Create an audit log entry.
        
        Args:
            event_type: Type of event (from EventType choices)
            entity_type: Type of entity (from EntityType choices)
            entity_id: ID of the entity
            payload: Additional event-specific data
            actor: User who performed the action (if not provided, tries to get from context)
            tenant_id: Tenant ID (if not provided, tries to get from context)
            request: HTTP request object for extracting metadata
            
        Returns:
            Created Event instance
        """
        # Get tenant from context if not provided
        if not tenant_id:
            tenant_id = get_current_tenant_id()
            if not tenant_id:
                raise ValueError("No tenant context available for event logging")
        
        # Get actor from context if not provided
        if not actor:
            actor = get_current_user()
        
        # Extract request metadata
        ip_address = None
        user_agent = ""
        if request:
            ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Create the event
        event = Event.objects.create(
            tenant_id=tenant_id,
            actor=actor,
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info(
            "event_logged event_id=%s event_type=%s entity_type=%s entity_id=%s tenant_id=%s actor_id=%s",
            event.id,
            event_type,
            entity_type,
            entity_id,
            tenant_id,
            actor.id if actor else None,
        )
        
        return event
    
    @staticmethod
    def get_entity_history(
        entity_type: str,
        entity_id: UUID,
        tenant_id: Optional[UUID] = None
    ) -> 'QuerySet[Event]':
        """
        Get all events for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            tenant_id: Tenant ID (if not provided, uses context)
            
        Returns:
            QuerySet of events for the entity
        """
        if not tenant_id:
            tenant_id = get_current_tenant_id()
        
        return Event.objects.filter(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id
        ).select_related('actor').order_by('-created_at')


# Singleton instance
event_service = EventService()
