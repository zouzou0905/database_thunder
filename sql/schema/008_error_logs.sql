CREATE TABLE IF NOT EXISTS error_logs (
    id              BIGSERIAL PRIMARY KEY,
    level           TEXT NOT NULL DEFAULT 'ERROR',
    source          TEXT NOT NULL DEFAULT 'backend',
    endpoint        TEXT,
    method          TEXT,
    status_code     INTEGER,
    message         TEXT NOT NULL,
    traceback       TEXT,
    request_body    TEXT,
    user_agent      TEXT,
    client_ip       TEXT,
    user_account    TEXT,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_error_logs_created
    ON error_logs (resolved, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_error_logs_level
    ON error_logs (level, created_at DESC);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keyword_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON error_logs TO keyword_user;
        GRANT USAGE, SELECT ON SEQUENCE error_logs_id_seq TO keyword_user;
    END IF;
END $$;
