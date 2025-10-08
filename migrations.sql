-- Auto-generated PostgreSQL migrations from Pydantic models
-- Generated at: 2025-07-14T23:08:59.559755

BEGIN;

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- Updated at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TABLE IF NOT EXISTS user_analytics (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    total_tokens INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    messages_sent INTEGER,
    uploads_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
    );

    CREATE TRIGGER update_user_analytics_updated_at BEFORE UPDATE
    ON user_analytics FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS user_data (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    onboarding_completed BOOLEAN,
    analytics_id TEXT,
    avatar_url TEXT,
    full_name TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER update_user_data_updated_at BEFORE UPDATE
    ON user_data FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS user_settings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    avatar_type TEXT,
    theme TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER update_user_settings_updated_at BEFORE UPDATE
    ON user_settings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS tag (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    label TEXT NOT NULL,
    description TEXT NOT NULL,
    user_id UUID,
    auto_generated BOOLEAN,
    last_used TIMESTAMP WITH TIME ZONE,
    is_system BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER update_tag_updated_at BEFORE UPDATE
    ON tag FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TABLE IF NOT EXISTS tagging (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_id UUID,
    taggable_type TEXT NOT NULL,
    taggable_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TRIGGER update_tagging_updated_at BEFORE UPDATE
    ON tagging FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- Foreign Key Constraints

ALTER TABLE user_analytics 
ADD CONSTRAINT fk_user_analytics_user_id 
FOREIGN KEY (user_id) 
REFERENCES user_data(id) 
ON DELETE CASCADE;

ALTER TABLE user_settings 
ADD CONSTRAINT fk_user_settings_user_id 
FOREIGN KEY (user_id) 
REFERENCES user_data(id) 
ON DELETE CASCADE;

ALTER TABLE tag 
ADD CONSTRAINT fk_tag_user_id 
FOREIGN KEY (user_id) 
REFERENCES user_data(id) 
ON DELETE CASCADE;

ALTER TABLE tagging 
ADD CONSTRAINT fk_tagging_tag_id 
FOREIGN KEY (tag_id) 
REFERENCES tag(id) 
ON DELETE CASCADE;

COMMIT;
    
-- =====================================================
-- Phase 2: Med Spa Memberships and Entitlements Ledger
-- =====================================================

BEGIN;

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- TABLES
-- =====================================================

-- Plans table: Defines available membership plans
CREATE TABLE IF NOT EXISTS public.plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Memberships table: Tracks user membership subscriptions
CREATE TABLE IF NOT EXISTS public.memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_id UUID NOT NULL REFERENCES public.plans(id),
    status VARCHAR(50) NOT NULL CHECK (status IN ('active', 'canceled', 'expired', 'suspended')),
    started_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create index for user lookups
CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON public.memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_status ON public.memberships(status);

-- Entitlements table: Defines what benefits/services are available
CREATE TABLE IF NOT EXISTS public.entitlements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    unit_type VARCHAR(50) NOT NULL CHECK (unit_type IN ('currency', 'quantity', 'boolean')),
    is_active BOOLEAN DEFAULT true,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Ledger entries table: Immutable event-sourced ledger
CREATE TABLE IF NOT EXISTS public.ledger_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    source VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL CHECK (type IN ('credit', 'debit')),
    amount DECIMAL(10, 2),
    quantity INTEGER,
    unit_type VARCHAR(50) NOT NULL CHECK (unit_type IN ('currency', 'quantity')),
    entitlement_code VARCHAR(100) REFERENCES public.entitlements(code),
    correlation_reference_id VARCHAR(255),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    CONSTRAINT chk_unit_values CHECK (
        (unit_type = 'currency' AND amount IS NOT NULL AND quantity IS NULL) OR
        (unit_type = 'quantity' AND quantity IS NOT NULL AND amount IS NULL)
    )
);

-- Create indexes for ledger queries
CREATE INDEX IF NOT EXISTS idx_ledger_entries_user_id ON public.ledger_entries(user_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_created_at ON public.ledger_entries(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_correlation_ref ON public.ledger_entries(correlation_reference_id);
CREATE INDEX IF NOT EXISTS idx_ledger_entries_entitlement_code ON public.ledger_entries(entitlement_code);

-- Webhook events table: Track webhook processing
CREATE TABLE IF NOT EXISTS public.webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source VARCHAR(100) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    processed_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'failed', 'ignored')),
    error_message TEXT,
    correlation_id VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Create index for webhook processing
CREATE INDEX IF NOT EXISTS idx_webhook_events_status ON public.webhook_events(status);
CREATE INDEX IF NOT EXISTS idx_webhook_events_correlation_id ON public.webhook_events(correlation_id);

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.webhook_events ENABLE ROW LEVEL SECURITY;

-- Plans policies (read-only for all authenticated users)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'plans' AND policyname = 'Users can view active plans'
    ) THEN
        CREATE POLICY "Users can view active plans" ON public.plans
            FOR SELECT
            USING (is_active = true);
    END IF;
END $$;

-- Memberships policies (users can read their own)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'memberships' AND policyname = 'Users can view their own memberships'
    ) THEN
        CREATE POLICY "Users can view their own memberships" ON public.memberships
            FOR SELECT
            USING (auth.uid() = user_id);
    END IF;
END $$;

-- Entitlements policies (read-only for all authenticated users)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'entitlements' AND policyname = 'Users can view active entitlements'
    ) THEN
        CREATE POLICY "Users can view active entitlements" ON public.entitlements
            FOR SELECT
            USING (is_active = true);
    END IF;
END $$;

-- Ledger entries policies (users can read their own)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'ledger_entries' AND policyname = 'Users can view their own ledger entries'
    ) THEN
        CREATE POLICY "Users can view their own ledger entries" ON public.ledger_entries
            FOR SELECT
            USING (auth.uid() = user_id);
    END IF;
END $$;

-- Webhook events policies (no user access): none; use service role only

-- =====================================================
-- VIEW
-- =====================================================

-- Create view for user membership status and recent ledger entries
CREATE OR REPLACE VIEW public.user_membership_summary AS
WITH latest_membership AS (
    SELECT DISTINCT ON (user_id)
        user_id,
        id AS membership_id,
        plan_id,
        status AS membership_status,
        started_at,
        expires_at,
        canceled_at
    FROM public.memberships
    ORDER BY user_id, created_at DESC
),
recent_ledger AS (
    SELECT 
        user_id,
        ARRAY_AGG(
            json_build_object(
                'id', id,
                'source', source,
                'type', type,
                'amount', amount,
                'quantity', quantity,
                'unit_type', unit_type,
                'entitlement_code', entitlement_code,
                'correlation_reference_id', correlation_reference_id,
                'created_at', created_at
            ) ORDER BY created_at DESC
        ) FILTER (WHERE rn <= 10) AS recent_entries
    FROM (
        SELECT 
            *,
            ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
        FROM public.ledger_entries
    ) ranked_entries
    GROUP BY user_id
)
SELECT 
    lm.user_id,
    lm.membership_id,
    lm.plan_id,
    p.code AS plan_code,
    p.name AS plan_name,
    lm.membership_status,
    lm.started_at,
    lm.expires_at,
    lm.canceled_at,
    COALESCE(rl.recent_entries, ARRAY[]::json[]) AS last_ten_ledger_entries,
    NOW() AS query_timestamp
FROM latest_membership lm
LEFT JOIN public.plans p ON lm.plan_id = p.id
LEFT JOIN recent_ledger rl ON lm.user_id = rl.user_id;

-- Grant access to the view for authenticated users
GRANT SELECT ON public.user_membership_summary TO authenticated;

-- =====================================================
-- TRIGGERS FOR IMMUTABILITY
-- =====================================================

-- Function to prevent updates and deletes on ledger_entries
CREATE OR REPLACE FUNCTION public.prevent_ledger_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Ledger entries are immutable and cannot be modified or deleted';
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Trigger to enforce immutability on ledger_entries
DROP TRIGGER IF EXISTS enforce_ledger_immutability ON public.ledger_entries;
CREATE TRIGGER enforce_ledger_immutability
    BEFORE UPDATE OR DELETE ON public.ledger_entries
    FOR EACH ROW
    EXECUTE FUNCTION public.prevent_ledger_modification();

-- =====================================================
-- UPDATED_AT TRIGGERS
-- =====================================================

-- Function to update updated_at timestamp (idempotent; a version exists above)
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add triggers for tables with updated_at
DROP TRIGGER IF EXISTS update_plans_updated_at ON public.plans;
CREATE TRIGGER update_plans_updated_at BEFORE UPDATE ON public.plans
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_memberships_updated_at ON public.memberships;
CREATE TRIGGER update_memberships_updated_at BEFORE UPDATE ON public.memberships
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

DROP TRIGGER IF EXISTS update_entitlements_updated_at ON public.entitlements;
CREATE TRIGGER update_entitlements_updated_at BEFORE UPDATE ON public.entitlements
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- =====================================================
-- Stripe Integration Schema Updates
-- =====================================================

-- Add Stripe-specific columns to existing tables
ALTER TABLE public.memberships 
ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255) UNIQUE,
ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_memberships_stripe_sub ON public.memberships(stripe_subscription_id);

-- Add Stripe price mapping to plans
ALTER TABLE public.plans
ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(255);

-- Insert test Starter plan with entitlement
INSERT INTO public.plans (code, name, description, stripe_price_id, is_active)
VALUES ('starter', 'Starter Membership', 'Monthly membership with exclusive perks', 'price_REPLACE_WITH_YOUR_PRICE_ID', true)
ON CONFLICT (code) DO UPDATE 
SET stripe_price_id = EXCLUDED.stripe_price_id;

-- Insert a membership credit entitlement
INSERT INTO public.entitlements (code, name, description, unit_type, is_active)
VALUES ('membership_credit', 'Membership Credit', 'Monthly membership credit allowance', 'currency', true)
ON CONFLICT (code) DO NOTHING;

-- =====================================================
-- RPC Function: Burn Entitlement with Balance Check
-- =====================================================

CREATE OR REPLACE FUNCTION public.burn_entitlement(
    p_entitlement_code VARCHAR(100),
    p_quantity INTEGER DEFAULT 1,
    p_reason VARCHAR(255) DEFAULT 'redemption'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_user_id UUID;
    v_current_balance NUMERIC;
    v_unit_type VARCHAR(50);
    v_debit_id UUID;
BEGIN
    -- Get the current user
    v_user_id := auth.uid();
    
    IF v_user_id IS NULL THEN
        RETURN jsonb_build_object(
            'success', false,
            'error', 'User not authenticated'
        );
    END IF;

    -- Start transaction
    BEGIN
        -- Get the entitlement unit type
        SELECT unit_type INTO v_unit_type
        FROM public.entitlements
        WHERE code = p_entitlement_code
        AND is_active = true;

        IF v_unit_type IS NULL THEN
            RETURN jsonb_build_object(
                'success', false,
                'error', 'Invalid or inactive entitlement code'
            );
        END IF;

        -- Calculate current balance for this entitlement
        -- Sum all credits minus debits for this specific entitlement
        SELECT 
            COALESCE(
                SUM(CASE 
                    WHEN type = 'credit' THEN 
                        CASE 
                            WHEN unit_type = 'currency' THEN amount
                            WHEN unit_type = 'quantity' THEN quantity::NUMERIC
                        END
                    WHEN type = 'debit' THEN 
                        CASE 
                            WHEN unit_type = 'currency' THEN -amount
                            WHEN unit_type = 'quantity' THEN -quantity::NUMERIC
                        END
                END), 
                0
            )
        INTO v_current_balance
        FROM public.ledger_entries
        WHERE user_id = v_user_id
        AND entitlement_code = p_entitlement_code;

        -- Check if sufficient balance
        IF v_unit_type = 'quantity' THEN
            IF v_current_balance < p_quantity THEN
                RETURN jsonb_build_object(
                    'success', false,
                    'error', 'Insufficient balance',
                    'current_balance', v_current_balance,
                    'requested', p_quantity
                );
            END IF;

            -- Create debit entry for quantity
            INSERT INTO public.ledger_entries (
                user_id,
                source,
                type,
                quantity,
                unit_type,
                entitlement_code,
                correlation_reference_id,
                metadata
            ) VALUES (
                v_user_id,
                'manual_redemption',
                'debit',
                p_quantity,
                'quantity',
                p_entitlement_code,
                gen_random_uuid()::TEXT,
                jsonb_build_object(
                    'reason', p_reason,
                    'redeemed_at', NOW()
                )
            )
            RETURNING id INTO v_debit_id;

        ELSIF v_unit_type = 'currency' THEN
            -- For currency, assume p_quantity represents cents/dollars
            IF v_current_balance < p_quantity THEN
                RETURN jsonb_build_object(
                    'success', false,
                    'error', 'Insufficient balance',
                    'current_balance', v_current_balance,
                    'requested', p_quantity
                );
            END IF;

            -- Create debit entry for currency
            INSERT INTO public.ledger_entries (
                user_id,
                source,
                type,
                amount,
                unit_type,
                entitlement_code,
                correlation_reference_id,
                metadata
            ) VALUES (
                v_user_id,
                'manual_redemption',
                'debit',
                p_quantity,
                'currency',
                p_entitlement_code,
                gen_random_uuid()::TEXT,
                jsonb_build_object(
                    'reason', p_reason,
                    'redeemed_at', NOW()
                )
            )
            RETURNING id INTO v_debit_id;
        END IF;

        -- Return success with new balance
        RETURN jsonb_build_object(
            'success', true,
            'debit_id', v_debit_id,
            'previous_balance', v_current_balance,
            'amount_debited', p_quantity,
            'new_balance', v_current_balance - p_quantity
        );

    EXCEPTION WHEN OTHERS THEN
        -- Rollback will happen automatically
        RETURN jsonb_build_object(
            'success', false,
            'error', SQLERRM
        );
    END;
END;
$$;

-- Grant execute permission to authenticated users
GRANT EXECUTE ON FUNCTION public.burn_entitlement TO authenticated;

-- =====================================================
-- Add Balance to View (Update existing view)
-- =====================================================

DROP VIEW IF EXISTS public.user_membership_summary;

CREATE OR REPLACE VIEW public.user_membership_summary AS
WITH latest_membership AS (
    SELECT DISTINCT ON (user_id)
        user_id,
        id AS membership_id,
        plan_id,
        status AS membership_status,
        started_at,
        expires_at,
        canceled_at
    FROM public.memberships
    ORDER BY user_id, created_at DESC
),
recent_ledger AS (
    SELECT 
        user_id,
        ARRAY_AGG(
            json_build_object(
                'id', id,
                'source', source,
                'type', type,
                'amount', amount,
                'quantity', quantity,
                'unit_type', unit_type,
                'entitlement_code', entitlement_code,
                'correlation_reference_id', correlation_reference_id,
                'created_at', created_at
            ) ORDER BY created_at DESC
        ) FILTER (WHERE rn <= 10) AS recent_entries
    FROM (
        SELECT 
            *,
            ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn
        FROM public.ledger_entries
    ) ranked_entries
    GROUP BY user_id
),
entitlement_balances AS (
    SELECT 
        user_id,
        entitlement_code,
        SUM(CASE 
            WHEN type = 'credit' THEN 
                CASE 
                    WHEN unit_type = 'currency' THEN amount
                    WHEN unit_type = 'quantity' THEN quantity::NUMERIC
                END
            WHEN type = 'debit' THEN 
                CASE 
                    WHEN unit_type = 'currency' THEN -amount
                    WHEN unit_type = 'quantity' THEN -quantity::NUMERIC
                END
        END) AS balance
    FROM public.ledger_entries
    WHERE entitlement_code = 'membership_credit'
    GROUP BY user_id, entitlement_code
)
SELECT 
    lm.user_id,
    lm.membership_id,
    lm.plan_id,
    p.code AS plan_code,
    p.name AS plan_name,
    lm.membership_status,
    lm.started_at,
    lm.expires_at,
    lm.canceled_at,
    COALESCE(rl.recent_entries, ARRAY[]::json[]) AS last_ten_ledger_entries,
    COALESCE(eb.balance, 0) AS membership_credit_balance,
    NOW() AS query_timestamp
FROM latest_membership lm
LEFT JOIN public.plans p ON lm.plan_id = p.id
LEFT JOIN recent_ledger rl ON lm.user_id = rl.user_id
LEFT JOIN entitlement_balances eb ON lm.user_id = eb.user_id;

-- Grant access to the view for authenticated users
GRANT SELECT ON public.user_membership_summary TO authenticated;

COMMIT;
