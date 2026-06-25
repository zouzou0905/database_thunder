CREATE OR REPLACE VIEW v_ops_priority_keywords AS
SELECT *
FROM keyword_ops_monthly
WHERE opportunity_score >= 70
  AND process_status = 'unprocessed'
  AND trend_label IN ('new', 'rising');

CREATE OR REPLACE VIEW v_new_opportunity_keywords AS
SELECT *
FROM keyword_ops_monthly
WHERE trend_label = 'new';

CREATE OR REPLACE VIEW v_rising_keywords AS
SELECT *
FROM keyword_ops_monthly
WHERE trend_label = 'rising';

CREATE OR REPLACE VIEW v_declining_keywords AS
SELECT *
FROM keyword_ops_monthly
WHERE trend_label = 'falling';

CREATE OR REPLACE VIEW v_high_conversion_keywords AS
SELECT *
FROM keyword_ops_monthly
WHERE conversion_score >= 80;

CREATE OR REPLACE VIEW v_asin_keyword_coverage AS
SELECT
    ako.asin,
    ako.keyword_id,
    ako.keyword,
    ako.analysis_month,
    ako.marketplace,
    ako.asin_position,
    ako.click_share,
    ako.conversion_share,
    ako.keyword_search_rank,
    ako.keyword_search_volume,
    ako.is_our_asin,
    ako.product_line,
    ako.brand,
    ako.owner
FROM asin_keyword_ops ako;
