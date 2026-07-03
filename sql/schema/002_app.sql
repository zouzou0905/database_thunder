CREATE TABLE IF NOT EXISTS app_users (
    id BIGSERIAL PRIMARY KEY,
    account TEXT NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'operator',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT app_users_account_unique UNIQUE (account),
    CONSTRAINT app_users_role_check
        CHECK (role IN ('admin', 'manager', 'operator', 'viewer'))
);

CREATE TABLE IF NOT EXISTS keyword_selection_states (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    analysis_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    owner_user_id BIGINT NOT NULL REFERENCES app_users(id),
    status TEXT NOT NULL DEFAULT 'new',
    priority TEXT,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT keyword_selection_states_status_check
        CHECK (status IN ('new', 'watching', 'researching', 'rejected', 'approved', 'launched')),
    CONSTRAINT keyword_selection_states_priority_check
        CHECK (priority IS NULL OR priority IN ('low', 'medium', 'high')),
    CONSTRAINT keyword_selection_states_unique_user_keyword
        UNIQUE (keyword_id, analysis_month, marketplace, owner_user_id)
);

CREATE INDEX IF NOT EXISTS idx_keyword_selection_states_user
    ON keyword_selection_states (owner_user_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_keyword_selection_states_favorite
    ON keyword_selection_states (owner_user_id, is_favorite, analysis_month, marketplace);

CREATE INDEX IF NOT EXISTS idx_keyword_selection_states_keyword
    ON keyword_selection_states (keyword_id, analysis_month, marketplace);

CREATE TABLE IF NOT EXISTS keyword_selection_notes (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    analysis_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    user_id BIGINT NOT NULL REFERENCES app_users(id),
    note TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_keyword_selection_notes_keyword
    ON keyword_selection_notes (keyword_id, analysis_month, marketplace, created_at DESC);

CREATE TABLE IF NOT EXISTS shared_clipboard_items (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    content_size INTEGER NOT NULL,
    created_by BIGINT NOT NULL REFERENCES app_users(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_shared_clipboard_items_recent
    ON shared_clipboard_items (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_shared_clipboard_items_user
    ON shared_clipboard_items (created_by, created_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keyword_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON shared_clipboard_items TO keyword_user;
        GRANT USAGE, SELECT ON SEQUENCE shared_clipboard_items_id_seq TO keyword_user;
    END IF;
END $$;
