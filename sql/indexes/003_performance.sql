-- Performance indexes for the product-selection cache table.
-- These cover the most common filter + sort patterns used by the operations dashboard.

-- Primary filter + sort: listing candidates by (analysis_month, marketplace) sorted by score
CREATE INDEX IF NOT EXISTS idx_candidates_month_market_score
ON keyword_selection_candidates_monthly (analysis_month, marketplace, product_selection_score DESC);

-- Category drill-down within a month + marketplace
CREATE INDEX IF NOT EXISTS idx_candidates_month_market_category
ON keyword_selection_candidates_monthly (analysis_month, marketplace, category, product_selection_score DESC);

-- Full-text keyword search (ILIKE '%term%') — supports the existing pg_trgm GIN index
-- by adding a composite that includes the commonly co-filtered columns.
-- (The GIN trigram index already exists from 002_trigram.sql for the keyword column;
--  this B-tree index helps when keyword ILIKE is NOT the leading filter.)
CREATE INDEX IF NOT EXISTS idx_candidates_market_month_trend
ON keyword_selection_candidates_monthly (marketplace, analysis_month, trend_label, product_selection_score DESC);

-- Cover sort-by-volume queries
CREATE INDEX IF NOT EXISTS idx_candidates_month_market_volume
ON keyword_selection_candidates_monthly (analysis_month, marketplace, search_volume DESC);

-- Cover sort-by-SPR queries
CREATE INDEX IF NOT EXISTS idx_candidates_month_market_spr
ON keyword_selection_candidates_monthly (analysis_month, marketplace, spr);

-- Cover sort-by-PPC queries
CREATE INDEX IF NOT EXISTS idx_candidates_month_market_ppc
ON keyword_selection_candidates_monthly (analysis_month, marketplace, ppc_bid_mid);
