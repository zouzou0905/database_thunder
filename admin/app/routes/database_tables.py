from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from psycopg import Connection

from admin.app.core.auth import get_current_admin
from admin.app.core.config import get_admin_settings
from admin.app.db import get_connection

router = APIRouter(prefix="/admin/database-tables", tags=["admin-database-tables"])
templates = Jinja2Templates(directory=str(get_admin_settings().templates_dir))


@router.get("")
def database_tables(
    request: Request,
    admin=Depends(get_current_admin),
    conn: Connection = Depends(get_connection),
):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                n.nspname AS schema_name,
                c.relname AS table_name,
                CASE c.relkind
                    WHEN 'p' THEN 'partitioned'
                    ELSE 'table'
                END AS table_type,
                GREATEST(COALESCE(s.n_live_tup, c.reltuples, 0), 0)::bigint AS approx_rows,
                COALESCE(s.n_dead_tup, 0)::bigint AS dead_rows,
                pg_relation_size(c.oid) AS table_bytes,
                pg_indexes_size(c.oid) AS index_bytes,
                pg_total_relation_size(c.oid) AS total_bytes,
                pg_size_pretty(pg_relation_size(c.oid)) AS table_size,
                pg_size_pretty(pg_indexes_size(c.oid)) AS index_size,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                s.last_analyze,
                s.last_autoanalyze
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE c.relkind IN ('r', 'p')
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
              AND n.nspname NOT LIKE 'pg_toast%'
            ORDER BY pg_total_relation_size(c.oid) DESC, n.nspname, c.relname
            """
        )
        tables = cur.fetchall()

    total_rows = sum(int(row["approx_rows"] or 0) for row in tables)
    total_bytes = sum(int(row["total_bytes"] or 0) for row in tables)
    total_table_bytes = sum(int(row["table_bytes"] or 0) for row in tables)
    total_index_bytes = sum(int(row["index_bytes"] or 0) for row in tables)

    return templates.TemplateResponse(
        request,
        "database_tables/list.html",
        {
            "admin": admin,
            "tables": tables,
            "table_count": len(tables),
            "total_rows": total_rows,
            "total_size": _format_bytes(total_bytes),
            "total_table_size": _format_bytes(total_table_bytes),
            "total_index_size": _format_bytes(total_index_bytes),
        },
    )


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024
    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"
