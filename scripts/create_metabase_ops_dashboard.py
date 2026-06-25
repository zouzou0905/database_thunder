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
    parser = argparse.ArgumentParser(description="Create an operational keyword list dashboard in Metabase.")
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
            "本月运营优先词 Top 100",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_rank AS "当前排名",
                search_volume AS "搜索量",
                trend_label_cn AS "趋势",
                ROUND(opportunity_score, 2) AS "机会分",
                ROUND(conversion_score, 2) AS "转化分",
                recommended_action_cn AS "建议动作"
            FROM v_mb_keyword_ops
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND opportunity_score >= 70
            ORDER BY opportunity_score DESC NULLS LAST, search_volume DESC NULLS LAST
            LIMIT 100
            """,
            0,
            0,
            24,
            9,
        ),
        (
            "本月上升词：适合广告测试 / Listing 扩词",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_rank AS "当前排名",
                search_volume AS "搜索量",
                rank_change_mom AS "排名提升",
                ROUND(volume_growth_rate_mom * 100, 2) AS "搜索量增长%",
                ROUND(opportunity_score, 2) AS "机会分",
                recommended_action_cn AS "建议动作"
            FROM v_mb_keyword_ops
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND trend_label = 'rising'
            ORDER BY opportunity_score DESC NULLS LAST, search_volume DESC NULLS LAST
            LIMIT 100
            """,
            0,
            9,
            24,
            9,
        ),
        (
            "本月下滑风险词：优先排查高搜索量",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_rank AS "当前排名",
                search_volume AS "搜索量",
                rank_change_mom AS "排名变化",
                ROUND(volume_growth_rate_mom * 100, 2) AS "搜索量变化%",
                ROUND(opportunity_score, 2) AS "机会分",
                recommended_action_cn AS "建议动作"
            FROM v_mb_keyword_ops
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND trend_label = 'falling'
            ORDER BY search_volume DESC NULLS LAST, opportunity_score DESC NULLS LAST
            LIMIT 100
            """,
            0,
            18,
            24,
            9,
        ),
        (
            "疑似新机会词：近两个月未出现",
            """
            SELECT
                o.keyword AS "关键词",
                o.keyword_translation AS "中文释义",
                o.category AS "类目",
                o.search_rank AS "当前排名",
                o.search_volume AS "搜索量",
                ROUND(o.opportunity_score, 2) AS "机会分",
                ROUND(o.conversion_score, 2) AS "转化分",
                o.recommended_action_cn AS "建议动作"
            FROM v_mb_keyword_ops o
            WHERE o.analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND NOT EXISTS (
                  SELECT 1
                  FROM keyword_monthly_metrics p
                  WHERE p.keyword_id = o.keyword_id
                    AND p.marketplace = o.marketplace
                    AND p.data_month IN (
                        (o.analysis_month - INTERVAL '1 month')::date,
                        (o.analysis_month - INTERVAL '2 month')::date
                    )
              )
            ORDER BY o.search_volume DESC NULLS LAST, o.opportunity_score DESC NULLS LAST
            LIMIT 100
            """,
            0,
            27,
            24,
            9,
        ),
        (
            "高转化可埋词：适合标题 / 五点 / 描述候选",
            """
            SELECT
                keyword AS "关键词",
                keyword_translation AS "中文释义",
                category AS "类目",
                search_rank AS "当前排名",
                search_volume AS "搜索量",
                trend_label_cn AS "趋势",
                ROUND(conversion_score, 2) AS "转化分",
                ROUND(opportunity_score, 2) AS "机会分",
                recommended_action_cn AS "建议动作"
            FROM v_mb_keyword_ops
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
              AND conversion_score >= 90
              AND search_volume >= 1000
            ORDER BY conversion_score DESC NULLS LAST, search_volume DESC NULLS LAST
            LIMIT 100
            """,
            0,
            36,
            24,
            9,
        ),
        (
            "类目机会汇总：看哪个类目值得先分配运营",
            """
            SELECT
                category AS "类目",
                keyword_count AS "关键词数",
                rising_count AS "上升词",
                falling_count AS "下滑词",
                high_opportunity_count AS "高机会词",
                high_conversion_count AS "高转化词",
                avg_opportunity_score AS "平均机会分",
                avg_conversion_score AS "平均转化分"
            FROM v_mb_category_monthly
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
            ORDER BY high_opportunity_count DESC, keyword_count DESC
            LIMIT 50
            """,
            0,
            45,
            24,
            8,
        ),
    ]

    dashboard_name = "关键词运营实用清单"
    dashboard_description = "给运营使用的关键词行动清单，重点展示可筛选、可处理、可导出的关键词数据。"
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
