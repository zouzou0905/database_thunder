-- Query coverage indexes for the operational list views.
-- Keep these aligned with ORDER BY ... DESC NULLS LAST in the API.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;

-- Keyword horizontal compare: full-range snapshot.
CREATE INDEX IF NOT EXISTS idx_compare_snapshot_growth_order
    ON keyword_compare_snapshot (
        marketplace,
        search_volume_growth_rate DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_volume_order
    ON keyword_compare_snapshot (
        marketplace,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_rank_change_order
    ON keyword_compare_snapshot (
        marketplace,
        rank_change DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_volume_change_order
    ON keyword_compare_snapshot (
        marketplace,
        search_volume_change DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_month_count_order
    ON keyword_compare_snapshot (
        marketplace,
        month_count DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_ppc_filter
    ON keyword_compare_snapshot (marketplace, ppc_bid_mid);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_spr_filter
    ON keyword_compare_snapshot (marketplace, spr);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_market_keyword_trgm
    ON keyword_compare_snapshot USING GIN (marketplace, keyword gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_compare_snapshot_market_translation_trgm
    ON keyword_compare_snapshot USING GIN (marketplace, keyword_translation gin_trgm_ops);

-- Keyword horizontal compare: on-demand range cache.
CREATE INDEX IF NOT EXISTS idx_compare_range_cache_growth_order
    ON keyword_compare_range_cache (
        marketplace,
        start_month,
        end_month,
        search_volume_growth_rate DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_volume_order
    ON keyword_compare_range_cache (
        marketplace,
        start_month,
        end_month,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_rank_change_order
    ON keyword_compare_range_cache (
        marketplace,
        start_month,
        end_month,
        rank_change DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_volume_change_order
    ON keyword_compare_range_cache (
        marketplace,
        start_month,
        end_month,
        search_volume_change DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_month_count_order
    ON keyword_compare_range_cache (
        marketplace,
        start_month,
        end_month,
        month_count DESC NULLS LAST,
        end_search_volume DESC NULLS LAST,
        keyword
    );

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_ppc_filter
    ON keyword_compare_range_cache (marketplace, start_month, end_month, ppc_bid_mid);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_spr_filter
    ON keyword_compare_range_cache (marketplace, start_month, end_month, spr);

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_range_keyword_trgm
    ON keyword_compare_range_cache USING GIN (
        marketplace,
        start_month,
        end_month,
        keyword gin_trgm_ops
    );

CREATE INDEX IF NOT EXISTS idx_compare_range_cache_range_translation_trgm
    ON keyword_compare_range_cache USING GIN (
        marketplace,
        start_month,
        end_month,
        keyword_translation gin_trgm_ops
    );

-- Product-selection cache list sorting and filters.
CREATE INDEX IF NOT EXISTS idx_selection_cache_score_order
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        product_selection_score DESC NULLS LAST,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_volume_order
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_rank_order
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        search_rank DESC NULLS LAST,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_months_seen_order
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        months_seen_to_date DESC NULLS LAST,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_ppc_order
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        ppc_bid_mid DESC NULLS LAST,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_spr_order
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        spr DESC NULLS LAST,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_segment_score
    ON keyword_selection_candidates_monthly (
        analysis_month,
        marketplace,
        selection_segment_cn,
        product_selection_score DESC NULLS LAST,
        search_volume DESC NULLS LAST
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_month_market_keyword_trgm
    ON keyword_selection_candidates_monthly USING GIN (
        analysis_month,
        marketplace,
        keyword gin_trgm_ops
    );

CREATE INDEX IF NOT EXISTS idx_selection_cache_month_market_translation_trgm
    ON keyword_selection_candidates_monthly USING GIN (
        analysis_month,
        marketplace,
        keyword_translation gin_trgm_ops
    );
