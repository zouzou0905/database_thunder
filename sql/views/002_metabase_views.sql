CREATE OR REPLACE VIEW v_mb_keyword_ops AS
SELECT
    o.keyword_id,
    o.keyword,
    m.keyword_translation,
    o.analysis_month,
    o.marketplace,
    o.category,
    o.search_rank,
    o.search_volume,
    o.click_share,
    o.conversion_share,
    o.rank_change_mom,
    o.volume_change_mom,
    o.volume_growth_rate_mom,
    o.avg_rank_3m,
    o.avg_volume_3m,
    o.avg_rank_6m,
    o.avg_volume_6m,
    o.yoy_growth_rate,
    o.trend_label,
    CASE o.trend_label
        WHEN 'new' THEN '新词'
        WHEN 'rising' THEN '上升'
        WHEN 'falling' THEN '下滑'
        WHEN 'stable' THEN '稳定'
        WHEN 'volatile' THEN '波动'
        WHEN 'disappeared' THEN '消失'
        WHEN 'seasonal_candidate' THEN '疑似季节词'
        WHEN 'volume_up_rank_down' THEN '需求升但排名降'
        WHEN 'rank_up_volume_down' THEN '排名升但需求降'
        WHEN 'volume_up' THEN '需求上升'
        WHEN 'volume_down' THEN '需求下降'
        WHEN 'rank_up' THEN '排名上升'
        WHEN 'rank_down' THEN '排名下降'
        ELSE o.trend_label
    END AS trend_label_cn,
    o.keyword_level,
    o.lifecycle_stage,
    o.opportunity_score,
    o.competition_score,
    o.conversion_score,
    o.recommended_action,
    CASE o.recommended_action
        WHEN 'add_to_ads' THEN '加广告'
        WHEN 'increase_budget' THEN '提预算'
        WHEN 'decrease_budget' THEN '降预算'
        WHEN 'add_to_listing' THEN '加入Listing'
        WHEN 'add_to_watchlist' THEN '加入关注'
        WHEN 'observe' THEN '观察'
        WHEN 'discard' THEN '淘汰'
        ELSE o.recommended_action
    END AS recommended_action_cn,
    o.operation_tag,
    o.top1_asin,
    o.top2_asin,
    o.top3_asin,
    o.owner,
    o.process_status,
    o.updated_at
FROM keyword_ops_monthly o
LEFT JOIN keyword_monthly_metrics m
  ON m.keyword_id = o.keyword_id
 AND m.data_month = o.analysis_month
 AND m.marketplace = o.marketplace;

CREATE OR REPLACE VIEW v_mb_month_health AS
SELECT
    COALESCE(m.data_month, o.analysis_month) AS data_month,
    COALESCE(m.marketplace, o.marketplace) AS marketplace,
    COALESCE(m.metrics_count, 0) AS metrics_count,
    COALESCE(o.ops_count, 0) AS ops_count,
    COALESCE(o.new_count, 0) AS new_count,
    COALESCE(o.rising_count, 0) AS rising_count,
    COALESCE(o.falling_count, 0) AS falling_count,
    COALESCE(o.stable_count, 0) AS stable_count,
    COALESCE(o.high_opportunity_count, 0) AS high_opportunity_count,
    COALESCE(o.high_conversion_count, 0) AS high_conversion_count,
    o.avg_opportunity_score,
    o.avg_conversion_score,
    CASE
        WHEN COALESCE(m.metrics_count, 0) < 10000 THEN '疑似不完整'
        ELSE '可分析'
    END AS data_status
FROM (
    SELECT
        data_month,
        marketplace,
        COUNT(*) AS metrics_count
    FROM keyword_monthly_metrics
    GROUP BY data_month, marketplace
) m
FULL JOIN (
    SELECT
        analysis_month,
        marketplace,
        COUNT(*) AS ops_count,
        COUNT(*) FILTER (WHERE trend_label = 'new') AS new_count,
        COUNT(*) FILTER (WHERE trend_label = 'rising') AS rising_count,
        COUNT(*) FILTER (WHERE trend_label = 'falling') AS falling_count,
        COUNT(*) FILTER (WHERE trend_label = 'stable') AS stable_count,
        COUNT(*) FILTER (WHERE opportunity_score >= 80) AS high_opportunity_count,
        COUNT(*) FILTER (WHERE conversion_score >= 80) AS high_conversion_count,
        ROUND(AVG(opportunity_score), 2) AS avg_opportunity_score,
        ROUND(AVG(conversion_score), 2) AS avg_conversion_score
    FROM keyword_ops_monthly
    GROUP BY analysis_month, marketplace
) o
  ON o.analysis_month = m.data_month
 AND o.marketplace = m.marketplace;

CREATE OR REPLACE VIEW v_mb_category_monthly AS
SELECT
    analysis_month,
    marketplace,
    COALESCE(NULLIF(category, ''), '-') AS category,
    COUNT(*) AS keyword_count,
    COUNT(*) FILTER (WHERE trend_label = 'new') AS new_count,
    COUNT(*) FILTER (WHERE trend_label = 'rising') AS rising_count,
    COUNT(*) FILTER (WHERE trend_label = 'falling') AS falling_count,
    COUNT(*) FILTER (WHERE opportunity_score >= 80) AS high_opportunity_count,
    COUNT(*) FILTER (WHERE conversion_score >= 80) AS high_conversion_count,
    ROUND(AVG(opportunity_score), 2) AS avg_opportunity_score,
    ROUND(AVG(conversion_score), 2) AS avg_conversion_score
FROM keyword_ops_monthly
GROUP BY analysis_month, marketplace, COALESCE(NULLIF(category, ''), '-');

CREATE OR REPLACE VIEW v_mb_keyword_4m_compare AS
SELECT
    cur.keyword_id,
    k.keyword_normalized AS keyword,
    cur.keyword_translation,
    cur.data_month AS analysis_month,
    cur.marketplace,
    cur.category,
    cur.search_rank AS current_rank,
    p1.search_rank AS prev_1m_rank,
    p2.search_rank AS prev_2m_rank,
    p3.search_rank AS prev_3m_rank,
    cur.search_volume AS current_search_volume,
    p1.search_volume AS prev_1m_search_volume,
    p2.search_volume AS prev_2m_search_volume,
    p3.search_volume AS prev_3m_search_volume,
    CASE
        WHEN p1.search_rank IS NULL OR cur.search_rank IS NULL THEN NULL
        ELSE p1.search_rank - cur.search_rank
    END AS rank_change_1m,
    CASE
        WHEN p3.search_rank IS NULL OR cur.search_rank IS NULL THEN NULL
        ELSE p3.search_rank - cur.search_rank
    END AS rank_change_3m,
    CASE
        WHEN p1.search_volume IS NULL OR p1.search_volume = 0 OR cur.search_volume IS NULL THEN NULL
        ELSE ROUND((cur.search_volume - p1.search_volume) / p1.search_volume * 100, 2)
    END AS search_volume_growth_1m_pct,
    CASE
        WHEN p3.search_volume IS NULL OR p3.search_volume = 0 OR cur.search_volume IS NULL THEN NULL
        ELSE ROUND((cur.search_volume - p3.search_volume) / p3.search_volume * 100, 2)
    END AS search_volume_growth_3m_pct,
    ops.trend_label,
    ops.trend_label_cn,
    ops.opportunity_score,
    ops.conversion_score,
    ops.recommended_action_cn,
    (p1.keyword_id IS NOT NULL) AS has_prev_1m,
    (p2.keyword_id IS NOT NULL) AS has_prev_2m,
    (p3.keyword_id IS NOT NULL) AS has_prev_3m
FROM keyword_monthly_metrics cur
JOIN keywords k
  ON k.id = cur.keyword_id
LEFT JOIN keyword_monthly_metrics p1
  ON p1.keyword_id = cur.keyword_id
 AND p1.marketplace = cur.marketplace
 AND p1.data_month = (cur.data_month - INTERVAL '1 month')::date
LEFT JOIN keyword_monthly_metrics p2
  ON p2.keyword_id = cur.keyword_id
 AND p2.marketplace = cur.marketplace
 AND p2.data_month = (cur.data_month - INTERVAL '2 month')::date
LEFT JOIN keyword_monthly_metrics p3
  ON p3.keyword_id = cur.keyword_id
 AND p3.marketplace = cur.marketplace
 AND p3.data_month = (cur.data_month - INTERVAL '3 month')::date
LEFT JOIN v_mb_keyword_ops ops
  ON ops.keyword_id = cur.keyword_id
 AND ops.marketplace = cur.marketplace
 AND ops.analysis_month = cur.data_month;
