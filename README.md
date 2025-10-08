## iact-api — Backend Structure Overview

A Django-based backend organized by domains ("apps") with clear separation between HTTP views, services, models, and integrations.

### Task Triage: Frontend or Backend?

- When you request a change, first decide who should implement it:
  - **Frontend**: UI, navigation, client-side state, Flutter widgets, mobile/web behavior, API consumption.
  - **Backend**: New/changed endpoints, business logic, data models, async tasks, integrations (GCP, Supabase, LLM).
- If a request spans both, the frontend will implement the UI and call stubs/mock APIs; the backend work will be isolated and listed as “Backend needs to handle”.

### Tech Stack

- **Framework**: Django (ASGI/WSGI ready)
- **Queue/Events**: Google Cloud Tasks, Pub/Sub
- **Storage/Auth**: Google Cloud Storage, Supabase
- **LLM**: Pluggable providers (OpenAI, GTE small)
- **Container/Deploy**: Docker, Procfile, Cloud Build

### Project Layout

- **Root**
  - `manage.py`: Django management entrypoint
  - `requirements.txt`: Python dependencies
  - `Dockerfile`, `Procfile`, `cloudbuild.yaml`: Container and deployment config
  - `migrations.sql`, `pydantic_to_sql.py`: SQL migrations/pydantic tooling
- **Project config**
  - `iact_api/`: Django project module (settings, ASGI/WSGI, root `urls.py`)
- **Shared libraries**
  - `common/`: Cross-cutting utilities
    - `auth_routes.py`, `decorators.py`
    - `events/domain_event_manager.py`: Domain event dispatching
    - `google/`: GCP clients (Pub/Sub, Storage, Tasks)
    - `logger/logger_service.py`
    - `supabase/supabase_client.py`
    - `task_queue/task_queue.py`: Queue abstraction
  - `config/`: Config for Cloud Tasks and Pub/Sub
- **Domain apps**
  - `files/`: File upload/serve
    - `services/file_service.py`
    - `views/file_view.py`, `urls.py`
  - `invite/`: Invites lifecycle
    - `models/invite.py`
    - `services/invite_service.py`
    - `views/invite_view.py`, `urls.py`
  - `knowledgebase/`: Source ingestion, chunking, metadata, background tasks
    - `services/`: `chunking_service.py`, `content_extractor.py`, `metadata_service.py`, etc.
    - `tasks/`: `ingestion_task_queue.py`, `deletion_task_queue.py`
    - `event_handlers/`: Source created/deleted handlers
    - `views/knowledgebase_task_handlers.py`
    - `urls/pubsub_urls.py`
  - `llm/`: LLM abstraction and providers
    - `services/llm_service.py`, `llm_provider.py`, `llm_utils.py`
    - `providers/openai_provider.py`, `gte_small_provider.py`
  - `tag/`: Tagging and associations
    - `models/tag.py`, `taggable_type.py`, `tagging.py`
    - `services/tag_service.py`, `tag_service_admin.py`
    - `views/tag_view.py`, `urls.py`
  - `tasks/`: Generic task endpoints
    - `views/task_view.py`, `urls.py`
  - `transcription/`: Audio transcription workflows
    - `services/transcription_service.py`
    - `views/transcription_view.py`, `urls.py`
  - `user/`: User profiles, settings, analytics
    - `models/`: `user_data.py`, `user_settings.py`, `user_analytics.py`, `user_context.py`, `onboarding_payload.py`
    - `services/`: `user_service.py`, `user_settings_service.py`, `analytics_service.py`
    - `views/`: `user_view.py`, `user_settings_view.py`, `analytics_view.py`
    - `urls.py`

### Architectural Conventions

- **App structure**: Each domain app keeps `views/` (HTTP endpoints), `services/` (business logic), `models/` (pydantic/dataclasses or ORM), and `urls.py`.
- **Routing**: The project-level `iact_api/urls.py` aggregates each app’s `urls.py`.
- **Services-first**: Views are thin; core logic lives in `services/` for testability.
- **Events/Tasks**: Domain events flow via `common/events`, async work via `common/task_queue` and app `tasks/`.
- **Integrations**: External clients are wrapped in `common/google/*` and `common/supabase/*`.

### Local Development

1. Create a virtualenv and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Set required environment variables (DB, secrets, GCP, Supabase). Ensure `DJANGO_SETTINGS_MODULE=iact_api.settings`.

3. Run the server:

   ```bash
   python manage.py runserver
   ```

4. Optional: Run with Docker/Procfile.

### Notes

- The legacy `api/` module is being replaced by `iact_api/` (see git status). Ensure the new settings module is used in local and deploy environments.

## Stripe Integration

The backend includes a complete Stripe integration for membership subscriptions with event-sourced ledger tracking.

### Setup

1. **Stripe Dashboard Configuration**:
   - Create a Product: "Starter Membership" 
   - Create a recurring price (e.g., $99/month)
   - Note the Price ID (starts with `price_`)
   - Get API keys from Developers → API keys
   - Set up webhook endpoint: `https://YOUR_PROJECT_ID.supabase.co/functions/v1/stripe-webhook`
   - Select events: `invoice.payment_succeeded`, `customer.subscription.updated`
   - Copy webhook signing secret (starts with `whsec_`)

2. **Environment Variables**:
   ```bash
   STRIPE_SECRET_KEY=sk_test_YOUR_SECRET_KEY
   STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET
   ```

3. **Database Migration**:
   - Run `migrations.sql` to add Stripe columns and seed data
   - Update the `price_REPLACE_WITH_YOUR_PRICE_ID` placeholder in the plans table

4. **Deploy Edge Functions**:
   ```bash
   supabase functions deploy create-checkout-session
   supabase functions deploy stripe-webhook
   ```

### API Usage

**Create Checkout Session**:
```bash
curl -X POST https://YOUR_PROJECT_ID.supabase.co/functions/v1/create-checkout-session \
  -H "Authorization: Bearer YOUR_USER_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plan_code": "starter"}'
```

**View Membership Summary**:
```sql
SELECT * FROM public.user_membership_summary WHERE user_id = 'USER_UUID';
```

### Features

- **Event-sourced ledger**: All payments create immutable ledger entries
- **Idempotent processing**: Webhook events are deduplicated by Stripe invoice ID
- **Membership tracking**: Automatic status updates based on subscription state
- **Audit trail**: All webhook events stored in `webhook_events` table
- **RLS security**: Users can only view their own memberships and ledger entries
- **Entitlement burning**: RPC function for redeeming credits with balance checks

## Acceptance Checklist

### ✅ Initial Setup
1. **Stripe test mode configured**:
   - "Starter Membership" product created
   - Monthly recurring price created (note the price ID)
   - Webhook endpoint: `https://YOUR_PROJECT_ID.supabase.co/functions/v1/stripe-webhook`
   - Events: `invoice.payment_succeeded`, `customer.subscription.updated`
   - Webhook signing secret saved

2. **Supabase configured**:
   - All tables created (plans, memberships, entitlements, ledger_entries, webhook_events)
   - RLS policies active
   - Edge functions deployed (create-checkout-session, stripe-webhook)
   - Environment variables set (STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET)
   - Starter plan inserted with correct Stripe price ID
   - membership_credit entitlement created

### ✅ New User Flow
3. **New user can create account and log in**
4. **Home screen shows "No active membership"**
5. **Subscribe button is visible**
6. **Ledger shows "No ledger entries yet"**

### ✅ Subscription Purchase
7. **Click "Subscribe Now" navigates to Subscribe screen**
8. **Subscribe button launches Stripe Checkout**
9. **Test card: 4242 4242 4242 4242 (any future date, any CVC)**
10. **Payment completes successfully**
11. **Redirects back to app with success screen**
12. **Automatically navigates to Home after 2 seconds**

### ✅ Post-Purchase Verification
13. **Home screen shows**:
    - Plan: "Starter Membership"
    - Status: "ACTIVE"
    - Credit Balance: "$99.00" (or your test amount)
    - Started date is today
    - Expires date is one month from today
14. **Ledger shows exactly ONE credit entry**:
    - Type: credit
    - Amount: +$99.00
    - Source: stripe_subscription
    - Entitlement: membership_credit
    - Has correlation_reference_id (Stripe invoice ID)

### ✅ Webhook Idempotency Test
15. **Using Stripe CLI or dashboard, replay the same webhook event**
16. **Check database: webhook_events table has 2 rows for same event**
17. **Check ledger_entries: Still only ONE credit entry (no duplicate)**
18. **Home screen still shows same $99.00 balance**

### ✅ Entitlement Burn Test - First Redemption
19. **"Redeem test entitlement" button is visible and enabled**
20. **Click button shows loading state**
21. **Success toast appears: "Success! Redeemed 1 credit. New balance: 98"**
22. **Home screen updates to show**:
    - Credit Balance: "$98.00"
    - New debit entry in ledger (-$1.00)
    - Source: manual_redemption

### ✅ Entitlement Burn Test - Insufficient Balance
23. **Burn credits until balance reaches $0.00**
24. **Button text changes to "Insufficient balance"**
25. **Button is disabled (grayed out)**
26. **Error toast: "Insufficient balance! Current balance: 0"**
27. **No new debit entry created**
28. **Balance remains at $0.00**

### ✅ Data Consistency
29. **Pull-to-refresh updates all data from server**
30. **No local caching - closing and reopening app shows current server state**
31. **Manual refresh button in app bar works**
32. **All dates/times display correctly**
33. **Currency amounts format correctly with 2 decimal places**

### ✅ Database Verification
34. **memberships table has one row with correct user_id and stripe_subscription_id**
35. **ledger_entries table has**:
    - Immutable entries (cannot UPDATE or DELETE)
    - Correct credit/debit entries
    - All entries linked to user_id
36. **webhook_events table tracks all Stripe events with status**
37. **user_membership_summary view returns correct aggregated data**

### ✅ Edge Cases
38. **Non-authenticated user cannot access membership screens**
39. **User can only see their own membership and ledger entries**
40. **Invalid plan_code returns error**
41. **Network errors show appropriate error messages**
42. **Stripe checkout cancel returns user to app without changes**

### 🚀 Ship Criteria
- All checklist items pass
- No console errors in browser/app
- No unhandled exceptions
- Test with at least 2 different user accounts
- Verify RLS policies prevent cross-user data access

### Test Commands for Verification

```sql
-- Check for duplicate ledger entries
SELECT user_id, correlation_reference_id, COUNT(*) 
FROM ledger_entries 
WHERE source = 'stripe_subscription'
GROUP BY user_id, correlation_reference_id 
HAVING COUNT(*) > 1;

-- Verify balance calculation
SELECT 
    user_id,
    entitlement_code,
    SUM(CASE 
        WHEN type = 'credit' THEN amount 
        WHEN type = 'debit' THEN -amount 
    END) as calculated_balance
FROM ledger_entries
WHERE entitlement_code = 'membership_credit'
GROUP BY user_id, entitlement_code;

-- Check webhook processing
SELECT 
    event_type,
    status,
    COUNT(*) as count,
    MAX(created_at) as latest
FROM webhook_events
GROUP BY event_type, status
ORDER BY event_type;
```

---

## Frontend (Flutter) app — Morgan

The Flutter client is organized by feature modules under `lib/modules` with shared infrastructure in `lib/modules/core`. It uses BLoC for state management, GoRouter for navigation, and custom theming.

### Getting Started

This project is a starting point for a Flutter application.

- Lab: Write your first Flutter app: https://docs.flutter.dev/get-started/codelab
- Cookbook: Useful Flutter samples: https://docs.flutter.dev/cookbook
- Online documentation: https://docs.flutter.dev/

### Project Structure

#### Entry Points
- `lib/main.dart`: Base entry
- `lib/main_development.dart`, `lib/main_staging.dart`, `lib/main_production.dart`: Environment-specific bootstraps
- `lib/config/environment.dart`: Environment configuration
- `lib/firebase_options.dart`: Firebase configuration (generated)

#### Routing
- `lib/modules/core/routing/app_router.dart`: Route definitions
- `lib/modules/core/routing/router_observer.dart`: Navigation observer
- `lib/modules/core/routing/router_refresh_stream_group.dart` and `router-refresh-stream.dart`: Router refresh utilities

#### Dependency Injection
- `lib/modules/core/di/service_locator.dart`: Registers app-wide services and repositories

#### State Management (BLoC)
Feature BLoCs live within each module, typically with `*_bloc.dart`, `*_event.dart`, `*_state.dart`:
- `lib/modules/auth/blocs/*`
- `lib/modules/core/blocs/*`
- `lib/modules/invites/blocs/*`
- `lib/modules/onboarding/blocs/*`
- `lib/modules/settings/blocs/*`
- `lib/modules/tags/blocs/*`
- `lib/modules/user/blocs/*`

#### Feature Modules
- `lib/modules/auth/`: Auth pages (login, signup, join) and listeners
- `lib/modules/home/`: Home layout and feed widgets
- `lib/modules/invites/`: Invite model, repository, and state
- `lib/modules/onboarding/`: Onboarding flow
- `lib/modules/settings/`: Settings pages and state
- `lib/modules/tags/`: Tag models and state
- `lib/modules/transcriptions/`: Transcription services and widgets
- `lib/modules/user/`: User models, repositories, and state

#### Core Layer
- `lib/modules/core/enums/`: UI-related enums
- `lib/modules/core/platform/`: URL strategy (web vs stub)
- `lib/modules/core/services/`:
  - `api/`: API clients
  - `sse/`: Server-sent events
  - `upload/`: Upload helpers
  - `lexorank.dart`: Ordering utility (LexoRank)
- `lib/modules/core/theme/`: Theme colors, extensions, provider
- `lib/modules/core/ui/`: Reusable pages, dialogs, widgets
- `lib/modules/core/utils/`: Shared utilities (e.g., invite code helpers)

#### UI/Theme
- `lib/modules/core/theme/*`: Centralized theme configuration
- `lib/modules/core/ui/widgets/*`: Reusable components across features

#### Assets
- `assets/img/*`: Logos, icons, onboarding images
- `pubspec.yaml`: Declares assets and dependencies

#### Platform & Web
- `web/`: PWA assets (`index.html`, `manifest.json`, icons)
- `ios/Runner/*`: iOS configuration (Info.plist, storyboards, assets)
- `android/app/*`: Android configuration (manifests, Gradle, google-services.json)

#### Testing
- `test/widget_test.dart`: Sample Flutter widget test

#### Run Targets
Use the environment-specific entry points:

```bash
flutter run -t lib/main_development.dart
```

```bash
flutter run -t lib/main_staging.dart
```

```bash
flutter run -t lib/main_production.dart
```

### Workflow Agreement

- For any new request:
  1) Determine if it’s frontend, backend, or both (see Task Triage above).
  2) Frontend implements UI/state/navigation and calls to existing or stubbed APIs.
  3) If backend changes are needed, list them explicitly under “Backend needs to handle”.



