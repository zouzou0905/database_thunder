from __future__ import annotations

import psycopg


DATABASE_URL = "postgresql://keyword_user:keyword_user_123456@localhost:5432/keyword_trends"


def main() -> None:
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT to_char(data_month, 'YYYY-MM') AS month, marketplace, count(*) AS rows
                FROM keyword_monthly_metrics
                GROUP BY 1, 2
                ORDER BY 1, 2
                """
            )
            print("keyword_monthly_metrics")
            for month, marketplace, rows in cur.fetchall():
                print(f"{month} {marketplace} rows={rows}")

            cur.execute(
                """
                SELECT
                    to_char(data_month, 'YYYY-MM') AS month,
                    status,
                    count(*) AS batches,
                    coalesce(sum(total_files), 0) AS files,
                    coalesce(sum(total_rows), 0) AS rows,
                    coalesce(sum(valid_rows), 0) AS valid
                FROM import_batches
                GROUP BY 1, 2
                ORDER BY 1, 2
                """
            )
            print("import_batches")
            for month, status, batches, files, rows, valid in cur.fetchall():
                print(f"{month} {status} batches={batches} files={files} rows={rows} valid={valid}")


if __name__ == "__main__":
    main()
