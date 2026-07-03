CREATE TABLE IF NOT EXISTS keyword_holiday_tags (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL,
    marketplace TEXT NOT NULL,
    holiday_event_id BIGINT NOT NULL,
    holiday_code TEXT NOT NULL,
    holiday_name_cn TEXT NOT NULL,
    confidence TEXT NOT NULL CHECK (confidence IN ('confirmed', 'suspected')),
    matched_terms JSONB NOT NULL DEFAULT '[]'::jsonb,
    match_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    trend_year INTEGER NOT NULL,
    trend_start_month SMALLINT NOT NULL,
    trend_end_month SMALLINT NOT NULL,
    start_volume NUMERIC,
    end_volume NUMERIC,
    growth_rate NUMERIC,
    is_trend_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (keyword_id, marketplace, holiday_event_id, trend_year)
);

CREATE INDEX IF NOT EXISTS idx_holiday_tags_keyword
    ON keyword_holiday_tags (keyword_id, marketplace);

CREATE INDEX IF NOT EXISTS idx_holiday_tags_event_confidence
    ON keyword_holiday_tags (holiday_code, confidence, marketplace);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keyword_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON keyword_holiday_tags TO keyword_user;
        GRANT USAGE, SELECT ON SEQUENCE keyword_holiday_tags_id_seq TO keyword_user;
    END IF;
END $$;
