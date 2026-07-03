from __future__ import annotations

from pathlib import Path

import psycopg

from common import get_database_url


SQL_FILES = [
    "sql/schema/001_core.sql",
    "sql/schema/002_app.sql",
    "sql/schema/003_product_selection_cache.sql",
    "sql/schema/004_keyword_compare_snapshot.sql",
    "sql/schema/005_keyword_compare_snapshot_stats.sql",
    "sql/schema/006_keyword_compare_range_cache.sql",
    "sql/schema/007_keyword_compare_mom_yoy.sql",
    "sql/schema/008_error_logs.sql",
    "sql/schema/009_login_history.sql",
    "sql/schema/010_holiday_lexicon.sql",
    "sql/schema/011_keyword_holiday_tags.sql",
    "sql/indexes/001_indexes.sql",
    "sql/indexes/002_trigram.sql",
    "sql/indexes/003_performance.sql",
    "sql/indexes/004_query_coverage.sql",
    "sql/views/001_ops_views.sql",
    "sql/views/002_metabase_views.sql",
    "sql/views/003_product_selection_views.sql",
]


def main() -> None:
    database_url = get_database_url()
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for file_name in SQL_FILES:
                sql_path = Path(file_name)
                cur.execute(sql_path.read_text(encoding="utf-8"))
        conn.commit()
    print("Database schema initialized.")


if __name__ == "__main__":
    main()
