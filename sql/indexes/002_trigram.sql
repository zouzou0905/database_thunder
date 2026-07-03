-- Enable the pg_trgm extension for fuzzy text search.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- GIN trigram index on the keywords master table to accelerate ILIKE '%term%' searches.
-- A standard B-tree index cannot accelerate leading-wildcard patterns;
-- pg_trgm GIN indexes are purpose-built for this.
CREATE INDEX IF NOT EXISTS idx_keywords_trgm
    ON keywords USING GIN (keyword_normalized gin_trgm_ops);

