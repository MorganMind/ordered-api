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
    