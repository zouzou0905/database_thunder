from __future__ import annotations

import argparse
from getpass import getpass

from create_metabase_dashboard import (
    MetabaseClient,
    create_dashboard,
    create_native_card,
    find_keyword_database,
    update_dashboard_cards,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a product-selection dashboard in Metabase.")
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--email", required=True, help="Metabase admin email.")
    parser.add_argument("--password", help="Metabase admin password. Omit to prompt securely.")
    parser.add_argument("--database-name", help="Metabase display name for the PostgreSQL database.")
    args = parser.parse_args()

    password = args.password or getpass("Metabase password: ")
    client = MetabaseClient(args.url)
    client.login(args.email, password)
    database_id = find_keyword_database(client, args.database_name)

    latest_month = "(SELECT MAX(data_month) FROM keyword_monthly_metrics)"
    cards = [
        (
            "选品漏斗：本月从全部关键词筛到候选池",
            f"""
            SELECT
                step_order AS "步骤",
                step_name_cn AS "筛选步骤",
                keyword_count AS "关键词数"
            FROM v_mb_product_selection_funnel
            WHERE analysis_month = {latest_month}
            ORDER BY step_order
            """,
            "table",
            {},
            0,
            0,
            10,
            8,
        ),
        (
            "类目选品机会排行",
            f"""
            SELECT
                category AS "类目",
                candidate_count AS "最终候选词",
                level_a_count AS "A级候选",
                growth_candidate_count AS "增长型",
                stable_candidate_count AS "稳定型",
                avg_candidate_score AS "平均选品分",
                candidate_search_volume_sum AS "候选词搜索量合计",
                avg_candidate_ppc_mid AS "平均PPC中位价",
                avg_candidate_spr AS "平均SPR"
            FROM v_mb_product_selection_category_summary
            WHERE analysis_month = {latest_month}
              AND candidate_count > 0
            ORDER BY candidate_count DESC, level_a_count DESC
            LIMIT 50
            """,
            "table",
            {},
            10,
            0,
            14,
            8,
        ),
        (
            "本月选品候选清单 Top 200",
            f"""
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_rank AS "搜索排名",
                search_volume AS "搜索量",
                months_seen_to_date AS "已出现月数",
                trend_label_cn AS "趋势",
                selection_segment_cn AS "选品类型",
                candidate_level_cn AS "候选等级",
                product_selection_score AS "选品分",
                ppc_bid_mid AS "PPC中位价",
                spr AS "SPR",
                click_share AS "点击份额",
                conversion_share AS "转化份额"
            FROM v_mb_product_selection_candidates
            WHERE analysis_month = {latest_month}
              AND is_product_selection_candidate
            ORDER BY product_selection_score DESC, search_volume DESC
            LIMIT 200
            """,
            "table",
            {},
            0,
            8,
            24,
            10,
        ),
        (
            "增长型选品机会：适合优先调研",
            f"""
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_volume AS "搜索量",
                months_seen_to_date AS "已出现月数",
                search_volume_growth_1m_pct AS "搜索量环比%",
                rank_change_1m AS "排名提升",
                product_selection_score AS "选品分",
                ppc_bid_mid AS "PPC中位价",
                spr AS "SPR",
                click_share AS "点击份额",
                conversion_share AS "转化份额"
            FROM v_mb_product_selection_candidates
            WHERE analysis_month = {latest_month}
              AND is_product_selection_candidate
              AND trend_label = 'rising'
            ORDER BY product_selection_score DESC, search_volume DESC
            LIMIT 150
            """,
            "table",
            {},
            0,
            18,
            24,
            9,
        ),
        (
            "稳定型选品机会：适合做长期需求池",
            f"""
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_volume AS "搜索量",
                months_seen_to_date AS "已出现月数",
                prev_1m_search_volume AS "上月搜索量",
                prev_2m_search_volume AS "前2月搜索量",
                prev_3m_search_volume AS "前3月搜索量",
                product_selection_score AS "选品分",
                ppc_bid_mid AS "PPC中位价",
                spr AS "SPR"
            FROM v_mb_product_selection_candidates
            WHERE analysis_month = {latest_month}
              AND is_product_selection_candidate
              AND months_seen_to_date >= 4
            ORDER BY product_selection_score DESC, search_volume DESC
            LIMIT 150
            """,
            "table",
            {},
            0,
            27,
            24,
            9,
        ),
        (
            "待人工判断类目：可能有机会，但需要先补类目",
            f"""
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                search_volume AS "搜索量",
                word_count AS "词数",
                months_seen_to_date AS "已出现月数",
                trend_label_cn AS "趋势",
                demand_band_cn AS "需求层级",
                product_selection_score AS "选品分",
                ppc_bid_mid AS "PPC中位价",
                spr AS "SPR",
                exclusion_reason_cn AS "原因"
            FROM v_mb_product_selection_candidates
            WHERE analysis_month = {latest_month}
              AND is_unknown_category
              AND NOT is_media_category
              AND word_count BETWEEN 2 AND 5
              AND search_volume >= 1000
            ORDER BY search_volume DESC, product_selection_score DESC
            LIMIT 150
            """,
            "table",
            {},
            0,
            36,
            24,
            9,
        ),
        (
            "人工排除词维护表：品牌词/不选品词",
            """
            SELECT
                term AS "词根",
                match_type AS "匹配方式",
                exclusion_type AS "排除类型",
                reason AS "原因",
                is_active AS "是否启用",
                updated_at AS "更新时间"
            FROM keyword_selection_exclusions
            ORDER BY updated_at DESC, term
            LIMIT 200
            """,
            "table",
            {},
            0,
            45,
            24,
            6,
        ),
    ]

    dashboard_name = "选品机会池"
    dashboard_description = "围绕选品开发设计的关键词候选池：先看漏斗和类目，再进入可排序、可筛选、可导出的候选清单。"
    dashboard_id = create_dashboard(client, dashboard_name, dashboard_description)

    dashcards = []
    for index, (name, query, display, settings, col, row, size_x, size_y) in enumerate(cards, start=1):
        card_id = create_native_card(client, database_id, name, query, display, settings)
        dashcards.append(
            {
                "id": -index,
                "card_id": card_id,
                "row": row,
                "col": col,
                "size_x": size_x,
                "size_y": size_y,
                "visualization_settings": {},
                "parameter_mappings": [],
            }
        )
        print(f"Created card: {name}")

    update_dashboard_cards(client, dashboard_id, dashboard_name, dashboard_description, dashcards)
    print(f"Dashboard created: {args.url.rstrip('/')}/dashboard/{dashboard_id}")


if __name__ == "__main__":
    main()
