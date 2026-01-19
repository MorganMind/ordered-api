# Intake Chat Frontend Integration Reference

## API Endpoints

### Session Management

#### `GET /api/v1/intake/sessions/`
List intake sessions for the authenticated client.

**Query Parameters:**
- `status` (optional): Filter by status (active, paused, completed, abandoned)
- `limit` (optional, default: 20, max: 100): Number of results
- `offset` (optional, default: 0): Pagination offset

**Response:**
```json
{
  "sessions": [...],
  "total": 10,
  "limit": 20,
  "offset": 0
}
```

#### `POST /api/v1/intake/sessions/`
Create a new intake session.

**Request Body:**
```json
{
  "property_id": "uuid" (optional),
  "title": "string" (optional),
  "auto_greet": true (optional, default: true)
}
```

**Response:**
```json
{
  "id": "uuid",
  "title": "string",
  "status": "active",
  "status_display": "Active",
  "property_id": "uuid" (nullable),
  "property_address": "string" (nullable),
  "message_count": 0,
  "last_message_at": "datetime" (nullable),
  "created_at": "datetime",
  "updated_at": "datetime",
  "onboarding_progress": {...},
  "greeting_message": {...} (if auto_greet=true)
}
```

#### `GET /api/v1/intake/sessions/{session_id}/`
Get session details including messages and pending proposals.

**Response:**
```json
{
  "id": "uuid",
  "title": "string",
  "status": "active",
  "status_display": "Active",
  "property_id": "uuid" (nullable),
  "property_address": "string" (nullable),
  "message_count": 5,
  "last_message_at": "datetime",
  "created_at": "datetime",
  "updated_at": "datetime",
  "messages": [...],
  "pending_proposals": [...],
  "onboarding_progress": {...}
}
```

#### `PATCH /api/v1/intake/sessions/{session_id}/status/`
Update session status.

**Request Body:**
```json
{
  "status": "active|paused|completed|abandoned"
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "completed",
  ...
}
```

### Messaging

#### `GET /api/v1/intake/sessions/{session_id}/messages/`
Get paginated messages for a session.

**Query Parameters:**
- `limit` (optional, default: 50, max: 100): Number of messages
- `before_sequence` (optional): Get messages before this sequence number

**Response:**
```json
{
  "messages": [...],
  "has_more": true
}
```

#### `POST /api/v1/intake/sessions/{session_id}/send/`
Send a user message and receive AI response.

**Request Body:**
```json
{
  "content": "string" (required, 1-10000 chars),
  "media_attachments": [
    {
      "blob_name": "string",
      "content_type": "string",
      "file_name": "string"
    }
  ] (optional)
}
```

**Response:**
```json
{
  "user_message": {...},
  "assistant_message": {...},
  "new_proposals": [...],
  "fact_status": {...},
  "ready_to_proceed": false
}
```

**Error Responses:**
- `429 Too Many Requests`: Rate limit exceeded (100 messages/day)
- `500 Internal Server Error`: AI processing failed (user message still saved)

#### `POST /api/v1/intake/sessions/{session_id}/messages/{message_id}/retry/`
Retry generating assistant response for a user message (idempotent).

**Response:**
```json
{
  "user_message": {...},
  "assistant_message": {...},
  "new_proposals": [...],
  "fact_status": {...},
  "ready_to_proceed": false,
  "regenerated": true
}
```

### Proposals & Progress

#### `GET /api/v1/intake/sessions/{session_id}/proposals/`
Get all pending proposals for a session.

**Response:**
```json
{
  "proposals": [...]
}
```

#### `GET /api/v1/intake/sessions/{session_id}/progress/`
Get onboarding progress for a session.

**Response:**
```json
{
  "progress": {
    "property_type": "single_family",
    "overall_completion": 65.5,
    "required_completion": 80.0,
    "categories": {...},
    "missing_required": ["address", "access_method"],
    "missing_important": ["square_feet"],
    "suggested_next_topic": "access",
    "suggested_next_fields": ["access_method", "access_details"]
  }
}
```

#### `GET /api/v1/intake/sessions/{session_id}/fact-status/`
Get fact-based onboarding status.

**Response:**
```json
{
  "fact_status": {
    "property_exists": true,
    "all_critical_facts_complete": false,
    "ready_to_proceed": false,
    "completion_percentage": 75.0,
    "missing_critical": ["access_method"],
    "missing_optional": ["service_frequency"],
    "next_to_collect": "access_method",
    "by_category": {...}
  },
  "ready_to_proceed": false,
  "missing_summary": "Still need to collect:\nAccess:\n  - How to access the property",
  "next_question_hint": "How will our team access your home?"
}
```

### Proposal Management

#### `POST /api/v1/intake/sessions/{session_id}/proposals/{proposal_id}/apply/`
Apply a single proposal to canonical data (idempotent).

**Response:**
```json
{
  "success": true,
  "entity_type": "property",
  "entity_id": "uuid",
  "message": "Property created"
}
```

**Error Responses:**
- `400 Bad Request`: Validation failed
- `500 Internal Server Error`: Application failed

#### `POST /api/v1/intake/sessions/{session_id}/proposals/apply-multiple/`
Apply multiple proposals in a single transaction (partial acceptance supported).

**Request Body:**
```json
{
  "proposal_ids": ["uuid1", "uuid2", ...] (1-50 proposals)
}
```

**Response:**
```json
{
  "successful": [
    {
      "proposal_id": "uuid",
      "success": true,
      "entity_type": "memory",
      "entity_id": "uuid",
      "message": "Memory created"
    }
  ],
  "failed": [
    {
      "proposal_id": "uuid",
      "error": "Validation failed: ...",
      "error_type": "validation"
    }
  ],
  "total": 5
}
```

#### `POST /api/v1/intake/sessions/{session_id}/proposals/{proposal_id}/reject/`
Reject a proposal.

**Request Body:**
```json
{
  "reason": "string" (optional, max 500 chars)
}
```

**Response:**
```json
{
  "id": "uuid",
  "status": "rejected",
  ...
}
```

### Outcome & Output

#### `GET /api/v1/intake/sessions/{session_id}/output/`
Get structured intake output for downstream systems (pricing, booking).

**Response:**
```json
{
  "session_id": "uuid",
  "property_id": "uuid",
  "onboarding_complete": true,
  "home_basics": {...},
  "property_characteristics": {...},
  "service_preferences": {...},
  "scope_signals": {...},
  "rules_and_preferences": {...},
  "access": {...},
  "general_notes": [...],
  "reference_photos": [...]
}
```

#### `GET /api/v1/intake/sessions/{session_id}/outcome/`
Get complete intake outcome (applied data only, no proposals or chat).

**Response:**
```json
{
  "session": {
    "id": "uuid",
    "status": "completed",
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "property_id": "uuid" (nullable),
  "has_property": true,
  "property": {...} (nullable),
  "rooms": [...],
  "standards": {
    "do_rules": [...],
    "dont_rules": [...],
    "product_preferences": [...],
    "sensitivities": [...],
    "general_notes": [...],
    "summary": {...}
  },
  "readiness": {
    "status": "ready|incomplete|not_ready",
    "is_ready": true,
    "completion_percentage": 100.0,
    "missing": {...} (nullable)
  },
  "generated_at": "datetime"
}
```

#### `GET /api/v1/intake/property/{property_id}/outcome/`
Get intake outcome by property ID (finds most recent session).

**Response:** Same as session outcome endpoint.

---

## Schema Definitions

### IntakeSession

```python
{
  "id": "uuid",
  "client": "user_id",
  "property": "property_id" (nullable),
  "property_locked": boolean,
  "title": "string",
  "status": "active|paused|completed|abandoned",
  "system_context": {},
  "last_message_at": "datetime" (nullable),
  "message_count": integer,
  "onboarding_complete": boolean,
  "onboarding_completed_at": "datetime" (nullable),
  "fact_check_cache": {},
  "fact_check_cache_updated_at": "datetime" (nullable),
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### IntakeMessage

```python
{
  "id": "uuid",
  "session": "session_id",
  "role": "user|assistant|system",
  "content": "string",
  "in_reply_to": "message_id" (nullable),
  "media_attachments": [
    {
      "blob_name": "string",
      "content_type": "string",
      "file_name": "string"
    }
  ],
  "sequence_number": integer,
  "metadata": {},
  "created_at": "datetime"
}
```

### UpdateProposal

```python
{
  "id": "uuid",
  "session": "session_id",
  "source_message": "message_id",
  "proposal_type": "property_create|property_update|room_create|room_update|memory_create|memory_update|preference_create|preference_update|do_rule_create|do_rule_update|dont_rule_create|dont_rule_update|photo_create|photo_update",
  "status": "pending|approved|rejected|applied|superseded",
  "target_entity_id": "uuid" (nullable),
  "target_entity_type": "string",
  "proposed_data": {},
  "content_hash": "string",
  "summary": "string",
  "reviewed_at": "datetime" (nullable),
  "reviewed_by": "user_id" (nullable),
  "created_at": "datetime"
}
```

### OnboardingProgress

```python
{
  "property_type": "string",
  "overall_completion": float (0-100),
  "required_completion": float (0-100),
  "categories": {
    "category_name": {
      "completion": float,
      "required_complete": integer,
      "required_total": integer,
      "important_complete": integer,
      "important_total": integer
    }
  },
  "missing_required": ["field_key", ...],
  "missing_important": ["field_key", ...],
  "suggested_next_topic": "string" (nullable),
  "suggested_next_fields": ["field_key", ...]
}
```

### OnboardingFactStatus

```python
{
  "property_exists": boolean,
  "all_critical_facts_complete": boolean,
  "ready_to_proceed": boolean,
  "completion_percentage": float (0-100),
  "missing_critical": ["fact_key", ...],
  "missing_optional": ["fact_key", ...],
  "next_to_collect": "fact_key" (nullable),
  "by_category": {
    "category": {
      "fact_key": "complete|partial|missing"
    }
  }
}
```

### IntakeOutcome

```python
{
  "session": {
    "id": "uuid",
    "status": "string",
    "created_at": "datetime",
    "updated_at": "datetime"
  },
  "property_id": "uuid" (nullable),
  "has_property": boolean,
  "property": {
    "id": "uuid",
    "address": "string",
    "address_line_1": "string" (nullable),
    "city": "string" (nullable),
    "state": "string" (nullable),
    "zip_code": "string" (nullable),
    "property_type": "string" (nullable),
    "square_feet": integer (nullable),
    "bedrooms": integer (nullable),
    "bathrooms": float (nullable),
    "num_floors": integer (nullable),
    "year_built": integer (nullable),
    "access_instructions": "string" (nullable),
    "parking_instructions": "string" (nullable)
  } (nullable),
  "rooms": [
    {
      "name": "string",
      "display_name": "string",
      "notes": ["string", ...],
      "surfaces": ["string", ...]
    }
  ],
  "standards": {
    "do_rules": [
      {
        "id": "uuid",
        "rule_type": "do",
        "content": "string",
        "room_name": "string" (nullable),
        "surface_name": "string" (nullable),
        "priority": integer
      }
    ],
    "dont_rules": [...],
    "product_preferences": [
      {
        "id": "uuid",
        "product_name": "string",
        "use_product": boolean,
        "notes": "string" (nullable),
        "room_name": "string" (nullable)
      }
    ],
    "sensitivities": [
      {
        "id": "uuid",
        "content": "string",
        "severity": "string" (nullable)
      }
    ],
    "general_notes": [
      {
        "id": "uuid",
        "content": "string",
        "room_name": "string" (nullable),
        "surface_name": "string" (nullable),
        "label": "string" (nullable),
        "created_at": "datetime" (nullable)
      }
    ],
    "summary": {
      "total_rules": integer,
      "total_product_preferences": integer,
      "total_sensitivities": integer,
      "total_notes": integer
    }
  },
  "readiness": {
    "status": "ready|incomplete|not_ready",
    "is_ready": boolean,
    "completion_percentage": float,
    "missing": {
      "categories": ["string", ...],
      "details": {
        "category": ["description", ...]
      }
    } (nullable)
  },
  "generated_at": "datetime"
}
```

---

## Complete File Contents

### apps/intake/models.py

```python
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
```

### apps/intake/serializers.py

```python
"""
Serializers for intake session API.
"""
from rest_framework import serializers
from apps.intake.models import (
    IntakeSession,
    IntakeSessionStatus,
    IntakeMessage,
    MessageRole,
    UpdateProposal,
    UpdateProposalStatus,
)


class MediaAttachmentSerializer(serializers.Serializer):
    """Serializer for media attachment references."""
    blob_name = serializers.CharField(max_length=500)
    content_type = serializers.CharField(max_length=100)
    file_name = serializers.CharField(max_length=255)


class IntakeMessageSerializer(serializers.ModelSerializer):
    """Serializer for intake messages."""
    media_attachments = MediaAttachmentSerializer(many=True, read_only=True)
    in_reply_to_id = serializers.UUIDField(
        source="in_reply_to.id", 
        read_only=True, 
        allow_null=True
    )
    
    class Meta:
        model = IntakeMessage
        fields = [
            "id",
            "role",
            "content",
            "media_attachments",
            "in_reply_to_id",
            "sequence_number",
            "created_at",
        ]
        read_only_fields = fields


class UpdateProposalSerializer(serializers.ModelSerializer):
    """Serializer for update proposals."""
    proposal_type_display = serializers.CharField(
        source="get_proposal_type_display",
        read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True
    )
    
    class Meta:
        model = UpdateProposal
        fields = [
            "id",
            "proposal_type",
            "proposal_type_display",
            "status",
            "status_display",
            "target_entity_id",
            "target_entity_type",
            "proposed_data",
            "summary",
            "created_at",
        ]
        read_only_fields = fields


class OnboardingProgressSerializer(serializers.Serializer):
    """Serializer for onboarding progress."""
    property_type = serializers.CharField()
    overall_completion = serializers.FloatField()
    required_completion = serializers.FloatField()
    categories = serializers.DictField()
    missing_required = serializers.ListField(child=serializers.CharField())
    missing_important = serializers.ListField(child=serializers.CharField())
    suggested_next_topic = serializers.CharField(allow_null=True)
    suggested_next_fields = serializers.ListField(child=serializers.CharField())


class IntakeSessionSerializer(serializers.ModelSerializer):
    """Serializer for intake sessions."""
    property_id = serializers.UUIDField(
        source="property.id", 
        read_only=True, 
        allow_null=True
    )
    property_address = serializers.CharField(
        source="property.address", 
        read_only=True, 
        allow_null=True
    )
    status_display = serializers.CharField(
        source="get_status_display", 
        read_only=True
    )
    
    class Meta:
        model = IntakeSession
        fields = [
            "id",
            "title",
            "status",
            "status_display",
            "property_id",
            "property_address",
            "message_count",
            "last_message_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IntakeSessionDetailSerializer(IntakeSessionSerializer):
    """Detailed serializer including messages, proposals, and progress."""
    messages = IntakeMessageSerializer(many=True, read_only=True)
    pending_proposals = UpdateProposalSerializer(many=True, read_only=True)
    onboarding_progress = serializers.SerializerMethodField()
    
    class Meta(IntakeSessionSerializer.Meta):
        fields = IntakeSessionSerializer.Meta.fields + [
            "messages",
            "pending_proposals",
            "onboarding_progress",
        ]
    
    def get_onboarding_progress(self, obj):
        from apps.intake.services import IntakeSessionService
        progress = IntakeSessionService.get_onboarding_progress(obj)
        return progress.to_dict()


class CreateSessionRequestSerializer(serializers.Serializer):
    """Request serializer for creating a session."""
    property_id = serializers.UUIDField(required=False, allow_null=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    auto_greet = serializers.BooleanField(default=True)


class SendMessageRequestSerializer(serializers.Serializer):
    """Request serializer for sending a message."""
    content = serializers.CharField(min_length=1, max_length=10000)
    media_attachments = MediaAttachmentSerializer(many=True, required=False)


class SendMessageResponseSerializer(serializers.Serializer):
    """Response serializer for send message endpoint."""
    user_message = IntakeMessageSerializer()
    assistant_message = IntakeMessageSerializer()
    new_proposals = UpdateProposalSerializer(many=True)
    onboarding_progress = OnboardingProgressSerializer()


class ApplyProposalRequestSerializer(serializers.Serializer):
    """Request serializer for applying a proposal."""
    proposal_id = serializers.UUIDField(required=True)


class ApplyMultipleProposalsRequestSerializer(serializers.Serializer):
    """Request serializer for applying multiple proposals."""
    proposal_ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
        max_length=50,
    )


class RejectProposalRequestSerializer(serializers.Serializer):
    """Request serializer for rejecting a proposal."""
    reason = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        help_text="Optional reason for rejection"
    )


class ProposalApplicationResultSerializer(serializers.Serializer):
    """Serializer for proposal application result."""
    success = serializers.BooleanField()
    entity_type = serializers.CharField(allow_null=True)
    entity_id = serializers.UUIDField(allow_null=True)
    message = serializers.CharField()


class ApplyProposalsResponseSerializer(serializers.Serializer):
    """Response serializer for applying proposals."""
    successful = ProposalApplicationResultSerializer(many=True)
    failed = serializers.ListField(
        child=serializers.DictField()
    )
    total = serializers.IntegerField()


# Outcome serializers
class PropertyDetailsSerializer(serializers.Serializer):
    """Serializer for property details in outcome."""
    id = serializers.CharField()
    address = serializers.CharField()
    address_line_1 = serializers.CharField(allow_null=True)
    city = serializers.CharField(allow_null=True)
    state = serializers.CharField(allow_null=True)
    zip_code = serializers.CharField(allow_null=True)
    property_type = serializers.CharField(allow_null=True)
    square_feet = serializers.IntegerField(allow_null=True)
    bedrooms = serializers.IntegerField(allow_null=True)
    bathrooms = serializers.FloatField(allow_null=True)
    num_floors = serializers.IntegerField(allow_null=True)
    year_built = serializers.IntegerField(allow_null=True)
    access_instructions = serializers.CharField(allow_null=True)
    parking_instructions = serializers.CharField(allow_null=True)


class RoomInfoSerializer(serializers.Serializer):
    """Serializer for room info in outcome."""
    name = serializers.CharField()
    display_name = serializers.CharField()
    notes = serializers.ListField(child=serializers.CharField())
    surfaces = serializers.ListField(child=serializers.CharField())


class StandardRuleSerializer(serializers.Serializer):
    """Serializer for do/don't rules."""
    id = serializers.CharField()
    rule_type = serializers.CharField()
    content = serializers.CharField()
    room_name = serializers.CharField(allow_null=True)
    surface_name = serializers.CharField(allow_null=True)
    priority = serializers.IntegerField()


class ProductPreferenceSerializer(serializers.Serializer):
    """Serializer for product preferences."""
    id = serializers.CharField()
    product_name = serializers.CharField()
    use_product = serializers.BooleanField()
    notes = serializers.CharField(allow_null=True)
    room_name = serializers.CharField(allow_null=True)


class SensitivitySerializer(serializers.Serializer):
    """Serializer for sensitivities."""
    id = serializers.CharField()
    content = serializers.CharField()
    severity = serializers.CharField(allow_null=True)


class GeneralNoteSerializer(serializers.Serializer):
    """Serializer for general notes."""
    id = serializers.CharField()
    content = serializers.CharField()
    room_name = serializers.CharField(allow_null=True)
    surface_name = serializers.CharField(allow_null=True)
    label = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField(allow_null=True)


class StandardsSummarySerializer(serializers.Serializer):
    """Summary counts for standards."""
    total_rules = serializers.IntegerField()
    total_product_preferences = serializers.IntegerField()
    total_sensitivities = serializers.IntegerField()
    total_notes = serializers.IntegerField()


class StandardsSerializer(serializers.Serializer):
    """Serializer for all standards."""
    do_rules = StandardRuleSerializer(many=True)
    dont_rules = StandardRuleSerializer(many=True)
    product_preferences = ProductPreferenceSerializer(many=True)
    sensitivities = SensitivitySerializer(many=True)
    general_notes = GeneralNoteSerializer(many=True)
    summary = StandardsSummarySerializer()


class MissingInfoSerializer(serializers.Serializer):
    """Serializer for missing info."""
    categories = serializers.ListField(child=serializers.CharField())
    details = serializers.DictField()


class ReadinessInfoSerializer(serializers.Serializer):
    """Serializer for readiness status."""
    status = serializers.CharField()
    is_ready = serializers.BooleanField()
    completion_percentage = serializers.FloatField()
    missing = MissingInfoSerializer(allow_null=True, required=False)


class SessionInfoSerializer(serializers.Serializer):
    """Serializer for session info in outcome."""
    id = serializers.CharField()
    status = serializers.CharField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class IntakeOutcomeSerializer(serializers.Serializer):
    """
    Serializer for the complete intake outcome.
    
    This is the main response format for the outcome endpoint.
    """
    session = SessionInfoSerializer()
    property_id = serializers.CharField(allow_null=True)
    has_property = serializers.BooleanField()
    property = PropertyDetailsSerializer(allow_null=True)
    rooms = RoomInfoSerializer(many=True)
    standards = StandardsSerializer()
    readiness = ReadinessInfoSerializer()
    generated_at = serializers.DateTimeField()
```

### apps/intake/views.py

[Full file content from earlier read - 956 lines]

### apps/intake/urls.py

[Full file content from earlier read - 110 lines]

### apps/intake/services.py

[Full file content from earlier read - 945 lines]

### apps/intake/services/proposal_application.py

[Full file content from earlier read - 1108 lines]

### apps/intake/services/intake_output.py

[Full file content from earlier read - 291 lines]

### apps/intake/outcome.py

[Full file content from earlier read - 502 lines]

### apps/intake/onboarding_schema.py

[Full file content from earlier read - 439 lines]

### apps/intake/onboarding_tracker.py

[Full file content from earlier read - 672 lines]

### apps/intake/context_builder.py

[Full file content from earlier read - 297 lines]

### apps/intake/fact_requirements.py

[Full file content from earlier read - 626 lines]
