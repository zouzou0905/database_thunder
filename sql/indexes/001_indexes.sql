CREATE INDEX IF NOT EXISTS idx_source_files_month
ON source_files (data_month, marketplace);

CREATE INDEX IF NOT EXISTS idx_raw_rows_source
ON raw_aba_rows (source_file_id);

CREATE INDEX IF NOT EXISTS idx_metrics_month
ON keyword_monthly_metrics (data_month);

CREATE INDEX IF NOT EXISTS idx_metrics_keyword_month
ON keyword_monthly_metrics (keyword_id, data_month);

CREATE INDEX IF NOT EXISTS idx_metrics_market_month_rank
ON keyword_monthly_metrics (marketplace, data_month, search_rank);

CREATE INDEX IF NOT EXISTS idx_metrics_market_month_volume
ON keyword_monthly_metrics (marketplace, data_month, search_volume DESC);

CREATE INDEX IF NOT EXISTS idx_metrics_market_month_category
ON keyword_monthly_metrics (marketplace, data_month, category);

CREATE INDEX IF NOT EXISTS idx_metrics_market_month_ppc
ON keyword_monthly_metrics (marketplace, data_month, ppc_bid_mid);

CREATE INDEX IF NOT EXISTS idx_metrics_market_month_spr
ON keyword_monthly_metrics (marketplace, data_month, spr);

CREATE INDEX IF NOT EXISTS idx_metrics_keyword_market_month
ON keyword_monthly_metrics (keyword_id, marketplace, data_month);

CREATE INDEX IF NOT EXISTS idx_metrics_category_month
ON keyword_monthly_metrics (category, data_month);

CREATE INDEX IF NOT EXISTS idx_keywords_normalized
ON keywords (keyword_normalized);

CREATE INDEX IF NOT EXISTS idx_trends_month_label
ON keyword_monthly_trends (analysis_month, trend_label);

CREATE INDEX IF NOT EXISTS idx_ops_month_score
ON keyword_ops_monthly (analysis_month, opportunity_score DESC);

CREATE INDEX IF NOT EXISTS idx_ops_keyword_market_month
ON keyword_ops_monthly (keyword_id, marketplace, analysis_month);

CREATE INDEX IF NOT EXISTS idx_ops_market_month_trend
ON keyword_ops_monthly (marketplace, analysis_month, trend_label);

CREATE INDEX IF NOT EXISTS idx_ops_month_trend
ON keyword_ops_monthly (analysis_month, trend_label);

CREATE INDEX IF NOT EXISTS idx_ops_owner_status
ON keyword_ops_monthly (owner, process_status);
