from __future__ import annotations

from pathlib import Path

import psycopg

from common import get_database_url


SQL_FILES = [
    "sql/schema/001_core.sql",
    "sql/schema/002_app.sql",
    "sql/schema/003_product_selection_cache.sql",
    "sql/indexes/001_indexes.sql",
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
