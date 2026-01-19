# Intake Chat API Reference

API reference for frontend integration. This document contains only endpoints, request/response schemas, and data structures. No backend code.

---

## Base URL

All endpoints are prefixed with `/api/v1/`

---

## Authentication

All endpoints require authentication via `SupabaseAuthentication`. Include the authentication token in the request headers.

**Required Role:** `CLIENT` (most endpoints), `ADMIN` (outcome endpoints)

---

## API Endpoints

### Session Management

#### `GET /api/v1/intake/sessions/`
List intake sessions for the authenticated client.

**Query Parameters:**
- `status` (optional): Filter by status (`active`, `paused`, `completed`, `abandoned`)
- `limit` (optional, default: 20, max: 100): Number of results
- `offset` (optional, default: 0): Pagination offset

**Response:**
```json
{
  "sessions": [
    {
      "id": "uuid",
      "title": "string",
      "status": "active",
      "status_display": "Active",
      "property_id": "uuid" (nullable),
      "property_address": "string" (nullable),
      "message_count": 5,
      "last_message_at": "2024-01-15T10:30:00Z",
      "created_at": "2024-01-15T09:00:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
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
  "message_count": 1,
  "last_message_at": "2024-01-15T10:00:00Z",
  "created_at": "2024-01-15T10:00:00Z",
  "updated_at": "2024-01-15T10:00:00Z",
  "onboarding_progress": {
    "property_type": "single_family",
    "overall_completion": 0.0,
    "required_completion": 0.0,
    "categories": {},
    "missing_required": ["address", "property_type", "num_bedrooms", "num_bathrooms", "access_method", "access_details", "room_list", "standards_discussed", "service_type"],
    "missing_important": [],
    "suggested_next_topic": "property_basics",
    "suggested_next_fields": ["address"]
  },
  "greeting_message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Hi! I'm here to help set up your home profile...",
    "media_attachments": [],
    "in_reply_to_id": null,
    "sequence_number": 1,
    "created_at": "2024-01-15T10:00:00Z"
  }
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
  "last_message_at": "2024-01-15T10:30:00Z",
  "created_at": "2024-01-15T09:00:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "messages": [
    {
      "id": "uuid",
      "role": "user|assistant|system",
      "content": "string",
      "media_attachments": [],
      "in_reply_to_id": "uuid" (nullable),
      "sequence_number": 1,
      "created_at": "2024-01-15T10:00:00Z"
    }
  ],
  "pending_proposals": [
    {
      "id": "uuid",
      "proposal_type": "property_create",
      "proposal_type_display": "Create Property",
      "status": "pending",
      "status_display": "Pending",
      "target_entity_id": null,
      "target_entity_type": "property",
      "proposed_data": {},
      "summary": "Create property at 123 Main St",
      "created_at": "2024-01-15T10:05:00Z"
    }
  ],
  "onboarding_progress": {}
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
  "status_display": "Completed",
  ...
}
```

---

### Messaging

#### `GET /api/v1/intake/sessions/{session_id}/messages/`
Get paginated messages for a session.

**Query Parameters:**
- `limit` (optional, default: 50, max: 100): Number of messages
- `before_sequence` (optional): Get messages before this sequence number

**Response:**
```json
{
  "messages": [
    {
      "id": "uuid",
      "role": "user",
      "content": "I have a 3 bedroom house",
      "media_attachments": [],
      "in_reply_to_id": null,
      "sequence_number": 2,
      "created_at": "2024-01-15T10:05:00Z"
    }
  ],
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
      "content_type": "image/jpeg",
      "file_name": "photo.jpg"
    }
  ] (optional)
}
```

**Response:**
```json
{
  "user_message": {
    "id": "uuid",
    "role": "user",
    "content": "I have a 3 bedroom house",
    "media_attachments": [],
    "in_reply_to_id": null,
    "sequence_number": 2,
    "created_at": "2024-01-15T10:05:00Z"
  },
  "assistant_message": {
    "id": "uuid",
    "role": "assistant",
    "content": "Great! How many bathrooms does it have?",
    "media_attachments": [],
    "in_reply_to_id": "uuid",
    "sequence_number": 3,
    "created_at": "2024-01-15T10:05:05Z"
  },
  "new_proposals": [
    {
      "id": "uuid",
      "proposal_type": "property_update",
      "proposal_type_display": "Update Property",
      "status": "pending",
      "status_display": "Pending",
      "target_entity_id": "uuid",
      "target_entity_type": "property",
      "proposed_data": {
        "bedrooms": 3
      },
      "summary": "Update property bedrooms to 3",
      "created_at": "2024-01-15T10:05:05Z"
    }
  ],
  "fact_status": {
    "property_exists": true,
    "all_critical_facts_complete": false,
    "ready_to_proceed": false,
    "completion_percentage": 25.0,
    "missing_critical": ["num_bathrooms", "access_method", "room_list", "standards_discussed", "service_type"],
    "missing_optional": ["service_frequency"],
    "next_to_collect": "num_bathrooms",
    "by_category": {
      "property": {
        "property_size": "partial"
      }
    }
  },
  "ready_to_proceed": false
}
```

**Error Responses:**
- `400 Bad Request`: Invalid request body
- `403 Forbidden`: Not a client user
- `404 Not Found`: Session not found
- `429 Too Many Requests`: Rate limit exceeded (100 messages/day)
  ```json
  {
    "error": "Rate limit exceeded",
    "message": "You have reached the daily limit of 100 messages. Please try again tomorrow.",
    "current_count": 100,
    "limit": 100
  }
  ```
- `500 Internal Server Error`: AI processing failed (user message still saved)
  ```json
  {
    "user_message": {...},
    "assistant_message": null,
    "new_proposals": [],
    "fact_status": null,
    "error": "AI processing failed, please try again"
  }
  ```

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

---

### Proposals & Progress

#### `GET /api/v1/intake/sessions/{session_id}/proposals/`
Get all pending proposals for a session.

**Response:**
```json
{
  "proposals": [
    {
      "id": "uuid",
      "proposal_type": "memory_create",
      "proposal_type_display": "Create Memory/Note",
      "status": "pending",
      "status_display": "Pending",
      "target_entity_id": null,
      "target_entity_type": "memory",
      "proposed_data": {
        "memory_type": "note",
        "content": "Kitchen has granite countertops",
        "room_name": "kitchen"
      },
      "summary": "Note about kitchen countertops",
      "created_at": "2024-01-15T10:10:00Z"
    }
  ]
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
    "categories": {
      "property_basics": {
        "completion": 75.0,
        "required_complete": 3,
        "required_total": 4,
        "important_complete": 1,
        "important_total": 2
      },
      "access": {
        "completion": 50.0,
        "required_complete": 1,
        "required_total": 2,
        "important_complete": 0,
        "important_total": 1
      }
    },
    "missing_required": ["access_method", "room_list"],
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
    "by_category": {
      "property": {
        "property_exists": "complete",
        "property_type": "complete",
        "property_size": "complete"
      },
      "access": {
        "access_method": "missing"
      }
    }
  },
  "ready_to_proceed": false,
  "missing_summary": "Still need to collect:\nAccess:\n  - How to access the property",
  "next_question_hint": "How will our team access your home?"
}
```

---

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
  ```json
  {
    "error": "Validation failed: Property required for this proposal type"
  }
  ```
- `404 Not Found`: Proposal not found
- `500 Internal Server Error`: Application failed

#### `POST /api/v1/intake/sessions/{session_id}/proposals/apply-multiple/`
Apply multiple proposals in a single transaction (partial acceptance supported).

**Request Body:**
```json
{
  "proposal_ids": ["uuid1", "uuid2", "uuid3"] (1-50 proposals)
}
```

**Response:**
```json
{
  "successful": [
    {
      "proposal_id": "uuid1",
      "success": true,
      "entity_type": "memory",
      "entity_id": "uuid",
      "message": "Memory created"
    },
    {
      "proposal_id": "uuid2",
      "success": true,
      "entity_type": "property",
      "entity_id": "uuid",
      "message": "Property updated"
    }
  ],
  "failed": [
    {
      "proposal_id": "uuid3",
      "error": "Validation failed: Property required for this proposal type",
      "error_type": "validation"
    }
  ],
  "total": 3
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
  "proposal_type": "memory_create",
  "status": "rejected",
  "status_display": "Rejected",
  "target_entity_id": null,
  "target_entity_type": "memory",
  "proposed_data": {...},
  "summary": "Note about kitchen [REJECTED: Not accurate]",
  "created_at": "2024-01-15T10:10:00Z"
}
```

---

### Outcome & Output

#### `GET /api/v1/intake/sessions/{session_id}/output/`
Get structured intake output for downstream systems (pricing, booking).

**Response:**
```json
{
  "session_id": "uuid",
  "property_id": "uuid",
  "onboarding_complete": true,
  "home_basics": {
    "address": "123 Main Street, Austin, TX 78701",
    "address_line_1": "123 Main Street",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78701",
    "country": "USA"
  },
  "property_characteristics": {
    "property_type": "single_family",
    "square_feet": 2400,
    "bedrooms": 4,
    "bathrooms": 2.5,
    "year_built": 2015,
    "lot_size_sqft": null
  },
  "service_preferences": {
    "service_type": "regular",
    "frequency": "biweekly"
  },
  "scope_signals": {
    "rooms_identified": ["kitchen", "living room", "master bedroom", "master bathroom"],
    "priority_areas": [
      {
        "room": "kitchen",
        "note": "Granite counters need special care"
      }
    ]
  },
  "rules_and_preferences": {
    "do_rules": [
      {
        "id": "uuid",
        "content": "Always use microfiber cloths on wood surfaces",
        "label": "Do Rule",
        "level": "property",
        "room_name": null,
        "surface_name": null,
        "priority": 1
      }
    ],
    "dont_rules": [
      {
        "id": "uuid",
        "content": "No bleach products anywhere in the house",
        "label": "Don't Rule",
        "level": "property",
        "room_name": null,
        "surface_name": null,
        "priority": 2
      }
    ],
    "product_preferences": [
      {
        "id": "uuid",
        "product_name": "Method All-Purpose Cleaner",
        "use_product": true,
        "content": "Client prefers this brand",
        "level": "property",
        "room_name": null
      }
    ],
    "sensitivities": [
      {
        "id": "uuid",
        "content": "Strong chemical scents trigger migraines",
        "label": "Sensitivity",
        "level": "property",
        "room_name": null
      }
    ]
  },
  "access": {
    "instructions": "Lockbox on back door, code 1234"
  },
  "general_notes": [
    {
      "id": "uuid",
      "content": "Two dogs will be in the backyard during service",
      "label": "Pets",
      "room_name": null,
      "level": "property"
    }
  ],
  "reference_photos": [
    {
      "id": "uuid",
      "file_name": "kitchen.jpg",
      "file_url": "https://...",
      "thumbnail_url": "https://...",
      "room_name": "kitchen",
      "surface_name": "countertops",
      "location_description": "Kitchen island",
      "caption": "Ideal condition for granite countertops"
    }
  ]
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
    "created_at": "2024-01-15T10:00:00Z",
    "updated_at": "2024-01-15T11:45:00Z"
  },
  "property_id": "uuid",
  "has_property": true,
  "property": {
    "id": "uuid",
    "address": "123 Main Street, Austin, TX 78701",
    "address_line_1": "123 Main Street",
    "city": "Austin",
    "state": "TX",
    "zip_code": "78701",
    "property_type": "single_family",
    "square_feet": 2400,
    "bedrooms": 4,
    "bathrooms": 2.5,
    "num_floors": null,
    "year_built": 2015,
    "access_instructions": "Lockbox on back door, code 1234",
    "parking_instructions": null
  },
  "rooms": [
    {
      "name": "kitchen",
      "display_name": "Kitchen",
      "notes": [
        "Granite counters need special care",
        "Don't use acidic cleaners"
      ],
      "surfaces": ["granite countertops", "hardwood floors", "stainless appliances"]
    },
    {
      "name": "master bedroom",
      "display_name": "Master Bedroom",
      "notes": ["Please make bed with hospital corners"],
      "surfaces": ["carpet", "wood furniture"]
    }
  ],
  "standards": {
    "do_rules": [
      {
        "id": "uuid",
        "rule_type": "do",
        "content": "Always use microfiber cloths on wood surfaces",
        "room_name": null,
        "surface_name": null,
        "priority": 1
      }
    ],
    "dont_rules": [
      {
        "id": "uuid",
        "rule_type": "dont",
        "content": "No bleach products anywhere in the house",
        "room_name": null,
        "surface_name": null,
        "priority": 2
      }
    ],
    "product_preferences": [
      {
        "id": "uuid",
        "product_name": "Method All-Purpose Cleaner",
        "use_product": true,
        "notes": "Client prefers this brand",
        "room_name": null
      }
    ],
    "sensitivities": [
      {
        "id": "uuid",
        "content": "Strong chemical scents trigger migraines",
        "severity": null
      }
    ],
    "general_notes": [
      {
        "id": "uuid",
        "content": "Two dogs will be in the backyard during service",
        "room_name": null,
        "surface_name": null,
        "label": "Pets",
        "created_at": "2024-01-15T11:00:00Z"
      }
    ],
    "summary": {
      "total_rules": 2,
      "total_product_preferences": 1,
      "total_sensitivities": 1,
      "total_notes": 1
    }
  },
  "readiness": {
    "status": "ready",
    "is_ready": true,
    "completion_percentage": 100.0,
    "missing": null
  },
  "generated_at": "2024-01-15T12:00:00Z"
}
```

**Not Ready Response:**
```json
{
  "session": {...},
  "property_id": "uuid",
  "has_property": true,
  "property": {...},
  "rooms": [],
  "standards": {
    "do_rules": [],
    "dont_rules": [],
    "product_preferences": [],
    "sensitivities": [],
    "general_notes": [],
    "summary": {
      "total_rules": 0,
      "total_product_preferences": 0,
      "total_sensitivities": 0,
      "total_notes": 0
    }
  },
  "readiness": {
    "status": "incomplete",
    "is_ready": false,
    "completion_percentage": 37.5,
    "missing": {
      "categories": ["access", "rooms", "service", "standards"],
      "details": {
        "access": ["How to access the property"],
        "rooms": ["Main rooms to be serviced identified"],
        "service": ["Type of service needed"],
        "standards": ["Standards, rules, or preferences discussed"]
      }
    }
  },
  "generated_at": "2024-01-15T12:00:00Z"
}
```

#### `GET /api/v1/intake/property/{property_id}/outcome/`
Get intake outcome by property ID (finds most recent session).

**Response:** Same as session outcome endpoint.

---

## Data Schemas

### IntakeSession

```json
{
  "id": "uuid",
  "title": "string",
  "status": "active|paused|completed|abandoned",
  "status_display": "Active|Paused|Completed|Abandoned",
  "property_id": "uuid" (nullable),
  "property_address": "string" (nullable),
  "message_count": integer,
  "last_message_at": "datetime" (nullable),
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### IntakeMessage

```json
{
  "id": "uuid",
  "role": "user|assistant|system",
  "content": "string",
  "media_attachments": [
    {
      "blob_name": "string",
      "content_type": "string",
      "file_name": "string"
    }
  ],
  "in_reply_to_id": "uuid" (nullable),
  "sequence_number": integer,
  "created_at": "datetime"
}
```

### UpdateProposal

```json
{
  "id": "uuid",
  "proposal_type": "property_create|property_update|room_create|room_update|memory_create|memory_update|preference_create|preference_update|do_rule_create|do_rule_update|dont_rule_create|dont_rule_update|photo_create|photo_update",
  "proposal_type_display": "Create Property|Update Property|...",
  "status": "pending|approved|rejected|applied|superseded",
  "status_display": "Pending|Approved|Rejected|Applied|Superseded",
  "target_entity_id": "uuid" (nullable),
  "target_entity_type": "string",
  "proposed_data": {
    "field": "value"
  },
  "summary": "string",
  "created_at": "datetime"
}
```

### OnboardingProgress

```json
{
  "property_type": "string",
  "overall_completion": float (0-100),
  "required_completion": float (0-100),
  "categories": {
    "category_name": {
      "completion": float (0-100),
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

```json
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

```json
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
    "dont_rules": [
      {
        "id": "uuid",
        "rule_type": "dont",
        "content": "string",
        "room_name": "string" (nullable),
        "surface_name": "string" (nullable),
        "priority": integer
      }
    ],
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
    "completion_percentage": float (0-100),
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

### IntakeOutput

```json
{
  "session_id": "uuid",
  "property_id": "uuid" (nullable),
  "onboarding_complete": boolean,
  "home_basics": {
    "address": "string" (nullable),
    "address_line_1": "string" (nullable),
    "city": "string" (nullable),
    "state": "string" (nullable),
    "zip_code": "string" (nullable),
    "country": "string"
  },
  "property_characteristics": {
    "property_type": "string" (nullable),
    "square_feet": integer (nullable),
    "bedrooms": integer (nullable),
    "bathrooms": float (nullable),
    "year_built": integer (nullable),
    "lot_size_sqft": integer (nullable)
  },
  "service_preferences": {
    "service_type": "regular|deep|specific" (nullable),
    "frequency": "weekly|biweekly|monthly|one-time" (nullable)
  },
  "scope_signals": {
    "rooms_identified": ["string", ...],
    "priority_areas": [
      {
        "room": "string",
        "note": "string"
      }
    ]
  },
  "rules_and_preferences": {
    "do_rules": [
      {
        "id": "uuid",
        "content": "string",
        "label": "string",
        "level": "property|room|surface",
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
        "content": "string",
        "level": "property|room|surface",
        "room_name": "string" (nullable)
      }
    ],
    "sensitivities": [
      {
        "id": "uuid",
        "content": "string",
        "label": "string",
        "level": "property|room|surface",
        "room_name": "string" (nullable)
      }
    ]
  },
  "access": {
    "instructions": "string" (nullable)
  },
  "general_notes": [
    {
      "id": "uuid",
      "content": "string",
      "label": "string",
      "room_name": "string" (nullable),
      "level": "property|room|surface"
    }
  ],
  "reference_photos": [
    {
      "id": "uuid",
      "file_name": "string",
      "file_url": "string",
      "thumbnail_url": "string" (nullable)",
      "room_name": "string" (nullable),
      "surface_name": "string" (nullable),
      "location_description": "string" (nullable),
      "caption": "string" (nullable)
    }
  ]
}
```

---

## Proposal Types

### property_create
Creates a new Property record.

**proposed_data:**
```json
{
  "address": "string",
  "address_line_1": "string" (optional),
  "city": "string" (optional),
  "state": "string" (optional),
  "zip_code": "string" (optional),
  "country": "string" (optional, default: "USA"),
  "property_type": "string",
  "square_feet": integer (optional),
  "num_bedrooms": integer (optional),
  "num_bathrooms": float (optional),
  "year_built": integer (optional),
  "lot_size_sqft": integer (optional),
  "client_name": "string" (optional),
  "client_email": "string" (optional),
  "client_phone": "string" (optional),
  "access_details": "string" (optional),
  "notes": "string" (optional)
}
```

### property_update
Updates an existing Property record.

**proposed_data:** Same as property_create (only provided fields are updated)

### room_create
Creates a room note in PropertyMemory.

**proposed_data:**
```json
{
  "room_name": "string",
  "name": "string" (alternative to room_name),
  "description": "string" (optional),
  "content": "string" (alternative to description)
}
```

### memory_create
Creates a general memory/note in PropertyMemory.

**proposed_data:**
```json
{
  "memory_type": "note|do_rule|dont_rule|product_preference|personal_sensitivity",
  "level": "property|room|surface" (optional, default: "property"),
  "room_name": "string" (optional),
  "surface_name": "string" (optional),
  "label": "string" (optional),
  "content": "string",
  "priority": integer (optional, default: 0)
}
```

### preference_create
Creates a product preference in PropertyMemory.

**proposed_data:**
```json
{
  "product_name": "string",
  "use_product": boolean,
  "content": "string" (optional),
  "level": "property|room|surface" (optional),
  "room_name": "string" (optional)
}
```

### do_rule_create
Creates a "do" rule in PropertyMemory.

**proposed_data:**
```json
{
  "content": "string",
  "rule": "string" (alternative to content),
  "level": "property|room|surface" (optional),
  "room_name": "string" (optional),
  "surface_name": "string" (optional),
  "label": "string" (optional),
  "priority": integer (optional)
}
```

### dont_rule_create
Creates a "don't" rule in PropertyMemory.

**proposed_data:** Same as do_rule_create

### photo_create
Creates a reference photo (IdealConditionPhoto).

**proposed_data:**
```json
{
  "room_name": "string" (optional),
  "surface_name": "string" (optional),
  "location_description": "string" (optional),
  "caption": "string" (optional),
  "photo_type": "ideal_condition|problem_zone" (optional, default: "ideal_condition"),
  "file_url": "string" (optional, auto-generated if not provided),
  "thumbnail_url": "string" (optional)
}
```

**Note:** Photo proposals require media attachments in the source message.

---

## Important Notes

### Proposals vs Applied Memory

**CRITICAL:** Proposals are NEVER treated as truth by downstream systems. Only applied canonical memory counts.

- **Proposals** = Pending suggestions from AI (status: `pending`)
- **Applied Memory** = Data in Property/PropertyMemory models (after proposal is applied)

Downstream systems (pricing, booking, jobs) must ONLY read from:
- Property model
- PropertyMemory model
- IdealConditionPhoto model

They must NEVER read from:
- UpdateProposal records (even if status=`pending`)
- IntakeMessage records (chat transcripts)

### Session ↔ Property Linkage

**Rule:** One session = one home (MVP)

- Once a property is set on a session, it cannot be changed
- Property linkage is automatically locked when first set
- Prevents ambiguity in retrieval and intake results

### Idempotency

- **Proposal creation:** Uses `content_hash` for deduplication (prevents duplicate proposals from retries)
- **Proposal application:** Idempotent - applying an already-applied proposal returns success without duplicate changes
- **Message retry:** Safe to call multiple times, uses content_hash to prevent duplicate proposals

### Rate Limiting

- **Limit:** 100 messages per user per day
- **Endpoint:** `POST /api/v1/intake/sessions/{session_id}/send/`
- **Response:** `429 Too Many Requests` when limit exceeded

### Error Handling

- **User messages are always saved** before AI processing
- If AI processing fails, user message is still persisted
- Use retry endpoint to regenerate assistant response
- Proposal application supports partial acceptance (some succeed, some fail)

### Media Attachments

- Use existing file upload flow to get `blob_name`
- Include in message `media_attachments` array
- Photo proposals require media attachments in source message
- File URLs are auto-generated when proposals are applied

---

## Endpoint Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/intake/sessions/` | List sessions |
| POST | `/intake/sessions/` | Create session |
| GET | `/intake/sessions/{id}/` | Get session details |
| PATCH | `/intake/sessions/{id}/status/` | Update session status |
| GET | `/intake/sessions/{id}/messages/` | Get messages (paginated) |
| POST | `/intake/sessions/{id}/send/` | Send message |
| POST | `/intake/sessions/{id}/messages/{msg_id}/retry/` | Retry message |
| GET | `/intake/sessions/{id}/proposals/` | Get pending proposals |
| GET | `/intake/sessions/{id}/progress/` | Get onboarding progress |
| GET | `/intake/sessions/{id}/fact-status/` | Get fact status |
| POST | `/intake/sessions/{id}/proposals/{prop_id}/apply/` | Apply proposal |
| POST | `/intake/sessions/{id}/proposals/apply-multiple/` | Apply multiple proposals |
| POST | `/intake/sessions/{id}/proposals/{prop_id}/reject/` | Reject proposal |
| GET | `/intake/sessions/{id}/output/` | Get structured output |
| GET | `/intake/sessions/{id}/outcome/` | Get intake outcome |
| GET | `/intake/property/{id}/outcome/` | Get outcome by property |
