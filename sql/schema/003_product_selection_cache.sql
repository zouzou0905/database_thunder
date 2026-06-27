CREATE TABLE IF NOT EXISTS keyword_selection_candidates_monthly (
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    keyword TEXT NOT NULL,
    keyword_translation TEXT,
    analysis_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    category TEXT,
    search_rank INTEGER,
    search_volume NUMERIC,
    ppc_bid_low NUMERIC,
    ppc_bid_mid NUMERIC,
    ppc_bid_high NUMERIC,
    spr INTEGER,
    click_share NUMERIC,
    conversion_share NUMERIC,
    rank_change_mom INTEGER,
    volume_change_mom NUMERIC,
    volume_growth_rate_mom NUMERIC,
    trend_label TEXT,
    trend_label_cn TEXT,
    opportunity_score NUMERIC,
    competition_score NUMERIC,
    conversion_score NUMERIC,
    prev_1m_rank INTEGER,
    prev_2m_rank INTEGER,
    prev_3m_rank INTEGER,
    prev_1m_search_volume NUMERIC,
    prev_2m_search_volume NUMERIC,
    prev_3m_search_volume NUMERIC,
    rank_change_1m INTEGER,
    rank_change_3m INTEGER,
    search_volume_growth_1m_pct NUMERIC,
    search_volume_growth_3m_pct NUMERIC,
    months_seen_to_date BIGINT,
    months_seen_total BIGINT,
    first_seen_month DATE,
    last_seen_month DATE,
    word_count INTEGER,
    is_media_category BOOLEAN NOT NULL DEFAULT FALSE,
    is_unknown_category BOOLEAN NOT NULL DEFAULT FALSE,
    is_manual_excluded BOOLEAN NOT NULL DEFAULT FALSE,
    intent_score INTEGER,
    demand_score INTEGER,
    growth_score INTEGER,
    stability_score INTEGER,
    competition_access_score INTEGER,
    conversion_signal_score INTEGER,
    selection_segment_cn TEXT,
    demand_band_cn TEXT,
    exclusion_reason_cn TEXT,
    is_product_selection_candidate BOOLEAN NOT NULL DEFAULT FALSE,
    product_selection_score NUMERIC,
    candidate_level_cn TEXT,
    refreshed_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (keyword_id, analysis_month, marketplace)
);

CREATE INDEX IF NOT EXISTS idx_selection_cache_month_market
    ON keyword_selection_candidates_monthly (analysis_month, marketplace);

CREATE INDEX IF NOT EXISTS idx_selection_cache_candidate_score
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        is_product_selection_candidate,
        product_selection_score DESC,
        search_volume DESC
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_volume
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        search_volume DESC
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_category
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        category
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_trend
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        trend_label
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_keyword_lower
    ON keyword_selection_candidates_monthly (LOWER(keyword));
