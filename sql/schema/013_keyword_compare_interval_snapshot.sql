-- Pre-computed compare snapshots for common date intervals.
-- Unlike keyword_compare_range_cache (UNLOGGED), this table is LOGGED and
-- survives PostgreSQL restarts. Populated once and refreshed explicitly.
-- Examples: halloween_2025 (Aug-Oct), christmas_2025 (Oct-Dec),
-- recent_3m, recent_6m.

CREATE TABLE IF NOT EXISTS keyword_compare_interval_snapshot (
    interval_code TEXT NOT NULL,
    interval_name TEXT NOT NULL,
    start_month DATE NOT NULL,
    end_month DATE NOT NULL,
    keyword_id BIGINT NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'UK',
    keyword TEXT NOT NULL,
    keyword_translation TEXT,
    category TEXT,
    first_month DATE NOT NULL,
    last_month DATE NOT NULL,
    month_count INT NOT NULL,
    total_months INT NOT NULL,
    start_search_volume NUMERIC,
    end_search_volume NUMERIC,
    search_volume_change NUMERIC,
    search_volume_growth_rate NUMERIC,
    start_rank INTEGER,
    end_rank INTEGER,
    rank_change INTEGER,
    trend_type TEXT NOT NULL,
    trend_type_cn TEXT,
    ppc_bid_mid NUMERIC,
    spr INTEGER,
    prev_month_rank INTEGER,
    four_months_ago_rank INTEGER,
    twelve_months_ago_rank INTEGER,
    monthly JSONB NOT NULL DEFAULT '[]'::jsonb,
    avg_search_volume NUMERIC,
    stddev_search_volume NUMERIC,
    cv_search_volume NUMERIC,
    volume_slope NUMERIC,
    volume_r2 NUMERIC,
    gap_count INTEGER,
    prev_month_search_volume NUMERIC,
    yoy_search_volume NUMERIC,
    mom_change NUMERIC,
    mom_rate NUMERIC,
    yoy_change NUMERIC,
    yoy_rate NUMERIC,
    generated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (interval_code, marketplace, start_month, end_month, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_compare_interval_lookup
    ON keyword_compare_interval_snapshot (interval_code, marketplace, start_month, end_month);

CREATE INDEX IF NOT EXISTS idx_compare_interval_volume_order
    ON keyword_compare_interval_snapshot (
        interval_code,
        marketplace,
        start_month,
        end_month,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_interval_growth_order
    ON keyword_compare_interval_snapshot (
        interval_code,
        marketplace,
        start_month,
        end_month,
        search_volume_growth_rate DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_interval_trend
    ON keyword_compare_interval_snapshot (interval_code, marketplace, trend_type);

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'keyword_user') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON keyword_compare_interval_snapshot TO keyword_user;
    END IF;
END $$;
