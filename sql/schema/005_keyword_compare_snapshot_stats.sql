-- Add statistical columns to keyword_compare_snapshot for the 5-category
-- reclassification (常年稳定型/季节型/上升型/下降型/波动型).
--
-- These are computed from the monthly JSONB column using PostgreSQL aggregates
-- (REGR_SLOPE, REGR_R2, STDDEV) during snapshot refresh Step 6.5.

ALTER TABLE keyword_compare_snapshot
    ADD COLUMN IF NOT EXISTS avg_search_volume     NUMERIC,
    ADD COLUMN IF NOT EXISTS stddev_search_volume  NUMERIC,
    ADD COLUMN IF NOT EXISTS cv_search_volume      NUMERIC,
    ADD COLUMN IF NOT EXISTS volume_slope          NUMERIC,
    ADD COLUMN IF NOT EXISTS volume_r2             NUMERIC,
    ADD COLUMN IF NOT EXISTS gap_count             INTEGER;

COMMENT ON COLUMN keyword_compare_snapshot.avg_search_volume
    IS 'Mean search volume across months where the keyword appeared';

COMMENT ON COLUMN keyword_compare_snapshot.stddev_search_volume
    IS 'Standard deviation of monthly search volume';

COMMENT ON COLUMN keyword_compare_snapshot.cv_search_volume
    IS 'Coefficient of variation (stddev / mean) — lower = more stable';

COMMENT ON COLUMN keyword_compare_snapshot.volume_slope
    IS 'Linear regression slope — per-month volume change (positive = growing)';

COMMENT ON COLUMN keyword_compare_snapshot.volume_r2
    IS 'R-squared of linear fit — how linear the trend is (0–1)';

COMMENT ON COLUMN keyword_compare_snapshot.gap_count
    IS 'Number of months in the full range where this keyword had no data';
