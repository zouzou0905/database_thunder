from __future__ import annotations

import os

import psycopg
from psycopg import sql


def main() -> None:
    admin_user = os.environ.get("PG_ADMIN_USER", "postgres")
    admin_password = os.environ["PG_ADMIN_PASSWORD"]
    host = os.environ.get("PG_HOST", "localhost")
    port = os.environ.get("PG_PORT", "5432")
    app_db = os.environ.get("APP_DB_NAME", "keyword_trends")
    app_user = os.environ.get("APP_DB_USER", "keyword_user")
    app_password = os.environ["APP_DB_PASSWORD"]

    admin_url = f"postgresql://{admin_user}:{admin_password}@{host}:{port}/postgres"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [app_user])
            role_exists = cur.fetchone() is not None
            if role_exists:
                cur.execute(
                    sql.SQL("ALTER USER {} WITH PASSWORD {}").format(
                        sql.Identifier(app_user),
                        sql.Literal(app_password),
                    )
                )
            else:
                cur.execute(
                    sql.SQL("CREATE USER {} WITH PASSWORD {}").format(
                        sql.Identifier(app_user),
                        sql.Literal(app_password),
                    )
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", [app_db])
            db_exists = cur.fetchone() is not None
            if not db_exists:
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(app_db),
                        sql.Identifier(app_user),
                    )
                )

    app_url = f"postgresql://{app_user}:{app_password}@{host}:{port}/{app_db}"
    with psycopg.connect(app_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    print(f"PostgreSQL ready: database={app_db} user={app_user}")


if __name__ == "__main__":
    main()
