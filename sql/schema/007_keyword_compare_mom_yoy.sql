-- Add 环比 (MoM) and 同比 (YoY) columns to snapshot and range cache tables.

ALTER TABLE keyword_compare_snapshot
    ADD COLUMN IF NOT EXISTS prev_month_search_volume NUMERIC,
    ADD COLUMN IF NOT EXISTS yoy_search_volume NUMERIC,
    ADD COLUMN IF NOT EXISTS mom_change NUMERIC,
    ADD COLUMN IF NOT EXISTS mom_rate NUMERIC,
    ADD COLUMN IF NOT EXISTS yoy_change NUMERIC,
    ADD COLUMN IF NOT EXISTS yoy_rate NUMERIC;

ALTER TABLE keyword_compare_range_cache
    ADD COLUMN IF NOT EXISTS prev_month_search_volume NUMERIC,
    ADD COLUMN IF NOT EXISTS yoy_search_volume NUMERIC,
    ADD COLUMN IF NOT EXISTS mom_change NUMERIC,
    ADD COLUMN IF NOT EXISTS mom_rate NUMERIC,
    ADD COLUMN IF NOT EXISTS yoy_change NUMERIC,
    ADD COLUMN IF NOT EXISTS yoy_rate NUMERIC;
