DROP VIEW IF EXISTS v_mb_product_selection_funnel;
DROP VIEW IF EXISTS v_mb_product_selection_category_summary;
DROP VIEW IF EXISTS v_mb_product_selection_candidates;

CREATE TABLE IF NOT EXISTS keyword_selection_exclusions (
    id BIGSERIAL PRIMARY KEY,
    term TEXT NOT NULL,
    match_type TEXT NOT NULL DEFAULT 'contains',
    exclusion_type TEXT NOT NULL DEFAULT 'brand',
    reason TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT keyword_selection_exclusions_match_type_check
        CHECK (match_type IN ('contains', 'exact')),
    CONSTRAINT keyword_selection_exclusions_unique_term
        UNIQUE (term, match_type, exclusion_type)
);

CREATE INDEX IF NOT EXISTS idx_keyword_selection_exclusions_active
    ON keyword_selection_exclusions (is_active, exclusion_type);

CREATE OR REPLACE VIEW v_mb_product_selection_candidates AS
WITH base AS (
    SELECT
        m.keyword_id,
        k.keyword_normalized AS keyword,
        m.keyword_translation,
        m.data_month AS analysis_month,
        m.marketplace,
        COALESCE(NULLIF(m.category, ''), '-') AS category,
        m.search_rank,
        m.search_volume,
        m.ppc_bid_low,
        m.ppc_bid_mid,
        m.ppc_bid_high,
        m.spr,
        m.click_share,
        m.conversion_share,
        o.rank_change_mom,
        o.volume_change_mom,
        o.volume_growth_rate_mom,
        o.trend_label,
        CASE o.trend_label
            WHEN 'new' THEN '新出现词'
            WHEN 'rising' THEN '搜索量上升 + 排名改善'
            WHEN 'volume_up_rank_down' THEN '搜索量上升 + 排名下降'
            WHEN 'rank_up_volume_down' THEN '排名改善 + 搜索量下降'
            WHEN 'falling' THEN '搜索量下降 + 排名下降'
            WHEN 'volume_up' THEN '仅搜索量上升'
            WHEN 'volume_down' THEN '仅搜索量下降'
            WHEN 'rank_up' THEN '仅排名改善'
            WHEN 'rank_down' THEN '仅排名下降'
            WHEN 'stable' THEN '稳定词'
            WHEN 'volatile' THEN '波动观察'
            WHEN 'disappeared' THEN '消失'
            WHEN 'seasonal_candidate' THEN '疑似季节词'
            ELSE o.trend_label
        END AS trend_label_cn,
        o.opportunity_score,
        o.competition_score,
        o.conversion_score,
        p1.search_rank AS prev_1m_rank,
        p2.search_rank AS prev_2m_rank,
        p3.search_rank AS prev_3m_rank,
        p1.search_volume AS prev_1m_search_volume,
        p2.search_volume AS prev_2m_search_volume,
        p3.search_volume AS prev_3m_search_volume,
        CASE
            WHEN p1.search_rank IS NULL OR m.search_rank IS NULL THEN NULL
            ELSE p1.search_rank - m.search_rank
        END AS rank_change_1m,
        CASE
            WHEN p3.search_rank IS NULL OR m.search_rank IS NULL THEN NULL
            ELSE p3.search_rank - m.search_rank
        END AS rank_change_3m,
        CASE
            WHEN p1.search_volume IS NULL OR p1.search_volume = 0 OR m.search_volume IS NULL THEN NULL
            ELSE ROUND((m.search_volume - p1.search_volume) / p1.search_volume * 100, 2)
        END AS search_volume_growth_1m_pct,
        CASE
            WHEN p3.search_volume IS NULL OR p3.search_volume = 0 OR m.search_volume IS NULL THEN NULL
            ELSE ROUND((m.search_volume - p3.search_volume) / p3.search_volume * 100, 2)
        END AS search_volume_growth_3m_pct,
        (
            SELECT COUNT(*)
            FROM keyword_monthly_metrics h
            WHERE h.keyword_id = m.keyword_id
              AND h.marketplace = m.marketplace
              AND h.data_month <= m.data_month
        ) AS months_seen_to_date,
        (
            SELECT COUNT(*)
            FROM keyword_monthly_metrics h
            WHERE h.keyword_id = m.keyword_id
              AND h.marketplace = m.marketplace
        ) AS months_seen_total,
        (
            SELECT MIN(h.data_month)
            FROM keyword_monthly_metrics h
            WHERE h.keyword_id = m.keyword_id
              AND h.marketplace = m.marketplace
        ) AS first_seen_month,
        (
            SELECT MAX(h.data_month)
            FROM keyword_monthly_metrics h
            WHERE h.keyword_id = m.keyword_id
              AND h.marketplace = m.marketplace
        ) AS last_seen_month,
        CASE
            WHEN TRIM(k.keyword_normalized) = '' THEN 0
            ELSE LENGTH(TRIM(k.keyword_normalized)) - LENGTH(REPLACE(TRIM(k.keyword_normalized), ' ', '')) + 1
        END AS word_count
    FROM keyword_monthly_metrics m
    JOIN keywords k
      ON k.id = m.keyword_id
    LEFT JOIN keyword_ops_monthly o
      ON o.keyword_id = m.keyword_id
     AND o.marketplace = m.marketplace
     AND o.analysis_month = m.data_month
    LEFT JOIN keyword_monthly_metrics p1
      ON p1.keyword_id = m.keyword_id
     AND p1.marketplace = m.marketplace
     AND p1.data_month = (m.data_month - INTERVAL '1 month')::date
    LEFT JOIN keyword_monthly_metrics p2
      ON p2.keyword_id = m.keyword_id
     AND p2.marketplace = m.marketplace
     AND p2.data_month = (m.data_month - INTERVAL '2 month')::date
    LEFT JOIN keyword_monthly_metrics p3
      ON p3.keyword_id = m.keyword_id
     AND p3.marketplace = m.marketplace
     AND p3.data_month = (m.data_month - INTERVAL '3 month')::date
),
flags AS (
    SELECT
        b.*,
        (b.category ~* '(Kindle|Books|Movies|DVD|Digital Music|Video Games)') AS is_media_category,
        (b.category = '-') AS is_unknown_category,
        EXISTS (
            SELECT 1
            FROM keyword_selection_exclusions e
            WHERE e.is_active
              AND (
                  (e.match_type = 'exact' AND LOWER(b.keyword) = LOWER(e.term))
                  OR
                  (e.match_type = 'contains' AND LOWER(b.keyword) LIKE '%' || LOWER(e.term) || '%')
              )
        ) AS is_manual_excluded
    FROM base b
),
scores AS (
    SELECT
        f.*,
        CASE
            WHEN f.is_media_category OR f.is_manual_excluded THEN 0
            WHEN f.word_count BETWEEN 3 AND 4 THEN 15
            WHEN f.word_count IN (2, 5) THEN 12
            ELSE 0
        END AS intent_score,
        CASE
            WHEN f.search_volume BETWEEN 2000 AND 12000 THEN 20
            WHEN f.search_volume BETWEEN 1000 AND 1999 THEN 14
            WHEN f.search_volume BETWEEN 12001 AND 20000 THEN 12
            WHEN f.search_volume > 20000 THEN 8
            ELSE 0
        END AS demand_score,
        CASE
            WHEN f.trend_label = 'rising' THEN 20
            WHEN f.trend_label = 'volume_up_rank_down' THEN 10
            WHEN f.trend_label = 'rank_up_volume_down' THEN 8
            WHEN f.trend_label IN ('volume_up', 'rank_up') THEN 8
            WHEN f.trend_label = 'stable' THEN 12
            WHEN f.trend_label = 'new' THEN 8
            WHEN f.trend_label = 'volatile' THEN 4
            ELSE 0
        END AS growth_score,
        CASE
            WHEN f.months_seen_total >= 4 THEN 15
            WHEN f.months_seen_total = 3 THEN 12
            WHEN f.months_seen_total = 2 THEN 8
            ELSE 0
        END AS stability_score,
        (
            CASE
                WHEN f.ppc_bid_mid IS NULL THEN 4
                WHEN f.ppc_bid_mid < 0.2 THEN 8
                WHEN f.ppc_bid_mid BETWEEN 0.2 AND 0.8 THEN 10
                WHEN f.ppc_bid_mid > 0.8 AND f.ppc_bid_mid <= 1.2 THEN 8
                WHEN f.ppc_bid_mid > 1.2 AND f.ppc_bid_mid <= 1.5 THEN 5
                ELSE 0
            END
            +
            CASE
                WHEN f.spr IS NULL THEN 3
                WHEN f.spr BETWEEN 1 AND 8 THEN 10
                WHEN f.spr BETWEEN 9 AND 15 THEN 8
                WHEN f.spr BETWEEN 16 AND 20 THEN 4
                ELSE 0
            END
            +
            CASE
                WHEN f.click_share IS NULL THEN 3
                WHEN f.click_share BETWEEN 0.05 AND 0.30 THEN 5
                WHEN f.click_share < 0.05 THEN 3
                ELSE 1
            END
        ) AS competition_access_score,
        CASE
            WHEN f.conversion_share IS NULL THEN 3
            WHEN f.conversion_share BETWEEN 0.02 AND 0.18 THEN 10
            WHEN f.conversion_share > 0.18 AND f.conversion_share <= 0.30 THEN 8
            WHEN f.conversion_share > 0.30 THEN 6
            ELSE 3
        END AS conversion_signal_score
    FROM flags f
)
SELECT
    s.*,
    CASE
        WHEN s.is_media_category THEN '排除-媒体内容'
        WHEN s.is_manual_excluded THEN '排除-人工规则'
        WHEN s.is_unknown_category THEN '待人工判断类目'
        WHEN s.word_count NOT BETWEEN 2 AND 5 THEN '词长不适合'
        WHEN s.search_volume < 1000 THEN '需求偏低'
        WHEN s.search_volume > 20000 THEN '高需求谨慎池'
        WHEN s.trend_label = 'rising' AND s.months_seen_total >= 2 THEN '增长型机会'
        WHEN s.trend_label = 'volume_up_rank_down' THEN '量升但排名下降观察'
        WHEN s.trend_label = 'rank_up_volume_down' THEN '排名改善但需求下降观察'
        WHEN s.months_seen_total >= 4 THEN '稳定型机会'
        WHEN s.trend_label = 'new' THEN '新词观察'
        ELSE '常规候选'
    END AS selection_segment_cn,
    CASE
        WHEN s.search_volume > 20000 THEN '高需求'
        WHEN s.search_volume >= 1000 THEN '可开发需求'
        WHEN s.search_volume >= 300 THEN '小需求测试'
        ELSE '需求过低'
    END AS demand_band_cn,
    CASE
        WHEN s.is_media_category THEN '媒体/书籍/游戏类目不适合作为实物关键词机会'
        WHEN s.is_manual_excluded THEN '命中人工禁用词规则'
        WHEN s.is_unknown_category THEN '类目缺失，需要人工判断'
        WHEN s.word_count NOT BETWEEN 2 AND 5 THEN '词长不适合，产品意图可能过泛或过窄'
        WHEN s.search_volume < 1000 THEN '搜索量不足以作为优先关键词机会'
        WHEN s.search_volume > 20000 THEN '搜索量较高，未排除，但需要单独判断竞争强度'
        ELSE NULL
    END AS exclusion_reason_cn,
    (
        NOT s.is_media_category
        AND NOT s.is_manual_excluded
        AND NOT s.is_unknown_category
        AND s.word_count BETWEEN 2 AND 5
        AND s.search_volume >= 1000
        AND s.months_seen_total >= 2
        AND (s.ppc_bid_mid IS NULL OR s.ppc_bid_mid <= 1.5)
        AND (s.spr IS NULL OR s.spr <= 20)
    ) AS is_product_selection_candidate,
    CASE
        WHEN NOT (
            NOT s.is_media_category
            AND NOT s.is_manual_excluded
            AND NOT s.is_unknown_category
            AND s.word_count BETWEEN 2 AND 5
            AND s.search_volume >= 1000
            AND s.months_seen_total >= 2
            AND (s.ppc_bid_mid IS NULL OR s.ppc_bid_mid <= 1.5)
            AND (s.spr IS NULL OR s.spr <= 20)
        ) THEN LEAST(
            50,
            s.intent_score
            + s.demand_score
            + s.growth_score
            + s.stability_score
            + s.competition_access_score
            + s.conversion_signal_score
        )
        ELSE LEAST(
            100,
            s.intent_score
            + s.demand_score
            + s.growth_score
            + s.stability_score
            + s.competition_access_score
            + s.conversion_signal_score
        )
    END AS product_selection_score,
    CASE
        WHEN s.is_media_category OR s.is_manual_excluded THEN '排除'
        WHEN LEAST(
            100,
            s.intent_score + s.demand_score + s.growth_score + s.stability_score + s.competition_access_score
            + s.conversion_signal_score
        ) >= 85 THEN 'A级'
        WHEN LEAST(
            100,
            s.intent_score + s.demand_score + s.growth_score + s.stability_score + s.competition_access_score
            + s.conversion_signal_score
        ) >= 75 THEN 'B级'
        WHEN LEAST(
            100,
            s.intent_score + s.demand_score + s.growth_score + s.stability_score + s.competition_access_score
            + s.conversion_signal_score
        ) >= 65 THEN 'C级'
        ELSE '观察'
    END AS candidate_level_cn
FROM scores s;

CREATE OR REPLACE VIEW v_mb_product_selection_category_summary AS
SELECT
    analysis_month,
    marketplace,
    category,
    COUNT(*) AS keyword_count,
    COUNT(*) FILTER (WHERE is_product_selection_candidate) AS candidate_count,
    COUNT(*) FILTER (WHERE is_product_selection_candidate AND product_selection_score >= 85) AS level_a_count,
    COUNT(*) FILTER (WHERE is_product_selection_candidate AND trend_label = 'rising' AND months_seen_total >= 2) AS growth_candidate_count,
    COUNT(*) FILTER (WHERE is_product_selection_candidate AND months_seen_total >= 4) AS stable_candidate_count,
    COUNT(*) FILTER (WHERE selection_segment_cn = '待人工判断类目') AS unknown_category_count,
    ROUND(AVG(product_selection_score) FILTER (WHERE is_product_selection_candidate), 2) AS avg_candidate_score,
    ROUND(SUM(search_volume) FILTER (WHERE is_product_selection_candidate), 0) AS candidate_search_volume_sum,
    ROUND(AVG(ppc_bid_mid) FILTER (WHERE is_product_selection_candidate), 2) AS avg_candidate_ppc_mid,
    ROUND(AVG(spr) FILTER (WHERE is_product_selection_candidate), 2) AS avg_candidate_spr
FROM v_mb_product_selection_candidates
GROUP BY analysis_month, marketplace, category;

CREATE OR REPLACE VIEW v_mb_product_selection_funnel AS
SELECT analysis_month, marketplace, 1 AS step_order, '全部关键词' AS step_name_cn, COUNT(*) AS keyword_count
FROM v_mb_product_selection_candidates
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 2, '有可识别类目', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE NOT is_unknown_category
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 3, '排除媒体内容类目', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE NOT is_unknown_category AND NOT is_media_category
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 4, '2-5词产品意图', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE NOT is_unknown_category AND NOT is_media_category AND word_count BETWEEN 2 AND 5
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 5, '搜索量不低于1000', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE NOT is_unknown_category AND NOT is_media_category AND word_count BETWEEN 2 AND 5
  AND search_volume >= 1000
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 6, '至少出现2个月', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE NOT is_unknown_category AND NOT is_media_category AND word_count BETWEEN 2 AND 5
  AND search_volume >= 1000 AND months_seen_total >= 2
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 7, 'PPC/SPR可承受', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE NOT is_unknown_category AND NOT is_media_category AND word_count BETWEEN 2 AND 5
  AND search_volume >= 1000 AND months_seen_total >= 2
  AND (ppc_bid_mid IS NULL OR ppc_bid_mid <= 1.5)
  AND (spr IS NULL OR spr <= 20)
GROUP BY analysis_month, marketplace
UNION ALL
SELECT analysis_month, marketplace, 8, '最终关键词候选', COUNT(*)
FROM v_mb_product_selection_candidates
WHERE is_product_selection_candidate
GROUP BY analysis_month, marketplace;
