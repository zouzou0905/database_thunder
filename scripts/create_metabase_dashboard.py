from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from getpass import getpass
from typing import Any


@dataclass
class MetabaseClient:
    base_url: str
    session_id: str | None = None

    def request(self, method: str, path: str, payload: dict | None = None) -> Any:
        url = f"{self.base_url.rstrip('/')}{path}"
        data = None
        headers = {"Content-Type": "application/json"}
        if self.session_id:
            headers["X-Metabase-Session"] = self.session_id
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8")
                return json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {path} failed: HTTP {exc.code} {body}") from exc

    def login(self, email: str, password: str) -> None:
        result = self.request("POST", "/api/session", {"username": email, "password": password})
        self.session_id = result["id"]


def find_keyword_database(client: MetabaseClient, name_hint: str | None = None) -> int:
    result = client.request("GET", "/api/database")
    databases = result.get("data", result if isinstance(result, list) else [])
    if name_hint:
        for db in databases:
            if db.get("name") == name_hint:
                return db["id"]
    for db in databases:
        if "keyword" in db.get("name", "").lower() or "关键词" in db.get("name", ""):
            return db["id"]
    if len(databases) == 1:
        return databases[0]["id"]
    names = ", ".join(db.get("name", "<unnamed>") for db in databases)
    raise RuntimeError(f"Cannot identify keyword database. Use --database-name. Available: {names}")


def create_native_card(
    client: MetabaseClient,
    database_id: int,
    name: str,
    query: str,
    display: str,
    visualization_settings: dict | None = None,
) -> int:
    payload = {
        "name": name,
        "dataset_query": {
            "database": database_id,
            "type": "native",
            "native": {
                "query": query,
                "template-tags": {},
            },
        },
        "display": display,
        "visualization_settings": visualization_settings or {},
    }
    result = client.request("POST", "/api/card", payload)
    return result["id"]


def create_dashboard(client: MetabaseClient, name: str, description: str) -> int:
    result = client.request(
        "POST",
        "/api/dashboard",
        {
            "name": name,
            "description": description,
        },
    )
    return result["id"]


def update_dashboard_cards(
    client: MetabaseClient,
    dashboard_id: int,
    name: str,
    description: str,
    dashcards: list[dict],
) -> None:
    payload = {
        "name": name,
        "description": description,
        "dashcards": dashcards,
    }
    client.request("PUT", f"/api/dashboard/{dashboard_id}", payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the initial keyword Metabase dashboard.")
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
            "各月关键词数量",
            """
            SELECT data_month, metrics_count
            FROM v_mb_month_health
            ORDER BY data_month
            """,
            "line",
            {"graph.dimensions": ["data_month"], "graph.metrics": ["metrics_count"]},
            0,
            0,
            12,
            7,
        ),
        (
            "各月趋势分布",
            """
            SELECT data_month, new_count, rising_count, falling_count, stable_count
            FROM v_mb_month_health
            ORDER BY data_month
            """,
            "bar",
            {
                "graph.dimensions": ["data_month"],
                "graph.metrics": ["new_count", "rising_count", "falling_count", "stable_count"],
                "stackable.stack_type": "stacked",
            },
            12,
            0,
            12,
            7,
        ),
        (
            "各月高机会词数量",
            """
            SELECT data_month, high_opportunity_count
            FROM v_mb_month_health
            ORDER BY data_month
            """,
            "bar",
            {"graph.dimensions": ["data_month"], "graph.metrics": ["high_opportunity_count"]},
            0,
            7,
            8,
            6,
        ),
        (
            "各月高转化词数量",
            """
            SELECT data_month, high_conversion_count
            FROM v_mb_month_health
            ORDER BY data_month
            """,
            "bar",
            {"graph.dimensions": ["data_month"], "graph.metrics": ["high_conversion_count"]},
            8,
            7,
            8,
            6,
        ),
        (
            "月份数据健康明细",
            """
            SELECT
                data_month,
                marketplace,
                metrics_count,
                ops_count,
                new_count,
                rising_count,
                falling_count,
                high_opportunity_count,
                high_conversion_count,
                avg_opportunity_score,
                avg_conversion_score,
                data_status
            FROM v_mb_month_health
            ORDER BY data_month DESC
            """,
            "table",
            {},
            0,
            13,
            24,
            8,
        ),
        (
            "最新月份高机会关键词 Top 100",
            """
            SELECT
                keyword,
                keyword_translation,
                analysis_month,
                category,
                search_rank,
                search_volume,
                trend_label_cn,
                opportunity_score,
                conversion_score,
                recommended_action_cn
            FROM v_mb_keyword_ops
            WHERE analysis_month = (SELECT MAX(data_month) FROM v_mb_month_health)
            ORDER BY opportunity_score DESC NULLS LAST, search_volume DESC NULLS LAST
            LIMIT 100
            """,
            "table",
            {},
            0,
            21,
            24,
            10,
        ),
    ]

    dashboard_name = "关键词数据健康总览"
    dashboard_description = "用于检查各月份数据完整度、趋势分布和初步高机会关键词。"
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
    try:
        main()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise
