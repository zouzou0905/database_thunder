-- Pre-computed snapshot for the keyword horizontal compare module.
-- The live query against keyword_monthly_metrics across multiple months is too
-- heavy for real-time API responses (>2M rows for UK across 7 months).
-- This table is refreshed by scripts/calculate_trends.py and queried by the API.

CREATE TABLE IF NOT EXISTS keyword_compare_snapshot (
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
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
    -- Statistical columns for 5-category reclassification
    avg_search_volume NUMERIC,
    stddev_search_volume NUMERIC,
    cv_search_volume NUMERIC,
    volume_slope NUMERIC,
    volume_r2 NUMERIC,
    gap_count INTEGER,
    refreshed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (keyword_id, marketplace)
);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_market
    ON keyword_compare_snapshot (marketplace);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_trend
    ON keyword_compare_snapshot (marketplace, trend_type);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_volume
    ON keyword_compare_snapshot (marketplace, end_search_volume DESC);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_growth
    ON keyword_compare_snapshot (marketplace, search_volume_growth_rate DESC);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_category
    ON keyword_compare_snapshot (marketplace, category);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_keyword_trgm
    ON keyword_compare_snapshot USING GIN (keyword gin_trgm_ops);
