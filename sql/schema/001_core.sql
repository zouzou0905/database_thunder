CREATE TABLE IF NOT EXISTS import_batches (
    id BIGSERIAL PRIMARY KEY,
    batch_name TEXT NOT NULL,
    data_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'running',
    total_files INTEGER DEFAULT 0,
    total_rows INTEGER DEFAULT 0,
    valid_rows INTEGER DEFAULT 0,
    duplicate_rows INTEGER DEFAULT 0,
    error_rows INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS source_files (
    id BIGSERIAL PRIMARY KEY,
    batch_id BIGINT REFERENCES import_batches(id),
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    data_month DATE NOT NULL,
    rank_start INTEGER,
    rank_end INTEGER,
    row_count INTEGER DEFAULT 0,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'imported',
    UNIQUE (file_hash)
);

CREATE TABLE IF NOT EXISTS raw_aba_rows (
    id BIGSERIAL PRIMARY KEY,
    source_file_id BIGINT NOT NULL REFERENCES source_files(id),
    row_number INTEGER NOT NULL,
    data_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    raw_keyword TEXT,
    raw_rank TEXT,
    raw_search_volume TEXT,
    raw_click_share TEXT,
    raw_conversion_share TEXT,
    raw_top_asins TEXT,
    raw_payload JSONB,
    imported_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (source_file_id, row_number)
);

CREATE TABLE IF NOT EXISTS keywords (
    id BIGSERIAL PRIMARY KEY,
    keyword_raw TEXT NOT NULL,
    keyword_normalized TEXT NOT NULL,
    keyword_hash TEXT NOT NULL,
    language TEXT,
    word_count INTEGER,
    char_count INTEGER,
    is_brand_word BOOLEAN DEFAULT FALSE,
    is_competitor_word BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (keyword_hash)
);

CREATE TABLE IF NOT EXISTS keyword_monthly_metrics (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    data_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    serial_no INTEGER,
    keyword_translation TEXT,
    category TEXT,
    page_no INTEGER,
    search_rank INTEGER,
    search_volume NUMERIC,
    prev_month_rank INTEGER,
    four_months_ago_rank INTEGER,
    twelve_months_ago_rank INTEGER,
    rank_change_prev_month INTEGER,
    rank_change_four_months INTEGER,
    rank_change_twelve_months INTEGER,
    rank_change_rate_prev_month NUMERIC,
    rank_change_rate_four_months NUMERIC,
    rank_change_rate_twelve_months NUMERIC,
    impressions NUMERIC,
    clicks NUMERIC,
    ppc_bid_low NUMERIC,
    ppc_bid_mid NUMERIC,
    ppc_bid_high NUMERIC,
    spr INTEGER,
    click_share NUMERIC,
    conversion_share NUMERIC,
    top1_asin TEXT,
    top2_asin TEXT,
    top3_asin TEXT,
    source_file_id BIGINT REFERENCES source_files(id),
    raw_row_id BIGINT REFERENCES raw_aba_rows(id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (keyword_id, data_month, marketplace)
);

CREATE TABLE IF NOT EXISTS asins (
    id BIGSERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    first_seen_month DATE,
    is_our_asin BOOLEAN DEFAULT FALSE,
    brand TEXT,
    product_line TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (asin, marketplace)
);

CREATE TABLE IF NOT EXISTS keyword_asin_monthly (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    asin_id BIGINT NOT NULL REFERENCES asins(id),
    data_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    position_type TEXT NOT NULL,
    position_rank INTEGER NOT NULL,
    share_value NUMERIC,
    source_file_id BIGINT REFERENCES source_files(id),
    UNIQUE (keyword_id, asin_id, data_month, marketplace, position_type, position_rank)
);

CREATE TABLE IF NOT EXISTS keyword_monthly_trends (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    analysis_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    prev_month_rank INTEGER,
    current_rank INTEGER,
    rank_change INTEGER,
    rank_change_rate NUMERIC,
    prev_month_search_volume NUMERIC,
    current_search_volume NUMERIC,
    search_volume_change NUMERIC,
    search_volume_growth_rate NUMERIC,
    avg_rank_3m NUMERIC,
    avg_search_volume_3m NUMERIC,
    avg_rank_6m NUMERIC,
    avg_search_volume_6m NUMERIC,
    yoy_rank INTEGER,
    yoy_search_volume NUMERIC,
    yoy_growth_rate NUMERIC,
    trend_label TEXT,
    calculated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (keyword_id, analysis_month, marketplace)
);

CREATE TABLE IF NOT EXISTS keyword_ops_monthly (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    keyword TEXT NOT NULL,
    analysis_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    category TEXT,
    search_rank INTEGER,
    search_volume NUMERIC,
    click_share NUMERIC,
    conversion_share NUMERIC,
    rank_change_mom INTEGER,
    volume_change_mom NUMERIC,
    volume_growth_rate_mom NUMERIC,
    avg_rank_3m NUMERIC,
    avg_volume_3m NUMERIC,
    avg_rank_6m NUMERIC,
    avg_volume_6m NUMERIC,
    yoy_growth_rate NUMERIC,
    trend_label TEXT,
    keyword_level TEXT,
    lifecycle_stage TEXT,
    opportunity_score NUMERIC,
    competition_score NUMERIC,
    conversion_score NUMERIC,
    recommended_action TEXT,
    operation_tag TEXT,
    top1_asin TEXT,
    top2_asin TEXT,
    top3_asin TEXT,
    owner TEXT,
    process_status TEXT DEFAULT 'unprocessed',
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (keyword_id, analysis_month, marketplace)
);

CREATE TABLE IF NOT EXISTS keyword_watchlist (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    marketplace TEXT NOT NULL DEFAULT 'US',
    owner TEXT,
    watch_reason TEXT,
    priority TEXT,
    status TEXT NOT NULL DEFAULT 'watching',
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE (keyword_id, marketplace, owner)
);

CREATE TABLE IF NOT EXISTS keyword_action_log (
    id BIGSERIAL PRIMARY KEY,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    marketplace TEXT NOT NULL DEFAULT 'US',
    action_month DATE NOT NULL,
    operator TEXT NOT NULL,
    action_type TEXT NOT NULL,
    action_detail TEXT,
    before_status TEXT,
    after_status TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS asin_keyword_ops (
    id BIGSERIAL PRIMARY KEY,
    asin TEXT NOT NULL,
    keyword_id BIGINT NOT NULL REFERENCES keywords(id),
    keyword TEXT NOT NULL,
    analysis_month DATE NOT NULL,
    marketplace TEXT NOT NULL DEFAULT 'US',
    asin_position INTEGER,
    click_share NUMERIC,
    conversion_share NUMERIC,
    keyword_search_rank INTEGER,
    keyword_search_volume NUMERIC,
    is_our_asin BOOLEAN DEFAULT FALSE,
    product_line TEXT,
    brand TEXT,
    owner TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
