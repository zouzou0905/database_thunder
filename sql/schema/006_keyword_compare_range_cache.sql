-- On-demand exact range cache for the keyword horizontal compare module.
-- Each row stores metrics recomputed for one marketplace + month range.

CREATE UNLOGGED TABLE IF NOT EXISTS keyword_compare_range_cache (
    start_month DATE NOT NULL,
    end_month DATE NOT NULL,
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
    PRIMARY KEY (start_month, end_month, marketplace, keyword_id)
);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_market_range
    ON keyword_compare_range_cache (marketplace, start_month, end_month);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_volume
    ON keyword_compare_range_cache (marketplace, start_month, end_month, end_search_volume DESC);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_growth
    ON keyword_compare_range_cache (marketplace, start_month, end_month, search_volume_growth_rate DESC);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_trend
    ON keyword_compare_range_cache (marketplace, start_month, end_month, trend_type);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_category
    ON keyword_compare_range_cache (marketplace, start_month, end_month, category);
