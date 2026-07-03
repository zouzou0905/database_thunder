CREATE TABLE IF NOT EXISTS login_history (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT REFERENCES app_users(id),
    account     TEXT NOT NULL,
    login_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    client_ip   TEXT,
    user_agent  TEXT,
    success     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_login_history_user
    ON login_history (user_id, login_at DESC);

CREATE INDEX IF NOT EXISTS idx_login_history_time
    ON login_history (login_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keyword_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON login_history TO keyword_user;
        GRANT USAGE, SELECT ON SEQUENCE login_history_id_seq TO keyword_user;
    END IF;
END $$;
