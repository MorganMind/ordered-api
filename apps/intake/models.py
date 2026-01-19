"""
Intake Session models for AI-guided chat intake.

IntakeSession: A conversation session tied to a client user and optionally a property.
IntakeMessage: Individual messages within a session (user, assistant, system roles).
UpdateProposal: Structured AI-proposed updates to home/room/notes, stored but not applied.
"""
import uuid
import hashlib
import json
from django.db import models
from django.core.validators import MinValueValidator
from apps.core.models import TenantAwareModel


class IntakeSessionStatus(models.TextChoices):
    """Status of an intake session."""
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    COMPLETED = "completed", "Completed"
    ABANDONED = "abandoned", "Abandoned"


class IntakeSession(TenantAwareModel):
    """
    A chat intake session for a client user.
    
    Sessions are tenant-scoped and tied to the authenticated client user.
    Optionally linked to a property if one already exists.
    Sessions can be resumed by the client app and re-processed by the backend.
    """
    # Client association (required)
    client = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="intake_sessions",
        db_index=True,
        help_text="Client user who owns this session"
    )
    
    # Optional property association
    # RULE: One session = one home (MVP)
    # Once a property is set, it cannot be changed to prevent ambiguity
    # in retrieval and intake results.
    property = models.ForeignKey(
        "properties.Property",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="intake_sessions",
        db_index=True,
        help_text="Property this session relates to (if known). Once set, cannot be changed."
    )
    property_locked = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether the property linkage is locked (prevents changing property)"
    )
    
    # Session metadata
    title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional title for the session (can be auto-generated)"
    )
    status = models.CharField(
        max_length=20,
        choices=IntakeSessionStatus.choices,
        default=IntakeSessionStatus.ACTIVE,
        db_index=True,
        help_text="Current status of the session"
    )
    
    # Session context (JSONB for flexibility)
    # Stores: intake rules, what fields to collect, what it can/can't do
    system_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="System rules and context for this intake session"
    )
    
    # Tracking
    last_message_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last message in this session"
    )
    message_count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total number of messages in this session"
    )
    
    # Fact-based completion tracking
    onboarding_complete = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether all required facts have been collected"
    )
    onboarding_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When onboarding was marked complete"
    )
    fact_check_cache = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cached results of fact checking"
    )
    fact_check_cache_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When fact check cache was last updated"
    )
    
    class Meta:
        db_table = "intake_sessions"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["tenant", "client", "status"]),
            models.Index(fields=["tenant", "client", "-updated_at"]),
            models.Index(fields=["tenant", "property", "status"]),
            models.Index(fields=["client", "-last_message_at"]),
        ]
    
    def __str__(self):
        title = self.title or f"Session {str(self.id)[:8]}"
        return f"{title} - {self.client.email}"
    
    def can_change_property(self) -> bool:
        """
        Check if property can be changed.
        
        RULE: One session = one home (MVP)
        Once a property is set and locked, it cannot be changed.
        """
        return not self.property_locked
    
    def lock_property(self):
        """
        Lock the property linkage.
        
        Once locked, the property cannot be changed to prevent ambiguity
        in retrieval and intake results.
        """
        if self.property:
            self.property_locked = True
            self.save(update_fields=["property_locked"])
    
    def set_property(self, property_obj):
        """
        Set the property for this session.
        
        RULE: One session = one home (MVP)
        If property is already locked, raises ValueError.
        """
        if self.property_locked and self.property != property_obj:
            raise ValueError(
                f"Cannot change property for session {self.id}: "
                "property linkage is locked (one session = one home)"
            )
        
        self.property = property_obj
        if property_obj:
            # Auto-lock when property is first set
            self.property_locked = True
        self.save(update_fields=["property", "property_locked"])


class MessageRole(models.TextChoices):
    """Role of the message sender."""
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"
    SYSTEM = "system", "System"


class IntakeMessage(TenantAwareModel):
    """
    A single message within an intake session.
    
    Messages are first-class records with timestamps and optional media references.
    User messages are stored BEFORE any AI processing runs.
    Assistant messages link back to the user message they respond to.
    """
    session = models.ForeignKey(
        IntakeSession,
        on_delete=models.CASCADE,
        related_name="messages",
        db_index=True,
        help_text="Session this message belongs to"
    )
    
    # Message content
    role = models.CharField(
        max_length=20,
        choices=MessageRole.choices,
        db_index=True,
        help_text="Role of the message sender"
    )
    content = models.TextField(
        help_text="Text content of the message"
    )
    
    # Response linking (for assistant messages)
    in_reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        help_text="The user message this assistant message responds to"
    )
    
    # Media attachments (references to uploaded files)
    # Uses existing file upload flow - stores blob_name references
    media_attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="List of media attachment references [{blob_name, content_type, file_name}]"
    )
    
    # Ordering within session
    sequence_number = models.IntegerField(
        db_index=True,
        help_text="Order of this message within the session"
    )
    
    # Processing metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional metadata (model used, token counts, etc.)"
    )
    
    class Meta:
        db_table = "intake_messages"
        ordering = ["session", "sequence_number"]
        indexes = [
            models.Index(fields=["session", "sequence_number"]),
            models.Index(fields=["session", "role"]),
            models.Index(fields=["tenant", "session", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "sequence_number"],
                name="unique_session_sequence"
            )
        ]
    
    def __str__(self):
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"[{self.role}] {preview}"


class UpdateProposalStatus(models.TextChoices):
    """Status of an update proposal."""
    PENDING = "pending", "Pending"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    APPLIED = "applied", "Applied"
    SUPERSEDED = "superseded", "Superseded"


class UpdateProposalType(models.TextChoices):
    """Types of updates that can be proposed."""
    PROPERTY_CREATE = "property_create", "Create Property"
    PROPERTY_UPDATE = "property_update", "Update Property"
    ROOM_CREATE = "room_create", "Create Room"
    ROOM_UPDATE = "room_update", "Update Room"
    MEMORY_CREATE = "memory_create", "Create Memory/Note"
    MEMORY_UPDATE = "memory_update", "Update Memory/Note"
    PREFERENCE_CREATE = "preference_create", "Create Preference"
    PREFERENCE_UPDATE = "preference_update", "Update Preference"
    DO_RULE_CREATE = "do_rule_create", "Create Do Rule"
    DO_RULE_UPDATE = "do_rule_update", "Update Do Rule"
    DONT_RULE_CREATE = "dont_rule_create", "Create Don't Rule"
    DONT_RULE_UPDATE = "dont_rule_update", "Update Don't Rule"
    PHOTO_CREATE = "photo_create", "Create Reference Photo"
    PHOTO_UPDATE = "photo_update", "Update Reference Photo"


class UpdateProposal(TenantAwareModel):
    """
    Stores AI-proposed updates to home/room/notes without applying them.
    
    The AI generates structured payloads for what should be written.
    These are stored as a ledger (not overwritten) for review and later application.
    Proposals are tied to the session and the specific message that generated them.
    
    CRITICAL BOUNDARY: Proposals vs Applied Memory
    ==============================================
    PROPOSALS are NEVER treated as truth by downstream systems.
    ONLY APPLIED canonical memory counts (Property, PropertyMemory models).
    
    This prevents half-applied intake from leaking into pricing or jobs.
    
    Downstream systems (pricing, booking, jobs) must ONLY read from:
    - Property model
    - PropertyMemory model
    - IdealConditionPhoto model
    
    They must NEVER read from:
    - UpdateProposal records (even if status=PENDING)
    - IntakeMessage records (chat transcripts)
    
    Proposals must be explicitly applied via ProposalApplicationService
    before they become part of canonical data.
    """
    session = models.ForeignKey(
        IntakeSession,
        on_delete=models.CASCADE,
        related_name="update_proposals",
        db_index=True,
        help_text="Session this proposal was generated in"
    )
    
    # Link to the assistant message that proposed this update
    source_message = models.ForeignKey(
        IntakeMessage,
        on_delete=models.CASCADE,
        related_name="proposals",
        db_index=True,
        help_text="The assistant message that generated this proposal"
    )
    
    # Proposal classification
    proposal_type = models.CharField(
        max_length=30,
        choices=UpdateProposalType.choices,
        db_index=True,
        help_text="Type of update being proposed"
    )
    status = models.CharField(
        max_length=20,
        choices=UpdateProposalStatus.choices,
        default=UpdateProposalStatus.PENDING,
        db_index=True,
        help_text="Current status of this proposal"
    )
    
    # Target reference (what entity this proposal affects)
    # For updates: the UUID of the existing entity
    # For creates: null until applied
    target_entity_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of the entity this proposal affects (null for creates)"
    )
    target_entity_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of entity (property, room, memory, etc.)"
    )
    
    # The actual proposed data (structured payload)
    proposed_data = models.JSONField(
        help_text="Structured payload of the proposed update"
    )
    
    # For deduplication: hash of key fields to detect repeat proposals
    content_hash = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Hash of proposed_data for deduplication"
    )
    
    # Human-readable summary
    summary = models.TextField(
        blank=True,
        help_text="Human-readable summary of what this proposal does"
    )
    
    # Review tracking
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this proposal was reviewed"
    )
    reviewed_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_proposals",
        help_text="User who reviewed this proposal"
    )
    
    class Meta:
        db_table = "intake_update_proposals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["session", "status"]),
            models.Index(fields=["session", "proposal_type"]),
            models.Index(fields=["tenant", "status", "-created_at"]),
            models.Index(fields=["content_hash"]),
            models.Index(fields=["source_message"]),
        ]
    
    def __str__(self):
        return f"{self.get_proposal_type_display()} - {self.get_status_display()}"
    
    @classmethod
    def compute_content_hash(cls, proposed_data: dict) -> str:
        """Compute a hash of the proposed data for deduplication."""
        # Sort keys for consistent hashing
        normalized = json.dumps(proposed_data, sort_keys=True)
        return hashlib.sha256(normalized.encode()).hexdigest()


class ProposalApplicationAuditLog(TenantAwareModel):
    """
    Audit trail for proposal applications.
    
    Records every attempt to apply proposals, including:
    - Which proposals were applied
    - Which proposals were rejected (and why)
    - What entities were created/updated
    - Which chat message/media triggered the proposal
    - Who applied it and when
    
    This provides a complete audit trail for "why does this home have this rule?"
    and prevents silent corruption of the memory layer.
    """
    # Link to the proposal that was applied/rejected
    proposal = models.ForeignKey(
        UpdateProposal,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        db_index=True,
        help_text="The proposal this audit entry relates to"
    )
    
    # Application result
    APPLICATION_RESULT_CHOICES = [
        ("applied", "Applied Successfully"),
        ("rejected", "Rejected"),
        ("failed", "Application Failed"),
    ]
    result = models.CharField(
        max_length=20,
        choices=APPLICATION_RESULT_CHOICES,
        db_index=True,
        help_text="Result of the application attempt"
    )
    
    # What entity was affected (if applied)
    affected_entity_type = models.CharField(
        max_length=50,
        blank=True,
        help_text="Type of entity that was created/updated (property, memory, etc.)"
    )
    affected_entity_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of the entity that was created/updated"
    )
    
    # Who applied it
    applied_by = models.ForeignKey(
        "users.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proposal_application_audits",
        help_text="User who applied/rejected this proposal"
    )
    
    # Source tracking
    source_message_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text="ID of the chat message that generated this proposal"
    )
    source_media_attachments = models.JSONField(
        default=list,
        blank=True,
        help_text="Media attachments from the source message"
    )
    
    # Before/after state
    previous_state = models.JSONField(
        null=True,
        blank=True,
        help_text="State before application (for updates)"
    )
    new_state = models.JSONField(
        null=True,
        blank=True,
        help_text="State after application"
    )
    
    # Error information (if failed/rejected)
    error_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Error code if application failed"
    )
    error_message = models.TextField(
        blank=True,
        help_text="Detailed error message if application failed"
    )
    rejection_reason = models.TextField(
        blank=True,
        help_text="Reason for rejection (if rejected)"
    )
    
    # Validation details
    validation_passed = models.BooleanField(
        default=True,
        help_text="Whether validation passed before application"
    )
    validation_errors = models.JSONField(
        default=list,
        blank=True,
        help_text="List of validation errors encountered"
    )
    
    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the request"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent of the request"
    )
    request_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Request ID for correlation"
    )
    
    class Meta:
        db_table = "proposal_application_audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["proposal", "-created_at"]),
            models.Index(fields=["tenant", "result", "-created_at"]),
            models.Index(fields=["applied_by", "-created_at"]),
            models.Index(fields=["affected_entity_type", "affected_entity_id"]),
            models.Index(fields=["source_message_id"]),
        ]
    
    def __str__(self):
        return f"{self.get_result_display()} - {self.proposal.get_proposal_type_display()}"


class IntakeMessageUsage(TenantAwareModel):
    """
    Tracks LLM API calls per user per day for rate limiting.
    
    This ensures fair usage and prevents abuse of the intake chat system.
    """
    user = models.ForeignKey(
        "users.User",
        on_delete=models.CASCADE,
        related_name="intake_message_usage",
        db_index=True,
        help_text="User who made the LLM request"
    )
    
    date = models.DateField(
        db_index=True,
        help_text="Date in YYYY-MM-DD format"
    )
    
    count = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Number of LLM calls made on this date"
    )
    
    class Meta:
        db_table = "intake_message_usage"
        unique_together = [["tenant", "user", "date"]]
        indexes = [
            models.Index(fields=["tenant", "user", "date"]),
            models.Index(fields=["tenant", "date"]),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.date}: {self.count} calls"
    
    @staticmethod
    def get_current_date():
        """Get current date."""
        from django.utils import timezone
        return timezone.now().date()
    
    @staticmethod
    def get_or_create_usage(user):
        """Get or create usage record for current date."""
        from django.utils import timezone
        date = timezone.now().date()
        usage, created = IntakeMessageUsage.objects.get_or_create(
            tenant=user.tenant,
            user=user,
            date=date,
            defaults={"count": 0}
        )
        return usage
    
    @staticmethod
    def increment_usage(user):
        """Increment usage count for current date."""
        usage = IntakeMessageUsage.get_or_create_usage(user)
        usage.count += 1
        usage.save(update_fields=["count", "updated_at"])
        return usage
    
    @staticmethod
    def get_usage_count(user):
        """Get current date's usage count for user."""
        from django.utils import timezone
        date = timezone.now().date()
        try:
            usage = IntakeMessageUsage.objects.get(
                tenant=user.tenant,
                user=user,
                date=date
            )
            return usage.count
        except IntakeMessageUsage.DoesNotExist:
            return 0
    
    @staticmethod
    def can_make_request(user, limit: int = 100):
        """
        Check if user can make an intake message request.
        
        Args:
            user: The user
            limit: Daily limit (default: 100 messages per day)
            
        Returns:
            Tuple of (can_make_request, current_count, limit)
        """
        current_count = IntakeMessageUsage.get_usage_count(user)
        return current_count < limit, current_count, limit
