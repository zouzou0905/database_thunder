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
    parser = argparse.ArgumentParser(description="Create a keyword month-over-month comparison dashboard in Metabase.")
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--email", required=True, help="Metabase admin email.")
    parser.add_argument("--password", help="Metabase admin password. Omit to prompt securely.")
    parser.add_argument("--database-name", help="Metabase display name for the PostgreSQL database.")
    args = parser.parse_args()

    password = args.password or getpass("Metabase password: ")
    client = MetabaseClient(args.url)
    client.login(args.email, password)
    database_id = find_keyword_database(client, args.database_name)

    cards = [
        (
            "最近4个月关键词横向对比：排名",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                analysis_month AS "当前月",
                current_rank AS "当前排名",
                prev_1m_rank AS "上月排名",
                prev_2m_rank AS "前2月排名",
                prev_3m_rank AS "前3月排名",
                rank_change_1m AS "近1月排名提升",
                rank_change_3m AS "近3月排名提升",
                trend_label_cn AS "趋势",
                ROUND(opportunity_score, 2) AS "机会分"
            FROM v_mb_keyword_4m_compare
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND has_prev_1m
            ORDER BY ABS(rank_change_1m) DESC NULLS LAST
            LIMIT 200
            """,
            0,
            0,
            24,
            10,
        ),
        (
            "最近4个月关键词横向对比：搜索量",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                analysis_month AS "当前月",
                current_search_volume AS "当前搜索量",
                prev_1m_search_volume AS "上月搜索量",
                prev_2m_search_volume AS "前2月搜索量",
                prev_3m_search_volume AS "前3月搜索量",
                search_volume_growth_1m_pct AS "近1月增长%",
                search_volume_growth_3m_pct AS "近3月增长%",
                trend_label_cn AS "趋势",
                ROUND(opportunity_score, 2) AS "机会分"
            FROM v_mb_keyword_4m_compare
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND has_prev_1m
            ORDER BY ABS(search_volume_growth_1m_pct) DESC NULLS LAST
            LIMIT 200
            """,
            0,
            10,
            24,
            10,
        ),
        (
            "连续4个月都出现的关键词",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                current_rank AS "当前排名",
                prev_1m_rank AS "上月排名",
                prev_2m_rank AS "前2月排名",
                prev_3m_rank AS "前3月排名",
                current_search_volume AS "当前搜索量",
                prev_1m_search_volume AS "上月搜索量",
                prev_2m_search_volume AS "前2月搜索量",
                prev_3m_search_volume AS "前3月搜索量",
                trend_label_cn AS "趋势",
                ROUND(opportunity_score, 2) AS "机会分",
                recommended_action_cn AS "建议动作"
            FROM v_mb_keyword_4m_compare
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND has_prev_1m
              AND has_prev_2m
              AND has_prev_3m
            ORDER BY opportunity_score DESC NULLS LAST, current_search_volume DESC NULLS LAST
            LIMIT 200
            """,
            0,
            20,
            24,
            10,
        ),
    ]

    dashboard_name = "关键词月份横向对比"
    dashboard_description = "把同一个关键词在当前月、上月、前2月、前3月的排名和搜索量放在一张表里横向对比。"
    dashboard_id = create_dashboard(client, dashboard_name, dashboard_description)

    dashcards = []
    for index, (name, query, col, row, size_x, size_y) in enumerate(cards, start=1):
        card_id = create_native_card(client, database_id, name, query, "table", {})
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
